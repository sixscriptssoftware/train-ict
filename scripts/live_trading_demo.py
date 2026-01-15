"""
Example: Live Trading with the ICT Trading Agent

This script demonstrates how to:
1. Connect to live data feeds
2. Run the agent in real-time
3. Generate and log signals
4. Manage risk and positions

NOTE: This is a demonstration script. For real trading, you would need to:
- Connect to your broker's API
- Implement proper error handling
- Add monitoring and alerting
- Test extensively in paper trading first
"""

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ict_agent.engine.agent import ICTTradingAgent, AgentConfig
from ict_agent.engine.killzone import KillzoneManager, Killzone
from ict_agent.execution.risk_manager import RiskManager, RiskConfig
from ict_agent.execution.position_manager import PositionManager
from ict_agent.data.fetcher import DataFetcher
from ict_agent.data.preprocessor import DataPreprocessor
from loguru import logger


class LiveTradingDemo:
    """Demonstration of live trading workflow"""
    
    def __init__(self, symbols: list[str], paper_mode: bool = True):
        self.symbols = symbols
        self.paper_mode = paper_mode
        
        agent_config = AgentConfig(
            symbols=symbols,
            min_risk_reward=2.0,
            min_confluences=3,
            max_trades_per_day=3,
        )
        
        self.agent = ICTTradingAgent(config=agent_config)
        
        risk_config = RiskConfig(
            account_balance=10000.0,
            max_risk_per_trade=0.01,
            max_daily_loss=0.02,
            max_positions=3,
        )
        
        self.risk_manager = RiskManager(config=risk_config)
        self.position_manager = PositionManager(max_positions=3, max_cycles=2)
        self.killzone_manager = KillzoneManager()
        
        self.data_fetcher = DataFetcher(source="yfinance")
        self.preprocessor = DataPreprocessor()
        
        logger.info(f"Live trading demo initialized | Symbols: {symbols}")
    
    def run(self, duration_seconds: int = 60):
        """
        Run the live trading loop.
        
        Args:
            duration_seconds: How long to run (for demo purposes)
        """
        logger.info("Starting live trading demo...")
        logger.info(f"Paper mode: {self.paper_mode}")
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            try:
                self._trading_loop()
            except KeyboardInterrupt:
                logger.info("Stopping on keyboard interrupt...")
                break
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
            
            time.sleep(60)
        
        self._shutdown()
    
    def _trading_loop(self):
        """Single iteration of the trading loop"""
        current_time = datetime.now()
        
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.info(f"Trading paused: {reason}")
            return
        
        current_kz = self.killzone_manager.get_current_killzone(current_time)
        if current_kz:
            logger.info(f"Active killzone: {current_kz.value}")
        else:
            logger.debug("Outside killzones, monitoring only...")
        
        for symbol in self.symbols:
            signal = self._analyze_symbol(symbol)
            
            if signal:
                self._handle_signal(signal)
        
        self._update_positions()
    
    def _analyze_symbol(self, symbol: str):
        """Analyze a symbol for trading signals"""
        try:
            htf_data = self.data_fetcher.fetch(symbol, "1d", limit=100)
            itf_data = self.data_fetcher.fetch(symbol, "1h", limit=200)
            ltf_data = self.data_fetcher.fetch(symbol, "15m", limit=100)
            
            htf_data = self.preprocessor.preprocess(htf_data)
            itf_data = self.preprocessor.preprocess(itf_data)
            ltf_data = self.preprocessor.preprocess(ltf_data)
            
            signal = self.agent.analyze(symbol, htf_data, itf_data, ltf_data)
            
            return signal
            
        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None
    
    def _handle_signal(self, signal):
        """Handle a generated trading signal"""
        logger.info(
            f"SIGNAL: {signal.symbol} {signal.signal_type.value.upper()} | "
            f"Model: {signal.model.value} | "
            f"Confidence: {signal.confidence:.2f}"
        )
        
        position_size = self.risk_manager.calculate_position_size(
            signal.entry_price,
            signal.stop_loss,
        )
        
        is_valid, reason = self.risk_manager.validate_trade(
            signal.entry_price,
            signal.stop_loss,
            position_size,
        )
        
        if not is_valid:
            logger.warning(f"Trade rejected: {reason}")
            return
        
        if self.paper_mode:
            logger.info(
                f"[PAPER] Would execute: {signal.signal_type.value} {position_size} lots "
                f"@ {signal.entry_price:.5f} | SL: {signal.stop_loss:.5f} | "
                f"TP1: {signal.target_1:.5f}"
            )
            
            self.position_manager.open_position(
                symbol=signal.symbol,
                direction=signal.signal_type.value,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                target_1=signal.target_1,
                target_2=signal.target_2,
                position_size=position_size,
            )
        else:
            logger.warning("Live execution not implemented in demo")
    
    def _update_positions(self):
        """Update open positions with current prices"""
        positions = self.position_manager.get_open_positions()
        
        if not positions:
            return
        
        prices = {}
        for pos in positions:
            try:
                data = self.data_fetcher.fetch(pos.symbol, "1m", limit=1)
                prices[pos.symbol] = data.iloc[-1]["close"]
            except Exception:
                pass
        
        if prices:
            actions = self.position_manager.update_positions(prices)
            
            for action in actions:
                logger.info(f"Position action: {action}")
                
                if action["action"] in ["stop_loss", "target_2", "max_cycles_close"]:
                    self.risk_manager.record_trade_result(action.get("pnl", 0))
    
    def _shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down...")
        
        positions = self.position_manager.get_open_positions()
        if positions:
            logger.info(f"Closing {len(positions)} open positions...")
            self.position_manager.close_all_positions("shutdown")
        
        risk_report = self.risk_manager.get_risk_report()
        logger.info(f"Final risk report: {risk_report}")
        
        stats = self.agent.get_performance_stats()
        logger.info(f"Session stats: {stats}")


def main():
    print("=" * 60)
    print("ICT Trading Agent - Live Trading Demo")
    print("=" * 60)
    print("\nThis is a DEMONSTRATION ONLY - no real trades will be executed")
    print("For actual trading, connect to your broker's API")
    print("\nPress Ctrl+C to stop\n")
    
    demo = LiveTradingDemo(
        symbols=["EURUSD", "GBPUSD"],
        paper_mode=True,
    )
    
    demo.run(duration_seconds=300)


if __name__ == "__main__":
    main()
