"""
Vector Lesson Memory Engine

Replaces the static LessonRollback history.
Dynamically retrieves Top K (default 3) relevant lessons based on string similarity
to the query, schema context, and error type.
"""

import json
import math
import os
from collections import Counter
from typing import List, Dict, Any

from core.utils.logger import logger

class VectorLessonMemory:
    def __init__(self, storage_path: str = "lessons_db.json"):
        self.storage_path = storage_path
        self.lessons: List[Dict[str, Any]] = self._load_lessons()

    def _load_lessons(self) -> List[Dict[str, Any]]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[VectorLessonMemory] Failed to load lessons: {e}")
        return []

    def _save_lessons(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.lessons, f, indent=2)
        except Exception as e:
            logger.error(f"[VectorLessonMemory] Failed to save lessons: {e}")

    def store_lesson(self, question: str, error_type: str, fix: str, dialect: str):
        """Store a new lesson into memory."""
        lesson = {
            "question": question,
            "error_type": error_type,
            "fix": fix,
            "dialect": dialect
        }
        self.lessons.append(lesson)
        self._save_lessons()
        logger.info(f"[VectorLessonMemory] Stored new lesson for error '{error_type}'.")

    def _compute_cosine_similarity(self, text1: str, text2: str) -> float:
        """Simple Bag-of-Words Cosine Similarity without heavy dependencies."""
        def get_words(text):
            import re
            words = re.compile(r'\w+').findall(text.lower())
            return Counter(words)

        vec1 = get_words(text1)
        vec2 = get_words(text2)
        
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])
        
        sum1 = sum([vec1[x]**2 for x in vec1.keys()])
        sum2 = sum([vec2[x]**2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)
        
        if not denominator:
            return 0.0
        return float(numerator) / denominator

    def retrieve_top_k(self, question: str, error_type: str = "", dialect: str = "", k: int = 3) -> str:
        """
        Retrieve the top K most relevant lessons.
        If error_type is provided, exact matches get a heavy boost.
        """
        if not self.lessons:
            return ""

        query_text = f"{question} {error_type}"
        scored_lessons = []

        for lesson in self.lessons:
            # Skip cross-dialect lessons if strictly different, though often logic overlaps
            if dialect and lesson.get("dialect") and dialect != lesson.get("dialect"):
                continue

            lesson_text = f"{lesson.get('question', "")} {lesson.get('error_type', "")}"
            score = self._compute_cosine_similarity(query_text, lesson_text)
            
            # Boost exact error matches
            if error_type and error_type.lower() == lesson.get("error_type", "").lower():
                score += 1.0
                
            scored_lessons.append((score, lesson))

        # Sort descending
        scored_lessons.sort(key=lambda x: x[0], reverse=True)
        top_lessons = [item[1] for item in scored_lessons[:k]]

        if not top_lessons:
            return ""

        # Format retrieved lessons
        formatted = []
        for i, l in enumerate(top_lessons):
            formatted.append(f"Lesson {i+1} [Error: {l.get('error_type', 'Unknown')}]:\n{l.get('fix')}")
            
        return "\n\n".join(formatted)

vector_lesson_memory = VectorLessonMemory()
