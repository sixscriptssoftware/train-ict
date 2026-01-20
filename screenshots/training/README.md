# Training Screenshots

Chart screenshots linked to trade setups in `data/training/`.

## Structure

```
screenshots/training/
├── positive/    # Winning trades / valid setups
│   └── {trade_id}.png
└── negative/    # Failed trades / invalid setups
    └── {trade_id}.png
```

## Naming Convention

Screenshots must match the trade ID exactly:
- Trade: `data/training/positive/2022-02-18_NY_EURUSD_Achilles_001.json`
- Screenshot: `screenshots/training/positive/2022-02-18_NY_EURUSD_Achilles_001.png`

## Linking in Trade JSON

```json
"references": {
  "screenshots": ["screenshots/training/positive/2022-02-18_NY_EURUSD_Achilles_001.png"],
  "image_ids": ["2022-02-18_NY_EURUSD_Achilles_001.png"]
}
```

## Multiple Screenshots

If a trade has multiple timeframes or entry/exit charts:

```json
"screenshots": [
  "screenshots/training/positive/2022-02-18_NY_EURUSD_Achilles_001_H1.png",
  "screenshots/training/positive/2022-02-18_NY_EURUSD_Achilles_001_M15.png",
  "screenshots/training/positive/2022-02-18_NY_EURUSD_Achilles_001_entry.png"
]
```
