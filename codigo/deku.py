"""
Preço DIGITAL do jogo no Deku Deals (região Brasil, em R$).

Para cada jogo do banco busca, no máximo uma vez por dia:
  - preço digital atual (eShop / PlayStation Store / Microsoft Store)
  - menor preço digital da história ("All time low")
  - preço cheio (MSRP)

Como acha a página do jogo, nesta ordem:
  1. link que você colou no painel (sempre vence)
  2. busca do próprio Deku Deals
  3. o nome do jogo transformado em endereço (ex.: astro-bot)
E confere se a página tem a versão digital da MESMA plataforma.

Uso educado: uma página por vez, alguns segundos entre elas, cache de 24h.
"""
import re
import sqlite3
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Optional

from rapidfuzz import fuzz

from extrator import PLATAFORMAS, classificar, normalizar_nome

BASE = "https://www.dekudeals.com"
PAIS = "br"
AGENTE = "Mozilla/5.0 (monitor pessoal de precos; consulta 1x por dia por jogo)"
INTERVALO_ENTRE_PAGINAS = 4      # segundos
VALIDADE_HORAS = 24              # refaz a consulta depois disso
ESPERA_APOS_FALHA_HORAS = 72     # não insiste em jogo que não foi achado
ESPERA_SITE_FORA_HORAS = 6       # site fora do ar / bloqueou: tenta de novo mais cedo
VALIDADE_INATIVO_DIAS = 7        # jogo sem oferta física há 30 dias: digital é atualizado 1x por semana
POR_RODADA = 15                  # jogos por rodada do atualizador
RODADA_MIN = 10                  # minutos entre rodadas
PAUSA_CARGA_INICIAL_S = 20       # enquanto houver jogo nunca consultado, rodadas seguidas (só esta pausa)


class SiteIndisponivel(Exception):
    """Deku Deals fora do ar, lento ou bloqueando (403/429/5xx). Não é 'jogo não achado'."""

# Nossa plataforma -> rótulo que o Deku Deals usa nas linhas "<rótulo> Digital"
ROTULO = {
    "Switch 2": "Switch 2",
    "Switch": "Switch",
    "PS5": "PS5",
    "PS4": "PS4",
    "Xbox Series": "Xbox Series X|S",
    "Xbox One": "Xbox One",
}
_ROTULOS_RE = r"Switch 2|Switch|PS5|PS4|Xbox Series X\|S|Xbox Series|Xbox X\|S|Xbox One|Steam"
# a mesma versão digital pode valer para mais de um console: "PS5 / PS4 Digital R$74,85"
_GRUPO_RE = rf"(?:{_ROTULOS_RE})(?:\s*/\s*(?:{_ROTULOS_RE}))*"


def _rotulos(grupo: str) -> list[str]:
    """'PS5 / PS4' -> ['PS5', 'PS4']; as variações de Xbox Series viram 'Xbox Series X|S'."""
    return ["Xbox Series X|S" if r.strip().startswith(("Xbox Series", "Xbox X|S")) else r.strip()
            for r in grupo.split("/")]
_PRECO = r"R\$\s?(\d{1,3}(?:\.\d{3})*,\d{2})"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS digital (
    jogo_id INTEGER PRIMARY KEY,
    url TEXT,
    manual INTEGER DEFAULT 0,
    preco_atual REAL,
    menor_preco REAL,
    msrp REAL,
    atualizado TEXT,
    erro TEXT,
    temporario INTEGER DEFAULT 0
);
"""


# ================================================================ HTML -> texto
class _Texto(HTMLParser):
    BLOCOS = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "h5", "h6",
              "table", "ul", "ol", "section", "header", "footer"}

    def __init__(self):
        super().__init__()
        self.partes, self.links, self._pular = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._pular += 1
        if tag in self.BLOCOS:
            self.partes.append("\n")
        if tag in ("td", "th", "a", "span"):
            self.partes.append(" ")
        if tag == "a":
            href = dict(attrs).get("href") or ""
            self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._pular = max(0, self._pular - 1)
        if tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self._pular:
            self.partes.append(data)


def html_para_texto(html: str) -> tuple[str, list[str]]:
    p = _Texto()
    p.feed(html)
    texto = "".join(p.partes).replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\s*\n\s*", "\n", texto)
    return texto, p.links


def _f(v: str) -> float:
    return float(v.replace(".", "").replace(",", "."))


# ================================================================ leitura da página
def ler_pagina(html: str, plataforma: Optional[str]) -> Optional[dict]:
    """
    Extrai {preco_atual, menor_preco, msrp} da versão digital da plataforma.
    Retorna None se a página não tiver essa versão.
    """
    texto, _ = html_para_texto(html)
    rotulo = ROTULO.get(plataforma or "", None)

    # ---- preços atuais: "<Loja> <Rótulo> Digital R$49,99-80%"
    ini = texto.find("Current prices")
    fim_candidatos = [i for i in (texto.find("Price history", ini), texto.find("All time low", ini)) if i > ini]
    trecho = texto[ini:min(fim_candidatos)] if ini >= 0 and fim_candidatos else texto
    atuais: dict[str, list[float]] = {}
    for m in re.finditer(rf"({_GRUPO_RE})\s*Digital\s*{_PRECO}", trecho):
        for nome in _rotulos(m.group(1)):
            atuais.setdefault(nome, []).append(_f(m.group(2)))

    if rotulo:
        if rotulo not in atuais:
            return None
        preco_atual = min(atuais[rotulo])
    elif len(atuais) == 1:
        rotulo, precos = next(iter(atuais.items()))
        preco_atual = min(precos)
    else:
        return None

    # ---- menor preço histórico
    menor = None
    i = texto.find("All time low")
    if i >= 0:
        bloco = texto[i + len("All time low"): i + 700]
        corte = re.search(r"Time range|Price history|Details|dekudeals\.com", bloco)
        if corte:
            bloco = bloco[:corte.start()]
        rotulados = {nome: _f(v) for g, v in re.findall(rf"({_GRUPO_RE}|Digital)\s*:?\s*{_PRECO}", bloco)
                     for nome in _rotulos(g)}
        if rotulo in rotulados:
            menor = rotulados[rotulo]
        elif "Digital" in rotulados:
            menor = rotulados["Digital"]
        elif not rotulados and len(atuais) == 1:
            m = re.search(_PRECO, bloco)
            menor = _f(m.group(1)) if m else None

    msrp = None
    m = re.search(rf"MSRP:?\s*{_PRECO}", texto)
    if m:
        msrp = _f(m.group(1))

    if menor is None or menor > preco_atual:
        menor = preco_atual if menor is None else min(menor, preco_atual)
    return {"preco_atual": preco_atual, "menor_preco": menor, "msrp": msrp}


def plataformas_na_pagina(html: str) -> list[str]:
    """Consoles (nos nossos nomes) que têm preço digital na página."""
    texto, _ = html_para_texto(html)
    ini = texto.find("Current prices")
    fim_candidatos = [i for i in (texto.find("Price history", ini), texto.find("All time low", ini)) if i > ini]
    trecho = texto[ini:min(fim_candidatos)] if ini >= 0 and fim_candidatos else texto
    nossos = {v: k for k, v in ROTULO.items()}
    achadas = []
    for m in re.finditer(rf"({_GRUPO_RE})\s*Digital\s*{_PRECO}", trecho):
        for r in _rotulos(m.group(1)):
            if r in nossos and nossos[r] not in achadas:
                achadas.append(nossos[r])
    return achadas


def ler_busca(html: str) -> list[tuple[str, str]]:
    """Resultados da busca: [(slug, título)]."""
    _, links = html_para_texto(html)
    vistos, saida = set(), []
    for href in links:
        m = re.match(r"(?:https://www\.dekudeals\.com)?/items/([a-z0-9-]+)", href or "")
        if m and m.group(1) not in vistos:
            vistos.add(m.group(1))
            saida.append((m.group(1), m.group(1).replace("-", " ")))
    return saida


# "NS2", "(nacional)", "Edição de colecionador de ..." não existem no Deku Deals e zeram a busca
_RUIDO_BUSCA = re.compile(
    r"\b(ns ?[12]|nacional|importad[oa]|lacrado|m[ií]dia f[ií]sica|pr[ée]-?venda|"
    r"edi[cç][aã]o( de)?( (colecionador|deluxe|especial|limitada|definitiva|completa|standard|"
    r"padr[aã]o|ouro|gold|premium|lan[cç]amento))?( de)?|ed\.)(?=\W|$)", re.I)
# edições que o Deku Deals às vezes não tem: 2ª tentativa de busca sem elas
_EDICAO = re.compile(r"\b(deluxe|legendary|anniversary|collector'?s|complete|definitive|gold|ultimate|"
                     r"special|limited|standard|premium|launch|day one|edition)\b", re.I)
# resultados que são complemento, não o jogo (a não ser que o nome do jogo também diga isso)
_COMPLEMENTO = {"dlc", "pack", "upgrade", "pass", "amiibo", "outfit", "costume", "soundtrack",
                "expansion", "bundle", "skin", "skins", "character", "season"}
_SW2_EDITION = "nintendo switch 2 edition"


def termos_busca(nome: str) -> list[str]:
    """Textos para a busca do Deku Deals, do mais fiel ao mais curto."""
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", nome)
    for _, padrao in PLATAFORMAS:
        s = re.sub(padrao, " ", s, flags=re.I)
    s = _RUIDO_BUSCA.sub(" ", s)
    s = re.sub(r"[^\w&'’:.\- ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -:")
    curto = re.sub(r"\s+", " ", _EDICAO.sub(" ", s)).strip(" -:")
    return [x for x in dict.fromkeys([s, curto]) if x]


def escolher(termo: str, plataforma: Optional[str], resultados: list[tuple[str, str]]) -> list[str]:
    """Ordena os resultados da busca: o jogo em si antes de DLCs e edições parecidas."""
    chave = normalizar_nome(termo)
    palavras = set(chave.split())
    notas = []
    for slug, titulo in resultados:
        if (set(titulo.split()) & _COMPLEMENTO) - palavras:
            continue                                   # DLC/pacote: o preço não é o do jogo
        eh_sw2 = _SW2_EDITION in titulo
        base = titulo.replace(_SW2_EDITION, " ") if eh_sw2 else titulo
        nota = fuzz.token_set_ratio(chave, base)
        if nota < 80:
            continue
        # desempate: título mais parecido no todo (sem palavras sobrando) e, no Switch 2,
        # a "Nintendo Switch 2 Edition" quando existir
        sobra_edicao = {m.lower() for m in _EDICAO.findall(base)} - palavras   # "deluxe" que não pedimos
        notas.append((nota, not sobra_edicao, eh_sw2 == (plataforma == "Switch 2"),
                      fuzz.token_sort_ratio(chave, normalizar_nome(base)), slug))
    notas.sort(reverse=True)
    return [n[-1] for n in notas]


def slugify(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def slug_de_url(url: str) -> Optional[str]:
    m = re.match(r"https?://(?:www\.)?dekudeals\.com/items/([a-z0-9-]+)", (url or "").strip())
    return m.group(1) if m else None


# ================================================================ rede
def _baixar(caminho: str, params: dict) -> str:
    url = f"{BASE}{caminho}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def pagina_do_item(slug: str) -> str:
    return _baixar(f"/items/{slug}", {"country": PAIS, "platform": "all"})


def consultar(nome: str, chave: str, plataforma: Optional[str], url_manual: Optional[str] = None,
              baixar=None, url_conhecida: Optional[str] = None,
              info: Optional[dict] = None) -> tuple[Optional[str], Optional[dict], Optional[str]]:
    """
    Acha a página e lê os preços. Retorna (url, dados, erro).
    `url_conhecida`: página achada numa consulta anterior; vai direto nela (1 acesso em vez de 3-4).
    `baixar(caminho, params)` pode ser trocado em testes.
    `info`, se passado, recebe {"outras": [...]}: consoles que a página achada tem, quando não tem o do jogo.
    """
    info = info if info is not None else {}
    baixar = baixar or _baixar
    pausa = (lambda: time.sleep(INTERVALO_ENTRE_PAGINAS)) if baixar is _baixar else (lambda: None)

    def tentar(slug):
        try:
            html = baixar(f"/items/{slug}", {"country": PAIS, "platform": "all"})
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None                      # esse endereço não existe: tenta o próximo
            raise SiteIndisponivel(f"o site respondeu {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SiteIndisponivel(str(getattr(e, "reason", e))) from e
        dados = ler_pagina(html, plataforma)
        if not dados and "outras" not in info:
            outras = [p for p in plataformas_na_pagina(html) if p != plataforma]
            if outras:
                info["outras"], info["url"] = outras, f"{BASE}/items/{slug}"
        return dados

    if url_manual:
        slug = slug_de_url(url_manual)
        if not slug:
            return url_manual, None, "Link inválido: use um endereço dekudeals.com/items/..."
        dados = tentar(slug)                     # SiteIndisponivel sobe para quem chamou
        if not dados:
            outras = info.get("outras")
            return url_manual, None, (f"A página só tem preço digital para {' e '.join(outras)}, não para "
                                      f"{plataforma or 'este console'}. O jogo é mesmo de {plataforma or 'outro console'}?"
                                      if outras else
                                      f"A página não tem preço digital para {plataforma or 'essa plataforma'} no Brasil")
        return f"{BASE}/items/{slug}", dados, None

    if classificar(nome) != "jogo":
        return None, None, "Console ou acessório: não tem versão digital."

    slug_antigo = slug_de_url(url_conhecida or "")
    if slug_antigo:
        dados = tentar(slug_antigo)
        pausa()
        if dados:
            return f"{BASE}/items/{slug_antigo}", dados, None

    candidatos = []
    termos = termos_busca(nome)
    for termo in termos:
        try:
            busca = baixar("/search", {"q": termo, "country": PAIS})
            pausa()
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) or e.code >= 500:
                raise SiteIndisponivel(f"o site respondeu {e.code}") from e
            continue
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise SiteIndisponivel(str(getattr(e, "reason", e))) from e
        candidatos = escolher(termo, plataforma, ler_busca(busca))[:3]
        if candidatos:
            break
    for s in (slugify(termos[0] if termos else nome), slugify(chave)):
        if s and s not in candidatos:
            candidatos.append(s)

    for slug in candidatos[:4]:
        dados = tentar(slug)
        pausa()
        if dados:
            return f"{BASE}/items/{slug}", dados, None
    if info.get("outras"):
        return info["url"], None, (f"Achei a página, mas ela só tem preço digital para {' e '.join(info['outras'])}, "
                                   f"não para {plataforma or 'este console'}. O jogo é mesmo de {plataforma or 'outro console'}?")
    return None, None, "Não achei este jogo no Deku Deals. Cole o link da página dele no painel."


# ================================================================ banco
def preparar(db):
    db.executescript(ESQUEMA)
    colunas = {c[1] for c in db.execute("PRAGMA table_info(digital)")}
    if "temporario" not in colunas:
        db.execute("ALTER TABLE digital ADD COLUMN temporario INTEGER DEFAULT 0")
        db.commit()
    if "outras" not in colunas:            # consoles que a página tem quando não tem o do jogo ("Switch 2")
        db.execute("ALTER TABLE digital ADD COLUMN outras TEXT")
        db.commit()


def dados_digitais(db, jogo_id: int) -> Optional[dict]:
    preparar(db)
    r = db.execute("SELECT * FROM digital WHERE jogo_id=?", (jogo_id,)).fetchone()
    return dict(r) if r else None


def todos_digitais(db) -> dict:
    preparar(db)
    return {r["jogo_id"]: dict(r) for r in db.execute("SELECT * FROM digital")}


def salvar(db, jogo_id: int, url, dados, erro, manual: bool = False, temporario: bool = False,
           outras: Optional[list] = None):
    """
    Grava o resultado. Se a consulta falhou, MANTÉM os preços que já sabíamos
    (só marca o erro), para uma queda do site não apagar o histórico.
    """
    preparar(db)
    agora = datetime.now(timezone.utc).isoformat()
    antigo = dados_digitais(db, jogo_id) or {}
    if dados:
        menores = [x for x in (dados["menor_preco"], antigo.get("menor_preco")) if x is not None]
        # se o link mudou, o histórico antigo era de outra página: não mistura
        if antigo.get("url") and url and antigo["url"] != url:
            menores = [dados["menor_preco"]]
        valores = (dados["preco_atual"], min(menores), dados["msrp"])
    else:
        valores = (antigo.get("preco_atual"), antigo.get("menor_preco"), antigo.get("msrp"))
    db.execute(
        """INSERT INTO digital (jogo_id, url, manual, preco_atual, menor_preco, msrp, atualizado, erro, temporario, outras)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(jogo_id) DO UPDATE SET url=excluded.url, manual=excluded.manual,
             preco_atual=excluded.preco_atual, menor_preco=excluded.menor_preco, msrp=excluded.msrp,
             atualizado=excluded.atualizado, erro=excluded.erro, temporario=excluded.temporario,
             outras=excluded.outras""",
        (jogo_id, url or antigo.get("url"), int(manual or antigo.get("manual") or 0),
         *valores, agora, erro, int(temporario), ",".join(outras or []) or None))
    db.commit()


def atualizar_jogo(db, jogo_id: int, url_manual: Optional[str] = None) -> dict:
    """Consulta e grava. Levanta SiteIndisponivel se o Deku Deals não respondeu."""
    j = db.execute("SELECT * FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    if not j:
        raise ValueError("Jogo não encontrado")
    antigo = dados_digitais(db, jogo_id) or {}
    manual = url_manual or (antigo.get("url") if antigo.get("manual") else None)
    try:
        conhecida = antigo.get("url") if not manual and antigo.get("preco_atual") is not None else None
        info = {}
        url, dados, erro = consultar(j["nome"], j["chave"], j["plataforma"], manual, url_conhecida=conhecida, info=info)
    except SiteIndisponivel as e:
        salvar(db, jogo_id, manual, None, f"Deku Deals indisponível agora ({e}). Tentarei de novo mais tarde.",
               manual=bool(manual), temporario=True)
        raise
    salvar(db, jogo_id, url, dados, erro, manual=bool(manual), outras=None if dados else info.get("outras"))
    return dados_digitais(db, jogo_id)


def pendentes(db, limite: int = POR_RODADA) -> list[int]:
    """
    Jogos sem consulta, com consulta vencida, ou com falha antiga.
    Primeiro os que tiveram oferta física nos últimos 30 dias (é com eles que o veredito importa);
    os parados são atualizados só 1x por semana.
    """
    preparar(db)
    agora = datetime.now(timezone.utc)
    ok_ate = (agora - timedelta(hours=VALIDADE_HORAS)).isoformat()
    ok_inativo_ate = (agora - timedelta(days=VALIDADE_INATIVO_DIAS)).isoformat()
    ativo_desde = (agora - timedelta(days=30)).isoformat()
    falha_ate = (agora - timedelta(hours=ESPERA_APOS_FALHA_HORAS)).isoformat()
    fora_ate = (agora - timedelta(hours=ESPERA_SITE_FORA_HORAS)).isoformat()
    rows = db.execute(
        """SELECT j.id FROM jogos j
             LEFT JOIN digital d ON d.jogo_id = j.id
             LEFT JOIN (SELECT jogo_id, MAX(data) ultima FROM ofertas GROUP BY jogo_id) o ON o.jogo_id = j.id
           WHERE IFNULL(j.tipo, 'jogo') = 'jogo' AND (d.jogo_id IS NULL
              OR (d.erro IS NULL AND d.atualizado < CASE WHEN o.ultima >= ? THEN ? ELSE ? END)
              OR (d.erro IS NOT NULL AND d.temporario = 1 AND d.atualizado < ?)
              OR (d.erro IS NOT NULL AND IFNULL(d.temporario, 0) = 0 AND d.atualizado < ?))
           ORDER BY IFNULL(o.ultima >= ?, 0) DESC, d.atualizado IS NOT NULL, d.atualizado, o.ultima DESC
           LIMIT ?""",
        (ativo_desde, ok_ate, ok_inativo_ate, fora_ate, falha_ate, ativo_desde, limite)).fetchall()
    return [r["id"] for r in rows]


def iniciar_atualizador(caminho_db: str, log=print, a_cada_min: int = RODADA_MIN):
    """
    Thread que, de tempos em tempos, atualiza alguns jogos pendentes.
    Carga inicial: enquanto existir jogo que nunca foi consultado, emenda uma rodada na outra
    (mantendo a pausa entre páginas); depois volta ao ritmo normal de RODADA_MIN.
    """
    def nunca_consultados() -> tuple[int, int]:
        db = sqlite3.connect(caminho_db, timeout=10)
        try:
            preparar(db)
            total = db.execute("SELECT COUNT(*) FROM jogos").fetchone()[0]
            faltam = db.execute("SELECT COUNT(*) FROM jogos j LEFT JOIN digital d ON d.jogo_id = j.id "
                                "WHERE d.jogo_id IS NULL AND IFNULL(j.tipo, 'jogo') = 'jogo'").fetchone()[0]
            return faltam, total
        finally:
            db.close()

    def rodada() -> bool:
        """False se o site estava fora/limitando (aí não emenda outra rodada)."""
        db = sqlite3.connect(caminho_db, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            for jogo_id in pendentes(db):
                nome = db.execute("SELECT nome FROM jogos WHERE id=?", (jogo_id,)).fetchone()["nome"]
                try:
                    d = atualizar_jogo(db, jogo_id)
                except SiteIndisponivel as e:
                    log(f"Deku Deals indisponível ({e}). Pauso as consultas até a próxima rodada.")
                    return False                   # não insiste: o site pode estar nos limitando
                except Exception as e:             # erro inesperado num jogo não para os outros
                    log(f"Falha ao consultar o digital de {nome}: {e!r}")
                    try:                           # registra, para a carga inicial não girar nele para sempre
                        salvar(db, jogo_id, None, None, f"Erro ao ler a página ({e}). Tentarei de novo mais tarde.")
                    except Exception:
                        pass
                    continue
                if d and d.get("preco_atual") is not None and not d.get("erro"):
                    log(f"💻 Digital de {nome}: R$ {d['preco_atual']:.2f} (menor R$ {d['menor_preco']:.2f})")
                time.sleep(INTERVALO_ENTRE_PAGINAS)
            return True
        finally:
            db.close()

    def laco():
        time.sleep(20)                             # deixa o monitor terminar de iniciar
        em_carga = False
        while True:
            site_ok = True
            try:
                site_ok = rodada()
                faltam, total = nunca_consultados()
            except Exception as e:
                log(f"Atualizador do Deku Deals: {e!r}")
                faltam, total = 0, 0
            if site_ok and faltam:
                if not em_carga:
                    log(f"📦 Carga inicial do digital: {faltam} jogos sem consulta. Vou emendar as rodadas até terminar.")
                em_carga = True
                log(f"📦 Carga inicial: {total - faltam} de {total} jogos consultados")
                time.sleep(PAUSA_CARGA_INICIAL_S)
                continue
            if em_carga and not faltam:
                log("📦 Carga inicial do digital concluída. Volto a atualizar a cada "
                    f"{a_cada_min} min (ativos 1x por dia, parados 1x por semana).")
                em_carga = False
            time.sleep(a_cada_min * 60)

    threading.Thread(target=laco, daemon=True, name="deku").start()


# ================================================================ veredito
def veredito(fisico_atual: Optional[float], fisico_menor: Optional[float], dig: Optional[dict],
             data_fisico: Optional[str] = None) -> Optional[dict]:
    """
    Compara o físico (dos canais) com o digital (Deku Deals).
    tipo: 'fisico' | 'fisico_hoje' | 'digital' | 'empate'
    """
    if not dig or dig.get("preco_atual") is None or fisico_atual is None:
        return None
    da, dm = dig["preco_atual"], dig.get("menor_preco") or dig["preco_atual"]
    dif = round(fisico_atual - da, 2)

    if abs(dif) <= max(5, da * 0.03):
        tipo, texto = "empate", "Físico e digital estão praticamente no mesmo preço. O físico ainda pode ser revendido ou emprestado."
    elif fisico_atual <= dm:
        tipo = "fisico"
        texto = (f"R$ {da - fisico_atual:.2f} mais barato que o digital hoje "
                 f"e abaixo do menor preço digital da história (R$ {dm:.2f}).")
    elif fisico_atual < da:
        tipo = "fisico_hoje"
        texto = (f"O físico está R$ {da - fisico_atual:.2f} mais barato que o digital hoje, "
                 f"mas o digital já chegou a R$ {dm:.2f} em promoção.")
    else:
        tipo = "digital"
        texto = f"O digital está R$ {dif:.2f} mais barato agora."
        if fisico_menor is not None and fisico_menor < da:
            texto += f" O físico já apareceu por R$ {fisico_menor:.2f} nos canais."
    if data_fisico:
        dias = (datetime.now(timezone.utc) - datetime.fromisoformat(data_fisico)).days
        if dias >= 30:
            texto += f" Atenção: a última oferta física que vi é de {dias} dias atrás."
    titulo = {"fisico": "Vale o físico", "fisico_hoje": "Físico mais barato hoje",
              "digital": "Digital mais barato", "empate": "Mesmo preço"}[tipo]
    return {"tipo": tipo, "titulo": titulo, "texto": _br(texto), "diferenca": dif}


def _br(texto: str) -> str:
    """Troca 'R$ 123.45' por 'R$ 123,45' no texto."""
    return re.sub(r"R\$ (\d+)\.(\d{2})", lambda m: f"R$ {int(m.group(1)):,}".replace(",", ".") + f",{m.group(2)}", texto)
