"""
BISI/SIBI and Liquidity Void Detector

BISI = Buyside Imbalance Sellside Inefficiency (Bullish FVG)
SIBI = Sellside Imbalance Buyside Inefficiency (Bearish FVG)

These are just FVGs with proper ICT naming.
Liquidity Void = larger unfilled gap, often from news or session opens.
"""

from dataclasses import dataclass
from typing import List, Literal, Optional
import pandas as pd
import numpy as np


@dataclass
class Imbalance:
    """BISI or SIBI imbalance"""
    index: int
    timestamp: pd.Timestamp
    type: Literal["BISI", "SIBI"]  # BISI = bullish, SIBI = bearish
    top: float
    bottom: float
    ce: float  # Consequent Encroachment (midpoint)
    size_pips: float
    mitigated: bool = False
    mitigation_percent: float = 0.0  # How much has been filled


@dataclass
class LiquidityVoid:
    """Large unfilled gap - typically from news or session gaps"""
    index: int
    timestamp: pd.Timestamp
    direction: Literal["BULLISH", "BEARISH"]
    top: float
    bottom: float
    size_pips: float
    filled: bool = False


class ImbalanceDetector:
    """
    Detects BISI/SIBI (ICT's proper names for FVGs) and Liquidity Voids.
    
    BISI = Buyside Imbalance Sellside Inefficiency
        - Gap UP - price moved up so fast sellers couldn't fill
        - Bullish FVG - expect price to return and fill partially
        
    SIBI = Sellside Imbalance Buyside Inefficiency  
        - Gap DOWN - price moved down so fast buyers couldn't fill
        - Bearish FVG - expect price to return and fill partially
        
    Liquidity Void = Larger gap (3x normal), often unfilled for longer
    """
    
    def __init__(
        self,
        min_imbalance_pips: float = 2.0,
        liquidity_void_multiplier: float = 3.0,  # 3x normal = void
        pip_size: float = 0.0001
    ):
        self.min_imbalance_pips = min_imbalance_pips
        self.liquidity_void_multiplier = liquidity_void_multiplier
        self.pip_size = pip_size
    
    def detect(self, ohlc: pd.DataFrame) -> dict:
        """
        Detect all imbalances and voids.
        
        Returns:
            {
                'bisi': List[Imbalance],  # Bullish imbalances
                'sibi': List[Imbalance],  # Bearish imbalances
                'voids': List[LiquidityVoid],
                'open_bisi': List[Imbalance],  # Unmitigated
                'open_sibi': List[Imbalance],  # Unmitigated
            }
        """
        bisi_list = []
        sibi_list = []
        voids = []
        
        min_gap = self.min_imbalance_pips * self.pip_size
        void_threshold = min_gap * self.liquidity_void_multiplier
        
        highs = ohlc['high'].values
        lows = ohlc['low'].values
        
        for i in range(2, len(ohlc)):
            # BISI (Bullish) - Candle 1 high < Candle 3 low
            if highs[i-2] < lows[i]:
                gap_size = lows[i] - highs[i-2]
                if gap_size >= min_gap:
                    imbalance = Imbalance(
                        index=i-1,  # Middle candle
                        timestamp=ohlc.index[i-1],
                        type="BISI",
                        top=lows[i],
                        bottom=highs[i-2],
                        ce=(lows[i] + highs[i-2]) / 2,
                        size_pips=gap_size / self.pip_size
                    )
                    
                    # Check mitigation
                    imbalance = self._check_mitigation(imbalance, ohlc, i)
                    bisi_list.append(imbalance)
                    
                    # Is it a void?
                    if gap_size >= void_threshold:
                        voids.append(LiquidityVoid(
                            index=i-1,
                            timestamp=ohlc.index[i-1],
                            direction="BULLISH",
                            top=lows[i],
                            bottom=highs[i-2],
                            size_pips=gap_size / self.pip_size,
                            filled=imbalance.mitigated
                        ))
            
            # SIBI (Bearish) - Candle 1 low > Candle 3 high
            if lows[i-2] > highs[i]:
                gap_size = lows[i-2] - highs[i]
                if gap_size >= min_gap:
                    imbalance = Imbalance(
                        index=i-1,
                        timestamp=ohlc.index[i-1],
                        type="SIBI",
                        top=lows[i-2],
                        bottom=highs[i],
                        ce=(lows[i-2] + highs[i]) / 2,
                        size_pips=gap_size / self.pip_size
                    )
                    
                    imbalance = self._check_mitigation(imbalance, ohlc, i)
                    sibi_list.append(imbalance)
                    
                    if gap_size >= void_threshold:
                        voids.append(LiquidityVoid(
                            index=i-1,
                            timestamp=ohlc.index[i-1],
                            direction="BEARISH",
                            top=lows[i-2],
                            bottom=highs[i],
                            size_pips=gap_size / self.pip_size,
                            filled=imbalance.mitigated
                        ))
        
        return {
            'bisi': bisi_list,
            'sibi': sibi_list,
            'voids': voids,
            'open_bisi': [b for b in bisi_list if not b.mitigated],
            'open_sibi': [s for s in sibi_list if not s.mitigated],
        }
    
    def _check_mitigation(self, imbalance: Imbalance, ohlc: pd.DataFrame, start_idx: int) -> Imbalance:
        """Check if imbalance has been mitigated (price returned to fill it)"""
        for j in range(start_idx + 1, len(ohlc)):
            if imbalance.type == "BISI":
                # Price needs to come DOWN into the gap
                if ohlc['low'].iloc[j] <= imbalance.top:
                    # Calculate how much was filled
                    lowest = ohlc['low'].iloc[j]
                    if lowest <= imbalance.bottom:
                        imbalance.mitigated = True
                        imbalance.mitigation_percent = 100.0
                    else:
                        filled = imbalance.top - lowest
                        total = imbalance.top - imbalance.bottom
                        imbalance.mitigation_percent = (filled / total) * 100
                        if imbalance.mitigation_percent >= 50:  # CE touched
                            imbalance.mitigated = True
                    break
            else:  # SIBI
                # Price needs to come UP into the gap
                if ohlc['high'].iloc[j] >= imbalance.bottom:
                    highest = ohlc['high'].iloc[j]
                    if highest >= imbalance.top:
                        imbalance.mitigated = True
                        imbalance.mitigation_percent = 100.0
                    else:
                        filled = highest - imbalance.bottom
                        total = imbalance.top - imbalance.bottom
                        imbalance.mitigation_percent = (filled / total) * 100
                        if imbalance.mitigation_percent >= 50:
                            imbalance.mitigated = True
                    break
        
        return imbalance
    
    def get_nearest_bisi(self, price: float, imbalances: List[Imbalance]) -> Optional[Imbalance]:
        """Get nearest open BISI below price (for long entries)"""
        below = [b for b in imbalances if not b.mitigated and b.top < price]
        if below:
            return max(below, key=lambda x: x.top)
        return None
    
    def get_nearest_sibi(self, price: float, imbalances: List[Imbalance]) -> Optional[Imbalance]:
        """Get nearest open SIBI above price (for short entries)"""
        above = [s for s in imbalances if not s.mitigated and s.bottom > price]
        if above:
            return min(above, key=lambda x: x.bottom)
        return None
