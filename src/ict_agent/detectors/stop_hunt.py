"""
Turtle Soup, Judas Swing, and Stop Hunt Detector

Turtle Soup = Sweep of liquidity + immediate reversal (ICT's favorite)
Judas Swing = False breakout during manipulation phase (session-specific)
Stop Hunt = Any sweep of obvious liquidity
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import pytz


@dataclass
class TurtleSoup:
    """
    Turtle Soup pattern - sweep + reversal
    Named after the Turtle Traders whose stops got hunted
    """
    index: int
    timestamp: pd.Timestamp
    type: Literal["LONG", "SHORT"]  # Direction of the trade AFTER sweep
    sweep_price: float  # Price that swept the liquidity
    liquidity_level: float  # The level that was swept
    reversal_candle_index: int
    entry_price: float
    stop_loss: float
    invalidation: float  # If price goes beyond this, pattern fails


@dataclass
class JudasSwing:
    """
    Judas Swing - false breakout during manipulation phase
    Typically occurs during London or early NY to trap traders
    """
    index: int
    timestamp: pd.Timestamp
    session: Literal["LONDON", "NY"]
    direction: Literal["BULLISH", "BEARISH"]  # Direction of the FALSE move
    swing_high: float
    swing_low: float
    expected_reversal: Literal["LONG", "SHORT"]  # Expected trade direction


@dataclass
class StopHunt:
    """Any sweep of liquidity"""
    index: int
    timestamp: pd.Timestamp
    type: Literal["BSL_SWEEP", "SSL_SWEEP"]
    level_swept: float
    sweep_high: float
    sweep_low: float
    close_back_inside: bool  # Did price close back inside the range?


class StopHuntDetector:
    """
    Detects stop hunts, turtle soup patterns, and Judas swings.
    
    These are the "manipulation" part of AMD.
    """
    
    def __init__(
        self,
        swing_length: int = 5,
        min_sweep_pips: float = 2.0,  # Minimum pips beyond level to count as sweep
        pip_size: float = 0.0001
    ):
        self.swing_length = swing_length
        self.min_sweep_pips = min_sweep_pips
        self.pip_size = pip_size
        self.et = pytz.timezone('America/New_York')
    
    def detect(self, ohlc: pd.DataFrame) -> dict:
        """
        Detect all stop hunts and related patterns.
        
        Returns:
            {
                'stop_hunts': List[StopHunt],
                'turtle_soups': List[TurtleSoup],
                'judas_swings': List[JudasSwing],
                'recent_sweep': Optional[StopHunt],  # Most recent
            }
        """
        # Find swing points for liquidity levels
        swing_highs = self._find_swings(ohlc, "HIGH")
        swing_lows = self._find_swings(ohlc, "LOW")
        
        stop_hunts = []
        turtle_soups = []
        judas_swings = []
        
        # Look for sweeps
        for i in range(self.swing_length + 1, len(ohlc)):
            candle = ohlc.iloc[i]
            prev_candle = ohlc.iloc[i-1]
            
            # Check for BSL sweep (price went above swing high)
            for sh_idx, sh_price in swing_highs:
                if sh_idx >= i:
                    continue
                    
                sweep_amount = candle['high'] - sh_price
                if sweep_amount > self.min_sweep_pips * self.pip_size:
                    # It's a sweep!
                    close_back = candle['close'] < sh_price
                    
                    hunt = StopHunt(
                        index=i,
                        timestamp=ohlc.index[i],
                        type="BSL_SWEEP",
                        level_swept=sh_price,
                        sweep_high=candle['high'],
                        sweep_low=candle['low'],
                        close_back_inside=close_back
                    )
                    stop_hunts.append(hunt)
                    
                    # Check for Turtle Soup (sweep + close back + reversal)
                    if close_back and candle['close'] < candle['open']:
                        # Bearish candle closing back inside = potential turtle soup SHORT
                        turtle_soups.append(TurtleSoup(
                            index=i,
                            timestamp=ohlc.index[i],
                            type="SHORT",
                            sweep_price=candle['high'],
                            liquidity_level=sh_price,
                            reversal_candle_index=i,
                            entry_price=candle['close'],
                            stop_loss=candle['high'] + (5 * self.pip_size),
                            invalidation=candle['high']
                        ))
                    
                    # Check for Judas Swing
                    judas = self._check_judas_swing(ohlc, i, "BULLISH", candle['high'])
                    if judas:
                        judas_swings.append(judas)
                    
                    break  # Only count one sweep per candle
            
            # Check for SSL sweep (price went below swing low)
            for sl_idx, sl_price in swing_lows:
                if sl_idx >= i:
                    continue
                    
                sweep_amount = sl_price - candle['low']
                if sweep_amount > self.min_sweep_pips * self.pip_size:
                    close_back = candle['close'] > sl_price
                    
                    hunt = StopHunt(
                        index=i,
                        timestamp=ohlc.index[i],
                        type="SSL_SWEEP",
                        level_swept=sl_price,
                        sweep_high=candle['high'],
                        sweep_low=candle['low'],
                        close_back_inside=close_back
                    )
                    stop_hunts.append(hunt)
                    
                    if close_back and candle['close'] > candle['open']:
                        # Bullish candle closing back inside = potential turtle soup LONG
                        turtle_soups.append(TurtleSoup(
                            index=i,
                            timestamp=ohlc.index[i],
                            type="LONG",
                            sweep_price=candle['low'],
                            liquidity_level=sl_price,
                            reversal_candle_index=i,
                            entry_price=candle['close'],
                            stop_loss=candle['low'] - (5 * self.pip_size),
                            invalidation=candle['low']
                        ))
                    
                    judas = self._check_judas_swing(ohlc, i, "BEARISH", candle['low'])
                    if judas:
                        judas_swings.append(judas)
                    
                    break
        
        return {
            'stop_hunts': stop_hunts,
            'turtle_soups': turtle_soups,
            'judas_swings': judas_swings,
            'recent_sweep': stop_hunts[-1] if stop_hunts else None,
        }
    
    def _find_swings(self, ohlc: pd.DataFrame, swing_type: str) -> List[tuple]:
        """Find swing highs or lows"""
        swings = []
        n = self.swing_length
        
        if swing_type == "HIGH":
            values = ohlc['high'].values
            for i in range(n, len(ohlc) - n):
                if values[i] == max(values[i-n:i+n+1]):
                    swings.append((i, values[i]))
        else:
            values = ohlc['low'].values
            for i in range(n, len(ohlc) - n):
                if values[i] == min(values[i-n:i+n+1]):
                    swings.append((i, values[i]))
        
        return swings
    
    def _check_judas_swing(
        self, 
        ohlc: pd.DataFrame, 
        index: int, 
        direction: str,
        extreme_price: float
    ) -> Optional[JudasSwing]:
        """Check if sweep occurred during manipulation session (London or early NY)"""
        try:
            ts = ohlc.index[index]
            if ts.tzinfo is None:
                ts = ts.tz_localize('UTC')
            et_time = ts.astimezone(self.et)
            hour = et_time.hour
            
            # London manipulation: 2-5 AM ET
            # NY manipulation: 7-8 AM ET (early NY before real move)
            session = None
            if 2 <= hour < 5:
                session = "LONDON"
            elif 7 <= hour < 8:
                session = "NY"
            
            if session:
                # Get session range so far
                session_start = index - 12  # ~3 hours of 15m candles
                if session_start < 0:
                    session_start = 0
                
                session_high = ohlc['high'].iloc[session_start:index+1].max()
                session_low = ohlc['low'].iloc[session_start:index+1].min()
                
                return JudasSwing(
                    index=index,
                    timestamp=ohlc.index[index],
                    session=session,
                    direction=direction,
                    swing_high=session_high,
                    swing_low=session_low,
                    expected_reversal="SHORT" if direction == "BULLISH" else "LONG"
                )
        except:
            pass
        
        return None
    
    def detect_inducement(self, ohlc: pd.DataFrame) -> List[dict]:
        """
        Detect inducement - obvious liquidity that smart money will target.
        
        Inducement = minor swing point that creates obvious stop placement
        before the REAL liquidity target.
        """
        inducements = []
        swing_highs = self._find_swings(ohlc, "HIGH")
        swing_lows = self._find_swings(ohlc, "LOW")
        
        # Find minor swings between major swings (these are inducement)
        for i in range(1, len(swing_highs) - 1):
            prev_sh = swing_highs[i-1][1]
            curr_sh = swing_highs[i][1]
            next_sh = swing_highs[i+1][1]
            
            # If current swing is lower than both neighbors, it's potential inducement
            if curr_sh < prev_sh and curr_sh < next_sh:
                inducements.append({
                    'type': 'BSL_INDUCEMENT',
                    'index': swing_highs[i][0],
                    'price': curr_sh,
                    'real_target': max(prev_sh, next_sh),
                    'description': f'Minor high at {curr_sh:.5f} before real BSL at {max(prev_sh, next_sh):.5f}'
                })
        
        for i in range(1, len(swing_lows) - 1):
            prev_sl = swing_lows[i-1][1]
            curr_sl = swing_lows[i][1]
            next_sl = swing_lows[i+1][1]
            
            if curr_sl > prev_sl and curr_sl > next_sl:
                inducements.append({
                    'type': 'SSL_INDUCEMENT',
                    'index': swing_lows[i][0],
                    'price': curr_sl,
                    'real_target': min(prev_sl, next_sl),
                    'description': f'Minor low at {curr_sl:.5f} before real SSL at {min(prev_sl, next_sl):.5f}'
                })
        
        return inducements
