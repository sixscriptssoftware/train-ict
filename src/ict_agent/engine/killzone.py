"""Killzone Time Management Module

Manages ICT trading time windows (Killzones) when institutional
activity is highest.
"""

from dataclasses import dataclass
from enum import Enum
from datetime import datetime, time, timezone, timedelta
from typing import Optional
import pandas as pd


class Killzone(Enum):
    ASIA = "asia"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_LUNCH = "ny_lunch"
    NY_PM = "ny_pm"
    SILVER_BULLET_LONDON = "silver_bullet_london"
    SILVER_BULLET_NY_AM = "silver_bullet_ny_am"
    SILVER_BULLET_NY_PM = "silver_bullet_ny_pm"


@dataclass
class KillzoneWindow:
    """Defines a killzone time window"""
    name: Killzone
    start: time
    end: time
    priority: int
    is_primary: bool


@dataclass 
class MacroTime:
    """ICT Macro time windows for precision entries"""
    name: str
    minute_start: int
    minute_end: int


class KillzoneManager:
    """
    Manages ICT Killzone timing for trade filtering.
    
    Primary Killzones (EST/EDT):
    - Asia: 7:00 PM - 12:00 AM (accumulation, range building)
    - London: 2:00 AM - 5:00 AM (first expansion)
    - NY AM: 7:00 AM - 10:00 AM (highest volatility)
    - NY Lunch: 12:00 PM - 1:00 PM (avoid - choppy)
    - NY PM: 1:00 PM - 4:00 PM (second expansion)
    
    Silver Bullet Windows:
    - London: 3:00 AM - 4:00 AM EST
    - NY AM: 10:00 AM - 11:00 AM EST
    - NY PM: 2:00 PM - 3:00 PM EST
    
    Macro Times (precision windows):
    - :02 to :10 (2 to 10 minutes past hour)
    - :18 to :20
    - :28 to :33
    - :48 to :53
    - :58 to :02 (wrapping to next hour)
    """
    
    KILLZONES = {
        Killzone.ASIA: KillzoneWindow(
            name=Killzone.ASIA,
            start=time(19, 0),
            end=time(23, 59),
            priority=3,
            is_primary=False,
        ),
        Killzone.LONDON: KillzoneWindow(
            name=Killzone.LONDON,
            start=time(2, 0),
            end=time(5, 0),
            priority=2,
            is_primary=True,
        ),
        Killzone.NY_AM: KillzoneWindow(
            name=Killzone.NY_AM,
            start=time(7, 0),
            end=time(10, 0),
            priority=1,
            is_primary=True,
        ),
        Killzone.NY_LUNCH: KillzoneWindow(
            name=Killzone.NY_LUNCH,
            start=time(12, 0),
            end=time(13, 0),
            priority=5,
            is_primary=False,
        ),
        Killzone.NY_PM: KillzoneWindow(
            name=Killzone.NY_PM,
            start=time(13, 0),
            end=time(16, 0),
            priority=2,
            is_primary=True,
        ),
        Killzone.SILVER_BULLET_LONDON: KillzoneWindow(
            name=Killzone.SILVER_BULLET_LONDON,
            start=time(3, 0),
            end=time(4, 0),
            priority=1,
            is_primary=True,
        ),
        Killzone.SILVER_BULLET_NY_AM: KillzoneWindow(
            name=Killzone.SILVER_BULLET_NY_AM,
            start=time(10, 0),
            end=time(11, 0),
            priority=1,
            is_primary=True,
        ),
        Killzone.SILVER_BULLET_NY_PM: KillzoneWindow(
            name=Killzone.SILVER_BULLET_NY_PM,
            start=time(14, 0),
            end=time(15, 0),
            priority=1,
            is_primary=True,
        ),
    }
    
    MACRO_TIMES = [
        MacroTime(name="macro_1", minute_start=2, minute_end=10),
        MacroTime(name="macro_2", minute_start=18, minute_end=20),
        MacroTime(name="macro_3", minute_start=28, minute_end=33),
        MacroTime(name="macro_4", minute_start=48, minute_end=53),
        MacroTime(name="macro_5", minute_start=58, minute_end=2),
    ]
    
    def __init__(self, timezone_offset: int = -5):
        self.timezone_offset = timezone_offset
    
    def get_current_killzone(self, dt: datetime) -> Optional[Killzone]:
        """Get the active killzone for given datetime (in EST)"""
        est_time = self._to_est(dt).time()
        
        for kz, window in self.KILLZONES.items():
            if self._time_in_range(est_time, window.start, window.end):
                return kz
        
        return None
    
    def is_in_killzone(
        self, dt: datetime, killzone: Optional[Killzone] = None
    ) -> bool:
        """Check if datetime is within a killzone"""
        current = self.get_current_killzone(dt)
        
        if killzone:
            return current == killzone
        
        return current is not None
    
    def is_primary_killzone(self, dt: datetime) -> bool:
        """Check if datetime is within a primary trading killzone"""
        kz = self.get_current_killzone(dt)
        if kz:
            return self.KILLZONES[kz].is_primary
        return False
    
    def is_in_macro_time(self, dt: datetime) -> bool:
        """Check if datetime is within an ICT macro time window"""
        minute = self._to_est(dt).minute
        
        for macro in self.MACRO_TIMES:
            if macro.minute_start <= macro.minute_end:
                if macro.minute_start <= minute <= macro.minute_end:
                    return True
            else:
                if minute >= macro.minute_start or minute <= macro.minute_end:
                    return True
        
        return False
    
    def is_silver_bullet_window(self, dt: datetime) -> bool:
        """Check if datetime is within a Silver Bullet window"""
        kz = self.get_current_killzone(dt)
        return kz in [
            Killzone.SILVER_BULLET_LONDON,
            Killzone.SILVER_BULLET_NY_AM,
            Killzone.SILVER_BULLET_NY_PM,
        ]
    
    def get_killzone_priority(self, dt: datetime) -> int:
        """Get priority score of current killzone (lower is better)"""
        kz = self.get_current_killzone(dt)
        if kz:
            return self.KILLZONES[kz].priority
        return 10
    
    def get_next_killzone(
        self, dt: datetime, primary_only: bool = True
    ) -> tuple[Killzone, datetime]:
        """Get next upcoming killzone and its start time"""
        est_dt = self._to_est(dt)
        current_time = est_dt.time()
        current_date = est_dt.date()
        
        candidates = []
        for kz, window in self.KILLZONES.items():
            if primary_only and not window.is_primary:
                continue
            
            if window.start > current_time:
                start_dt = datetime.combine(current_date, window.start)
                candidates.append((kz, start_dt))
            else:
                next_date = current_date + timedelta(days=1)
                start_dt = datetime.combine(next_date, window.start)
                candidates.append((kz, start_dt))
        
        if candidates:
            return min(candidates, key=lambda x: x[1])
        
        return (Killzone.NY_AM, datetime.combine(current_date + timedelta(days=1), time(7, 0)))
    
    def is_trading_day(self, dt: datetime) -> bool:
        """Check if it's a valid trading day (Mon-Fri)"""
        weekday = self._to_est(dt).weekday()
        return weekday < 5
    
    def is_weekend_close_time(self, dt: datetime) -> bool:
        """Check if it's time to close positions for weekend"""
        est_dt = self._to_est(dt)
        return est_dt.weekday() == 4 and est_dt.hour >= 16
    
    def filter_by_killzone(
        self, ohlc: pd.DataFrame, killzones: Optional[list[Killzone]] = None
    ) -> pd.DataFrame:
        """Filter OHLC data to only include rows within specified killzones"""
        if killzones is None:
            killzones = [Killzone.LONDON, Killzone.NY_AM, Killzone.NY_PM]
        
        mask = ohlc.index.map(lambda dt: self.get_current_killzone(dt) in killzones)
        return ohlc[mask]
    
    def add_killzone_column(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Add killzone information columns to OHLC DataFrame"""
        df = ohlc.copy()
        df["killzone"] = df.index.map(
            lambda dt: self.get_current_killzone(dt).value
            if self.get_current_killzone(dt)
            else ""
        )
        df["is_primary_kz"] = df.index.map(self.is_primary_killzone)
        df["is_macro_time"] = df.index.map(self.is_in_macro_time)
        df["is_silver_bullet"] = df.index.map(self.is_silver_bullet_window)
        return df
    
    def _to_est(self, dt: datetime) -> datetime:
        """Convert datetime to EST (assuming input is UTC if no tz)"""
        if dt.tzinfo is None:
            utc_dt = dt.replace(tzinfo=timezone.utc)
        else:
            utc_dt = dt.astimezone(timezone.utc)
        
        est_offset = timedelta(hours=self.timezone_offset)
        return utc_dt + est_offset
    
    def _time_in_range(self, t: time, start: time, end: time) -> bool:
        """Check if time is within range (handles midnight crossing)"""
        if start <= end:
            return start <= t <= end
        else:
            return t >= start or t <= end
