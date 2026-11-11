"""
Testes das correções da revisão (não usam internet nem Telegram).
Uso: python codigo/testes/testar_revisao.py
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))   # módulos de codigo/
import base64
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

PASTA_TESTE = tempfile.mkdtemp()
os.environ["MONITOR_DB"] = os.path.join(PASTA_TESTE, "teste.db")
os.environ["SENHA_PAINEL"] = "segredo"

import api  # noqa: E402
import banco  # noqa: E402
import deku  # noqa: E402
from extrator import extrair, menciona_esgotado, normalizar_nome  # noqa: E402

erros = 0


def confere(nome, obtido, esperado):
    global erros
    ok = obtido == esperado
    erros += not ok
    print(("✅" if ok else "❌"), nome, "" if ok else f"→ {obtido!r} (esperado {esperado!r})")


# ---------------------------------------------------------------- extrator
confere("preço com ponto decimal", extrair("[Mídia Física] Jogo via Loja\nDe R$ 399.90 por R$ 299.90").preco, 299.90)
confere("preço com milhar", extrair("[Mídia Física] Jogo via Loja\nDe R$1.299,90 por R$999").preco, 999.0)
confere("'esgotado' marca", menciona_esgotado("Cupom: X Esgotado 😢"), True)
confere("'antes que esgote' não marca", menciona_esgotado("Corre antes que esgote!"), False)

# ---------------------------------------------------------------- banco
db = banco.conectar(os.environ["MONITOR_DB"])
agora = datetime.now(timezone.utc)


def of(nome, preco, plat="PS5"):
    return extrair(f"[Mídia Física] {nome} via Amazon\nPor R${preco}", plat)


sf5 = banco.obter_ou_criar_jogo(db, of("Street Fighter 5", 99))
sf6 = banco.obter_ou_criar_jogo(db, of("Street Fighter 6", 149))
confere("continuações não se misturam (SF5 ≠ SF6)", sf5 != sf6, True)
confere("mesmo jogo com nome diferente se junta",
        banco.obter_ou_criar_jogo(db, of("Street Fighter 6 - PS5", 140)), sf6)
ff7 = banco.obter_ou_criar_jogo(db, of("Final Fantasy VII Rebirth", 200))
ff16 = banco.obter_ou_criar_jogo(db, of("Final Fantasy XVI", 150))
confere("algarismos romanos diferenciam (VII ≠ XVI)", ff7 != ff16, True)

desejo = {"chave": normalizar_nome("Street Fighter 5"), "plataforma": None}
confere("desejo SF5 não dispara com SF6", banco.desejo_combina(desejo, normalizar_nome("Street Fighter 6"), "PS5"), False)
desejo = {"chave": normalizar_nome("zelda"), "plataforma": None}
confere("desejo 'zelda' pega qualquer Zelda", banco.desejo_combina(desejo, normalizar_nome("Zelda Tears of the Kingdom"), "Switch"), True)

banco.marcar_lida(db, -100, 50)
banco.marcar_lida(db, -100, 40)                     # edição de mensagem antiga não volta o cursor
confere("cursor de leitura do canal", banco.ultimo_msg_id(db, -100), 50)

# ---------------------------------------------------------------- deku: falha não apaga preço
deku.salvar(db, sf6, "https://www.dekudeals.com/items/street-fighter-6",
            {"preco_atual": 199.0, "menor_preco": 120.0, "msrp": 249.0}, None)
deku.salvar(db, sf6, None, None, "Deku Deals indisponível agora", temporario=True)
d = deku.dados_digitais(db, sf6)
confere("falha mantém o preço anterior", (d["preco_atual"], d["menor_preco"], d["temporario"]), (199.0, 120.0, 1))
db.execute("UPDATE digital SET atualizado=? WHERE jogo_id=?", ((agora - timedelta(hours=7)).isoformat(), sf6))
db.commit()
confere("site fora: tenta de novo depois de 6h", sf6 in deku.pendentes(db, 50), True)

antigo = (agora - timedelta(days=45)).isoformat()
v = deku.veredito(150.0, 150.0, {"preco_atual": 199.0, "menor_preco": 120.0}, antigo)
confere("veredito avisa oferta física antiga", "45 dias" in v["texto"], True)


def falso_bloqueado(caminho, params):
    raise urllib.error.HTTPError("x", 403, "Forbidden", {}, None)


try:
    deku.consultar("Street Fighter 6", "street fighter 6", "PS5", baixar=falso_bloqueado)
    confere("403 vira 'site indisponível'", False, True)
except deku.SiteIndisponivel:
    confere("403 vira 'site indisponível'", True, True)

# ---------------------------------------------------------------- painel: senha e proteção
api.SENHA = "segredo"
srv = api.criar_servidor(0, "127.0.0.1")
porta = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{porta}"
AUTH = "Basic " + base64.b64encode(b"eu:segredo").decode()


def chamar(metodo, caminho, corpo=None, cab=None):
    req = urllib.request.Request(BASE + caminho, method=metodo, headers=cab or {},
                                 data=json.dumps(corpo).encode() if corpo is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


confere("sem senha: 401", chamar("GET", "/api/resumo"), 401)
confere("com senha: 200", chamar("GET", "/api/resumo", cab={"Authorization": AUTH}), 200)
confere("senha errada: 401", chamar("GET", "/api/resumo",
        cab={"Authorization": "Basic " + base64.b64encode(b"eu:x").decode()}), 401)
confere("gravação sem JSON (site de fora): 403", chamar("POST", "/api/desejos", {"texto": "x", "preco_alvo": 10},
        cab={"Authorization": AUTH, "Content-Type": "text/plain"}), 403)
confere("gravação de outra origem: 403", chamar("POST", "/api/desejos", {"texto": "x", "preco_alvo": 10},
        cab={"Authorization": AUTH, "Content-Type": "application/json", "Origin": "https://malicioso.com"}), 403)
confere("gravação do painel: 201", chamar("POST", "/api/desejos", {"texto": "Astro Bot", "preco_alvo": 150},
        cab={"Authorization": AUTH, "Content-Type": "application/json", "Origin": BASE}), 201)
confere("parâmetro inválido: 400 (não derruba)", chamar("GET", "/api/ofertas?limite=abc", cab={"Authorization": AUTH}), 400)
confere("caminho fora da pasta: não vaza", chamar("GET", "/capas/../config.py", cab={"Authorization": AUTH}), 404)
confere("caminho fora da pasta via /api/capas: não vaza", chamar("GET", "/api/capas/../config.py", cab={"Authorization": AUTH}), 404)
srv.shutdown()

print("\nTudo certo." if not erros else f"\n{erros} teste(s) falharam.")
sys.exit(1 if erros else 0)
