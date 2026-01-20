"""
Seed ICT Knowledge Base - Populate Turso database with core ICT concepts and models.

Run this once to initialize the knowledge base.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ict_agent.database import get_db


# ─────────────────────────────────────────────────────────────────────────────
# ICT CONCEPTS
# ─────────────────────────────────────────────────────────────────────────────

ICT_CONCEPTS = [
    # PD Arrays (Price Delivery Arrays)
    {
        "name": "Fair Value Gap",
        "category": "PD Arrays",
        "definition": "A 3-candle pattern where the wicks of candles 1 and 3 don't overlap, creating an imbalance that price tends to return to.",
        "key_points": [
            "Forms during displacement/momentum",
            "Acts as magnetic support/resistance",
            "Price often returns to fill or react at FVGs",
            "Bullish FVG: Candle 1 high < Candle 3 low",
            "Bearish FVG: Candle 1 low > Candle 3 high"
        ],
        "how_to_identify": "Look for 3 consecutive candles where the wicks don't overlap. The gap between candle 1 and 3 is the FVG.",
        "trading_rules": [
            "Trade in direction of FVG formation (trend)",
            "Use 50% of FVG as optimal entry point",
            "Stop loss beyond the FVG",
            "Higher timeframe FVGs are stronger"
        ],
        "related_concepts": ["Order Block", "Displacement", "Imbalance", "SIBI", "BISI"]
    },
    {
        "name": "Order Block",
        "category": "PD Arrays",
        "definition": "The last up-candle before a down move (bearish OB) or last down-candle before an up move (bullish OB). Represents institutional entry zones.",
        "key_points": [
            "Bullish OB: Last red candle before displacement up",
            "Bearish OB: Last green candle before displacement down",
            "Best OBs create FVGs (displacement)",
            "Use the body, not wicks, for entries"
        ],
        "how_to_identify": "Find the last opposing candle before a strong move. The open and close of that candle define the OB zone.",
        "trading_rules": [
            "Trade in direction of the displacement",
            "Enter at the 50% or full body of OB",
            "Stop loss beyond the OB",
            "Combine with FVG for confluence"
        ],
        "related_concepts": ["Fair Value Gap", "Displacement", "Breaker Block", "Mitigation Block"]
    },
    {
        "name": "Breaker Block",
        "category": "PD Arrays",
        "definition": "A failed Order Block that gets broken and then becomes support/resistance from the opposite side.",
        "key_points": [
            "Order Block that failed to hold",
            "After break, it flips polarity",
            "Often stronger than original OB",
            "Confirms market structure shift"
        ],
        "how_to_identify": "Find an OB that was broken through. When price returns to that zone from the opposite side, it's now a breaker.",
        "trading_rules": [
            "Wait for price to break the OB",
            "Enter when price retests from opposite direction",
            "Shows institutional footprint"
        ],
        "related_concepts": ["Order Block", "Market Structure Shift", "Change of Character"]
    },
    {
        "name": "SIBI",
        "category": "PD Arrays",
        "definition": "Sell-side Imbalance, Buy-side Inefficiency - A bearish FVG where sellers created an imbalance. Price may return to fill this inefficiency.",
        "key_points": [
            "Bearish FVG formation",
            "Created by aggressive selling",
            "Acts as resistance",
            "Look for shorts when price enters"
        ],
        "how_to_identify": "Candle 1 low is higher than Candle 3 high in a down move.",
        "trading_rules": [
            "Use as short entry zone",
            "Combine with bearish bias",
            "Stop above the SIBI"
        ],
        "related_concepts": ["Fair Value Gap", "BISI", "Imbalance"]
    },
    {
        "name": "BISI",
        "category": "PD Arrays",
        "definition": "Buy-side Imbalance, Sell-side Inefficiency - A bullish FVG where buyers created an imbalance. Price may return to fill this inefficiency.",
        "key_points": [
            "Bullish FVG formation",
            "Created by aggressive buying",
            "Acts as support",
            "Look for longs when price enters"
        ],
        "how_to_identify": "Candle 1 high is lower than Candle 3 low in an up move.",
        "trading_rules": [
            "Use as long entry zone",
            "Combine with bullish bias",
            "Stop below the BISI"
        ],
        "related_concepts": ["Fair Value Gap", "SIBI", "Imbalance"]
    },
    
    # Market Structure
    {
        "name": "Market Structure Shift",
        "category": "Market Structure",
        "definition": "A break of the most recent swing high (bullish MSS) or swing low (bearish MSS) that signals a potential trend change.",
        "key_points": [
            "Break of structure confirms direction change",
            "Must see displacement through the level",
            "Creates new order flow",
            "Different from simple retracement"
        ],
        "how_to_identify": "In a downtrend, watch for break above the most recent lower high. In uptrend, break below most recent higher low.",
        "trading_rules": [
            "Wait for MSS before looking for entries",
            "Trade pullbacks after MSS",
            "Use FVG/OB formed during MSS as entry"
        ],
        "related_concepts": ["Change of Character", "BOS", "Displacement"]
    },
    {
        "name": "Change of Character",
        "category": "Market Structure",
        "definition": "The first sign of a trend reversal - breaking the most recent swing point after taking liquidity.",
        "key_points": [
            "Occurs after liquidity grab",
            "First break of structure",
            "Entry opportunity on retest",
            "Confirms smart money activity"
        ],
        "how_to_identify": "After a liquidity sweep (raid of highs/lows), price reverses and breaks the opposing swing point.",
        "trading_rules": [
            "Wait for liquidity sweep first",
            "Enter on retest of CHoCH level",
            "Target opposite liquidity"
        ],
        "related_concepts": ["Market Structure Shift", "Liquidity Sweep", "Smart Money Reversal"]
    },
    {
        "name": "BOS",
        "category": "Market Structure",
        "definition": "Break of Structure - When price breaks a recent swing high or low, continuing the current trend.",
        "key_points": [
            "Confirms trend continuation",
            "Bullish BOS: Break above swing high",
            "Bearish BOS: Break below swing low",
            "Creates new range"
        ],
        "how_to_identify": "Watch for price to close beyond the most recent swing point in the direction of the trend.",
        "trading_rules": [
            "Trade pullbacks after BOS",
            "Look for entries in FVG/OB created",
            "Use for trend trading"
        ],
        "related_concepts": ["Market Structure Shift", "Swing High", "Swing Low"]
    },
    
    # Liquidity
    {
        "name": "Buy-side Liquidity",
        "category": "Liquidity",
        "definition": "Stop losses and buy orders resting above swing highs. Smart money targets these to fill large sell orders.",
        "key_points": [
            "Located above relative equal highs",
            "Above old swing highs",
            "Retail stop losses from shorts",
            "Target for smart money sells"
        ],
        "how_to_identify": "Look for equal highs, old highs, or obvious resistance levels where stops would accumulate.",
        "trading_rules": [
            "Don't place stops at obvious levels",
            "Expect price to hunt these levels",
            "After BSL is taken, look for reversal"
        ],
        "related_concepts": ["Sell-side Liquidity", "Stop Hunt", "Liquidity Sweep"]
    },
    {
        "name": "Sell-side Liquidity",
        "category": "Liquidity",
        "definition": "Stop losses and sell orders resting below swing lows. Smart money targets these to fill large buy orders.",
        "key_points": [
            "Located below relative equal lows",
            "Below old swing lows",
            "Retail stop losses from longs",
            "Target for smart money buys"
        ],
        "how_to_identify": "Look for equal lows, old lows, or obvious support levels where stops would accumulate.",
        "trading_rules": [
            "Don't place stops at obvious levels",
            "Expect price to hunt these levels",
            "After SSL is taken, look for reversal"
        ],
        "related_concepts": ["Buy-side Liquidity", "Stop Hunt", "Liquidity Sweep"]
    },
    {
        "name": "Liquidity Sweep",
        "category": "Liquidity",
        "definition": "When price runs through a liquidity level (highs/lows) to fill orders, then reverses.",
        "key_points": [
            "Quick wick beyond level",
            "Triggers retail stops",
            "Fills smart money orders",
            "Often precedes reversal"
        ],
        "how_to_identify": "Watch for price to spike beyond a key level (high/low) with a wick, then close back inside.",
        "trading_rules": [
            "Wait for sweep to complete",
            "Enter after confirmation",
            "Target opposite liquidity"
        ],
        "related_concepts": ["Stop Hunt", "Judas Swing", "Turtle Soup"]
    },
    
    # Time & Sessions
    {
        "name": "Killzone",
        "category": "Time",
        "definition": "Specific time windows when institutional trading activity creates the best opportunities.",
        "key_points": [
            "London Open: 2-5 AM EST",
            "NY Open: 7-10 AM EST (Best)",
            "London Close: 10 AM - 12 PM EST",
            "Avoid midnight to 2 AM"
        ],
        "how_to_identify": "Mark these times on your chart. Most high-probability setups occur during killzones.",
        "trading_rules": [
            "Only trade during killzones",
            "Best setups in NY AM (7-10 AM)",
            "Avoid low-volume periods"
        ],
        "related_concepts": ["Power of 3", "Asian Range", "CBDR"]
    },
    {
        "name": "CBDR",
        "category": "Time",
        "definition": "Central Bank Dealer Range - The range formed during 2:00 AM - 5:00 AM EST. Used to project targets.",
        "key_points": [
            "Forms during London open",
            "Range should be < 30 pips ideally",
            "Use for SD projections",
            "First liquidity target of the day"
        ],
        "how_to_identify": "Mark the high and low between 2-5 AM EST. Calculate the range in pips.",
        "trading_rules": [
            "Trade toward CBDR extensions",
            "Use 1.0, 1.5, 2.0 SD projections",
            "CBDR high/low are targets"
        ],
        "related_concepts": ["Asian Range", "Standard Deviation", "Killzone"]
    },
    {
        "name": "Asian Range",
        "category": "Time",
        "definition": "The trading range formed during Asian session (7 PM - 2 AM EST). Often swept during London/NY.",
        "key_points": [
            "Usually forms consolidation",
            "High and low are liquidity targets",
            "Often swept during London",
            "Sets up the daily bias"
        ],
        "how_to_identify": "Mark the high and low formed between 7 PM and 2 AM EST.",
        "trading_rules": [
            "Expect Asian range to be swept",
            "Trade breakouts during killzones",
            "Use as entry after sweep"
        ],
        "related_concepts": ["CBDR", "Liquidity Sweep", "London Open"]
    },
    
    # Power of 3 / AMD
    {
        "name": "Power of 3",
        "category": "Price Delivery",
        "definition": "The 3-phase daily algorithm: Accumulation, Manipulation, Distribution. Smart money's daily playbook.",
        "key_points": [
            "Accumulation: Building positions (Asian)",
            "Manipulation: Fake move/stop hunt",
            "Distribution: True move direction",
            "Repeats on multiple timeframes"
        ],
        "how_to_identify": "Asian range = accumulation, London fake = manipulation, NY move = distribution.",
        "trading_rules": [
            "Wait for manipulation phase",
            "Enter during distribution",
            "Don't chase accumulation breakouts"
        ],
        "related_concepts": ["AMD", "Judas Swing", "Smart Money Reversal"]
    },
    {
        "name": "AMD",
        "category": "Price Delivery",
        "definition": "Accumulation, Manipulation, Distribution - The institutional trading cycle that repeats daily.",
        "key_points": [
            "Same as Power of 3",
            "A = Building (Asian)",
            "M = Fake/sweep",
            "D = Real move"
        ],
        "how_to_identify": "Identify the accumulation range, wait for manipulation (sweep), trade the distribution.",
        "trading_rules": [
            "Never trade during accumulation",
            "Identify manipulation as entry signal",
            "Distribution is your trade"
        ],
        "related_concepts": ["Power of 3", "Judas Swing", "Smart Money"]
    },
    
    # Premium/Discount
    {
        "name": "Premium",
        "category": "Price Theory",
        "definition": "Price trading above the 50% (equilibrium) of a range. Favor sells in premium.",
        "key_points": [
            "Above 50% of range",
            "Expensive price",
            "Look for shorts here",
            "Smart money sells premium"
        ],
        "how_to_identify": "Calculate the 50% of the current range. Above this is premium.",
        "trading_rules": [
            "Look for short entries in premium",
            "Don't buy in premium",
            "Use with bearish bias"
        ],
        "related_concepts": ["Discount", "Equilibrium", "Optimal Trade Entry"]
    },
    {
        "name": "Discount",
        "category": "Price Theory",
        "definition": "Price trading below the 50% (equilibrium) of a range. Favor buys in discount.",
        "key_points": [
            "Below 50% of range",
            "Cheap price",
            "Look for longs here",
            "Smart money buys discount"
        ],
        "how_to_identify": "Calculate the 50% of the current range. Below this is discount.",
        "trading_rules": [
            "Look for long entries in discount",
            "Don't sell in discount",
            "Use with bullish bias"
        ],
        "related_concepts": ["Premium", "Equilibrium", "Optimal Trade Entry"]
    },
    {
        "name": "Equilibrium",
        "category": "Price Theory",
        "definition": "The 50% level of any range. Fair value where neither buyers nor sellers have advantage.",
        "key_points": [
            "50% of range",
            "Fair value",
            "Reference point for premium/discount",
            "Often acts as support/resistance"
        ],
        "how_to_identify": "Take the high minus low of a range, divide by 2, add to the low.",
        "trading_rules": [
            "Use to determine premium/discount",
            "Don't enter at equilibrium",
            "Look for entries away from EQ"
        ],
        "related_concepts": ["Premium", "Discount", "Optimal Trade Entry"]
    },
    {
        "name": "Optimal Trade Entry",
        "category": "Price Theory",
        "definition": "The 62-79% retracement zone in a swing. The sweet spot for entries.",
        "key_points": [
            "62-79% fib zone",
            "Best risk-to-reward entries",
            "Often aligns with FVG/OB",
            "Discount for longs, premium for shorts"
        ],
        "how_to_identify": "Draw fib from swing low to high (bullish) or high to low (bearish). OTE is 62-79% zone.",
        "trading_rules": [
            "Enter in OTE zone",
            "Combine with FVG/OB",
            "Stop beyond the swing"
        ],
        "related_concepts": ["Premium", "Discount", "Fair Value Gap", "Order Block"]
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# ICT MODELS
# ─────────────────────────────────────────────────────────────────────────────

ICT_MODELS = [
    {
        "name": "Silver Bullet",
        "description": "High-probability setup during specific 1-hour windows when price creates a FVG and returns to fill it.",
        "time_window": "10-11 AM EST (NY AM) or 2-3 PM EST (NY PM)",
        "setup_criteria": [
            "Must occur during Silver Bullet window",
            "Identify a displacement that creates FVG",
            "Wait for price to retrace to FVG",
            "FVG should be in line with higher timeframe bias"
        ],
        "entry_rules": [
            "Enter when price enters the FVG",
            "Optimal entry at 50% of FVG",
            "Must have HTF confluence"
        ],
        "exit_rules": [
            "Target 1: 2R",
            "Target 2: Next liquidity level",
            "Stop below/above FVG"
        ],
        "best_pairs": ["EUR_USD", "GBP_USD", "NASDAQ"],
        "win_rate": 68.0,
        "avg_rr": 2.5,
        "notes": "One of ICT's most reliable intraday models. Best during NY AM session."
    },
    {
        "name": "Turtle Soup",
        "description": "A liquidity sweep setup where price takes out a high/low, then reverses.",
        "time_window": "Any killzone, best during London/NY overlap",
        "setup_criteria": [
            "Identify old high or low (liquidity)",
            "Wait for price to sweep beyond it",
            "Look for rejection (wick/reversal candle)",
            "Confirm with market structure shift"
        ],
        "entry_rules": [
            "Enter after sweep and rejection",
            "Stop beyond the swept level",
            "Entry on FVG/OB formed after sweep"
        ],
        "exit_rules": [
            "Target opposite liquidity",
            "Use 2-3R minimum",
            "Trail stop after 1R"
        ],
        "best_pairs": ["EUR_USD", "GBP_USD", "USD_JPY"],
        "win_rate": 62.0,
        "avg_rr": 3.0,
        "notes": "Named after the Turtle Traders. Fades breakouts."
    },
    {
        "name": "Judas Swing",
        "description": "A fake/manipulation move against the real direction, designed to trap traders.",
        "time_window": "London Open (2-5 AM EST)",
        "setup_criteria": [
            "Identify daily bias from HTF",
            "Wait for move against the bias during manipulation",
            "Look for liquidity sweep",
            "Confirm reversal with FVG/OB"
        ],
        "entry_rules": [
            "Enter after Judas move reverses",
            "Use FVG/OB as entry",
            "Align with daily bias"
        ],
        "exit_rules": [
            "Target NY session highs/lows",
            "Use CBDR extensions",
            "Minimum 2R target"
        ],
        "best_pairs": ["EUR_USD", "GBP_USD", "XAU_USD"],
        "win_rate": 65.0,
        "avg_rr": 2.5,
        "notes": "The betrayal move. Often occurs during London open."
    },
    {
        "name": "ICT 2022 Model",
        "description": "ICT's refined 2022 approach focusing on 15m FVGs within HTF PD arrays.",
        "time_window": "NY AM Killzone (7-10 AM EST)",
        "setup_criteria": [
            "Daily bias determined",
            "Price in HTF PD array (4H FVG/OB)",
            "15m FVG forms in direction of bias",
            "Liquidity present for target"
        ],
        "entry_rules": [
            "Enter at 15m FVG within HTF zone",
            "50% of 15m FVG optimal",
            "Stop below/above 15m FVG"
        ],
        "exit_rules": [
            "Target next liquidity pool",
            "Use 3R minimum",
            "Scale out at 2R"
        ],
        "best_pairs": ["EUR_USD", "NASDAQ", "ES"],
        "win_rate": 70.0,
        "avg_rr": 3.5,
        "notes": "ICT's most recent and refined model."
    },
    {
        "name": "Unicorn Model",
        "description": "Breaker block + FVG overlap creating a powerful confluence zone.",
        "time_window": "Any killzone",
        "setup_criteria": [
            "Identify a failed order block (breaker)",
            "FVG overlaps with breaker zone",
            "Creates 'unicorn' overlap zone",
            "HTF bias alignment"
        ],
        "entry_rules": [
            "Enter at the overlap zone",
            "This is the 'unicorn' entry",
            "Stop beyond the breaker"
        ],
        "exit_rules": [
            "Target opposing liquidity",
            "3R minimum target",
            "High probability setup"
        ],
        "best_pairs": ["EUR_USD", "GBP_USD", "NASDAQ"],
        "win_rate": 72.0,
        "avg_rr": 3.0,
        "notes": "Rare but very high probability when found."
    },
    {
        "name": "MMXM Model",
        "description": "Market Maker Model - The complete institutional order flow cycle.",
        "time_window": "Multi-day analysis",
        "setup_criteria": [
            "Identify original consolidation",
            "Smart Money Reversal (SMR) forms",
            "Break of structure confirms",
            "Fair Value Gap provides entry"
        ],
        "entry_rules": [
            "Enter at FVG after structure break",
            "Must follow SMR",
            "Align with weekly bias"
        ],
        "exit_rules": [
            "Target original consolidation opposite",
            "Major liquidity pools",
            "Can hold for multiple days"
        ],
        "best_pairs": ["EUR_USD", "GBP_USD", "DXY"],
        "win_rate": 65.0,
        "avg_rr": 5.0,
        "notes": "Swing trading model. Requires patience."
    }
]


def seed_database():
    """Seed the database with ICT knowledge."""
    print("\n" + "=" * 60)
    print("  SEEDING ICT KNOWLEDGE BASE")
    print("=" * 60)
    
    db = get_db()
    
    try:
        # Initialize tables
        print("\n  📦 Initializing tables...")
        db.initialize_tables()
        
        # Seed concepts
        print(f"\n  📚 Adding {len(ICT_CONCEPTS)} ICT concepts...")
        for concept in ICT_CONCEPTS:
            db.save_concept(concept)
            print(f"     ✓ {concept['name']}")
        
        # Seed models
        print(f"\n  🎯 Adding {len(ICT_MODELS)} trading models...")
        for model in ICT_MODELS:
            db.save_model(model)
            print(f"     ✓ {model['name']}")
        
        # Add some initial knowledge
        print("\n  💡 Adding initial knowledge entries...")
        knowledge_entries = [
            {
                "type": "lesson",
                "category": "psychology",
                "content": "The Two Strike Rule: After two consecutive losses on a pair, STOP trading that pair for the day.",
                "source": "Personal rule",
                "importance": "critical",
                "tags": ["risk management", "psychology", "rules"]
            },
            {
                "type": "lesson",
                "category": "execution",
                "content": "Always wait for the killzone. Best setups occur during NY AM (7-10 AM EST).",
                "source": "ICT",
                "importance": "high",
                "tags": ["timing", "killzone", "execution"]
            },
            {
                "type": "insight",
                "category": "market_structure",
                "content": "Liquidity is the fuel for price movement. Without liquidity, price cannot move significantly.",
                "source": "ICT",
                "importance": "high",
                "tags": ["liquidity", "price action", "fundamentals"]
            },
            {
                "type": "lesson",
                "category": "risk",
                "content": "Never risk more than 1% per trade. Protect capital above all else.",
                "source": "Personal rule",
                "importance": "critical",
                "tags": ["risk management", "position sizing"]
            }
        ]
        
        for entry in knowledge_entries:
            db.save_knowledge(entry)
            print(f"     ✓ {entry['type']}: {entry['content'][:50]}...")
        
        # Verify
        print("\n  🔍 Verifying database...")
        concepts = db.get_all_concepts()
        models = db.get_all_models()
        knowledge = db.get_knowledge()
        
        print(f"     Concepts: {len(concepts)}")
        print(f"     Models: {len(models)}")
        print(f"     Knowledge: {len(knowledge)}")
        
        print("\n" + "=" * 60)
        print("  ✅ DATABASE SEEDED SUCCESSFULLY!")
        print("=" * 60)
        
        # Show categories
        categories = set(c['category'] for c in concepts)
        print(f"\n  Categories: {', '.join(sorted(categories))}")
        print(f"\n  Models: {', '.join(m['name'] for m in models)}")
        
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
