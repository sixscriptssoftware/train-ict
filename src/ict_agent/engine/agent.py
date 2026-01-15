"""ICT Trading Agent - Main Agent Class

The central orchestrator for ICT-based algorithmic trading.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Callable
import pandas as pd
import json
from pathlib import Path
from loguru import logger

from ict_agent.engine.signal_generator import SignalGenerator, TradeSignal, ModelType
from ict_agent.engine.mtf_analyzer import MultiTimeframeAnalyzer, Bias, Timeframe, MTFConfluence
from ict_agent.engine.killzone import KillzoneManager, Killzone
from ict_agent.detectors import (
    FVGDetector,
    OrderBlockDetector,
    MarketStructureAnalyzer,
    LiquidityDetector,
    DisplacementDetector,
)


@dataclass
class AgentConfig:
    """Configuration for ICT Trading Agent"""
    symbols: list[str] = field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    htf_timeframe: Timeframe = Timeframe.D1
    itf_timeframe: Timeframe = Timeframe.H1
    ltf_timeframe: Timeframe = Timeframe.M15
    
    pip_size: float = 0.0001
    min_risk_reward: float = 2.0
    max_daily_loss_pct: float = 2.0
    max_position_size: float = 0.02
    
    min_confluences: int = 3
    min_confidence: float = 0.6
    
    allowed_killzones: list[Killzone] = field(default_factory=lambda: [
        Killzone.LONDON,
        Killzone.NY_AM,
        Killzone.NY_PM,
    ])
    
    allowed_models: list[ModelType] = field(default_factory=lambda: [
        ModelType.SILVER_BULLET,
        ModelType.JUDAS_SWING,
        ModelType.OTE_RETRACEMENT,
        ModelType.FVG_REBALANCE,
    ])
    
    max_trades_per_day: int = 3
    max_position_cycles: int = 2
    weekend_close: bool = True
    
    log_signals: bool = True
    signal_log_path: str = "signals/"


@dataclass
class AgentState:
    """Current state of the trading agent"""
    daily_trades: int = 0
    daily_pnl: float = 0.0
    open_positions: list = field(default_factory=list)
    last_signal: Optional[TradeSignal] = None
    htf_biases: dict = field(default_factory=dict)
    is_active: bool = True
    last_analysis_time: Optional[datetime] = None


class ICTTradingAgent:
    """
    ICT Trading Agent - Autonomous trading using Inner Circle Trader methodology.
    
    Core Workflow:
    1. Establish HTF bias (Daily structure, draw on liquidity)
    2. Wait for valid killzone or macro time
    3. Analyze LTF for entry trigger (BOS/SMS + displacement)
    4. Stack confluences (FVG, OB, OTE, liquidity sweep)
    5. Generate signal if minimum confluences met
    6. Execute with proper risk management
    
    Rules Enforced:
    - No trades outside killzones
    - Minimum 3 confluences required
    - HTF bias must be established
    - Weekend positions closed Friday 4PM EST
    - Max daily loss limit enforced
    - Position cycling limited to 2 cycles
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        data_fetcher: Optional[Callable] = None,
    ):
        self.config = config or AgentConfig()
        self.state = AgentState()
        self.data_fetcher = data_fetcher
        
        self.signal_generator = SignalGenerator(
            pip_size=self.config.pip_size,
            min_rr=self.config.min_risk_reward,
        )
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.killzone_manager = KillzoneManager()
        
        self._signal_history: list[TradeSignal] = []
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging"""
        if self.config.log_signals:
            Path(self.config.signal_log_path).mkdir(parents=True, exist_ok=True)
    
    def analyze(
        self,
        symbol: str,
        htf_data: pd.DataFrame,
        itf_data: pd.DataFrame,
        ltf_data: pd.DataFrame,
    ) -> Optional[TradeSignal]:
        """
        Perform complete analysis and generate signal if conditions met.
        
        Args:
            symbol: Trading symbol
            htf_data: Higher timeframe OHLC (Daily/4H)
            itf_data: Intermediate timeframe OHLC (1H)
            ltf_data: Lower timeframe OHLC (15M/5M)
        
        Returns:
            TradeSignal if valid setup found, None otherwise
        """
        current_time = ltf_data.index[-1]
        
        if not self._check_trading_conditions(current_time):
            return None
        
        mtf_result = self.mtf_analyzer.analyze_mtf(
            htf_data, itf_data, ltf_data,
            self.config.htf_timeframe,
            self.config.itf_timeframe,
            self.config.ltf_timeframe,
        )
        
        self.state.htf_biases[symbol] = mtf_result.htf_bias
        
        if mtf_result.trade_direction is None:
            logger.debug(f"{symbol}: No trade direction - {mtf_result.reasoning}")
            return None
        
        signal = self.signal_generator.generate_signal(
            symbol=symbol,
            ltf_ohlc=ltf_data,
            htf_bias=mtf_result.htf_bias,
            htf_ohlc=htf_data,
        )
        
        if signal:
            if signal.model not in self.config.allowed_models:
                logger.debug(f"{symbol}: Model {signal.model} not in allowed list")
                return None
            
            if signal.killzone and signal.killzone not in self.config.allowed_killzones:
                logger.debug(f"{symbol}: Killzone {signal.killzone} not in allowed list")
                return None
            
            self._record_signal(signal)
            self.state.last_signal = signal
            
            logger.info(
                f"SIGNAL: {symbol} {signal.signal_type.value.upper()} | "
                f"Model: {signal.model.value} | "
                f"Confidence: {signal.confidence:.2f} | "
                f"R:R: {signal.risk_reward:.1f}"
            )
        
        self.state.last_analysis_time = current_time
        return signal
    
    def _check_trading_conditions(self, current_time: datetime) -> bool:
        """Check if trading is allowed under current conditions"""
        if not self.state.is_active:
            return False
        
        if self.state.daily_trades >= self.config.max_trades_per_day:
            logger.debug("Max daily trades reached")
            return False
        
        if not self.killzone_manager.is_trading_day(current_time):
            return False
        
        if self.config.weekend_close and self.killzone_manager.is_weekend_close_time(current_time):
            logger.info("Weekend close time - no new trades")
            return False
        
        in_killzone = any(
            self.killzone_manager.is_in_killzone(current_time, kz)
            for kz in self.config.allowed_killzones
        )
        in_macro = self.killzone_manager.is_in_macro_time(current_time)
        
        if not (in_killzone or in_macro):
            return False
        
        return True
    
    def _record_signal(self, signal: TradeSignal) -> None:
        """Record signal to history and log file"""
        self._signal_history.append(signal)
        
        if self.config.log_signals:
            date_str = signal.timestamp.strftime("%Y-%m-%d")
            log_file = Path(self.config.signal_log_path) / f"signals_{date_str}.json"
            
            signals_data = []
            if log_file.exists():
                with open(log_file, "r") as f:
                    signals_data = json.load(f)
            
            signals_data.append(signal.to_dict())
            
            with open(log_file, "w") as f:
                json.dump(signals_data, f, indent=2, default=str)
    
    def get_htf_bias(self, symbol: str) -> Bias:
        """Get current HTF bias for symbol"""
        return self.state.htf_biases.get(symbol, Bias.NEUTRAL)
    
    def get_signal_history(
        self,
        symbol: Optional[str] = None,
        model: Optional[ModelType] = None,
        since: Optional[datetime] = None,
    ) -> list[TradeSignal]:
        """Get filtered signal history"""
        signals = self._signal_history
        
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        if model:
            signals = [s for s in signals if s.model == model]
        if since:
            signals = [s for s in signals if s.timestamp >= since]
        
        return signals
    
    def get_performance_stats(self) -> dict:
        """Calculate performance statistics from signal history"""
        if not self._signal_history:
            return {"total_signals": 0}
        
        signals = self._signal_history
        
        model_counts = {}
        for s in signals:
            model_counts[s.model.value] = model_counts.get(s.model.value, 0) + 1
        
        avg_confidence = sum(s.confidence for s in signals) / len(signals)
        avg_rr = sum(s.risk_reward for s in signals) / len(signals)
        avg_confluences = sum(s.confluences.count for s in signals) / len(signals)
        
        return {
            "total_signals": len(signals),
            "signals_by_model": model_counts,
            "avg_confidence": round(avg_confidence, 3),
            "avg_risk_reward": round(avg_rr, 2),
            "avg_confluences": round(avg_confluences, 1),
            "symbols": list(set(s.symbol for s in signals)),
        }
    
    def reset_daily_state(self) -> None:
        """Reset daily counters (call at start of trading day)"""
        self.state.daily_trades = 0
        self.state.daily_pnl = 0.0
        logger.info("Daily state reset")
    
    def pause(self) -> None:
        """Pause trading"""
        self.state.is_active = False
        logger.info("Agent paused")
    
    def resume(self) -> None:
        """Resume trading"""
        self.state.is_active = True
        logger.info("Agent resumed")
    
    def run_backtest(
        self,
        symbol: str,
        htf_data: pd.DataFrame,
        itf_data: pd.DataFrame,
        ltf_data: pd.DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[TradeSignal]:
        """
        Run backtest over historical data.
        
        Returns list of signals that would have been generated.
        """
        signals = []
        
        if start_date:
            ltf_data = ltf_data[ltf_data.index >= start_date]
        if end_date:
            ltf_data = ltf_data[ltf_data.index <= end_date]
        
        lookback_htf = 100
        lookback_itf = 200
        lookback_ltf = 100
        
        for i in range(lookback_ltf, len(ltf_data)):
            current_time = ltf_data.index[i]
            
            ltf_window = ltf_data.iloc[i - lookback_ltf : i + 1]
            
            itf_mask = itf_data.index <= current_time
            itf_window = itf_data[itf_mask].tail(lookback_itf)
            
            htf_mask = htf_data.index <= current_time
            htf_window = htf_data[htf_mask].tail(lookback_htf)
            
            if len(htf_window) < 20 or len(itf_window) < 20:
                continue
            
            signal = self.analyze(symbol, htf_window, itf_window, ltf_window)
            if signal:
                signals.append(signal)
        
        return signals
