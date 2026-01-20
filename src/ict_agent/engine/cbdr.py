"""CBDR (Central Bank Dealers Range) Calculator

The CBDR is the price range formed between 2:00 PM - 8:00 PM New York time.
This range is used to project standard deviation levels for the next trading day.

Key Rules:
- Ideal CBDR: < 40 pips (preferably 20-30 pips)
- Sell Days: High of day forms 1-3 SD above CBDR high
- Buy Days: Low of day forms 2+ SD below CBDR low
- Tight CBDR = More reliable projections
- Wide CBDR = Less reliable, expect consolidation
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional, List, Tuple
from zoneinfo import ZoneInfo
import pandas as pd

from ict_agent.data.oanda_fetcher import OANDAFetcher


# NY timezone
NY_TZ = ZoneInfo("America/New_York")


@dataclass
class CBDRRange:
    """CBDR range data for a specific date"""
    date: datetime
    high: float
    low: float
    open: float
    close: float
    
    @property
    def range_pips(self) -> float:
        """Range in pips (assumes 4-digit pair)"""
        return abs(self.high - self.low) * 10000
    
    @property
    def range_pips_jpy(self) -> float:
        """Range in pips for JPY pairs"""
        return abs(self.high - self.low) * 100
    
    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2
    
    @property
    def is_ideal(self) -> bool:
        """CBDR < 40 pips is ideal"""
        return self.range_pips < 40
    
    @property
    def is_tight(self) -> bool:
        """CBDR 20-30 pips is preferred"""
        return 20 <= self.range_pips <= 30
    
    def get_range_pips(self, is_jpy: bool = False) -> float:
        return self.range_pips_jpy if is_jpy else self.range_pips


@dataclass  
class StandardDeviationLevels:
    """Standard deviation projection levels from CBDR"""
    cbdr: CBDRRange
    
    # Above CBDR (buy-side)
    sd_1_high: float = 0.0
    sd_2_high: float = 0.0
    sd_3_high: float = 0.0
    sd_4_high: float = 0.0
    
    # Below CBDR (sell-side)
    sd_1_low: float = 0.0
    sd_2_low: float = 0.0
    sd_3_low: float = 0.0
    sd_4_low: float = 0.0
    
    def __post_init__(self):
        """Calculate SD levels"""
        range_size = self.cbdr.high - self.cbdr.low
        
        # Above CBDR
        self.sd_1_high = self.cbdr.high + (range_size * 1)
        self.sd_2_high = self.cbdr.high + (range_size * 2)
        self.sd_3_high = self.cbdr.high + (range_size * 3)
        self.sd_4_high = self.cbdr.high + (range_size * 4)
        
        # Below CBDR
        self.sd_1_low = self.cbdr.low - (range_size * 1)
        self.sd_2_low = self.cbdr.low - (range_size * 2)
        self.sd_3_low = self.cbdr.low - (range_size * 3)
        self.sd_4_low = self.cbdr.low - (range_size * 4)
    
    def get_sell_day_targets(self) -> List[Tuple[str, float]]:
        """
        On sell days, high forms 1-3 SD above CBDR high.
        Returns potential high of day levels.
        """
        return [
            ("SD +1 (High)", self.sd_1_high),
            ("SD +2 (High)", self.sd_2_high),
            ("SD +3 (High)", self.sd_3_high),
        ]
    
    def get_buy_day_targets(self) -> List[Tuple[str, float]]:
        """
        On buy days, low forms 2+ SD below CBDR low.
        Returns potential low of day levels.
        """
        return [
            ("SD -2 (Low)", self.sd_2_low),
            ("SD -3 (Low)", self.sd_3_low),
            ("SD -4 (Low)", self.sd_4_low),
        ]
    
    def get_all_levels(self) -> List[Tuple[str, float]]:
        """Get all SD levels"""
        return [
            ("SD +4", self.sd_4_high),
            ("SD +3", self.sd_3_high),
            ("SD +2", self.sd_2_high),
            ("SD +1", self.sd_1_high),
            ("CBDR High", self.cbdr.high),
            ("CBDR Mid", self.cbdr.midpoint),
            ("CBDR Low", self.cbdr.low),
            ("SD -1", self.sd_1_low),
            ("SD -2", self.sd_2_low),
            ("SD -3", self.sd_3_low),
            ("SD -4", self.sd_4_low),
        ]


@dataclass
class AsianRange:
    """Asian session range (for additional context)"""
    date: datetime
    high: float
    low: float
    
    @property
    def range_pips(self) -> float:
        return abs(self.high - self.low) * 10000
    
    @property
    def is_ideal(self) -> bool:
        """Asian range < 20 pips is ideal before Frankfurt"""
        return self.range_pips < 20


@dataclass
class DailyProjection:
    """Complete daily projection with CBDR and Asian range"""
    symbol: str
    date: datetime
    cbdr: CBDRRange
    sd_levels: StandardDeviationLevels
    asian_range: Optional[AsianRange] = None
    
    # Current session data
    current_high: float = 0.0
    current_low: float = 0.0
    current_price: float = 0.0
    
    @property
    def bias(self) -> str:
        """Determine bias based on where price is relative to CBDR"""
        if self.current_price > self.cbdr.high:
            return "bullish"
        elif self.current_price < self.cbdr.low:
            return "bearish"
        else:
            return "neutral"
    
    @property
    def sd_reached_high(self) -> int:
        """How many SDs above CBDR has price reached"""
        if self.current_high >= self.sd_levels.sd_4_high:
            return 4
        elif self.current_high >= self.sd_levels.sd_3_high:
            return 3
        elif self.current_high >= self.sd_levels.sd_2_high:
            return 2
        elif self.current_high >= self.sd_levels.sd_1_high:
            return 1
        return 0
    
    @property
    def sd_reached_low(self) -> int:
        """How many SDs below CBDR has price reached"""
        if self.current_low <= self.sd_levels.sd_4_low:
            return 4
        elif self.current_low <= self.sd_levels.sd_3_low:
            return 3
        elif self.current_low <= self.sd_levels.sd_2_low:
            return 2
        elif self.current_low <= self.sd_levels.sd_1_low:
            return 1
        return 0


class CBDRCalculator:
    """
    Central Bank Dealers Range Calculator
    
    Calculates the CBDR (2 PM - 8 PM NY) and projects standard deviation levels
    for daily high/low forecasting.
    """
    
    # CBDR window: 2 PM - 8 PM NY time
    CBDR_START = time(14, 0)  # 2:00 PM
    CBDR_END = time(20, 0)    # 8:00 PM
    
    # Asian range: 8 PM - Midnight NY (or 0 GMT opening)
    ASIAN_START = time(20, 0)
    ASIAN_END = time(0, 0)
    
    def __init__(self, fetcher: Optional[OANDAFetcher] = None):
        self.fetcher = fetcher or OANDAFetcher()
    
    def get_cbdr(
        self,
        symbol: str,
        date: Optional[datetime] = None,
    ) -> Optional[CBDRRange]:
        """
        Get CBDR for a specific date.
        
        Args:
            symbol: Trading pair
            date: Date to calculate CBDR for (default: yesterday)
        
        Returns:
            CBDRRange object
        """
        if date is None:
            # Use yesterday's CBDR for today's projections
            date = datetime.now(NY_TZ) - timedelta(days=1)
        
        # Ensure date is in NY timezone
        if date.tzinfo is None:
            date = date.replace(tzinfo=NY_TZ)
        
        # CBDR window
        cbdr_start = datetime.combine(date.date(), self.CBDR_START, tzinfo=NY_TZ)
        cbdr_end = datetime.combine(date.date(), self.CBDR_END, tzinfo=NY_TZ)
        
        # Fetch 5-minute data for precision
        try:
            from ict_agent.data.fetcher import DataConfig
            
            config = DataConfig(
                symbol=symbol,
                timeframe="5m",
                start_date=cbdr_start,
                end_date=cbdr_end,
            )
            
            df = self.fetcher.fetch(config)
            
            if df.empty:
                return None
            
            return CBDRRange(
                date=date,
                high=df['high'].max(),
                low=df['low'].min(),
                open=df['open'].iloc[0],
                close=df['close'].iloc[-1],
            )
        except Exception as e:
            print(f"Error fetching CBDR: {e}")
            return None
    
    def get_cbdr_from_data(
        self,
        df: pd.DataFrame,
        date: Optional[datetime] = None,
    ) -> Optional[CBDRRange]:
        """
        Calculate CBDR from existing DataFrame.
        
        Args:
            df: OHLCV DataFrame with timezone-aware DatetimeIndex
            date: Date to calculate CBDR for
        """
        if df.empty:
            return None
        
        if date is None:
            date = datetime.now(NY_TZ) - timedelta(days=1)
        
        # Convert index to NY time if needed
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(NY_TZ)
        else:
            df.index = df.index.tz_convert(NY_TZ)
        
        # Filter to CBDR window
        cbdr_start = datetime.combine(date.date(), self.CBDR_START, tzinfo=NY_TZ)
        cbdr_end = datetime.combine(date.date(), self.CBDR_END, tzinfo=NY_TZ)
        
        cbdr_data = df[(df.index >= cbdr_start) & (df.index <= cbdr_end)]
        
        if cbdr_data.empty:
            return None
        
        return CBDRRange(
            date=date,
            high=cbdr_data['high'].max(),
            low=cbdr_data['low'].min(),
            open=cbdr_data['open'].iloc[0],
            close=cbdr_data['close'].iloc[-1],
        )
    
    def get_asian_range(
        self,
        symbol: str,
        date: Optional[datetime] = None,
    ) -> Optional[AsianRange]:
        """Get Asian session range (8 PM - Midnight NY)"""
        if date is None:
            date = datetime.now(NY_TZ) - timedelta(days=1)
        
        if date.tzinfo is None:
            date = date.replace(tzinfo=NY_TZ)
        
        # Asian range starts at 8 PM previous day
        asian_start = datetime.combine(date.date(), self.ASIAN_START, tzinfo=NY_TZ)
        asian_end = datetime.combine(date.date() + timedelta(days=1), time(0, 0), tzinfo=NY_TZ)
        
        try:
            from ict_agent.data.fetcher import DataConfig
            
            config = DataConfig(
                symbol=symbol,
                timeframe="5m",
                start_date=asian_start,
                end_date=asian_end,
            )
            
            df = self.fetcher.fetch(config)
            
            if df.empty:
                return None
            
            return AsianRange(
                date=date,
                high=df['high'].max(),
                low=df['low'].min(),
            )
        except:
            return None
    
    def calculate_projections(
        self,
        symbol: str,
        date: Optional[datetime] = None,
    ) -> Optional[DailyProjection]:
        """
        Calculate complete daily projection with CBDR and SD levels.
        
        Args:
            symbol: Trading pair
            date: Date for CBDR (default: yesterday for today's projections)
        
        Returns:
            DailyProjection with all levels
        """
        cbdr = self.get_cbdr(symbol, date)
        
        if cbdr is None:
            return None
        
        sd_levels = StandardDeviationLevels(cbdr=cbdr)
        asian_range = self.get_asian_range(symbol, date)
        
        # Get current session data
        try:
            current_df = self.fetcher.fetch_latest(symbol, "5m", 100)
            if not current_df.empty:
                # Today's high/low
                now = datetime.now(NY_TZ)
                today_start = datetime.combine(now.date(), time(0, 0), tzinfo=NY_TZ)
                
                # Convert to NY time
                if current_df.index.tz is None:
                    current_df.index = current_df.index.tz_localize('UTC').tz_convert(NY_TZ)
                
                today_data = current_df[current_df.index >= today_start]
                
                current_high = today_data['high'].max() if not today_data.empty else current_df['high'].iloc[-1]
                current_low = today_data['low'].min() if not today_data.empty else current_df['low'].iloc[-1]
                current_price = current_df['close'].iloc[-1]
            else:
                current_high = current_low = current_price = 0
        except:
            current_high = current_low = current_price = 0
        
        return DailyProjection(
            symbol=symbol,
            date=datetime.now(NY_TZ),
            cbdr=cbdr,
            sd_levels=sd_levels,
            asian_range=asian_range,
            current_high=current_high,
            current_low=current_low,
            current_price=current_price,
        )
    
    def format_projection(self, projection: DailyProjection) -> str:
        """Format projection for display"""
        is_jpy = "JPY" in projection.symbol
        pip_mult = 100 if is_jpy else 10000
        
        lines = [
            f"╔{'═'*56}╗",
            f"║  CBDR PROJECTION: {projection.symbol}".ljust(57) + "║",
            f"║  {projection.date.strftime('%Y-%m-%d %H:%M %Z')}".ljust(57) + "║",
            f"╠{'═'*56}╣",
        ]
        
        # CBDR Info
        cbdr = projection.cbdr
        range_pips = cbdr.get_range_pips(is_jpy)
        quality = "✅ IDEAL" if cbdr.is_tight else ("✓ Good" if cbdr.is_ideal else "⚠️ Wide")
        
        lines.extend([
            f"║  CBDR (2-8 PM NY):".ljust(57) + "║",
            f"║    High:  {cbdr.high:.5f}".ljust(57) + "║",
            f"║    Low:   {cbdr.low:.5f}".ljust(57) + "║",
            f"║    Range: {range_pips:.1f} pips {quality}".ljust(57) + "║",
        ])
        
        # Asian Range
        if projection.asian_range:
            ar = projection.asian_range
            ar_pips = ar.range_pips if not is_jpy else ar.range_pips / 100
            ar_quality = "✅" if ar.is_ideal else ""
            lines.append(f"║    Asian: {ar_pips:.1f} pips {ar_quality}".ljust(57) + "║")
        
        lines.append(f"╠{'═'*56}╣")
        
        # Current Status
        lines.extend([
            f"║  CURRENT STATUS:".ljust(57) + "║",
            f"║    Price:     {projection.current_price:.5f}".ljust(57) + "║",
            f"║    Today High: {projection.current_high:.5f} (SD +{projection.sd_reached_high})".ljust(57) + "║",
            f"║    Today Low:  {projection.current_low:.5f} (SD -{projection.sd_reached_low})".ljust(57) + "║",
            f"║    Bias: {projection.bias.upper()}".ljust(57) + "║",
        ])
        
        lines.append(f"╠{'═'*56}╣")
        
        # SD Levels
        sd = projection.sd_levels
        lines.append(f"║  STANDARD DEVIATION LEVELS:".ljust(57) + "║")
        
        # Format levels with distance from current price
        levels = sd.get_all_levels()
        for name, price in levels:
            distance = (price - projection.current_price) * pip_mult
            direction = "↑" if distance > 0 else "↓"
            
            # Mark if price has reached this level
            reached = ""
            if price <= projection.current_high and price >= projection.cbdr.high:
                reached = " ✓"
            elif price >= projection.current_low and price <= projection.cbdr.low:
                reached = " ✓"
            
            line = f"║    {name:12} {price:.5f}  {direction} {abs(distance):5.0f} pips{reached}"
            lines.append(line.ljust(57) + "║")
        
        lines.append(f"╠{'═'*56}╣")
        
        # Trading Notes
        lines.append(f"║  TRADING NOTES:".ljust(57) + "║")
        
        if projection.bias == "bearish":
            lines.append(f"║    → SELL DAY: Look for high at SD +1 to +3".ljust(57) + "║")
            targets = sd.get_sell_day_targets()
            for name, price in targets[:2]:
                dist = (price - projection.current_price) * pip_mult
                lines.append(f"║      {name}: {price:.5f} ({dist:+.0f} pips)".ljust(57) + "║")
        elif projection.bias == "bullish":
            lines.append(f"║    → BUY DAY: Look for low at SD -2 or lower".ljust(57) + "║")
            targets = sd.get_buy_day_targets()
            for name, price in targets[:2]:
                dist = (price - projection.current_price) * pip_mult
                lines.append(f"║      {name}: {price:.5f} ({dist:+.0f} pips)".ljust(57) + "║")
        else:
            lines.append(f"║    → Price inside CBDR, wait for breakout".ljust(57) + "║")
        
        lines.append(f"╚{'═'*56}╝")
        
        return "\n".join(lines)


def get_cbdr_projection(symbol: str = "EURUSD") -> Optional[DailyProjection]:
    """Quick function to get CBDR projection"""
    calc = CBDRCalculator()
    return calc.calculate_projections(symbol)


# CLI usage
if __name__ == "__main__":
    import sys
    
    symbol = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    
    print(f"Calculating CBDR projection for {symbol}...")
    
    calc = CBDRCalculator()
    projection = calc.calculate_projections(symbol)
    
    if projection:
        print(calc.format_projection(projection))
    else:
        print("Could not calculate CBDR projection")
