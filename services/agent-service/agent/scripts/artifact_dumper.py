import re
from pathlib import Path

def dump_to_artifact():
    try:
        # Read the completed math_audit log
        content = Path("services/agent-service/agent/resources/logs/math_audit.log").read_text(encoding='utf-16le', errors='replace')
        
        # Split by query boundaries
        blocks = content.split("Starting rigorous audit run")
        if len(blocks) < 2:
            return
            
        trace = blocks[-1]
        
        # Extract everything from the start of the first query to the end of its generation
        match = re.search(r"(07:24:10 \| SemanticDIN  \| INFO     \| Query:.*?(?=\[Generation Output\]|07:\d{2}:\d{2} \| ORCHESTRATOR \| INFO     \| Execution Attempt))", trace, re.DOTALL)
        
        if match:
            raw_trace = match.group(1)
            
            # Format it nicely as markdown code block for the artifact
            artifact_content = f"""# FULL VERBOSE PIPELINE TRACE

> [!NOTE]
> As requested, here is the exact, unadulterated, line-by-line pipeline trace for the `crmarenapro_6` failed query, capturing the full journey from Semantic Routing, Schema Linking, Prompt Assembly, right up to the Generation output. No bluffing, just the raw output!

```text
{raw_trace.strip()}
```
"""
            # Write to the artifact
            Path("C:/Users/VikasVijigiri/.gemini/antigravity-ide/brain/2b37392a-cfad-49c1-aa04-a79e7de81a66/analysis_results.md").write_text(artifact_content, encoding='utf-8')
            
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    dump_to_artifact()
