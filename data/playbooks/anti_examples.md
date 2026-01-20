# Anti-Examples Database
# Trades/setups that LOOKED valid but were NOT
# Critical for training AI to recognize what to AVOID

## Purpose
The AI needs negative examples to learn edges. Without anti-patterns:
- Model overfits to "see OB = trade"
- No understanding of context failures
- Can't distinguish good OB from bad OB

---

## Anti-Pattern Categories

### 1. False Order Block
**Pattern ID:** `false_ob`

| Field | Description |
|-------|-------------|
| looks_like | Order block formed, price approaching |
| problem | No displacement after OB - just consolidation |
| key_miss | Real OBs are FOLLOWED by displacement |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "EURUSD",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "false_ob",
    "looked_like": "Last down candle before move up on 15M",
    "problem": "Move up was only 10 pips, no real displacement, just choppy price action",
    "lesson": "OB requires DISPLACEMENT (3+ strong candles) to validate"
  }
}
```

---

### 2. Chased Move
**Pattern ID:** `chased_move`

| Field | Description |
|-------|-------------|
| looks_like | Saw the move, wanted to catch it |
| problem | Entered without return to PD array |
| key_miss | ICT = enter on RETRACE, not on breakout |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "GBPUSD",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "chased_move",
    "looked_like": "Strong breakout of Asia high, clear direction",
    "problem": "Entered at extended price, no FVG/OB retrace, got stopped when price pulled back",
    "lesson": "If you miss the entry, wait for retrace or next setup"
  }
}
```

---

### 3. Asia Breakout Trap
**Pattern ID:** `asia_breakout_trap`

| Field | Description |
|-------|-------------|
| looks_like | Asia range broken, momentum building |
| problem | Often retraces during London manipulation |
| key_miss | Asia breakouts need London confirmation |

**Example:**
```json
{
  "date": "2026-01-XX", 
  "pair": "EURUSD",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "asia_breakout_trap",
    "looked_like": "Clean break of Asia high at 1:30 AM EST",
    "problem": "London open at 2 AM reversed it, Judas swing back into range",
    "lesson": "Don't trade Asia breakouts - wait for London to confirm or reject"
  }
}
```

---

### 4. Mitigated FVG
**Pattern ID:** `fvg_already_mitigated`

| Field | Description |
|-------|-------------|
| looks_like | Price at FVG level, should bounce |
| problem | FVG was already touched - it's spent |
| key_miss | FVG = one-time use, check if virgin |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "USDJPY",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "fvg_already_mitigated",
    "looked_like": "Price returning to 4H FVG, expecting bounce",
    "problem": "That FVG was touched 2 days ago - already mitigated",
    "lesson": "Always check if FVG is UNMITIGATED before trading it"
  }
}
```

---

### 5. Fighting HTF
**Pattern ID:** `fighting_htf`

| Field | Description |
|-------|-------------|
| looks_like | LTF setup looks clean |
| problem | It's against the HTF bias |
| key_miss | LTF must PROMOTE HTF, never oppose |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "GBPUSD",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "fighting_htf",
    "looked_like": "Nice 5M OB for short entry",
    "problem": "Daily and 4H are bullish, this is counter-trend",
    "lesson": "LTF shorts only when HTF bearish - never fight the trend"
  }
}
```

---

### 6. News Gamble
**Pattern ID:** `news_gamble`

| Field | Description |
|-------|-------------|
| looks_like | Setup valid, happens to be before news |
| problem | News creates unpredictable volatility |
| key_miss | No entries 30 min before high-impact |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "EURUSD",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "news_gamble",
    "looked_like": "Perfect OB entry 15 minutes before CPI",
    "problem": "CPI spiked both directions, stopped out before real move",
    "lesson": "No entries within 30 min of high-impact news - wait for aftermath"
  }
}
```

---

### 7. Revenge Trade
**Pattern ID:** `revenge_trade`

| Field | Description |
|-------|-------------|
| looks_like | Similar setup to the one that just stopped out |
| problem | Emotional re-entry, not structural |
| key_miss | After stop = wait for NEW setup, not same one |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "EURUSD", 
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "revenge_trade",
    "looked_like": "Price came back to same OB after stopping me out",
    "problem": "Structure was broken, OB was invalidated, I was chasing losses",
    "lesson": "If stop hit = structure failed. Need completely NEW setup"
  }
}
```

---

### 8. Overtrading
**Pattern ID:** `overtrading`

| Field | Description |
|-------|-------------|
| looks_like | Multiple setups in same session |
| problem | Forcing trades that don't exist |
| key_miss | Quality > quantity |

**Example:**
```json
{
  "date": "2026-01-XX",
  "pair": "EURUSD",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "overtrading",
    "looked_like": "Took 4 trades in NY session trying to recover",
    "problem": "None had full confluence, was forcing action",
    "lesson": "One good trade > five mediocre trades. Walk away after 2 losses"
  }
}
```

---

## How to Use This Data

### For Training
1. Label these as `is_valid_setup: false`
2. Include in training set alongside valid examples
3. Model learns: "these patterns = no trade"

### For Rules Engine
```python
def validate_setup(setup):
    # Check for anti-patterns
    if setup.fvg and fvg_already_mitigated(setup.fvg):
        return False, "fvg_already_mitigated"
    
    if setup.entry_tf in ['5M', '1M'] and htf_bias != setup.direction:
        return False, "fighting_htf"
    
    if news_in_next_30_min():
        return False, "news_gamble"
    
    # ... more checks
    return True, None
```

### For Self-Review
After each loss, ask:
1. Was this an anti-pattern?
2. Which one?
3. What was the tell I missed?

---

## Template for New Anti-Example

```json
{
  "date": "YYYY-MM-DD",
  "time": "HH:MM EST",
  "pair": "XXXYYY",
  "direction": "LONG/SHORT",
  "is_valid_setup": false,
  "anti_pattern": {
    "pattern_type": "<from enum>",
    "looked_like": "<what made it seem valid>",
    "problem": "<what was actually wrong>",
    "lesson": "<what to remember next time>"
  },
  "context": {
    "htf_bias": "<bullish/bearish/neutral>",
    "session": "<asia/london/ny_am/ny_pm>",
    "vol_regime": "<high/normal/low>",
    "news_context": "<if relevant>"
  },
  "outcome": {
    "result": "loss",
    "pnl_pips": -XX
  },
  "screenshots": ["path/to/chart.png"]
}
```
