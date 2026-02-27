import os
import re

log_path = 'logs/confluence_breakdown.log'

if not os.path.exists(log_path):
    print("Log not found")
else:
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # split by the delimiter to get each symbol's breakdown
    blocks = content.split("================================================================================")
    
    # look at last 20 blocks
    for block in blocks[-30:]:
        block = block.strip()
        if not block: continue
        
        lines = block.split('\n')
        header = lines[0]
        score_line = next((l for l in lines if l.startswith("Final Score:")), "")
        
        print(header)
        if score_line:
            print(f"  {score_line}")
