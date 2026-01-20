#!/usr/bin/env python3
"""
VEX CHART MARKUP - GBP/JPY Multi-Timeframe Analysis
Shows: Candlesticks, Structure, FVGs, Liquidity Levels, Entry Points
"""
import os
import sys
sys.path.insert(0, '/Users/villain/Documents/transfer/ICT_WORK/ict_trainer/src')

# Set API directly
os.environ['OANDA_API_KEY'] = '4d4e1570f95fc098a40fe90c7ca3c757-c68e27913fd46c5e690381d56fed375c'
os.environ['OANDA_ACCOUNT_ID'] = '101-001-21727967-002'

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
import subprocess
from ict_agent.data.oanda_fetcher import OANDAFetcher

plt.style.use('dark_background')
fetcher = OANDAFetcher()

PAIR = "GBP_JPY"
PIP_SIZE = 0.01  # JPY pair


def fetch_data(pair: str, timeframe: str, count: int = 100) -> pd.DataFrame:
    """Fetch data using project's OANDAFetcher."""
    # Map timeframes to what fetcher expects
    tf_map = {'D': 'D', 'H4': '4h', 'H1': '1h', 'M15': '15m', 'M5': '5m'}
    tf = tf_map.get(timeframe, timeframe)
    
    df = fetcher.fetch_latest(pair, tf, count)
    df = df.reset_index()
    df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
    return df


def find_swing_points(df: pd.DataFrame):
    swing_highs = []
    swing_lows = []
    
    for i in range(2, len(df) - 2):
        if (df['high'].iloc[i] > df['high'].iloc[i-1] and
            df['high'].iloc[i] > df['high'].iloc[i-2] and
            df['high'].iloc[i] > df['high'].iloc[i+1] and
            df['high'].iloc[i] > df['high'].iloc[i+2]):
            swing_highs.append({'idx': i, 'price': df['high'].iloc[i]})
        
        if (df['low'].iloc[i] < df['low'].iloc[i-1] and
            df['low'].iloc[i] < df['low'].iloc[i-2] and
            df['low'].iloc[i] < df['low'].iloc[i+1] and
            df['low'].iloc[i] < df['low'].iloc[i+2]):
            swing_lows.append({'idx': i, 'price': df['low'].iloc[i]})
    
    return swing_highs, swing_lows


def find_fvgs(df: pd.DataFrame):
    """Find Fair Value Gaps (wick-based)."""
    bullish_fvgs = []
    bearish_fvgs = []
    
    for i in range(2, len(df)):
        # Bullish FVG: Gap between candle 1 high and candle 3 low
        c1_high = df['high'].iloc[i-2]
        c3_low = df['low'].iloc[i]
        
        if c3_low > c1_high:
            fvg = {
                'idx': i - 1,
                'top': c3_low,
                'bottom': c1_high,
                'fifty': (c3_low + c1_high) / 2,
                'mitigated': False
            }
            for j in range(i + 1, len(df)):
                if df['low'].iloc[j] <= fvg['fifty']:
                    fvg['mitigated'] = True
                    break
            if not fvg['mitigated']:
                bullish_fvgs.append(fvg)
        
        # Bearish FVG: Gap between candle 1 low and candle 3 high
        c1_low = df['low'].iloc[i-2]
        c3_high = df['high'].iloc[i]
        
        if c1_low > c3_high:
            fvg = {
                'idx': i - 1,
                'top': c1_low,
                'bottom': c3_high,
                'fifty': (c1_low + c3_high) / 2,
                'mitigated': False
            }
            for j in range(i + 1, len(df)):
                if df['high'].iloc[j] >= fvg['fifty']:
                    fvg['mitigated'] = True
                    break
            if not fvg['mitigated']:
                bearish_fvgs.append(fvg)
    
    return bullish_fvgs, bearish_fvgs


def find_equal_levels(df: pd.DataFrame, tolerance_pips: float = 3.0):
    """Find equal highs and equal lows (liquidity pools)."""
    swing_highs, swing_lows = find_swing_points(df)
    
    equal_highs = []
    equal_lows = []
    
    tol = tolerance_pips * PIP_SIZE
    
    for i, sh1 in enumerate(swing_highs):
        for sh2 in swing_highs[i+1:]:
            if abs(sh1['price'] - sh2['price']) <= tol:
                equal_highs.append({
                    'price': (sh1['price'] + sh2['price']) / 2,
                    'idx1': sh1['idx'],
                    'idx2': sh2['idx']
                })
                break
    
    for i, sl1 in enumerate(swing_lows):
        for sl2 in swing_lows[i+1:]:
            if abs(sl1['price'] - sl2['price']) <= tol:
                equal_lows.append({
                    'price': (sl1['price'] + sl2['price']) / 2,
                    'idx1': sl1['idx'],
                    'idx2': sl2['idx']
                })
                break
    
    return equal_highs, equal_lows


def find_order_blocks(df: pd.DataFrame):
    """Find order blocks (last opposite candle before displacement)."""
    bullish_obs = []
    bearish_obs = []
    
    for i in range(3, len(df)):
        # Check for bullish OB: down candle followed by strong up move
        if df['close'].iloc[i-2] < df['open'].iloc[i-2]:  # Previous is bearish
            # Check if next candles broke above and continued
            if (df['close'].iloc[i-1] > df['high'].iloc[i-2] and 
                df['close'].iloc[i] > df['close'].iloc[i-1]):
                bullish_obs.append({
                    'idx': i - 2,
                    'high': df['high'].iloc[i-2],
                    'low': df['low'].iloc[i-2],
                    'fifty': (df['high'].iloc[i-2] + df['low'].iloc[i-2]) / 2
                })
        
        # Check for bearish OB: up candle followed by strong down move
        if df['close'].iloc[i-2] > df['open'].iloc[i-2]:  # Previous is bullish
            if (df['close'].iloc[i-1] < df['low'].iloc[i-2] and 
                df['close'].iloc[i] < df['close'].iloc[i-1]):
                bearish_obs.append({
                    'idx': i - 2,
                    'high': df['high'].iloc[i-2],
                    'low': df['low'].iloc[i-2],
                    'fifty': (df['high'].iloc[i-2] + df['low'].iloc[i-2]) / 2
                })
    
    return bullish_obs, bearish_obs


def plot_chart(df: pd.DataFrame, tf: str, ax):
    """Plot fully marked up chart."""
    
    swing_highs, swing_lows = find_swing_points(df)
    bull_fvgs, bear_fvgs = find_fvgs(df)
    equal_highs, equal_lows = find_equal_levels(df)
    bull_obs, bear_obs = find_order_blocks(df)
    
    # Calculate range for PD array zones
    range_high = df['high'].max()
    range_low = df['low'].min()
    equilibrium = (range_high + range_low) / 2
    
    # Premium/Discount zones
    ax.axhspan(equilibrium, range_high, alpha=0.05, color='red', label='Premium Zone')
    ax.axhspan(range_low, equilibrium, alpha=0.05, color='green', label='Discount Zone')
    ax.axhline(y=equilibrium, color='yellow', linestyle='-', linewidth=1.5, alpha=0.7)
    ax.annotate(f"EQ: {equilibrium:.3f}", (5, equilibrium), fontsize=7, color='yellow')
    
    # Plot candlesticks
    for i in range(len(df)):
        color = '#00ff00' if df['close'].iloc[i] >= df['open'].iloc[i] else '#ff0000'
        ax.plot([i, i], [df['low'].iloc[i], df['high'].iloc[i]], color=color, linewidth=0.5)
        
        body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
        body_top = max(df['open'].iloc[i], df['close'].iloc[i])
        body_height = max(body_top - body_bottom, 0.001)
        
        rect = mpatches.Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                                   linewidth=0, facecolor=color)
        ax.add_patch(rect)
    
    # Plot BULLISH FVGs (green boxes)
    for fvg in bull_fvgs[-3:]:
        rect = mpatches.Rectangle((fvg['idx'], fvg['bottom']), 
                                   len(df) - fvg['idx'], fvg['top'] - fvg['bottom'],
                                   linewidth=1, facecolor='#00ff00', alpha=0.15, edgecolor='#00ff00')
        ax.add_patch(rect)
        ax.axhline(y=fvg['fifty'], color='#00ff00', linestyle=':', linewidth=1, alpha=0.8)
        ax.annotate(f"BUY: {fvg['fifty']:.3f}", 
                   (len(df) - 3, fvg['fifty']),
                   fontsize=6, color='#00ff00', ha='right')
    
    # Plot BEARISH FVGs (red boxes)
    for fvg in bear_fvgs[-3:]:
        rect = mpatches.Rectangle((fvg['idx'], fvg['bottom']),
                                   len(df) - fvg['idx'], fvg['top'] - fvg['bottom'],
                                   linewidth=1, facecolor='#ff0000', alpha=0.15, edgecolor='#ff0000')
        ax.add_patch(rect)
        ax.axhline(y=fvg['fifty'], color='#ff0000', linestyle=':', linewidth=1, alpha=0.8)
        ax.annotate(f"SELL: {fvg['fifty']:.3f}",
                   (len(df) - 3, fvg['fifty']),
                   fontsize=6, color='#ff0000', ha='right')
    
    # Plot ORDER BLOCKS (thicker boxes)
    for ob in bull_obs[-2:]:
        rect = mpatches.Rectangle((ob['idx'] - 0.5, ob['low']),
                                   len(df) - ob['idx'], ob['high'] - ob['low'],
                                   linewidth=2, facecolor='none', edgecolor='#00ffff', linestyle='--')
        ax.add_patch(rect)
        ax.annotate(f"B-OB", (ob['idx'], ob['low']), fontsize=6, color='#00ffff')
    
    for ob in bear_obs[-2:]:
        rect = mpatches.Rectangle((ob['idx'] - 0.5, ob['low']),
                                   len(df) - ob['idx'], ob['high'] - ob['low'],
                                   linewidth=2, facecolor='none', edgecolor='#ff6600', linestyle='--')
        ax.add_patch(rect)
        ax.annotate(f"S-OB", (ob['idx'], ob['high']), fontsize=6, color='#ff6600')
    
    # Plot EQUAL HIGHS (BSL)
    for eh in equal_highs[-2:]:
        ax.axhline(y=eh['price'], color='#ff00ff', linestyle='--', linewidth=2, alpha=0.8)
        ax.annotate(f"EQH/BSL: {eh['price']:.3f}", 
                   (len(df) - 2, eh['price']),
                   fontsize=7, color='#ff00ff', ha='right', fontweight='bold')
    
    # Plot EQUAL LOWS (SSL)
    for el in equal_lows[-2:]:
        ax.axhline(y=el['price'], color='#00ffff', linestyle='--', linewidth=2, alpha=0.8)
        ax.annotate(f"EQL/SSL: {el['price']:.3f}",
                   (len(df) - 2, el['price']),
                   fontsize=7, color='#00ffff', ha='right', fontweight='bold')
    
    # Swing highs/lows
    for sh in swing_highs[-5:]:
        ax.scatter(sh['idx'], sh['price'], marker='v', color='yellow', s=40, zorder=5)
    for sl in swing_lows[-5:]:
        ax.scatter(sl['idx'], sl['price'], marker='^', color='yellow', s=40, zorder=5)
    
    # Current price
    current = df['close'].iloc[-1]
    zone = "PREMIUM" if current > equilibrium else "DISCOUNT"
    zone_color = '#ff6666' if zone == "PREMIUM" else '#66ff66'
    
    ax.axhline(y=current, color='white', linestyle='-', linewidth=2, alpha=1)
    ax.annotate(f"NOW: {current:.3f}",
               (len(df) - 1, current),
               fontsize=8, color='white', fontweight='bold', ha='right',
               bbox=dict(boxstyle='round', facecolor='#333', alpha=0.9))
    
    # Determine structure
    bias = "NEUTRAL"
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        lh = swing_highs[-1]['price'] < swing_highs[-2]['price']
        ll = swing_lows[-1]['price'] < swing_lows[-2]['price']
        hh = swing_highs[-1]['price'] > swing_highs[-2]['price']
        hl = swing_lows[-1]['price'] > swing_lows[-2]['price']
        
        if lh and ll:
            bias = "BEARISH 🔴"
        elif hh and hl:
            bias = "BULLISH 🟢"
        else:
            bias = "MIXED ⚪"
    
    ax.set_title(f"{tf}: {bias} | Zone: {zone}\nBull FVG: {len(bull_fvgs)} | Bear FVG: {len(bear_fvgs)}", 
                 fontsize=10, fontweight='bold', color=zone_color)
    ax.grid(True, alpha=0.15)
    ax.set_ylabel('Price', fontsize=7)
    
    # X-axis labels
    tick_positions = range(0, len(df), max(1, len(df) // 4))
    tick_labels = [df['time'].iloc[i].strftime('%m/%d %H:%M') for i in tick_positions]
    ax.set_xticks(list(tick_positions))
    ax.set_xticklabels(tick_labels, fontsize=5, rotation=20)


def main():
    print(f"\n{'='*60}")
    print(f"  VEX CHART MARKUP: {PAIR}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Fetch timeframes
    timeframes = {
        'DAILY': 'D',
        '4-HOUR': 'H4',
        '1-HOUR': 'H1',
        '15-MIN': 'M15'
    }
    
    data = {}
    for label, tf in timeframes.items():
        print(f"  Fetching {label}...", end=" ")
        data[label] = fetch_data(PAIR, tf, 80)
        print(f"✓ {len(data[label])} candles")
    
    # Create 2x2 figure
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.patch.set_facecolor('#0a0a0a')
    
    fig.suptitle(
        f"GBP/JPY MULTI-TIMEFRAME MARKUP - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"🟢 Green Box = Bullish FVG | 🔴 Red Box = Bearish FVG | ⬜ Dotted = 50% Entry\n"
        f"🟣 Magenta = EQH (BSL) | 🔵 Cyan = EQL (SSL) | 🟡 Yellow = Equilibrium",
        fontsize=12, fontweight='bold', color='white'
    )
    
    positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
    labels = ['DAILY', '4-HOUR', '1-HOUR', '15-MIN']
    
    for i, label in enumerate(labels):
        row, col = positions[i]
        plot_chart(data[label], label, axes[row, col])
        print(f"  ✓ {label} plotted")
    
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = f"/Users/villain/Documents/transfer/ICT_WORK/ict_trainer/screenshots/GBPJPY_markup_{timestamp}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
    print(f"\n✅ Chart saved: {output_path}")
    plt.close()
    
    # Open it
    subprocess.run(["open", output_path])
    
    # Print thesis
    daily = data['DAILY']
    h4 = data['4-HOUR']
    current = h4['close'].iloc[-1]
    d_eq = (daily['high'].max() + daily['low'].min()) / 2
    h4_eq = (h4['high'].max() + h4['low'].min()) / 2
    
    bull_fvgs, bear_fvgs = find_fvgs(h4)
    
    print(f"\n{'='*60}")
    print(f"  VEX TRADE THESIS")
    print(f"{'='*60}")
    print(f"\n  Current: {current:.3f}")
    print(f"  Daily EQ: {d_eq:.3f} → {'PREMIUM (SHORT BIAS)' if current > d_eq else 'DISCOUNT (LONG BIAS)'}")
    print(f"  4H EQ: {h4_eq:.3f}")
    
    if bear_fvgs:
        print(f"\n  UNMITIGATED SELL ZONES:")
        for fvg in bear_fvgs[-3:]:
            print(f"    → FVG 50%: {fvg['fifty']:.3f}")
    
    if bull_fvgs:
        print(f"\n  UNMITIGATED BUY ZONES:")
        for fvg in bull_fvgs[-3:]:
            print(f"    → FVG 50%: {fvg['fifty']:.3f}")


if __name__ == "__main__":
    main()
