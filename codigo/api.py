"""
API local + servidor do painel (React compilado em ./dist).
Roda sozinha com `python api.py` (só o painel, sem ler o Telegram)
ou junto com o monitor.py, que a inicia automaticamente.
Endereço: http://localhost:8787 (ou o HOST_PAINEL/PORTA_PAINEL do config.py)

Segurança quando aberto na rede (HOST_PAINEL = "0.0.0.0"):
  - SENHA_PAINEL no config.py liga a senha (o navegador pede uma vez)
  - gravações só aceitam JSON vindo do próprio painel (bloqueia sites de fora)
"""
import base64
import hmac
import json
import logging
import os
import mimetypes
import re
import statistics
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from rapidfuzz import fuzz, process

from raiz import RAIZ
import banco
import capas
import deku
from extrator import detectar_plataforma, normalizar_nome
from semelhanca import EDICAO, numeros, palavras

try:
    import config as _config
except ImportError:                  # api.py --demo sem config.py
    _config = None

log = logging.getLogger("painel")
PASTA = RAIZ                          # pasta do projeto (o código fica em codigo/)
# Onde ficam os dados (banco, capas, sessões do Telegram). No Docker/servidor aponte para um volume.
PASTA_DADOS = Path(os.environ.get("MONITOR_DADOS") or PASTA).resolve()
PASTA_DADOS.mkdir(parents=True, exist_ok=True)
SENHA = (os.environ.get("SENHA_PAINEL") or getattr(_config, "SENHA_PAINEL", "") or "").strip()
TAMANHO_MAX_CORPO = 64 * 1024
TAMANHO_MAX_IMAGEM = 12 * 1024 * 1024     # capa enviada pelo painel
PAINEL = PASTA / "dist"
DB_PATH = os.environ.get("MONITOR_DB") or str(PASTA_DADOS / "precos.db")
PASTA_CAPAS = PASTA_DADOS / "capas"
DEMO = False
MIN_REGISTROS = 3
_IGNORADAS = set(getattr(_config, "PLATAFORMAS_IGNORADAS", []) or [])
SEM_PLATAFORMA = "sem"     # valor do filtro "Sem plataforma"
TIPOS = ("jogo", "bundle", "colecionador", "acessorio")
PLATAFORMAS_VALIDAS = [p for p in ("Switch 2", "Switch", "PS5", "PS4", "Xbox Series", "Xbox One")
                       if p not in _IGNORADAS]


def url_capa(arquivo):
    """Endereço da capa, com a data do arquivo para o navegador não usar cópia velha."""
    if not arquivo:
        return None
    caminho = PASTA_CAPAS / arquivo
    if not caminho.is_file():
        return None
    return f"api/capas/{arquivo}?v={int(caminho.stat().st_mtime)}"   # relativo à página; passa pelo /api do host


# ================================================================ consultas
def _ofertas_por_jogo(db):
    grupos = defaultdict(list)
    for o in db.execute("SELECT * FROM ofertas ORDER BY data"):
        grupos[o["jogo_id"]].append(dict(o))
    return grupos


def _estatisticas(ofertas: list[dict]) -> dict:
    precos = [o["preco"] for o in ofertas]
    menor = min(ofertas, key=lambda o: (o["preco"], o["data"]))
    ultima = ofertas[-1]
    mediana = statistics.median(precos)
    return {
        "ofertas": len(ofertas),
        "menor_preco": menor["preco"],
        "menor_data": menor["data"],
        "menor_loja": menor["loja"],
        "mediana": mediana,
        "ultimo_preco": ultima["preco"],
        "ultima_data": ultima["data"],
        "ultima_loja": ultima["loja"],
        "ultimo_link": ultima["link"],
        "no_menor_preco": ultima["preco"] <= menor["preco"],
        "vs_mediana": round(100 * (ultima["preco"] / mediana - 1)) if mediana else None,
    }


def _digital(dig, est):
    """Resumo do digital (Deku Deals) + veredito contra o físico."""
    if not dig:
        return {"digital": None, "veredito": None}
    d = {k: dig.get(k) for k in ("url", "manual", "preco_atual", "menor_preco", "msrp", "atualizado", "erro", "temporario")}
    # a página do Deku Deals tem outro console (ex.: jogo cadastrado como Switch, página só de Switch 2)
    d["outras"] = [p for p in (dig.get("outras") or "").split(",") if p in PLATAFORMAS_VALIDAS]
    v = deku.veredito(est.get("ultimo_preco"), est.get("menor_preco"), dig, est.get("ultima_data")) if est else None
    return {"digital": d, "veredito": v}


def _escondido(j, marca: str, buscando: bool = False) -> bool:
    """Jogos marcados ("já tenho"/"não me interessa") saem das listas; o filtro da marca mostra só eles.
    Na busca aparecem todos (com o selo), para você achar o que marcou."""
    if marca:
        return j["marca"] != marca
    return bool(j["marca"]) and not buscando


def listar_jogos(db, q: str = "", plataforma: str = "", ordem: str = "recentes", tipo: str = "", marca: str = ""):
    grupos = _ofertas_por_jogo(db)
    digitais = deku.todos_digitais(db)
    chave_q = normalizar_nome(q) if q else ""
    itens = []
    for j in db.execute("SELECT * FROM jogos"):
        ofs = grupos.get(j["id"])
        if not ofs:
            continue
        if plataforma and j["plataforma"] != (None if plataforma == SEM_PLATAFORMA else plataforma):
            continue
        if tipo and (j["tipo"] or "jogo") != tipo:
            continue
        if _escondido(j, marca, bool(q)):
            continue
        nota = 100
        if chave_q:
            if all(p in j["chave"] for p in chave_q.split()):
                nota = 100                                 # todas as palavras aparecem
            else:
                nota = fuzz.token_set_ratio(chave_q, j["chave"])   # tolera erro de digitação
                if nota < 80:
                    continue
        est = _estatisticas(ofs)
        itens.append({"id": j["id"], "nome": j["nome"], "plataforma": j["plataforma"], "tipo": j["tipo"] or "jogo",
                      "marca": j["marca"], "capa": url_capa(j["capa"]), "relevancia": nota, **est,
                      **_digital(digitais.get(j["id"]), est)})

    if chave_q:
        itens.sort(key=lambda x: (-x["relevancia"], x["nome"]))
    elif ordem == "desconto":
        itens.sort(key=lambda x: (x["vs_mediana"] if x["ofertas"] >= MIN_REGISTROS else 999))
    elif ordem == "nome":
        itens.sort(key=lambda x: x["nome"].lower())
    elif ordem == "preco":
        itens.sort(key=lambda x: x["ultimo_preco"])
    else:
        itens.sort(key=lambda x: x["ultima_data"], reverse=True)
    return itens


def detalhe_jogo(db, jogo_id: int):
    j = db.execute("SELECT * FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    if not j:
        return None
    ofs = [dict(o) for o in db.execute(
        "SELECT * FROM ofertas WHERE jogo_id=? ORDER BY data", (jogo_id,))]
    est = _estatisticas(ofs) if ofs else {}
    return {"id": j["id"], "nome": j["nome"], "plataforma": j["plataforma"], "tipo": j["tipo"] or "jogo",
            "marca": j["marca"],
            "capa": url_capa(j["capa"]), "capa_original": capas.tem_original(PASTA_CAPAS, j["id"]),
            **est, "historico": ofs,
            **_digital(deku.dados_digitais(db, jogo_id), est)}


def ofertas_recentes(db, limite: int = 60, plataforma: str = "", tipo: str = "", marca: str = ""):
    grupos = _ofertas_por_jogo(db)
    jogos = {j["id"]: j for j in db.execute("SELECT * FROM jogos")}
    recentes = db.execute("SELECT * FROM ofertas ORDER BY data DESC LIMIT ?",
                          (limite * 4,)).fetchall()
    saida = []
    for o in recentes:
        j = jogos[o["jogo_id"]]
        if plataforma and j["plataforma"] != (None if plataforma == SEM_PLATAFORMA else plataforma):
            continue
        if tipo and (j["tipo"] or "jogo") != tipo:
            continue
        if _escondido(j, marca):
            continue
        antes = [x["preco"] for x in grupos[o["jogo_id"]] if x["data"] < o["data"]]
        menor_ate_entao = len(antes) >= MIN_REGISTROS and o["preco"] < min(antes)
        vs = (round(100 * (o["preco"] / statistics.median(antes) - 1))
              if len(antes) >= MIN_REGISTROS else None)
        saida.append({**dict(o), "nome": j["nome"], "plataforma": j["plataforma"], "tipo": j["tipo"] or "jogo",
                      "marca": j["marca"], "capa": url_capa(j["capa"]), "menor_ate_entao": menor_ate_entao, "vs_mediana": vs})
        if len(saida) >= limite:
            break
    return saida


def listar_desejos(db):
    grupos = _ofertas_por_jogo(db)
    jogos = db.execute("SELECT * FROM jogos").fetchall()
    trinta_dias = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    saida = []
    for d in banco.listar_desejos(db):
        achados = [j for j in jogos if banco.desejo_combina(d, j["chave"], j["plataforma"])]
        ofs = sorted((o | {"nome": j["nome"], "plataforma": j["plataforma"]}
                      for j in achados for o in grupos.get(j["id"], [])),
                     key=lambda o: o["data"])
        recentes = [o for o in ofs if o["data"] >= trinta_dias and o["ativo"]]
        melhor_recente = min(recentes, key=lambda o: o["preco"]) if recentes else None
        saida.append({
            **dict(d),
            "jogos": [{"id": j["id"], "nome": j["nome"], "plataforma": j["plataforma"]}
                      for j in achados],
            "capa": next((url_capa(j["capa"]) for j in achados if url_capa(j["capa"])), None),
            "menor_preco": min((o["preco"] for o in ofs), default=None),
            "melhor_recente": melhor_recente,
            "atingiu": bool(melhor_recente and melhor_recente["preco"] <= d["preco_alvo"]),
        })
    return saida


def resumo(db):
    r = db.execute("""SELECT (SELECT COUNT(*) FROM jogos) jogos,
                             (SELECT COUNT(*) FROM ofertas) ofertas,
                             (SELECT MAX(data) FROM ofertas) ultima,
                             (SELECT COUNT(*) FROM desejos) desejos""").fetchone()
    plataformas = [p[0] for p in db.execute(
        "SELECT plataforma, COUNT(*) n FROM jogos WHERE plataforma IS NOT NULL "
        "GROUP BY plataforma ORDER BY n DESC")]
    tipos = {row[0] or "jogo": row[1] for row in db.execute(
        "SELECT tipo, COUNT(*) FROM jogos j WHERE EXISTS (SELECT 1 FROM ofertas o WHERE o.jogo_id = j.id) GROUP BY tipo")}
    sem_plataforma = db.execute(
        "SELECT COUNT(*) FROM jogos j WHERE plataforma IS NULL "
        "AND EXISTS (SELECT 1 FROM ofertas o WHERE o.jogo_id = j.id)").fetchone()[0]
    marcas = {row[0]: row[1] for row in db.execute(
        "SELECT marca, COUNT(*) FROM jogos j WHERE marca IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM ofertas o WHERE o.jogo_id = j.id) GROUP BY marca")}
    fila = revisao(db)
    return {**dict(r), "plataformas": plataformas, "plataformas_validas": PLATAFORMAS_VALIDAS, "tipos": tipos,
            "sem_plataforma": sem_plataforma, "marcas": marcas,
            "revisao": sum(len(v) for v in fila.values()), "saude": saude_resumida(db)}


# ================================================================ fila de revisão
PARECIDO_MIN = 85            # nota (0-100) para dois nomes do mesmo console entrarem como "possível repetido"
_cache_repetidos = {"chave": None, "pares": []}


def _resumo_jogo(j, ofs):
    ultima = ofs[-1] if ofs else {}
    return {"id": j["id"], "nome": j["nome"], "plataforma": j["plataforma"], "tipo": j["tipo"] or "jogo",
            "capa": url_capa(j["capa"]), "ofertas": len(ofs), "ultimo_preco": ultima.get("preco"),
            "ultima_data": ultima.get("data"), "ultima_loja": ultima.get("loja")}


def _pares_parecidos(jogos, medianas=None):
    """Pares de jogos do mesmo console com nomes muito parecidos (e os mesmos números no nome)."""
    por_plat = defaultdict(list)
    for j in jogos:
        por_plat[j["plataforma"]].append(j)
    pares = []
    for lista in por_plat.values():
        nomes = [" ".join(palavras(j["nome"])) for j in lista]
        for i, nome in enumerate(nomes):
            if not nome:
                continue
            for _, nota, k in process.extract(nome, nomes, scorer=fuzz.token_sort_ratio,
                                              score_cutoff=PARECIDO_MIN, limit=None):
                if k <= i:
                    continue
                a, b = lista[i], lista[k]
                if (a["tipo"] == "acessorio") != (b["tipo"] == "acessorio"):
                    continue
                if numeros(palavras(a["nome"])) != numeros(palavras(b["nome"])):
                    continue                      # "Dragon Quest II" x "Dragon Quest III": jogos diferentes
                pares.append((round(nota), min(a["id"], b["id"]), max(a["id"], b["id"])))
        pares += _contidos(lista, medianas or {}) + _acessorios_iguais(lista)
    vistos, unicos = set(), []
    for p in sorted(pares, reverse=True):
        if p[1:] not in vistos:
            vistos.add(p[1:])
            unicos.append(p)
    return unicos


def _contidos(lista, medianas):
    """
    Um nome contém o outro com até 2 palavras a mais e o preço normal dos dois é parecido
    ("Silksong" / "Hollow Knight: Silksong", "Metal Gear Solid V:" / "Metal Gear Solid V: The Phantom Pain").
    Palavra de edição a mais (Deluxe, Steelbook, Edition...) não entra: aí costuma ser outro produto.
    """
    pares = []
    jogos = [(j, frozenset(palavras(j["nome"]))) for j in lista if j["tipo"] != "acessorio" and medianas.get(j["id"])]
    for i, (a, pa) in enumerate(jogos):
        for b, pb in jogos[i + 1:]:
            menor, maior = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
            extras = maior - menor
            if not (len(menor) >= 2 and menor < maior and len(extras) <= 2 and not extras & EDICAO
                    and numeros(tuple(pa)) == numeros(tuple(pb))):
                continue
            razao = medianas[a["id"]] / medianas[b["id"]]
            if 0.8 <= razao <= 1.25:
                pares.append((80, min(a["id"], b["id"]), max(a["id"], b["id"])))
    return pares


# palavras que não distinguem um acessório do outro (o que distingue é a cor/edição)
_GENERICAS_ACESSORIO = {
    "controle", "controles", "sem", "fio", "sony", "dualsense", "dualsenses", "edicao", "edicoes", "limitada",
    "limited", "edition", "especial", "colecao", "ps5", "ps", "5", "2", "console", "consoles", "para", "slim", "pro",
    "joy", "con", "cons", "nintendo", "switch", "s", "marvel", "c", "oficial", "original", "tampa", "tampas", "capa"}
_PECA = [("tampa", {"tampa", "tampas", "capa", "faceplate"}), ("controle", {"controle", "controles", "dualsense", "joy"})]


def _acessorios_iguais(lista):
    """Mesma cor/edição e mesmo tipo de peça ("Controle DualSense Sem Fio - Cobalt Blue" / "Dualsense Cobalt Blue")."""
    grupos = defaultdict(list)
    for j in lista:
        if j["tipo"] != "acessorio":
            continue
        pals = set(palavras(j["nome"]))
        sig = frozenset(pals - _GENERICAS_ACESSORIO)
        peca = next((nome for nome, chaves in _PECA if pals & chaves), "outro")
        if sig:
            grupos[(peca, sig)].append(j)
    pares = []
    for g in grupos.values():
        for i, a in enumerate(g):
            for b in g[i + 1:]:
                pares.append((90, min(a["id"], b["id"]), max(a["id"], b["id"])))
    return pares


def revisao(db) -> dict:
    """O que precisa da sua atenção: sem plataforma, possíveis repetidos e sem capa."""
    dispensados = {r[0] for r in db.execute("SELECT chave FROM revisao_ok")}
    grupos = _ofertas_por_jogo(db)
    jogos = [j for j in db.execute("SELECT * FROM jogos") if j["id"] in grupos and j["marca"] != "ignorar"]
    por_id = {j["id"]: j for j in jogos}

    chave = (len(jogos), max(por_id, default=0), db.execute("SELECT MAX(id) FROM ofertas").fetchone()[0],
             tuple(sorted((j["id"], j["nome"], j["plataforma"], j["tipo"]) for j in jogos)).__hash__())
    if _cache_repetidos["chave"] != chave:             # recalcula só quando algum jogo mudou
        medianas = {j["id"]: statistics.median(o["preco"] for o in grupos[j["id"]]) for j in jogos}
        _cache_repetidos.update(chave=chave, pares=_pares_parecidos(jogos, medianas))

    recentes = lambda j: grupos[j["id"]][-1]["data"]
    sem_plataforma = sorted((j for j in jogos if not j["plataforma"] and f"sem_plataforma:{j['id']}" not in dispensados),
                            key=recentes, reverse=True)
    sem_capa = sorted((j for j in jogos if not url_capa(j["capa"]) and f"sem_capa:{j['id']}" not in dispensados),
                      key=recentes, reverse=True)
    repetidos = [{"chave": f"repetido:{a}:{b}", "nota": nota,
                  "jogos": [_resumo_jogo(por_id[a], grupos[a]), _resumo_jogo(por_id[b], grupos[b])]}
                 for nota, a, b in _cache_repetidos["pares"]
                 if a in por_id and b in por_id and f"repetido:{a}:{b}" not in dispensados]
    # jogo comum que o Deku Deals não achou (ou achou só em outro console); erro "temporário" (site fora) não entra
    tem_digital = db.execute("SELECT 1 FROM sqlite_master WHERE name='digital'").fetchone()
    falhas = {r["jogo_id"]: r for r in db.execute(
        "SELECT jogo_id, url, erro FROM digital WHERE erro IS NOT NULL AND IFNULL(temporario, 0) = 0")} if tem_digital else {}
    sem_digital = sorted((j for j in jogos if j["id"] in falhas and (j["tipo"] or "jogo") == "jogo"
                          and f"sem_digital:{j['id']}" not in dispensados), key=recentes, reverse=True)
    return {
        "repetidos": repetidos,
        "sem_plataforma": [_resumo_jogo(j, grupos[j["id"]]) | {"chave": f"sem_plataforma:{j['id']}"} for j in sem_plataforma],
        "sem_digital": [_resumo_jogo(j, grupos[j["id"]]) | {"chave": f"sem_digital:{j['id']}", "erro": falhas[j["id"]]["erro"],
                                                            "url": falhas[j["id"]]["url"]} for j in sem_digital],
        "sem_capa": [_resumo_jogo(j, grupos[j["id"]]) | {"chave": f"sem_capa:{j['id']}"} for j in sem_capa],
    }


def dispensar_revisao(db, chave: str):
    if not re.fullmatch(r"(repetido:\d+:\d+|sem_plataforma:\d+|sem_capa:\d+|sem_digital:\d+)", chave or ""):
        raise ValueError("item de revisão desconhecido")
    db.execute("INSERT OR REPLACE INTO revisao_ok (chave, data) VALUES (?, ?)", (chave, banco.agora()))
    db.commit()


def juntar(db, fica: int, sai: int) -> int:
    """Possível repetido confirmado: as ofertas de `sai` vão para `fica` (o nome de `sai` vira apelido)."""
    if fica == sai:
        raise ValueError("escolha dois jogos diferentes")
    _jogo(db, fica)
    _jogo(db, sai)
    banco.juntar_jogos(db, sai, fica)
    _sumir_se_vazio(db, sai, fica)                 # leva a capa se o que fica não tiver
    capas.apagar_capas(PASTA_CAPAS, sai)
    return fica


# ================================================================ saúde do monitor
BATIDA_MAX_MIN = 15          # sem sinal do monitor há mais que isso = parado
_CANAIS_CFG = list(getattr(_config, "CANAIS", []) or [])
HORAS_SILENCIO_CANAL = getattr(_config, "HORAS_SILENCIO_CANAL", 48)
HORAS_SILENCIO_GERAL = getattr(_config, "HORAS_SILENCIO_GERAL", 16)
PASTA_BACKUPS = PASTA_DADOS / "backups"


def _horas_desde(iso):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d).total_seconds() / 3600


def _tamanho_pasta(pasta: Path, padrao: str = "*"):
    arquivos = [f for f in pasta.glob(padrao) if f.is_file()] if pasta.is_dir() else []
    return len(arquivos), sum(f.stat().st_size for f in arquivos)


def saude_resumida(db) -> dict:
    """Só o semáforo do topo: monitor ligado e algum canal parado."""
    _, batida = banco.ler_estado(db, "batida")
    h = _horas_desde(batida)
    ativo = h is not None and h * 60 <= BATIDA_MAX_MIN
    parados = sum(1 for c in _canais(db) if c["parado"])
    return {"monitor": ativo, "canais_parados": parados, "ok": ativo and not parados}


def _canais(db):
    lidos = {r["canal_id"]: r for r in db.execute("SELECT * FROM canais_lidos")}
    saida = []
    for c in _CANAIS_CFG:
        o = db.execute("SELECT MAX(data) ultima, SUM(data >= ?) dia FROM ofertas WHERE canal_id=?",
                       ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(), c["id"])).fetchone()
        ultima_msg = (lidos.get(c["id"]) or {"data": None})["data"] or o["ultima"]
        h = _horas_desde(ultima_msg)
        limite = c.get("horas_silencio") or HORAS_SILENCIO_CANAL
        saida.append({"id": c["id"], "nome": c.get("nome") or str(c["id"]), "ultima_mensagem": ultima_msg,
                      "ultima_oferta": o["ultima"], "ofertas_24h": o["dia"] or 0, "limite_horas": limite,
                      "parado": h is not None and h > limite})
    return saida


def saude(db) -> dict:
    inicio_v, inicio = banco.ler_estado(db, "inicio")
    conectado, batida = banco.ler_estado(db, "telegram")
    _, batida = banco.ler_estado(db, "batida")
    h = _horas_desde(batida)
    ativo = h is not None and h * 60 <= BATIDA_MAX_MIN
    tem_digital = db.execute("SELECT 1 FROM sqlite_master WHERE name='digital'").fetchone()
    dig = dict(db.execute("""SELECT COUNT(*) total, MAX(atualizado) ultimo, SUM(erro IS NOT NULL) erros,
                                 SUM(preco_atual IS NOT NULL) com_preco FROM digital""").fetchone()) if tem_digital else {}
    n_capas, b_capas = _tamanho_pasta(PASTA_CAPAS, "*.jpg")
    backups = sorted((f for f in PASTA_BACKUPS.glob("*.db") if f.is_file()) if PASTA_BACKUPS.is_dir() else [],
                     key=lambda f: f.stat().st_mtime, reverse=True)
    banco_bytes = sum(Path(DB_PATH + suf).stat().st_size for suf in ("", "-wal") if Path(DB_PATH + suf).is_file())
    _, ultimo_backup = banco.ler_estado(db, "backup")
    canais = _canais(db)
    ultimas = [c["ultima_mensagem"] for c in canais if c["ultima_mensagem"]]
    h_geral = _horas_desde(max(ultimas)) if ultimas else None
    return {
        "monitor": {"ativo": ativo, "ultima_batida": batida, "ligado_desde": inicio,
                    "telegram_conectado": conectado == "1" if conectado is not None else None,
                    "limite_min": BATIDA_MAX_MIN},
        "canais": canais,
        "silencio_geral": {"horas": h_geral, "limite_horas": HORAS_SILENCIO_GERAL,
                           "parado": h_geral is not None and h_geral > HORAS_SILENCIO_GERAL},
        "digital": dig,
        "erros": [dict(r) for r in db.execute(
            "SELECT data, nivel, texto FROM registro_erros ORDER BY id DESC LIMIT 30")],
        "espaco": {
            "banco": banco_bytes,
            "capas": {"arquivos": n_capas, "bytes": b_capas},
            "backups": [{"nome": f.name, "bytes": f.stat().st_size,
                         "data": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()} for f in backups],
            "backups_manter": getattr(_config, "BACKUPS_MANTER", 7),
            "ultimo_backup": ultimo_backup,
        },
    }


# ================================================================ correções feitas no painel
def _plataforma(valor):
    if valor in (None, ""):
        return None
    if valor not in PLATAFORMAS_VALIDAS:
        raise ValueError(f"plataforma desconhecida: {valor}")
    return valor


def _jogo(db, jogo_id):
    j = db.execute("SELECT * FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    if not j:
        raise LookupError("Jogo não encontrado")
    return j


def _sumir_se_vazio(db, jogo_id, herdeiro=None):
    """Jogo que ficou sem ofertas some; a capa vai para o herdeiro, se ele não tiver uma."""
    if db.execute("SELECT 1 FROM ofertas WHERE jogo_id=?", (jogo_id,)).fetchone():
        return False
    if herdeiro and capas.passar_capa(PASTA_CAPAS, jogo_id, herdeiro):
        banco.definir_capa(db, herdeiro, f"{herdeiro}.jpg")
    if herdeiro:                                    # você levou tudo para o herdeiro: o nome vira apelido dele
        j = db.execute("SELECT nome, plataforma FROM jogos WHERE id=?", (jogo_id,)).fetchone()
        if j:
            banco.lembrar_apelido(db, j["nome"], j["plataforma"], herdeiro)
        db.execute("UPDATE apelidos SET jogo_id=? WHERE jogo_id=?", (herdeiro, jogo_id))
    capas.apagar_capas(PASTA_CAPAS, jogo_id)
    banco.apagar_jogo(db, jogo_id)
    return True


def editar_jogo(db, jogo_id: int, dados: dict) -> int:
    """Muda nome e/ou plataforma. Se já existe o mesmo jogo nessa plataforma, junta os dois.
    Retorna o id do jogo que ficou."""
    j = _jogo(db, jogo_id)
    nome = str(dados.get("nome") or j["nome"]).strip()[:200]
    plataforma = _plataforma(dados.get("plataforma", j["plataforma"]))
    tipo = dados.get("tipo") or j["tipo"] or "jogo"
    if tipo not in TIPOS:
        raise ValueError(f"tipo desconhecido: {tipo}")
    chave = normalizar_nome(nome) or j["chave"]
    if tipo != (j["tipo"] or "jogo"):
        db.execute("UPDATE jogos SET tipo=? WHERE id=?", (tipo, jogo_id))
        if tipo != "jogo":
            db.execute("DELETE FROM digital WHERE jogo_id=?", (jogo_id,))   # acessório/console: sem digital
        db.commit()
    if (nome, plataforma) == (j["nome"], j["plataforma"]):
        return jogo_id
    # a página do Deku Deals continua sendo a do jogo: guarda o link para consultar no console certo
    antigo = deku.dados_digitais(db, jogo_id) or {}
    destino = banco.achar_mesmo_jogo(db, nome, plataforma, excluir=jogo_id)
    if destino:
        banco.juntar_jogos(db, jogo_id, destino)
        _sumir_se_vazio(db, jogo_id, destino)       # leva a capa se o outro não tiver
        capas.apagar_capas(PASTA_CAPAS, jogo_id)
        db.execute("UPDATE jogos SET nome=?, tipo=? WHERE id=?", (nome, tipo, destino))   # fica o que você estava vendo
        db.commit()
        jogo_id = destino
    else:
        if plataforma != j["plataforma"]:
            db.execute("DELETE FROM digital WHERE jogo_id=?", (jogo_id,))   # preço digital era da outra plataforma
        banco.lembrar_apelido(db, j["nome"], j["plataforma"], jogo_id)   # o nome antigo continua achando este jogo
        db.execute("UPDATE jogos SET nome=?, chave=?, plataforma=? WHERE id=?", (nome, chave, plataforma, jogo_id))
        db.execute("UPDATE ofertas SET manual=1 WHERE jogo_id=?", (jogo_id,))
        db.commit()
    novo = deku.dados_digitais(db, jogo_id) or {}
    if (tipo == "jogo" and plataforma != j["plataforma"] and antigo.get("url")
            and novo.get("preco_atual") is None and not DEMO):
        try:
            deku.atualizar_jogo(db, jogo_id, antigo["url"])
        except Exception as e:                      # sem internet/site fora: o atualizador tenta depois
            log.warning(f"Não consegui consultar o digital de {nome} agora: {e}")
    return jogo_id


def mover_ofertas(db, ids: list, dados: dict) -> dict:
    """
    Leva uma ou várias ofertas (do mesmo jogo) para outro jogo:
    {"jogo_id": n} ou {"plataforma": "PS4"} (mesmo jogo, outro console).
    """
    ids = list(dict.fromkeys(int(i) for i in ids))[:1000]
    if not ids:
        raise ValueError("nenhuma oferta escolhida")
    marcas = ",".join("?" * len(ids))
    linhas = db.execute(f"SELECT id, jogo_id FROM ofertas WHERE id IN ({marcas})", ids).fetchall()
    if len(linhas) != len(ids):
        raise LookupError("Oferta não encontrada (talvez já tenha sido movida ou excluída)")
    if len({o["jogo_id"] for o in linhas}) > 1:
        raise ValueError("as ofertas escolhidas são de jogos diferentes")
    origem = _jogo(db, linhas[0]["jogo_id"])
    if dados.get("jogo_id"):
        destino = _jogo(db, int(dados["jogo_id"]))["id"]
    else:
        nome = str(dados.get("nome") or origem["nome"]).strip()[:200]
        plataforma = _plataforma(dados.get("plataforma", origem["plataforma"]))
        chave = normalizar_nome(nome) or origem["chave"]
        destino = (banco.achar_mesmo_jogo(db, nome, plataforma, excluir=origem["id"])
                   or banco.criar_jogo(db, nome, chave, plataforma, origem["tipo"] or "jogo"))
    if destino == origem["id"]:
        raise ValueError("as ofertas já estão nesse jogo")
    db.execute(f"UPDATE ofertas SET jogo_id=?, manual=1 WHERE id IN ({marcas})", (destino, *ids))
    db.commit()
    if not _sumir_se_vazio(db, origem["id"], destino):
        # jogo novo (ex.: a versão de PS4) começa com a mesma capa; dá para trocar depois
        if capas.passar_capa(PASTA_CAPAS, origem["id"], destino, copiar=True):
            banco.definir_capa(db, destino, f"{destino}.jpg")
        return {"origem": origem["id"], "destino": destino, "movidas": len(ids)}
    return {"origem": None, "destino": destino, "movidas": len(ids)}


def mover_oferta(db, oferta_id: int, dados: dict) -> dict:
    return mover_ofertas(db, [oferta_id], dados)


def alterar_capa(db, jogo_id: int, dados: dict):
    _jogo(db, jogo_id)
    if dados.get("restaurar"):
        arquivo = capas.restaurar_original(PASTA_CAPAS, jogo_id)
    elif dados.get("recorte"):
        c = dados["recorte"]
        arquivo = capas.recortar_atual(PASTA_CAPAS, jogo_id, float(c["x"]), float(c["y"]), float(c["w"]), float(c["h"]))
    elif dados.get("imagem"):
        texto = str(dados["imagem"])
        try:
            bruto = base64.b64decode(texto.split(",", 1)[-1], validate=False)
        except Exception:
            raise ValueError("imagem inválida")
        arquivo = capas.trocar_imagem(PASTA_CAPAS, jogo_id, bruto)
    else:
        raise ValueError("diga o que fazer com a capa")
    banco.definir_capa(db, jogo_id, arquivo)


# ================================================================ HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "MonitorJogos"
    sys_version = ""

    def log_message(self, *a):  # silencioso
        pass

    # ---------------------------------------------------------------- proteção
    def _autorizado(self) -> bool:
        if not SENHA:
            return True
        cab = self.headers.get("Authorization", "")
        if cab.startswith("Basic "):
            try:
                _, _, senha = base64.b64decode(cab[6:]).decode("utf-8").partition(":")
            except Exception:
                return False
            return hmac.compare_digest(senha.encode(), SENHA.encode())
        return False

    def _pedir_senha(self):
        corpo = "Senha necessária.".encode()
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Monitor de jogos", charset="UTF-8"')
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _gravacao_permitida(self) -> bool:
        """Só aceita gravações do próprio painel: JSON (exige preflight) e mesma origem."""
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return False
        origem = self.headers.get("Origin")
        if origem and urlparse(origem).netloc != self.headers.get("Host"):
            return False
        return True

    def _seguro(self, metodo, gravacao=False):
        try:
            if not self._autorizado():
                return self._pedir_senha()
            if gravacao and not self._gravacao_permitida():
                return self._json({"erro": "Requisição recusada."}, 403)
            return metodo()
        except (BrokenPipeError, ConnectionResetError):
            pass                                  # o navegador fechou a conexão
        except ValueError as e:
            self._json({"erro": f"Dados inválidos: {e}"}, 400)
        except Exception:
            log.exception(f"Erro no painel em {self.command} {self.path}")
            try:
                self._json({"erro": "Erro interno. Veja o log do monitor."}, 500)
            except Exception:
                pass

    def do_GET(self):
        self._seguro(self._get)

    def do_POST(self):
        self._seguro(self._post, gravacao=True)

    def do_DELETE(self):
        self._seguro(self._delete, gravacao=True)

    def _json(self, dados, status=200):
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self, limite: int = TAMANHO_MAX_CORPO) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n > limite:
            raise ValueError("corpo grande demais")
        dados = json.loads(self.rfile.read(n) or b"{}")
        if not isinstance(dados, dict):
            raise ValueError("esperava um objeto JSON")
        return dados

    def _get(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path.startswith("/api/capas/"):
            return self._arquivo(url.path[len("/api"):])
        if url.path.startswith("/api/"):
            db = banco.conectar(DB_PATH)
            try:
                if url.path == "/api/resumo":
                    return self._json(resumo(db))
                if url.path == "/api/jogos":
                    return self._json(listar_jogos(db, q.get("q", ""), q.get("plataforma", ""),
                                                   q.get("ordem", "recentes"), q.get("tipo", ""), q.get("marca", "")))
                m = re.fullmatch(r"/api/jogos/(\d+)", url.path)
                if m:
                    d = detalhe_jogo(db, int(m.group(1)))
                    return self._json(d) if d else self._json({"erro": "Jogo não encontrado"}, 404)
                if url.path == "/api/ofertas":
                    limite = min(max(int(q.get("limite") or 60), 1), 500)
                    return self._json(ofertas_recentes(db, limite, q.get("plataforma", ""), q.get("tipo", ""),
                                                       q.get("marca", "")))
                if url.path == "/api/revisao":
                    return self._json(revisao(db))
                if url.path == "/api/saude":
                    return self._json(saude(db))
                if url.path == "/api/desejos":
                    return self._json(listar_desejos(db))
                return self._json({"erro": "Rota não existe"}, 404)
            finally:
                db.close()
        self._arquivo(url.path)

    def _post(self):
        if self.path == "/api/ofertas/mover":          # várias de uma vez: {"ids": [...], "jogo_id" | "plataforma"}
            dados = self._corpo()
            db = banco.conectar(DB_PATH)
            try:
                return self._json(mover_ofertas(db, dados.get("ids") or [], dados))
            except LookupError as e:
                return self._json({"erro": str(e)}, 404)
            finally:
                db.close()
        if self.path == "/api/revisao/ok":             # "São diferentes" / "Está certo assim"
            dados = self._corpo()
            db = banco.conectar(DB_PATH)
            try:
                dispensar_revisao(db, str(dados.get("chave") or ""))
                return self._json(revisao(db))
            finally:
                db.close()
        rota = re.fullmatch(r"/api/jogos/(\d+)/(marcar|juntar)", self.path)
        if rota:
            n, acao = int(rota.group(1)), rota.group(2)
            dados = self._corpo()
            db = banco.conectar(DB_PATH)
            try:
                deku.preparar(db)
                if acao == "marcar":                  # {"marca": "tenho" | "ignorar" | null}
                    _jogo(db, n)
                    banco.marcar_jogo(db, n, dados.get("marca") or None)
                    return self._json(detalhe_jogo(db, n))
                return self._json(detalhe_jogo(db, juntar(db, n, int(dados.get("com") or 0))))
            except LookupError as e:
                return self._json({"erro": str(e)}, 404)
            finally:
                db.close()
        rota = re.fullmatch(r"/api/(jogos|ofertas)/(\d+)/(editar|mover|capa)", self.path)
        if rota:
            tipo, n, acao = rota.group(1), int(rota.group(2)), rota.group(3)
            dados = self._corpo(TAMANHO_MAX_IMAGEM if acao == "capa" else TAMANHO_MAX_CORPO)
            db = banco.conectar(DB_PATH)
            try:
                deku.preparar(db)
                if tipo == "jogos" and acao == "editar":
                    return self._json(detalhe_jogo(db, editar_jogo(db, n, dados)))
                if tipo == "jogos" and acao == "capa":
                    alterar_capa(db, n, dados)
                    return self._json(detalhe_jogo(db, n))
                if tipo == "ofertas" and acao == "mover":
                    return self._json(mover_oferta(db, n, dados))
                return self._json({"erro": "Rota não existe"}, 404)
            except LookupError as e:
                return self._json({"erro": str(e)}, 404)
            finally:
                db.close()
        m = re.fullmatch(r"/api/jogos/(\d+)/digital", self.path)
        if m:                                   # atualizar agora / vincular link do Deku Deals
            url = (self._corpo().get("url") or "").strip() or None
            if url and not deku.slug_de_url(url):
                return self._json({"erro": "Cole um link de página de jogo do Deku Deals, "
                                           "ex.: https://www.dekudeals.com/items/astro-bot"}, 400)
            db = banco.conectar(DB_PATH)
            try:
                if DEMO:
                    return self._json({"erro": "No modo de demonstração o Deku Deals não é consultado."}, 400)
                deku.atualizar_jogo(db, int(m.group(1)), url)
                return self._json(detalhe_jogo(db, int(m.group(1))))
            except deku.SiteIndisponivel as e:
                return self._json({"erro": f"O Deku Deals não respondeu agora ({e}). Tente de novo em alguns minutos."}, 503)
            except ValueError as e:
                return self._json({"erro": str(e)}, 404)
            finally:
                db.close()
        if self.path != "/api/desejos":
            return self._json({"erro": "Rota não existe"}, 404)
        dados = self._corpo()
        texto = str(dados.get("texto", "")).strip()
        try:
            alvo = float(str(dados.get("preco_alvo", "")).replace(",", "."))
        except ValueError:
            alvo = 0
        if not texto or alvo <= 0:
            return self._json({"erro": "Informe o nome do jogo e um preço maior que zero."}, 400)
        plataforma = dados.get("plataforma") or detectar_plataforma(texto)
        db = banco.conectar(DB_PATH)
        try:
            banco.adicionar_desejo(db, texto, normalizar_nome(texto), plataforma, alvo)
            return self._json(listar_desejos(db), 201)
        finally:
            db.close()

    def _delete(self):
        j = re.fullmatch(r"/api/jogos/(\d+)", self.path)
        if j:
            # só com confirmação explícita no corpo: um DELETE solto (ou repetido) não apaga nada
            if self._corpo().get("confirmar") is not True:
                return self._json({"erro": "Confirme a exclusão."}, 400)
            db = banco.conectar(DB_PATH)
            try:
                deku.preparar(db)
                jogo = db.execute("SELECT nome, plataforma FROM jogos WHERE id=?", (int(j.group(1)),)).fetchone()
                if not jogo:
                    return self._json({"erro": "Jogo não encontrado"}, 404)
                n = banco.excluir_jogo(db, int(j.group(1)))
                capas.apagar_capas(PASTA_CAPAS, int(j.group(1)))
                log.info(f"🗑 Excluído no painel: {jogo['nome']} [{jogo['plataforma']}] e {n} ofertas")
                return self._json({"excluido": int(j.group(1)), "ofertas": n})
            finally:
                db.close()
        m = re.fullmatch(r"/api/desejos/(\d+)", self.path)
        if not m:
            return self._json({"erro": "Rota não existe"}, 404)
        db = banco.conectar(DB_PATH)
        try:
            banco.remover_desejo(db, int(m.group(1)))
            return self._json(listar_desejos(db))
        finally:
            db.close()

    def _arquivo(self, caminho: str):
        if caminho.startswith("/capas/"):
            alvo = (PASTA_CAPAS / caminho[len("/capas/"):]).resolve()
            if alvo.parent == PASTA_CAPAS.resolve() and alvo.is_file():
                corpo = alvo.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Cache-Control", "max-age=604800")
                self.end_headers()
                return self.wfile.write(corpo)
            self.send_response(404)
            self.end_headers()
            return
        alvo = (PAINEL / caminho.lstrip("/")).resolve()
        if not alvo.is_relative_to(PAINEL.resolve()) or not alvo.is_file():
            alvo = PAINEL / "index.html"          # SPA: tudo cai no index
        if not alvo.is_file():
            corpo = "Painel não encontrado. Rode o build (veja o LEIA-ME).".encode()
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            return self.wfile.write(corpo)
        tipo = mimetypes.guess_type(alvo.name)[0] or "application/octet-stream"
        if alvo.suffix == ".js":
            tipo = "text/javascript"
        corpo = alvo.read_bytes()
        if alvo.name == "index.html":            # o build usa caminhos relativos
            corpo = corpo.replace(b"<head>", b'<head><base href="/">', 1)
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        # arquivos do build têm hash no nome: podem ficar em cache; o index.html não
        self.send_header("Cache-Control", "public, max-age=31536000, immutable"
                         if "/assets/" in alvo.as_posix() else "no-cache")
        self.end_headers()
        self.wfile.write(corpo)


def criar_servidor(porta: int, host: str) -> ThreadingHTTPServer:
    banco.conectar(DB_PATH).close()   # garante que as tabelas existem
    try:
        servidor = ThreadingHTTPServer((host, porta), Handler)
    except OSError as e:
        raise SystemExit(f"Não consegui abrir o painel em {host}:{porta} ({e}). "
                         "A porta está em uso? Troque PORTA_PAINEL no config.py.")
    servidor.daemon_threads = True
    if host not in ("127.0.0.1", "localhost", "::1") and not SENHA:
        print("⚠️  O painel está aberto na rede SEM senha. Defina SENHA_PAINEL no config.py.")
    endereco = "localhost" if host in ("127.0.0.1", "0.0.0.0", "::") else host
    print(f"🌐 Painel em http://{endereco}:{porta}" + ("  (aberto na rede)" if host in ("0.0.0.0", "::") else ""))
    return servidor


def iniciar_em_segundo_plano(porta: int = 8787, host: str = "127.0.0.1"):
    servidor = criar_servidor(porta, host)
    threading.Thread(target=servidor.serve_forever, daemon=True, name="painel").start()
    return servidor


if __name__ == "__main__":
    import sys
    if "--demo" in sys.argv:                       # python api.py --demo  → usa demo.db
        DB_PATH = str(PASTA / "demo.db")
        PASTA_CAPAS = PASTA / "capas_demo"
        DEMO = True
    logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)
    portas = [a for a in sys.argv[1:] if a.isdigit()]
    porta = int(portas[0]) if portas else getattr(_config, "PORTA_PAINEL", 8787)
    host = os.environ.get("HOST_PAINEL") or getattr(_config, "HOST_PAINEL", "127.0.0.1")
    try:
        criar_servidor(porta, host).serve_forever()
    except KeyboardInterrupt:
        pass
