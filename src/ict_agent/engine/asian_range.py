"""
Asian Range Calculator

The Asian Range is the price range formed during the Asian trading session.
It serves as a reference for the London/NY sessions to react to.

Key Concepts:
- Asian Range: Typically 7:00 PM - 12:00 AM New York time (or 0:00 - 5:00 AM London)
- Alternative: Some use 6:00 PM - 12:00 AM NY for broader capture
- The range represents the "liquidity building" phase before London opens
- London often sweeps one side of Asian Range before reversing (Judas Swing)

ICT Principles:
1. Asian Range sets the initial liquidity pools for the day
2. London session often takes one side (sweep) then reverses
3. NY session often continues or reverses London's direction
4. Tight Asian Range (<20 pips) = Explosive move coming
5. Wide Asian Range (>40 pips) = Possible consolidation day

Integration with CBDR:
- CBDR: 2:00 PM - 8:00 PM NY (afternoon liquidity)
- Asian: 7:00 PM - 12:00 AM NY (evening liquidity, overlaps end of CBDR)
- Combined: Full pre-London liquidity picture
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional, List, Tuple
from zoneinfo import ZoneInfo
from enum import Enum
import pandas as pd

from ict_agent.data.oanda_fetcher import OANDAFetcher


# Timezone
NY_TZ = ZoneInfo("America/New_York")
LONDON_TZ = ZoneInfo("Europe/London")


class SessionType(Enum):
    """Trading session types"""
    ASIAN = "asian"
    LONDON = "london"
    NEW_YORK = "new_york"
    CBDR = "cbdr"


@dataclass
class AsianRange:
    """Asian session range data"""
    date: datetime  # Date this range applies to (next trading day)
    high: float
    low: float
    open: float
    close: float
    start_time: datetime
    end_time: datetime
    
    @property
    def range_pips(self) -> float:
        """Range in pips (4-digit pairs)"""
        return abs(self.high - self.low) * 10000
    
    @property
    def range_pips_jpy(self) -> float:
        """Range in pips for JPY pairs"""
        return abs(self.high - self.low) * 100
    
    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2
    
    @property
    def is_tight(self) -> bool:
        """Tight Asian Range < 20 pips = explosive move likely"""
        return self.range_pips < 20
    
    @property
    def is_ideal(self) -> bool:
        """Ideal Asian Range 15-25 pips"""
        return 15 <= self.range_pips <= 25
    
    @property
    def is_wide(self) -> bool:
        """Wide Asian Range > 40 pips = consolidation likely"""
        return self.range_pips > 40
    
    @property
    def bias(self) -> str:
        """Session bias based on close relative to open"""
        if self.close > self.open:
            return "bullish"
        elif self.close < self.open:
            return "bearish"
        return "neutral"
    
    def get_range_pips(self, is_jpy: bool = False) -> float:
        return self.range_pips_jpy if is_jpy else self.range_pips


@dataclass
class AsianRangeProjection:
    """Projection levels from Asian Range"""
    asian_range: AsianRange
    
    # Standard deviation multipliers
    sd_multipliers: List[float] = field(default_factory=lambda: [0.5, 1.0, 1.5, 2.0, 2.5])
    
    # Projection levels above
    projections_high: List[Tuple[float, float]] = field(default_factory=list)  # (multiplier, price)
    
    # Projection levels below
    projections_low: List[Tuple[float, float]] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate projection levels"""
        range_size = self.asian_range.high - self.asian_range.low
        
        self.projections_high = []
        self.projections_low = []
        
        for mult in self.sd_multipliers:
            self.projections_high.append((mult, self.asian_range.high + (range_size * mult)))
            self.projections_low.append((mult, self.asian_range.low - (range_size * mult)))
    
    def get_london_sweep_targets(self) -> dict:
        """
        London typically sweeps Asian high or low before reversing.
        Returns potential sweep levels.
        """
        return {
            'sweep_high': self.asian_range.high,
            'sweep_high_1sd': self.projections_high[1][1] if len(self.projections_high) > 1 else None,
            'sweep_low': self.asian_range.low,
            'sweep_low_1sd': self.projections_low[1][1] if len(self.projections_low) > 1 else None,
        }


class AsianRangeCalculator:
    """
    Calculates the Asian Range for ICT trading methodology.
    
    Default times (NY timezone):
    - Start: 7:00 PM (19:00)
    - End: 12:00 AM (00:00) next day
    
    This captures the Asian liquidity building before London opens.
    """
    
    # Default Asian session times (NY timezone)
    DEFAULT_START_HOUR = 19  # 7:00 PM NY
    DEFAULT_END_HOUR = 0     # 12:00 AM NY (next day)
    
    def __init__(
        self,
        start_hour: int = None,
        end_hour: int = None,
        use_london_tz: bool = False
    ):
        """
        Initialize Asian Range Calculator.
        
        Args:
            start_hour: Session start hour (default 19 = 7 PM NY)
            end_hour: Session end hour (default 0 = 12 AM NY)
            use_london_tz: If True, interpret hours as London time
        """
        self.start_hour = start_hour or self.DEFAULT_START_HOUR
        self.end_hour = end_hour or self.DEFAULT_END_HOUR
        self.timezone = LONDON_TZ if use_london_tz else NY_TZ
        self.fetcher = None
    
    def _ensure_fetcher(self):
        """Lazily initialize OANDA fetcher"""
        if self.fetcher is None:
            self.fetcher = OANDAFetcher()
    
    def _get_session_candles(
        self, 
        df: pd.DataFrame, 
        target_date: datetime = None
    ) -> pd.DataFrame:
        """
        Extract candles that fall within the Asian session.
        
        Args:
            df: OHLCV DataFrame with datetime index
            target_date: Specific date to get range for (None = most recent)
        """
        if df.empty:
            return pd.DataFrame()
        
        # Ensure datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            return pd.DataFrame()
        
        # Convert index to NY timezone if not already
        df = df.copy()
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(self.timezone)
        else:
            df.index = df.index.tz_convert(self.timezone)
        
        now = datetime.now(self.timezone)
        
        if target_date is None:
            # Find the most recent complete Asian session
            # Asian session is 7PM to midnight
            # If current hour is 0-6 (after midnight, before market opens), use yesterday's session
            # If current hour is 7-18, use yesterday's session (already complete)
            # If current hour is 19-23, session is in progress, use previous day
            
            if now.hour < 19:
                # Use yesterday's 7PM to today's midnight
                session_date = now.date() - timedelta(days=1)
            else:
                # Session in progress - use day before yesterday to get complete session
                session_date = now.date() - timedelta(days=1)
        else:
            session_date = target_date if isinstance(target_date, type(now.date())) else target_date.date()
        
        # Build session time range: 7PM on session_date to midnight (next day 00:00)
        session_start = datetime.combine(session_date, time(self.start_hour, 0), tzinfo=self.timezone)
        session_end = datetime.combine(session_date + timedelta(days=1), time(0, 0), tzinfo=self.timezone)
        
        # Filter candles
        mask = (df.index >= session_start) & (df.index < session_end)
        return df[mask]
    
    def calculate(
        self, 
        df: pd.DataFrame, 
        target_date: datetime = None
    ) -> Optional[AsianRange]:
        """
        Calculate Asian Range from OHLCV data.
        
        Args:
            df: OHLCV DataFrame
            target_date: Specific date (None = most recent)
            
        Returns:
            AsianRange object or None if insufficient data
        """
        session_candles = self._get_session_candles(df, target_date)
        
        if session_candles.empty or len(session_candles) < 2:
            return None
        
        return AsianRange(
            date=session_candles.index[0].date() + timedelta(days=1),  # Applies to next trading day
            high=session_candles['high'].max(),
            low=session_candles['low'].min(),
            open=session_candles['open'].iloc[0],
            close=session_candles['close'].iloc[-1],
            start_time=session_candles.index[0].to_pydatetime(),
            end_time=session_candles.index[-1].to_pydatetime(),
        )
    
    def calculate_projections(
        self, 
        asian_range: AsianRange,
        sd_multipliers: List[float] = None
    ) -> AsianRangeProjection:
        """
        Calculate standard deviation projections from Asian Range.
        """
        return AsianRangeProjection(
            asian_range=asian_range,
            sd_multipliers=sd_multipliers or [0.5, 1.0, 1.5, 2.0, 2.5]
        )
    
    def fetch_and_calculate(
        self, 
        symbol: str,
        target_date: datetime = None
    ) -> Optional[AsianRange]:
        """
        Fetch data from OANDA and calculate Asian Range.
        
        Args:
            symbol: Trading pair (e.g., "EURUSD", "EUR_USD")
            target_date: Specific date (None = most recent)
        """
        self._ensure_fetcher()
        
        # Fetch enough 15m candles to cover Asian session (need ~200 for 2 days)
        df = self.fetcher.fetch_latest(symbol, timeframe='15m', count=200)
        
        if df.empty:
            return None
        
        return self.calculate(df, target_date)
    
    def get_full_analysis(self, symbol: str) -> dict:
        """
        Get complete Asian Range analysis including projections and signals.
        """
        asian_range = self.fetch_and_calculate(symbol)
        
        if asian_range is None:
            return {'error': 'Could not calculate Asian Range', 'symbol': symbol}
        
        projections = self.calculate_projections(asian_range)
        sweep_targets = projections.get_london_sweep_targets()
        
        # Get current price for context
        self._ensure_fetcher()
        price_data = self.fetcher.get_current_price(symbol)
        current_price = price_data.get('mid') if price_data else None
        
        # Determine price location
        price_location = "inside"
        if current_price:
            if current_price > asian_range.high:
                price_location = "above"
            elif current_price < asian_range.low:
                price_location = "below"
        
        return {
            'symbol': symbol,
            'asian_range': asian_range,
            'projections': projections,
            'sweep_targets': sweep_targets,
            'current_price': current_price,
            'price_location': price_location,
            'range_quality': self._assess_range_quality(asian_range),
        }
    
    def _assess_range_quality(self, ar: AsianRange) -> dict:
        """Assess the quality and trading implications of the Asian Range"""
        pips = ar.range_pips
        
        if pips < 15:
            quality = "VERY_TIGHT"
            implication = "Explosive breakout likely - wait for direction confirmation"
        elif pips < 25:
            quality = "IDEAL"
            implication = "Good for standard London sweep play"
        elif pips < 40:
            quality = "ACCEPTABLE"
            implication = "Moderate move expected, standard deviation targets less reliable"
        else:
            quality = "WIDE"
            implication = "Consolidation likely - reduced directional conviction"
        
        return {
            'quality': quality,
            'range_pips': pips,
            'implication': implication,
            'is_tight': ar.is_tight,
            'is_ideal': ar.is_ideal,
            'is_wide': ar.is_wide,
            'session_bias': ar.bias,
        }
    
    def format_analysis(self, analysis: dict, is_jpy: bool = False) -> str:
        """Format analysis for display"""
        if 'error' in analysis:
            return f"❌ {analysis['error']}"
        
        ar = analysis['asian_range']
        quality = analysis['range_quality']
        
        pip_mult = 100 if is_jpy else 10000
        pips = quality['range_pips']
        
        # Quality indicator
        if quality['quality'] == 'VERY_TIGHT':
            indicator = "💥"
        elif quality['quality'] == 'IDEAL':
            indicator = "✅"
        elif quality['quality'] == 'ACCEPTABLE':
            indicator = "✓"
        else:
            indicator = "⚠️"
        
        lines = [
            f"═══ ASIAN RANGE ({analysis['symbol']}) ═══",
            f"Range: {pips:.1f} pips {indicator}",
            f"High: {ar.high:.5f}",
            f"Low: {ar.low:.5f}",
            f"Session Bias: {quality['session_bias'].upper()}",
            f"Quality: {quality['quality']}",
            f"",
            f"📍 Price Location: {analysis['price_location'].upper()}",
        ]
        
        if analysis['current_price']:
            cp = analysis['current_price']
            to_high = (ar.high - cp) * pip_mult
            to_low = (cp - ar.low) * pip_mult
            lines.append(f"Current: {cp:.5f}")
            lines.append(f"To High: {to_high:+.0f} pips | To Low: {to_low:+.0f} pips")
        
        # London sweep targets
        st = analysis['sweep_targets']
        lines.extend([
            "",
            "🎯 London Sweep Targets:",
            f"  Above: {st['sweep_high']:.5f}",
            f"  Below: {st['sweep_low']:.5f}",
        ])
        
        lines.extend([
            "",
            f"💡 {quality['implication']}",
        ])
        
        return "\n".join(lines)


# Convenience functions
def get_asian_range(symbol: str) -> Optional[AsianRange]:
    """Quick function to get Asian Range for a symbol"""
    calc = AsianRangeCalculator()
    return calc.fetch_and_calculate(symbol)


def get_asian_analysis(symbol: str) -> str:
    """Get formatted Asian Range analysis"""
    calc = AsianRangeCalculator()
    analysis = calc.get_full_analysis(symbol)
    return calc.format_analysis(analysis)


# Test
if __name__ == "__main__":
    print("Testing Asian Range Calculator...")
    
    for symbol in ['EUR_USD', 'GBP_USD']:
        print(f"\n{symbol}")
        print("-" * 40)
        print(get_asian_analysis(symbol))
