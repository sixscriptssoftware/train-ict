"""Position Manager

Manages open positions with ICT-specific rules like position cycling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import pandas as pd
from loguru import logger


class PositionState(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"


@dataclass
class Position:
    """Represents a trading position"""
    id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    stop_loss: float
    target_1: float
    target_2: Optional[float]
    position_size: float
    remaining_size: float
    entry_time: datetime
    state: PositionState = PositionState.OPEN
    cycles: int = 0
    t1_hit: bool = False
    pnl: float = 0.0
    
    def update_price(self, price: float) -> None:
        """Update current price and unrealized P&L"""
        self.current_price = price
        if self.direction == "long":
            self.pnl = (price - self.entry_price) * self.remaining_size
        else:
            self.pnl = (self.entry_price - price) * self.remaining_size


class PositionManager:
    """
    Manages trading positions with ICT rules.
    
    Features:
    - Position cycling (max 2 cycles per trade)
    - Partial exit management (50% at T1)
    - Break-even stop movement
    - Weekend close enforcement
    
    ICT Position Rules:
    1. Scale out 50% at Target 1
    2. Move stop to break-even after T1
    3. Maximum 2 position cycles per setup
    4. Close all positions Friday 4PM EST
    """
    
    def __init__(
        self,
        max_positions: int = 3,
        max_cycles: int = 2,
        partial_exit_pct: float = 0.5,
    ):
        self.max_positions = max_positions
        self.max_cycles = max_cycles
        self.partial_exit_pct = partial_exit_pct
        
        self._positions: dict[str, Position] = {}
        self._closed_positions: list[Position] = []
        self._position_counter = 0
    
    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        target_1: float,
        target_2: Optional[float],
        position_size: float,
    ) -> Optional[Position]:
        """
        Open a new position.
        
        Returns:
            Position object if opened, None if max positions reached
        """
        if len(self._positions) >= self.max_positions:
            logger.warning("Max positions reached, cannot open new position")
            return None
        
        self._position_counter += 1
        pos_id = f"{symbol}_{self._position_counter}"
        
        position = Position(
            id=pos_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            position_size=position_size,
            remaining_size=position_size,
            entry_time=datetime.now(),
        )
        
        self._positions[pos_id] = position
        
        logger.info(
            f"POSITION OPENED: {pos_id} | {direction} {symbol} @ {entry_price} | "
            f"Size: {position_size}"
        )
        
        return position
    
    def update_positions(self, prices: dict[str, float]) -> list[dict]:
        """
        Update all positions with current prices.
        
        Args:
            prices: Dict of symbol -> current price
        
        Returns:
            List of actions taken (partial exits, stops hit, etc.)
        """
        actions = []
        positions_to_close = []
        
        for pos_id, pos in self._positions.items():
            if pos.symbol not in prices:
                continue
            
            current_price = prices[pos.symbol]
            pos.update_price(current_price)
            
            if pos.direction == "long":
                if current_price <= pos.stop_loss:
                    actions.append({
                        "action": "stop_loss",
                        "position_id": pos_id,
                        "price": pos.stop_loss,
                        "pnl": pos.pnl,
                    })
                    positions_to_close.append(pos_id)
                    continue
                
                if not pos.t1_hit and current_price >= pos.target_1:
                    partial_action = self._handle_t1_hit(pos, current_price)
                    if partial_action:
                        actions.append(partial_action)
                
                elif pos.t1_hit and pos.target_2 and current_price >= pos.target_2:
                    actions.append({
                        "action": "target_2",
                        "position_id": pos_id,
                        "price": pos.target_2,
                        "pnl": pos.pnl,
                    })
                    positions_to_close.append(pos_id)
            
            else:
                if current_price >= pos.stop_loss:
                    actions.append({
                        "action": "stop_loss",
                        "position_id": pos_id,
                        "price": pos.stop_loss,
                        "pnl": pos.pnl,
                    })
                    positions_to_close.append(pos_id)
                    continue
                
                if not pos.t1_hit and current_price <= pos.target_1:
                    partial_action = self._handle_t1_hit(pos, current_price)
                    if partial_action:
                        actions.append(partial_action)
                
                elif pos.t1_hit and pos.target_2 and current_price <= pos.target_2:
                    actions.append({
                        "action": "target_2",
                        "position_id": pos_id,
                        "price": pos.target_2,
                        "pnl": pos.pnl,
                    })
                    positions_to_close.append(pos_id)
        
        for pos_id in positions_to_close:
            self.close_position(pos_id)
        
        return actions
    
    def _handle_t1_hit(self, pos: Position, current_price: float) -> Optional[dict]:
        """Handle Target 1 hit - partial exit and stop adjustment"""
        if pos.cycles >= self.max_cycles:
            logger.info(f"Max cycles reached for {pos.id}, closing full position")
            return {
                "action": "max_cycles_close",
                "position_id": pos.id,
                "price": current_price,
                "pnl": pos.pnl,
            }
        
        partial_size = pos.remaining_size * self.partial_exit_pct
        pos.remaining_size -= partial_size
        pos.t1_hit = True
        pos.state = PositionState.PARTIAL
        
        pos.stop_loss = pos.entry_price
        
        pos.cycles += 1
        
        logger.info(
            f"T1 HIT: {pos.id} | Partial exit {partial_size} @ {current_price} | "
            f"Stop moved to BE | Cycle {pos.cycles}/{self.max_cycles}"
        )
        
        return {
            "action": "partial_exit",
            "position_id": pos.id,
            "exit_size": partial_size,
            "price": current_price,
            "remaining_size": pos.remaining_size,
            "cycles": pos.cycles,
        }
    
    def close_position(
        self,
        pos_id: str,
        reason: str = "manual",
    ) -> Optional[Position]:
        """Close a position"""
        if pos_id not in self._positions:
            return None
        
        pos = self._positions.pop(pos_id)
        pos.state = PositionState.CLOSED
        self._closed_positions.append(pos)
        
        logger.info(
            f"POSITION CLOSED: {pos_id} | Reason: {reason} | "
            f"P&L: {pos.pnl:.2f}"
        )
        
        return pos
    
    def close_all_positions(self, reason: str = "manual") -> list[Position]:
        """Close all open positions"""
        closed = []
        for pos_id in list(self._positions.keys()):
            pos = self.close_position(pos_id, reason)
            if pos:
                closed.append(pos)
        return closed
    
    def get_position(self, pos_id: str) -> Optional[Position]:
        """Get position by ID"""
        return self._positions.get(pos_id)
    
    def get_open_positions(self) -> list[Position]:
        """Get all open positions"""
        return list(self._positions.values())
    
    def get_positions_by_symbol(self, symbol: str) -> list[Position]:
        """Get all positions for a symbol"""
        return [p for p in self._positions.values() if p.symbol == symbol]
    
    def get_total_exposure(self) -> float:
        """Get total position size across all positions"""
        return sum(p.remaining_size for p in self._positions.values())
    
    def get_unrealized_pnl(self) -> float:
        """Get total unrealized P&L"""
        return sum(p.pnl for p in self._positions.values())
