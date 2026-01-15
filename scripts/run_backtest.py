"""
Example: Running a Backtest with the ICT Trading Agent

This script demonstrates how to:
1. Fetch historical data
2. Configure the trading agent
3. Run a backtest
4. Analyze results
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ict_agent.engine.agent import ICTTradingAgent, AgentConfig
from ict_agent.engine.signal_generator import ModelType
from ict_agent.engine.killzone import Killzone
from ict_agent.data.fetcher import DataFetcher
from ict_agent.data.preprocessor import DataPreprocessor
from ict_agent.backtest.engine import BacktestEngine, BacktestConfig


def main():
    parser = argparse.ArgumentParser(description="Run ICT agent backtest")
    parser.add_argument(
        "--source",
        default="csv",
        choices=["csv", "yfinance", "ccxt"],
        help="Data source. For TradingView, export CSV and use --source csv.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing CSV files when --source csv",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ICT Trading Agent - Backtest Example")
    print("=" * 60)
    
    symbol = "EURUSD"
    
    print(f"\n1. Fetching data for {symbol}...")
    
    fetcher_kwargs = {}
    if args.source == "csv":
        fetcher_kwargs["data_dir"] = args.data_dir
    fetcher = DataFetcher(source=args.source, **fetcher_kwargs)
    preprocessor = DataPreprocessor()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    try:
        htf_data = fetcher.fetch(symbol, "1d", start_date=start_date, end_date=end_date)
        itf_data = fetcher.fetch(symbol, "1h", start_date=start_date, end_date=end_date)
        ltf_data = fetcher.fetch(symbol, "15m", start_date=start_date, end_date=end_date)
        
        htf_data = preprocessor.preprocess(htf_data)
        itf_data = preprocessor.preprocess(itf_data)
        ltf_data = preprocessor.preprocess(ltf_data)
        
        print(f"   HTF (Daily): {len(htf_data)} bars")
        print(f"   ITF (1H):    {len(itf_data)} bars")
        print(f"   LTF (15M):   {len(ltf_data)} bars")
        
    except Exception as e:
        print(f"   Error fetching data: {e}")
        print("   Refusing to continue without real market data.")
        print("   If you want TradingView data: export chart data as CSV and place files in ./data")
        print("   Expected filenames: EURUSD_1d.csv, EURUSD_1h.csv, EURUSD_15m.csv")
        return 2
    
    print("\n2. Configuring agent...")
    
    agent_config = AgentConfig(
        symbols=[symbol],
        min_risk_reward=2.0,
        min_confluences=3,
        min_confidence=0.6,
        max_trades_per_day=3,
        allowed_killzones=[
            Killzone.LONDON,
            Killzone.NY_AM,
            Killzone.NY_PM,
        ],
        allowed_models=[
            ModelType.SILVER_BULLET,
            ModelType.JUDAS_SWING,
            ModelType.OTE_RETRACEMENT,
            ModelType.FVG_REBALANCE,
        ],
    )
    
    backtest_config = BacktestConfig(
        initial_capital=10000.0,
        risk_per_trade=0.01,
        commission_pips=0.5,
        slippage_pips=0.5,
        max_trades_per_day=3,
    )
    
    print("   Agent configured with ICT rules")
    print(f"   - Min R:R: {agent_config.min_risk_reward}")
    print(f"   - Min confluences: {agent_config.min_confluences}")
    print(f"   - Models: {[m.value for m in agent_config.allowed_models]}")
    
    print("\n3. Running backtest...")
    
    engine = BacktestEngine(
        config=backtest_config,
        agent_config=agent_config,
    )
    
    metrics = engine.run(
        symbol=symbol,
        htf_data=htf_data,
        itf_data=itf_data,
        ltf_data=ltf_data,
    )
    
    print("\n4. Results:")
    print(metrics.summary())
    
    if metrics.model_performance:
        print("\n5. Performance by ICT Model:")
        for model, stats in metrics.model_performance.items():
            print(f"   {model}:")
            print(f"      Trades: {stats['trades']}")
            print(f"      Win Rate: {stats['win_rate']*100:.1f}%")
            print(f"      Total P&L: ${stats['total_pnl']:+,.2f}")
    
    if metrics.confluence_performance:
        print("\n6. Performance by Confluence Count:")
        for conf, stats in sorted(metrics.confluence_performance.items()):
            print(f"   {conf} confluences: {stats['trades']} trades, "
                  f"{stats['win_rate']*100:.1f}% WR, ${stats['total_pnl']:+,.2f}")
    
    return 0


def create_sample_data():
    """Create sample OHLCV data for demonstration"""
    import pandas as pd
    import numpy as np
    
    np.random.seed(42)
    
    periods_15m = 2000
    dates_15m = pd.date_range(end=datetime.now(), periods=periods_15m, freq="15min")
    
    base_price = 1.0850
    returns = np.random.randn(periods_15m) * 0.0003
    prices = base_price + np.cumsum(returns)
    
    ltf_data = pd.DataFrame({
        "open": prices,
        "high": prices + np.abs(np.random.randn(periods_15m) * 0.0005),
        "low": prices - np.abs(np.random.randn(periods_15m) * 0.0005),
        "close": prices + np.random.randn(periods_15m) * 0.0002,
        "volume": np.random.randint(1000, 10000, periods_15m),
    }, index=dates_15m)
    
    itf_data = ltf_data.resample("1h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    
    htf_data = ltf_data.resample("1D").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    
    return htf_data, itf_data, ltf_data


if __name__ == "__main__":
    raise SystemExit(main())
