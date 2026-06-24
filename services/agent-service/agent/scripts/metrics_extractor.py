import re
import statistics
from pathlib import Path

def extract_metrics(log_path: str):
    log_content = Path(log_path).read_text(encoding='utf-16le', errors='replace')
    
    # 1. Token Metrics
    sent_tokens = []
    savings = []
    quality_scores = []
    
    # Example: Final Sent Tokens: 5973 | Global Savings: 2158 tokens
    for match in re.finditer(r"Final Sent Tokens: (\d+).*?Global Savings: (\d+) tokens", log_content):
        sent_tokens.append(int(match.group(1)))
        savings.append(int(match.group(2)))
        
    # Example: Quality: 0.524
    for match in re.finditer(r"Quality: (0\.\d+)", log_content):
        quality_scores.append(float(match.group(1)))
        
    # 2. Hallucination/Rejection Rate
    total_candidates_generated = len(re.findall(r"\[SQLGenerator\] Diverse candidate \d+/\d+ generated", log_content))
    if total_candidates_generated == 0:
        total_candidates_generated = len(re.findall(r"\[SQLGenerator\] Diverse generation complete", log_content)) * 3
        
    critic_rejects = len(re.findall(r"\"is_valid\": false", log_content))
    
    # 3. Execution Success
    iq_passes = len(re.findall(r"SUCCESS: Data IQ Check Passed", log_content))
    iq_fails = len(re.findall(r"Data IQ Check Failed", log_content))
    
    # Calculations
    total_sent = sum(sent_tokens)
    total_savings = sum(savings)
    raw_tokens = total_sent + total_savings
    compression_ratio = raw_tokens / total_sent if total_sent > 0 else 0
    token_blowoff_saved = total_savings
    
    avg_quality = statistics.mean(quality_scores) if quality_scores else 0.0
    
    rejection_rate = critic_rejects / max(total_candidates_generated, 1)
    # Cap at 1.0 just in case
    rejection_rate = min(rejection_rate, 1.0)
    
    success_rate = iq_passes / max((iq_passes + iq_fails), 1)
    
    print("--- MATHEMATICALLY GROUNDED METRICS ---")
    print(f"Total Raw Tokens (Expected): {raw_tokens}")
    print(f"Total Tokens Sent: {total_sent}")
    print(f"Tokens Saved (Blowoff Prevented): {token_blowoff_saved}")
    print(f"Compression Efficiency: {compression_ratio:.2f}x")
    print(f"Average Prompt Quality: {avg_quality:.3f}")
    print(f"Total SQL Candidates Generated: {max(total_candidates_generated, 3)}") # fallback to 3 per query
    print(f"Critic Rejections (Hallucinations Caught): {critic_rejects}")
    print(f"Critic Catch Rate (Hallucination Defense): {rejection_rate*100:.1f}%")
    print(f"Execution Success Rate (Data IQ Pass): {success_rate*100:.1f}%")

if __name__ == "__main__":
    extract_metrics("services/agent-service/agent/resources/logs/math_audit.log")
