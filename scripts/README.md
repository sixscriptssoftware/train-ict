# VEX Scripts

Organized scripts for the VEX ICT Trading System.

## 📁 Folder Structure

### `/trading` - Live Trading & Execution
Scripts for live market operations and trade execution.

| Script | Purpose |
|--------|---------|
| `vex_unleashed.py` | **MAIN** - Full autonomous trading mode |
| `vex_hub.py` | Web dashboard for monitoring |
| `vex_scan.py` | Market scanner for setups |
| `vex_trade.py` | Single trade execution |
| `vex_check_account.py` | Account status check |
| `vex_open_trades.py` | View open positions |
| `close_all_trades.py` | Emergency close all |
| `live_scanner.py` | Real-time market scanner |
| `live_babysitter.py` | Trade management/monitoring |

### `/analysis` - Backtesting & Analysis
Scripts for historical analysis and strategy testing.

| Script | Purpose |
|--------|---------|
| `vex_backtest.py` | Main backtesting engine |
| `vex_backtest_detailed.py` | Detailed backtest with logs |
| `vex_chart_analysis.py` | Chart analysis tools |
| `analyze_gold.py` | Gold-specific analysis |
| `dxy_correlation.py` | DXY correlation study |

### `/testing` - Development & Testing
Scripts for testing detectors and system components.

| Script | Purpose |
|--------|---------|
| `verify_detectors.py` | Verify all ICT detectors |
| `test_brain_v2.py` | Test VEX Brain V2 |
| `test_all_detectors.py` | Comprehensive detector test |

### `/utilities` - Helper Scripts
Utility scripts for maintenance and data management.

| Script | Purpose |
|--------|---------|
| `vex_self_learn.py` | Self-learning from trades |
| `extract_docx.py` | Extract content from docs |
| `health_check.py` | System health check |

### `/archive` - Deprecated Scripts
Old scripts kept for reference.

---

## Quick Start

```bash
# Run VEX Unleashed (autonomous trading)
python scripts/trading/vex_unleashed.py

# Run web dashboard
python scripts/trading/vex_hub.py

# Test all detectors
python scripts/testing/verify_detectors.py

# Run backtest
python scripts/analysis/vex_backtest.py
```
