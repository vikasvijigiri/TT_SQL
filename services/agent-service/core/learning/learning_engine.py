import json
from core.learning.sqlite_memory import SQLiteMemoryDB
from core.blackboard.run_blackboard import get_blackboard
from core.utils.logger import logger

class LearningEngine:
    """
    Manages Cross-Run learning.
    Reads/writes to the persistent SQLite memory.
    """
    def __init__(self):
        self.db = SQLiteMemoryDB()

    def inject_prior_knowledge(self, user_query: str):
        """
        Runs BEFORE a new execution to pull Top-K relevant past knowledge 
        into the active Blackboard.
        """
        bb = get_blackboard()
        logger.info(f"Retrieving cross-run learning context for query: '{user_query}'")

        # Retrieve relevant past failures
        similar_failures = self.db.search_similar_failures(user_query, limit=3)
        for f in similar_failures:
            logger.info(f"Injected past failure rule: {f['prevention_rule']}")
            # Convert to temporary rule format for the blackboard
            bb.temporary_rules.append({
                "rule": f["prevention_rule"],
                "confidence": 0.9,
                "scope": "cross_run_injected"
            })

        # Retrieve relevant past successes
        similar_successes = self.db.search_similar_successes(user_query, limit=2)
        for s in similar_successes:
            logger.info(f"Injected past success strategy: {s['successful_strategy']}")
            bb.facts.append({
                "fact": f"Past successful strategy: {s['successful_strategy']}",
                "source": "LEARNING_ENGINE",
                "confidence": s['confidence']
            })

    def persist_run_results(self):
        """
        Runs AFTER execution to dump the Blackboard state into SQLite.
        """
        bb = get_blackboard()
        logger.info("Persisting run results to Learning Engine...")

        # 1. Persist new rules from failures
        for rule in bb.temporary_rules:
            if rule["scope"] != "cross_run_injected":
                self.db.insert_failure(
                    f_type="Runtime Rule Generation",
                    root_cause="Derived from blackboard feedback",
                    fix="Applied dynamic rule",
                    rule=rule["rule"]
                )

        # 2. Persist execution errors
        for err in bb.execution_errors:
            self.db.insert_failure(
                f_type=err.get("failure_type", "Execution Error"),
                root_cause=err.get("root_cause", "Unknown"),
                fix=err.get("fix", "Unknown"),
                rule=err.get("prevention_rule", "Unknown")
            )

        # 3. Persist success if confidence is high
        if bb.confidence.get("evidence", 0.0) >= 0.8:
            self.db.insert_success(
                question=bb.goal,
                schema=json.dumps(bb.validated_tables),
                reasoning=bb.answer_strategy,
                strategy="Derived from successful facts accumulation",
                conf=bb.confidence["evidence"]
            )
            logger.success("Successfully persisted cross-run knowledge pattern.")
