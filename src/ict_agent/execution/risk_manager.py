"""Risk Manager

Manages trading risk with ICT-specific rules and prop firm constraints.
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional
from loguru import logger


@dataclass
class RiskConfig:
    """Risk management configuration"""
    account_balance: float = 10000.0
    max_risk_per_trade: float = 0.01
    max_daily_loss: float = 0.02
    max_weekly_loss: float = 0.05
    max_drawdown: float = 0.10
    max_positions: int = 3
    max_lots_per_position: float = 1.0
    pip_size: float = 0.0001
    pip_value: float = 10.0
    weekend_close_hour: int = 16
    weekend_close_day: int = 4


@dataclass
class RiskState:
    """Current risk state"""
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    peak_equity: float = 0.0
    current_drawdown: float = 0.0
    trades_today: int = 0
    is_halted: bool = False
    halt_reason: str = ""


class RiskManager:
    """
    Manages trading risk according to ICT principles and prop firm rules.
    
    Risk Rules:
    1. Max 1% risk per trade
    2. Max 2% daily loss limit
    3. Max 5% weekly loss limit  
    4. Max 10% total drawdown
    5. Weekend position closure
    6. Position sizing based on stop distance
    
    Prop Firm Compatibility:
    - Designed for FTMO, MFF, and similar rules
    - Respects max daily/total drawdown limits
    - Tracks all metrics for compliance
    """
    
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()
        self.state = RiskState(peak_equity=self.config.account_balance)
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        risk_override: Optional[float] = None,
    ) -> float:
        """
        Calculate position size based on risk parameters.
        
        Args:
            entry_price: Planned entry price
            stop_loss: Stop loss price
            risk_override: Optional override for risk per trade
        
        Returns:
            Position size in lots
        """
        risk_pct = risk_override or self.config.max_risk_per_trade
        risk_amount = self.config.account_balance * risk_pct
        
        pip_distance = abs(entry_price - stop_loss) / self.config.pip_size
        
        if pip_distance == 0:
            logger.warning("Stop loss at entry price, cannot calculate size")
            return 0.0
        
        lots = risk_amount / (pip_distance * self.config.pip_value)
        
        lots = min(lots, self.config.max_lots_per_position)
        
        lots = round(lots, 2)
        
        return max(lots, 0.01)
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed under current risk conditions.
        
        Returns:
            Tuple of (can_trade, reason)
        """
        if self.state.is_halted:
            return False, self.state.halt_reason
        
        if abs(self.state.daily_pnl) >= self.config.account_balance * self.config.max_daily_loss:
            self._halt("Daily loss limit reached")
            return False, "Daily loss limit reached"
        
        if abs(self.state.weekly_pnl) >= self.config.account_balance * self.config.max_weekly_loss:
            self._halt("Weekly loss limit reached")
            return False, "Weekly loss limit reached"
        
        if self.state.current_drawdown >= self.config.max_drawdown:
            self._halt("Maximum drawdown reached")
            return False, "Maximum drawdown reached"
        
        if self._is_weekend_close_time():
            return False, "Weekend close period"
        
        return True, "OK"
    
    def validate_trade(
        self,
        entry_price: float,
        stop_loss: float,
        position_size: float,
    ) -> tuple[bool, str]:
        """
        Validate a specific trade against risk rules.
        
        Returns:
            Tuple of (is_valid, reason)
        """
        can_trade, reason = self.can_trade()
        if not can_trade:
            return False, reason
        
        pip_distance = abs(entry_price - stop_loss) / self.config.pip_size
        potential_loss = pip_distance * position_size * self.config.pip_value
        
        max_allowed_loss = self.config.account_balance * self.config.max_risk_per_trade
        if potential_loss > max_allowed_loss * 1.1:
            return False, f"Risk too high: ${potential_loss:.2f} > ${max_allowed_loss:.2f}"
        
        if position_size > self.config.max_lots_per_position:
            return False, f"Position size {position_size} exceeds max {self.config.max_lots_per_position}"
        
        return True, "OK"
    
    def record_trade_result(self, pnl: float) -> None:
        """Record a trade result and update risk state"""
        self.state.daily_pnl += pnl
        self.state.weekly_pnl += pnl
        self.state.trades_today += 1
        
        current_equity = self.config.account_balance + self.state.daily_pnl
        
        if current_equity > self.state.peak_equity:
            self.state.peak_equity = current_equity
        
        self.state.current_drawdown = (
            (self.state.peak_equity - current_equity) / self.state.peak_equity
        )
        
        logger.debug(
            f"Trade recorded: PnL ${pnl:+.2f} | "
            f"Daily: ${self.state.daily_pnl:+.2f} | "
            f"DD: {self.state.current_drawdown*100:.2f}%"
        )
    
    def reset_daily(self) -> None:
        """Reset daily risk counters (call at start of trading day)"""
        self.state.daily_pnl = 0.0
        self.state.trades_today = 0
        
        if self.state.is_halted and "Daily" in self.state.halt_reason:
            self.state.is_halted = False
            self.state.halt_reason = ""
        
        logger.info("Daily risk counters reset")
    
    def reset_weekly(self) -> None:
        """Reset weekly risk counters (call at start of trading week)"""
        self.state.weekly_pnl = 0.0
        self.reset_daily()
        
        if self.state.is_halted and "Weekly" in self.state.halt_reason:
            self.state.is_halted = False
            self.state.halt_reason = ""
        
        logger.info("Weekly risk counters reset")
    
    def update_account_balance(self, new_balance: float) -> None:
        """Update account balance (e.g., after withdrawal/deposit)"""
        self.config.account_balance = new_balance
        self.state.peak_equity = max(self.state.peak_equity, new_balance)
    
    def get_remaining_daily_risk(self) -> float:
        """Get remaining risk budget for today"""
        max_daily = self.config.account_balance * self.config.max_daily_loss
        used = abs(min(0, self.state.daily_pnl))
        return max(0, max_daily - used)
    
    def get_risk_report(self) -> dict:
        """Generate comprehensive risk report"""
        return {
            "account_balance": self.config.account_balance,
            "peak_equity": self.state.peak_equity,
            "current_equity": self.config.account_balance + self.state.daily_pnl,
            "daily_pnl": self.state.daily_pnl,
            "weekly_pnl": self.state.weekly_pnl,
            "current_drawdown_pct": self.state.current_drawdown * 100,
            "max_drawdown_pct": self.config.max_drawdown * 100,
            "trades_today": self.state.trades_today,
            "remaining_daily_risk": self.get_remaining_daily_risk(),
            "is_halted": self.state.is_halted,
            "halt_reason": self.state.halt_reason,
            "limits": {
                "max_risk_per_trade": self.config.max_risk_per_trade * 100,
                "max_daily_loss": self.config.max_daily_loss * 100,
                "max_weekly_loss": self.config.max_weekly_loss * 100,
                "max_drawdown": self.config.max_drawdown * 100,
            },
        }
    
    def _halt(self, reason: str) -> None:
        """Halt trading"""
        self.state.is_halted = True
        self.state.halt_reason = reason
        logger.warning(f"TRADING HALTED: {reason}")
    
    def _is_weekend_close_time(self) -> bool:
        """Check if it's time to close for weekend"""
        now = datetime.now()
        return (
            now.weekday() == self.config.weekend_close_day
            and now.hour >= self.config.weekend_close_hour
        ) or now.weekday() > self.config.weekend_close_day
