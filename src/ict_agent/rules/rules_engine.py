"""
VEX Rules Engine - Enforce trading rules and track violations.

Features:
- Real-time rule violation checking
- Pre-trade rule validation
- Violation tracking and history
- Psychology-based warnings
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
JOURNAL_DIR = PROJECT_ROOT / "journal" / "ashton"
TRADES_DB = JOURNAL_DIR / "trades_database.json"


class RuleSeverity(Enum):
    HARD = "hard"  # Non-negotiable, must not violate
    SOFT = "soft"  # Recommended, can be flexible


class ViolationType(Enum):
    WARNING = "warning"  # Caution, not yet violated
    VIOLATION = "violation"  # Rule broken
    BLOCKED = "blocked"  # Cannot proceed


@dataclass
class RuleCheck:
    """Result of checking a single rule."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: str
    message: str
    suggestion: str = ""


@dataclass
class RuleCheckResult:
    """Complete result of all rule checks."""
    timestamp: str
    pair: str
    direction: str
    all_passed: bool
    hard_rules_passed: bool
    checks: List[Dict]
    warnings: List[str]
    blockers: List[str]
    recommendation: str


class RulesEngine:
    """
    Enforces Ashton's trading rules and tracks violations.
    
    Hard Rules (Non-negotiable):
    1. Two Strike Rule - Stopped twice on a pair = stop trading it
    2. No trading against Daily bias
    3. Max 3 trades per day
    4. No trading Fridays after 12pm EST
    5. Minimum 2:1 R:R
    6. Stop must account for spread
    7. Pre-trade journal BEFORE entering
    
    Soft Rules (Flexible):
    1. Prefer London and NY AM sessions
    2. Size up only on A+ setups (7+ confluence)
    3. Wait for liquidity sweep before entry
    """
    
    def __init__(self):
        self.rules = self._load_rules()
        self.triggers = self._load_triggers()
        self.trades_db = self._load_trades()
    
    def _load_rules(self) -> Dict:
        """Load rules from memory."""
        path = MEMORY_DIR / "rules.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {"hard_rules": [], "soft_rules": []}
    
    def _save_rules(self):
        """Save rules to memory."""
        path = MEMORY_DIR / "rules.json"
        with open(path, "w") as f:
            json.dump(self.rules, f, indent=2)
    
    def _load_triggers(self) -> Dict:
        """Load psychology triggers."""
        path = MEMORY_DIR / "triggers.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def _load_trades(self) -> Dict:
        """Load trades database."""
        if TRADES_DB.exists():
            with open(TRADES_DB) as f:
                return json.load(f)
        return {"trades": []}
    
    def get_today_trades(self) -> List[Dict]:
        """Get trades from today."""
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            t for t in self.trades_db.get("trades", [])
            if t.get("created_at", "").startswith(today)
        ]
    
    def get_pair_strikes(self, pair: str) -> int:
        """Count consecutive losses on a pair (strikes)."""
        pair_trades = [
            t for t in self.trades_db.get("trades", [])
            if t.get("pre_trade", {}).get("pair") == pair
            and t.get("status") == "closed"
        ]
        
        # Sort by date descending
        pair_trades.sort(key=lambda x: x.get("exit_time", ""), reverse=True)
        
        strikes = 0
        for trade in pair_trades:
            if trade.get("result") == "LOSS":
                strikes += 1
            else:
                break  # Reset on win
        
        return strikes
    
    def check_two_strike_rule(self, pair: str) -> RuleCheck:
        """Check Two Strike Rule - stopped twice = stop trading that pair."""
        strikes = self.get_pair_strikes(pair)
        
        passed = strikes < 2
        
        if strikes >= 2:
            message = f"❌ TWO STRIKES on {pair}! You've been stopped out {strikes} times in a row."
            suggestion = "STOP trading this pair today. Come back tomorrow with fresh eyes."
        elif strikes == 1:
            message = f"⚠️ One strike on {pair}. One more loss and you're done with this pair today."
            suggestion = "Be extra selective. Only take A+ setups."
        else:
            message = f"✅ No strikes on {pair}. Clear to trade."
            suggestion = ""
        
        return RuleCheck(
            rule_id="two_strike",
            rule_name="Two Strike Rule",
            passed=passed,
            severity=RuleSeverity.HARD.value,
            message=message,
            suggestion=suggestion
        )
    
    def check_daily_bias_alignment(self, pair: str, direction: str, daily_bias: str) -> RuleCheck:
        """Check if trade aligns with daily bias."""
        # Direction should match bias
        aligned = (
            (direction == "LONG" and daily_bias == "BULLISH") or
            (direction == "SHORT" and daily_bias == "BEARISH") or
            daily_bias == "NEUTRAL"
        )
        
        if aligned:
            message = f"✅ {direction} aligns with {daily_bias} daily bias."
            suggestion = ""
        else:
            message = f"❌ {direction} AGAINST {daily_bias} daily bias!"
            suggestion = "Trading against daily bias is forbidden. Wait for alignment or find another pair."
        
        return RuleCheck(
            rule_id="daily_bias",
            rule_name="Daily Bias Alignment",
            passed=aligned,
            severity=RuleSeverity.HARD.value,
            message=message,
            suggestion=suggestion
        )
    
    def check_max_trades(self) -> RuleCheck:
        """Check max 3 trades per day rule."""
        today_trades = self.get_today_trades()
        count = len(today_trades)
        
        passed = count < 3
        
        if count >= 3:
            message = f"❌ MAX TRADES REACHED! You've taken {count} trades today."
            suggestion = "STOP trading. You've hit your daily limit. Journal and review instead."
        elif count == 2:
            message = f"⚠️ {count}/3 trades today. This would be your LAST trade."
            suggestion = "Make it count. Only take if it's an A+ setup."
        else:
            message = f"✅ {count}/3 trades today. {3-count} remaining."
            suggestion = ""
        
        return RuleCheck(
            rule_id="max_trades",
            rule_name="Max 3 Trades/Day",
            passed=passed,
            severity=RuleSeverity.HARD.value,
            message=message,
            suggestion=suggestion
        )
    
    def check_friday_restriction(self) -> RuleCheck:
        """Check no trading Fridays after 12pm EST rule."""
        now = datetime.now()
        is_friday = now.weekday() == 4
        hour = now.hour
        
        # Assuming system time is EST (adjust if needed)
        is_restricted = is_friday and hour >= 12
        passed = not is_restricted
        
        if is_restricted:
            message = "❌ FRIDAY AFTERNOON - Trading is forbidden after 12pm EST on Fridays."
            suggestion = "Market is erratic. Close your charts and enjoy your weekend."
        elif is_friday and hour >= 10:
            message = f"⚠️ Friday {hour}:00 EST - Getting close to cutoff time (12pm)."
            suggestion = "Wrap up soon. Don't start new trades close to cutoff."
        else:
            message = "✅ Not Friday afternoon. Clear to trade."
            suggestion = ""
        
        return RuleCheck(
            rule_id="friday_restriction",
            rule_name="No Friday PM Trading",
            passed=passed,
            severity=RuleSeverity.HARD.value,
            message=message,
            suggestion=suggestion
        )
    
    def check_risk_reward(self, entry: float, stop: float, target: float) -> RuleCheck:
        """Check minimum 2:1 R:R rule."""
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0
        
        passed = rr >= 2.0
        
        if rr >= 3.0:
            message = f"✅ Excellent R:R of {rr:.1f}:1"
            suggestion = "Great setup. Consider holding for full target."
        elif rr >= 2.0:
            message = f"✅ R:R of {rr:.1f}:1 meets minimum requirement."
            suggestion = ""
        else:
            message = f"❌ R:R of {rr:.1f}:1 is below minimum 2:1!"
            suggestion = "Adjust entry, stop, or target to achieve at least 2:1 R:R."
        
        return RuleCheck(
            rule_id="rr_ratio",
            rule_name="Minimum 2:1 R:R",
            passed=passed,
            severity=RuleSeverity.HARD.value,
            message=message,
            suggestion=suggestion
        )
    
    def check_killzone(self, killzone: str) -> RuleCheck:
        """Check if trading in optimal killzone (soft rule)."""
        optimal = killzone in ["LONDON", "NY_AM"]
        
        if optimal:
            message = f"✅ Trading in optimal {killzone} session."
            suggestion = ""
        elif killzone == "ASIAN":
            message = f"⚠️ Asian session - lower probability setups."
            suggestion = "Asian session can be choppy. Be more selective."
        else:
            message = f"⚠️ {killzone} session - not optimal."
            suggestion = "Best setups occur in London and NY AM. Consider waiting."
        
        return RuleCheck(
            rule_id="killzone",
            rule_name="Optimal Killzone",
            passed=optimal,
            severity=RuleSeverity.SOFT.value,
            message=message,
            suggestion=suggestion
        )
    
    def check_psychology(self) -> List[RuleCheck]:
        """Check psychology triggers and emotional state."""
        checks = []
        current_state = self.triggers.get("current_state", {})
        
        # Check revenge trading
        if current_state.get("recent_loss"):
            last_loss_time = current_state.get("last_loss_time", "")
            if last_loss_time:
                # If loss was within last 30 minutes
                try:
                    loss_dt = datetime.fromisoformat(last_loss_time)
                    if datetime.now() - loss_dt < timedelta(minutes=30):
                        checks.append(RuleCheck(
                            rule_id="revenge_trading",
                            rule_name="Revenge Trading Check",
                            passed=False,
                            severity=RuleSeverity.HARD.value,
                            message="⚠️ REVENGE TRADING ALERT - You just took a loss within 30 minutes!",
                            suggestion="Step away from the charts. Take a 30-minute break minimum."
                        ))
                except:
                    pass
        
        # Check overtrading
        today_trades = self.get_today_trades()
        if len(today_trades) >= 2:
            # Check if trades were close together
            recent_trades = sorted(today_trades, key=lambda x: x.get("created_at", ""), reverse=True)[:2]
            if len(recent_trades) >= 2:
                try:
                    t1 = datetime.fromisoformat(recent_trades[0].get("created_at", ""))
                    t2 = datetime.fromisoformat(recent_trades[1].get("created_at", ""))
                    if abs((t1 - t2).total_seconds()) < 1800:  # 30 minutes
                        checks.append(RuleCheck(
                            rule_id="overtrading",
                            rule_name="Overtrading Check",
                            passed=False,
                            severity=RuleSeverity.SOFT.value,
                            message="⚠️ OVERTRADING ALERT - Multiple trades in quick succession!",
                            suggestion="Slow down. Quality over quantity."
                        ))
                except:
                    pass
        
        # If no issues, add positive check
        if not checks:
            checks.append(RuleCheck(
                rule_id="psychology_clear",
                rule_name="Psychology Check",
                passed=True,
                severity=RuleSeverity.SOFT.value,
                message="✅ Psychology clear. No red flags detected.",
                suggestion=""
            ))
        
        return checks
    
    def full_pre_trade_check(
        self,
        pair: str,
        direction: str,
        entry: float,
        stop: float,
        target: float,
        daily_bias: str = "",
        killzone: str = ""
    ) -> RuleCheckResult:
        """
        Run all rule checks before a trade.
        
        Returns comprehensive check result with pass/fail status.
        """
        all_checks = []
        warnings = []
        blockers = []
        
        # Hard Rules
        all_checks.append(asdict(self.check_two_strike_rule(pair)))
        all_checks.append(asdict(self.check_max_trades()))
        all_checks.append(asdict(self.check_friday_restriction()))
        all_checks.append(asdict(self.check_risk_reward(entry, stop, target)))
        
        if daily_bias:
            all_checks.append(asdict(self.check_daily_bias_alignment(pair, direction, daily_bias)))
        
        # Soft Rules
        if killzone:
            all_checks.append(asdict(self.check_killzone(killzone)))
        
        # Psychology
        for check in self.check_psychology():
            all_checks.append(asdict(check))
        
        # Categorize results
        hard_passed = True
        all_passed = True
        
        for check in all_checks:
            if not check["passed"]:
                all_passed = False
                if check["severity"] == RuleSeverity.HARD.value:
                    hard_passed = False
                    blockers.append(check["message"])
                else:
                    warnings.append(check["message"])
        
        # Generate recommendation
        if not hard_passed:
            recommendation = "❌ BLOCKED - Hard rule violation(s). DO NOT TAKE THIS TRADE."
        elif warnings:
            recommendation = f"⚠️ CAUTION - {len(warnings)} warning(s). Proceed with extra caution."
        else:
            recommendation = "✅ ALL CLEAR - No rule violations. Trade is approved."
        
        return RuleCheckResult(
            timestamp=datetime.now().isoformat(),
            pair=pair,
            direction=direction,
            all_passed=all_passed,
            hard_rules_passed=hard_passed,
            checks=all_checks,
            warnings=warnings,
            blockers=blockers,
            recommendation=recommendation
        )
    
    def record_violation(self, rule_id: str, trade_id: str = "", notes: str = ""):
        """Record a rule violation."""
        for rule in self.rules.get("hard_rules", []) + self.rules.get("soft_rules", []):
            if rule.get("id") == rule_id:
                if "violations" not in rule:
                    rule["violations"] = []
                
                rule["violations"].append({
                    "timestamp": datetime.now().isoformat(),
                    "trade_id": trade_id,
                    "notes": notes
                })
                rule["violation_count"] = rule.get("violation_count", 0) + 1
                
                self._save_rules()
                return True
        return False
    
    def update_psychology_state(self, **kwargs):
        """Update current psychology state."""
        current = self.triggers.get("current_state", {})
        current.update(kwargs)
        current["last_updated"] = datetime.now().isoformat()
        self.triggers["current_state"] = current
        
        # Save
        path = MEMORY_DIR / "triggers.json"
        with open(path, "w") as f:
            json.dump(self.triggers, f, indent=2)
    
    def format_check_result(self, result: RuleCheckResult) -> str:
        """Format check result as readable report."""
        lines = []
        lines.append("")
        lines.append("═" * 60)
        lines.append(f"  PRE-TRADE RULE CHECK: {result.pair} {result.direction}")
        lines.append("═" * 60)
        lines.append("")
        
        # Summary
        status = "✅ APPROVED" if result.hard_rules_passed else "❌ BLOCKED"
        lines.append(f"  Status: {status}")
        lines.append("")
        
        # All checks
        lines.append("  RULE CHECKS:")
        lines.append("  " + "-" * 50)
        
        for check in result.checks:
            severity_tag = "[HARD]" if check["severity"] == "hard" else "[SOFT]"
            lines.append(f"  {check['message']}")
            if check["suggestion"]:
                lines.append(f"      └─ {check['suggestion']}")
        
        # Blockers
        if result.blockers:
            lines.append("")
            lines.append("  🚫 BLOCKERS (Must Fix):")
            for b in result.blockers:
                lines.append(f"  {b}")
        
        # Warnings
        if result.warnings:
            lines.append("")
            lines.append("  ⚠️ WARNINGS:")
            for w in result.warnings:
                lines.append(f"  {w}")
        
        # Recommendation
        lines.append("")
        lines.append("  " + "-" * 50)
        lines.append(f"  {result.recommendation}")
        lines.append("")
        lines.append("═" * 60)
        
        return "\n".join(lines)


def main():
    """CLI entry point for rules engine."""
    import sys
    
    engine = RulesEngine()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python rules_engine.py check PAIR DIRECTION ENTRY STOP TARGET")
        print("  python rules_engine.py status")
        print("  python rules_engine.py strikes PAIR")
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == "check" and len(sys.argv) >= 7:
        pair = sys.argv[2].upper()
        direction = sys.argv[3].upper()
        entry = float(sys.argv[4])
        stop = float(sys.argv[5])
        target = float(sys.argv[6])
        
        result = engine.full_pre_trade_check(pair, direction, entry, stop, target)
        print(engine.format_check_result(result))
    
    elif cmd == "status":
        print("\n" + "=" * 50)
        print("  RULES STATUS")
        print("=" * 50)
        
        # Today's trades
        today_trades = engine.get_today_trades()
        print(f"\n  Trades Today: {len(today_trades)}/3")
        
        # Friday check
        friday_check = engine.check_friday_restriction()
        print(f"  {friday_check.message}")
        
        # Psychology
        print("\n  Psychology Checks:")
        for check in engine.check_psychology():
            print(f"  {check.message}")
        
        print("=" * 50)
    
    elif cmd == "strikes" and len(sys.argv) >= 3:
        pair = sys.argv[2].upper()
        strikes = engine.get_pair_strikes(pair)
        print(f"\n{pair} Strikes: {strikes}/2")
        if strikes >= 2:
            print("⚠️ TWO STRIKE RULE ACTIVE - Stop trading this pair!")
        elif strikes == 1:
            print("⚠️ One more loss and you're done with this pair today.")
        else:
            print("✅ Clear to trade.")
    
    else:
        print(f"Unknown command or missing arguments: {cmd}")


if __name__ == "__main__":
    main()
