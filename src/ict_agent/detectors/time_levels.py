"""
ICT Time-Based PD Arrays

- Previous Day High/Low (PDH/PDL)
- Previous Week High/Low (PWH/PWL)  
- Previous Month High/Low
- Midnight Opening Price
- Weekly Opening Price
- True Day Open (6pm EST prior day)
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz


@dataclass
class PDArray:
    """
    Price Delivery Array from time-based levels.
    """
    name: str
    level: float
    level_type: Literal["HIGH", "LOW", "OPEN"]
    timeframe: str  # "DAILY", "WEEKLY", "MONTHLY"
    is_premium: bool  # Above current price
    distance_pips: float


@dataclass
class OpeningPrices:
    """
    Key opening prices for ICT analysis.
    """
    true_day_open: float  # 6pm EST prior day
    midnight_open: float  # Midnight EST
    weekly_open: float  # Sunday 6pm EST
    asia_open: float  # 7pm EST
    london_open: float  # 2am EST
    ny_open: float  # 8:30am EST


@dataclass
class KeyTimeLevels:
    """
    All time-based levels compiled.
    """
    pdh: float  # Previous Day High
    pdl: float  # Previous Day Low
    pwh: float  # Previous Week High
    pwl: float  # Previous Week Low
    pmh: float  # Previous Month High
    pml: float  # Previous Month Low
    opening_prices: OpeningPrices
    

class TimeBasedLevelsDetector:
    """
    Detects time-based ICT levels (PDH/PDL, PWH/PWL, etc.)
    """
    
    def __init__(self, pip_size: float = 0.0001):
        self.pip_size = pip_size
        self.et = pytz.timezone('America/New_York')
        self.utc = pytz.UTC
    
    def get_all_levels(self, ohlc: pd.DataFrame) -> KeyTimeLevels:
        """
        Get all time-based key levels.
        
        Args:
            ohlc: OHLC data (should have timezone-aware index)
        """
        # Convert to ET for proper day boundaries
        try:
            ohlc_et = self._to_eastern(ohlc)
        except:
            ohlc_et = ohlc
        
        # Previous Day
        pdh, pdl = self._get_previous_day_hl(ohlc_et)
        
        # Previous Week
        pwh, pwl = self._get_previous_week_hl(ohlc_et)
        
        # Previous Month
        pmh, pml = self._get_previous_month_hl(ohlc_et)
        
        # Opening Prices
        opening_prices = self._get_opening_prices(ohlc_et)
        
        return KeyTimeLevels(
            pdh=pdh,
            pdl=pdl,
            pwh=pwh,
            pwl=pwl,
            pmh=pmh,
            pml=pml,
            opening_prices=opening_prices
        )
    
    def get_pd_arrays(self, ohlc: pd.DataFrame) -> List[PDArray]:
        """
        Get all time-based levels as PD Arrays for analysis.
        """
        levels = self.get_all_levels(ohlc)
        current_price = ohlc['close'].iloc[-1]
        
        pd_arrays = []
        
        # Add PDH/PDL
        if levels.pdh > 0:
            pd_arrays.append(PDArray(
                name="PDH",
                level=levels.pdh,
                level_type="HIGH",
                timeframe="DAILY",
                is_premium=levels.pdh > current_price,
                distance_pips=abs(levels.pdh - current_price) / self.pip_size
            ))
        
        if levels.pdl > 0:
            pd_arrays.append(PDArray(
                name="PDL",
                level=levels.pdl,
                level_type="LOW",
                timeframe="DAILY",
                is_premium=levels.pdl > current_price,
                distance_pips=abs(levels.pdl - current_price) / self.pip_size
            ))
        
        # Add PWH/PWL
        if levels.pwh > 0:
            pd_arrays.append(PDArray(
                name="PWH",
                level=levels.pwh,
                level_type="HIGH",
                timeframe="WEEKLY",
                is_premium=levels.pwh > current_price,
                distance_pips=abs(levels.pwh - current_price) / self.pip_size
            ))
        
        if levels.pwl > 0:
            pd_arrays.append(PDArray(
                name="PWL",
                level=levels.pwl,
                level_type="LOW",
                timeframe="WEEKLY",
                is_premium=levels.pwl > current_price,
                distance_pips=abs(levels.pwl - current_price) / self.pip_size
            ))
        
        # Add PMH/PML
        if levels.pmh > 0:
            pd_arrays.append(PDArray(
                name="PMH",
                level=levels.pmh,
                level_type="HIGH",
                timeframe="MONTHLY",
                is_premium=levels.pmh > current_price,
                distance_pips=abs(levels.pmh - current_price) / self.pip_size
            ))
        
        if levels.pml > 0:
            pd_arrays.append(PDArray(
                name="PML",
                level=levels.pml,
                level_type="LOW",
                timeframe="MONTHLY",
                is_premium=levels.pml > current_price,
                distance_pips=abs(levels.pml - current_price) / self.pip_size
            ))
        
        # Add Opening Prices
        op = levels.opening_prices
        
        if op.true_day_open > 0:
            pd_arrays.append(PDArray(
                name="True Day Open",
                level=op.true_day_open,
                level_type="OPEN",
                timeframe="DAILY",
                is_premium=op.true_day_open > current_price,
                distance_pips=abs(op.true_day_open - current_price) / self.pip_size
            ))
        
        if op.midnight_open > 0:
            pd_arrays.append(PDArray(
                name="Midnight Open",
                level=op.midnight_open,
                level_type="OPEN",
                timeframe="DAILY",
                is_premium=op.midnight_open > current_price,
                distance_pips=abs(op.midnight_open - current_price) / self.pip_size
            ))
        
        if op.weekly_open > 0:
            pd_arrays.append(PDArray(
                name="Weekly Open",
                level=op.weekly_open,
                level_type="OPEN",
                timeframe="WEEKLY",
                is_premium=op.weekly_open > current_price,
                distance_pips=abs(op.weekly_open - current_price) / self.pip_size
            ))
        
        # Sort by distance from current price
        pd_arrays.sort(key=lambda x: x.distance_pips)
        
        return pd_arrays
    
    def _to_eastern(self, ohlc: pd.DataFrame) -> pd.DataFrame:
        """Convert OHLC to Eastern Time."""
        df = ohlc.copy()
        if df.index.tzinfo is None:
            df.index = df.index.tz_localize('UTC')
        df.index = df.index.tz_convert(self.et)
        return df
    
    def _get_previous_day_hl(self, ohlc: pd.DataFrame) -> tuple:
        """Get Previous Day High/Low (ICT True Day = 6pm-6pm)."""
        try:
            now = ohlc.index[-1]
            
            # ICT True Day starts at 6pm EST
            if now.hour >= 18:
                # Current true day started today at 6pm
                true_day_start = now.replace(hour=18, minute=0, second=0, microsecond=0)
                prev_day_start = true_day_start - timedelta(days=1)
                prev_day_end = true_day_start
            else:
                # Current true day started yesterday at 6pm
                yesterday = now - timedelta(days=1)
                true_day_start = yesterday.replace(hour=18, minute=0, second=0, microsecond=0)
                prev_day_start = true_day_start - timedelta(days=1)
                prev_day_end = true_day_start
            
            # Get previous day data
            prev_day = ohlc[(ohlc.index >= prev_day_start) & (ohlc.index < prev_day_end)]
            
            if len(prev_day) > 0:
                return prev_day['high'].max(), prev_day['low'].min()
            
        except Exception:
            pass
        
        # Fallback to simple previous day
        if len(ohlc) >= 96:  # ~1 day on 15m
            prev_day = ohlc.iloc[-192:-96]
            return prev_day['high'].max(), prev_day['low'].min()
        
        return 0, 0
    
    def _get_previous_week_hl(self, ohlc: pd.DataFrame) -> tuple:
        """Get Previous Week High/Low."""
        try:
            now = ohlc.index[-1]
            
            # Week starts Sunday 6pm EST
            days_since_sunday = now.weekday() + 1  # Monday = 0
            if days_since_sunday == 7:
                days_since_sunday = 0
            
            this_week_start = (now - timedelta(days=days_since_sunday)).replace(
                hour=18, minute=0, second=0, microsecond=0
            )
            prev_week_start = this_week_start - timedelta(days=7)
            prev_week_end = this_week_start
            
            prev_week = ohlc[(ohlc.index >= prev_week_start) & (ohlc.index < prev_week_end)]
            
            if len(prev_week) > 0:
                return prev_week['high'].max(), prev_week['low'].min()
        
        except Exception:
            pass
        
        # Fallback
        if len(ohlc) >= 672:  # ~1 week on 15m
            prev_week = ohlc.iloc[-1344:-672]
            return prev_week['high'].max(), prev_week['low'].min()
        
        return 0, 0
    
    def _get_previous_month_hl(self, ohlc: pd.DataFrame) -> tuple:
        """Get Previous Month High/Low."""
        try:
            now = ohlc.index[-1]
            
            # First day of current month
            this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # First day of previous month
            prev_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
            prev_month_end = this_month_start
            
            prev_month = ohlc[(ohlc.index >= prev_month_start) & (ohlc.index < prev_month_end)]
            
            if len(prev_month) > 0:
                return prev_month['high'].max(), prev_month['low'].min()
        
        except Exception:
            pass
        
        return 0, 0
    
    def _get_opening_prices(self, ohlc: pd.DataFrame) -> OpeningPrices:
        """Get all key opening prices."""
        
        def get_open_at_hour(hour: int, offset_days: int = 0) -> float:
            try:
                now = ohlc.index[-1]
                target = (now - timedelta(days=offset_days)).replace(
                    hour=hour, minute=0, second=0, microsecond=0
                )
                # Find candle closest to target
                time_diff = abs(ohlc.index - target)
                closest_idx = time_diff.argmin()
                return ohlc['open'].iloc[closest_idx]
            except:
                return 0
        
        try:
            now = ohlc.index[-1]
            
            # True day open (6pm EST prior day)
            true_day_open = get_open_at_hour(18, 1) if now.hour < 18 else get_open_at_hour(18, 0)
            
            # Midnight open
            midnight_open = get_open_at_hour(0, 0) if now.hour > 0 else get_open_at_hour(0, 1)
            
            # Weekly open (Sunday 6pm EST)
            days_since_sunday = now.weekday() + 1
            if days_since_sunday == 7:
                days_since_sunday = 0
            weekly_open = get_open_at_hour(18, days_since_sunday)
            
            # Asia open (7pm EST)
            asia_open = get_open_at_hour(19, 0) if now.hour >= 19 else get_open_at_hour(19, 1)
            
            # London open (2am EST)
            london_open = get_open_at_hour(2, 0) if now.hour >= 2 else get_open_at_hour(2, 1)
            
            # NY open (8:30am EST)
            ny_open = get_open_at_hour(8, 0) if now.hour >= 8 else get_open_at_hour(8, 1)
            
        except:
            true_day_open = midnight_open = weekly_open = asia_open = london_open = ny_open = 0
        
        return OpeningPrices(
            true_day_open=true_day_open,
            midnight_open=midnight_open,
            weekly_open=weekly_open,
            asia_open=asia_open,
            london_open=london_open,
            ny_open=ny_open
        )
    
    def is_above_opens(self, ohlc: pd.DataFrame) -> dict:
        """
        Check if price is above or below key opens.
        
        ICT uses opens for bias:
        - Above weekly open = weekly bullish bias
        - Above midnight open = daily bullish bias
        """
        levels = self.get_all_levels(ohlc)
        current = ohlc['close'].iloc[-1]
        op = levels.opening_prices
        
        return {
            'above_true_day_open': current > op.true_day_open if op.true_day_open > 0 else None,
            'above_midnight_open': current > op.midnight_open if op.midnight_open > 0 else None,
            'above_weekly_open': current > op.weekly_open if op.weekly_open > 0 else None,
            'above_asia_open': current > op.asia_open if op.asia_open > 0 else None,
            'above_london_open': current > op.london_open if op.london_open > 0 else None,
            'above_ny_open': current > op.ny_open if op.ny_open > 0 else None,
        }
