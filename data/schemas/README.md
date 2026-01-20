# ICT Trade Setup Schemas

## Overview

This directory contains the comprehensive JSON schemas for recording ICT trade setups. Both **positive** (valid trades) and **negative** (failed/bad setups) use the same master schema, enabling the AI to learn what TO trade and what NOT to trade.

## Files

| File | Purpose |
|------|---------|
| `ict_trade_setup.schema.json` | JSON Schema (2020-12) for validation |
| `trade_object.json` | Legacy simple schema (deprecated) |
| `ict_ontology.yaml` | ICT vocabulary definitions |
| `templates/positive_setup_template.json` | Example of a winning trade |
| `templates/negative_setup_template.json` | Example of a failed trade |
| `templates/blank_template.json` | Empty template to copy |

## Quick Start

1. Copy `templates/blank_template.json`
2. Rename: `YYYY-MM-DD_SESSION_PAIR_SETUP_NUM.json`
3. Fill in all fields
4. Set `labels.example_type` to `"positive"` or `"negative"`
5. If negative, fill in `failure_analysis` section

## Schema Structure

```
├── id                    # Unique identifier
├── meta                  # Author, version, tags
├── market                # Pair, instrument type, broker
├── references            # Links to videos, images, charts
├── time                  # Date, session, killzone, TF hierarchy
├── context               # Day type, vol regime, news, HTF bias
│   ├── range             # Prior day, Asia, terminus levels
│   └── liquidity_map     # BSL/SSL levels
├── pd_arrays             # PD arrays identified
│   ├── htf_order_blocks
│   ├── ltf_order_blocks
│   ├── fair_value_gaps
│   ├── extensions        # CBDR projections
│   └── discount_premium  # Entry zone analysis
├── setup                 # The trade setup
│   ├── bias              # long/short
│   ├── setup_type        # OB_FVG_retrace, Judas_into_OB, etc.
│   ├── pattern_story     # Structure, objective, timing
│   └── confirmation      # BOS/CHoCH, displacement, entry model
├── execution             # Entry, stop, targets
├── management            # Partials, BE, outcome
├── reasoning             # why_here, why_now, invalidation
├── failure_analysis      # ONLY for negative examples
└── labels                # quality_tag, example_type
```

## Example Types

### Positive Example
```json
{
  "labels": {
    "quality_tag": "A_plus",
    "example_type": "positive",
    "teaching_focus": ["multi_tf_alignment", "Judas_swing_usage"]
  }
}
```

### Negative Example
```json
{
  "labels": {
    "quality_tag": "C",
    "example_type": "negative",
    "failure_category": "structural",
    "teaching_focus": ["no_real_displacement", "chasing_price"]
  },
  "failure_analysis": {
    "root_cause": ["misidentified_order_block"],
    "structural_mistakes": ["no_HTF_OB_confluence"],
    "behavioral_mistakes": ["FOMO_after_missing_clean_setup"],
    "lesson_summary": "Not every reaction is an OB. Require displacement.",
    "lesson_label": "do_not_chase_after_liquidity_is_taken"
  }
}
```

## Quality Tags

| Tag | Meaning |
|-----|---------|
| `A_plus` | Perfect setup, all confluences aligned |
| `A` | Strong setup, minor imperfections |
| `B` | Acceptable setup, some compromises |
| `C` | Weak setup, significant issues (usually negative) |

## Failure Categories

| Category | Description |
|----------|-------------|
| `structural` | Misread structure (fake OB, no displacement) |
| `behavioral` | Psychology issues (FOMO, revenge, overtrading) |
| `risk` | Position sizing, stop placement errors |
| `news` | News-related failure |
| `random` | Market randomness, unforeseeable |

## Validation

Validate a setup file:
```bash
# Using jsonschema (pip install jsonschema)
python -c "
import json
from jsonschema import validate
schema = json.load(open('ict_trade_setup.schema.json'))
data = json.load(open('your_setup.json'))
validate(data, schema)
print('Valid!')
"
```

## ID Format

`{date}_{session}_{pair}_{setup_type}_{number}`

Examples:
- `2026-01-20_LON_EURUSD_OBFVG_001`
- `2026-01-20_NY_GBPUSD_Judas_001`
- `2026-01-20_LON_EURUSD_fake_OB_001` (negative example)

## Training Data Location

Save completed setups to:
```
data/training/
├── positive/
│   ├── 2026-01-20_LON_EURUSD_OBFVG_001.json
│   └── ...
└── negative/
    ├── 2026-01-20_LON_EURUSD_fake_OB_001.json
    └── ...
```
