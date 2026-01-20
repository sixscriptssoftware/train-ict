#!/usr/bin/env python3
"""
VEX Session Statistics
Analyzes trading performance by killzone, day of week, setup type, etc.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class TradeStats:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    total_r: float = 0.0
    total_pnl: float = 0.0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.wins / self.total_trades) * 100

    @property
    def avg_r(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_r / self.total_trades

    def add_trade(self, r: float, pnl: float):
        self.total_trades += 1
        self.total_r += r
        self.total_pnl += pnl
        if r > 0.1:
            self.wins += 1
        elif r < -0.1:
            self.losses += 1
        else:
            self.breakeven += 1


class SessionStatistics:
    """
    Tracks and analyzes trading statistics across different dimensions.
    """

    def __init__(self, journal_path: str = None):
        self.journal_path = journal_path or Path(__file__).parent.parent.parent / "journal"
        self.trades: List[dict] = []

        # Stats by different dimensions
        self.by_killzone: Dict[str, TradeStats] = defaultdict(TradeStats)
        self.by_day: Dict[str, TradeStats] = defaultdict(TradeStats)  # Mon, Tue, etc.
        self.by_pair: Dict[str, TradeStats] = defaultdict(TradeStats)
        self.by_model: Dict[str, TradeStats] = defaultdict(TradeStats)
        self.by_direction: Dict[str, TradeStats] = defaultdict(TradeStats)
        self.by_hour: Dict[int, TradeStats] = defaultdict(TradeStats)

        self.overall = TradeStats()

    def load_trades(self, trader: str = "ashton"):
        """Load trades from JSON database."""
        db_path = Path(self.journal_path) / trader / "trades_database.json"

        if not db_path.exists():
            print(f"No trades database found at {db_path}")
            return

        with open(db_path) as f:
            data = json.load(f)
            self.trades = data.get("trades", [])

        self._calculate_stats()

    def _calculate_stats(self):
        """Calculate statistics from loaded trades."""
        for trade in self.trades:
            if trade.get("status") != "closed":
                continue

            r = trade.get("r_captured", 0)
            pnl = trade.get("pnl", 0)

            # Overall
            self.overall.add_trade(r, pnl)

            # By killzone
            killzone = trade.get("session", "unknown")
            self.by_killzone[killzone].add_trade(r, pnl)

            # By day of week
            date_str = trade.get("date", "")
            if date_str:
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    day = dt.strftime("%A")
                    self.by_day[day].add_trade(r, pnl)
                    self.by_hour[dt.hour].add_trade(r, pnl)
                except:
                    pass

            # By pair
            pair = trade.get("pair", "unknown")
            self.by_pair[pair].add_trade(r, pnl)

            # By model
            model = trade.get("model", "unknown")
            self.by_model[model].add_trade(r, pnl)

            # By direction
            direction = trade.get("direction", "unknown")
            self.by_direction[direction].add_trade(r, pnl)

    def format_stats(self, stats: TradeStats, name: str = "") -> str:
        """Format stats for display."""
        return f"""
{name}
  Trades: {stats.total_trades} | Win Rate: {stats.win_rate:.1f}%
  Wins: {stats.wins} | Losses: {stats.losses} | BE: {stats.breakeven}
  Total R: {stats.total_r:+.2f} | Avg R: {stats.avg_r:+.2f}
  P/L: ${stats.total_pnl:+.2f}
"""

    def generate_report(self) -> str:
        """Generate full statistics report."""
        report = """
╔══════════════════════════════════════════════════════════════╗
║                 📊 VEX SESSION STATISTICS                     ║
╚══════════════════════════════════════════════════════════════╝
"""

        # Overall
        report += "\n" + "═" * 50
        report += self.format_stats(self.overall, "\n📈 OVERALL PERFORMANCE")

        # By Killzone
        report += "\n" + "═" * 50
        report += "\n⏰ BY KILLZONE\n"
        for kz, stats in sorted(self.by_killzone.items(), key=lambda x: x[1].total_r, reverse=True):
            if stats.total_trades > 0:
                wr = f"{stats.win_rate:.0f}%"
                report += f"  {kz:15} | {stats.total_trades:2} trades | WR: {wr:5} | R: {stats.total_r:+.1f}\n"

        # By Day
        report += "\n" + "═" * 50
        report += "\n📅 BY DAY OF WEEK\n"
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in days_order:
            if day in self.by_day:
                stats = self.by_day[day]
                if stats.total_trades > 0:
                    wr = f"{stats.win_rate:.0f}%"
                    report += f"  {day:12} | {stats.total_trades:2} trades | WR: {wr:5} | R: {stats.total_r:+.1f}\n"

        # By Pair
        report += "\n" + "═" * 50
        report += "\n💱 BY PAIR\n"
        for pair, stats in sorted(self.by_pair.items(), key=lambda x: x[1].total_r, reverse=True):
            if stats.total_trades > 0:
                wr = f"{stats.win_rate:.0f}%"
                report += f"  {pair:12} | {stats.total_trades:2} trades | WR: {wr:5} | R: {stats.total_r:+.1f}\n"

        # By Model
        report += "\n" + "═" * 50
        report += "\n🎯 BY MODEL/SETUP\n"
        for model, stats in sorted(self.by_model.items(), key=lambda x: x[1].total_r, reverse=True):
            if stats.total_trades > 0:
                wr = f"{stats.win_rate:.0f}%"
                report += f"  {model[:20]:20} | {stats.total_trades:2} trades | WR: {wr:5} | R: {stats.total_r:+.1f}\n"

        # By Direction
        report += "\n" + "═" * 50
        report += "\n↕️ BY DIRECTION\n"
        for direction, stats in self.by_direction.items():
            if stats.total_trades > 0:
                wr = f"{stats.win_rate:.0f}%"
                report += f"  {direction:12} | {stats.total_trades:2} trades | WR: {wr:5} | R: {stats.total_r:+.1f}\n"

        # Insights
        report += "\n" + "═" * 50
        report += "\n💡 INSIGHTS\n"

        # Best killzone
        best_kz = max(self.by_killzone.items(), key=lambda x: x[1].total_r, default=(None, None))
        if best_kz[0]:
            report += f"  🏆 Best Killzone: {best_kz[0]} ({best_kz[1].total_r:+.1f}R)\n"

        # Best day
        best_day = max(self.by_day.items(), key=lambda x: x[1].total_r, default=(None, None))
        if best_day[0]:
            report += f"  🏆 Best Day: {best_day[0]} ({best_day[1].total_r:+.1f}R)\n"

        # Best pair
        best_pair = max(self.by_pair.items(), key=lambda x: x[1].total_r, default=(None, None))
        if best_pair[0]:
            report += f"  🏆 Best Pair: {best_pair[0]} ({best_pair[1].total_r:+.1f}R)\n"

        # Best model
        best_model = max(self.by_model.items(), key=lambda x: x[1].total_r, default=(None, None))
        if best_model[0]:
            report += f"  🏆 Best Model: {best_model[0]} ({best_model[1].total_r:+.1f}R)\n"

        report += "\n" + "═" * 50

        return report

    def get_edge_recommendation(self) -> str:
        """Get recommendation for trading edge."""
        rec = "\n🎯 YOUR EDGE (Based on Data):\n"

        # Best killzone
        best_kz = max(self.by_killzone.items(), key=lambda x: x[1].win_rate if x[1].total_trades >= 3 else 0, default=(None, None))
        if best_kz[0] and best_kz[1].total_trades >= 3:
            rec += f"  → Focus on {best_kz[0]} session ({best_kz[1].win_rate:.0f}% win rate)\n"

        # Best pair
        best_pair = max(self.by_pair.items(), key=lambda x: x[1].win_rate if x[1].total_trades >= 3 else 0, default=(None, None))
        if best_pair[0] and best_pair[1].total_trades >= 3:
            rec += f"  → Focus on {best_pair[0]} ({best_pair[1].win_rate:.0f}% win rate)\n"

        # Best model
        best_model = max(self.by_model.items(), key=lambda x: x[1].win_rate if x[1].total_trades >= 3 else 0, default=(None, None))
        if best_model[0] and best_model[1].total_trades >= 3:
            rec += f"  → Focus on {best_model[0]} setups ({best_model[1].win_rate:.0f}% win rate)\n"

        # Avoid worst
        worst_day = min(self.by_day.items(), key=lambda x: x[1].total_r if x[1].total_trades >= 2 else 999, default=(None, None))
        if worst_day[0] and worst_day[1].total_trades >= 2 and worst_day[1].total_r < 0:
            rec += f"  → Consider avoiding {worst_day[0]}s ({worst_day[1].total_r:+.1f}R)\n"

        return rec


def main():
    """Generate statistics report."""
    stats = SessionStatistics()
    stats.load_trades("ashton")

    print(stats.generate_report())
    print(stats.get_edge_recommendation())


if __name__ == "__main__":
    main()
