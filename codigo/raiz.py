"""
Pasta do projeto: config.py, banco, capas, sessões do Telegram e o painel (dist/) ficam lá,
um nível acima desta pasta de código. Importar este módulo deixa o `import config` funcionando.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.append(str(RAIZ))       # no fim: os módulos de codigo/ continuam tendo prioridade
