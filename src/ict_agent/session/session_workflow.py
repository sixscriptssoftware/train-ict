"""
VEX Daily Session Workflow - Guided pre-market routine.

Steps:
1. Bias Determination - Auto-fetch Daily candle, mark bias
2. HTF Markup - 1H charts with key levels, FVGs, OBs
3. Session Planning - Killzones, focus pairs, max trades
4. Psychology Check-in - Sleep, emotions, confidence
5. Generate Watchlist - Today's focus with bias and levels
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

MEMORY_DIR = PROJECT_ROOT / "data" / "memory"
SCREENSHOTS_DIR = PROJECT_ROOT / "screenshots"

NY_TZ = ZoneInfo("America/New_York")


class SessionWorkflow:
    """
    Guided daily session workflow for ICT trading.
    """
    
    # Your focus pairs
    PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "GBP_JPY", "EUR_GBP", "AUD_USD", "XAU_USD"]
    
    def __init__(self):
        self.context = self._load_json("context.json")
        self.identity = self._load_json("identity.json")
        self.triggers = self._load_json("triggers.json")
        self.fetcher = None
        self._init_fetcher()
    
    def _init_fetcher(self):
        """Initialize OANDA fetcher."""
        try:
            from ict_agent.data.oanda_fetcher import OANDAFetcher
            self.fetcher = OANDAFetcher()
        except Exception as e:
            print(f"Warning: Could not initialize fetcher: {e}")
    
    def _load_json(self, filename: str) -> Dict:
        """Load JSON from memory."""
        path = MEMORY_DIR / filename
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def _save_json(self, filename: str, data: Dict):
        """Save JSON to memory."""
        path = MEMORY_DIR / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def run_full_workflow(self) -> Dict:
        """Run the complete daily session workflow."""
        print("\n" + "═" * 70)
        print("                    VEX DAILY SESSION WORKFLOW")
        print("═" * 70)
        
        now = datetime.now(NY_TZ)
        print(f"\n📅 {now.strftime('%A, %B %d, %Y')} | {now.strftime('%I:%M %p')} EST")
        
        session_data = {
            "date": now.strftime("%Y-%m-%d"),
            "start_time": now.isoformat(),
            "bias": {},
            "watchlist": [],
            "psychology": {},
            "plan": {}
        }
        
        # Step 1: Bias Determination
        print("\n" + "─" * 70)
        print("  STEP 1: BIAS DETERMINATION")
        print("─" * 70)
        session_data["bias"] = self._step_bias_determination()
        
        # Step 2: HTF Markup (1H)
        print("\n" + "─" * 70)
        print("  STEP 2: 1-HOUR MARKUP")
        print("─" * 70)
        self._step_htf_markup(session_data["bias"])
        
        # Step 3: Session Planning
        print("\n" + "─" * 70)
        print("  STEP 3: SESSION PLANNING")
        print("─" * 70)
        session_data["plan"] = self._step_session_planning()
        
        # Step 4: Psychology Check-in
        print("\n" + "─" * 70)
        print("  STEP 4: PSYCHOLOGY CHECK-IN")
        print("─" * 70)
        session_data["psychology"] = self._step_psychology_checkin()
        
        # Step 5: Generate Watchlist
        print("\n" + "─" * 70)
        print("  STEP 5: TODAY'S WATCHLIST")
        print("─" * 70)
        session_data["watchlist"] = self._step_generate_watchlist(session_data)
        
        # Save to context
        self.context["current_session"] = session_data
        self.context["last_session_date"] = session_data["date"]
        self._save_json("context.json", self.context)
        
        # Final Summary
        self._print_summary(session_data)
        
        return session_data
    
    def _step_bias_determination(self) -> Dict[str, Dict]:
        """Step 1: Determine daily bias for each pair."""
        bias_data = {}
        
        print("\n  Fetching Daily candles for all pairs...\n")
        
        for pair in self.PAIRS:
            try:
                if self.fetcher:
                    df = self.fetcher.fetch_latest(pair, "D", 5)
                    if df is not None and len(df) > 0:
                        df = df.reset_index()
                        
                        # Get recent candles
                        current = df.iloc[-1]
                        prev = df.iloc[-2] if len(df) > 1 else current
                        
                        high = current['high']
                        low = current['low']
                        close = current['close']
                        open_price = current['open']
                        
                        # Calculate zones
                        range_size = high - low
                        eq = (high + low) / 2
                        
                        # Determine zone
                        if close > eq:
                            zone = "PREMIUM"
                        else:
                            zone = "DISCOUNT"
                        
                        # Determine bias based on structure
                        if close > prev['high']:
                            bias = "BULLISH"
                            bias_reason = "Closed above previous day high"
                        elif close < prev['low']:
                            bias = "BEARISH"
                            bias_reason = "Closed below previous day low"
                        elif close > open_price and close > eq:
                            bias = "BULLISH"
                            bias_reason = "Bullish candle in premium (looking for retracement)"
                        elif close < open_price and close < eq:
                            bias = "BEARISH"
                            bias_reason = "Bearish candle in discount (looking for retracement)"
                        else:
                            bias = "NEUTRAL"
                            bias_reason = "No clear direction"
                        
                        pip_size = 0.01 if 'JPY' in pair else 0.0001
                        range_pips = range_size / pip_size
                        
                        bias_data[pair] = {
                            "bias": bias,
                            "zone": zone,
                            "reason": bias_reason,
                            "daily_high": round(high, 5),
                            "daily_low": round(low, 5),
                            "equilibrium": round(eq, 5),
                            "current_price": round(close, 5),
                            "range_pips": round(range_pips, 1)
                        }
                        
                        bias_icon = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "⚪"
                        zone_icon = "📈" if zone == "PREMIUM" else "📉"
                        
                        print(f"  {bias_icon} {pair}: {bias} | {zone_icon} {zone}")
                        print(f"     Range: {range_pips:.1f} pips | EQ: {eq:.5f}")
                        print(f"     {bias_reason}")
                        print()
                else:
                    # Manual input fallback
                    print(f"\n  {pair}:")
                    bias = input("    Bias (BULLISH/BEARISH/NEUTRAL): ").strip().upper() or "NEUTRAL"
                    zone = input("    Zone (PREMIUM/DISCOUNT): ").strip().upper() or "NEUTRAL"
                    bias_data[pair] = {"bias": bias, "zone": zone, "reason": "Manual input"}
                    
            except Exception as e:
                print(f"  ⚠️ {pair}: Error fetching data - {e}")
                bias_data[pair] = {"bias": "NEUTRAL", "zone": "NEUTRAL", "reason": str(e)}
        
        return bias_data
    
    def _step_htf_markup(self, bias_data: Dict):
        """Step 2: Generate 1H markup charts."""
        print("\n  Generating 1-Hour markup charts...\n")
        
        # Filter to pairs with clear bias
        focus_pairs = [p for p, d in bias_data.items() if d.get("bias") != "NEUTRAL"]
        
        if not focus_pairs:
            focus_pairs = self.PAIRS[:3]  # Default to first 3
        
        for pair in focus_pairs[:4]:  # Max 4 charts
            try:
                if self.fetcher:
                    print(f"  📊 Generating {pair} 1H chart...", end=" ")
                    
                    df = self.fetcher.fetch_latest(pair, "1h", 100)
                    if df is not None and len(df) > 0:
                        # Generate chart
                        self._generate_markup_chart(pair, df, bias_data.get(pair, {}))
                        print("✓")
                    else:
                        print("No data")
                else:
                    print(f"  ⚠️ Skipping {pair} chart (no fetcher)")
                    
            except Exception as e:
                print(f"Error: {e}")
        
        print("\n  💡 Review charts in screenshots/ folder")
    
    def _generate_markup_chart(self, pair: str, df, bias_info: Dict):
        """Generate a markup chart for a pair."""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            
            df = df.reset_index()
            df.columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            
            fig, ax = plt.subplots(figsize=(16, 8))
            fig.patch.set_facecolor('#0a0a0a')
            ax.set_facecolor('#0a0a0a')
            
            # Calculate zones
            range_high = df['high'].max()
            range_low = df['low'].min()
            eq = (range_high + range_low) / 2
            
            # Premium/discount shading
            ax.axhspan(eq, range_high, alpha=0.05, color='red', label='Premium')
            ax.axhspan(range_low, eq, alpha=0.05, color='green', label='Discount')
            ax.axhline(y=eq, color='yellow', linestyle='-', linewidth=1.5, alpha=0.7, label='Equilibrium')
            
            # Plot candles
            pip_size = 0.01 if 'JPY' in pair else 0.0001
            for j in range(len(df)):
                color = '#00ff00' if df['close'].iloc[j] >= df['open'].iloc[j] else '#ff0000'
                ax.plot([j, j], [df['low'].iloc[j], df['high'].iloc[j]], color=color, linewidth=0.5)
                body_bottom = min(df['open'].iloc[j], df['close'].iloc[j])
                body_top = max(df['open'].iloc[j], df['close'].iloc[j])
                body_height = max(body_top - body_bottom, pip_size)
                rect = mpatches.Rectangle((j - 0.3, body_bottom), 0.6, body_height,
                                          linewidth=0, facecolor=color)
                ax.add_patch(rect)
            
            # Mark key levels
            # Previous day high/low (approximate using recent swing)
            recent_high = df['high'].iloc[-24:].max() if len(df) >= 24 else df['high'].max()
            recent_low = df['low'].iloc[-24:].min() if len(df) >= 24 else df['low'].min()
            
            ax.axhline(y=recent_high, color='#ff6666', linestyle='--', linewidth=1, alpha=0.7)
            ax.axhline(y=recent_low, color='#66ff66', linestyle='--', linewidth=1, alpha=0.7)
            
            # Current price
            current = df['close'].iloc[-1]
            ax.axhline(y=current, color='white', linestyle='-', linewidth=2)
            
            # Detect FVGs (last 50 candles)
            fvg_count = 0
            for i in range(2, min(50, len(df))):
                c1, c2, c3 = df.iloc[-(i+1)], df.iloc[-i], df.iloc[-(i-1)] if i > 1 else df.iloc[-1]
                
                # Bullish FVG
                if c3['low'] > c1['high']:
                    ax.axhspan(c1['high'], c3['low'], xmin=(len(df)-i)/len(df), 
                              alpha=0.2, color='green')
                    fvg_count += 1
                # Bearish FVG
                elif c3['high'] < c1['low']:
                    ax.axhspan(c3['high'], c1['low'], xmin=(len(df)-i)/len(df),
                              alpha=0.2, color='red')
                    fvg_count += 1
                
                if fvg_count >= 5:
                    break
            
            # Title with bias
            bias = bias_info.get("bias", "NEUTRAL")
            zone = bias_info.get("zone", "")
            bias_color = '#00ff00' if bias == "BULLISH" else '#ff0000' if bias == "BEARISH" else '#ffffff'
            
            ax.set_title(f"{pair} 1H | Bias: {bias} | Zone: {zone}", 
                        fontsize=14, fontweight='bold', color=bias_color)
            
            ax.grid(True, alpha=0.15)
            ax.tick_params(colors='white')
            for spine in ax.spines.values():
                spine.set_color('#333')
            
            # Save
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = SCREENSHOTS_DIR / f'{pair}_1H_session_{timestamp}.png'
            plt.savefig(filepath, dpi=150, bbox_inches='tight', facecolor='#0a0a0a')
            plt.close()
            
        except Exception as e:
            print(f"Chart error: {e}")
    
    def _step_session_planning(self) -> Dict:
        """Step 3: Plan trading sessions."""
        plan = {}
        
        print("\n  Which sessions will you trade today?\n")
        
        sessions = {
            "1": ("ASIAN", "7PM - 2AM EST"),
            "2": ("LONDON", "2AM - 5AM EST"),
            "3": ("NY_AM", "7AM - 10AM EST"),
            "4": ("NY_PM", "1PM - 4PM EST")
        }
        
        for key, (name, time) in sessions.items():
            print(f"    {key}. {name} ({time})")
        
        selected = input("\n  Enter session numbers (e.g., 2,3): ").strip()
        plan["sessions"] = []
        
        for s in selected.split(","):
            s = s.strip()
            if s in sessions:
                plan["sessions"].append(sessions[s][0])
        
        if not plan["sessions"]:
            plan["sessions"] = ["LONDON", "NY_AM"]  # Default
        
        print(f"\n  ✅ Trading: {', '.join(plan['sessions'])}")
        
        # Max trades
        max_trades = input("\n  Max trades for today (default: 3): ").strip()
        plan["max_trades"] = int(max_trades) if max_trades.isdigit() else 3
        print(f"  ✅ Max trades: {plan['max_trades']}")
        
        # News events
        news = input("\n  Any high-impact news to avoid? (time or 'none'): ").strip()
        plan["news_avoid"] = news if news.lower() != "none" else None
        if plan["news_avoid"]:
            print(f"  ⚠️ Avoiding: {plan['news_avoid']}")
        
        # Focus
        focus = input("\n  Special focus for today? (optional): ").strip()
        plan["focus"] = focus if focus else None
        
        return plan
    
    def _step_psychology_checkin(self) -> Dict:
        """Step 4: Psychology check-in."""
        psych = {}
        
        print("\n  Quick psychology check...\n")
        
        # Sleep
        sleep = input("  How did you sleep last night? (1-10): ").strip()
        psych["sleep_quality"] = int(sleep) if sleep.isdigit() else 5
        
        if psych["sleep_quality"] < 5:
            print("  ⚠️ Low sleep quality. Consider reducing position sizes today.")
        
        # Emotional state
        print("\n  Current emotional state:")
        print("    1. Calm and focused")
        print("    2. Slightly anxious")
        print("    3. Frustrated/angry")
        print("    4. Overconfident")
        print("    5. FOMO feeling")
        
        emotion = input("  Select (1-5): ").strip()
        emotion_map = {
            "1": ("calm", "✅ Great mindset for trading"),
            "2": ("anxious", "⚠️ Be extra patient. Wait for A+ setups only."),
            "3": ("frustrated", "🚫 Consider NOT trading today. Journal instead."),
            "4": ("overconfident", "⚠️ Stick to normal size. Don't chase."),
            "5": ("fomo", "🚫 Step away. FOMO = losses.")
        }
        
        state, msg = emotion_map.get(emotion, ("neutral", ""))
        psych["emotional_state"] = state
        print(f"  {msg}")
        
        # Confidence
        conf = input("\n  Confidence level for today (1-10): ").strip()
        psych["confidence"] = int(conf) if conf.isdigit() else 5
        
        # Recent loss check
        recent_loss = input("\n  Did you take a loss recently? (y/n): ").strip().lower()
        psych["recent_loss"] = recent_loss == 'y'
        
        if psych["recent_loss"]:
            print("  ⚠️ REVENGE TRADING ALERT: Be extra careful. Only A+ setups.")
        
        # Update triggers
        self.triggers["current_state"] = {
            "sleep_quality": psych["sleep_quality"],
            "emotional_state": psych["emotional_state"],
            "confidence": psych["confidence"],
            "recent_loss": psych["recent_loss"],
            "last_updated": datetime.now(NY_TZ).isoformat()
        }
        self._save_json("triggers.json", self.triggers)
        
        return psych
    
    def _step_generate_watchlist(self, session_data: Dict) -> List[Dict]:
        """Step 5: Generate today's watchlist."""
        watchlist = []
        
        bias_data = session_data.get("bias", {})
        
        print("\n  Based on your bias determination:\n")
        
        for pair, data in bias_data.items():
            if data.get("bias") in ["BULLISH", "BEARISH"]:
                direction = "LONG" if data["bias"] == "BULLISH" else "SHORT"
                zone = data.get("zone", "")
                eq = data.get("equilibrium", 0)
                
                # Determine entry zone
                if direction == "LONG" and zone == "PREMIUM":
                    entry_zone = f"Wait for retracement to discount (below {eq:.5f})"
                elif direction == "LONG" and zone == "DISCOUNT":
                    entry_zone = f"Look for entry in current discount zone"
                elif direction == "SHORT" and zone == "DISCOUNT":
                    entry_zone = f"Wait for retracement to premium (above {eq:.5f})"
                else:
                    entry_zone = f"Look for entry in current premium zone"
                
                item = {
                    "pair": pair,
                    "bias": data["bias"],
                    "direction": direction,
                    "zone": zone,
                    "equilibrium": eq,
                    "entry_zone": entry_zone,
                    "daily_high": data.get("daily_high"),
                    "daily_low": data.get("daily_low")
                }
                watchlist.append(item)
                
                icon = "🟢" if direction == "LONG" else "🔴"
                print(f"  {icon} {pair}: Looking for {direction}s")
                print(f"     {entry_zone}")
                print(f"     Targets: PDH {data.get('daily_high', 'N/A')} | PDL {data.get('daily_low', 'N/A')}")
                print()
        
        if not watchlist:
            print("  ⚠️ No clear setups today. Consider sitting out or using smaller size.")
        
        return watchlist
    
    def _print_summary(self, session_data: Dict):
        """Print final session summary."""
        print("\n" + "═" * 70)
        print("                    SESSION SUMMARY")
        print("═" * 70)
        
        # Watchlist
        watchlist = session_data.get("watchlist", [])
        if watchlist:
            print(f"\n  📋 WATCHLIST ({len(watchlist)} pairs):")
            for item in watchlist:
                icon = "🟢" if item["direction"] == "LONG" else "🔴"
                print(f"     {icon} {item['pair']} {item['direction']}")
        
        # Plan
        plan = session_data.get("plan", {})
        print(f"\n  ⏰ SESSIONS: {', '.join(plan.get('sessions', []))}")
        print(f"  🎯 MAX TRADES: {plan.get('max_trades', 3)}")
        
        # Psychology
        psych = session_data.get("psychology", {})
        state = psych.get("emotional_state", "unknown")
        if state in ["frustrated", "fomo"]:
            print(f"\n  ⚠️ PSYCHOLOGY WARNING: {state.upper()} detected")
            print("     Consider reduced size or sitting out.")
        else:
            print(f"\n  🧠 PSYCHOLOGY: {state} (confidence: {psych.get('confidence', 5)}/10)")
        
        # Rules reminder
        print("\n  📜 RULES REMINDER:")
        print("     • Two Strike Rule active")
        print("     • Min 2:1 R:R required")
        print("     • Pre-trade journal BEFORE entry")
        
        if plan.get("news_avoid"):
            print(f"     • ⚠️ Avoid trading during: {plan['news_avoid']}")
        
        print("\n" + "═" * 70)
        print("  ✅ Session workflow complete. Good trading!")
        print("═" * 70 + "\n")
    
    def quick_status(self):
        """Print quick status from today's session."""
        session = self.context.get("current_session", {})
        
        if not session or session.get("date") != datetime.now(NY_TZ).strftime("%Y-%m-%d"):
            print("\n  ⚠️ No session workflow completed today.")
            print("  Run 'python vex.py session start' to begin.")
            return
        
        print("\n" + "═" * 60)
        print("  TODAY'S SESSION STATUS")
        print("═" * 60)
        
        # Bias summary
        bias = session.get("bias", {})
        bullish = [p for p, d in bias.items() if d.get("bias") == "BULLISH"]
        bearish = [p for p, d in bias.items() if d.get("bias") == "BEARISH"]
        
        print(f"\n  🟢 BULLISH: {', '.join(bullish) if bullish else 'None'}")
        print(f"  🔴 BEARISH: {', '.join(bearish) if bearish else 'None'}")
        
        # Watchlist
        watchlist = session.get("watchlist", [])
        if watchlist:
            print(f"\n  📋 WATCHLIST:")
            for item in watchlist[:5]:
                icon = "🟢" if item.get("direction") == "LONG" else "🔴"
                print(f"     {icon} {item['pair']} {item['direction']}")
        
        # Psychology
        psych = session.get("psychology", {})
        print(f"\n  🧠 MOOD: {psych.get('emotional_state', 'N/A')} | Confidence: {psych.get('confidence', 'N/A')}/10")
        
        print("\n" + "═" * 60)


def main():
    """CLI entry point."""
    workflow = SessionWorkflow()
    workflow.run_full_workflow()


if __name__ == "__main__":
    main()
