"""
Capas automáticas: recorta a foto que vem na mensagem do canal.
  1. corta a faixa com o logo do canal (topo) e selos de preço (base)
  2. remove a margem branca em volta da caixa do jogo
  3. salva em capas/<id do jogo>.jpg (largura máx. 400px)
"""
import io
import re
from pathlib import Path
from typing import Optional

from PIL import Image, ImageChops

# 400px: o painel mostra a capa com até 168px (336px em tela de alta densidade) e sobra para recortar.
LARGURA_MAX = 400
QUALIDADE = 80


def recortar(dados: bytes, cortar_topo: float = 0.0, cortar_base: float = 0.0) -> Image.Image:
    img = Image.open(io.BytesIO(dados)).convert("RGB")
    w, h = img.size
    img = img.crop((0, int(h * cortar_topo), w, int(h * (1 - cortar_base))))

    # tira o fundo branco/claro em volta da caixa
    fundo = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, fundo).convert("L").point(lambda v: 255 if v > 28 else 0)
    caixa = diff.getbbox()
    if caixa:
        cw, ch = caixa[2] - caixa[0], caixa[3] - caixa[1]
        # só aceita o recorte se sobrar algo com cara de capa (evita cortar demais)
        if cw > img.width * 0.25 and ch > img.height * 0.4:
            m = 4
            img = img.crop((max(0, caixa[0] - m), max(0, caixa[1] - m),
                            min(img.width, caixa[2] + m), min(img.height, caixa[3] + m)))

    if img.width > LARGURA_MAX:
        img = img.resize((LARGURA_MAX, round(img.height * LARGURA_MAX / img.width)), Image.LANCZOS)
    return img


def salvar_capa(pasta: Path, jogo_id: int, dados: bytes,
                cortar_topo: float = 0.0, cortar_base: float = 0.0) -> str:
    pasta.mkdir(exist_ok=True)
    destino = pasta / f"{jogo_id}.jpg"
    recortar(dados, cortar_topo, cortar_base).save(destino, "JPEG", quality=QUALIDADE, optimize=True, progressive=True)
    return destino.name


# ================================================================ edição no painel
# A primeira mudança guarda a foto que veio do canal em <id>.orig.jpg, para poder restaurar.
def _arquivos(pasta: Path, jogo_id: int) -> tuple[Path, Path]:
    return pasta / f"{jogo_id}.jpg", pasta / f"{jogo_id}.orig.jpg"


def _guardar_original(pasta: Path, jogo_id: int):
    atual, orig = _arquivos(pasta, jogo_id)
    if atual.is_file() and not orig.is_file():
        orig.write_bytes(atual.read_bytes())


def _salvar(img: Image.Image, destino: Path) -> str:
    if img.width > LARGURA_MAX:
        img = img.resize((LARGURA_MAX, round(img.height * LARGURA_MAX / img.width)), Image.LANCZOS)
    img.convert("RGB").save(destino, "JPEG", quality=QUALIDADE, optimize=True, progressive=True)
    return destino.name


def tem_original(pasta: Path, jogo_id: int) -> bool:
    return _arquivos(pasta, jogo_id)[1].is_file()


def trocar_imagem(pasta: Path, jogo_id: int, dados: bytes) -> str:
    """Capa nova enviada pelo painel (JPG, PNG, WEBP...)."""
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except Exception:
        raise ValueError("o arquivo não é uma imagem que eu consiga abrir (use JPG, PNG ou WEBP)")
    if img.width < 40 or img.height < 40:
        raise ValueError("imagem pequena demais")
    pasta.mkdir(exist_ok=True)
    _guardar_original(pasta, jogo_id)
    return _salvar(img, _arquivos(pasta, jogo_id)[0])


def recortar_atual(pasta: Path, jogo_id: int, x: float, y: float, w: float, h: float) -> str:
    """Recorta a capa atual. x, y, w, h são frações (0 a 1) da imagem."""
    atual, _ = _arquivos(pasta, jogo_id)
    if not atual.is_file():
        raise ValueError("este jogo ainda não tem capa para recortar")
    x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
    w, h = min(w, 1.0 - x), min(h, 1.0 - y)
    if w < 0.05 or h < 0.05:
        raise ValueError("a área do recorte é pequena demais")
    _guardar_original(pasta, jogo_id)
    img = Image.open(atual).convert("RGB")
    caixa = (round(x * img.width), round(y * img.height), round((x + w) * img.width), round((y + h) * img.height))
    return _salvar(img.crop(caixa), atual)


def restaurar_original(pasta: Path, jogo_id: int) -> str:
    atual, orig = _arquivos(pasta, jogo_id)
    if not orig.is_file():
        raise ValueError("não há foto original guardada para este jogo")
    atual.write_bytes(orig.read_bytes())              # grava de novo: muda a data e o navegador recarrega
    orig.unlink()
    return atual.name


def passar_capa(pasta: Path, origem: int, destino: int, copiar: bool = False) -> Optional[str]:
    """Leva (ou copia) a capa de um jogo para outro que ainda não tem. Retorna o nome do arquivo."""
    de, de_orig = _arquivos(pasta, origem)
    para, para_orig = _arquivos(pasta, destino)
    if not de.is_file() or para.is_file():
        return None
    para.write_bytes(de.read_bytes())
    if de_orig.is_file():
        para_orig.write_bytes(de_orig.read_bytes())
    if not copiar:
        apagar_capas(pasta, origem)
    return para.name


def apagar_capas(pasta: Path, jogo_id: int):
    for arq in _arquivos(pasta, jogo_id):
        arq.unlink(missing_ok=True)


# ================================================================ faxina
def limpar_orfas(pasta: Path, db) -> tuple[int, int]:
    """
    Apaga capas que nenhum item usa: de itens que não existem mais, ou que o item não usa
    (ex.: sobrou de uma troca). A original (<id>.orig.jpg) fica enquanto o item existir: é o
    "Voltar à foto original". Só mexe em arquivos com o nome no padrão das capas.
    Retorna (quantos arquivos, quantos bytes).
    """
    if not pasta.is_dir():
        return 0, 0
    capa_de = {r[0]: r[1] for r in db.execute("SELECT id, capa FROM jogos")}
    apagados = bytes_ = 0
    for arq in pasta.iterdir():
        m = re.fullmatch(r"(\d+)(\.orig)?\.jpg", arq.name)
        if not m or not arq.is_file():
            continue
        jogo_id, original = int(m.group(1)), bool(m.group(2))
        usada = jogo_id in capa_de and (original or capa_de[jogo_id] == arq.name)
        if not usada:
            bytes_ += arq.stat().st_size
            arq.unlink(missing_ok=True)
            apagados += 1
    return apagados, bytes_
