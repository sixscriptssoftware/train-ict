"""Data Preprocessor Module

Prepares OHLCV data for ICT analysis.
"""

from typing import Optional
import pandas as pd
import numpy as np


class DataPreprocessor:
    """
    Preprocesses OHLCV data for ICT trading analysis.
    
    Features:
    - Timeframe conversion
    - Missing data handling
    - Session filtering
    - Feature engineering (ATR, ranges, etc.)
    """
    
    def __init__(self):
        pass
    
    def preprocess(
        self,
        df: pd.DataFrame,
        fill_gaps: bool = True,
        add_features: bool = True,
    ) -> pd.DataFrame:
        """
        Main preprocessing pipeline.
        
        Args:
            df: Raw OHLCV DataFrame
            fill_gaps: Whether to fill missing data
            add_features: Whether to add derived features
        
        Returns:
            Preprocessed DataFrame
        """
        df = df.copy()
        
        df = self._ensure_columns(df)
        
        if fill_gaps:
            df = self._fill_gaps(df)
        
        if add_features:
            df = self._add_features(df)
        
        return df
    
    def _ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all required columns exist"""
        required = ["open", "high", "low", "close"]
        
        df.columns = df.columns.str.lower()
        
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        if "volume" not in df.columns:
            df["volume"] = 0
        
        return df
    
    def _fill_gaps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill missing data gaps"""
        df = df.ffill()
        
        for col in ["open", "high", "low", "close"]:
            if df[col].isna().any():
                df[col] = df[col].bfill()
        
        return df
    
    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add derived features useful for ICT analysis"""
        df["range"] = df["high"] - df["low"]
        
        df["body"] = abs(df["close"] - df["open"])
        
        df["body_ratio"] = df["body"] / df["range"].replace(0, np.nan)
        
        df["is_bullish"] = df["close"] > df["open"]
        df["is_bearish"] = df["close"] < df["open"]
        
        df["upper_wick"] = df["high"] - df[["open", "close"]].max(axis=1)
        df["lower_wick"] = df[["open", "close"]].min(axis=1) - df["low"]
        
        df["atr_14"] = self._calculate_atr(df, period=14)
        
        df["session_high"] = df.groupby(df.index.date)["high"].cummax()
        df["session_low"] = df.groupby(df.index.date)["low"].cummin()
        
        df["midpoint"] = (df["high"] + df["low"]) / 2
        
        return df
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df["high"]
        low = df["low"]
        close = df["close"].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def resample_timeframe(
        self,
        df: pd.DataFrame,
        target_timeframe: str,
    ) -> pd.DataFrame:
        """
        Resample data to a different timeframe.
        
        Args:
            df: Source DataFrame
            target_timeframe: Target timeframe (e.g., '1H', '4H', '1D')
        
        Returns:
            Resampled DataFrame
        """
        resampled = df.resample(target_timeframe).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        })
        
        return resampled.dropna()
    
    def filter_trading_hours(
        self,
        df: pd.DataFrame,
        start_hour: int = 7,
        end_hour: int = 17,
    ) -> pd.DataFrame:
        """Filter data to only include trading hours"""
        mask = (df.index.hour >= start_hour) & (df.index.hour < end_hour)
        return df[mask]
    
    def add_session_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add trading session labels"""
        df = df.copy()
        
        def get_session(hour: int) -> str:
            if 19 <= hour or hour < 2:
                return "asia"
            elif 2 <= hour < 7:
                return "london"
            elif 7 <= hour < 12:
                return "ny_am"
            elif 12 <= hour < 13:
                return "ny_lunch"
            elif 13 <= hour < 17:
                return "ny_pm"
            else:
                return "off_hours"
        
        df["session"] = df.index.hour.map(get_session)
        return df
    
    def calculate_daily_range(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate daily high-low range metrics"""
        df = df.copy()
        
        daily = df.resample("D").agg({
            "high": "max",
            "low": "min",
            "open": "first",
            "close": "last",
        })
        daily["daily_range"] = daily["high"] - daily["low"]
        daily["adr_5"] = daily["daily_range"].rolling(5).mean()
        daily["adr_10"] = daily["daily_range"].rolling(10).mean()
        
        df["daily_high"] = df.index.date
        df["daily_high"] = df["daily_high"].map(
            daily["high"].to_dict()
        )
        df["daily_low"] = df.index.date
        df["daily_low"] = df["daily_low"].map(
            daily["low"].to_dict()
        )
        
        return df
    
    def prepare_for_backtest(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.7,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Split data for backtesting.
        
        Returns:
            Tuple of (train_data, test_data)
        """
        split_idx = int(len(df) * train_ratio)
        
        train = df.iloc[:split_idx].copy()
        test = df.iloc[split_idx:].copy()
        
        return train, test
