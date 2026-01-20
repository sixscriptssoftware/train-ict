"""
VEX Setup Grader - Score trading setups against your template trade criteria.

Grades setups on a 1-10 scale based on:
- Template trade confluence factors
- Historical performance on similar setups
- Current market conditions
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
JOURNAL_DIR = PROJECT_ROOT / "journal" / "ashton"


@dataclass
class SetupCriteria:
    """Individual setup criterion with score."""
    name: str
    present: bool
    weight: float
    notes: str = ""


@dataclass
class SetupGrade:
    """Complete setup grade with all criteria."""
    pair: str
    direction: str  # LONG or SHORT
    timestamp: str
    total_score: float
    grade_letter: str
    criteria: List[Dict]
    recommendation: str
    similar_trades: List[Dict]
    warnings: List[str]


class SetupGrader:
    """
    Grades trading setups against Ashton's template trade criteria.
    
    Template Trade Criteria (from Jan 16, 2026 FTMO-passing trade):
    1. Prior displacement establishes bias
    2. 4H FVG as primary entry zone
    3. 15M OB + 15M FVG confluence
    4. CBDR setup present (<30 pips)
    5. Asian range liquidity swept
    6. Clear liquidity target
    7. Stop accounts for deeper retest
    8. TP at CBDR extension
    """
    
    # Template trade criteria with weights
    CRITERIA = {
        "displacement": {
            "name": "Prior Displacement",
            "description": "Clear displacement establishing directional bias",
            "weight": 1.5,
            "required": True
        },
        "htf_fvg": {
            "name": "4H FVG Entry Zone",
            "description": "4H Fair Value Gap as primary entry zone",
            "weight": 1.5,
            "required": True
        },
        "ltf_confluence": {
            "name": "15M OB + FVG Confluence",
            "description": "15M Order Block with FVG overlap",
            "weight": 1.5,
            "required": False
        },
        "cbdr_setup": {
            "name": "CBDR Setup (<30 pips)",
            "description": "Central Bank Dealer Range under 30 pips",
            "weight": 1.0,
            "required": False
        },
        "liquidity_sweep": {
            "name": "Liquidity Swept",
            "description": "Asian/London range liquidity already swept",
            "weight": 1.5,
            "required": True
        },
        "clear_target": {
            "name": "Clear Liquidity Target",
            "description": "Obvious target (swing high/low, EQH/EQL)",
            "weight": 1.0,
            "required": True
        },
        "stop_placement": {
            "name": "Stop Accounts for Retest",
            "description": "Stop below/above potential deeper retest",
            "weight": 1.0,
            "required": True
        },
        "rr_ratio": {
            "name": "Minimum 2:1 R:R",
            "description": "Risk-reward ratio at least 2:1",
            "weight": 1.0,
            "required": True
        },
        "killzone": {
            "name": "In Optimal Killzone",
            "description": "Trade in London or NY AM session",
            "weight": 0.5,
            "required": False
        },
        "daily_bias": {
            "name": "Aligned with Daily Bias",
            "description": "Trade direction matches Daily chart bias",
            "weight": 1.0,
            "required": True
        }
    }
    
    GRADE_THRESHOLDS = {
        "A+": 9.0,
        "A": 8.0,
        "B+": 7.0,
        "B": 6.0,
        "C": 5.0,
        "D": 4.0,
        "F": 0.0
    }
    
    def __init__(self):
        self.trading_profile = self._load_json(MEMORY_DIR / "trading_profile.json")
        self.rules = self._load_json(MEMORY_DIR / "rules.json")
        self.trade_history = self._load_trade_history()
    
    def _load_json(self, path: Path) -> Dict:
        """Load JSON file."""
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def _load_trade_history(self) -> List[Dict]:
        """Load past trades from journal."""
        trades = []
        db_path = JOURNAL_DIR / "trades_database.json"
        if db_path.exists():
            with open(db_path) as f:
                data = json.load(f)
                trades = data.get("trades", [])
        return trades
    
    def grade_setup(
        self,
        pair: str,
        direction: str,
        criteria_present: Dict[str, bool],
        entry_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        notes: Dict[str, str] = None
    ) -> SetupGrade:
        """
        Grade a trading setup against template criteria.
        
        Args:
            pair: Trading pair (e.g., "EURUSD")
            direction: "LONG" or "SHORT"
            criteria_present: Dict mapping criterion key to True/False
            entry_price: Optional entry price for R:R calculation
            stop_price: Optional stop price
            target_price: Optional target price
            notes: Optional notes for each criterion
        
        Returns:
            SetupGrade with score, letter grade, and recommendations
        """
        notes = notes or {}
        scored_criteria = []
        total_points = 0
        max_points = 0
        warnings = []
        
        # Score each criterion
        for key, criterion in self.CRITERIA.items():
            present = criteria_present.get(key, False)
            weight = criterion["weight"]
            max_points += weight
            
            if present:
                total_points += weight
            elif criterion["required"]:
                warnings.append(f"⚠️ MISSING REQUIRED: {criterion['name']}")
            
            scored_criteria.append({
                "key": key,
                "name": criterion["name"],
                "description": criterion["description"],
                "present": present,
                "weight": weight,
                "required": criterion["required"],
                "notes": notes.get(key, "")
            })
        
        # Calculate R:R if prices provided
        if entry_price and stop_price and target_price:
            risk = abs(entry_price - stop_price)
            reward = abs(target_price - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio < 2.0:
                warnings.append(f"⚠️ R:R is {rr_ratio:.1f}:1 (minimum 2:1 required)")
                # Override the rr_ratio criterion
                for c in scored_criteria:
                    if c["key"] == "rr_ratio":
                        c["present"] = False
                        c["notes"] = f"Actual R:R: {rr_ratio:.1f}:1"
                        total_points -= self.CRITERIA["rr_ratio"]["weight"]
        
        # Calculate final score (normalize to 10-point scale)
        score = (total_points / max_points) * 10 if max_points > 0 else 0
        
        # Determine letter grade
        grade_letter = "F"
        for letter, threshold in self.GRADE_THRESHOLDS.items():
            if score >= threshold:
                grade_letter = letter
                break
        
        # Find similar past trades
        similar_trades = self._find_similar_trades(pair, direction, criteria_present)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(score, grade_letter, warnings, similar_trades)
        
        return SetupGrade(
            pair=pair,
            direction=direction,
            timestamp=datetime.now().isoformat(),
            total_score=round(score, 1),
            grade_letter=grade_letter,
            criteria=scored_criteria,
            recommendation=recommendation,
            similar_trades=similar_trades,
            warnings=warnings
        )
    
    def _find_similar_trades(
        self,
        pair: str,
        direction: str,
        criteria: Dict[str, bool]
    ) -> List[Dict]:
        """Find similar past trades based on criteria overlap."""
        similar = []
        
        for trade in self.trade_history:
            if trade.get("pair") == pair or trade.get("direction") == direction:
                # Calculate similarity score
                trade_criteria = trade.get("criteria", {})
                overlap = sum(1 for k, v in criteria.items() if trade_criteria.get(k) == v)
                similarity = overlap / len(criteria) if criteria else 0
                
                if similarity > 0.5:  # At least 50% similar
                    similar.append({
                        "date": trade.get("date"),
                        "pair": trade.get("pair"),
                        "direction": trade.get("direction"),
                        "result": trade.get("result"),
                        "pnl": trade.get("pnl"),
                        "similarity": round(similarity * 100)
                    })
        
        return similar[:5]  # Return top 5
    
    def _generate_recommendation(
        self,
        score: float,
        grade: str,
        warnings: List[str],
        similar_trades: List[Dict]
    ) -> str:
        """Generate trade recommendation based on grade."""
        
        if grade in ["A+", "A"]:
            rec = "✅ HIGH CONFIDENCE - This is your template trade setup. Execute with conviction."
            if grade == "A+":
                rec += " Consider sizing up (1.5x normal)."
        elif grade in ["B+", "B"]:
            rec = "🟡 MODERATE CONFIDENCE - Solid setup but missing some confluence. Trade normal size."
        elif grade == "C":
            rec = "⚠️ LOW CONFIDENCE - Below your standard. Consider passing or taking reduced size."
        else:
            rec = "❌ DO NOT TRADE - This setup does not meet your minimum criteria."
        
        # Add warning context
        if warnings:
            rec += f"\n\n⚠️ {len(warnings)} warning(s) flagged."
        
        # Add historical context
        if similar_trades:
            wins = sum(1 for t in similar_trades if t.get("result") == "WIN")
            total = len(similar_trades)
            if total > 0:
                rec += f"\n\n📊 Similar setups: {wins}/{total} wins ({wins/total*100:.0f}%)"
        
        return rec
    
    def interactive_grade(self, pair: str, direction: str) -> SetupGrade:
        """
        Interactive grading - prompts for each criterion.
        For CLI use.
        """
        print(f"\n{'='*60}")
        print(f"  SETUP GRADER: {pair} {direction}")
        print(f"{'='*60}\n")
        
        criteria_present = {}
        notes = {}
        
        for key, criterion in self.CRITERIA.items():
            required_tag = " [REQUIRED]" if criterion["required"] else ""
            print(f"\n{criterion['name']}{required_tag}")
            print(f"  {criterion['description']}")
            
            while True:
                response = input("  Present? (y/n): ").strip().lower()
                if response in ['y', 'yes', '1', 'true']:
                    criteria_present[key] = True
                    break
                elif response in ['n', 'no', '0', 'false']:
                    criteria_present[key] = False
                    break
                else:
                    print("  Please enter 'y' or 'n'")
            
            note = input("  Notes (optional): ").strip()
            if note:
                notes[key] = note
        
        # Get prices for R:R calculation
        print("\n--- PRICE LEVELS (optional, press Enter to skip) ---")
        entry = input("Entry price: ").strip()
        stop = input("Stop price: ").strip()
        target = input("Target price: ").strip()
        
        entry_price = float(entry) if entry else None
        stop_price = float(stop) if stop else None
        target_price = float(target) if target else None
        
        return self.grade_setup(
            pair=pair,
            direction=direction,
            criteria_present=criteria_present,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            notes=notes
        )
    
    def quick_grade(self, pair: str, direction: str, **kwargs) -> SetupGrade:
        """
        Quick grade with keyword arguments for criteria.
        
        Example:
            grader.quick_grade(
                "EURUSD", "LONG",
                displacement=True,
                htf_fvg=True,
                ltf_confluence=True,
                liquidity_sweep=True,
                clear_target=True,
                stop_placement=True,
                rr_ratio=True,
                daily_bias=True
            )
        """
        criteria_present = {k: kwargs.get(k, False) for k in self.CRITERIA.keys()}
        return self.grade_setup(pair, direction, criteria_present)
    
    def format_grade_report(self, grade: SetupGrade) -> str:
        """Format grade as printable report."""
        lines = []
        lines.append("")
        lines.append("═" * 60)
        lines.append(f"  SETUP GRADE: {grade.pair} {grade.direction}")
        lines.append("═" * 60)
        lines.append("")
        
        # Big score display
        score_bar = "█" * int(grade.total_score) + "░" * (10 - int(grade.total_score))
        lines.append(f"  Score: [{score_bar}] {grade.total_score}/10 ({grade.grade_letter})")
        lines.append("")
        
        # Criteria breakdown
        lines.append("  CRITERIA BREAKDOWN:")
        lines.append("  " + "-" * 50)
        
        for c in grade.criteria:
            status = "✅" if c["present"] else "❌"
            req = "*" if c["required"] else " "
            lines.append(f"  {status} {c['name']}{req} (weight: {c['weight']})")
            if c["notes"]:
                lines.append(f"      └─ {c['notes']}")
        
        lines.append("")
        lines.append("  * = Required criterion")
        
        # Warnings
        if grade.warnings:
            lines.append("")
            lines.append("  ⚠️  WARNINGS:")
            for w in grade.warnings:
                lines.append(f"  {w}")
        
        # Similar trades
        if grade.similar_trades:
            lines.append("")
            lines.append("  📊 SIMILAR PAST TRADES:")
            for t in grade.similar_trades:
                result_icon = "✅" if t["result"] == "WIN" else "❌"
                lines.append(f"  {result_icon} {t['date']} {t['pair']} {t['direction']} → {t['pnl']} ({t['similarity']}% similar)")
        
        # Recommendation
        lines.append("")
        lines.append("  " + "-" * 50)
        lines.append("  RECOMMENDATION:")
        for line in grade.recommendation.split("\n"):
            lines.append(f"  {line}")
        
        lines.append("")
        lines.append("═" * 60)
        
        return "\n".join(lines)


def main():
    """CLI entry point for setup grader."""
    import sys
    
    grader = SetupGrader()
    
    if len(sys.argv) >= 3:
        pair = sys.argv[1].upper()
        direction = sys.argv[2].upper()
        
        if direction not in ["LONG", "SHORT"]:
            print("Direction must be LONG or SHORT")
            sys.exit(1)
        
        grade = grader.interactive_grade(pair, direction)
        print(grader.format_grade_report(grade))
    else:
        print("Usage: python setup_grader.py <PAIR> <LONG|SHORT>")
        print("Example: python setup_grader.py EURUSD LONG")


if __name__ == "__main__":
    main()
