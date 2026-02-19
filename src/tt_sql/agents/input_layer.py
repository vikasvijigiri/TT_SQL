import os
import sqlite3
from typing import Dict, Any, List
from ..core.agent_base import BaseAgent, AgentState
from ..core.llm_service import LLMService
from ..core.prompt_loader import PromptLoader
from ..core.file_coordinator import FileCoordinator
from ..rag.vector_store import VectorStoreAgent
import json

def format_schema_to_str(schema_info: Dict[str, Any]) -> str:
    """Formats schema dict into a compact string: Table(col1, col2)"""
    if not schema_info: return ""
    lines = []
    for table, data in schema_info.items():
        # Handle potential dictionary structure
        if isinstance(data, dict) and "columns" in data:
            cols = data["columns"]
        elif isinstance(data, list):
            cols = data
        else:
            cols = []
            
        col_names = [c.get("name", c) if isinstance(c, dict) else str(c) for c in cols]
        lines.append(f"{table}({', '.join(col_names)})")
    return "\n".join(lines)

class SQLiteFileLoaderAgent(BaseAgent):
    """
    Validates that the SQLite file exists and is accessible.
    """
    def __init__(self):
        super().__init__(name="SQLiteFileLoader")

    def run(self, state: AgentState) -> AgentState:
        self.log(state, "PLAN_CATEGORY: 📁 Database Access")
        db_path = state.db_path
        
        if not os.path.exists(db_path):
             self.log(state, f"ERROR: Database file not found at {db_path}")
             raise FileNotFoundError(f"Database at {db_path} does not exist.")
        
        # Test connection
        try:
            conn = sqlite3.connect(db_path)
            conn.close()
            self.log(state, f"PLAN_STEP: 1. Database Found at {os.path.basename(db_path)}")
            self.log(state, "PLAN_STEP: 2. SQL Connection Established")
        except sqlite3.Error as e:
            self.log(state, f"ERROR: Failed to open SQLite DB: {e}")
            raise e
            
        return state

class SchemaAnalyzerAgent(BaseAgent):
    """
    Extracts schema information (tables, columns, types) from the SQLite database.
    """
    def __init__(self):
        super().__init__(name="SchemaAnalyzer")
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        self.log(state, "PLAN_CATEGORY: 🔍 Semantic Analysis")
        conn = sqlite3.connect(state.db_path)
        cursor = conn.cursor()
        
        schema_info = {}
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            # Format: (cid, name, type, notnull, dflt_value, pk)
            col_details = []
            for col in columns:
                col_details.append({
                    "name": col[1],
                    "type": col[2],
                    "pk": bool(col[5])
                })
            
            # Simple foreign key check
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            fks = cursor.fetchall()
            # Format: (id, seq, table, from, to, on_update, on_delete, match)
            fk_details = []
            for fk in fks:
                fk_details.append({
                    "to_table": fk[2],
                    "from_col": fk[3], 
                    "to_col": fk[4]
                })
                
            schema_info[table] = {
                "columns": col_details,
                "foreign_keys": fk_details
            }
            
        conn.close()
        
        
        state.schema_info = schema_info
        
        # Write schema to results/{model}/schema/ for downstream agents
        try:
            self.file_coordinator.write_schema(state.instance_id, schema_info, state.model_name)
            self.log(state, f"PLAN_STEP: 3. Schema Extracted & Saved to dynamic path ({len(tables)} tables identified)")
        except Exception as e:
            self.log(state, f"Warning: Could not write schema file: {e}", level="WARN")
            self.log(state, f"PLAN_STEP: 3. Schema Extracted (Memory only) ({len(tables)} tables identified)")
        return state




class ContextEnrichmentAgent(BaseAgent):
    """
    Enriches the context by identifying relevant tables/terms.
    """
    def __init__(self, llm_service: LLMService):
        super().__init__(name="TableSelector")
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.file_coordinator = FileCoordinator()
        
    def run(self, state: AgentState) -> AgentState:
        # Prepare inputs from state
        schema_context = format_schema_to_str(state.schema_info)
        
        # No intent data to pass — the LLM will classify it in this same call
        intent_context = "Not yet classified — please classify in your response."
        
        kb_context_str = ""
        rag_source = getattr(state, "rag_source", "none")
        
        # --- 1. Qdrant (Local Vector Store) ---
        if rag_source == "qdrant":
             try:
                 # Instantiate on demand to avoid overhead if not used
                 vector_store = VectorStoreAgent() 
                 examples = vector_store.retrieve_similar_examples(state.user_query, limit=3)
                 
                 if examples:
                     kb_context_str += "#### Similar Past Examples (from Qdrant):\n"
                     for ex in examples:
                         kb_context_str += f"- **User Query**: {ex['query']}\n  **Correct SQL**: `{ex['sql']}`\n\n"
                     
                     self.log(state, f"Retrieved {len(examples)} examples from Qdrant")
                 else:
                     self.log(state, "No examples found in Qdrant")

                 # --- RAG TABLE RETRIEVAL ---
                 rag_tables = vector_store.retrieve_relevant_tables(state.user_query, limit=8)
                 if rag_tables:
                     kb_context_str += "\n#### Relevant Table Suggestions (from Vector Search):\n"
                     kb_context_str += "The following tables were found to be semantically relevant to the query:\n"
                     for t in rag_tables:
                         kb_context_str += f"- **{t['table_name']}** (Similarity: {t['score']:.2f})\n"
                     
                     self.log(state, f"Retrieved {len(rag_tables)} relevant tables from Qdrant")

             except Exception as e:
                 self.log(state, f"Qdrant retrieval failed: {e}")

        # --- 2. Amazon Bedrock Knowledge Base ---
        elif rag_source == "bedrock":
            kb_id = os.getenv("BEDROCK_KB_ID")
            
            if kb_id:
                self.log(state, f"Querying Knowledge Base ({kb_id})...")
                
                kb_chunks = self.llm.retrieve_from_kb(kb_id, state.user_query)
                if kb_chunks:
                    # Extract table names using specific format
                    kb_tables = []
                    for chunk in kb_chunks:
                        first_line = chunk.strip().split("\n")[0]
                        if "Table:" in first_line:
                            t_name = first_line.replace("Table:", "").strip()
                            kb_tables.append(t_name)
                    
                    # Format context with explicit table list
                    temp_str = ""
                    if kb_tables:
                        temp_str += f"KB Suggested Tables: {', '.join(kb_tables)}\n\n"
                    
                    temp_str += "Relevant Domain Knowledge:\n" + "\n---\n".join(kb_chunks)
                    
                    kb_context_str += temp_str
                    self.log(state, f"Injected {len(kb_chunks)} chunks (Tables: {', '.join(kb_tables)})")
                else:
                     self.log(state, "No relevant context found in Knowledge Base")
        
        # Use in-memory inputs
        messages = self.prompt_loader.load_prompt(
            "table_selector",
            user_query=state.user_query,
            schema_path=schema_context,
            intent_path=intent_context,
            kb_context=kb_context_str 
        )
                    
        response = self.llm.get_json_completion(messages, state=state)
        
        relevant = []
        if response and "relevant_tables" in response:
            relevant = response["relevant_tables"]
            # Validate they actually exist (need to read schema file to validate)
            # For now, trust the LLM or check against schema if loaded
            # We can load schema to validate if needed
        else:
            # Fallback
            relevant = [] 

        state.relevant_tables = relevant

        # Extract intent and complexity from the same response
        state.query_intent = response.get("intent", "DATA_RETRIEVAL") if response else "DATA_RETRIEVAL"
        state.complexity_score = response.get("complexity", "MEDIUM") if response else "MEDIUM"

        self.log(state, f"PLAN_STEP: 5. Context Enriched (Tables: {', '.join(relevant)} | Intent: {state.query_intent} | Complexity: {state.complexity_score})")
        
        # Create context data structure
        context_data = {
            "relevant_tables": relevant,
            "reasoning": response.get("reasoning", "") if response else "No response"
        }
        
        state.context_reasoning = context_data["reasoning"]
        
        # Write context to results/context/ - REMOVED
        # self.file_coordinator.write_context(...)
        
        # Write filtered schema for downstream agents
        # (Generator currently expects this)
        try:
             # We need to read the full schema to filter it
             schema_info = state.schema_info
             if schema_info:
                 filtered_schema = {k: v for k, v in schema_info.items() if k in relevant}
                 # We can overwrite the main schema file or keep it separately?
                 # Actually, Generator reads the main schema file. 
                 # Maybe we should create a specific filtered schema file?
                 # The plan says Generator reads schema from file.
                 # Let's keep writing filtered schema to results/schema for now as "filtered" version?
                 # Wait, Generator reads InstancePaths.schema(). 
                 # If we overwrite it, downstream agents lose full schema.
                 # But Generator needs filtered schema.
                 # Let's create a NEW path for filtered schema? Or just put it in context?
                 # Ah, context file has relevant_tables. Generator should read context and filter schema itself?
                 # Generator logic: 
                 # schema_from_file = self.file_coordinator.read_schema(state.instance_id)
                 # if schema_from_file: ...
                 
                 # PROPOSAL: Let Generator use context to filter schema.
                 # ContextEnrichmentAgent just identifies tables.
                 pass
        except Exception as e:
            self.log(state, f"Error processing schema: {e}", level="ERROR")
        
        return state
