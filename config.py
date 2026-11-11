# ============================================================
#  CONFIGURAÇÃO — preencha antes de rodar (veja o LEIA-ME.md)
# ============================================================

import os
from pathlib import Path


def _carregar_env(arquivo: Path):
    """Lê o .env (CHAVE=valor por linha). Variável que já existe no sistema tem prioridade."""
    if not arquivo.is_file():
        return
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        os.environ.setdefault(chave.strip(), valor)


# As chaves do Telegram (e a senha do painel) ficam no arquivo .env, que NÃO vai para o GitHub.
# Copie o .env.exemplo com o nome .env e preencha (veja o README).
_carregar_env(Path(__file__).resolve().parent / ".env")

# 1) https://my.telegram.org  →  API development tools  (TG_API_ID e TG_API_HASH no .env)
# 2) Token do seu bot de alertas: @BotFather → /newbot   (TG_BOT_TOKEN no .env)
API_ID = int(os.environ.get("TG_API_ID") or 0)
API_HASH = os.environ.get("TG_API_HASH") or "cole_o_api_hash"
BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or "cole_o_token_do_bot"

# 3) Canais monitorados. Rode `python codigo\listar_canais.py` para descobrir os IDs.
#    "plataforma" é usada quando a mensagem não diz a plataforma
#    (ex.: canal da Nintendo mistura Switch e Switch 2 — ajuste se preferir).
#    "cortar_topo"/"cortar_base": quanto da foto cortar (0.15 = 15%) para tirar a faixa
#    com o logo do canal e selos de preço, sobrando só a capa do jogo.
CANAIS = [
    {"id": -1001637081487, "nome": "Ofertas Nintendo BR",    "plataforma": "Switch",
     "cortar_topo": 0.15, "cortar_base": 0.0},
    {"id": -1001695140674, "nome": "Ofertas Playstation BR", "plataforma": "PS5",
     "cortar_topo": 0.15, "cortar_base": 0.0},
    {"id": -1001124239751, "nome": "Desconto em Games",      "plataforma": None,
     "cortar_topo": 0.20, "cortar_base": 0.18},
    {"id": -1002747000473, "nome": "PromoGames",             "plataforma": None,
     "cortar_topo": 0.16, "cortar_base": 0.0},
    {"id": -1003134203042, "nome": "Promotec Games",         "plataforma": None,
     "cortar_topo": 0.0,  "cortar_base": 0.0},
    # foto com o logo "CONSUMER GAMES" em cima e a faixa do QR code embaixo
    {"id": -1002044549649, "nome": "Consumer Games",         "plataforma": None,
     "cortar_topo": 0.12, "cortar_base": 0.20},
]

# ------------------------------------------------------------
#  Regras de "preço bom" (ajuste ao seu gosto)
# ------------------------------------------------------------
DIAS_HISTORICO_INICIAL = 180   # na 1ª execução, quantos dias de mensagens antigas importar
MIN_REGISTROS = 3              # quantas ofertas anteriores precisa ter p/ comparar
DESCONTO_MEDIANA = 0.25        # avisa se estiver 25% abaixo da mediana do jogo
DESCONTO_ANUNCIADO = 50        # avisa se o "De R$X por R$Y" der 50% ou mais (mesmo sem histórico)
ALERTAR_PREVENDA = True       # pré-vendas entram no histórico, mas só alertam se for desejo

# Plataformas que você não quer acompanhar: as ofertas delas são ignoradas (não gravam,
# não alertam e não consultam o Deku Deals). Opções: "Switch 2", "Switch", "PS5", "PS4",
# "Xbox Series", "Xbox One".
PLATAFORMAS_IGNORADAS = ["Xbox Series", "Xbox One"]

# ------------------------------------------------------------
#  Saúde do monitor e backups
# ------------------------------------------------------------
# Avisa pelo bot quando um canal fica esse tempo sem mandar nada (pode ter parado, ou sua conta saiu dele).
# Para um canal específico, ponha "horas_silencio": 72 na linha dele em CANAIS.
HORAS_SILENCIO_CANAL = 48
# Avisa quando NENHUM canal manda nada por esse tempo (normal à noite: até ~13 h sem ofertas).
HORAS_SILENCIO_GERAL = 16
# Backup automático do banco 1x por dia em backups/; ficam só os mais novos (os outros são apagados).
BACKUPS_MANTER = 7

# ------------------------------------------------------------
#  Painel web
# ------------------------------------------------------------
PORTA_PAINEL = int(os.environ.get("PORTA_PAINEL") or 8787)
# "127.0.0.1" = só este computador. "0.0.0.0" = qualquer aparelho da sua rede (servidor).
HOST_PAINEL = os.environ.get("HOST_PAINEL") or "127.0.0.1"
# Senha do painel. Obrigatória se HOST_PAINEL for "0.0.0.0". Vazio = sem senha.
SENHA_PAINEL = os.environ.get("SENHA_PAINEL") or ""
