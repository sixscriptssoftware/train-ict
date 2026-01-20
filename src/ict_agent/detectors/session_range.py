"""
Session Ranges Detector

Detects key ICT ranges:
- Asian Range (7 PM - 12 AM ET)
- London Range (2 AM - 5 AM ET)  
- NY Range (7 AM - 10 AM ET)
- CBDR (Central Bank Dealers Range) - 2 PM - 8 PM ET
- Previous Day High/Low
- Previous Week High/Low
"""

from dataclasses import dataclass
from typing import Optional, Literal
from datetime import datetime, timedelta, time
import pandas as pd
import numpy as np
import pytz


@dataclass
class SessionRange:
    """A session's high/low range"""
    session: str
    date: datetime
    high: float
    low: float
    open: float
    close: float
    midpoint: float  # Equilibrium
    range_pips: float
    broken_high: bool = False
    broken_low: bool = False


@dataclass
class KeyLevel:
    """Previous day/week/month levels"""
    level_type: str  # PDH, PDL, PWH, PWL, PMH, PML
    price: float
    date: datetime
    swept: bool = False


class SessionRangeDetector:
    """
    Detects ICT session ranges and key levels.
    
    Asian Range: Accumulation phase
    London Range: Often manipulation
    NY Range: Distribution
    
    CBDR (Central Bank Dealers Range): 
    - 2 PM - 8 PM ET
    - This is where central banks and dealers set their positions
    - Very important for next day's direction
    """
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
        self.et = pytz.timezone('America/New_York')
        self.utc = pytz.UTC
        
        # Session times in ET
        self.sessions = {
            'ASIAN': {'start': 19, 'end': 0},  # 7 PM - 12 AM
            'LONDON': {'start': 2, 'end': 5},   # 2 AM - 5 AM
            'NY_AM': {'start': 7, 'end': 10},   # 7 AM - 10 AM (Killzone)
            'NY_PM': {'start': 13, 'end': 16},  # 1 PM - 4 PM
            'CBDR': {'start': 14, 'end': 20},   # 2 PM - 8 PM
        }
    
    def detect(self, ohlc: pd.DataFrame) -> dict:
        """
        Detect all session ranges and key levels.
        
        Returns:
            {
                'asian_range': SessionRange,
                'london_range': SessionRange,
                'ny_range': SessionRange,
                'cbdr': SessionRange,
                'pdh': KeyLevel,  # Previous Day High
                'pdl': KeyLevel,  # Previous Day Low
                'pwh': KeyLevel,  # Previous Week High
                'pwl': KeyLevel,  # Previous Week Low
                'current_session': str,
                'price_vs_ranges': dict,  # Where is price relative to each range
            }
        """
        # Convert index to ET
        ohlc_et = self._convert_to_et(ohlc)
        
        # Detect ranges
        asian = self._detect_session_range(ohlc_et, 'ASIAN')
        london = self._detect_session_range(ohlc_et, 'LONDON')
        ny = self._detect_session_range(ohlc_et, 'NY_AM')
        cbdr = self._detect_session_range(ohlc_et, 'CBDR')
        
        # Get key levels
        pdh, pdl = self._get_previous_day_hl(ohlc_et)
        pwh, pwl = self._get_previous_week_hl(ohlc_et)
        
        # Current session
        current = self._get_current_session(ohlc_et)
        
        # Check where price is relative to ranges
        current_price = ohlc['close'].iloc[-1]
        price_vs = {}
        
        for name, range_obj in [('asian', asian), ('london', london), ('ny', ny), ('cbdr', cbdr)]:
            if range_obj:
                if current_price > range_obj.high:
                    price_vs[name] = 'ABOVE'
                elif current_price < range_obj.low:
                    price_vs[name] = 'BELOW'
                elif current_price > range_obj.midpoint:
                    price_vs[name] = 'PREMIUM'
                else:
                    price_vs[name] = 'DISCOUNT'
        
        return {
            'asian_range': asian,
            'london_range': london,
            'ny_range': ny,
            'cbdr': cbdr,
            'pdh': pdh,
            'pdl': pdl,
            'pwh': pwh,
            'pwl': pwl,
            'current_session': current,
            'price_vs_ranges': price_vs,
        }
    
    def _convert_to_et(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Convert DataFrame index to ET timezone"""
        df = ohlc.copy()
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert(self.et)
        return df
    
    def _detect_session_range(self, ohlc: pd.DataFrame, session: str) -> Optional[SessionRange]:
        """Detect a specific session's range"""
        times = self.sessions.get(session)
        if not times:
            return None
        
        start_hour = times['start']
        end_hour = times['end']
        
        # Filter for session candles (today or yesterday)
        now = ohlc.index[-1]
        today = now.date()
        
        # Handle overnight sessions (Asian starts previous day)
        if session == 'ASIAN':
            # Asian session spans midnight
            session_candles = ohlc[
                ((ohlc.index.hour >= start_hour) | (ohlc.index.hour < end_hour)) &
                (ohlc.index.date >= today - timedelta(days=1))
            ]
        else:
            session_candles = ohlc[
                (ohlc.index.hour >= start_hour) & 
                (ohlc.index.hour < end_hour) &
                (ohlc.index.date == today)
            ]
        
        # If no candles today, try yesterday
        if len(session_candles) == 0:
            yesterday = today - timedelta(days=1)
            session_candles = ohlc[
                (ohlc.index.hour >= start_hour) & 
                (ohlc.index.hour < end_hour) &
                (ohlc.index.date == yesterday)
            ]
        
        if len(session_candles) == 0:
            return None
        
        high = session_candles['high'].max()
        low = session_candles['low'].min()
        open_price = session_candles['open'].iloc[0]
        close_price = session_candles['close'].iloc[-1]
        midpoint = (high + low) / 2
        range_pips = (high - low) / self.pip_size
        
        # Check if range has been broken
        current_price = ohlc['close'].iloc[-1]
        broken_high = current_price > high
        broken_low = current_price < low
        
        return SessionRange(
            session=session,
            date=session_candles.index[0].date(),
            high=high,
            low=low,
            open=open_price,
            close=close_price,
            midpoint=midpoint,
            range_pips=range_pips,
            broken_high=broken_high,
            broken_low=broken_low
        )
    
    def _get_previous_day_hl(self, ohlc: pd.DataFrame) -> tuple:
        """Get previous day's high and low"""
        today = ohlc.index[-1].date()
        yesterday = today - timedelta(days=1)
        
        # Skip weekends
        while yesterday.weekday() >= 5:  # Saturday = 5, Sunday = 6
            yesterday -= timedelta(days=1)
        
        yesterday_candles = ohlc[ohlc.index.date == yesterday]
        
        if len(yesterday_candles) == 0:
            return None, None
        
        pdh = KeyLevel(
            level_type='PDH',
            price=yesterday_candles['high'].max(),
            date=yesterday,
            swept=ohlc['high'].iloc[-20:].max() > yesterday_candles['high'].max()
        )
        
        pdl = KeyLevel(
            level_type='PDL',
            price=yesterday_candles['low'].min(),
            date=yesterday,
            swept=ohlc['low'].iloc[-20:].min() < yesterday_candles['low'].min()
        )
        
        return pdh, pdl
    
    def _get_previous_week_hl(self, ohlc: pd.DataFrame) -> tuple:
        """Get previous week's high and low"""
        today = ohlc.index[-1].date()
        
        # Find start and end of previous week
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        prev_monday = this_monday - timedelta(days=7)
        prev_friday = prev_monday + timedelta(days=4)
        
        prev_week_candles = ohlc[
            (ohlc.index.date >= prev_monday) & 
            (ohlc.index.date <= prev_friday)
        ]
        
        if len(prev_week_candles) == 0:
            return None, None
        
        pwh = KeyLevel(
            level_type='PWH',
            price=prev_week_candles['high'].max(),
            date=prev_friday,
            swept=ohlc['high'].max() > prev_week_candles['high'].max()
        )
        
        pwl = KeyLevel(
            level_type='PWL',
            price=prev_week_candles['low'].min(),
            date=prev_friday,
            swept=ohlc['low'].min() < prev_week_candles['low'].min()
        )
        
        return pwh, pwl
    
    def _get_current_session(self, ohlc: pd.DataFrame) -> str:
        """Determine current session"""
        now = ohlc.index[-1]
        hour = now.hour
        
        if 19 <= hour or hour < 0:
            return 'ASIAN'
        elif 0 <= hour < 2:
            return 'ASIAN_LATE'
        elif 2 <= hour < 5:
            return 'LONDON'
        elif 5 <= hour < 7:
            return 'LONDON_CLOSE'
        elif 7 <= hour < 10:
            return 'NY_AM'
        elif 10 <= hour < 13:
            return 'NY_LUNCH'
        elif 13 <= hour < 16:
            return 'NY_PM'
        elif 16 <= hour < 19:
            return 'NY_CLOSE'
        
        return 'UNKNOWN'
    
    def get_range_extension_targets(self, session_range: SessionRange) -> dict:
        """
        Calculate standard deviation extension targets from range.
        
        ICT uses these for take profit levels:
        - 1x range = first target
        - 1.5x range = conservative target
        - 2x range = standard target
        - 2.5x range = extended target
        """
        if not session_range:
            return {}
        
        range_size = session_range.high - session_range.low
        
        return {
            'long_targets': {
                '1x': session_range.high + range_size,
                '1.5x': session_range.high + (range_size * 1.5),
                '2x': session_range.high + (range_size * 2),
                '2.5x': session_range.high + (range_size * 2.5),
            },
            'short_targets': {
                '1x': session_range.low - range_size,
                '1.5x': session_range.low - (range_size * 1.5),
                '2x': session_range.low - (range_size * 2),
                '2.5x': session_range.low - (range_size * 2.5),
            }
        }
