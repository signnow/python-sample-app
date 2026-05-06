import sys
from pathlib import Path

# Make sure the project root is importable (so `app` and `samples` resolve).
sys.path.insert(0, str(Path(__file__).parent.parent))
