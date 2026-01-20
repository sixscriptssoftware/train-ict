"""VEX Learning Module

Two systems:
1. TradeLearner - Learns from trade outcomes (wins/losses/patterns)
2. KnowledgeManager - Manages ALL knowledge (concepts, models, user teachings)
"""

from ict_agent.learning.trade_learner import TradeLearner
from ict_agent.learning.knowledge_manager import (
    KnowledgeManager, 
    get_knowledge_manager,
    learn,
    add_rule,
    explain,
    search,
)

__all__ = [
    "TradeLearner",
    "KnowledgeManager",
    "get_knowledge_manager",
    "learn",
    "add_rule", 
    "explain",
    "search",
]
