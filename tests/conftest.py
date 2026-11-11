import sys
from pathlib import Path

# Permite "import app", "import auth", "import config" a partir da raiz do projeto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
