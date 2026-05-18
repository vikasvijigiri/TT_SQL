import json
from typing import Type, Dict, Any, List, Union
from pydantic import BaseModel
from backend.app.utils.logger import logger

class SchemaCompactor:
    """
    Enterprise Pydantic Schema Compaction Engine.
    Converts full verbose JSON schemas (containing anyOf, titles, descriptions, defaults)
    into minimal, clean JSON example skeletons, saving thousands of tokens per LLM call
    while strictly preserving structural reliability.
    """

    @classmethod
    def _get_type_skeleton(cls, field_type: Any) -> Any:
        origin = getattr(field_type, '__origin__', None)
        args = getattr(field_type, '__args__', ())

        # Handle Optional / Union
        if origin is Union:
            # Pick the first non-None type
            for arg in args:
                if arg != type(None):
                    return cls._get_type_skeleton(arg)
            return "string"

        # Handle List / Tuple / Set
        if origin in (list, tuple, set, List):
            if args:
                return [cls._get_type_skeleton(args[0])]
            return ["string"]

        # Handle Dict
        if origin in (dict, Dict):
            return {"string": "string"}

        # Handle BaseModel subclasses
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            return cls._build_skeleton_dict(field_type)

        # Base scalar types
        if field_type in (int, float):
            return 0
        if field_type == bool:
            return True
        return "string"

    @classmethod
    def _build_skeleton_dict(cls, model: Type[BaseModel]) -> Dict[str, Any]:
        skeleton = {}
        fields = getattr(model, 'model_fields', getattr(model, '__fields__', {}))
        
        for field_name, field_info in fields.items():
            field_type = getattr(field_info, 'annotation', getattr(field_info, 'type_', str))
            skeleton[field_name] = cls._get_type_skeleton(field_type)

        return skeleton

    @classmethod
    def compact_json_schema(cls, model: Type[BaseModel]) -> str:
        """
        Takes a Pydantic BaseModel class and returns a beautifully formatted, compact
        JSON skeleton string stripped of all metadata verbosity.
        """
        try:
            skeleton = cls._build_skeleton_dict(model)
            compact_str = json.dumps(skeleton, indent=2)
            logger.debug(f"[SchemaCompactor] Generated compact schema for '{model.__name__}' (~{max(1, len(compact_str)//4)} tokens).")
            return compact_str
        except Exception as e:
            logger.warning(f"[SchemaCompactor] Failed to compact schema for '{model.__name__}': {e}. Using raw schema fallback.")
            try:
                return json.dumps(model.model_json_schema(), indent=2)
            except:
                return f"{{\n  // Required fields matching {model.__name__}\n}}"
