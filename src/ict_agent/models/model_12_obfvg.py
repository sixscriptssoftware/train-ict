"""ICT Model 12: Order Block + FVG 20 Pips Scalping Model

Model 12 is a precision scalping model that combines Order Blocks with Fair Value Gaps:

THE SEQUENCE:
1. Order Block forms (last opposing candle before displacement)
2. Price retests the Order Block
3. Expansion swing creates displacement away from OB
4. FVG forms within the expansion swing
5. Price retraces to the FVG
6. ENTRY: On touch of FVG (or 50% of FVG)
7. TARGET: 20 pips (or projection equal to the FVG size)

KEY RULES:
- Only trade during killzones
- HTF must be aligned
- OB must be valid (created by displacement)
- FVG must form in the direction of the trade
- 20 pip fixed target OR FVG projection target
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, time
from typing import Optional, List, Tuple, Callable
import pandas as pd
import numpy as np

from ict_agent.detectors.order_block import OrderBlockDetector, OrderBlock, OBDirection
from ict_agent.detectors.fvg import FVGDetector, FVG, FVGDirection
from ict_agent.detectors.displacement import DisplacementDetector
from ict_agent.engine.killzone import KillzoneManager, Killzone


class Model12Phase(Enum):
    WAITING_OB = "waiting_ob"  # Looking for Order Block
    OB_FORMED = "ob_formed"  # OB formed, waiting for retest
    OB_RETESTED = "ob_retested"  # OB retested, waiting for expansion
    EXPANSION = "expansion"  # Expansion swing happening
    FVG_FORMED = "fvg_formed"  # FVG formed in expansion
    WAITING_ENTRY = "waiting_entry"  # Waiting for FVG retracement
    ENTRY_VALID = "entry_valid"  # Entry conditions met
    COMPLETE = "complete"  # Trade complete


class Model12Direction(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class Model12Setup:
    """Complete Model 12 trade setup"""
    direction: Model12Direction
    phase: Model12Phase
    
    # Order Block details
    order_block: Optional[OrderBlock] = None
    ob_retest_time: Optional[pd.Timestamp] = None
    ob_retest_price: Optional[float] = None
    
    # Expansion swing
    expansion_start: Optional[pd.Timestamp] = None
    expansion_high: Optional[float] = None
    expansion_low: Optional[float] = None
    
    # FVG details  
    fvg: Optional[FVG] = None
    
    # Entry details
    entry_price: Optional[float] = None
    entry_time: Optional[pd.Timestamp] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    target_pips: float = 20.0
    
    # Metadata
    killzone: Optional[str] = None
    confidence: float = 0.0
    is_valid: bool = True
    invalidation_reason: Optional[str] = None


@dataclass
class Model12Signal:
    """Trading signal from Model 12"""
    direction: str  # "long" or "short"
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_pips: float
    reward_pips: float
    risk_reward_ratio: float
    fvg: FVG
    order_block: OrderBlock
    confidence: float
    timestamp: pd.Timestamp


class Model12Detector:
    """
    ICT Model 12: OB + FVG 20 Pips Scalping Model
    
    This model identifies high-probability scalping setups by:
    1. Finding valid Order Blocks (created by displacement)
    2. Waiting for OB retest
    3. Identifying expansion swing with FVG
    4. Taking entry on FVG retracement
    5. Fixed 20-pip target (or FVG projection)
    
    Best used during:
    - London Open Kill Zone (2-5 AM NY)
    - NY AM Kill Zone (7-10 AM NY)
    - Silver Bullet windows
    """
    
    def __init__(
        self,
        pip_size: float = 0.0001,
        target_pips: float = 20.0,
        min_fvg_pips: float = 3.0,
        max_stop_pips: float = 15.0,
        use_fvg_projection: bool = False,
        require_killzone: bool = True,
    ):
        self.pip_size = pip_size
        self.target_pips = target_pips
        self.min_fvg_pips = min_fvg_pips
        self.max_stop_pips = max_stop_pips
        self.use_fvg_projection = use_fvg_projection
        self.require_killzone = require_killzone
        
        # Initialize detectors
        self.ob_detector = OrderBlockDetector(pip_size=pip_size)
        self.fvg_detector = FVGDetector(
            min_gap_pips=min_fvg_pips,
            pip_size=pip_size,
        )
        self.killzone_manager = KillzoneManager()
        
        # State
        self._active_setups: List[Model12Setup] = []
        self._signals: List[Model12Signal] = []
    
    def analyze(
        self,
        ohlc: pd.DataFrame,
        htf_bias: Optional[str] = None,
    ) -> List[Model12Setup]:
        """
        Analyze price data for Model 12 setups.
        
        Args:
            ohlc: OHLCV DataFrame with DatetimeIndex
            htf_bias: Optional HTF bias ("bullish" or "bearish")
        
        Returns:
            List of active Model12Setup objects
        """
        if len(ohlc) < 20:
            return []
        
        # Detect Order Blocks
        ob_df = self.ob_detector.detect(ohlc)
        
        # Detect FVGs
        fvg_df = self.fvg_detector.detect(ohlc)
        
        # Check if in killzone
        current_time = ohlc.index[-1]
        if hasattr(current_time, 'to_pydatetime'):
            current_time = current_time.to_pydatetime()
        current_killzone = self.killzone_manager.get_current_killzone(current_time)
        
        if self.require_killzone and current_killzone is None:
            # Update existing setups but don't create new ones
            self._update_existing_setups(ohlc)
            return self._active_setups
        
        # Look for new setups
        self._scan_for_new_setups(ohlc, htf_bias, current_killzone)
        
        # Update existing setups
        self._update_existing_setups(ohlc)
        
        # Check for entry signals
        self._check_entry_signals(ohlc)
        
        return self._active_setups
    
    def _scan_for_new_setups(
        self,
        ohlc: pd.DataFrame,
        htf_bias: Optional[str],
        killzone: Optional[Killzone],
    ) -> None:
        """Scan for new Model 12 setups"""
        
        current_price = ohlc['close'].iloc[-1]
        
        # Get active Order Blocks
        bullish_obs = self.ob_detector.get_active_order_blocks(OBDirection.BULLISH)
        bearish_obs = self.ob_detector.get_active_order_blocks(OBDirection.BEARISH)
        
        # Get active FVGs
        bullish_fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BULLISH)
        bearish_fvgs = self.fvg_detector.get_active_fvgs(FVGDirection.BEARISH)
        
        # Look for bullish setups (if not bearish bias)
        if htf_bias != "bearish":
            self._scan_bullish_setups(
                ohlc, bullish_obs, bullish_fvgs, killzone
            )
        
        # Look for bearish setups (if not bullish bias)
        if htf_bias != "bullish":
            self._scan_bearish_setups(
                ohlc, bearish_obs, bearish_fvgs, killzone
            )
    
    def _scan_bullish_setups(
        self,
        ohlc: pd.DataFrame,
        order_blocks: List[OrderBlock],
        fvgs: List[FVG],
        killzone: Optional[Killzone],
    ) -> None:
        """Scan for bullish Model 12 setups"""
        
        current_price = ohlc['close'].iloc[-1]
        current_time = ohlc.index[-1]
        
        for ob in order_blocks:
            # Skip if OB already in an active setup
            if self._ob_in_active_setup(ob):
                continue
            
            # Check if price has retested the OB
            if self._check_ob_retest(ohlc, ob, is_bullish=True):
                # Look for FVG that formed after the retest
                matching_fvg = self._find_matching_fvg(
                    fvgs, ob, ohlc, is_bullish=True
                )
                
                if matching_fvg:
                    # Create setup
                    setup = self._create_bullish_setup(
                        ob, matching_fvg, ohlc, killzone
                    )
                    
                    if setup.is_valid:
                        self._active_setups.append(setup)
    
    def _scan_bearish_setups(
        self,
        ohlc: pd.DataFrame,
        order_blocks: List[OrderBlock],
        fvgs: List[FVG],
        killzone: Optional[Killzone],
    ) -> None:
        """Scan for bearish Model 12 setups"""
        
        for ob in order_blocks:
            if self._ob_in_active_setup(ob):
                continue
            
            if self._check_ob_retest(ohlc, ob, is_bullish=False):
                matching_fvg = self._find_matching_fvg(
                    fvgs, ob, ohlc, is_bullish=False
                )
                
                if matching_fvg:
                    setup = self._create_bearish_setup(
                        ob, matching_fvg, ohlc, killzone
                    )
                    
                    if setup.is_valid:
                        self._active_setups.append(setup)
    
    def _check_ob_retest(
        self,
        ohlc: pd.DataFrame,
        ob: OrderBlock,
        is_bullish: bool,
    ) -> bool:
        """Check if Order Block has been retested"""
        
        # Look for price touching OB zone after it formed
        post_ob_data = ohlc.iloc[ob.index:]
        
        if len(post_ob_data) < 2:
            return False
        
        if is_bullish:
            # For bullish OB, check if price came down to the zone
            zone_top = ob.top
            zone_bottom = ob.bottom
            
            # Did any candle low touch the zone?
            retest = post_ob_data['low'] <= zone_top
            if retest.any():
                return True
        else:
            # For bearish OB, check if price came up to the zone
            zone_top = ob.top
            zone_bottom = ob.bottom
            
            retest = post_ob_data['high'] >= zone_bottom
            if retest.any():
                return True
        
        return False
    
    def _find_matching_fvg(
        self,
        fvgs: List[FVG],
        ob: OrderBlock,
        ohlc: pd.DataFrame,
        is_bullish: bool,
    ) -> Optional[FVG]:
        """Find FVG that matches the setup criteria"""
        
        # FVG must form after OB retest
        # FVG must be in the direction of the trade
        
        matching_fvgs = []
        
        for fvg in fvgs:
            # FVG must be after OB
            if fvg.index <= ob.index:
                continue
            
            # FVG direction must match
            if is_bullish and fvg.direction != FVGDirection.BULLISH:
                continue
            if not is_bullish and fvg.direction != FVGDirection.BEARISH:
                continue
            
            # FVG should not be fully mitigated
            if fvg.fully_mitigated:
                continue
            
            # FVG should be large enough
            fvg_size = abs(fvg.top - fvg.bottom) / self.pip_size
            if fvg_size < self.min_fvg_pips:
                continue
            
            matching_fvgs.append(fvg)
        
        # Return the most recent valid FVG
        if matching_fvgs:
            return max(matching_fvgs, key=lambda x: x.index)
        
        return None
    
    def _create_bullish_setup(
        self,
        ob: OrderBlock,
        fvg: FVG,
        ohlc: pd.DataFrame,
        killzone: Optional[Killzone],
    ) -> Model12Setup:
        """Create a bullish Model 12 setup"""
        
        current_price = ohlc['close'].iloc[-1]
        current_time = ohlc.index[-1]
        
        # Entry at FVG midpoint or top of FVG
        entry_price = fvg.midpoint if fvg.midpoint else (fvg.top + fvg.bottom) / 2
        
        # Stop loss below OB
        stop_buffer = 2 * self.pip_size  # 2 pip buffer
        stop_loss = ob.bottom - stop_buffer
        
        # Check if stop is within limits
        risk_pips = (entry_price - stop_loss) / self.pip_size
        
        if risk_pips > self.max_stop_pips:
            return Model12Setup(
                direction=Model12Direction.BULLISH,
                phase=Model12Phase.WAITING_OB,
                is_valid=False,
                invalidation_reason=f"Risk too high: {risk_pips:.1f} pips > {self.max_stop_pips} max"
            )
        
        # Take profit
        if self.use_fvg_projection:
            # Use FVG size as target
            fvg_size = abs(fvg.top - fvg.bottom)
            take_profit = entry_price + fvg_size
        else:
            # Fixed 20 pip target
            take_profit = entry_price + (self.target_pips * self.pip_size)
        
        # Determine phase
        phase = Model12Phase.WAITING_ENTRY
        if current_price <= fvg.top and current_price >= fvg.bottom:
            phase = Model12Phase.ENTRY_VALID
        elif current_price < fvg.bottom:
            phase = Model12Phase.WAITING_ENTRY
        
        return Model12Setup(
            direction=Model12Direction.BULLISH,
            phase=phase,
            order_block=ob,
            fvg=fvg,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            target_pips=self.target_pips,
            killzone=killzone.name if killzone else None,
            confidence=self._calculate_setup_confidence(ob, fvg, killzone, risk_pips),
            is_valid=True,
        )
    
    def _create_bearish_setup(
        self,
        ob: OrderBlock,
        fvg: FVG,
        ohlc: pd.DataFrame,
        killzone: Optional[Killzone],
    ) -> Model12Setup:
        """Create a bearish Model 12 setup"""
        
        current_price = ohlc['close'].iloc[-1]
        
        # Entry at FVG midpoint
        entry_price = fvg.midpoint if fvg.midpoint else (fvg.top + fvg.bottom) / 2
        
        # Stop loss above OB
        stop_buffer = 2 * self.pip_size
        stop_loss = ob.top + stop_buffer
        
        risk_pips = (stop_loss - entry_price) / self.pip_size
        
        if risk_pips > self.max_stop_pips:
            return Model12Setup(
                direction=Model12Direction.BEARISH,
                phase=Model12Phase.WAITING_OB,
                is_valid=False,
                invalidation_reason=f"Risk too high: {risk_pips:.1f} pips > {self.max_stop_pips} max"
            )
        
        # Take profit
        if self.use_fvg_projection:
            fvg_size = abs(fvg.top - fvg.bottom)
            take_profit = entry_price - fvg_size
        else:
            take_profit = entry_price - (self.target_pips * self.pip_size)
        
        # Determine phase
        phase = Model12Phase.WAITING_ENTRY
        if current_price >= fvg.bottom and current_price <= fvg.top:
            phase = Model12Phase.ENTRY_VALID
        elif current_price > fvg.top:
            phase = Model12Phase.WAITING_ENTRY
        
        return Model12Setup(
            direction=Model12Direction.BEARISH,
            phase=phase,
            order_block=ob,
            fvg=fvg,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            target_pips=self.target_pips,
            killzone=killzone.name if killzone else None,
            confidence=self._calculate_setup_confidence(ob, fvg, killzone, risk_pips),
            is_valid=True,
        )
    
    def _calculate_setup_confidence(
        self,
        ob: OrderBlock,
        fvg: FVG,
        killzone: Optional[Killzone],
        risk_pips: float,
    ) -> float:
        """Calculate confidence score for setup"""
        
        score = 0.0
        
        # Order Block quality
        if ob.displacement_pips and ob.displacement_pips > 10:
            score += 0.2
        
        # FVG quality
        fvg_size = abs(fvg.top - fvg.bottom) / self.pip_size
        if fvg_size >= 5:
            score += 0.15
        if fvg_size >= 10:
            score += 0.1
        
        # Killzone bonus
        if killzone:
            score += 0.2
        
        # Risk/Reward
        reward_pips = self.target_pips
        rr = reward_pips / risk_pips if risk_pips > 0 else 0
        if rr >= 1.5:
            score += 0.15
        if rr >= 2.0:
            score += 0.1
        
        # OB not mitigated
        if not ob.mitigated:
            score += 0.1
        
        return min(score, 1.0)
    
    def _ob_in_active_setup(self, ob: OrderBlock) -> bool:
        """Check if OB is already in an active setup"""
        for setup in self._active_setups:
            if setup.order_block and setup.order_block.index == ob.index:
                return True
        return False
    
    def _update_existing_setups(self, ohlc: pd.DataFrame) -> None:
        """Update existing setups with current price action"""
        
        current_price = ohlc['close'].iloc[-1]
        current_high = ohlc['high'].iloc[-1]
        current_low = ohlc['low'].iloc[-1]
        
        for setup in self._active_setups[:]:  # Copy list to allow modification
            if not setup.is_valid:
                self._active_setups.remove(setup)
                continue
            
            # Check invalidation
            if setup.direction == Model12Direction.BULLISH:
                # Invalidated if price closes below stop
                if current_price < setup.stop_loss:
                    setup.is_valid = False
                    setup.invalidation_reason = "Price closed below stop loss"
                    continue
                
                # Check if FVG mitigated (touched entry zone)
                if setup.fvg and current_low <= setup.entry_price:
                    setup.phase = Model12Phase.ENTRY_VALID
                
                # Check if target hit
                if current_high >= setup.take_profit:
                    setup.phase = Model12Phase.COMPLETE
            
            else:  # Bearish
                if current_price > setup.stop_loss:
                    setup.is_valid = False
                    setup.invalidation_reason = "Price closed above stop loss"
                    continue
                
                if setup.fvg and current_high >= setup.entry_price:
                    setup.phase = Model12Phase.ENTRY_VALID
                
                if current_low <= setup.take_profit:
                    setup.phase = Model12Phase.COMPLETE
    
    def _check_entry_signals(self, ohlc: pd.DataFrame) -> None:
        """Check for entry signals on valid setups"""
        
        for setup in self._active_setups:
            if setup.phase == Model12Phase.ENTRY_VALID and setup.is_valid:
                signal = self._generate_signal(setup, ohlc)
                if signal:
                    self._signals.append(signal)
    
    def _generate_signal(
        self,
        setup: Model12Setup,
        ohlc: pd.DataFrame,
    ) -> Optional[Model12Signal]:
        """Generate trading signal from valid setup"""
        
        current_time = ohlc.index[-1]
        
        risk_pips = abs(setup.entry_price - setup.stop_loss) / self.pip_size
        reward_pips = abs(setup.take_profit - setup.entry_price) / self.pip_size
        rr = reward_pips / risk_pips if risk_pips > 0 else 0
        
        return Model12Signal(
            direction="long" if setup.direction == Model12Direction.BULLISH else "short",
            entry_price=setup.entry_price,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit,
            risk_pips=risk_pips,
            reward_pips=reward_pips,
            risk_reward_ratio=rr,
            fvg=setup.fvg,
            order_block=setup.order_block,
            confidence=setup.confidence,
            timestamp=current_time,
        )
    
    def get_active_setups(self) -> List[Model12Setup]:
        """Get all active setups"""
        return [s for s in self._active_setups if s.is_valid]
    
    def get_entry_valid_setups(self) -> List[Model12Setup]:
        """Get setups that are ready for entry"""
        return [s for s in self._active_setups 
                if s.phase == Model12Phase.ENTRY_VALID and s.is_valid]
    
    def get_signals(self) -> List[Model12Signal]:
        """Get generated signals"""
        return self._signals
    
    def clear_signals(self) -> None:
        """Clear processed signals"""
        self._signals = []
    
    def format_setup(self, setup: Model12Setup) -> str:
        """Format setup for display"""
        
        lines = [
            f"=== MODEL 12 SETUP ({setup.direction.value.upper()}) ===",
            f"Phase: {setup.phase.value}",
            f"Confidence: {setup.confidence:.0%}",
        ]
        
        if setup.order_block:
            lines.append(f"Order Block: {setup.order_block.top:.5f} - {setup.order_block.bottom:.5f}")
        
        if setup.fvg:
            lines.append(f"FVG: {setup.fvg.top:.5f} - {setup.fvg.bottom:.5f}")
        
        if setup.entry_price:
            lines.extend([
                f"Entry: {setup.entry_price:.5f}",
                f"Stop Loss: {setup.stop_loss:.5f}",
                f"Take Profit: {setup.take_profit:.5f}",
                f"Target: {setup.target_pips} pips",
            ])
        
        if setup.killzone:
            lines.append(f"Killzone: {setup.killzone}")
        
        if not setup.is_valid:
            lines.append(f"⚠️ INVALID: {setup.invalidation_reason}")
        
        return "\n".join(lines)
