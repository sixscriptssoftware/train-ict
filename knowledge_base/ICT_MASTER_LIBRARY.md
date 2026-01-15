# ICT (Inner Circle Trader) Master Knowledge Library
## Comprehensive Training Data for AI Trading Agent

---

# PART 1: CORE CONCEPTS

## 1.1 Market Structure

### Definition
Market Structure is the foundational layer of ICT methodology representing the real-time footprint of Smart Money. It shows whether institutions are accumulating (bullish) or distributing (bearish).

### Key Components
- **Bullish Structure**: Price making Higher Highs (HH) and Higher Lows (HL)
- **Bearish Structure**: Price making Lower Lows (LL) and Lower Highs (LH)
- **Validation**: Structure is only valid when confirmed by DISPLACEMENT

### Detection Rules
1. Identify swing highs and swing lows on the chart
2. Track the sequence: HH/HL = bullish, LL/LH = bearish
3. Confirm with displacement (strong, impulsive candle breaking structure)
4. Without displacement, a break is a liquidity raid, not structure

### Timeframe Priority
- Daily > 4H > 1H > 15M > 5M
- Always confirm structure on 1H and Daily before intraday entries

---

## 1.2 Break of Structure (BOS) vs Shift in Market Structure (SMS/MSS)

### Break of Structure (BOS)
- **Type**: Continuation signal
- **Definition**: Price breaks a previous swing point IN THE SAME DIRECTION as the prevailing trend with visible displacement
- **Example**: In bullish trend, price forms new HH that breaks previous HH with strength
- **Trading**: Confirms trend continuation; enter on retracements (OTE, FVG)

### Shift in Market Structure (SMS/MSS)
- **Type**: Reversal signal  
- **Definition**: Price breaks a swing point AGAINST the current trend with clear displacement
- **Validation**: Must have displacement through a protected swing low/high
- **Trading**: NOT an entry signal by itself; wait for new structure to form

### Change of Character (CHoCH)
- **Timing**: Long-term reversal signal
- **Location**: Key structure points
- **Purpose**: Signals major trend shifts
- Weaker than SMS but alerts to weakening dominant trend

### Key Distinction
| Signal | Direction | Meaning | Action |
|--------|-----------|---------|--------|
| BOS | With trend | Continuation | Look for entries on retracement |
| SMS/MSS | Against trend | Reversal starting | Wait for new structure confirmation |
| CHoCH | Against trend | Trend weakening | Early warning, prepare for reversal |

---

## 1.3 Fair Value Gap (FVG)

### Definition
A three-candle price formation exposing market imbalance where price moved so rapidly that the market skipped over opposing liquidity.

### Formation Rules
**Bullish FVG:**
- Candle 1: Any candle
- Candle 2: Large bullish displacement candle
- Candle 3: Opens higher
- **GAP**: Space between Candle 1's HIGH and Candle 3's LOW

**Bearish FVG:**
- Candle 1: Any candle
- Candle 2: Large bearish displacement candle  
- Candle 3: Opens lower
- **GAP**: Space between Candle 1's LOW and Candle 3's HIGH

### Validity Criteria
1. Must follow displacement (not just any gap)
2. Must be contextualized with market structure
3. Should align with liquidity raids and time-of-day models
4. Avoid FVGs in chop/consolidation

### Entry Refinement Levels
- **50% Midpoint**: Equilibrium of the gap, quick rebalance entries
- **62% Level**: Deeper retrace, better R:R
- **70.5% Sweet Spot**: Most sensitive level (aligns with OTE logic)

### Trading Rules
- Use FVGs as entry zones ONLY after confirmed BOS/SMS and directional bias
- Price often rebalances into FVG before continuing
- Combine with Order Block and OTE for high-probability setups

---

## 1.4 Order Block (OB)

### Definition
The last opposite-colored candle before a strong displacement move. Represents where institutions placed orders before breaking structure.

### Types
- **Bullish OB**: Last DOWN candle before bullish displacement
- **Bearish OB**: Last UP candle before bearish displacement

### Validation
- Must precede displacement (no displacement = no OB)
- Best when nested within OTE zones or aligned with FVGs
- Most reactive during Killzones with SMT or liquidity sweep

### Entry Strategy
- Price may wick through OB but respect body or midpoint
- Target the 50% level of the OB candle for precision
- Use as re-entry zone on retracements

---

## 1.5 Displacement

### Definition
Strong, impulsive price move that breaks a significant swing high or low with authority. The footprint of institutional order flow.

### Characteristics
- Long-bodied candle(s)
- Little to no wick on opposite end
- Not a grind or fakeout - violent assertion of control

### What Displacement Validates
1. Breaks of Structure (BOS)
2. Shifts in Market Structure (SMS)
3. Fair Value Gaps (FVGs)
4. Order Blocks (OBs)

### Rule
**Without displacement, any break or setup should be IGNORED.**

---

## 1.6 Liquidity

### Buy-Side Liquidity (BSL)
- Resting buy stop orders above swing highs
- Where short sellers have stops
- Price is "drawn" to sweep these levels

### Sell-Side Liquidity (SSL)
- Resting sell stop orders below swing lows
- Where long traders have stops
- Price is "drawn" to sweep these levels

### Liquidity Pools
- Equal highs/lows
- Previous day/week highs and lows
- Session highs/lows
- Asia range extremes

### Draw on Liquidity
- The institutional TARGET - where Smart Money intends to deliver price
- Must be identified BEFORE any trade
- "If there is no liquidity to draw on, there is no reason for price to move"

---

## 1.7 Optimal Trade Entry (OTE)

### Definition
The 61.8% to 79% Fibonacci retracement range where Smart Money often re-engages after displacement.

### Key Levels
- **61.8%**: Upper boundary of OTE zone
- **70.5%**: "Smart Money entry point" - most sensitive level
- **79%**: Lower boundary of OTE zone

### Application
1. Only use after confirmed displacement and BOS/SMS
2. Measure from swing low to swing high (bullish) or vice versa
3. Most effective during Killzones
4. Often aligns with FVGs and OBs

---

## 1.8 Premium and Discount Zones

### Concept
The 50% midpoint of any swing high-low range divides price into expensive (premium) and cheap (discount) zones.

### Trading Rules
- **Bullish narrative**: Buy in DISCOUNT (below 50%), target PREMIUM
- **Bearish narrative**: Sell in PREMIUM (above 50%), target DISCOUNT

### Application
- Filter setups: Bullish FVG in premium = low probability
- Bearish OB in discount = unlikely to hold
- Scales across all timeframes

---

# PART 2: ADVANCED CONCEPTS

## 2.1 Breaker Block

### Definition
A failed order block that causes a shift in market structure and acts as support/resistance.

### Formation
1. Price creates an Order Block
2. Price fails to continue in expected direction
3. Structure breaks THROUGH the OB
4. The failed OB becomes a Breaker Block

### Trading
- Entry on retest of broken level
- Confirms with market structure (HTF bias)
- Wait for clear breaks and retests

---

## 2.2 Mitigation Block

### Definition
A candle that caused a false move or liquidity raid, then was revisited and respected later as price returned.

### Key Difference from OB
- Order Blocks: Origin of institutional move
- Mitigation Blocks: Formed by FAILED breakouts/liquidity raids

### Trading
- Use only after SMS or liquidity raid
- Often align with FVGs or OBs
- Confirm the raid and reversal first

---

## 2.3 Balanced Price Range (BPR)

### Definition
Forms after price aggressively moves through a high/low (liquidity pool), then returns and trades back inside the range.

### Formation
1. Liquidity sweep high/low occurs
2. Structure level breaks
3. Price retraces and consolidates inside the range

### Trading
- Midpoint often acts as reaction level
- Used for re-entries when missed initial moves
- Strongest after BOS that sweeps liquidity and immediately rebalances

---

## 2.4 Liquidity Void

### Definition
A long-bodied candle with minimal to no wick overlap - visual representation of imbalance where price moved too fast.

### Characteristics
- No opposing transaction volume
- Often appears during major institutional delivery legs
- Midpoint is often a reaction point

### Trading
- Displacement confirmation (not entry signal)
- Price may rebalance before continuation
- Combine with BOS, OB, or FVG

---

## 2.5 PD Array Matrix

### Components (Priority Order)
1. **Order Blocks (OB)** - Institutional entry zones
2. **Fair Value Gaps (FVG)** - Price imbalances
3. **Breaker Blocks** - Failed OBs acting as S/R
4. **Mitigation Blocks** - Post-raid reaction zones
5. **Liquidity Voids** - Extreme imbalances
6. **NWOG/NDOG** - New Week/Day Opening Gaps

### Application
- Use PD Arrays in conjunction with ICT 2022 Model or Silver Bullet
- Higher timeframe PD Arrays take priority
- Always combine with structure and time

---

# PART 3: EXECUTION MODELS

## 3.1 Power of Three (PO3 / AMD)

### Three Phases
1. **Accumulation**: Range/consolidation, Smart Money builds positions
2. **Manipulation**: False move (Judas Swing), sweeps liquidity
3. **Distribution/Expansion**: True move delivering to liquidity target

### Session Application
- **Asian Session (7PM-12AM NY)**: Accumulation typically forms
- **London Open**: Manipulation phase begins
- **NY Session**: Distribution/Expansion completes

### Trading
1. Identify accumulation range
2. Wait for manipulation (sweep of range high/low)
3. Enter after displacement confirms distribution direction
4. Target opposite liquidity

---

## 3.2 Judas Swing

### Definition
Early-session move that lures traders in wrong direction, creating liquidity before the real move.

### Purpose
- Trap liquidity
- Induce retail participation
- Fuel institutional positions opposite direction

### Timing
- Before 10:00 AM EST typically
- Completes manipulation by Silver Bullet window
- Most common: London Open (2-5 AM EST), NY AM (7-10 AM EST)

### Trading Rule
**Never chase early Killzone breakouts - assume Judas Swing until displacement confirms direction.**

---

## 3.3 Silver Bullet Model

### Definition
Precision intraday entry framework operating EXCLUSIVELY 10-11 AM EST.

### Sequence
1. **Liquidity Sweep**: At/before 10AM, price raids BSL or SSL
2. **SMS**: Price displaces opposite the raid, structure confirms
3. **Execution Zone**: Enter on FVG/OB retracement (aligned with OTE)
4. **Delivery**: Target opposite intraday liquidity (30-60 min typically)

### Rules
- Time is the filter - no setup outside 10-11 AM counts
- Raid + displacement + FVG sequence is mandatory
- If setup fails, stop trading for the day
- Typically 1-2R scalps

---

## 3.4 Judas Swing + FVG Entry Combo

### Four Non-Negotiable Elements
1. **Liquidity Raid**: 7:00-9:30 AM or into 10:00 AM, sweep BSL/SSL
2. **Displacement**: Opposite raid direction, breaks intraday swing (SMS/BOS)
3. **Execution**: Retrace into FVG during 10-11 AM, OTE band confluence
4. **Delivery Target**: Clear draw on liquidity opposite side

### Invalidation
- Close through far side of FVG
- Second raid without displacement
- No displacement = no trade

---

## 3.5 NY AM/PM Delivery Models

### NY AM Session (7AM-12PM EST)
- Sets up day's primary move
- Begins with Judas Swing (7-9:30 AM)
- Silver Bullet provides entries (10-11 AM)
- Targets major liquidity pool (PDH/PDL, morning range extremes)

### NY PM Session (1-3 PM EST)
- Continuation OR reversal phase
- If AM incomplete: PM extends to target
- If AM completed: PM may engineer secondary Judas
- Provides scalp setups into close

### Key Insight
**AM session is king - most opportunity there. PM is for extending or rebalancing.**

---

## 3.6 Market Maker Buy/Sell Models

### Sell Model (Distribution-Based)
1. **Accumulation**: Sideways during Asia/early London
2. **Manipulation (Judas)**: Spike above BSL, trap breakout buyers
3. **Distribution**: Displace lower, deliver to SSL

### Buy Model (Accumulation-Based)
1. **Accumulation**: Range-bound below major high
2. **Manipulation**: Spike below SSL, trigger stops
3. **Expansion**: BOS higher, deliver to BSL

### Rule
"Never counter a completed model" - once distribution/accumulation complete, expect continuation toward liquidity.

---

## 3.7 ICT 2022 Trading Model

### Core Principle
**"Price is nothing without time."**

### Components
1. **Daily Bias**: Establish on daily timeframe first
2. **Liquidity Sweeps**: Previous day/session/week highs/lows
3. **Market Structure Shift (MSS)**: Confirm on lower TFs (5m, 3m, 1m)
4. **PD Array**: Target FVG, OB, Breaker after MSS

### Session Execution
**London (3 AM NY):**
1. Mark NY midnight to London open range
2. Wait for liquidity sweep
3. Identify MSS with displacement
4. Execute at PD Array retest

**New York (8 AM NY):**
- If London swept: Use OTE from London range
- If London ranged: Mark NY midnight-open, look for sweep

---

# PART 4: TIME-BASED CONCEPTS

## 4.1 Killzones

### London Killzone (2-5 AM EST)
- Engineers liquidity, creates Judas Swings
- Sets stage for NY delivery

### New York AM Killzone (7-10 AM EST)
- Highly reactive
- Liquidity raids, SMT divergences, structural shifts
- Silver Bullet setups initiate from tail end

### New York PM Killzone (1-3 PM EST)
- Secondary opportunity
- Continuation or reversal of morning setups

### Asian Kill Zone (7-10 PM EST)
- Lower volatility, accumulation zone
- Consolidation before London

### Rule
**Do not take entries outside Killzones - especially 11AM-12:30PM dead zone.**

---

## 4.2 ICT Macro Times

### Definition
Specific 20-minute intervals where the algorithm seeks liquidity or reprices FVGs.

### Key Macro Windows
- **London Macros**: Within 2-5 AM EST
- **NY AM Macros**: First 20 minutes of session
- **NY Lunch Macros**: Around noon
- **NY PM Macros**: Within 1-3 PM EST

### Purpose
- Add confluence to trading decisions
- Short instructions creating events in price delivery
- Target liquidity and balance imbalances

---

## 4.3 IPDA (Interbank Price Delivery Algorithm)

### Definition
ICT concept that price movements are driven by liquidity zones and imbalances, not random.

### Core Principle
Smart Money follows structured rules to:
1. Accumulate liquidity
2. Balance imbalances
3. Deliver price between liquidity pools

### Analysis Points
- **Price**: Key levels, PD Arrays
- **Time**: Session-specific behavior, macros
- **Liquidity**: Areas of price inaccuracy to cover

---

## 4.4 Daily Bias Model

### Definition
Pre-session determination of buy/sell day using HTF context.

### Components
1. **HTF Market Structure**: Daily, 4H, 1H
2. **Draw on Liquidity**: Where is price being delivered?
3. **Premium/Discount**: Are we expensive or cheap?
4. **Key Liquidity Pools**: PDH/PDL, weekly levels
5. **Time of Week**: Monday accumulation, Friday expansion

### Trading Rule
- Bullish bias = only buy setups at discount
- Bearish bias = only sell setups at premium
- Recalculate after major BOS/SMS or HTF liquidity event

---

# PART 5: CONFIRMATION TOOLS

## 5.1 SMT Divergence (Smart Money Tool)

### Definition
Comparative analysis between correlated instruments where one makes new swing high/low and the other fails to confirm.

### Examples
- EUR/USD makes lower low, GBP/USD does NOT = Bullish SMT
- NQ makes higher high, ES does NOT = Bearish SMT

### Best Use
- After liquidity sweep
- Confirmation of SMS
- During Killzones
- NOT an entry signal alone - filter and confirmation

---

## 5.2 Institutional Order Flow

### Definition
Dominant direction Smart Money pushes price - underlying bias driving structure and delivery.

### Building Blocks
1. Market structure (HH/HL or LL/LH)
2. Shifts in structure (SMS)
3. Liquidity targets (BSL/SSL)
4. Displacement events
5. Time of day/delivery windows

### Rule
**Do not counter flow unless confirmed SMS and divergence - "You will get steamrolled."**

---

## 5.3 Model Stacking (Confluence)

### High-Probability Setup Requirements
1. **Bias Confirmation**: HTF structure, order flow, daily bias
2. **Liquidity Event**: Judas Swing, stop hunt, SMT
3. **Displacement + BOS/SMS**: Smart Money footprint
4. **Execution Zone**: OB or FVG at OTE/50% levels
5. **Timing**: Inside Killzone
6. **Delivery Target**: Clear draw on liquidity

### Rule
**Any single concept can fail, but confluence makes the model reliable. Build playbook around 3-5 confluences, not one.**

---

# PART 6: MULTI-TIMEFRAME WORKFLOW

## 6.1 HTF Sweep → LTF Entry Process

### Layer 1: Higher Timeframe Sweep (Context)
- Identify external liquidity pool (PDH, PDL, weekly high/low)
- Watch for sweep of that level
- Bias shifts once raid occurs

### Layer 2: Intermediate Timeframe Confirmation (Structure)
- Move to H1/M15
- Check for BOS or SMS after sweep
- Displacement must confirm intent
- Identify new OB or FVG zones

### Layer 3: Lower Timeframe Execution (Precision)
- Drop to M5 or M1 inside Killzone
- Wait for retrace into OB/FVG from ITF
- Enter with refined levels (50% FVG, OTE 70.5%)
- Target opposite liquidity (internal first, external second)

### Rule
**Always start HTF → LTF. Never the other way. If no HTF liquidity event, no reason to trade.**

---

# PART 7: SPECIAL MODELS

## 7.1 Turtle Soup

### Standard Version
1. Price trades through previous high/low
2. Immediately reverses
3. Entry when price trades back inside prior candle range

### Turtle Soup Plus One
1. Day 1: Price runs high/low, closes
2. Day 2: Entry after confirmation (SMT, BOS, rejection)
3. More conservative and reliable

### Best Conditions
- Obvious level being run (equal highs/lows, prior week high/low)
- Impulsive move through level but fails to follow through
- No displacement confirming breakout

---

## 7.2 Equity Runs / Stop Hunts

### Definition
Aggressive price movement through well-defined swing to trigger stops, fuel liquidity, create opposite move.

### Targets
- Above equal highs (BSL)
- Below swing lows (SSL)
- Prior day/week highs/lows
- Session ranges (Asia, London)

### Key Insight
**Equity Runs are necessary, not random - they provide liquidity institutions need to position.**

### Trading
- Look for during Killzones (7-10 AM, 2-3 PM EST)
- Precede Judas Swings, Silver Bullet, SMT, BOS/SMS
- Wait for confirmation (displacement + SMS)

---

# PART 8: ALGORITHMIC IMPLEMENTATION

## 8.1 Python Package: smartmoneyconcepts

### Installation
```bash
pip install smartmoneyconcepts
```

### Core Functions

```python
from smartmoneyconcepts import smc

# Fair Value Gap Detection
fvg_data = smc.fvg(ohlc, join_consecutive=False)
# Returns: FVG direction (1/-1), Top, Bottom, MitigatedIndex

# Swing Highs and Lows
swings = smc.swing_highs_lows(ohlc, swing_length=50)
# Returns: HighLow (1/-1), Level

# Break of Structure & Change of Character
structure = smc.bos_choch(ohlc, swing_highs_lows, close_break=True)
# Returns: BOS, CHOCH, Level, BrokenIndex

# Order Blocks
ob_data = smc.ob(ohlc, swing_highs_lows, close_mitigation=False)
# Returns: OB direction (1/-1), Top, Bottom, OBVolume, Percentage

# Liquidity Detection
liquidity = smc.liquidity(ohlc, swing_highs_lows, range_percent=0.01)
# Returns: Liquidity direction (1/-1), Level, End, Swept

# Previous High/Low
prev_hl = smc.previous_high_low(ohlc, time_frame="1D")
# Returns: PreviousHigh, PreviousLow
```

### Data Requirements
- DataFrame with columns: ["open", "high", "low", "close", "volume"]
- All column names must be lowercase

---

## 8.2 Technical Architecture for Trading Bot

### Component Stack
| Layer | Technology |
|-------|-----------|
| Data | Pandas, CCXT, MetaTrader5, broker APIs |
| Strategy | smartmoneyconcepts library, custom algorithms |
| Signals | TradingView + Pine Script OR custom detection |
| Webhooks | Flask-based server |
| Execution | Exchange/broker APIs |
| Backtesting | backtrader, vectorbt |

### Automated Detection Capabilities
- FVG, IFVG (Inversion FVG)
- Order Blocks
- Market Structure (BOS, SMS, CHoCH)
- Liquidity Sweeps
- Swing Points
- Killzone Time Filtering

---

## 8.3 Detection Algorithm Logic

### FVG Detection
```
For each candle at index i:
  If bullish:
    If candle[i-2].high < candle[i].low:
      FVG = (top: candle[i].low, bottom: candle[i-2].high)
  If bearish:
    If candle[i-2].low > candle[i].high:
      FVG = (top: candle[i-2].low, bottom: candle[i].high)
```

### Swing Detection
```
For swing_length = N:
  Swing High at i if:
    high[i] > high[i-N:i] and high[i] > high[i+1:i+N+1]
  Swing Low at i if:
    low[i] < low[i-N:i] and low[i] < low[i+1:i+N+1]
```

### BOS/SMS Detection
```
After identifying swings:
  BOS (bullish): New HH breaks previous HH with displacement
  BOS (bearish): New LL breaks previous LL with displacement
  SMS (bullish): Price breaks below HL then reverses with displacement
  SMS (bearish): Price breaks above LH then reverses with displacement
```

### Order Block Detection
```
After BOS/SMS confirmed:
  Bullish OB: Last down candle before bullish displacement
  Bearish OB: Last up candle before bearish displacement
  Mark high and low of that candle as OB zone
```

---

# PART 9: RESOURCES AND REFERENCES

## 9.1 Official Sources
- **YouTube**: youtube.com/innercircletrader
- **Website**: theinnercircletrader.com
- **Core Mentorship**: ICT 2022 Mentorship Playlist

## 9.2 Key Video References
| Concept | Episode | Timestamp |
|---------|---------|-----------|
| Market Structure | Ep. 3 | 11:30 |
| BOS vs SMS | Ep. 3 | 13:10 |
| Liquidity | Ep. 4 | 07:30, 10:40, 14:20 |
| Displacement & FVG | Ep. 5 | 03:40, 06:20 |
| OTE | Ep. 6 | 08:40 |
| Order Blocks | Ep. 7 | 05:10 |
| Premium/Discount | Ep. 7 | 04:15 |
| BPR | Ep. 8 | 05:55 |
| Liquidity Voids | Ep. 9 | 04:25 |
| SMT Divergence | Ep. 9 | 05:45 |
| Judas Swings | Ep. 10 | 06:00 |
| Turtle Soup | Ep. 11 | 07:15 |
| Mitigation Blocks | Ep. 12 | 07:50 |
| Multi-TF Analysis | Ep. 12 | 07:00 |
| Market Maker Models | Ep. 13 | 06:30 |
| Daily Bias | Ep. 14 | 08:05 |
| Silver Bullet | Ep. 15 | 04:50 |
| AM/PM Sessions | Ep. 16 | 06:15 |
| Model Stacking | Ep. 17 | 05:10 |

## 9.3 GitHub Repositories
- `joshyattridge/smart-money-concepts` - Python package
- `tristanlee85/ict-indicators` - Pine Script indicators
- `manuelinfosec/profittown-sniper-smc` - ICT bot implementation

## 9.4 Community Resources
- innercircletrader.net (tutorials and glossary)
- TradingView ICT Scripts: tradingview.com/scripts/search/ict/
- r/InnerCircleTraders subreddit

---

# PART 10: TRAINING DATA STRUCTURE

## 10.1 Concept Encoding Schema

```json
{
  "concept": "FVG",
  "type": "bullish|bearish",
  "timeframe": "M5|M15|H1|H4|D1",
  "candle_1": {"open": float, "high": float, "low": float, "close": float},
  "candle_2": {"open": float, "high": float, "low": float, "close": float},
  "candle_3": {"open": float, "high": float, "low": float, "close": float},
  "gap_top": float,
  "gap_bottom": float,
  "gap_50_percent": float,
  "mitigated": boolean,
  "mitigated_index": int|null,
  "killzone": "london|ny_am|ny_pm|asian|none",
  "confluence_score": float
}
```

## 10.2 Trade Signal Schema

```json
{
  "timestamp": "ISO8601",
  "symbol": "EURUSD|GBPUSD",
  "direction": "long|short",
  "model": "silver_bullet|judas_fvg|ote_retracement",
  "htf_bias": "bullish|bearish",
  "killzone": "ny_am",
  "confluences": {
    "fvg": boolean,
    "order_block": boolean,
    "ote_zone": boolean,
    "liquidity_sweep": boolean,
    "smt_divergence": boolean,
    "displacement": boolean,
    "bos_sms": "bos|sms|choch"
  },
  "confluence_count": int,
  "entry_price": float,
  "stop_loss": float,
  "target_1": float,
  "target_2": float,
  "risk_reward": float,
  "outcome": "win|loss|breakeven",
  "pips_result": float
}
```

---

*This library is designed for training an AI agent to predict and execute ICT-based trading strategies.*
*Compiled from official ICT sources, community resources, and algorithmic implementations.*
*Version 1.0 - January 2026*
