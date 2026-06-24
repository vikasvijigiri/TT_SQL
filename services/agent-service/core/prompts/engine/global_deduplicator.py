import re
from typing import List, Set, Tuple
from core.utils.logger import logger


class GlobalPromptDeduplicator:
    """
    Enterprise Global Prompt Deduplication Engine.
    Detects and eliminates semantically identical or near-duplicate instructions across
    system prompts, user prompts, dialect rules, and past lessons.
    """

    STOP_PREFIXES = [
        "always",
        "strictly",
        "ensure",
        "remember to",
        "make sure to",
        "verify that",
        "note that",
        "rule",
        "directive",
        "must",
        "important",
    ]

    @classmethod
    def get_core_semantic_key(cls, text: str) -> str:
        """
        Strips whitespace, punctuation, common instructional prefixes, and stopwords
        to produce a highly robust canonical matching key for near-duplicate detection.
        Example: 'Always double quote identifiers' -> 'double quote identifiers'.
        """
        clean = text.lower()
        # Remove markdown bullet prefixes or numbers
        clean = re.sub(r"^[\*\-\'\d\.\)]+\s*", "", clean)
        # Remove common prefixes
        pattern_prefixes = re.compile(
            r"\b(?:" + "|".join(cls.STOP_PREFIXES) + r")\b\s*:\s*", re.IGNORECASE
        )
        clean = pattern_prefixes.sub("", clean)

        # Remove stop prefixes if they appear at the very beginning of the sentence
        for prefix in cls.STOP_PREFIXES:
            if clean.startswith(f"{prefix} "):
                clean = clean[len(prefix) + 1 :].strip()

        # Remove punctuation and extra whitespace
        clean = re.sub(r"[^\w\s]", "", clean)
        tokens = clean.split()
        return " ".join(tokens)

    @classmethod
    def compute_jaccard_similarity(cls, key1: str, key2: str) -> float:
        """Computes Jaccard word set similarity between two canonical keys."""
        set1 = set(key1.split())
        set2 = set(key2.split())
        if not set1 or not set2:
            return 0.0
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        return len(intersection) / len(union)

    @classmethod
    def deduplicate_lines(
        cls,
        lines: List[str],
        global_seen_keys: Set[str] | None = None,
        similarity_threshold: float = 0.85,
    ) -> Tuple[List[str], int]:
        """
        Deduplicates a list of text lines against an optional global set of already seen keys.
        Returns the deduplicated lines and the count of tokens saved.
        """
        if global_seen_keys is None:
            global_seen_keys = set()

        deduped = []
        tokens_saved = 0

        for line in lines:
            line_str = line.strip()
            if not line_str or len(line_str) < 5:
                deduped.append(line)
                continue

            key = cls.get_core_semantic_key(line_str)
            if not key or len(key) < 4:
                deduped.append(line)
                continue

            # Check exact match or near duplicate in seen keys
            is_dup = False
            if key in global_seen_keys:
                is_dup = True
            else:
                for seen in global_seen_keys:
                    if (
                        cls.compute_jaccard_similarity(key, seen)
                        >= similarity_threshold
                    ):
                        is_dup = True
                        break

            if is_dup:
                tokens_saved += max(1, len(line_str) // 4)
                logger.debug(
                    f"[GlobalDeduplicator] Removed duplicate line: '{line_str[:50]}...'"
                )
            else:
                global_seen_keys.add(key)
                deduped.append(line)

        return deduped, tokens_saved

    @classmethod
    def deduplicate_section_content(
        cls,
        content: str,
        global_seen_keys: Set[str],
        similarity_threshold: float = 0.85,
    ) -> Tuple[str, int]:
        """Deduplicates bulleted or multiline content within a specific prompt section."""
        if not content:
            return "", 0

        lines = content.splitlines()
        clean_lines, savings = cls.deduplicate_lines(
            lines, global_seen_keys, similarity_threshold
        )
        return "\n".join(clean_lines).strip(), savings
