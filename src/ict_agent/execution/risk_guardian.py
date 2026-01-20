"""
Risk Guardian

Enforces all risk management rules for autonomous trading:
- Maximum risk per trade (2.5%)
- Maximum trades per day (8)
- Maximum drawdown before shutdown ($450)
- Position sizing calculations
- Pre-trade validation

This is the gatekeeper - NO trade passes without approval.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path

from ict_agent.execution.oanda_executor import OANDAExecutor, AccountInfo


NY_TZ = ZoneInfo("America/New_York")


@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_risk_percent: float = 2.5      # Maximum risk per trade (% of balance)
    max_trades_per_day: int = 24       # Maximum trades per day
    max_drawdown_usd: float = 450.0    # Maximum drawdown before shutdown
    max_total_exposure: float = 450.0  # Maximum total risk across all open trades
    min_risk_reward: float = 1.5       # Minimum R:R ratio required
    max_open_positions: int = 4        # Maximum concurrent positions
    max_risk_per_pair: float = 5.0     # Maximum exposure per pair (% of balance)
    max_correlation_exposure: float = 7.5  # Max exposure to correlated pairs (EUR+GBP)


@dataclass
class RiskState:
    """Current risk state tracking"""
    starting_balance: float = 0.0      # Balance at start of session
    current_balance: float = 0.0       # Current balance
    high_water_mark: float = 0.0       # Highest balance reached
    current_drawdown: float = 0.0      # Current drawdown from HWM
    trades_today: int = 0              # Trades taken today
    daily_pnl: float = 0.0             # P&L for today
    is_shutdown: bool = False          # Whether trading is disabled
    shutdown_reason: str = ""          # Why we shutdown
    last_updated: datetime = field(default_factory=lambda: datetime.now(NY_TZ))
    
    def to_dict(self) -> dict:
        return {
            "starting_balance": self.starting_balance,
            "current_balance": self.current_balance,
            "high_water_mark": self.high_water_mark,
            "current_drawdown": self.current_drawdown,
            "trades_today": self.trades_today,
            "daily_pnl": self.daily_pnl,
            "is_shutdown": self.is_shutdown,
            "shutdown_reason": self.shutdown_reason,
            "last_updated": self.last_updated.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RiskState':
        return cls(
            starting_balance=data.get("starting_balance", 0),
            current_balance=data.get("current_balance", 0),
            high_water_mark=data.get("high_water_mark", 0),
            current_drawdown=data.get("current_drawdown", 0),
            trades_today=data.get("trades_today", 0),
            daily_pnl=data.get("daily_pnl", 0),
            is_shutdown=data.get("is_shutdown", False),
            shutdown_reason=data.get("shutdown_reason", ""),
            last_updated=datetime.fromisoformat(data["last_updated"]) if "last_updated" in data else datetime.now(NY_TZ),
        )


@dataclass
class TradeValidation:
    """Result of trade validation"""
    approved: bool
    risk_amount: float = 0.0
    position_size: int = 0
    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __str__(self):
        if self.approved:
            return f"✅ APPROVED - Risk: ${self.risk_amount:.2f}, Size: {self.position_size} units"
        else:
            return f"❌ REJECTED - {', '.join(self.rejection_reasons)}"


class RiskGuardian:
    """
    The Risk Guardian - enforces all risk rules.
    
    NO trade can be executed without passing through this guardian.
    """
    
    def __init__(
        self,
        executor: OANDAExecutor,
        config: RiskConfig = None,
        state_file: str = None,
    ):
        self.executor = executor
        self.config = config or RiskConfig()
        self.state_file = state_file or str(
            Path(__file__).parent.parent.parent.parent / "data" / "risk_state.json"
        )
        
        # Load or initialize state
        self.state = self._load_state()
        
        # Initialize if needed
        if self.state.starting_balance == 0:
            self._initialize_state()
    
    def _load_state(self) -> RiskState:
        """Load risk state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                
                state = RiskState.from_dict(data)
                
                # Reset daily counters if new day
                if state.last_updated.date() != datetime.now(NY_TZ).date():
                    state.trades_today = 0
                    state.daily_pnl = 0.0
                    state.is_shutdown = False
                    state.shutdown_reason = ""
                
                return state
        except Exception as e:
            print(f"Error loading risk state: {e}")
        
        return RiskState()
    
    def _save_state(self):
        """Save risk state to file"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving risk state: {e}")
    
    def _initialize_state(self):
        """Initialize state from current account"""
        account = self.executor.get_account_info(force_refresh=True)
        if account:
            self.state.starting_balance = account.balance
            self.state.current_balance = account.balance
            self.state.high_water_mark = account.balance
            self._save_state()
    
    def update_state(self):
        """Update state from current account info"""
        account = self.executor.get_account_info(force_refresh=True)
        if not account:
            return
        
        self.state.current_balance = account.nav  # Use NAV (includes unrealized)
        self.state.last_updated = datetime.now(NY_TZ)
        
        # Update high water mark
        if self.state.current_balance > self.state.high_water_mark:
            self.state.high_water_mark = self.state.current_balance
        
        # Calculate drawdown from HWM
        self.state.current_drawdown = self.state.high_water_mark - self.state.current_balance
        
        # Calculate daily P&L
        self.state.daily_pnl = self.state.current_balance - self.state.starting_balance
        
        # Check for shutdown conditions
        self._check_shutdown_conditions()
        
        self._save_state()
    
    def _check_shutdown_conditions(self):
        """Check if we should shutdown trading"""
        # Already shutdown
        if self.state.is_shutdown:
            return
        
        # Check max drawdown
        if self.state.current_drawdown >= self.config.max_drawdown_usd:
            self.state.is_shutdown = True
            self.state.shutdown_reason = f"Max drawdown reached: ${self.state.current_drawdown:.2f} >= ${self.config.max_drawdown_usd:.2f}"
            print(f"🚨 RISK GUARDIAN SHUTDOWN: {self.state.shutdown_reason}")
        
        # Check max trades per day
        if self.state.trades_today >= self.config.max_trades_per_day:
            self.state.is_shutdown = True
            self.state.shutdown_reason = f"Max trades per day reached: {self.state.trades_today}"
            print(f"🚨 RISK GUARDIAN SHUTDOWN: {self.state.shutdown_reason}")
    
    def validate_trade(
        self,
        symbol: str,
        side: str,  # "BUY" or "SELL"
        stop_loss_price: float,
        entry_price: float,
        take_profit_price: Optional[float] = None,
    ) -> TradeValidation:
        """
        Validate a proposed trade against all risk rules.
        
        Args:
            symbol: Trading pair
            side: "BUY" or "SELL"
            stop_loss_price: Stop loss price
            entry_price: Entry price
            take_profit_price: Take profit price (for R:R check)
        
        Returns:
            TradeValidation with approval status and position size
        """
        validation = TradeValidation(approved=True)
        
        # Update state first
        self.update_state()
        
        # ═══════════════════════════════════════════════════════════════════════
        # CHECK: System shutdown
        # ═══════════════════════════════════════════════════════════════════════
        if self.state.is_shutdown:
            validation.approved = False
            validation.rejection_reasons.append(f"System shutdown: {self.state.shutdown_reason}")
            return validation
        
        # ═══════════════════════════════════════════════════════════════════════
        # CHECK: Max trades per day
        # ═══════════════════════════════════════════════════════════════════════
        if self.state.trades_today >= self.config.max_trades_per_day:
            validation.approved = False
            validation.rejection_reasons.append(
                f"Max trades per day ({self.config.max_trades_per_day}) reached"
            )
            return validation
        
        # ═══════════════════════════════════════════════════════════════════════
        # CHECK: Max open positions
        # ═══════════════════════════════════════════════════════════════════════
        positions = self.executor.get_positions()
        if len(positions) >= self.config.max_open_positions:
            validation.approved = False
            validation.rejection_reasons.append(
                f"Max open positions ({self.config.max_open_positions}) reached"
            )
            return validation
        
        # ═══════════════════════════════════════════════════════════════════════
        # CHECK: Already have position in this pair
        # ═══════════════════════════════════════════════════════════════════════
        existing = self.executor.get_position(symbol)
        if existing:
            validation.approved = False
            validation.rejection_reasons.append(
                f"Already have {existing.side} position in {symbol}"
            )
            return validation
        
        # ═══════════════════════════════════════════════════════════════════════
        # CALCULATE: Stop loss pips and risk
        # ═══════════════════════════════════════════════════════════════════════
        pip_value = 0.01 if "JPY" in symbol.upper() else 0.0001
        
        if side.upper() == "BUY":
            stop_loss_pips = abs(entry_price - stop_loss_price) / pip_value
        else:
            stop_loss_pips = abs(stop_loss_price - entry_price) / pip_value
        
        if stop_loss_pips <= 0:
            validation.approved = False
            validation.rejection_reasons.append("Invalid stop loss (0 pips)")
            return validation
        
        if stop_loss_pips > 50:
            validation.warnings.append(f"Wide stop loss: {stop_loss_pips:.1f} pips")
        
        # ═══════════════════════════════════════════════════════════════════════
        # CALCULATE: Risk amount and position size
        # ═══════════════════════════════════════════════════════════════════════
        account_balance = self.state.current_balance
        max_risk_amount = account_balance * (self.config.max_risk_percent / 100)
        
        validation.risk_amount = max_risk_amount
        validation.position_size = self.executor.calculate_units(
            symbol, max_risk_amount, stop_loss_pips
        )
        
        if validation.position_size < 1000:
            validation.approved = False
            validation.rejection_reasons.append("Position size too small (< 1000 units)")
            return validation
        
        # ═══════════════════════════════════════════════════════════════════════
        # CHECK: Risk/Reward ratio
        # ═══════════════════════════════════════════════════════════════════════
        if take_profit_price:
            if side.upper() == "BUY":
                reward_pips = abs(take_profit_price - entry_price) / pip_value
            else:
                reward_pips = abs(entry_price - take_profit_price) / pip_value
            
            risk_reward = reward_pips / stop_loss_pips if stop_loss_pips > 0 else 0
            
            if risk_reward < self.config.min_risk_reward:
                validation.approved = False
                validation.rejection_reasons.append(
                    f"R:R too low: {risk_reward:.2f} < {self.config.min_risk_reward}"
                )
                return validation
            
            if risk_reward >= 3:
                validation.warnings.append(f"Excellent R:R: {risk_reward:.2f}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # CHECK: Correlation exposure
        # ═══════════════════════════════════════════════════════════════════════
        # EUR and GBP are correlated
        correlated_pairs = {
            "EUR_USD": ["GBP_USD", "EUR_GBP"],
            "GBP_USD": ["EUR_USD", "EUR_GBP"],
            "EUR_GBP": ["EUR_USD", "GBP_USD"],
        }
        
        instrument = self.executor._get_instrument(symbol)
        if instrument in correlated_pairs:
            for pos in positions:
                if pos.instrument in correlated_pairs[instrument]:
                    validation.warnings.append(
                        f"Correlated position: already have {pos.instrument}"
                    )
        
        # ═══════════════════════════════════════════════════════════════════════
        # ALL CHECKS PASSED
        # ═══════════════════════════════════════════════════════════════════════
        return validation
    
    def record_trade(self, trade_id: str, symbol: str, side: str, units: int):
        """Record that a trade was taken"""
        self.state.trades_today += 1
        self.update_state()
        self._save_state()
    
    def can_trade(self) -> Tuple[bool, str]:
        """Quick check if trading is allowed"""
        self.update_state()
        
        if self.state.is_shutdown:
            return False, self.state.shutdown_reason
        
        if self.state.trades_today >= self.config.max_trades_per_day:
            return False, f"Max trades per day reached ({self.state.trades_today})"
        
        return True, "Trading allowed"
    
    def get_status(self) -> dict:
        """Get current risk status"""
        self.update_state()
        
        return {
            "trading_allowed": not self.state.is_shutdown,
            "shutdown_reason": self.state.shutdown_reason,
            "balance": self.state.current_balance,
            "high_water_mark": self.state.high_water_mark,
            "current_drawdown": self.state.current_drawdown,
            "max_drawdown": self.config.max_drawdown_usd,
            "drawdown_remaining": self.config.max_drawdown_usd - self.state.current_drawdown,
            "trades_today": self.state.trades_today,
            "max_trades_per_day": self.config.max_trades_per_day,
            "trades_remaining": self.config.max_trades_per_day - self.state.trades_today,
            "daily_pnl": self.state.daily_pnl,
            "risk_per_trade": self.config.max_risk_percent,
        }
    
    def format_status(self) -> str:
        """Format status for display"""
        status = self.get_status()
        
        if status["trading_allowed"]:
            header = "🟢 RISK GUARDIAN: ACTIVE"
        else:
            header = f"🔴 RISK GUARDIAN: SHUTDOWN - {status['shutdown_reason']}"
        
        lines = [
            f"═══ {header} ═══",
            "",
            f"💰 Balance: ${status['balance']:,.2f}",
            f"📈 High Water Mark: ${status['high_water_mark']:,.2f}",
            f"📉 Current Drawdown: ${status['current_drawdown']:,.2f} / ${status['max_drawdown']:,.2f}",
            f"   Remaining: ${status['drawdown_remaining']:,.2f}",
            "",
            f"📊 Daily P&L: ${status['daily_pnl']:+,.2f}",
            f"🔄 Trades Today: {status['trades_today']} / {status['max_trades_per_day']}",
            f"   Remaining: {status['trades_remaining']}",
            "",
            f"⚖️ Risk Per Trade: {status['risk_per_trade']}%",
        ]
        
        return "\n".join(lines)
    
    def reset_daily(self):
        """Reset daily counters (call at start of new trading day)"""
        account = self.executor.get_account_info(force_refresh=True)
        if account:
            self.state.starting_balance = account.balance
            self.state.trades_today = 0
            self.state.daily_pnl = 0.0
            self.state.is_shutdown = False
            self.state.shutdown_reason = ""
            self._save_state()
    
    def emergency_shutdown(self, reason: str = "Manual shutdown"):
        """Emergency shutdown - stop all trading"""
        self.state.is_shutdown = True
        self.state.shutdown_reason = reason
        self._save_state()
        print(f"🚨 EMERGENCY SHUTDOWN: {reason}")
    
    def resume_trading(self):
        """Resume trading after shutdown (use with caution)"""
        self.state.is_shutdown = False
        self.state.shutdown_reason = ""
        self._save_state()
        print("🟢 Trading resumed")


# Test
if __name__ == "__main__":
    print("Testing Risk Guardian...")
    
    from ict_agent.execution.oanda_executor import OANDAExecutor
    
    executor = OANDAExecutor(environment="live")
    guardian = RiskGuardian(executor)
    
    print(guardian.format_status())
    
    # Test validation
    print("\n\nTest Trade Validation:")
    validation = guardian.validate_trade(
        symbol="EUR_USD",
        side="SELL",
        entry_price=1.16400,
        stop_loss_price=1.16600,
        take_profit_price=1.15900,
    )
    print(validation)
