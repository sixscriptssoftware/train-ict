"""
VEX Trade Learning Engine

This is where I actually LEARN from trades.
Every win, every loss, every pattern - I record it and remember it.

The goal: Never make the same mistake twice.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from zoneinfo import ZoneInfo
from collections import defaultdict

NY_TZ = ZoneInfo("America/New_York")


@dataclass
class TradeLesson:
    """A lesson learned from a trade"""
    timestamp: str
    trade_id: str
    symbol: str
    model: str
    outcome: str  # win, loss, breakeven
    pnl: float
    rr_achieved: float
    
    # What I learned
    lesson: str
    category: str  # "entry", "exit", "risk", "psychology", "timing"
    
    # Context
    killzone: str
    confluences: List[str]
    market_conditions: str
    
    # Importance (higher = remember more)
    importance: float = 1.0


@dataclass
class PatternStats:
    """Statistics for a trading pattern"""
    pattern_name: str
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_rr: float = 0.0
    win_rate: float = 0.0
    
    # Best/worst conditions
    best_killzone: str = ""
    worst_killzone: str = ""
    best_confluences: List[str] = field(default_factory=list)
    
    def update(self, is_win: bool, pnl: float, rr: float):
        self.total_trades += 1
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        self.total_pnl += pnl
        self.win_rate = self.wins / self.total_trades if self.total_trades > 0 else 0
        # Running average of R:R
        self.avg_rr = ((self.avg_rr * (self.total_trades - 1)) + rr) / self.total_trades


class TradeLearner:
    """
    I learn from every trade.
    
    After each trade closes, I:
    1. Analyze what happened
    2. Extract lessons
    3. Update my pattern statistics
    4. Store insights for future use
    
    Before each trade, I:
    1. Check if this setup has worked before
    2. Recall relevant lessons
    3. Flag potential issues based on past failures
    """
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path(__file__).parent.parent.parent.parent / "data" / "learning"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Learning files
        self.lessons_file = self.data_dir / "trade_lessons.json"
        self.patterns_file = self.data_dir / "pattern_stats.json"
        self.insights_file = self.data_dir / "insights.json"
        self.memory_file = self.data_dir / "vex_memory.json"
        
        # Load existing data
        self.lessons: List[TradeLesson] = self._load_lessons()
        self.patterns: Dict[str, PatternStats] = self._load_patterns()
        self.insights: Dict = self._load_insights()
        self.memory: Dict = self._load_memory()
        
        # Connect to KnowledgeManager for concept lookups
        self._knowledge_manager = None
    
    @property
    def knowledge(self):
        """Lazy-load knowledge manager to avoid circular imports"""
        if self._knowledge_manager is None:
            try:
                from ict_agent.learning.knowledge_manager import get_knowledge_manager
                self._knowledge_manager = get_knowledge_manager()
            except ImportError:
                pass
        return self._knowledge_manager
    
    def _load_lessons(self) -> List[TradeLesson]:
        """Load trade lessons"""
        if self.lessons_file.exists():
            with open(self.lessons_file) as f:
                data = json.load(f)
                return [TradeLesson(**l) for l in data]
        return []
    
    def _load_patterns(self) -> Dict[str, PatternStats]:
        """Load pattern statistics"""
        if self.patterns_file.exists():
            with open(self.patterns_file) as f:
                data = json.load(f)
                return {k: PatternStats(**v) for k, v in data.items()}
        return {}
    
    def _load_insights(self) -> Dict:
        """Load insights"""
        if self.insights_file.exists():
            with open(self.insights_file) as f:
                return json.load(f)
        return {
            "best_setups": [],
            "worst_setups": [],
            "rules_learned": [],
            "patterns_to_avoid": [],
            "optimal_conditions": {},
        }
    
    def _load_memory(self) -> Dict:
        """Load VEX's memory - things I should always remember"""
        if self.memory_file.exists():
            with open(self.memory_file) as f:
                return json.load(f)
        return {
            "golden_rules": [],
            "pair_specific": {},
            "model_specific": {},
            "time_specific": {},
            "psychological_triggers": [],
            "ashton_patterns": [],  # Patterns I've noticed in Ashton's trading
        }
    
    def _save_all(self):
        """Save all learning data"""
        with open(self.lessons_file, 'w') as f:
            json.dump([asdict(l) for l in self.lessons], f, indent=2)
        
        with open(self.patterns_file, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.patterns.items()}, f, indent=2)
        
        with open(self.insights_file, 'w') as f:
            json.dump(self.insights, f, indent=2)
        
        with open(self.memory_file, 'w') as f:
            json.dump(self.memory, f, indent=2)
    
    # =========================================================================
    # LEARN FROM TRADE
    # =========================================================================
    
    def learn_from_trade(
        self,
        trade_id: str,
        symbol: str,
        model: str,
        outcome: str,  # "win", "loss", "breakeven"
        pnl: float,
        rr_achieved: float,
        killzone: str,
        confluences: List[str],
        entry_price: float,
        exit_price: float,
        stop_loss: float,
        take_profit: float,
        notes: str = "",
    ) -> TradeLesson:
        """
        Learn from a completed trade.
        
        This is called EVERY time a trade closes.
        """
        # Analyze what happened
        lesson_text, category = self._analyze_trade(
            outcome=outcome,
            model=model,
            killzone=killzone,
            confluences=confluences,
            rr_achieved=rr_achieved,
            notes=notes,
        )
        
        # Create lesson
        lesson = TradeLesson(
            timestamp=datetime.now(NY_TZ).isoformat(),
            trade_id=trade_id,
            symbol=symbol,
            model=model,
            outcome=outcome,
            pnl=pnl,
            rr_achieved=rr_achieved,
            lesson=lesson_text,
            category=category,
            killzone=killzone,
            confluences=confluences,
            market_conditions=self._assess_conditions(confluences),
            importance=self._calculate_importance(outcome, pnl, rr_achieved),
        )
        
        self.lessons.append(lesson)
        
        # Update pattern statistics
        self._update_patterns(lesson)
        
        # Update insights if significant
        self._update_insights(lesson)
        
        # Save
        self._save_all()
        
        print(f"📚 Learned from {trade_id}: {lesson_text}")
        
        return lesson
    
    def _analyze_trade(
        self,
        outcome: str,
        model: str,
        killzone: str,
        confluences: List[str],
        rr_achieved: float,
        notes: str,
    ) -> Tuple[str, str]:
        """Analyze trade and extract lesson"""
        
        if outcome == "win":
            if rr_achieved >= 3:
                lesson = f"{model} with {len(confluences)}+ confluences in {killzone} = high R winner"
                category = "entry"
            elif rr_achieved >= 2:
                lesson = f"{model} in {killzone} working well - solid setup"
                category = "entry"
            else:
                lesson = f"Win but low R ({rr_achieved:.1f}) - consider holding longer"
                category = "exit"
        
        elif outcome == "loss":
            if rr_achieved < -1:
                lesson = f"Loss beyond 1R on {model} - stop management issue?"
                category = "risk"
            else:
                # Analyze why
                if len(confluences) < 3:
                    lesson = f"Loss with only {len(confluences)} confluences - need more confirmation"
                    category = "entry"
                else:
                    lesson = f"{model} loss in {killzone} - check if timing was off"
                    category = "timing"
        
        else:  # breakeven
            lesson = "Breakeven - good risk management, setup didn't follow through"
            category = "exit"
        
        # Add notes context if provided
        if notes:
            lesson += f" | Note: {notes[:100]}"
        
        return lesson, category
    
    def _assess_conditions(self, confluences: List[str]) -> str:
        """Assess market conditions from confluences"""
        if len(confluences) >= 5:
            return "high_confluence"
        elif len(confluences) >= 3:
            return "moderate_confluence"
        else:
            return "low_confluence"
    
    def _calculate_importance(self, outcome: str, pnl: float, rr: float) -> float:
        """Calculate how important this lesson is (0-10)"""
        importance = 5.0  # Base
        
        # Big wins/losses are more important
        if abs(pnl) > 200:
            importance += 2
        
        # Extreme R:R is important
        if abs(rr) > 3:
            importance += 2
        
        # Losses teach more
        if outcome == "loss":
            importance += 1
        
        return min(importance, 10.0)
    
    def _update_patterns(self, lesson: TradeLesson):
        """Update pattern statistics"""
        # Model pattern
        model_key = f"model_{lesson.model}"
        if model_key not in self.patterns:
            self.patterns[model_key] = PatternStats(pattern_name=lesson.model)
        
        is_win = lesson.outcome == "win"
        self.patterns[model_key].update(is_win, lesson.pnl, lesson.rr_achieved)
        
        # Killzone pattern
        kz_key = f"killzone_{lesson.killzone}"
        if kz_key not in self.patterns:
            self.patterns[kz_key] = PatternStats(pattern_name=lesson.killzone)
        self.patterns[kz_key].update(is_win, lesson.pnl, lesson.rr_achieved)
        
        # Symbol pattern
        sym_key = f"symbol_{lesson.symbol}"
        if sym_key not in self.patterns:
            self.patterns[sym_key] = PatternStats(pattern_name=lesson.symbol)
        self.patterns[sym_key].update(is_win, lesson.pnl, lesson.rr_achieved)
    
    def _update_insights(self, lesson: TradeLesson):
        """Update insights if this trade was significant"""
        if lesson.importance >= 7:
            if lesson.outcome == "win":
                self.insights["best_setups"].append({
                    "model": lesson.model,
                    "killzone": lesson.killzone,
                    "confluences": lesson.confluences,
                    "rr": lesson.rr_achieved,
                    "timestamp": lesson.timestamp,
                })
                # Keep only top 10
                self.insights["best_setups"] = sorted(
                    self.insights["best_setups"],
                    key=lambda x: x.get("rr", 0),
                    reverse=True
                )[:10]
            
            elif lesson.outcome == "loss" and lesson.importance >= 8:
                self.insights["worst_setups"].append({
                    "model": lesson.model,
                    "killzone": lesson.killzone,
                    "lesson": lesson.lesson,
                    "timestamp": lesson.timestamp,
                })
    
    # =========================================================================
    # RECALL BEFORE TRADE
    # =========================================================================
    
    def recall_for_setup(
        self,
        symbol: str,
        model: str,
        killzone: str,
        confluences: List[str],
    ) -> Dict:
        """
        Recall relevant lessons before taking a trade.
        
        Returns warnings, confidence, and relevant lessons.
        """
        result = {
            "confidence": 0.5,  # Base confidence
            "warnings": [],
            "relevant_lessons": [],
            "pattern_stats": {},
            "recommendation": "neutral",
        }
        
        # Check model stats
        model_key = f"model_{model}"
        if model_key in self.patterns:
            stats = self.patterns[model_key]
            result["pattern_stats"]["model"] = {
                "win_rate": stats.win_rate,
                "avg_rr": stats.avg_rr,
                "total_trades": stats.total_trades,
            }
            
            if stats.total_trades >= 5:
                if stats.win_rate < 0.4:
                    result["warnings"].append(f"⚠️ {model} has {stats.win_rate:.0%} win rate")
                    result["confidence"] -= 0.2
                elif stats.win_rate > 0.6:
                    result["confidence"] += 0.15
        
        # Check killzone stats
        kz_key = f"killzone_{killzone}"
        if kz_key in self.patterns:
            stats = self.patterns[kz_key]
            result["pattern_stats"]["killzone"] = {
                "win_rate": stats.win_rate,
                "avg_rr": stats.avg_rr,
            }
            
            if stats.total_trades >= 5 and stats.win_rate < 0.4:
                result["warnings"].append(f"⚠️ {killzone} killzone has low win rate")
        
        # Check symbol stats
        sym_key = f"symbol_{symbol}"
        if sym_key in self.patterns:
            stats = self.patterns[sym_key]
            result["pattern_stats"]["symbol"] = {
                "win_rate": stats.win_rate,
                "total_pnl": stats.total_pnl,
            }
        
        # Find relevant lessons
        for lesson in self.lessons[-50:]:  # Last 50 trades
            relevance = 0
            if lesson.symbol == symbol:
                relevance += 2
            if lesson.model == model:
                relevance += 2
            if lesson.killzone == killzone:
                relevance += 1
            
            if relevance >= 2:
                result["relevant_lessons"].append({
                    "lesson": lesson.lesson,
                    "outcome": lesson.outcome,
                    "relevance": relevance,
                })
        
        # Sort by relevance
        result["relevant_lessons"] = sorted(
            result["relevant_lessons"],
            key=lambda x: x["relevance"],
            reverse=True
        )[:5]
        
        # Check for red flags
        for lesson in result["relevant_lessons"]:
            if lesson["outcome"] == "loss" and lesson["relevance"] >= 3:
                result["warnings"].append(f"⚠️ Similar setup lost: {lesson['lesson'][:50]}")
        
        # === INTEGRATE KNOWLEDGE MANAGER ===
        # Get concept info and user teachings from knowledge base
        if self.knowledge:
            try:
                kb_recall = self.knowledge.recall_for_setup(
                    model=model,
                    concepts_involved=confluences,
                    session=killzone,
                )
                # Add user teachings as warnings/notes
                for teaching in kb_recall.get("user_teachings", [])[:3]:
                    result["warnings"].append(f"💡 {teaching[:80]}")
                
                # Add concept rules
                result["concept_rules"] = []
                for concept_info in kb_recall.get("concept_info", []):
                    for rule in concept_info.get("rules", []):
                        result["concept_rules"].append(rule)
            except Exception as e:
                pass  # Knowledge manager not critical
        
        # Overall recommendation
        if len(result["warnings"]) >= 2:
            result["recommendation"] = "caution"
        elif result["confidence"] >= 0.6:
            result["recommendation"] = "favorable"
        
        return result
    
    # =========================================================================
    # ADD MANUAL LESSONS
    # =========================================================================
    
    def add_rule(self, rule: str, source: str = "observation"):
        """Add a rule I've learned"""
        self.insights["rules_learned"].append({
            "timestamp": datetime.now(NY_TZ).isoformat(),
            "lesson": rule,
            "source": source,
        })
        self._save_all()
        print(f"📖 Rule added: {rule}")
    
    def add_pattern_to_avoid(self, pattern: str, reason: str):
        """Add a pattern to avoid"""
        self.insights["patterns_to_avoid"].append({
            "pattern": pattern,
            "reason": reason,
            "timestamp": datetime.now(NY_TZ).isoformat(),
        })
        self._save_all()
        print(f"🚫 Pattern to avoid: {pattern}")
    
    def remember(self, key: str, value: str, category: str = "golden_rules"):
        """Store something in permanent memory"""
        if category not in self.memory:
            self.memory[category] = []
        
        self.memory[category].append({
            "key": key,
            "value": value,
            "timestamp": datetime.now(NY_TZ).isoformat(),
        })
        self._save_all()
        print(f"🧠 Remembered: {key}")
    
    # =========================================================================
    # SIMPLE API FOR AGENT JOURNAL
    # =========================================================================
    
    def record_trade(
        self,
        symbol: str,
        direction: str,  # "LONG" or "SHORT"
        model: str,
        session: str,  # killzone name
        outcome: str,  # "win", "loss", "breakeven"
        rr_achieved: float = 0.0,
        confluences: List[str] = None,
        notes: str = "",
    ) -> TradeLesson:
        """
        Simple method for agent journal to record trades.
        Wrapper around learn_from_trade with sensible defaults.
        """
        import uuid
        trade_id = f"VEX_{datetime.now(NY_TZ).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        return self.learn_from_trade(
            trade_id=trade_id,
            symbol=symbol,
            model=model,
            outcome=outcome,
            pnl=0.0,  # Not always available
            rr_achieved=rr_achieved,
            killzone=session,
            confluences=confluences or [],
            entry_price=0.0,
            exit_price=0.0,
            stop_loss=0.0,
            take_profit=0.0,
            notes=notes,
        )
    
    def get_recommendation(
        self,
        symbol: str,
        direction: str,
        model: str,
        session: str,
        confluences: List[str] = None,
    ) -> Dict:
        """
        Simple method for agent journal to get pre-trade recommendation.
        Alias for recall_for_setup.
        """
        return self.recall_for_setup(
            symbol=symbol,
            model=model,
            killzone=session,
            confluences=confluences or [],
        )
    
    # =========================================================================
    # REPORTING
    # =========================================================================
    
    def get_summary(self) -> str:
        """Get learning summary"""
        lines = [
            "=" * 50,
            "📚 VEX LEARNING SUMMARY",
            "=" * 50,
            f"Total lessons learned: {len(self.lessons)}",
            f"Patterns tracked: {len(self.patterns)}",
            f"Rules: {len(self.insights.get('rules_learned', []))}",
            "",
            "📊 Top Performing Patterns:",
        ]
        
        # Best patterns by win rate
        sorted_patterns = sorted(
            [(k, v) for k, v in self.patterns.items() if v.total_trades >= 3],
            key=lambda x: x[1].win_rate,
            reverse=True
        )[:5]
        
        for name, stats in sorted_patterns:
            lines.append(f"  {name}: {stats.win_rate:.0%} win ({stats.total_trades} trades)")
        
        lines.append("")
        lines.append("⚠️ Patterns to Avoid:")
        for p in self.insights.get("patterns_to_avoid", [])[:3]:
            lines.append(f"  - {p['pattern']}")
        
        return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    learner = TradeLearner()
    
    # Test learning from a trade
    lesson = learner.learn_from_trade(
        trade_id="TEST_001",
        symbol="EUR_USD",
        model="SELL_MODEL",
        outcome="win",
        pnl=150.0,
        rr_achieved=2.5,
        killzone="ny_am",
        confluences=["FVG", "OB", "BSL_sweep", "bearish_structure"],
        entry_price=1.1650,
        exit_price=1.1600,
        stop_loss=1.1670,
        take_profit=1.1600,
        notes="Clean setup, waited for sweep",
    )
    
    print("\n" + learner.get_summary())
