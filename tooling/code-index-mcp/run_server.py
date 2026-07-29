"""Installation-free MCP stdio server bootstrap for genesis-code-index."""
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SRC = _THIS_DIR / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from genesis_code_index.server import main_stdio

if __name__ == "__main__":
    main_stdio()
