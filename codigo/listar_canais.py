"""Lista os canais e grupos da sua conta com o ID de cada um. Uso: python listar_canais.py"""
import os
from pathlib import Path

from telethon.sync import TelegramClient

from raiz import RAIZ
import config

PASTA_DADOS = Path(os.environ.get("MONITOR_DADOS") or RAIZ)
PASTA_DADOS.mkdir(parents=True, exist_ok=True)
SESSAO = str(PASTA_DADOS / "sessao_usuario")   # a mesma do monitor.py

with TelegramClient(SESSAO, config.API_ID, config.API_HASH) as cliente:
    print("\nID                     NOME")
    print("-" * 60)
    for d in cliente.iter_dialogs():
        if d.is_channel or d.is_group:
            print(f"{d.id:<22} {d.name}")
    print("\nCopie os IDs dos canais de promoção para CANAIS no config.py")
