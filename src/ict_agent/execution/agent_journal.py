"""
Vex's Trade Journal

Autonomous journal for tracking all trades Vex (the AI agent) takes.
Separate from Ashton's journal - this is VEX's trading record.

Records:
- Every trade entry and exit
- Setup details (model, confluences)
- Risk/reward analysis
- P&L tracking
- Learning notes (what worked, what didn't)
"""

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
from enum import Enum

# Import learning system for automatic trade learning
try:
    from ict_agent.learning.trade_learner import TradeLearner
    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False


NY_TZ = ZoneInfo("America/New_York")


class TradeStatus(Enum):
    PENDING = "pending"       # Order placed, waiting for fill
    OPEN = "open"             # Trade is live
    CLOSED = "closed"         # Trade completed
    CANCELLED = "cancelled"   # Order cancelled


class TradeOutcome(Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PARTIAL = "partial"


@dataclass
class JournalEntry:
    """A single trade journal entry"""
    # Identification
    id: str
    timestamp: datetime
    
    # Trade details
    symbol: str
    side: str  # "BUY" or "SELL"
    status: str = "open"  # pending, open, closed, cancelled
    
    # Execution
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0
    units: int = 0
    trade_id: Optional[str] = None
    
    # Setup details
    model: str = ""  # Which ICT model triggered this trade
    timeframe: str = ""
    confluences: List[str] = field(default_factory=list)
    setup_description: str = ""
    
    # Session context
    session: str = ""  # "london", "new_york", etc.
    asian_range_high: Optional[float] = None
    asian_range_low: Optional[float] = None
    cbdr_high: Optional[float] = None
    cbdr_low: Optional[float] = None
    
    # Risk management
    risk_amount: float = 0.0
    risk_percent: float = 0.0
    target_rr: float = 0.0
    
    # Results (filled when trade closes)
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pips: float = 0.0
    actual_rr: float = 0.0
    outcome: str = ""  # win, loss, breakeven
    
    # Learning
    notes: str = ""
    what_worked: str = ""
    what_failed: str = ""
    lesson_learned: str = ""
    
    # Screenshots (paths)
    entry_screenshot: Optional[str] = None
    exit_screenshot: Optional[str] = None
    
    def to_dict(self) -> dict:
        data = asdict(self)
        # Convert datetime to string
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        if self.exit_time:
            data['exit_time'] = self.exit_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'JournalEntry':
        # Convert strings back to datetime
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'exit_time' in data and data['exit_time'] and isinstance(data['exit_time'], str):
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)


@dataclass
class DailyStats:
    """Statistics for a trading day"""
    date: str
    trades_taken: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    total_pnl: float = 0.0
    total_pips: float = 0.0
    win_rate: float = 0.0
    average_rr: float = 0.0
    best_trade: Optional[str] = None
    worst_trade: Optional[str] = None
    models_used: List[str] = field(default_factory=list)
    notes: str = ""


class AgentJournal:
    """
    The Agent's Trade Journal
    
    I keep meticulous records of every trade I take.
    This helps me learn and improve over time.
    """
    
    def __init__(self, journal_dir: str = None):
        self.journal_dir = Path(journal_dir or 
            Path(__file__).parent.parent.parent.parent / "journal" / "vex"
        )
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        
        # Current entries (loaded for today)
        self.entries: Dict[str, JournalEntry] = {}
        
        # Load today's entries
        self._load_today()
    
    def _get_journal_file(self, date_obj: date = None) -> Path:
        """Get journal file path for a date"""
        if date_obj is None:
            date_obj = datetime.now(NY_TZ).date()
        return self.journal_dir / f"{date_obj.isoformat()}.json"
    
    def _load_today(self):
        """Load today's journal entries"""
        file_path = self._get_journal_file()
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                self.entries = {
                    entry_id: JournalEntry.from_dict(entry_data)
                    for entry_id, entry_data in data.get("entries", {}).items()
                }
            except Exception as e:
                print(f"Error loading journal: {e}")
                self.entries = {}
        else:
            self.entries = {}
    
    def _save(self):
        """Save journal to file"""
        file_path = self._get_journal_file()
        data = {
            "date": datetime.now(NY_TZ).date().isoformat(),
            "entries": {
                entry_id: entry.to_dict()
                for entry_id, entry in self.entries.items()
            },
            "stats": self._calculate_stats().to_dict() if hasattr(self._calculate_stats(), 'to_dict') else asdict(self._calculate_stats()),
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _generate_id(self) -> str:
        """Generate unique trade ID"""
        now = datetime.now(NY_TZ)
        return f"AGENT_{now.strftime('%Y%m%d_%H%M%S')}_{len(self.entries) + 1:03d}"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADE LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════
    
    def record_entry(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        units: int,
        trade_id: str,
        model: str,
        timeframe: str = "",
        confluences: List[str] = None,
        setup_description: str = "",
        risk_amount: float = 0.0,
        risk_percent: float = 0.0,
        session: str = "",
        asian_range: tuple = None,
        cbdr_range: tuple = None,
    ) -> JournalEntry:
        """
        Record a new trade entry.
        
        Called when a trade is executed.
        """
        entry_id = self._generate_id()
        
        # Calculate target R:R
        pip_value = 0.01 if "JPY" in symbol.upper() else 0.0001
        if side.upper() == "BUY":
            risk_pips = abs(entry_price - stop_loss) / pip_value
            reward_pips = abs(take_profit - entry_price) / pip_value
        else:
            risk_pips = abs(stop_loss - entry_price) / pip_value
            reward_pips = abs(entry_price - take_profit) / pip_value
        
        target_rr = reward_pips / risk_pips if risk_pips > 0 else 0
        
        entry = JournalEntry(
            id=entry_id,
            timestamp=datetime.now(NY_TZ),
            symbol=symbol,
            side=side.upper(),
            status="open",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            units=units,
            trade_id=trade_id,
            model=model,
            timeframe=timeframe,
            confluences=confluences or [],
            setup_description=setup_description,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            target_rr=target_rr,
            session=session,
            asian_range_high=asian_range[0] if asian_range else None,
            asian_range_low=asian_range[1] if asian_range else None,
            cbdr_high=cbdr_range[0] if cbdr_range else None,
            cbdr_low=cbdr_range[1] if cbdr_range else None,
        )
        
        self.entries[entry_id] = entry
        self._save()
        
        print(f"📝 Journal Entry Created: {entry_id}")
        print(f"   {side} {symbol} @ {entry_price:.5f}")
        print(f"   SL: {stop_loss:.5f} | TP: {take_profit:.5f}")
        print(f"   Model: {model} | R:R: 1:{target_rr:.2f}")
        
        return entry
    
    def record_exit(
        self,
        entry_id: str = None,
        trade_id: str = None,
        exit_price: float = 0.0,
        pnl: float = 0.0,
        notes: str = "",
        what_worked: str = "",
        what_failed: str = "",
        lesson_learned: str = "",
    ) -> Optional[JournalEntry]:
        """
        Record trade exit.
        
        Called when a trade closes (TP, SL, or manual).
        """
        # Find the entry
        entry = None
        if entry_id and entry_id in self.entries:
            entry = self.entries[entry_id]
        elif trade_id:
            for e in self.entries.values():
                if e.trade_id == trade_id:
                    entry = e
                    break
        
        if not entry:
            print(f"❌ Could not find trade to close: {entry_id or trade_id}")
            return None
        
        # Calculate results
        pip_value = 0.01 if "JPY" in entry.symbol.upper() else 0.0001
        
        if entry.side == "BUY":
            pnl_pips = (exit_price - entry.entry_price) / pip_value
        else:
            pnl_pips = (entry.entry_price - exit_price) / pip_value
        
        risk_pips = abs(entry.entry_price - entry.stop_loss) / pip_value
        actual_rr = pnl_pips / risk_pips if risk_pips > 0 else 0
        
        # Determine outcome
        if pnl > 0:
            outcome = "win"
        elif pnl < 0:
            outcome = "loss"
        else:
            outcome = "breakeven"
        
        # Update entry
        entry.status = "closed"
        entry.exit_price = exit_price
        entry.exit_time = datetime.now(NY_TZ)
        entry.pnl = pnl
        entry.pnl_pips = pnl_pips
        entry.actual_rr = actual_rr
        entry.outcome = outcome
        entry.notes = notes
        entry.what_worked = what_worked
        entry.what_failed = what_failed
        entry.lesson_learned = lesson_learned
        
        self._save()
        
        # ═══════════════════════════════════════════════════════════════════════
        # AUTOMATIC LEARNING - Learn from every closed trade
        # ═══════════════════════════════════════════════════════════════════════
        if LEARNING_AVAILABLE:
            try:
                learner = TradeLearner()
                learner.record_trade(
                    symbol=entry.symbol,
                    direction=entry.side,
                    model=entry.model or "unknown",
                    session=entry.session or "unknown",
                    outcome=outcome,
                    rr_achieved=actual_rr,
                    confluences=entry.confluences or [],
                    notes=f"W: {what_worked or 'N/A'} | F: {what_failed or 'N/A'} | L: {lesson_learned or 'N/A'}"
                )
                print(f"   📚 Trade recorded to learning system")
            except Exception as e:
                print(f"   ⚠️ Learning record failed: {e}")
        
        outcome_emoji = "🎯" if outcome == "win" else "❌" if outcome == "loss" else "➖"
        print(f"{outcome_emoji} Trade Closed: {entry.id}")
        print(f"   {entry.side} {entry.symbol} | {entry.model}")
        print(f"   Entry: {entry.entry_price:.5f} → Exit: {exit_price:.5f}")
        print(f"   P&L: ${pnl:+.2f} ({pnl_pips:+.1f} pips)")
        print(f"   R:R: {actual_rr:.2f}R")
        
        return entry
    
    def update_notes(
        self,
        entry_id: str,
        notes: str = None,
        what_worked: str = None,
        what_failed: str = None,
        lesson_learned: str = None,
    ):
        """Update notes on an existing entry"""
        if entry_id not in self.entries:
            return
        
        entry = self.entries[entry_id]
        
        if notes:
            entry.notes = notes
        if what_worked:
            entry.what_worked = what_worked
        if what_failed:
            entry.what_failed = what_failed
        if lesson_learned:
            entry.lesson_learned = lesson_learned
        
        self._save()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _calculate_stats(self, entries: Dict[str, JournalEntry] = None) -> DailyStats:
        """Calculate statistics for given entries"""
        entries = entries or self.entries
        
        closed = [e for e in entries.values() if e.status == "closed"]
        
        stats = DailyStats(
            date=datetime.now(NY_TZ).date().isoformat(),
            trades_taken=len(closed),
        )
        
        if not closed:
            return stats
        
        wins = [e for e in closed if e.outcome == "win"]
        losses = [e for e in closed if e.outcome == "loss"]
        breakevens = [e for e in closed if e.outcome == "breakeven"]
        
        stats.wins = len(wins)
        stats.losses = len(losses)
        stats.breakevens = len(breakevens)
        stats.total_pnl = sum(e.pnl for e in closed)
        stats.total_pips = sum(e.pnl_pips for e in closed)
        stats.win_rate = (len(wins) / len(closed) * 100) if closed else 0
        stats.average_rr = sum(e.actual_rr for e in closed) / len(closed) if closed else 0
        stats.models_used = list(set(e.model for e in closed if e.model))
        
        # Best and worst trades
        if closed:
            best = max(closed, key=lambda e: e.pnl)
            worst = min(closed, key=lambda e: e.pnl)
            stats.best_trade = f"{best.symbol} +${best.pnl:.2f}"
            stats.worst_trade = f"{worst.symbol} ${worst.pnl:.2f}"
        
        return stats
    
    def get_today_stats(self) -> DailyStats:
        """Get statistics for today"""
        return self._calculate_stats()
    
    def get_open_trades(self) -> List[JournalEntry]:
        """Get all currently open trades"""
        return [e for e in self.entries.values() if e.status == "open"]
    
    def get_trade_by_oanda_id(self, trade_id: str) -> Optional[JournalEntry]:
        """Find journal entry by OANDA trade ID"""
        for entry in self.entries.values():
            if entry.trade_id == trade_id:
                return entry
        return None
    
    def get_learning_recommendation(self, symbol: str, direction: str, model: str, session: str) -> Dict[str, Any]:
        """
        Get learning system recommendation BEFORE taking a trade.
        Returns warnings, pattern stats, and confidence assessment.
        """
        if not LEARNING_AVAILABLE:
            return {"available": False, "reason": "Learning system not available"}
        
        try:
            learner = TradeLearner()
            return learner.get_recommendation(
                symbol=symbol,
                direction=direction,
                model=model,
                session=session
            )
        except Exception as e:
            return {"available": False, "reason": str(e)}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REPORTING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def format_daily_report(self) -> str:
        """Format daily trading report"""
        stats = self.get_today_stats()
        open_trades = self.get_open_trades()
        
        lines = [
            "═══════════════════════════════════════════════════════════",
            f"📊 AGENT TRADE JOURNAL - {stats.date}",
            "═══════════════════════════════════════════════════════════",
            "",
        ]
        
        # Open trades
        if open_trades:
            lines.append(f"🔓 OPEN TRADES ({len(open_trades)}):")
            for trade in open_trades:
                lines.append(f"   {trade.side} {trade.symbol} @ {trade.entry_price:.5f}")
                lines.append(f"   Model: {trade.model} | SL: {trade.stop_loss:.5f} | TP: {trade.take_profit:.5f}")
            lines.append("")
        
        # Statistics
        lines.extend([
            "📈 TODAY'S STATISTICS:",
            f"   Trades: {stats.trades_taken}",
            f"   Wins: {stats.wins} | Losses: {stats.losses} | BE: {stats.breakevens}",
            f"   Win Rate: {stats.win_rate:.1f}%",
            f"   Total P&L: ${stats.total_pnl:+.2f} ({stats.total_pips:+.1f} pips)",
            f"   Average R:R: {stats.average_rr:.2f}R",
            "",
        ])
        
        if stats.best_trade:
            lines.append(f"   🏆 Best: {stats.best_trade}")
        if stats.worst_trade:
            lines.append(f"   💀 Worst: {stats.worst_trade}")
        
        if stats.models_used:
            lines.append(f"   📐 Models: {', '.join(stats.models_used)}")
        
        lines.append("")
        lines.append("═══════════════════════════════════════════════════════════")
        
        return "\n".join(lines)
    
    def format_trade_entry(self, entry: JournalEntry) -> str:
        """Format a single trade entry for display"""
        lines = [
            f"─── Trade {entry.id} ───",
            f"📍 {entry.side} {entry.symbol} @ {entry.entry_price:.5f}",
            f"🎯 Model: {entry.model}",
            f"⏰ {entry.timestamp.strftime('%Y-%m-%d %H:%M')} ({entry.session})",
            f"📊 SL: {entry.stop_loss:.5f} | TP: {entry.take_profit:.5f}",
            f"💰 Risk: ${entry.risk_amount:.2f} ({entry.risk_percent:.1f}%)",
            f"📏 Target R:R: 1:{entry.target_rr:.2f}",
        ]
        
        if entry.confluences:
            lines.append(f"✓ Confluences: {', '.join(entry.confluences)}")
        
        if entry.status == "closed":
            outcome_emoji = "🎯" if entry.outcome == "win" else "❌" if entry.outcome == "loss" else "➖"
            lines.extend([
                "",
                f"{outcome_emoji} RESULT: {entry.outcome.upper()}",
                f"   Exit: {entry.exit_price:.5f}",
                f"   P&L: ${entry.pnl:+.2f} ({entry.pnl_pips:+.1f} pips)",
                f"   Actual R:R: {entry.actual_rr:.2f}R",
            ])
            
            if entry.lesson_learned:
                lines.append(f"   📚 Lesson: {entry.lesson_learned}")
        
        return "\n".join(lines)


# Quick access function
def get_journal() -> AgentJournal:
    """Get the agent journal instance"""
    return AgentJournal()


# Test
if __name__ == "__main__":
    print("Testing Agent Journal...")
    
    journal = AgentJournal()
    
    # Create test entry
    entry = journal.record_entry(
        symbol="EUR_USD",
        side="SELL",
        entry_price=1.16400,
        stop_loss=1.16600,
        take_profit=1.15900,
        units=10000,
        trade_id="12345",
        model="MMSM",
        timeframe="M15",
        confluences=["FVG", "OB", "Killzone"],
        setup_description="MMSM in Smart Money Reversal phase",
        risk_amount=25.00,
        risk_percent=2.5,
        session="new_york",
    )
    
    print("\n" + journal.format_trade_entry(entry))
    print("\n" + journal.format_daily_report())
