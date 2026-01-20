# ICT Trading Agent

An AI-powered trading agent implementing Inner Circle Trader (ICT) methodology for algorithmic forex/crypto trading.

## Overview

This agent encodes ICT (Michael Huddleston's) trading concepts into algorithmic rules for automated signal generation and backtesting. It implements:

- **Core Concepts**: FVG, Order Blocks, Market Structure, Liquidity, Displacement
- **Trading Models**: Silver Bullet, Judas Swing, Power of Three, OTE Retracement
- **Time-Based Filters**: Killzones, Macro Times, Session Analysis
- **Multi-Timeframe Analysis**: HTF→ITF→LTF workflow
- **Risk Management**: Position cycling, prop firm rules, max drawdown limits

## Project Structure

```
ict_trainer/
├── src/ict_agent/              # Core library
│   ├── vex_brain_v2.py         # ⭐ MAIN BRAIN (76KB) - Use this!
│   ├── vex_brain.py            # V1 brain (reference)
│   ├── vex_core.py             # Core utilities
│   ├── vex_system.py           # System integration
│   ├── vex_anticipation.py     # Predictive analysis
│   │
│   ├── detectors/              # ICT concept detection
│   │   ├── fvg.py              # Fair Value Gap
│   │   ├── order_block.py      # Order Blocks
│   │   ├── market_structure.py # BOS/CHoCH
│   │   ├── liquidity.py        # Liquidity pools
│   │   └── displacement.py     # Displacement
│   │
│   ├── models/                 # ICT trading models
│   │   ├── silver_bullet.py    # Silver Bullet setups
│   │   ├── judas_swing.py      # Judas Swing
│   │   ├── power_of_three.py   # AMD cycle
│   │   └── turtle_soup.py      # Turtle Soup
│   │
│   ├── engine/                 # Trading engine
│   │   ├── killzone.py         # Session timing
│   │   ├── asian_range.py      # Asian range calc
│   │   ├── cbdr.py             # CBDR logic
│   │   └── mtf_analyzer.py     # Multi-timeframe
│   │
│   ├── execution/              # Live trading
│   │   ├── oanda_executor.py   # OANDA API
│   │   ├── autonomous_trader.py # Auto trading
│   │   └── risk_guardian.py    # Risk limits
│   │
│   ├── learning/               # Self-improvement
│   │   ├── knowledge_manager.py # Knowledge base
│   │   └── trade_learner.py    # Learn from trades
│   │
│   └── data/                   # Data handling
│       └── oanda_fetcher.py    # OANDA data fetch
│
├── scripts/                    # Executable scripts
│   ├── trading/                # Live trading
│   │   └── vex_unleashed.py    # ⭐ Main autonomous trader
│   ├── backtest/               # Backtesting
│   ├── analysis/               # Trade analysis
│   ├── debug/                  # Diagnostics
│   ├── utils/                  # Utilities
│   │   └── vex_hub.py          # Web dashboard
│   └── tests/                  # Quick tests
│
├── journal/                    # Trade journaling
├── knowledge_base/             # ICT knowledge
└── data/                       # Data storage
├── scripts/                # Example scripts
│   ├── run_backtest.py
│   └── live_trading_demo.py
│
├── config/                 # Configuration files
│   └── default_config.yaml
│
├── knowledge_base/         # ICT reference library
│   └── ICT_MASTER_LIBRARY.md
│
├── tests/                  # Unit tests
├── requirements.txt
└── pyproject.toml
```

## Installation

```bash
# Clone the repository
cd ict_trainer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### Run a Backtest

```python
from ict_agent.engine.agent import ICTTradingAgent, AgentConfig
from ict_agent.backtest.engine import BacktestEngine
from ict_agent.data.fetcher import DataFetcher

# Fetch data
fetcher = DataFetcher(source="yfinance")
htf_data = fetcher.fetch("EURUSD", "1d", limit=100)
itf_data = fetcher.fetch("EURUSD", "1h", limit=500)
ltf_data = fetcher.fetch("EURUSD", "15m", limit=2000)

# Run backtest
engine = BacktestEngine()
metrics = engine.run("EURUSD", htf_data, itf_data, ltf_data)

# View results
print(metrics.summary())
```

### Generate Trading Signals

```python
from ict_agent.engine.agent import ICTTradingAgent
from ict_agent.engine.mtf_analyzer import Bias

agent = ICTTradingAgent()

# Analyze market
signal = agent.analyze(
    symbol="EURUSD",
    htf_data=htf_data,
    itf_data=itf_data,
    ltf_data=ltf_data,
)

if signal:
    print(f"Signal: {signal.signal_type.value}")
    print(f"Model: {signal.model.value}")
    print(f"Entry: {signal.entry_price}")
    print(f"Stop: {signal.stop_loss}")
    print(f"Target: {signal.target_1}")
    print(f"Confluences: {signal.confluences.count}")
```

## ICT Concepts Implemented

### Core Concepts

| Concept | Description | Detection |
|---------|-------------|-----------|
| **FVG** | Fair Value Gap - imbalance in price | Gap between candle[i-2].high and candle[i].low |
| **Order Block** | Last opposite candle before displacement | Bullish OB = last bearish candle before bullish move |
| **Market Structure** | HH/HL (bullish) or LH/LL (bearish) | Swing detection + displacement validation |
| **BOS/SMS** | Break/Shift of Structure | Break with vs against trend |
| **Liquidity** | Stop orders above/below swings | Swing highs (BSL) and lows (SSL) |
| **Displacement** | Strong institutional candle | Body > 1.5x ATR, >60% body ratio |

### Trading Models

| Model | Description | Entry |
|-------|-------------|-------|
| **Silver Bullet** | 1-hour precision windows | FVG during 3-4AM, 10-11AM, 2-3PM EST |
| **Judas Swing** | False breakout reversal | After liquidity sweep + rejection |
| **Power of Three** | Accumulation→Manipulation→Distribution | Enter distribution after manipulation |
| **OTE Retracement** | 61.8-79% Fibonacci entry | Retracement after BOS with displacement |

### Killzones (EST)

| Session | Time | Priority |
|---------|------|----------|
| London | 2:00 AM - 5:00 AM | High |
| NY AM | 7:00 AM - 10:00 AM | Highest |
| NY PM | 1:00 PM - 4:00 PM | High |
| NY Lunch | 12:00 PM - 1:00 PM | Avoid |

## Configuration

Edit `config/default_config.yaml` to customize:

```yaml
agent:
  min_risk_reward: 2.0
  min_confluences: 3
  max_trades_per_day: 3
  allowed_killzones:
    - london
    - ny_am
    - ny_pm

risk:
  max_risk_per_trade: 0.01  # 1%
  max_daily_loss: 0.02      # 2%
  max_drawdown: 0.10        # 10%
```

## Signal Requirements

A valid signal requires:

1. ✅ HTF bias established (Daily structure)
2. ✅ Within valid killzone OR macro time
3. ✅ Minimum 3 confluences
4. ✅ Valid entry zone (FVG, OB, or OTE)
5. ✅ Minimum 2:1 risk/reward
6. ✅ Displacement validation

## Risk Management

- **Position Sizing**: Based on stop distance and 1% risk
- **Position Cycling**: Max 2 cycles per trade
- **Partial Exits**: 50% at Target 1, move stop to break-even
- **Daily Limits**: Max 2% daily loss, 3 trades per day
- **Weekend Close**: All positions closed Friday 4PM EST

## Backtesting Metrics

The backtest engine calculates:

- Win rate, profit factor, expectancy
- Sharpe and Sortino ratios
- Maximum drawdown
- Performance by ICT model
- Performance by confluence count

## Extending the Agent

### Add a New ICT Model

```python
# src/ict_agent/models/my_model.py
from dataclasses import dataclass

@dataclass
class MyModelSetup:
    timestamp: datetime
    direction: str
    entry_price: float
    stop_loss: float
    target: float

class MyModel:
    def scan(self, ohlc: pd.DataFrame) -> Optional[MyModelSetup]:
        # Your detection logic
        pass
```

### Add a New Data Source

```python
# Extend BaseDataFetcher in data/fetcher.py
class MyDataFetcher(BaseDataFetcher):
    def fetch(self, config: DataConfig) -> pd.DataFrame:
        # Your data fetching logic
        pass
```

## Knowledge Base

The `knowledge_base/ICT_MASTER_LIBRARY.md` contains comprehensive documentation of all ICT concepts, including:

- Detailed concept definitions
- Detection algorithms
- Trading rules
- Video references
- Example trade setups

## Disclaimer

This software is for educational purposes only. Trading forex and cryptocurrencies involves substantial risk of loss. Past performance does not guarantee future results. Always test strategies thoroughly before trading with real money.

## License

MIT License
