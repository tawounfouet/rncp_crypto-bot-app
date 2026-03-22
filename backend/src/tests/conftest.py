"""
Configuration pytest pour les tests du backend.
Ajoute le répertoire backend au PYTHONPATH.
"""

import sys
from pathlib import Path

# Ajouter le répertoire backend au PYTHONPATH
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
