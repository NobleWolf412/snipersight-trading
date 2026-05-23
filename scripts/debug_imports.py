import sys
import os

print(f"Current working directory: {os.getcwd()}")
print(f"System path: {sys.path}")

try:
    import backend.shared.models.smc
    print("SUCCESS: Successfully imported backend.shared.models.smc")
except ImportError as e:
    print(f"FAILURE: Could not import backend.shared.models.smc: {e}")
    
    # Try to see if adding CWD helps
    sys.path.append(os.getcwd())
    try:
        import backend.shared.models.smc
        print("SUCCESS (after fix): Successfully imported backend.shared.models.smc after adding CWD to path")
    except ImportError as e2:
        print(f"FAILURE (after fix): Still could not import: {e2}")
