"""Data Fetcher Module

Fetches OHLCV data from various sources for backtesting and live trading.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Union
import pandas as pd


@dataclass
class DataConfig:
    """Configuration for data fetching"""
    symbol: str
    timeframe: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 1000


class BaseDataFetcher(ABC):
    """Abstract base class for data fetchers"""
    
    @abstractmethod
    def fetch(self, config: DataConfig) -> pd.DataFrame:
        """Fetch OHLCV data"""
        pass
    
    @abstractmethod
    def get_available_symbols(self) -> list[str]:
        """Get list of available symbols"""
        pass
    
    def _validate_ohlc(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and normalize OHLC data"""
        if df is None or getattr(df, "empty", True):
            raise ValueError("No OHLCV data returned")

        required_cols = ["open", "high", "low", "close"]
        
        df.columns = df.columns.str.lower()
        
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        if not isinstance(df.index, pd.DatetimeIndex):
            if "timestamp" in df.columns:
                df.set_index("timestamp", inplace=True)
            elif "date" in df.columns:
                df.set_index("date", inplace=True)
            df.index = pd.to_datetime(df.index)
        
        df.sort_index(inplace=True)
        
        return df


class YFinanceFetcher(BaseDataFetcher):
    """Fetch data from Yahoo Finance (forex pairs as XXX=X)"""
    
    FOREX_SYMBOLS = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "AUDUSD": "AUDUSD=X",
        "USDCAD": "USDCAD=X",
        "USDCHF": "USDCHF=X",
        "NZDUSD": "NZDUSD=X",
        "EURGBP": "EURGBP=X",
        "EURJPY": "EURJPY=X",
        "GBPJPY": "GBPJPY=X",
    }
    
    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1wk",
    }
    
    def fetch(self, config: DataConfig) -> pd.DataFrame:
        """Fetch data from Yahoo Finance"""
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("yfinance not installed. Run: pip install yfinance")
        
        symbol = self.FOREX_SYMBOLS.get(config.symbol.upper(), config.symbol)
        interval = self.TIMEFRAME_MAP.get(config.timeframe, "1h")
        
        if config.start_date and config.end_date:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=config.start_date,
                end=config.end_date,
                interval=interval,
            )
        else:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max", interval=interval)
            if config.limit:
                df = df.tail(config.limit)
        
        df = df.rename(columns={
            "Open": "open",
            "High": "high", 
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        
        return self._validate_ohlc(df)
    
    def get_available_symbols(self) -> list[str]:
        return list(self.FOREX_SYMBOLS.keys())


class CCXTFetcher(BaseDataFetcher):
    """Fetch data from crypto exchanges via CCXT"""
    
    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }
    
    def __init__(self, exchange: str = "binance"):
        self.exchange_id = exchange
        self._exchange = None
    
    @property
    def exchange(self):
        if self._exchange is None:
            try:
                import ccxt
            except ImportError:
                raise ImportError("ccxt not installed. Run: pip install ccxt")
            
            exchange_class = getattr(ccxt, self.exchange_id)
            self._exchange = exchange_class()
        return self._exchange
    
    def fetch(self, config: DataConfig) -> pd.DataFrame:
        """Fetch data from crypto exchange"""
        timeframe = self.TIMEFRAME_MAP.get(config.timeframe, "1h")
        
        since = None
        if config.start_date:
            since = int(config.start_date.timestamp() * 1000)
        
        ohlcv = self.exchange.fetch_ohlcv(
            config.symbol,
            timeframe=timeframe,
            since=since,
            limit=config.limit,
        )
        
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        
        return self._validate_ohlc(df)
    
    def get_available_symbols(self) -> list[str]:
        self.exchange.load_markets()
        return list(self.exchange.symbols)


class CSVFetcher(BaseDataFetcher):
    """Fetch data from local CSV files"""
    
    def __init__(self, data_dir: str = "data/"):
        self.data_dir = data_dir
    
    def fetch(self, config: DataConfig) -> pd.DataFrame:
        """Fetch data from CSV file"""
        from pathlib import Path
        
        file_path = Path(self.data_dir) / f"{config.symbol}_{config.timeframe}.csv"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")
        
        df = pd.read_csv(file_path)

        # TradingView exports commonly use a first column like "time" or "Date".
        # Allow either an explicit time column or the first column as index.
        df.columns = df.columns.str.strip()

        time_col = None
        for candidate in ("time", "Time", "date", "Date", "datetime", "Datetime", "timestamp", "Timestamp"):
            if candidate in df.columns:
                time_col = candidate
                break

        if time_col is not None:
            df[time_col] = _coerce_datetime_series(df[time_col])
            df.set_index(time_col, inplace=True)
        else:
            # Fall back to first column as an index
            first_col = df.columns[0]
            df[first_col] = _coerce_datetime_series(df[first_col])
            df.set_index(first_col, inplace=True)
        
        if config.start_date:
            df = df[df.index >= config.start_date]
        if config.end_date:
            df = df[df.index <= config.end_date]
        if config.limit:
            df = df.tail(config.limit)
        
        return self._validate_ohlc(df)
    
    def get_available_symbols(self) -> list[str]:
        from pathlib import Path
        
        data_path = Path(self.data_dir)
        if not data_path.exists():
            return []
        
        symbols = set()
        for f in data_path.glob("*.csv"):
            parts = f.stem.split("_")
            if parts:
                symbols.add(parts[0])
        
        return list(symbols)


class DataFetcher:
    """Unified data fetcher with multiple source support"""
    
    def __init__(self, source: str = "yfinance", **kwargs):
        self.source = source
        
        if source == "yfinance":
            self.fetcher = YFinanceFetcher()
        elif source == "ccxt":
            self.fetcher = CCXTFetcher(**kwargs)
        elif source == "csv":
            self.fetcher = CSVFetcher(**kwargs)
        else:
            raise ValueError(f"Unknown data source: {source}")
    
    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """Fetch OHLCV data"""
        config = DataConfig(
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return self.fetcher.fetch(config)
    
    def fetch_multi_timeframe(
        self,
        symbol: str,
        timeframes: list[str],
        **kwargs,
    ) -> dict[str, pd.DataFrame]:
        """Fetch data for multiple timeframes"""
        data = {}
        for tf in timeframes:
            data[tf] = self.fetch(symbol, tf, **kwargs)
        return data
    
    def get_available_symbols(self) -> list[str]:
        return self.fetcher.get_available_symbols()


def _coerce_datetime_series(series: pd.Series) -> pd.Series:
    """Parse TradingView-like datetime columns.

    Supports:
    - ISO datetime strings
    - Unix timestamps in seconds or milliseconds
    """
    # numeric timestamps
    if pd.api.types.is_numeric_dtype(series):
        # Heuristic: ms timestamps are usually >= 1e12
        unit = "ms" if series.dropna().astype("int64").abs().max() >= 1_000_000_000_000 else "s"
        return pd.to_datetime(series, unit=unit, utc=False)

    # string/object timestamps
    return pd.to_datetime(series, errors="coerce")
