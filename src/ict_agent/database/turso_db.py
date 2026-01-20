"""
VEX Turso Database - Cloud storage for trades and ICT knowledge.

Uses HTTP API for compatibility.

Tables:
- trades: All trade records with full journal data
- ict_concepts: Core ICT concepts (FVG, OB, liquidity, etc.)
- ict_models: Trading models (Silver Bullet, Turtle Soup, etc.)
- knowledge: Lessons, insights, patterns learned
- setups: Graded setups for pattern recognition
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Database credentials
TURSO_URL = os.environ.get(
    "TURSO_DATABASE_URL",
    "libsql://ftmo-sixscripts-ai.aws-us-west-2.turso.io"
)
TURSO_AUTH_TOKEN = os.environ.get(
    "TURSO_AUTH_TOKEN",
    "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJleHAiOjI0MDA2NDM0NzcsImlhdCI6MTc2ODg4NjY3NywiaWQiOiI2MzM5Njg2MS1iYWMwLTRjZjItYjZhYy00ZGIwMGRjZjcwNWYiLCJyaWQiOiJjZGMwNzI5OS00NmQ0LTQ4NWItOWNkZS1jZDExN2Q3Y2E2MmMifQ.xz1fEuQyuNWYPiY-sf7wsMcYlYrFVFkumaKsKOVE4wKAIZCd6IWMa6h8-lw77K2eAuU5CRZh1j8bRGgB8oeYDQ"
)


def get_http_url(libsql_url: str) -> str:
    """Convert libsql:// URL to HTTPS URL for HTTP API."""
    if libsql_url.startswith("libsql://"):
        return "https://" + libsql_url[9:]
    return libsql_url


class TursoDB:
    """
    Turso database client for VEX trading system using HTTP API.
    
    Stores:
    - Trade journal entries
    - ICT concepts and definitions
    - Trading models and setups
    - Learned knowledge and patterns
    """
    
    def __init__(self):
        self.base_url = get_http_url(TURSO_URL)
        self.auth_token = TURSO_AUTH_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        })
    
    def execute(self, sql: str, params: Optional[List] = None) -> Dict:
        """Execute SQL query via HTTP API."""
        url = f"{self.base_url}/v2/pipeline"
        
        # Build request body
        stmt: Dict[str, Any] = {"sql": sql}
        if params:
            # Convert params to proper format
            args = []
            for p in params:
                if p is None:
                    args.append({"type": "null", "value": None})
                elif isinstance(p, bool):
                    args.append({"type": "integer", "value": str(1 if p else 0)})
                elif isinstance(p, int):
                    args.append({"type": "integer", "value": str(p)})
                elif isinstance(p, float):
                    # Turso expects float as number, not string
                    args.append({"type": "float", "value": p})
                else:
                    args.append({"type": "text", "value": str(p)})
            stmt["args"] = args
        
        body = {
            "requests": [
                {"type": "execute", "stmt": stmt},
                {"type": "close"}
            ]
        }
        
        response = self.session.post(url, json=body)
        
        if response.status_code != 200:
            raise Exception(f"Database error: {response.status_code} - {response.text}")
        
        data = response.json()
        
        # Check for errors
        if "results" in data and len(data["results"]) > 0:
            result = data["results"][0]
            if result.get("type") == "error":
                raise Exception(f"SQL Error: {result.get('error', {}).get('message', 'Unknown error')}")
            
            if result.get("type") == "ok" and "response" in result:
                resp = result["response"]
                if resp.get("type") == "execute":
                    exec_result = resp.get("result", {})
                    return {
                        "columns": [col["name"] for col in exec_result.get("cols", [])],
                        "rows": [[self._parse_value(v) for v in row] for row in exec_result.get("rows", [])],
                        "affected_rows": exec_result.get("affected_row_count", 0),
                        "last_insert_id": exec_result.get("last_insert_rowid")
                    }
        
        return {"columns": [], "rows": [], "affected_rows": 0}
    
    def _parse_value(self, value: Any) -> Any:
        """Parse a value from the API response."""
        if value is None:
            return None
        if isinstance(value, dict):
            val_type = value.get("type")
            val = value.get("value")
            if val_type == "null":
                return None
            if val_type == "integer":
                return int(val) if val else 0
            if val_type == "float":
                return float(val) if val else 0.0
            return val
        return value
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def initialize_tables(self):
        """Create all required tables if they don't exist."""
        
        # Trades table
        self.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                pair TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                position_size REAL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                pnl_dollars REAL,
                pnl_pips REAL,
                
                daily_bias TEXT,
                killzone TEXT,
                setup_type TEXT,
                setup_grade TEXT,
                confluence_score INTEGER,
                emotional_state TEXT,
                confidence INTEGER,
                reasoning TEXT,
                
                executed_as_planned INTEGER,
                lessons_learned TEXT,
                what_worked TEXT,
                what_didnt TEXT,
                overall_grade TEXT,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                entry_time TEXT,
                exit_time TEXT,
                updated_at TEXT
            )
        """)
        
        # ICT Concepts table
        self.execute("""
            CREATE TABLE IF NOT EXISTS ict_concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                definition TEXT,
                key_points TEXT,
                how_to_identify TEXT,
                trading_rules TEXT,
                examples TEXT,
                related_concepts TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        """)
        
        # ICT Models table
        self.execute("""
            CREATE TABLE IF NOT EXISTS ict_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                time_window TEXT,
                setup_criteria TEXT,
                entry_rules TEXT,
                exit_rules TEXT,
                best_pairs TEXT,
                win_rate REAL,
                avg_rr REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
        """)
        
        # Knowledge base table
        self.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                category TEXT,
                content TEXT NOT NULL,
                source TEXT,
                importance TEXT DEFAULT 'medium',
                tags TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Graded setups table
        self.execute("""
            CREATE TABLE IF NOT EXISTS setups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT,
                pair TEXT NOT NULL,
                direction TEXT NOT NULL,
                setup_type TEXT,
                grade TEXT,
                score REAL,
                
                htf_alignment INTEGER,
                pd_array_quality INTEGER,
                liquidity_present INTEGER,
                timing_score INTEGER,
                rr_ratio REAL,
                
                daily_bias TEXT,
                killzone TEXT,
                market_condition TEXT,
                
                result TEXT,
                actual_rr REAL,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("  ✅ Database tables initialized")
        return True
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRADES
    # ─────────────────────────────────────────────────────────────────────────
    
    def save_trade(self, trade: Dict) -> str:
        """Save a trade to the database."""
        trade_id = trade.get("id", f"T{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        self.execute(
            """
            INSERT OR REPLACE INTO trades (
                id, pair, direction, entry_price, stop_loss, take_profit,
                position_size, status, result, pnl_dollars, pnl_pips,
                daily_bias, killzone, setup_type, setup_grade, confluence_score,
                emotional_state, confidence, reasoning,
                executed_as_planned, lessons_learned, what_worked, what_didnt,
                overall_grade, created_at, entry_time, exit_time, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                trade_id,
                trade.get("pair"),
                trade.get("direction"),
                trade.get("entry_price"),
                trade.get("stop_loss"),
                trade.get("take_profit"),
                trade.get("position_size"),
                trade.get("status", "pending"),
                trade.get("result"),
                trade.get("pnl_dollars"),
                trade.get("pnl_pips"),
                trade.get("daily_bias"),
                trade.get("killzone"),
                trade.get("setup_type"),
                trade.get("setup_grade"),
                trade.get("confluence_score"),
                trade.get("emotional_state"),
                trade.get("confidence"),
                trade.get("reasoning"),
                1 if trade.get("executed_as_planned") else 0,
                trade.get("lessons_learned"),
                trade.get("what_worked"),
                trade.get("what_didnt"),
                trade.get("overall_grade"),
                trade.get("created_at", datetime.now().isoformat()),
                trade.get("entry_time"),
                trade.get("exit_time"),
                datetime.now().isoformat()
            ]
        )
        
        return trade_id
    
    def get_trade(self, trade_id: str) -> Optional[Dict]:
        """Get a trade by ID."""
        result = self.execute(
            "SELECT * FROM trades WHERE id = ?",
            [trade_id]
        )
        
        if result["rows"]:
            return dict(zip(result["columns"], result["rows"][0]))
        return None
    
    def get_trades(
        self,
        status: Optional[str] = None,
        pair: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get trades with optional filters."""
        query = "SELECT * FROM trades WHERE 1=1"
        params: List[Any] = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if pair:
            query += " AND pair = ?"
            params.append(pair)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        result = self.execute(query, params)
        return [dict(zip(result["columns"], row)) for row in result["rows"]]
    
    def get_trade_stats(self) -> Dict:
        """Get aggregate trade statistics."""
        result = self.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN result = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(pnl_dollars) as total_pnl,
                AVG(CASE WHEN result = 'WIN' THEN pnl_dollars END) as avg_win,
                AVG(CASE WHEN result = 'LOSS' THEN pnl_dollars END) as avg_loss
            FROM trades WHERE status = 'closed'
        """)
        
        if result["rows"]:
            row = result["rows"][0]
            total = int(row[0] or 0)
            wins = int(row[1] or 0)
            losses = int(row[2] or 0)
            
            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
                "total_pnl": round(float(row[3] or 0), 2),
                "avg_win": round(float(row[4] or 0), 2),
                "avg_loss": round(float(row[5] or 0), 2)
            }
        
        return {}
    
    # ─────────────────────────────────────────────────────────────────────────
    # ICT CONCEPTS
    # ─────────────────────────────────────────────────────────────────────────
    
    def save_concept(self, concept: Dict) -> int:
        """Save an ICT concept."""
        result = self.execute(
            """
            INSERT OR REPLACE INTO ict_concepts (
                name, category, definition, key_points, how_to_identify,
                trading_rules, examples, related_concepts, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                concept.get("name"),
                concept.get("category"),
                concept.get("definition"),
                json.dumps(concept.get("key_points", [])),
                concept.get("how_to_identify"),
                json.dumps(concept.get("trading_rules", [])),
                json.dumps(concept.get("examples", [])),
                json.dumps(concept.get("related_concepts", [])),
                datetime.now().isoformat()
            ]
        )
        
        return result.get("last_insert_id") or 0
    
    def get_concept(self, name: str) -> Optional[Dict]:
        """Get a concept by name."""
        result = self.execute(
            "SELECT * FROM ict_concepts WHERE name = ?",
            [name]
        )
        
        if result["rows"]:
            row = dict(zip(result["columns"], result["rows"][0]))
            # Parse JSON fields
            for field in ['key_points', 'trading_rules', 'examples', 'related_concepts']:
                if row.get(field):
                    try:
                        row[field] = json.loads(row[field])
                    except:
                        pass
            return row
        return None
    
    def get_concepts_by_category(self, category: str) -> List[Dict]:
        """Get all concepts in a category."""
        result = self.execute(
            "SELECT * FROM ict_concepts WHERE category = ? ORDER BY name",
            [category]
        )
        
        concepts = []
        for row in result["rows"]:
            concept = dict(zip(result["columns"], row))
            for field in ['key_points', 'trading_rules', 'examples', 'related_concepts']:
                if concept.get(field):
                    try:
                        concept[field] = json.loads(concept[field])
                    except:
                        pass
            concepts.append(concept)
        return concepts
    
    def search_concepts(self, query: str) -> List[Dict]:
        """Search concepts by name or definition."""
        result = self.execute(
            """
            SELECT * FROM ict_concepts 
            WHERE name LIKE ? OR definition LIKE ? OR category LIKE ?
            ORDER BY name
            """,
            [f"%{query}%", f"%{query}%", f"%{query}%"]
        )
        
        return [dict(zip(result["columns"], row)) for row in result["rows"]]
    
    def get_all_concepts(self) -> List[Dict]:
        """Get all concepts."""
        result = self.execute("SELECT * FROM ict_concepts ORDER BY category, name")
        
        concepts = []
        for row in result["rows"]:
            concept = dict(zip(result["columns"], row))
            for field in ['key_points', 'trading_rules', 'examples', 'related_concepts']:
                if concept.get(field):
                    try:
                        concept[field] = json.loads(concept[field])
                    except:
                        pass
            concepts.append(concept)
        return concepts
    
    # ─────────────────────────────────────────────────────────────────────────
    # ICT MODELS
    # ─────────────────────────────────────────────────────────────────────────
    
    def save_model(self, model: Dict) -> int:
        """Save an ICT trading model."""
        result = self.execute(
            """
            INSERT OR REPLACE INTO ict_models (
                name, description, time_window, setup_criteria,
                entry_rules, exit_rules, best_pairs, win_rate, avg_rr, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                model.get("name"),
                model.get("description"),
                model.get("time_window"),
                json.dumps(model.get("setup_criteria", [])),
                json.dumps(model.get("entry_rules", [])),
                json.dumps(model.get("exit_rules", [])),
                json.dumps(model.get("best_pairs", [])),
                model.get("win_rate"),
                model.get("avg_rr"),
                model.get("notes"),
                datetime.now().isoformat()
            ]
        )
        
        return result.get("last_insert_id") or 0
    
    def get_model(self, name: str) -> Optional[Dict]:
        """Get a model by name."""
        result = self.execute(
            "SELECT * FROM ict_models WHERE name = ?",
            [name]
        )
        
        if result["rows"]:
            row = dict(zip(result["columns"], result["rows"][0]))
            for field in ['setup_criteria', 'entry_rules', 'exit_rules', 'best_pairs']:
                if row.get(field):
                    try:
                        row[field] = json.loads(row[field])
                    except:
                        pass
            return row
        return None
    
    def get_all_models(self) -> List[Dict]:
        """Get all trading models."""
        result = self.execute("SELECT * FROM ict_models ORDER BY name")
        
        models = []
        for row in result["rows"]:
            model = dict(zip(result["columns"], row))
            for field in ['setup_criteria', 'entry_rules', 'exit_rules', 'best_pairs']:
                if model.get(field):
                    try:
                        model[field] = json.loads(model[field])
                    except:
                        pass
            models.append(model)
        return models
    
    # ─────────────────────────────────────────────────────────────────────────
    # KNOWLEDGE BASE
    # ─────────────────────────────────────────────────────────────────────────
    
    def save_knowledge(self, entry: Dict) -> int:
        """Save a knowledge entry."""
        result = self.execute(
            """
            INSERT INTO knowledge (type, category, content, source, importance, tags)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                entry.get("type", "lesson"),
                entry.get("category"),
                entry.get("content"),
                entry.get("source"),
                entry.get("importance", "medium"),
                json.dumps(entry.get("tags", []))
            ]
        )
        
        return result.get("last_insert_id") or 0
    
    def get_knowledge(
        self,
        knowledge_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get knowledge entries with optional filters."""
        query = "SELECT * FROM knowledge WHERE 1=1"
        params: List[Any] = []
        
        if knowledge_type:
            query += " AND type = ?"
            params.append(knowledge_type)
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        result = self.execute(query, params)
        
        entries = []
        for row in result["rows"]:
            entry = dict(zip(result["columns"], row))
            if entry.get("tags"):
                try:
                    entry["tags"] = json.loads(entry["tags"])
                except:
                    pass
            entries.append(entry)
        return entries
    
    # ─────────────────────────────────────────────────────────────────────────
    # SETUPS
    # ─────────────────────────────────────────────────────────────────────────
    
    def save_setup(self, setup: Dict) -> int:
        """Save a graded setup."""
        result = self.execute(
            """
            INSERT INTO setups (
                trade_id, pair, direction, setup_type, grade, score,
                htf_alignment, pd_array_quality, liquidity_present, timing_score, rr_ratio,
                daily_bias, killzone, market_condition, result, actual_rr
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                setup.get("trade_id"),
                setup.get("pair"),
                setup.get("direction"),
                setup.get("setup_type"),
                setup.get("grade"),
                setup.get("score"),
                setup.get("htf_alignment"),
                setup.get("pd_array_quality"),
                setup.get("liquidity_present"),
                setup.get("timing_score"),
                setup.get("rr_ratio"),
                setup.get("daily_bias"),
                setup.get("killzone"),
                setup.get("market_condition"),
                setup.get("result"),
                setup.get("actual_rr")
            ]
        )
        
        return result.get("last_insert_id") or 0
    
    def get_setups_by_grade(self, min_grade: str = "A") -> List[Dict]:
        """Get setups by minimum grade."""
        grade_order = {"A+": 1, "A": 2, "A-": 3, "B+": 4, "B": 5, "B-": 6, "C+": 7, "C": 8}
        max_order = grade_order.get(min_grade, 5)
        
        valid_grades = [g for g, o in grade_order.items() if o <= max_order]
        placeholders = ",".join(["?" for _ in valid_grades])
        
        result = self.execute(
            f"SELECT * FROM setups WHERE grade IN ({placeholders}) ORDER BY score DESC",
            valid_grades
        )
        
        return [dict(zip(result["columns"], row)) for row in result["rows"]]


def get_db() -> TursoDB:
    """Get a database instance."""
    return TursoDB()


# ─────────────────────────────────────────────────────────────────────────────
# CLI TEST
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Test database connection and initialization."""
    print("\n  🔌 Testing Turso database connection...")
    
    db = get_db()
    
    try:
        # Test connection
        result = db.execute("SELECT 1 as test")
        print(f"  ✅ Connected to Turso! Test: {result['rows']}")
        
        # Initialize tables
        db.initialize_tables()
        
        # Test saving a concept
        db.save_concept({
            "name": "Fair Value Gap",
            "category": "PD Arrays",
            "definition": "A 3-candle pattern where the wicks of candles 1 and 3 don't overlap, creating an imbalance",
            "key_points": [
                "Forms during displacement",
                "Acts as support/resistance",
                "Price tends to return to fill or react to FVGs"
            ],
            "how_to_identify": "Look for 3 consecutive candles where candle 1 high < candle 3 low (bullish) or candle 1 low > candle 3 high (bearish)",
            "trading_rules": [
                "Trade in direction of the FVG formation",
                "Use as entry zone on retracement",
                "Place stop beyond the FVG"
            ],
            "related_concepts": ["Order Block", "Displacement", "Imbalance"]
        })
        print("  ✅ Test concept saved!")
        
        # Verify
        concept = db.get_concept("Fair Value Gap")
        if concept:
            print(f"  ✅ Retrieved: {concept['name']} ({concept['category']})")
        
        print("\n  🎉 Database ready for use!")
        
    except Exception as e:
        print(f"\n  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
