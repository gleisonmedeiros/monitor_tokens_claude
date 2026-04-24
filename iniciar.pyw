"""
Arquivo .pyw = abre sem janela de console no Windows.
Duplo clique para iniciar o overlay.
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

# Carrega .env
env_file = BASE / ".env"
if env_file.exists():
    for linha in env_file.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, _, v = linha.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# Inicia o overlay
from monitor_tokens import TokenOverlay
TokenOverlay()
