"""Power of Three Model

ICT's session-based accumulation/manipulation/distribution model.
"""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Optional
import pandas as pd
import numpy as np


class PO3Phase(Enum):
    ACCUMULATION = "accumulation"
    MANIPULATION = "manipulation"
    DISTRIBUTION = "distribution"


@dataclass
class PO3Setup:
    """A valid Power of Three setup"""
    timestamp: datetime
    session: str
    current_phase: PO3Phase
    direction: str
    accumulation_range: tuple[float, float]
    manipulation_level: float
    entry_price: float
    stop_loss: float
    target: float
    risk_reward: float


class PowerOfThreeModel:
    """
    ICT Power of Three Model
    
    The three phases of price delivery:
    1. Accumulation: Range-bound consolidation (Smart Money building position)
    2. Manipulation: False breakout/stop hunt (Judas move)
    3. Distribution: True directional move (expansion)
    
    Session Application:
    - Asian session = Accumulation
    - London open = Manipulation
    - NY session = Distribution
    
    OR within any session:
    - First 30 min = Accumulation
    - Next 30 min = Manipulation  
    - Rest of session = Distribution
    
    Trading:
    - Identify accumulation range
    - Wait for manipulation (false break)
    - Enter on confirmation of distribution
    """
    
    SESSIONS = {
        "asia": (time(19, 0), time(0, 0)),
        "london": (time(2, 0), time(5, 0)),
        "ny": (time(7, 0), time(16, 0)),
    }
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
    
    def identify_phase(
        self,
        ohlc: pd.DataFrame,
        session: str = "ny",
    ) -> PO3Phase:
        """
        Identify current Power of Three phase.
        
        Returns the current phase based on session timing and price action.
        """
        if len(ohlc) < 10:
            return PO3Phase.ACCUMULATION
        
        current_time = ohlc.index[-1]
        session_data = self._get_session_data(ohlc, session)
        
        if len(session_data) < 5:
            return PO3Phase.ACCUMULATION
        
        session_start = session_data.index[0]
        minutes_elapsed = (current_time - session_start).total_seconds() / 60
        
        if minutes_elapsed < 30:
            return PO3Phase.ACCUMULATION
        elif minutes_elapsed < 60:
            return PO3Phase.MANIPULATION
        else:
            return PO3Phase.DISTRIBUTION
    
    def scan(
        self,
        ohlc: pd.DataFrame,
        session: str = "ny",
    ) -> Optional[PO3Setup]:
        """
        Scan for Power of Three setup.
        
        Returns:
            PO3Setup if in distribution phase with valid setup, None otherwise
        """
        current_phase = self.identify_phase(ohlc, session)
        
        if current_phase != PO3Phase.DISTRIBUTION:
            return None
        
        session_data = self._get_session_data(ohlc, session)
        if len(session_data) < 10:
            return None
        
        accum_data = session_data.head(6)
        accum_high = accum_data["high"].max()
        accum_low = accum_data["low"].min()
        accum_range = (accum_low, accum_high)
        
        manip_data = session_data.iloc[6:12] if len(session_data) > 12 else session_data.iloc[6:]
        
        if len(manip_data) == 0:
            return None
        
        manip_high = manip_data["high"].max()
        manip_low = manip_data["low"].min()
        
        broke_high = manip_high > accum_high
        broke_low = manip_low < accum_low
        
        if not (broke_high or broke_low):
            return None
        
        current_price = ohlc.iloc[-1]["close"]
        
        if broke_high and current_price < accum_high:
            direction = "bearish"
            manipulation_level = manip_high
            entry = current_price
            stop = manip_high + (10 * self.pip_size)
            target = accum_low
        elif broke_low and current_price > accum_low:
            direction = "bullish"
            manipulation_level = manip_low
            entry = current_price
            stop = manip_low - (10 * self.pip_size)
            target = accum_high
        else:
            return None
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0
        
        if rr < 1.5:
            return None
        
        return PO3Setup(
            timestamp=ohlc.index[-1],
            session=session,
            current_phase=current_phase,
            direction=direction,
            accumulation_range=accum_range,
            manipulation_level=manipulation_level,
            entry_price=entry,
            stop_loss=stop,
            target=target,
            risk_reward=rr,
        )
    
    def _get_session_data(
        self, ohlc: pd.DataFrame, session: str
    ) -> pd.DataFrame:
        """Extract data for the current session"""
        if session not in self.SESSIONS:
            return ohlc.tail(50)
        
        start_time, end_time = self.SESSIONS[session]
        
        current_date = ohlc.index[-1].date()
        
        mask = ohlc.index.map(
            lambda dt: self._time_in_session(dt.time(), start_time, end_time)
            and dt.date() == current_date
        )
        
        return ohlc[mask]
    
    def _time_in_session(
        self, t: time, start: time, end: time
    ) -> bool:
        """Check if time is within session"""
        if start <= end:
            return start <= t <= end
        else:
            return t >= start or t <= end
