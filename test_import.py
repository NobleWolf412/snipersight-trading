import sys
import os

# Add root to sys.path
root = os.path.abspath(os.path.join(os.getcwd()))
if root not in sys.path:
    sys.path.append(root)

try:
    from backend.shared.models.planner import TradePlan, Target
    print("SUCCESS: Imported TradePlan and Target from backend.shared.models.planner")
except ImportError as e:
    print(f"FAILURE: {e}")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"sys.path: {sys.path}")
