"""Silver Bullet Model

ICT's precision entry model for specific 1-hour windows with high probability setups.
"""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional
import pandas as pd

from ict_agent.detectors.fvg import FVGDetector, FVGDirection, FVG
from ict_agent.detectors.displacement import DisplacementDetector, DisplacementDirection
from ict_agent.detectors.market_structure import MarketStructureAnalyzer, StructureType
from ict_agent.engine.killzone import KillzoneManager


@dataclass
class SilverBulletSetup:
    """A valid Silver Bullet setup"""
    timestamp: datetime
    window: str
    direction: str
    fvg: FVG
    entry_price: float
    stop_loss: float
    target: float
    risk_reward: float
    has_displacement: bool


class SilverBulletModel:
    """
    ICT Silver Bullet Model
    
    Windows (EST):
    - London: 3:00 AM - 4:00 AM
    - NY AM: 10:00 AM - 11:00 AM  
    - NY PM: 2:00 PM - 3:00 PM
    
    Setup Requirements:
    1. Within Silver Bullet window
    2. HTF bias established
    3. Displacement creating FVG
    4. Entry on FVG retracement
    
    Entry:
    - Wait for displacement in direction of bias
    - Enter on retracement to FVG (50% or deeper)
    - Stop below FVG (longs) or above FVG (shorts)
    - Target: Previous swing or 2R minimum
    """
    
    WINDOWS = {
        "london": (time(3, 0), time(4, 0)),
        "ny_am": (time(10, 0), time(11, 0)),
        "ny_pm": (time(14, 0), time(15, 0)),
    }
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
        self.fvg_detector = FVGDetector(pip_size=pip_size)
        self.displacement_detector = DisplacementDetector()
        self.structure_analyzer = MarketStructureAnalyzer()
        self.killzone_manager = KillzoneManager()
    
    def scan(
        self,
        ohlc: pd.DataFrame,
        htf_bias: str,
    ) -> Optional[SilverBulletSetup]:
        """
        Scan for Silver Bullet setup.
        
        Args:
            ohlc: 5M or 15M OHLC data
            htf_bias: "bullish" or "bearish"
        
        Returns:
            SilverBulletSetup if valid, None otherwise
        """
        current_time = ohlc.index[-1]
        
        window = self._get_active_window(current_time)
        if not window:
            return None
        
        self.fvg_detector.detect(ohlc)
        self.displacement_detector.detect(ohlc)
        
        if htf_bias == "bullish":
            fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BULLISH)
            displacement = self.displacement_detector.get_recent_displacement(
                DisplacementDirection.BULLISH
            )
        else:
            fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BEARISH)
            displacement = self.displacement_detector.get_recent_displacement(
                DisplacementDirection.BEARISH
            )
        
        if not displacement:
            return None
        
        current_price = ohlc.iloc[-1]["close"]
        valid_fvgs = []
        
        for fvg in fvgs:
            window_start = self._get_window_start_index(ohlc, window)
            if fvg.index >= window_start:
                if fvg.contains_price(current_price):
                    valid_fvgs.append(fvg)
        
        if not valid_fvgs:
            return None
        
        target_fvg = valid_fvgs[-1]
        
        entry = target_fvg.midpoint
        
        if htf_bias == "bullish":
            stop = target_fvg.bottom - (5 * self.pip_size)
            swing_high = ohlc["high"].max()
            target = swing_high
        else:
            stop = target_fvg.top + (5 * self.pip_size)
            swing_low = ohlc["low"].min()
            target = swing_low
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0
        
        return SilverBulletSetup(
            timestamp=current_time,
            window=window,
            direction=htf_bias,
            fvg=target_fvg,
            entry_price=entry,
            stop_loss=stop,
            target=target,
            risk_reward=rr,
            has_displacement=True,
        )
    
    def _get_active_window(self, dt: datetime) -> Optional[str]:
        """Check if current time is in a Silver Bullet window"""
        current_time = dt.time()
        
        for window_name, (start, end) in self.WINDOWS.items():
            if start <= current_time <= end:
                return window_name
        
        return None
    
    def _get_window_start_index(self, ohlc: pd.DataFrame, window: str) -> int:
        """Get the index where the current window started"""
        window_start_time = self.WINDOWS[window][0]
        
        for i, idx in enumerate(ohlc.index):
            if idx.time() >= window_start_time:
                return i
        
        return 0
