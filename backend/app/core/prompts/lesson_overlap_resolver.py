from typing import List, Tuple, Set
from backend.app.core.prompts.global_deduplicator import GlobalPromptDeduplicator
from backend.app.utils.logger import logger

class LessonRuleOverlapResolver:
    """
    Enterprise Lesson-Rule Overlap Resolver.
    Compares past lesson experiences against active dialect rules and reasoning directives.
    If a lesson merely restates an established rule (e.g., 'Remember to quote identifiers'),
    it is surgically excised, keeping only novel domain deltas or removing the lesson entirely.
    """

    @classmethod
    def resolve_overlap(cls, past_lessons: str, active_rules: List[str], active_directives: str) -> Tuple[str, int]:
        """
        Deduplicates past lessons against active dialect rules and directives.
        Returns clean past lessons and total tokens saved.
        """
        if not past_lessons or len(past_lessons.strip()) < 5:
            return "", 0

        # Build baseline set of rule and directive semantic keys
        baseline_keys: Set[str] = set()
        for rule in active_rules:
            k = GlobalPromptDeduplicator.get_core_semantic_key(rule)
            if len(k) > 4:
                baseline_keys.add(k)

        if active_directives:
            for line in active_directives.splitlines():
                k = GlobalPromptDeduplicator.get_core_semantic_key(line)
                if len(k) > 4:
                    baseline_keys.add(k)

        if not baseline_keys:
            return past_lessons.strip(), 0

        raw_tokens = max(1, len(past_lessons) // 4)
        clean_lines = []
        tokens_saved = 0

        lines = past_lessons.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str:
                clean_lines.append("")
                continue

            # Check if line is just a decorative header like === PAST LESSONS === or VALUE MAPPINGS
            if "===" in line_str or "VALUE MAPPINGS" in line_str:
                clean_lines.append(line)
                continue

            key = GlobalPromptDeduplicator.get_core_semantic_key(line_str)
            if len(key) < 5:
                clean_lines.append(line)
                continue

            # Check for overlap against baseline keys
            is_overlap = False
            if key in baseline_keys:
                is_overlap = True
            else:
                for base in baseline_keys:
                    if GlobalPromptDeduplicator.compute_jaccard_similarity(key, base) >= 0.80 or base in key:
                        is_overlap = True
                        break

            if is_overlap:
                tokens_saved += max(1, len(line_str) // 4)
                logger.debug(f"[LessonResolver] Removed lesson line overlapping with core rule: '{line_str[:50]}...'")
            else:
                clean_lines.append(line)

        clean_text = "\n".join(clean_lines).strip()
        # If all substantive lines were removed, clear entirely
        substantive = [l for l in clean_lines if l.strip() and not ("===" in l or "VALUE MAPPINGS" in l)]
        if not substantive:
            tokens_saved = raw_tokens
            return "", tokens_saved

        return clean_text, tokens_saved
