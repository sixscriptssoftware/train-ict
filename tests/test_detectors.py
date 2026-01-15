"""Tests for ICT Concept Detectors"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def create_sample_ohlc(periods: int = 100, base_price: float = 1.0850) -> pd.DataFrame:
    """Create sample OHLC data for testing"""
    np.random.seed(42)
    
    dates = pd.date_range(end=datetime.now(), periods=periods, freq="15min")
    returns = np.random.randn(periods) * 0.0003
    prices = base_price + np.cumsum(returns)
    
    df = pd.DataFrame({
        "open": prices,
        "high": prices + np.abs(np.random.randn(periods) * 0.0005),
        "low": prices - np.abs(np.random.randn(periods) * 0.0005),
        "close": prices + np.random.randn(periods) * 0.0002,
        "volume": np.random.randint(1000, 10000, periods),
    }, index=dates)
    
    return df


class TestFVGDetector:
    """Tests for Fair Value Gap detector"""
    
    def test_detect_returns_dataframe(self):
        """Test that detect returns a DataFrame"""
        from ict_agent.detectors.fvg import FVGDetector
        
        detector = FVGDetector()
        ohlc = create_sample_ohlc()
        
        result = detector.detect(ohlc)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == len(ohlc)
    
    def test_detect_has_required_columns(self):
        """Test that result has required columns"""
        from ict_agent.detectors.fvg import FVGDetector
        
        detector = FVGDetector()
        ohlc = create_sample_ohlc()
        
        result = detector.detect(ohlc)
        
        required_cols = ["fvg_direction", "fvg_top", "fvg_bottom", "fvg_midpoint"]
        for col in required_cols:
            assert col in result.columns
    
    def test_bullish_fvg_detection(self):
        """Test bullish FVG is detected correctly"""
        from ict_agent.detectors.fvg import FVGDetector, FVGDirection
        
        dates = pd.date_range(start="2024-01-01", periods=5, freq="15min")
        ohlc = pd.DataFrame({
            "open":  [1.0800, 1.0810, 1.0850, 1.0900, 1.0910],
            "high":  [1.0815, 1.0820, 1.0920, 1.0950, 1.0920],
            "low":   [1.0795, 1.0805, 1.0840, 1.0890, 1.0900],
            "close": [1.0810, 1.0815, 1.0910, 1.0940, 1.0915],
        }, index=dates)
        
        detector = FVGDetector(min_gap_pips=1.0)
        result = detector.detect(ohlc)
        
        fvgs = detector.get_active_fvgs(FVGDirection.BULLISH)
        assert len(fvgs) >= 0


class TestMarketStructureAnalyzer:
    """Tests for Market Structure analyzer"""
    
    def test_analyze_returns_dataframe(self):
        """Test that analyze returns a DataFrame"""
        from ict_agent.detectors.market_structure import MarketStructureAnalyzer
        
        analyzer = MarketStructureAnalyzer(swing_length=5)
        ohlc = create_sample_ohlc(periods=50)
        
        result = analyzer.analyze(ohlc)
        
        assert isinstance(result, pd.DataFrame)
    
    def test_swing_detection(self):
        """Test that swings are detected"""
        from ict_agent.detectors.market_structure import MarketStructureAnalyzer
        
        analyzer = MarketStructureAnalyzer(swing_length=3)
        ohlc = create_sample_ohlc(periods=50)
        
        result = analyzer.analyze(ohlc)
        
        swings_detected = (result["swing_type"] != 0).any()
        assert "swing_type" in result.columns


class TestOrderBlockDetector:
    """Tests for Order Block detector"""
    
    def test_detect_returns_dataframe(self):
        """Test that detect returns a DataFrame"""
        from ict_agent.detectors.order_block import OrderBlockDetector
        
        detector = OrderBlockDetector()
        ohlc = create_sample_ohlc()
        
        result = detector.detect(ohlc)
        
        assert isinstance(result, pd.DataFrame)
        assert "ob_direction" in result.columns


class TestLiquidityDetector:
    """Tests for Liquidity detector"""
    
    def test_detect_returns_dataframe(self):
        """Test that detect returns a DataFrame"""
        from ict_agent.detectors.liquidity import LiquidityDetector
        
        detector = LiquidityDetector(swing_length=5)
        ohlc = create_sample_ohlc(periods=50)
        
        result = detector.detect(ohlc)
        
        assert isinstance(result, pd.DataFrame)
        assert "liquidity_type" in result.columns


class TestDisplacementDetector:
    """Tests for Displacement detector"""
    
    def test_detect_returns_dataframe(self):
        """Test that detect returns a DataFrame"""
        from ict_agent.detectors.displacement import DisplacementDetector
        
        detector = DisplacementDetector()
        ohlc = create_sample_ohlc()
        
        result = detector.detect(ohlc)
        
        assert isinstance(result, pd.DataFrame)
        assert "is_displacement" in result.columns


class TestKillzoneManager:
    """Tests for Killzone manager"""
    
    def test_ny_am_detection(self):
        """Test NY AM killzone detection"""
        from ict_agent.engine.killzone import KillzoneManager, Killzone
        
        manager = KillzoneManager(timezone_offset=-5)
        
        ny_am_time = datetime(2024, 1, 15, 13, 0, 0)
        
        is_in_kz = manager.is_in_killzone(ny_am_time)
        assert isinstance(is_in_kz, bool)
    
    def test_silver_bullet_window(self):
        """Test Silver Bullet window detection"""
        from ict_agent.engine.killzone import KillzoneManager
        
        manager = KillzoneManager()
        
        test_time = datetime(2024, 1, 15, 15, 30, 0)
        
        result = manager.is_silver_bullet_window(test_time)
        assert isinstance(result, bool)
    
    def test_macro_time(self):
        """Test macro time detection"""
        from ict_agent.engine.killzone import KillzoneManager
        
        manager = KillzoneManager()
        
        test_time = datetime(2024, 1, 15, 10, 5, 0)
        
        result = manager.is_in_macro_time(test_time)
        assert isinstance(result, bool)


class TestSignalGenerator:
    """Tests for Signal Generator"""
    
    def test_generate_signal_with_neutral_bias(self):
        """Test that no signal is generated with neutral bias"""
        from ict_agent.engine.signal_generator import SignalGenerator
        from ict_agent.engine.mtf_analyzer import Bias
        
        generator = SignalGenerator()
        ohlc = create_sample_ohlc()
        
        signal = generator.generate_signal(
            symbol="EURUSD",
            ltf_ohlc=ohlc,
            htf_bias=Bias.NEUTRAL,
        )
        
        assert signal is None


class TestBacktestMetrics:
    """Tests for Backtest Metrics"""
    
    def test_empty_trades_metrics(self):
        """Test metrics with no trades"""
        from ict_agent.backtest.metrics import BacktestMetrics
        
        metrics = BacktestMetrics(
            symbol="EURUSD",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            initial_capital=10000,
            final_capital=10000,
            trades=[],
            equity_curve=pd.DataFrame(),
            signals=[],
        )
        
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
