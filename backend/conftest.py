import sys
from pathlib import Path

# The CI helpers (including the pytest_honest plugin) live in ../scripts.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

pytest_plugins = ["pytest_honest"]
