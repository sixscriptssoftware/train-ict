"""
VEX CBDR Calculator - Central Bank Dealer Range Analysis.

Calculates:
- CBDR (2-5 AM EST range)
- Standard deviation projections
- Asian range analysis
- Liquidity levels
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo
from dataclasses import dataclass

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

MEMORY_DIR = PROJECT_ROOT / "data" / "memory"

NY_TZ = ZoneInfo("America/New_York")


@dataclass
class CBDRData:
    """CBDR calculation results."""
    pair: str
    date: str
    
    # CBDR (2-5 AM EST)
    cbdr_high: float
    cbdr_low: float
    cbdr_range: float
    cbdr_range_pips: float
    cbdr_valid: bool  # Under 30 pips
    
    # Standard Deviation Projections
    sd_value: float
    bullish_targets: Dict[str, float]
    bearish_targets: Dict[str, float]
    
    # Asian Range
    asian_high: float
    asian_low: float
    asian_range_pips: float
    
    # Liquidity Levels
    buy_side_liquidity: List[float]
    sell_side_liquidity: List[float]
    
    # Current context
    current_price: float
    equilibrium: float


class CBDRCalculator:
    """
    Central Bank Dealer Range Calculator.
    
    CBDR = The range formed during 2:00 AM - 5:00 AM EST
    This range is used to project targets using standard deviations.
    
    Key Rules:
    - CBDR under 30 pips = valid setup
    - Standard deviation multipliers: 0.5, 1.0, 1.5, 2.0, 2.5, 3.0
    - Asian range liquidity is the first target
    """
    
    # Standard deviation multipliers
    SD_MULTIPLIERS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    def __init__(self):
        self.fetcher = None
        self._init_fetcher()
    
    def _init_fetcher(self):
        """Initialize OANDA fetcher."""
        try:
            from ict_agent.data.oanda_fetcher import OANDAFetcher
            self.fetcher = OANDAFetcher()
        except Exception as e:
            print(f"Warning: Could not initialize fetcher: {e}")
    
    def calculate(self, pair: str, date: Optional[str] = None) -> Optional[CBDRData]:
        """
        Calculate CBDR for a pair.
        
        Args:
            pair: Trading pair (e.g., "EURUSD" or "EUR_USD")
            date: Date to calculate for (default: today)
        
        Returns:
            CBDRData with all calculations
        """
        # Normalize pair
        if "_" not in pair:
            pair = f"{pair[:3]}_{pair[3:]}"
        pair = pair.upper()
        
        pip_size = 0.01 if 'JPY' in pair else 0.0001
        
        if not self.fetcher:
            print("Error: No data fetcher available")
            return None
        
        try:
            # Fetch 15-minute data for granular range calculation
            df = self.fetcher.fetch_latest(pair, "15m", 200)
            if df is None or len(df) == 0:
                print(f"Error: No data for {pair}")
                return None
            
            df = df.reset_index()
            df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            
            # Convert to NY timezone
            df['time'] = df['time'].dt.tz_convert(NY_TZ) if df['time'].dt.tz else df['time'].dt.tz_localize('UTC').dt.tz_convert(NY_TZ)
            
            now = datetime.now(NY_TZ)
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=NY_TZ) if date else now
            
            # CBDR: 2:00 AM - 5:00 AM EST
            cbdr_start = target_date.replace(hour=2, minute=0, second=0, microsecond=0)
            cbdr_end = target_date.replace(hour=5, minute=0, second=0, microsecond=0)
            
            # If it's before 5 AM, use yesterday's CBDR
            if now.hour < 5:
                cbdr_start -= timedelta(days=1)
                cbdr_end -= timedelta(days=1)
            
            # Filter for CBDR period
            cbdr_df = df[(df['time'] >= cbdr_start) & (df['time'] < cbdr_end)]
            
            if len(cbdr_df) == 0:
                # Fallback: estimate from available data
                print("  ⚠️ No CBDR data available, using recent range estimate")
                cbdr_high = df['high'].iloc[-20:].max()
                cbdr_low = df['low'].iloc[-20:].min()
            else:
                cbdr_high = cbdr_df['high'].max()
                cbdr_low = cbdr_df['low'].min()
            
            cbdr_range = cbdr_high - cbdr_low
            cbdr_range_pips = cbdr_range / pip_size
            cbdr_valid = cbdr_range_pips < 30
            
            # Standard Deviation
            sd_value = cbdr_range * 0.5  # 0.5 SD = half the range
            
            # Calculate projections
            bullish_targets = {}
            bearish_targets = {}
            
            for mult in self.SD_MULTIPLIERS:
                offset = cbdr_range * mult
                bullish_targets[f"+{mult}SD"] = round(cbdr_high + offset, 5)
                bearish_targets[f"-{mult}SD"] = round(cbdr_low - offset, 5)
            
            # Asian Range: 7:00 PM - 2:00 AM EST (previous evening)
            asian_start = (target_date - timedelta(days=1)).replace(hour=19, minute=0)
            asian_end = target_date.replace(hour=2, minute=0)
            
            asian_df = df[(df['time'] >= asian_start) & (df['time'] < asian_end)]
            
            if len(asian_df) > 0:
                asian_high = asian_df['high'].max()
                asian_low = asian_df['low'].min()
            else:
                # Estimate from recent data
                asian_high = cbdr_high + (cbdr_range * 0.5)
                asian_low = cbdr_low - (cbdr_range * 0.5)
            
            asian_range_pips = (asian_high - asian_low) / pip_size
            
            # Current price and equilibrium
            current_price = df['close'].iloc[-1]
            equilibrium = (cbdr_high + cbdr_low) / 2
            
            # Liquidity levels
            # Buy-side: Above recent highs
            buy_side = [asian_high, cbdr_high]
            # Sell-side: Below recent lows
            sell_side = [asian_low, cbdr_low]
            
            return CBDRData(
                pair=pair,
                date=target_date.strftime("%Y-%m-%d"),
                cbdr_high=round(cbdr_high, 5),
                cbdr_low=round(cbdr_low, 5),
                cbdr_range=round(cbdr_range, 5),
                cbdr_range_pips=round(cbdr_range_pips, 1),
                cbdr_valid=cbdr_valid,
                sd_value=round(sd_value, 5),
                bullish_targets=bullish_targets,
                bearish_targets=bearish_targets,
                asian_high=round(asian_high, 5),
                asian_low=round(asian_low, 5),
                asian_range_pips=round(asian_range_pips, 1),
                buy_side_liquidity=buy_side,
                sell_side_liquidity=sell_side,
                current_price=round(current_price, 5),
                equilibrium=round(equilibrium, 5)
            )
            
        except Exception as e:
            print(f"Error calculating CBDR: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def format_report(self, data: CBDRData) -> str:
        """Format CBDR data as printable report."""
        lines = []
        
        lines.append("")
        lines.append("═" * 60)
        lines.append(f"  CBDR ANALYSIS: {data.pair}")
        lines.append(f"  Date: {data.date}")
        lines.append("═" * 60)
        
        # CBDR Section
        valid_icon = "✅" if data.cbdr_valid else "⚠️"
        lines.append(f"\n  📊 CBDR (2:00 AM - 5:00 AM EST):")
        lines.append(f"     High:  {data.cbdr_high}")
        lines.append(f"     Low:   {data.cbdr_low}")
        lines.append(f"     Range: {data.cbdr_range_pips:.1f} pips {valid_icon}")
        
        if not data.cbdr_valid:
            lines.append(f"     ⚠️ Range > 30 pips - Less reliable projections")
        else:
            lines.append(f"     ✅ Valid setup (under 30 pips)")
        
        # Current Position
        lines.append(f"\n  📍 CURRENT POSITION:")
        lines.append(f"     Price:       {data.current_price}")
        lines.append(f"     Equilibrium: {data.equilibrium}")
        
        if data.current_price > data.equilibrium:
            lines.append(f"     Zone:        PREMIUM (above EQ)")
        else:
            lines.append(f"     Zone:        DISCOUNT (below EQ)")
        
        # Bullish Targets
        lines.append(f"\n  🟢 BULLISH TARGETS (if bias is LONG):")
        for level, price in data.bullish_targets.items():
            marker = "← First target" if level == "+1.0SD" else ""
            marker = "← Common TP" if level == "+2.5SD" else marker
            lines.append(f"     {level}: {price} {marker}")
        
        # Bearish Targets
        lines.append(f"\n  🔴 BEARISH TARGETS (if bias is SHORT):")
        for level, price in data.bearish_targets.items():
            marker = "← First target" if level == "-1.0SD" else ""
            marker = "← Common TP" if level == "-2.5SD" else marker
            lines.append(f"     {level}: {price} {marker}")
        
        # Asian Range
        lines.append(f"\n  🌏 ASIAN RANGE (7:00 PM - 2:00 AM EST):")
        lines.append(f"     High:  {data.asian_high}")
        lines.append(f"     Low:   {data.asian_low}")
        lines.append(f"     Range: {data.asian_range_pips:.1f} pips")
        
        # Liquidity Levels
        lines.append(f"\n  ⚡ LIQUIDITY LEVELS:")
        lines.append(f"     🔼 Buy-side (targets for shorts / sweeps for longs):")
        for level in data.buy_side_liquidity:
            lines.append(f"        {level}")
        lines.append(f"     🔽 Sell-side (targets for longs / sweeps for shorts):")
        for level in data.sell_side_liquidity:
            lines.append(f"        {level}")
        
        # Trading Implications
        lines.append(f"\n  💡 TRADING IMPLICATIONS:")
        
        if data.current_price > data.equilibrium:
            lines.append(f"     • Price in PREMIUM - favor shorts for retracement")
            lines.append(f"     • Look for long entries below {data.equilibrium}")
            lines.append(f"     • Asian high sweep could signal reversal")
        else:
            lines.append(f"     • Price in DISCOUNT - favor longs for expansion")
            lines.append(f"     • Look for short entries above {data.equilibrium}")
            lines.append(f"     • Asian low sweep could signal reversal")
        
        if data.cbdr_valid:
            lines.append(f"     • Tight CBDR = potential for large expansion")
            lines.append(f"     • Target: 2.5 SD ({data.bullish_targets.get('+2.5SD', 'N/A')} bullish / {data.bearish_targets.get('-2.5SD', 'N/A')} bearish)")
        
        lines.append("")
        lines.append("═" * 60)
        
        return "\n".join(lines)
    
    def quick_levels(self, pair: str) -> Optional[Dict]:
        """Get quick reference levels for a pair."""
        data = self.calculate(pair)
        if not data:
            return None
        
        return {
            "pair": data.pair,
            "cbdr_high": data.cbdr_high,
            "cbdr_low": data.cbdr_low,
            "equilibrium": data.equilibrium,
            "asian_high": data.asian_high,
            "asian_low": data.asian_low,
            "current": data.current_price,
            "bullish_2.5sd": data.bullish_targets.get("+2.5SD"),
            "bearish_2.5sd": data.bearish_targets.get("-2.5SD"),
            "valid": data.cbdr_valid
        }


def main():
    """CLI entry point."""
    import sys
    
    calc = CBDRCalculator()
    
    pair = sys.argv[1].upper() if len(sys.argv) > 1 else "EUR_USD"
    
    print(f"\n  Calculating CBDR for {pair}...")
    
    data = calc.calculate(pair)
    if data:
        print(calc.format_report(data))
    else:
        print(f"\n  ❌ Could not calculate CBDR for {pair}")


if __name__ == "__main__":
    main()
