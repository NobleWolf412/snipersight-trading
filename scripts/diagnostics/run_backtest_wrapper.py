import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Override stdout to file
with open("final_backtest.txt", "w", encoding="utf-8") as f:
    sys.stdout = f
    sys.stderr = f
    
    import scripts.run_backtest
    sys.argv = ['run_backtest.py', '--compare', '--days', '14']
    try:
        scripts.run_backtest.main()
    except Exception as e:
        import traceback
        traceback.print_exc()
