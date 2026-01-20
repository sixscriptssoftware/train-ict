"""
Vex - Autonomous ICT Trading Agent

The brain that runs independently.
Scans for setups, checks risk, executes, and journals.

Built to trade like an ICT practitioner - patient, precise, disciplined.

Name: Vex
Role: Ashton's accountability partner & autonomous trader
"""

import os
import sys
import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from enum import Enum

from ict_agent.data.oanda_fetcher import get_oanda_data, get_current_price
from ict_agent.engine.killzone import KillzoneManager
from ict_agent.engine.asian_range import AsianRangeCalculator
from ict_agent.engine.signal_generator import SignalGenerator, ModelType
from ict_agent.detectors.market_structure import MarketStructureAnalyzer
from ict_agent.detectors.fvg import FVGDetector
from ict_agent.detectors.order_block import OrderBlockDetector
from ict_agent.detectors.liquidity import LiquidityDetector
from ict_agent.models.turtle_soup import TurtleSoupDetector
from ict_agent.models.market_maker_model import MarketMakerModelDetector
from ict_agent.execution.oanda_executor import OANDAExecutor, OrderType
from ict_agent.execution.risk_guardian import RiskGuardian
from ict_agent.execution.agent_journal import AgentJournal


NY_TZ = ZoneInfo("America/New_York")


class AgentState(Enum):
    IDLE = "idle"               # Waiting for next scan cycle
    SCANNING = "scanning"       # Looking for setups
    ANALYZING = "analyzing"     # Deep analysis of potential setup
    WAITING = "waiting"         # Waiting for entry trigger
    EXECUTING = "executing"     # Placing trade
    MONITORING = "monitoring"   # Watching open positions
    SHUTDOWN = "shutdown"       # Stopped trading (risk limit hit)


@dataclass
class TradingSetup:
    """A potential trading setup"""
    symbol: str
    direction: str  # "BUY" or "SELL"
    model: str      # Which ICT model
    timeframe: str
    
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    
    confluences: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    description: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(NY_TZ))
    
    # Entry type
    entry_type: str = "market"  # "market", "limit", "stop"
    limit_price: float = 0.0


class AutonomousTrader:
    """
    I am the Agent.
    
    I watch the markets. I wait for ICT setups.
    When the time is right, I strike.
    
    I am patient. I am disciplined. I am profitable.
    """
    
    def __init__(
        self,
        account_id: str,
        api_key: str,
        environment: str = "practice",  # practice = demo, live = real
        symbols: List[str] = None,
        base_account_balance: float = 10000.0,
    ):
        self.symbols = symbols or ["EUR_USD", "GBP_USD", "XAU_USD", "USD_JPY", "AUD_USD", "EUR_GBP"]
        self.account_id = account_id
        self.environment = environment
        self.base_balance = base_account_balance
        
        # State
        self.state = AgentState.IDLE
        self.running = False
        self.current_setups: List[TradingSetup] = []
        
        # Components
        self.executor = OANDAExecutor(
            api_key=api_key,
            account_id=account_id,
            environment=environment
        )
        
        # Risk configuration
        from ict_agent.execution.risk_guardian import RiskConfig
        risk_config = RiskConfig(
            max_risk_percent=2.5,
            max_trades_per_day=24,
            max_drawdown_usd=450.0,
            max_total_exposure=450.0,
            max_open_positions=4,
        )
        
        self.risk_guardian = RiskGuardian(
            executor=self.executor,
            config=risk_config,
        )
        
        self.journal = AgentJournal()
        
        # Analyzers
        self.kz_analyzer = KillzoneManager()
        self.asian_calc = AsianRangeCalculator()
        self.signal_gen = SignalGenerator()
        
        # Detectors
        self.ms_detector = MarketStructureAnalyzer()
        self.fvg_detector = FVGDetector()
        self.ob_detector = OrderBlockDetector()
        self.liq_detector = LiquidityDetector()
        self.turtle_detector = TurtleSoupDetector()
        self.mm_detector = MarketMakerModelDetector()
        
        # Timing
        self.scan_interval = 300  # Seconds between scans (5 minutes)
        self.last_scan = None
        
        print("═══════════════════════════════════════════════════════════")
        print("🤖 AUTONOMOUS ICT TRADING AGENT INITIALIZED")
        print("═══════════════════════════════════════════════════════════")
        print(f"   Environment: {environment.upper()}")
        print(f"   Symbols: {', '.join(self.symbols)}")
        print(f"   Base Balance: ${base_account_balance:,.2f}")
        print(f"   Max Risk/Trade: {self.risk_guardian.config.max_risk_percent}%")
        print(f"   Max Trades/Day: {self.risk_guardian.config.max_trades_per_day}")
        print(f"   Max Drawdown: ${self.risk_guardian.config.max_drawdown_usd}")
        print("═══════════════════════════════════════════════════════════")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CORE LOOP
    # ═══════════════════════════════════════════════════════════════════════════
    
    def run(self, duration_minutes: int = None):
        """
        Main trading loop.
        
        I will run until stopped or until risk limits are hit.
        """
        self.running = True
        start_time = datetime.now(NY_TZ)
        
        print(f"\n🚀 Agent starting at {start_time.strftime('%H:%M:%S')}")
        
        if duration_minutes:
            end_time = start_time + timedelta(minutes=duration_minutes)
            print(f"   Will run until {end_time.strftime('%H:%M:%S')}")
        
        try:
            while self.running:
                # Check if risk limits hit
                if self.state == AgentState.SHUTDOWN:
                    print("\n🛑 AGENT SHUTDOWN - Risk limits reached")
                    break
                
                # Check duration
                if duration_minutes:
                    if datetime.now(NY_TZ) > end_time:
                        print("\n⏰ Duration complete. Stopping agent.")
                        break
                
                # Main cycle
                self._trading_cycle()
                
                # Wait before next cycle
                time.sleep(self.scan_interval)
                
        except KeyboardInterrupt:
            print("\n⚠️ Agent stopped by user")
        finally:
            self.running = False
            self._print_session_summary()
    
    def _trading_cycle(self):
        """One complete trading cycle"""
        now = datetime.now(NY_TZ)
        
        # Get current session
        current_killzone = self.kz_analyzer.get_current_killzone(now)
        session_name = current_killzone.value if current_killzone else 'No Session'
        is_primary = self.kz_analyzer.is_primary_killzone(now)
        
        print(f"\n[{now.strftime('%H:%M:%S')}] 📡 Scan Cycle | Session: {session_name}")
        
        # 1. Check risk guardian
        can_trade, reason = self.risk_guardian.can_trade()
        if not can_trade:
            print(f"   ⛔ Risk Guardian: {reason}")
            if "drawdown" in reason.lower():
                self.state = AgentState.SHUTDOWN
            return
        
        # 2. Monitor open positions
        self._monitor_positions()
        
        # 3. Scan for setups (only during killzones)
        if current_killzone and is_primary:
            self.state = AgentState.SCANNING
            setups = self._scan_all_symbols()
            
            if setups:
                # 4. Analyze and filter
                self.state = AgentState.ANALYZING
                best_setup = self._select_best_setup(setups)
                
                if best_setup:
                    # 5. Execute
                    self._execute_setup(best_setup)
        else:
            print("   💤 Outside killzone - Waiting...")
        
        self.state = AgentState.IDLE
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SCANNING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _scan_all_symbols(self) -> List[TradingSetup]:
        """Scan all symbols for setups"""
        all_setups = []
        
        for symbol in self.symbols:
            print(f"   🔍 Scanning {symbol}...")
            
            try:
                setups = self._scan_symbol(symbol)
                all_setups.extend(setups)
            except Exception as e:
                print(f"   ❌ Error scanning {symbol}: {e}")
        
        if all_setups:
            print(f"   ✅ Found {len(all_setups)} potential setups")
        
        return all_setups
    
    def _scan_symbol(self, symbol: str) -> List[TradingSetup]:
        """Scan a single symbol for setups"""
        setups = []
        
        # Get data
        df_15m = get_oanda_data(symbol, timeframe="M15", count=200)
        df_1h = get_oanda_data(symbol, timeframe="H1", count=100)
        
        if df_15m is None or df_15m.empty:
            return setups
        
        # Get current price
        current = get_current_price(symbol)
        if current is None:
            return setups
        
        bid = current.get('bid', 0)
        ask = current.get('ask', 0)
        mid = (bid + ask) / 2
        
        # Get Asian Range context
        try:
            asian = self.asian_calc.calculate(symbol, df_15m)
        except:
            asian = None
        
        # Run all models
        # 1. Market Maker Model
        mm_results = self.mm_detector.analyze(df_15m)
        if mm_results:
            for mm_result in mm_results:
                if hasattr(mm_result, 'entry_price') and mm_result.entry_price:
                    model_type = getattr(mm_result, 'model_type', 'MMSM')
                    direction = "BUY" if "BUY" in str(model_type) else "SELL"
                    
                    setup = TradingSetup(
                        symbol=symbol,
                        direction=direction,
                        model=str(model_type),
                        timeframe="M15",
                        entry_price=mid,
                        stop_loss=getattr(mm_result, 'stop_loss', 0) or 0.0,
                        take_profit=getattr(mm_result, 'target', 0) or 0.0,
                        confluences=getattr(mm_result, 'confluences', []) or [],
                        confidence=getattr(mm_result, 'confidence', 70),
                        description=f"{model_type} - {getattr(mm_result, 'phase', '')}",
                    )
                    setups.append(setup)
        
        # 2. Turtle Soup
        ts_results = self.turtle_detector.analyze(df_15m)
        if ts_results:
            for ts_setup in ts_results if isinstance(ts_results, list) else [ts_results]:
                if hasattr(ts_setup, 'entry_price') and ts_setup.entry_price:
                    setup = TradingSetup(
                        symbol=symbol,
                        direction=getattr(ts_setup, 'direction', 'SELL'),
                        model="TURTLE_SOUP",
                        timeframe="M15",
                        entry_price=ts_setup.entry_price,
                        stop_loss=getattr(ts_setup, 'stop_loss', 0),
                        take_profit=getattr(ts_setup, 'take_profit', 0),
                        confluences=["Liquidity Sweep", "MSS"],
                        confidence=getattr(ts_setup, 'confidence', 70),
                        description="Failed breakout exploitation",
                    )
                    setups.append(setup)
        
        # 3. Signal Generator (IRL/ERL, Power of 3, etc.)
        # Note: signal_gen.generate_signal needs HTF bias, so we skip it for now
        # Can be enhanced later with proper MTF analysis
        
        # Add Asian Range context to setups
        try:
            if asian and hasattr(asian, 'range_pips') and asian.range_pips:
                for setup in setups:
                    if hasattr(asian, 'high_price') and hasattr(asian, 'low_price'):
                        if asian.high_price and asian.low_price:
                            # Check if setup aligns with Asian Range sweep
                            if setup.direction == "BUY" and mid < asian.low_price:
                                setup.confluences.append("Asian Low Sweep")
                                setup.confidence += 10
                            elif setup.direction == "SELL" and mid > asian.high_price:
                                setup.confluences.append("Asian High Sweep")
                                setup.confidence += 10
        except:
            pass
        
        return setups
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _select_best_setup(self, setups: List[TradingSetup]) -> Optional[TradingSetup]:
        """Select the best setup from available options"""
        if not setups:
            return None
        
        # Filter: minimum confidence
        valid = [s for s in setups if s.confidence >= 45]
        if not valid:
            print("   📊 No setups meet confidence threshold")
            return None
        
        # Filter: must have valid SL/TP
        valid = [s for s in valid if s.stop_loss and s.take_profit]
        if not valid:
            print("   📊 No setups with valid SL/TP")
            return None
        
        # Filter: Check R:R
        good_rr = []
        for setup in valid:
            pip_value = 0.01 if "JPY" in setup.symbol.upper() else 0.0001
            
            if setup.direction == "BUY":
                risk = abs(setup.entry_price - setup.stop_loss) / pip_value
                reward = abs(setup.take_profit - setup.entry_price) / pip_value
            else:
                risk = abs(setup.stop_loss - setup.entry_price) / pip_value
                reward = abs(setup.entry_price - setup.take_profit) / pip_value
            
            if risk > 0:
                rr = reward / risk
                if rr >= 2.0:  # Minimum 1:2 R:R
                    good_rr.append((setup, rr))
        
        if not good_rr:
            print("   📊 No setups meet R:R requirements (min 1:2)")
            return None
        
        # Sort by confidence, then R:R
        good_rr.sort(key=lambda x: (x[0].confidence, x[1]), reverse=True)
        
        best = good_rr[0][0]
        best_rr = good_rr[0][1]
        
        print(f"   🎯 Best Setup: {best.model} {best.direction} {best.symbol}")
        print(f"      Confidence: {best.confidence:.0f}% | R:R: 1:{best_rr:.1f}")
        print(f"      Confluences: {', '.join(best.confluences[:3])}")
        
        return best
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXECUTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _execute_setup(self, setup: TradingSetup):
        """Execute a trading setup"""
        self.state = AgentState.EXECUTING
        
        print(f"\n   💥 EXECUTING: {setup.direction} {setup.symbol}")
        
        # Calculate position size
        account_info = self.executor.get_account_info()
        if not account_info:
            print("   ❌ Could not get account info")
            return
        
        balance = float(account_info.get('balance', self.base_balance))
        
        # Risk calculation
        pip_value = 0.01 if "JPY" in setup.symbol.upper() else 0.0001
        if setup.direction == "BUY":
            risk_pips = abs(setup.entry_price - setup.stop_loss) / pip_value
        else:
            risk_pips = abs(setup.stop_loss - setup.entry_price) / pip_value
        
        # Calculate risk amount - can be 1.5-2.5% depending on setup quality
        # Higher confidence = higher risk
        if setup.confidence >= 85:
            risk_percent = 2.5
        elif setup.confidence >= 75:
            risk_percent = 2.0
        else:
            risk_percent = 1.5
        
        risk_amount = balance * (risk_percent / 100)
        
        # Correct position sizing: Units = Risk$ / (SL pips * pip value per unit)
        # For EUR/USD: pip value = $0.0001 per unit
        pip_value_per_unit = 0.0001 if "JPY" not in setup.symbol.upper() else 0.01
        
        if risk_pips > 0:
            units = int(risk_amount / (risk_pips * pip_value_per_unit))
            units = min(units, 500000)  # Cap at 5 lots
            units = max(units, 1000)    # Min 0.01 lot
        else:
            units = 10000  # Default to 0.1 lot
        
        # Check with risk guardian - validates total exposure
        can_trade, reason = self.risk_guardian.can_trade(
            symbol=setup.symbol,
            risk_amount=risk_amount,
        )
        
        if not can_trade:
            print(f"   ⛔ Risk Guardian blocked: {reason}")
            return
        
        # Place the order
        if setup.direction == "SELL":
            units = -abs(units)
        
        result = self.executor.place_market_order(
            instrument=setup.symbol,
            units=units,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit,
        )
        
        if result and 'orderFillTransaction' in result:
            fill = result['orderFillTransaction']
            trade_id = fill.get('tradeOpened', {}).get('tradeID', '')
            fill_price = float(fill.get('price', setup.entry_price))
            
            print(f"   ✅ ORDER FILLED @ {fill_price}")
            print(f"   Trade ID: {trade_id}")
            
            # Record in journal
            self.journal.record_entry(
                symbol=setup.symbol,
                side=setup.direction,
                entry_price=fill_price,
                stop_loss=setup.stop_loss,
                take_profit=setup.take_profit,
                units=abs(units),
                trade_id=trade_id,
                model=setup.model,
                timeframe=setup.timeframe,
                confluences=setup.confluences,
                setup_description=setup.description,
                risk_amount=risk_amount,
                risk_percent=self.risk_guardian.config.max_risk_percent,
                session=self.kz_analyzer.get_current_killzone(datetime.now(NY_TZ)).value if self.kz_analyzer.get_current_killzone(datetime.now(NY_TZ)) else '',
            )
            
            # Record trade for risk tracking
            direction = "long" if setup.direction == "BUY" else "short"
            self.risk_guardian.record_trade(
                trade_id=trade_id,
                symbol=setup.symbol,
                side=direction,
                units=abs(units),
            )
            
        else:
            print(f"   ❌ Order failed: {result}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MONITORING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _monitor_positions(self):
        """Monitor open positions for closes"""
        try:
            open_positions = self.executor.get_open_trades()
            
            if not open_positions:
                return
            
            # Just log current position status
            for pos in open_positions:
                trade_id = pos.get('id', '')
                symbol = pos.get('instrument', '')
                unrealized_pnl = float(pos.get('unrealizedPL', 0))
                
                # Print position status if significant P&L change
                if abs(unrealized_pnl) > 50:
                    print(f"   📊 Position #{trade_id} {symbol}: ${unrealized_pnl:+.2f}")
                    
        except Exception as e:
            # Silently handle API errors during monitoring
            pass
    
    def _check_closed_trades(self):
        """Check for trades that were closed"""
        try:
            # Get open journal entries  
            open_journal = self.journal.get_open_trades() if hasattr(self.journal, 'get_open_trades') else []
            
            # Get current OANDA positions
            open_positions = self.executor.get_open_trades()
            open_trade_ids = [p.get('id', '') for p in open_positions]
            
            # Find journal entries without matching OANDA position (= closed)
            for entry in open_journal:
                if hasattr(entry, 'trade_id') and entry.trade_id and entry.trade_id not in open_trade_ids:
                    # Trade was closed - get details from OANDA
                    current = get_current_price(entry.symbol)
                    if current:
                        exit_price = current.get('mid', entry.entry_price)
                        
                        # Calculate P&L
                        pip_value = 0.01 if "JPY" in entry.symbol.upper() else 0.0001
                        if entry.side == "BUY":
                            pnl_pips = (exit_price - entry.entry_price) / pip_value
                        else:
                            pnl_pips = (entry.entry_price - exit_price) / pip_value
                        
                        pnl = pnl_pips * (entry.units * pip_value * 10)  # Approximate
                        
                        # Determine if hit SL or TP
                        if entry.side == "BUY":
                            hit_sl = exit_price <= entry.stop_loss
                            hit_tp = exit_price >= entry.take_profit
                        else:
                            hit_sl = exit_price >= entry.stop_loss
                            hit_tp = exit_price <= entry.take_profit
                        
                        lesson = ""
                        if hit_sl:
                            lesson = "Stop loss hit - trade did not work out"
                        elif hit_tp:
                            lesson = "Take profit hit - trade worked as planned"
                        
                        # Record exit if journal has the method
                        if hasattr(self.journal, 'record_exit'):
                            self.journal.record_exit(
                                trade_id=entry.trade_id,
                                exit_price=exit_price,
                                pnl=pnl,
                                lesson_learned=lesson,
                            )
        except Exception as e:
            # Silently handle errors
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REPORTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _print_session_summary(self):
        """Print summary when session ends"""
        print("\n")
        print(self.journal.format_daily_report())
        
        # Risk summary
        print("\n📊 RISK SUMMARY:")
        print(f"   Trades Today: {self.risk_guardian.state.trades_today}")
        print(f"   Realized P&L: ${self.risk_guardian.state.daily_pnl:+.2f}")
        print(f"   Current Drawdown: ${self.risk_guardian.state.current_drawdown:.2f}")
    
    def stop(self):
        """Stop the agent"""
        self.running = False
        print("\n🛑 Agent stopping...")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def load_env_file():
    """Load .env file from project root"""
    from pathlib import Path
    env_file = Path(__file__).parent.parent.parent.parent / '.env'
    if env_file.exists():
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
        return True
    return False


def main():
    """Start the autonomous trader"""
    
    # Load .env file
    load_env_file()
    
    # OANDA Demo credentials
    API_KEY = os.getenv("OANDA_API_KEY", "")
    ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
    
    if not API_KEY or not ACCOUNT_ID:
        print("=" * 60)
        print("❌ OANDA Demo credentials not found!")
        print("=" * 60)
        print()
        print("To use the autonomous trader, please set:")
        print("  export OANDA_API_KEY='your-demo-api-key'")
        print("  export OANDA_ACCOUNT_ID='your-demo-account-id'")
        print()
        print("Get demo credentials at: https://www.oanda.com/demo-account/")
        print("=" * 60)
        return
    
    # Create the agent with expanded pairs
    agent = AutonomousTrader(
        account_id=ACCOUNT_ID,
        api_key=API_KEY,
        environment="practice",  # DEMO mode
        symbols=["EUR_USD", "GBP_USD", "XAU_USD", "USD_JPY", "AUD_USD", "EUR_GBP"],
        base_account_balance=10000.0,
    )
    
    # Run continuously (Ctrl+C to stop)
    agent.run(duration_minutes=None)


if __name__ == "__main__":
    main()
