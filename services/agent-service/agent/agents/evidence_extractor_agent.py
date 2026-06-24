import json
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.blackboard.run_blackboard import get_blackboard
from agent.blackboard.facts_engine import FactsEngine
from agent.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever

class EvidenceExtractorOutput(BaseModel):
    extracted_policies: list[str] = Field(description="List of specific policy facts extracted from documents")
    missing_documents: list[str] = Field(description="Documents that were requested but not found")

class EvidenceExtractorAgent:
    """
    Executes BEFORE or PARALLEL to SQL execution.
    Extracts unstructured business rules and policies from the document store
    using the requirements written to the Blackboard.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.retriever = HierarchicalRetriever()
        self.assembler = PromptAssembler(stage="EVIDENCE_EXTRACTOR")
        self.agent_name = "EVIDENCE_EXTRACTOR"

    def extract(self, user_query: str) -> EvidenceExtractorOutput:
        logger.set_agent(self.agent_name)
        bb = get_blackboard()
        
        if not bb.required_documents:
            logger.info("No documents required. Skipping Evidence Extraction.")
            return EvidenceExtractorOutput(extracted_policies=[], missing_documents=[])

        logger.info(f"Extracting evidence for required documents: {bb.required_documents}")
        
        # Retrieve documents
        docs = self.retriever.retrieve_documents(bb.required_documents)
        doc_text = "\n".join([d['content'] for d in docs]) if docs else "No documents found."

        assembled = self.assembler.assemble(
            user_query=user_query,
            agent_type=self.agent_name,
            context=doc_text,
            intent=None
        )

        response, _ = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=assembled.user_prompt
        )

        try:
            clean = response.strip()
            if clean.startswith("```json"): clean = clean[7:]
            if clean.endswith("```"): clean = clean[:-3]
            
            data = json.loads(clean.strip())
            output = EvidenceExtractorOutput(**data)
            
            # Post facts to the blackboard
            for policy in output.extracted_policies:
                FactsEngine.confirm_fact(fact=policy, source="DOCUMENT_EVIDENCE", confidence=0.95)
                
            bb.confidence["evidence"] = max(bb.confidence["evidence"], 0.90 if output.extracted_policies else 0.0)
            
            logger.log_parsed_data("Extracted Evidence", output)
            return output
        except Exception as e:
            logger.error(f"Failed to parse EvidenceExtractor output: {e}")
            return EvidenceExtractorOutput(extracted_policies=[], missing_documents=["Parse error"])
