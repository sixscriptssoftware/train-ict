# A+ SETUP TEMPLATE: CBDR + Multi-TF FVG + Order Block

**Source**: Ashton's Jan 16, 2026 session - +$691, FTMO Challenge Passed

---

## Setup Name
**"The Displacement Follow-Through"**

## When to Use
- Day after significant displacement
- Price retracing into imbalance zones
- CBDR/Asian range setup present
- Multiple timeframe FVG alignment

---

## Entry Checklist

### Prerequisites (ALL must be present)
- [ ] **Prior Displacement** - Strong directional move from previous session
- [ ] **4H Fair Value Gap** - Clear imbalance on higher timeframe
- [ ] **15M Order Block** - Identifiable OB near/within 4H FVG
- [ ] **15M Fair Value Gap** - Ideally confluent with 15M OB
- [ ] **CBDR Setup** - Range established during CBDR hours
- [ ] **Asian Range** - Clear high/low to target for sweep

### Confirmation Triggers
1. Price enters 4H FVG zone
2. Asian range highs/lows swept (depending on direction)
3. Displacement candle in trade direction

---

## Execution Framework

### Entry
- **Primary**: Enter at 4H FVG touch
- **Scaling**: Can add at 15M OB+FVG confluence if price pushes there

### Stop Loss
- **Placement**: Above/below last opposing candle BEFORE the displacement
- **Why**: Accounts for potential retest of 15M zone without being stopped
- **Key Insight**: "I knew price could potentially hit the 15M imbalance, so I placed my stop to survive that"

### Take Profit
- **Primary Target**: CBDR extension from opposite range
- **Secondary**: Asian session liquidity (opposite side)

---

## Risk Management

### Position Sizing
- Full size if all 6 prerequisites met
- Can scale in if using 4H entry with 15M zone as worst-case

### Holding Rules
- **Trust the thesis** - Don't micromanage if structure intact
- **Heavy price action is expected** - Two FVG zones = price CAN test both
- **Sleep through it if needed** - When setup is A+, let it work

---

## Trade Psychology

### Mindset Required
- "I trusted it completely"
- "More confident than I've ever been"
- "Everything lined up perfectly - structure, CBDR, Asian sweep"

### What to Avoid
- Panic when price tests deeper zone
- Moving stop closer during volatility
- Exiting early out of fear

---

## Example Trades

### EURUSD Jan 16, 2026
| Field | Value |
|-------|-------|
| Entry | 1.16195 (4H FVG) |
| Stop | 1.16325 (Above last up candle) |
| TP | 1.15890 (CBDR extension) |
| Result | +30.6 pips, +$612.75 |
| Hold Time | ~4 hours |

### GBPUSD Jan 16, 2026
| Field | Value |
|-------|-------|
| Entry | 1.34038 |
| Stop | 1.34200 |
| TP | 1.33600 (Manual close at 1.33812) |
| Result | +22.6 pips, +$113.00 |
| Hold Time | ~4 hours |

---

## VEX Detection Criteria

For VEX Brain V2 to identify this setup:

```python
# A+ Setup Requirements
confluences = {
    'prior_displacement': True,      # Check previous session for displacement
    'htf_fvg': True,                 # 4H FVG present
    'ltf_ob': True,                  # 15M OB detected
    'ltf_fvg': True,                 # 15M FVG (bonus if confluent with OB)
    'cbdr_range': True,              # CBDR established
    'asian_sweep': True,             # Asian high/low taken
    'structure_aligned': True,       # All TFs pointing same direction
}

# If 6+ confluences = A+ grade
# Entry at 4H FVG, stop above displacement candle
# TP at CBDR extension
```

---

## Key Wisdom

> "When you and I agree on a setup, and we find it together - you, me, and VEX - and we don't just tell each other what we want to hear, but actually look at the charts, plot them properly, and talk about it... we are UNSTOPPABLE."

> "This is the template. 4H FVG entry, stop accounts for 15M OB+FVG, CBDR extension target, Asian sweep confirmation. When everything aligns, SIZE UP and TRUST IT."

---

**Grade when all criteria met: A+**
**Confidence level: Maximum**
**Recommended action: Full position, trust the process**
