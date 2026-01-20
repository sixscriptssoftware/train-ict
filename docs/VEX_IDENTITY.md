# VEX: ICT Trading AI Agent - Complete System Documentation

## Who is VEX?

VEX is an autonomous AI trading agent designed to execute trades using the Inner Circle Trader (ICT) methodology developed by Michael J. Huddleston. VEX is not a simple indicator-based bot—it is a cognitive trading system that understands market structure, institutional order flow, and time-based algorithmic behavior the same way a professional ICT trader would.

The name "VEX" represents the agent's role: to vex the market makers by trading alongside smart money rather than against it.

---

## Project Mission

**Primary Objective:** Create an AI trading system that can autonomously identify, enter, manage, and exit trades using pure ICT methodology with a 60%+ win rate and 3:1+ average risk-reward ratio.

**Secondary Objectives:**
1. Maintain a learning system that improves from every trade
2. Journal all trades with ICT-specific analysis
3. Operate within prop firm rules (FTMO, etc.)
4. Provide real-time market analysis and trade coaching

---

## Understanding ICT Methodology (Critical Context)

ICT (Inner Circle Trader) is a trading methodology that reveals how institutional market makers and algorithms manipulate price to engineer liquidity before delivering price to their intended targets. This is NOT technical analysis in the traditional sense—it is understanding the mechanics of how markets are actually delivered.

### Core ICT Principles VEX Must Embody:

#### 1. **Liquidity is the Target**
Markets do not move randomly. Price is delivered to areas where stop losses cluster (liquidity pools). These include:
- **Buy-side Liquidity (BSL):** Equal highs, old highs, swing highs where buy stops rest
- **Sell-side Liquidity (SSL):** Equal lows, old lows, swing lows where sell stops rest
- **Relative Equal Highs/Lows:** Areas where retail traders place stops

VEX must identify these pools and anticipate which one price will seek BEFORE it happens.

#### 2. **Fair Value Gaps (FVG) / Imbalances**
When price moves aggressively (displacement), it leaves behind inefficiencies—gaps between candle wicks where price did not trade. These FVGs act as magnets:
- Price tends to return to fill these gaps (rebalance)
- FVGs in premium zones (above equilibrium) are resistance
- FVGs in discount zones (below equilibrium) are support

VEX identifies FVGs on multiple timeframes and uses them as entry points.

#### 3. **Order Blocks (OB)**
The last opposing candle before a significant move represents institutional order placement:
- **Bullish OB:** Last down-close candle before an up move
- **Bearish OB:** Last up-close candle before a down move

These are NOT random support/resistance—they mark where smart money placed orders.

#### 4. **Market Structure Shifts**
- **BOS (Break of Structure):** Continuation—price breaks a swing high/low in trend direction
- **CHoCH (Change of Character):** Reversal—price breaks structure against the trend
- **SMS (Smart Money Shift):** Internal structure change signaling potential reversal

VEX must track structure on HTF (4H, Daily) for bias and LTF (15m, 5m) for entry.

#### 5. **Time-Based Algorithmic Behavior**
ICT teaches that markets are algorithmically delivered at specific times:

**Killzones (High Probability Trading Windows):**
- **Asian Session:** 20:00-00:00 EST - Range formation, stop hunts
- **London Open:** 02:00-05:00 EST - Major moves begin
- **New York AM:** 07:00-10:00 EST - Highest volume, best setups
- **New York PM:** 13:30-16:00 EST - Continuation or reversal

**Macro Times (Micro Manipulations):**
- :50-:10 of each hour - Algorithmic delivery windows
- News events - Engineered liquidity grabs

**Power of Three (AMD Cycle):**
Every trading day/session follows:
1. **Accumulation:** Range-bound, building positions
2. **Manipulation:** False move to grab liquidity (Judas Swing)
3. **Distribution:** Real move to the daily target

VEX must recognize which phase the market is in.

#### 6. **Premium vs. Discount Arrays**
Using Fibonacci or equilibrium (50% of range):
- **Premium (above 50%):** Sell zone - look for shorts
- **Discount (below 50%):** Buy zone - look for longs
- **Equilibrium:** Decision zone - wait for confirmation

VEX should only buy in discount and sell in premium.

#### 7. **SMT Divergence (Smart Money Technique)**
When correlated pairs (EUR/USD vs GBP/USD, or indices ES vs NQ) make divergent highs/lows:
- If EUR makes a higher high but GBP fails to = bearish divergence
- If EUR makes a lower low but GBP fails to = bullish divergence

This signals smart money accumulation/distribution.

---

## The VEX Trading Algorithm Architecture

### Multi-Timeframe Analysis Flow

```
DAILY/WEEKLY (HTF Bias)
    ↓
4-HOUR (Institutional Levels)
    ↓
1-HOUR (Session Structure)
    ↓
15-MINUTE (Entry Timeframe)
    ↓
5-MINUTE (Precision Entry)
```

### Decision Pipeline

```python
# Pseudocode for VEX decision flow
def analyze_for_trade():
    # Step 1: Establish HTF Bias
    htf_bias = determine_daily_weekly_bias()  # LONG or SHORT only
    
    # Step 2: Identify HTF Liquidity Targets
    targets = find_liquidity_pools(htf)  # Where is price likely going?
    
    # Step 3: Wait for LTF Structure Alignment
    ltf_structure = get_market_structure(15m)
    if ltf_structure.direction != htf_bias:
        return NO_TRADE  # Don't fight HTF
    
    # Step 4: Check Time (Must be in Killzone)
    if not in_killzone():
        return NO_TRADE
    
    # Step 5: Look for Entry Model
    entry = find_entry_model()  # FVG, OB, OTE, etc.
    if not entry:
        return NO_TRADE
    
    # Step 6: Validate Confluences
    confluences = count_confluences()
    if confluences < 5:
        return NO_TRADE  # Need multiple confirmations
    
    # Step 7: Calculate Risk
    stop = calculate_stop()  # Above/below structure
    target = calculate_target()  # Liquidity pool or FVG
    rr = target_distance / stop_distance
    if rr < 2.0:
        return NO_TRADE  # Minimum 2R required
    
    # Step 8: Execute
    return TRADE(direction=htf_bias, entry=entry, stop=stop, target=target)
```

### The VexBrainV2 Scoring System

VEX uses an edge-based scoring system that evaluates 13+ confluences:

| Confluence | Points | Description |
|------------|--------|-------------|
| HTF FVG | +20 | 4H Fair Value Gap in entry zone |
| LTF FVG | +15 | 15m Fair Value Gap for precision |
| Order Block | +15 | Institutional order placement zone |
| Displacement | +10 | Strong momentum confirming direction |
| Structure Break | +15 | BOS/CHoCH confirming trend |
| Liquidity Sweep | +20 | Stop hunt before reversal |
| Killzone Active | +10 | Trading in high-probability window |
| Premium/Discount | +10 | Entry in correct zone |
| SMT Divergence | +15 | Correlated pair confirmation |
| Model Detection | +25 | Silver Bullet, Turtle Soup, etc. |

**Trade Grade Thresholds:**
- A+ Setup: 80+ points (EXECUTE IMMEDIATELY)
- A Setup: 65-79 points (High confidence)
- B Setup: 50-64 points (Acceptable with confirmation)
- C Setup: Below 50 (NO TRADE)

---

## ICT Trading Models VEX Must Execute

### 1. Silver Bullet (Primary Model)
**Time:** 10:00-11:00 AM EST or 14:00-15:00 EST
**Setup:**
1. Wait for FVG to form in killzone
2. Price returns to FVG
3. Enter at FVG with stop beyond
4. Target: Opposing liquidity pool

### 2. Turtle Soup
**Setup:**
1. Identify old high/low (liquidity pool)
2. Wait for price to sweep it (stop hunt)
3. Look for immediate reversal
4. Enter on FVG/OB after sweep
5. Target: Opposing liquidity

### 3. Judas Swing
**Setup:**
1. Asian range established
2. False breakout in one direction (manipulation)
3. Reversal back through range
4. Enter on retest of range
5. Target: Opposing side + extension

### 4. OTE Retracement (Optimal Trade Entry)
**Setup:**
1. Identify impulse move
2. Wait for retracement to 62-79% Fibonacci
3. Enter at OTE zone with FVG/OB confluence
4. Stop: Beyond 100% retracement
5. Target: -27% to -62% extension

### 5. Power of Three (AMD)
**Setup:**
1. Identify accumulation phase (Asian range)
2. Wait for manipulation (false move)
3. Enter distribution phase on structure break
4. Target: Daily/Weekly objective

---

## Risk Management Rules

VEX must enforce these rules WITHOUT EXCEPTION:

```python
RISK_RULES = {
    "max_risk_per_trade": 1.0,      # 1% of account
    "max_daily_loss": 3.0,          # 3% max daily drawdown
    "max_weekly_loss": 5.0,         # 5% max weekly drawdown
    "max_open_trades": 2,           # Never overexpose
    "min_rr_ratio": 2.0,            # Minimum 2:1 RR
    "required_confluences": 5,       # Minimum confirmations
    "forbidden_news_window": 15,     # Minutes before/after high-impact news
}
```

---

## The Learning System

VEX maintains a knowledge base that learns from every trade:

### What VEX Tracks:
1. **Win Rate by Model:** Which setups perform best
2. **Win Rate by Session:** London vs NY vs Asian
3. **Win Rate by Pair:** EUR/USD vs GBP/USD performance
4. **Confluence Effectiveness:** Which confirmations matter most
5. **Stop Distance Analysis:** Are stops too tight/loose?
6. **Entry Timing:** Early entries vs late entries

### Feedback Loop:
```
TRADE EXECUTED
    ↓
OUTCOME RECORDED (Win/Loss, R-multiple)
    ↓
PATTERN ANALYSIS (What confluences were present?)
    ↓
WEIGHT ADJUSTMENT (Increase/decrease confluence scores)
    ↓
IMPROVED FUTURE DECISIONS
```

---

## Technical Implementation

### Core Files:
- `src/ict_agent/vex_brain_v2.py` - Main decision engine (76KB)
- `src/ict_agent/detectors/` - ICT pattern detection
- `src/ict_agent/models/` - Trading model implementations
- `src/ict_agent/execution/` - OANDA API integration
- `src/ict_agent/learning/` - Knowledge management

### Execution:
```bash
# Run autonomous trader
python scripts/trading/vex_unleashed.py

# Run market scanner
python scripts/trading/vex_scan.py

# Launch dashboard
python scripts/utils/vex_hub.py
```

---

## What VEX Needs to Improve

### Current Limitations:
1. **Long trades underperform** - Bias toward shorts (needs rebalancing)
2. **News events** - No economic calendar integration
3. **Multi-pair correlation** - SMT detection needs refinement
4. **Entry precision** - Sometimes enters too early/late in killzone

### Development Priorities:
1. Integrate Silver Bullet time windows as hard filters
2. Add economic calendar API for news avoidance
3. Improve HTF bias determination using weekly structure
4. Add position scaling (partials at 1R, 2R, etc.)
5. Implement trailing stops based on structure

---

## For the Next AI Agent

If you are reading this to continue VEX development:

1. **Study ICT methodology deeply** - Watch Michael Huddleston's YouTube videos. Understand WHY markets move, not just WHERE.

2. **Respect the codebase structure** - VexBrainV2 is the main brain. Don't create new brains—improve this one.

3. **Test before deploying** - Run backtests on historical data before live trading.

4. **Preserve the learning system** - Every trade should feed back into knowledge_manager.py.

5. **Maintain the journal** - Both VEX's journal and Ashton's (the human) journal must be updated.

6. **Remember the goal** - We're not trying to predict the market. We're trying to ALIGN with institutional order flow and ride their coattails.

---

## Credentials & Connections

**OANDA Demo Account:**
- Account ID: `101-001-21727967-002`
- API Key: Stored in environment variables
- Server: Practice (demo trading)

**Project Location:**
```
/Users/villain/Documents/transfer/ICT_WORK/ict_trainer/
```

---

## Final Note

VEX is more than code—it represents a partnership between human intuition (Ashton) and AI precision. The goal is not to replace the human trader but to augment their capabilities: instant pattern recognition, 24/7 market monitoring, emotion-free execution, and continuous learning.

Trade like the institutions. Hunt the liquidity. Respect the algorithm.

**— VEX, January 2026**
