"""Banco SQLite: jogos, ofertas, lista de desejos e alertas enviados."""
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from rapidfuzz import fuzz

from extrator import Oferta, numeros_do_nome
from semelhanca import mesmo_jogo, palavras

SIMILARIDADE_MESMO_JOGO = 88   # 0-100: quão parecido o nome precisa ser p/ ser o mesmo jogo
# Mesma oferta (jogo, preço e loja) dentro dessa janela = repost de outro canal, não grava de novo.
# Depois disso conta como oferta nova: o canal repostando no dia seguinte mostra que o preço continua.
JANELA_REPOST_HORAS = 6

ESQUEMA = """
CREATE TABLE IF NOT EXISTS jogos (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    chave TEXT NOT NULL,
    plataforma TEXT
);
CREATE TABLE IF NOT EXISTS ofertas (
    id INTEGER PRIMARY KEY,
    jogo_id INTEGER NOT NULL REFERENCES jogos(id),
    preco REAL NOT NULL,
    preco_de REAL,
    loja TEXT,
    cupom TEXT,
    pix INTEGER,
    frete_gratis INTEGER,
    prevenda INTEGER,
    link TEXT,
    canal_id INTEGER,
    msg_id INTEGER,
    link_msg TEXT,
    data TEXT NOT NULL,
    ativo INTEGER DEFAULT 1,
    UNIQUE (canal_id, msg_id)
);
CREATE TABLE IF NOT EXISTS desejos (
    id INTEGER PRIMARY KEY,
    texto TEXT NOT NULL,
    chave TEXT NOT NULL,
    plataforma TEXT,
    preco_alvo REAL NOT NULL,
    criado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alertas (
    jogo_id INTEGER, preco REAL, data TEXT
);
CREATE TABLE IF NOT EXISTS canais_lidos (
    canal_id INTEGER PRIMARY KEY, ultimo_msg_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS apelidos (                  -- nome que você juntou/renomeou no painel -> jogo certo
    chave TEXT PRIMARY KEY, jogo_id INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mensagens_excluidas (       -- ofertas excluídas no painel: edição no canal não traz de volta
    canal_id INTEGER, msg_id INTEGER, PRIMARY KEY (canal_id, msg_id)
);
CREATE TABLE IF NOT EXISTS estado (                   -- sinais do monitor p/ a página de saúde
    chave TEXT PRIMARY KEY, valor TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS registro_erros (            -- últimos avisos/erros do log (página de saúde)
    id INTEGER PRIMARY KEY, data TEXT NOT NULL, nivel TEXT, texto TEXT
);
CREATE TABLE IF NOT EXISTS revisao_ok (                -- itens da fila de revisão que você dispensou
    chave TEXT PRIMARY KEY, data TEXT
);
CREATE INDEX IF NOT EXISTS idx_ofertas_jogo ON ofertas(jogo_id, data);
CREATE INDEX IF NOT EXISTS idx_alertas ON alertas(jogo_id, data);
"""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def conectar(caminho: str = "precos.db") -> sqlite3.Connection:
    db = sqlite3.connect(caminho, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")   # permite o painel ler enquanto o monitor grava
    db.executescript(ESQUEMA)
    colunas = {c["name"] for c in db.execute("PRAGMA table_info(jogos)")}
    if "capa" not in colunas:                       # bancos criados antes das capas
        db.execute("ALTER TABLE jogos ADD COLUMN capa TEXT")
        db.commit()
    if "tipo" not in {c["name"] for c in db.execute("PRAGMA table_info(jogos)")}:
        # "jogo", "acessorio" ou "console" — definido à mão no painel
        db.execute("ALTER TABLE jogos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'jogo'")
        db.commit()
    if "manual" not in {c["name"] for c in db.execute("PRAGMA table_info(ofertas)")}:
        # 1 = jogo corrigido à mão no painel: edição da mensagem no canal não desfaz
        db.execute("ALTER TABLE ofertas ADD COLUMN manual INTEGER DEFAULT 0")
        db.commit()
    if "marca" not in {c["name"] for c in db.execute("PRAGMA table_info(jogos)")}:
        # "tenho" (já tenho) ou "ignorar" (não me interessa): some das listas e não alerta
        db.execute("ALTER TABLE jogos ADD COLUMN marca TEXT")
        db.commit()
    if "data" not in {c["name"] for c in db.execute("PRAGMA table_info(canais_lidos)")}:
        db.execute("ALTER TABLE canais_lidos ADD COLUMN data TEXT")   # data da última mensagem do canal
        db.commit()
    return db


# ---------------------------------------------------------------- jogos
def _chave_apelido(nome: str, plataforma: Optional[str]) -> Optional[str]:
    pals = sorted(set(palavras(nome or "")))
    return f"{' '.join(pals)}|{plataforma or ''}" if pals else None


def lembrar_apelido(db, nome: str, plataforma: Optional[str], jogo_id: int):
    """Daqui em diante, oferta com esse nome (nesse console) vai para `jogo_id`."""
    chave = _chave_apelido(nome, plataforma)
    if chave:
        db.execute("INSERT OR REPLACE INTO apelidos (chave, jogo_id) VALUES (?, ?)", (chave, jogo_id))
        db.commit()


def jogo_do_apelido(db, nome: str, plataforma: Optional[str]) -> Optional[int]:
    chave = _chave_apelido(nome, plataforma)
    if not chave:
        return None
    r = db.execute("SELECT a.jogo_id FROM apelidos a JOIN jogos j ON j.id = a.jogo_id WHERE a.chave=?",
                   (chave,)).fetchone()
    return r[0] if r else None


def obter_ou_criar_jogo(db, oferta: Oferta) -> int:
    """
    Acha o jogo já cadastrado (mesmo nome pelas regras do semelhanca.py, mesma plataforma) ou cria um novo.
    Mensagem que não diz o console no canal da Nintendo: se o jogo só existe no Switch 2 com o nome igual,
    é ele ("Puyo Puyo Tetris 2S" não é do Switch só porque o canal assume Switch).
    """
    apelido = jogo_do_apelido(db, oferta.jogo, oferta.plataforma)   # correção que você já fez no painel
    if apelido:
        return apelido
    acessorio = getattr(oferta, "tipo", "jogo") == "acessorio"
    candidatos = db.execute(
        "SELECT id, nome, tipo, plataforma FROM jogos WHERE plataforma IS ? OR plataforma IS NULL OR ? IS NULL",
        (oferta.plataforma, oferta.plataforma)).fetchall()
    achado = _primeiro_igual(oferta.jogo, candidatos, acessorio)
    if achado:
        return achado
    if not getattr(oferta, "plataforma_escrita", True) and oferta.plataforma == "Switch":
        for c in db.execute("SELECT id, nome, tipo FROM jogos WHERE plataforma = 'Switch 2'"):
            if set(palavras(c["nome"])) == set(palavras(oferta.jogo)):
                return c["id"]
    cur = db.execute("INSERT INTO jogos (nome, chave, plataforma, tipo) VALUES (?, ?, ?, ?)",
                     (oferta.jogo, oferta.chave, oferta.plataforma, getattr(oferta, "tipo", "jogo")))
    db.commit()
    return cur.lastrowid


def _primeiro_igual(nome: str, candidatos, acessorio: bool = False) -> Optional[int]:
    """O candidato que é o mesmo jogo; nome idêntico (sem ruído) ganha de parecido."""
    exato = parecido = None
    alvo = set(palavras(nome))
    for c in candidatos:
        ehacess = acessorio or (c["tipo"] == "acessorio")
        if not mesmo_jogo(nome, c["nome"], acessorio=ehacess):
            continue
        if set(palavras(c["nome"])) == alvo:
            exato = exato or c["id"]
        else:
            parecido = parecido or c["id"]
    return exato or parecido


def achar_mesmo_jogo(db, nome: str, plataforma: Optional[str], excluir: Optional[int] = None) -> Optional[int]:
    """Jogo já cadastrado que é o mesmo e tem EXATAMENTE essa plataforma (correções no painel)."""
    candidatos = db.execute("SELECT id, nome, tipo FROM jogos WHERE plataforma IS ? AND id IS NOT ?",
                            (plataforma, excluir)).fetchall()
    return _primeiro_igual(nome, candidatos)


def criar_jogo(db, nome: str, chave: str, plataforma: Optional[str], tipo: str = "jogo") -> int:
    cur = db.execute("INSERT INTO jogos (nome, chave, plataforma, tipo) VALUES (?, ?, ?, ?)",
                     (nome, chave, plataforma, tipo))
    db.commit()
    return cur.lastrowid


def juntar_jogos(db, origem: int, destino: int):
    """Passa ofertas e alertas de `origem` para `destino` e apaga `origem` (a capa é com quem chama).
    O nome de `origem` vira apelido de `destino`: ofertas futuras com aquele nome já caem no lugar certo."""
    o = db.execute("SELECT nome, plataforma FROM jogos WHERE id=?", (origem,)).fetchone()
    if o:
        lembrar_apelido(db, o["nome"], o["plataforma"], destino)
    db.execute("UPDATE apelidos SET jogo_id=? WHERE jogo_id=?", (destino, origem))
    db.execute("UPDATE ofertas SET jogo_id=?, manual=1 WHERE jogo_id=?", (destino, origem))
    db.execute("UPDATE alertas SET jogo_id=? WHERE jogo_id=?", (destino, origem))
    if o:                                           # "já tenho"/"não me interessa" vai junto, se o destino não tiver
        db.execute("UPDATE jogos SET marca = IFNULL(marca, (SELECT marca FROM jogos WHERE id=?)) WHERE id=?",
                   (origem, destino))
    apagar_jogo(db, origem)


def excluir_jogo(db, jogo_id: int) -> int:
    """Exclui o jogo e TODAS as ofertas dele (pedido no painel). Retorna quantas ofertas foram junto."""
    db.execute("""INSERT OR IGNORE INTO mensagens_excluidas (canal_id, msg_id)
                  SELECT canal_id, msg_id FROM ofertas WHERE jogo_id=? AND msg_id IS NOT NULL""", (jogo_id,))
    n = db.execute("DELETE FROM ofertas WHERE jogo_id=?", (jogo_id,)).rowcount
    apagar_jogo(db, jogo_id)                          # já faz o commit
    return n


def mensagem_excluida(db, canal_id: int, msg_id: int) -> bool:
    return db.execute("SELECT 1 FROM mensagens_excluidas WHERE canal_id=? AND msg_id=?",
                      (canal_id, msg_id)).fetchone() is not None


def apagar_jogo(db, jogo_id: int):
    """Apaga o jogo (sem ofertas) e o preço digital dele."""
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='digital'").fetchone():
        db.execute("DELETE FROM digital WHERE jogo_id=?", (jogo_id,))
    db.execute("DELETE FROM alertas WHERE jogo_id=?", (jogo_id,))
    db.execute("DELETE FROM apelidos WHERE jogo_id=?", (jogo_id,))
    db.execute("DELETE FROM jogos WHERE id=?", (jogo_id,))
    db.commit()


def tipo_do_jogo(db, jogo_id: int) -> str:
    r = db.execute("SELECT tipo FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    return (r["tipo"] if r else None) or "jogo"


def capa_do_jogo(db, jogo_id: int) -> Optional[str]:
    r = db.execute("SELECT capa FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    return r["capa"] if r else None


def definir_capa(db, jogo_id: int, arquivo: str):
    db.execute("UPDATE jogos SET capa=? WHERE id=?", (arquivo, jogo_id))
    db.commit()


def buscar_jogos(db, texto: str, limite: int = 5):
    from extrator import normalizar_nome
    chave = normalizar_nome(texto)
    jogos = db.execute("SELECT * FROM jogos").fetchall()
    notas = sorted(((fuzz.token_set_ratio(chave, j["chave"]), j) for j in jogos),
                   key=lambda x: -x[0])
    return [j for n, j in notas if n >= 70][:limite]


# ---------------------------------------------------------------- ofertas
def registrar_oferta(db, oferta: Oferta, canal_id: int, msg_id: int,
                     data: datetime, link_msg: str) -> Optional[tuple[int, int]]:
    """
    Grava a oferta. Retorna (jogo_id, oferta_id), ou None se for repetida
    (mesmo jogo, loja e preço nas últimas JANELA_REPOST_HORAS — repost em outro canal).
    Se a mensagem já existia (edição), atualiza e retorna None.
    """
    existente = db.execute("SELECT id, jogo_id, manual FROM ofertas WHERE canal_id=? AND msg_id=?",
                           (canal_id, msg_id)).fetchone()
    # oferta corrigida à mão no painel: a edição da mensagem atualiza o preço, mas não troca o jogo
    jogo_id = existente["jogo_id"] if existente and existente["manual"] else obter_ou_criar_jogo(db, oferta)
    campos = (jogo_id, oferta.preco, oferta.preco_de, oferta.loja, oferta.cupom,
              int(oferta.pix), int(oferta.frete_gratis), int(oferta.prevenda),
              oferta.link, link_msg)

    if existente:
        db.execute("""UPDATE ofertas SET jogo_id=?, preco=?, preco_de=?, loja=?, cupom=?,
                      pix=?, frete_gratis=?, prevenda=?, link=?, link_msg=? WHERE id=?""",
                   (*campos, existente["id"]))
        db.commit()
        return None

    desde = (data - timedelta(hours=JANELA_REPOST_HORAS)).isoformat()
    repetida = db.execute(
        """SELECT 1 FROM ofertas WHERE jogo_id=? AND preco=? AND IFNULL(loja,'')=IFNULL(?,'')
           AND data >= ?""", (jogo_id, oferta.preco, oferta.loja, desde)).fetchone()
    if repetida:
        return None

    cur = db.execute(
        """INSERT INTO ofertas (jogo_id, preco, preco_de, loja, cupom, pix, frete_gratis,
           prevenda, link, link_msg, canal_id, msg_id, data)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (*campos, canal_id, msg_id, data.isoformat()))
    db.commit()
    return jogo_id, cur.lastrowid


def marcar_esgotado(db, canal_id: int, msg_id: int):
    db.execute("UPDATE ofertas SET ativo=0 WHERE canal_id=? AND msg_id=?", (canal_id, msg_id))
    db.commit()


def ultimo_msg_id(db, canal_id: int) -> Optional[int]:
    """Última mensagem LIDA do canal (oferta ou não), para não reler tudo ao reiniciar."""
    r = db.execute("SELECT ultimo_msg_id FROM canais_lidos WHERE canal_id=?", (canal_id,)).fetchone()
    if r:
        return r["ultimo_msg_id"]
    r = db.execute("SELECT MAX(msg_id) m FROM ofertas WHERE canal_id=?", (canal_id,)).fetchone()
    return r["m"]                                   # bancos de versões anteriores


def marcar_lida(db, canal_id: int, msg_id: int, data: Optional[datetime] = None):
    """Guarda a última mensagem lida do canal e a data dela (a página de saúde vê canal parado)."""
    quando = data.isoformat() if data else None
    db.execute("""INSERT INTO canais_lidos (canal_id, ultimo_msg_id, data) VALUES (?, ?, ?)
                  ON CONFLICT(canal_id) DO UPDATE SET ultimo_msg_id = MAX(ultimo_msg_id, excluded.ultimo_msg_id),
                  data = CASE WHEN data IS NULL OR excluded.data > data THEN IFNULL(excluded.data, data) ELSE data END""",
               (canal_id, msg_id, quando))
    db.commit()


# ---------------------------------------------------------------- estado do monitor
def definir_estado(db, chave: str, valor=None):
    db.execute("INSERT OR REPLACE INTO estado (chave, valor, data) VALUES (?, ?, ?)",
               (chave, None if valor is None else str(valor), agora()))
    db.commit()


def ler_estado(db, chave: str):
    r = db.execute("SELECT valor, data FROM estado WHERE chave=?", (chave,)).fetchone()
    return (r["valor"], r["data"]) if r else (None, None)


def apagar_estado(db, chave: str):
    db.execute("DELETE FROM estado WHERE chave=?", (chave,))
    db.commit()


def registrar_erro(db, nivel: str, texto: str, manter: int = 200):
    db.execute("INSERT INTO registro_erros (data, nivel, texto) VALUES (?, ?, ?)", (agora(), nivel, texto[:2000]))
    db.execute("DELETE FROM registro_erros WHERE id <= (SELECT MAX(id) FROM registro_erros) - ?", (manter,))
    db.commit()


# ---------------------------------------------------------------- já tenho / não me interessa
MARCAS = ("tenho", "ignorar")


def marcar_jogo(db, jogo_id: int, marca: Optional[str]):
    if marca not in (None, *MARCAS):
        raise ValueError(f"marca desconhecida: {marca}")
    db.execute("UPDATE jogos SET marca=? WHERE id=?", (marca, jogo_id))
    db.commit()


def marca_do_jogo(db, jogo_id: int) -> Optional[str]:
    r = db.execute("SELECT marca FROM jogos WHERE id=?", (jogo_id,)).fetchone()
    return r["marca"] if r else None


def precos_anteriores(db, jogo_id: int, excluir_id: int, dias: int = 180) -> list[float]:
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    rows = db.execute("SELECT preco FROM ofertas WHERE jogo_id=? AND id<>? AND data>=?",
                      (jogo_id, excluir_id, desde)).fetchall()
    return [r["preco"] for r in rows]


def resumo_jogo(db, jogo_id: int) -> dict:
    rows = db.execute("SELECT * FROM ofertas WHERE jogo_id=? ORDER BY data DESC",
                      (jogo_id,)).fetchall()
    precos = [r["preco"] for r in rows]
    return {
        "jogo": db.execute("SELECT * FROM jogos WHERE id=?", (jogo_id,)).fetchone(),
        "total": len(rows),
        "minimo": min(precos) if precos else None,
        "mediana": statistics.median(precos) if precos else None,
        "ultimas": rows[:5],
    }


def ultimas_ofertas(db, limite: int = 10):
    return db.execute("""SELECT o.*, j.nome, j.plataforma FROM ofertas o
                         JOIN jogos j ON j.id=o.jogo_id ORDER BY o.data DESC LIMIT ?""",
                      (limite,)).fetchall()


# ---------------------------------------------------------------- desejos
def adicionar_desejo(db, texto: str, chave: str, plataforma: Optional[str], alvo: float):
    db.execute("INSERT INTO desejos (texto, chave, plataforma, preco_alvo, criado) "
               "VALUES (?,?,?,?,?)", (texto, chave, plataforma, alvo, agora()))
    db.commit()


def listar_desejos(db):
    return db.execute("SELECT * FROM desejos ORDER BY id").fetchall()


def desejo_combina(desejo, chave: str, plataforma: Optional[str]) -> bool:
    """O jogo (chave normalizada + plataforma) corresponde ao item da lista de desejos?"""
    if desejo["plataforma"] and desejo["plataforma"] != plataforma:
        return False
    palavras = set(desejo["chave"].split())
    if palavras <= set(chave.split()):          # "zelda" combina com qualquer Zelda
        return True
    return (numeros_do_nome(desejo["chave"]) == numeros_do_nome(chave)
            and fuzz.token_sort_ratio(desejo["chave"], chave) >= 88)


def remover_desejo(db, desejo_id: int) -> bool:
    cur = db.execute("DELETE FROM desejos WHERE id=?", (desejo_id,))
    db.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------- alertas
def alerta_ja_enviado(db, jogo_id: int, preco: float, horas: int = 24) -> bool:
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    return db.execute("SELECT 1 FROM alertas WHERE jogo_id=? AND preco<=? AND data>=?",
                      (jogo_id, preco, desde)).fetchone() is not None


def registrar_alerta(db, jogo_id: int, preco: float):
    db.execute("INSERT INTO alertas VALUES (?,?,?)", (jogo_id, preco, agora()))
    db.commit()
