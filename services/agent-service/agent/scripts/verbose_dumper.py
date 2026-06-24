import re
from pathlib import Path

def extract_verbose_trace(log_path: str):
    try:
        content = Path(log_path).read_text(encoding='utf-16le', errors='replace')
        
        # We want the exact text from the PromptAssembler down to the Generation output.
        # Let's just find the first instance of a full execution trace
        blocks = content.split("Starting rigorous audit run")
        if len(blocks) < 2:
            return "Audit run has not started properly yet."
            
        trace = blocks[-1]
        
        # Find the first full query trace
        query_match = re.search(r"Query: '(.*?)'", trace)
        if not query_match:
            return "No query found in trace."
            
        query = query_match.group(1)
        
        # Find telemetry block
        tel_match = re.search(r"(\[PromptTelemetry\].*?)(?=\n\d{2}:\d{2}:\d{2}|$)", trace, re.DOTALL)
        telemetry = tel_match.group(1) if tel_match else "Telemetry not found"
        
        # Find generation block
        gen_match = re.search(r"(\[Generation Output\].*?)(?=\n\d{2}:\d{2}:\d{2} \| [A-Z_]+ \||$)", trace, re.DOTALL)
        generation = gen_match.group(1) if gen_match else "Generation not found"
        
        return f"""
# RAW VERBOSE TRACE: {query[:50]}...

## TELEMETRY & COMPRESSION:
{telemetry}

## GENERATION PAYLOAD & PROMPT OUTPUT:
{generation}
"""
    except Exception as e:
        return f"Error extracting: {e}"

if __name__ == "__main__":
    res = extract_verbose_trace("services/agent-service/agent/resources/logs/optimized_audit.log")
    with open("services/agent-service/agent/resources/logs/verbose_dump.txt", "w", encoding="utf-8") as f:
        f.write(res)
