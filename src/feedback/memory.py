import json
import os
from typing import List, Dict

MEMORY_FILE = "resources/memory/lessons.json"

class MemoryManager:
    def __init__(self):
        self.memory_path = MEMORY_FILE
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        if not os.path.exists(self.memory_path):
            with open(self.memory_path, 'w') as f:
                json.dump([], f)

    def add_lesson(self, user_query: str, error: str, correction_thought: str, successful_sql: str):
        """Distills a lesson from a successful correction."""
        lesson = {
            "user_intent_pattern": user_query[:100], # Simple pattern for now
            "error_encountered": error,
            "fix_reasoning": correction_thought,
            "successful_pattern": "..." # Could be simplified SQL
        }
        
        lessons = self.load_lessons()
        # Avoid exact duplicates
        if any(l['fix_reasoning'] == correction_thought for l in lessons):
            return
            
        lessons.append(lesson)
        with open(self.memory_path, 'w') as f:
            json.dump(lessons[-10:], f, indent=2) # Keep last 10 lessons for context

    def load_lessons(self) -> List[Dict]:
        try:
            with open(self.memory_path, 'r') as f:
                return json.load(f)
        except:
            return []

    def get_context_string(self) -> str:
        lessons = self.load_lessons()
        if not lessons:
            return "No previous lessons learned yet."
            
        formatted = "PREVIOUS LESSONS LEARNED (Internal Knowledge):\n"
        for i, l in enumerate(lessons):
            formatted += f"{i+1}. When encountering '{l['error_encountered']}', the fix was: {l['fix_reasoning']}\n"
        return formatted
