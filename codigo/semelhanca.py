"""
Quando dois nomes de oferta são o MESMO jogo.

Os canais escrevem o mesmo jogo de jeitos diferentes ("Ratchet & Clank" / "Ratchet and Clank",
"Metroid Prime 4 Beyond (nacional)" / "Metroid Prime 4: Beyond"). Em vez de um "% de parecido",
usa regras:
  - ruído não conta: região/idioma ("nacional", "japonês"), "+ brindes", "day one", "liberada"...
  - edições continuam separadas: Deluxe, Gold, Steelbook, Collector's, "Seekers Edition"...
  - números diferentes = jogos diferentes ("Puyo Puyo Tetris 2S" ≠ "Puyo Puyo Tetris")
  - em nome longo (5+ palavras), uma palavra a mais é o mesmo jogo ("Assassin's Creed Black Flag Resynced")
  - acessórios só juntam com o nome igual (a cor faz diferença: "DualSense Cosmic Red" ≠ "Techno Red")
"""
import re
from functools import lru_cache

from rapidfuzz import fuzz

from extrator import PLATAFORMAS, ROMANOS, sem_acento

# não mudam o produto
RUIDO = re.compile(
    r"\b(nacional|japon[eê]s|europeu|europeia|american[oa]|importad[oa]|lacrad[oa]|liberad[oa]|"
    r"em m[ií]dia f[ií]sica|m[ií]dia f[ií]sica|brindes?|activision|playstation hits|hits|"
    r"edi[cç][aã]o padr[aã]o|standard edition|standard|day one( edition)?|launch edition|"
    r"pr[eé][- ]?venda|capa (regular|americana|brasileira|nacional|exclusiva)|"
    r"vers[aã]o (americana|nacional|europeia|brasileira)|xbox( series)?( x\s*/?\s*s| sx| xs| one)?|"
    r"modelo (importado|nacional)|caiu|baixou|oferta|promo[cç][aã]o|novo|nova|"
    r"remaster(ed)?|remasterizad[oa])\b", re.I)
# palavras que não ajudam a distinguir jogos
VAZIAS = {"the", "of", "de", "do", "da", "dos", "das", "o", "a", "e", "and", "em", "para", "jogo", "game",
          "nintendo", "playstation", "sony", "vs", "com", "with"}
# marcam uma edição diferente do mesmo jogo: nunca junta só porque o resto do nome bate
EDICAO = {"edition", "edicao", "ed", "deluxe", "gold", "ultimate", "complete", "completa", "collector",
          "collectors", "colecionador", "special", "especial", "premium", "definitive", "definitiva", "goty",
          "anniversary", "aniversario", "steelbook", "limited", "limitada", "bundle", "remake", "trilogy",
          "trilogia", "collection", "colecao", "pack", "dlc", "season", "pass"}
CONJUNCAO = re.compile(r"\s(\+|&|e|and)\s", re.I)
ROMANO_NUM = {r: n for n, r in enumerate(
    ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi"], 1)}


@lru_cache(maxsize=20000)
def palavras(nome: str) -> tuple:
    """Palavras que identificam o jogo, sem ruído, plataforma e palavras vazias."""
    s = sem_acento((nome or "").lower()).replace("&", " and ")
    s = re.sub(r"\b(the\s+)?legend\s+of\s+", " ", s)          # "Legend of Zelda ..." = "Zelda ..."
    for _, padrao in PLATAFORMAS:
        s = re.sub(padrao, " ", s, flags=re.I)
    s = RUIDO.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    pals = [p for p in s.split() if p not in VAZIAS]
    # "Part II" = "Part 2", "GTA V" = "GTA 5". "I" só vira 1 fora do começo ("I Am Setsuna" fica igual)
    return tuple(str(ROMANO_NUM[p]) if p in ROMANO_NUM and (p != "i" or i > 0) else p
                 for i, p in enumerate(pals))


def numeros(pals) -> frozenset:
    """Números (inclusive dentro de "2S", "x2") e algarismos romanos: separam continuações."""
    achados = set()
    for p in pals:
        if p in ROMANOS:
            achados.add(p)
        achados.update(str(int(n)) for n in re.findall(r"\d+", p))
    return frozenset(achados)


def mesmo_jogo(a: str, b: str, acessorio: bool = False) -> bool:
    pa, pb = palavras(a), palavras(b)
    if not pa or not pb or numeros(pa) != numeros(pb):
        return False
    sa, sb = set(pa), set(pb)
    if sa == sb:
        return True
    if acessorio:                                  # acessório: a cor/modelo faz diferença
        return False
    menor, maior, nome_maior, nome_menor = (sa, sb, b, a) if len(sa) <= len(sb) else (sb, sa, a, b)
    if menor <= maior:
        extras = maior - menor
        if extras & EDICAO:
            return False                            # "Resident Evil 4" ≠ "Resident Evil 4 Gold Edition"
        if CONJUNCAO.search(RUIDO.sub(" ", nome_maior)) and not CONJUNCAO.search(RUIDO.sub(" ", nome_menor)):
            return False                            # "FF VII Rebirth" ≠ "FF VII Remake e Rebirth" (dois jogos)
        # nome longo com uma palavra a mais: "Assassin's Creed Black Flag" = "... Black Flag Resynced".
        # Nome curto não: "Shin Megami Tensei V" ≠ "Shin Megami Tensei V Vengeance"
        return len(extras) == 1 and len(menor) >= 5
    # nenhum contém o outro: só erro de digitação ("Wings of Theve" / "Wings of Thieves")
    if (sa ^ sb) & EDICAO:
        return False
    return fuzz.token_sort_ratio(" ".join(sorted(sa)), " ".join(sorted(sb))) >= 92
