"""
Extrai ofertas de jogos em mídia física a partir do texto das mensagens.
Calibrado para os formatos de:
  - Ofertas Nintendo BR / Ofertas Playstation BR  ("[Mídia Física] X via Loja" + "De R$A por R$B")
  - Desconto em Games                              ("Jogo - Plataforma - (Loja)" + "R$ X à vista")
  - Promo Games                                    ("Jogo - Plataforma" + "R$ X" + "[LOJA]")
  - Promotec Games                                 ("[LOJA] Jogo - Plataforma" + "De: R$A / Por: R$B")
Controles, fones etc. viram oferta com tipo "acessorio"; bundles, "bundle"; edições de colecionador, "colecionador".
Consoles (sozinhos ou com jogo), monitores e teclados são descartados.
Avisos, produtos digitais (gift card, assinatura) e o que não tem a ver com games retornam None.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------- plataformas
# Ordem importa: o mais específico primeiro ("Switch 2" antes de "Switch").
PLATAFORMAS = [
    ("Switch 2", r"(nintendo\s*)?switch\s*2\b|\bns2\b"),
    ("Switch",   r"(nintendo\s*)?switch\b|\bnsw\b"),
    ("PS5",      r"\bps\s?5\b|playstation\s*5"),
    ("PS4",      r"\bps\s?4\b|playstation\s*4"),
    ("Xbox Series", r"xbox\s*series(\s*[xs](\s*\|\s*[xs])?)?|\bxsx\b"),
    ("Xbox One", r"xbox\s*one"),
]

# ---------------------------------------------------------------- o que é cada oferta
# Ordem: descartar > acessório > console > jogo (ex.: "Unidade de disco para consoles PS5" é acessório).
DESCARTAR = re.compile(
    r"\b(assinatura|ps plus|playstation plus|game pass|nintendo switch online|gift ?cards?|giftcards?|"
    r"placas? de v[ií]deo|placa-m[aã]e|processador|mem[oó]ria ram|gabinete|fonte de alimenta[cç][aã]o|"
    r"water ?cooler|rtx ?\d+|geforce|radeon|monitor(es)?|teclados?|headsets?|headphones?|fones?|cadeiras?|mousepads?|^\s*(\[\[\]]*\]\s*)?mouses?\b(?!\s*(:|p\.?\s?i\b))|mouses?\s+(gamer|sem fio|com fio|wireless|bluetooth|[oó]ptico|vertical)|earbuds?|airpods|pulse (elite|explore|3d)|inzone|iphone|ipad|macbook|samsung galaxy|galaxy (s|z|a|m|note|tab|buds|watch) ?\w*\d|redmi|xiaomi|motorola|"
    r"smartwatch|apple watch|"
    r"cart[aã]o presente|cart[aã]o pr[eé]-?pago|m[ií]dia digital|c[oó]digo digital|vers[aã]o digital|\bkey\b|"
    r"pacote de melhorias|funko|camiseta|caneca|notebook|smartphone|celular|smart ?tv|geladeira|"
    r"cupom:?\s*\S+\s+esgotado)\b",
    re.I,
)
ACESSORIO = re.compile(
    r"\b(controles?|dualsense|dualshock|joy-?cons?|pro controller|carregador(es)?|"
    r"base de carregamento|cases?|capinhas?|capas? protetoras?|pel[ií]culas?|suportes?|hd externo|ssd|"
    r"cart[aã]o de mem[oó]ria|micro ?sd|volantes?|pedais|pedal|estojos?|c[aâ]mbio|tampas?|faceplates?|split pad|"
    r"unidade de disco|amiibos?|grips?|bolsas?|mochilas?|cabos?|adaptador(es)?|dock|protetor(es)?|"
    r"skins?|gamepad|joystick|arcade stick|hub|playstation portal|ps portal)\b|^\s*(drive|leitor) de disco\b|\bpara\s+(o\s+)?(ps\s?5|playstation\s*5)\s+(fat|slim|pro)\b",
    re.I,
)
CONSOLE = re.compile(
    r"\bconsoles?\b|\b\d+\s?(gb|tb)\b|\bleitor de disco\b|\bcom leitor\b|\bedi[cç][aã]o digital\b|"
    r"\b(playstation\s*5|ps\s?5|nintendo\s+switch(\s*2)?|switch\s*2)\s+(slim|pro|lite|oled)\b|"
    r"^\s*(nintendo\s+)?switch(\s*2|\s+lite|\s+oled)?\s*(\(.*\))?\s*$|"
    r"^\s*(playstation|ps)\s*5\s*(\(.*\))?\s*$|"
    r"^\s*(\[[^\]]*\]\s*)?(bundle\s+)?(console\s+)?(nintendo\s+)?switch(\s*2|\s+oled|\s+lite)?\s*\+|"
    r"^\s*(\[[^\]]*\]\s*)?(bundle\s+)?(console\s+)?(playstation|ps)\s*5(\s+(slim|pro|digital))?\s*\+|"
    r"\b(playstation\s*5|ps\s?5)(\s+(slim|pro))?\s+(sem|com)\s+drive\b|"
    r"^\s*(\[\[\]]*\]\s*)?bundle\s+(console\s+)?(nintendo\s+switch|switch\s*2|playstation\s*5|ps\s?5)\b|"
    r"^\s*(\[[^\]]*\]\s*)?(console\s+)?(nintendo\s+switch(\s*2)?|switch\s*2|playstation\s*5|ps\s?5)"
    r"\s+(edi[cç][aã]o|bundle)\b",
    re.I,
)
# console que a regra de acessório pegaria antes ("PlayStation 5 Pro SSD 2TB", "Bundle Console Switch 2 + Cartão microSD")
CONSOLE_ANTES = re.compile(
    r"^\s*(\[[^\]]*\]\s*)?(bundle\s+)?console\s+(nintendo|playstation|ps\s?5|switch)|"
    r"^\s*(\[[^\]]*\]\s*)?(console\s+)?(playstation\s*5|ps\s?5)(\s+(pro|slim|digital))?\s+(ssd\s+)?\d+\s?(gb|tb)\b",
    re.I)
# post de várias ofertas ("Franquia God of War", "Games Pokémon em promo", "Promoção jogos PS5 no Mercado Livre")
PROMO_GENERICA = re.compile(
    r"^\s*(\[[^\]]*\]\s*)?(franquia|games|promo[cç][aã]o( de)?( muitos)? jogos|sele[cç][aã]o de jogos)\b|"
    r"^\s*(\[[^\]]*\]\s*)?jogos\s+(d[aeo]s?|por|para|com|em|ps\s?[45]|nintendo|switch)\b|"
    r"\b(em oferta|com desconto|em promo|para aproveitar o cupom)\s*$|\bjogos digitais\b", re.I)
BUNDLE = re.compile(r"\bbundles?\b", re.I)
COLECIONADOR = re.compile(r"colecionador|collector'?s", re.I)

# compatibilidade: "não é jogo" (usado pelo deku.py para não buscar preço digital)
NAO_JOGO = re.compile(f"{DESCARTAR.pattern}|{ACESSORIO.pattern}|{CONSOLE.pattern}", re.I)


GENERICAS = re.compile(r"\b(em|na|no|de|do|da|promo\w*|oferta\w*|nacional|novo|nova|console|bundle|"
                       r"lan[cç]amento|caiu|baixou|desconto|imperd[ií]vel|ap[eé]nas|s[oó])\b", re.I)


def classificar(titulo: str) -> str:
    """'descartar', 'acessorio', 'colecionador', 'bundle' ou 'jogo'.
    Consoles (sozinhos ou com jogo), monitores e teclados são descartados."""
    # "Switch™ 2", "Switch V2", "Switch 2 – Sports": tira os símbolos e padroniza antes de comparar
    titulo = re.sub(r"[™®©]", "", titulo).replace("–", "-").replace("—", "-")
    titulo = re.sub(r"(?i)\bswitch\s*v2\b", "Switch", titulo)
    if DESCARTAR.search(titulo) or PROMO_GENERICA.search(titulo) or CONSOLE_ANTES.search(titulo):
        return "descartar"
    if ACESSORIO.search(titulo):
        return "acessorio"
    if CONSOLE.search(titulo):
        return "descartar"
    if COLECIONADOR.search(titulo):          # "Bundle ... Collector's Edition" conta como colecionador
        return "colecionador"
    if BUNDLE.search(titulo):
        return "bundle"
    # sobra só o nome do console e palavras genéricas ("PS5 EM PROMOÇÃO") → é o console: descarta
    resto = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", titulo)
    for _, padrao in PLATAFORMAS:
        resto = re.sub(padrao, " ", resto, flags=re.I)
    resto = GENERICAS.sub(" ", sem_acento(resto))
    if detectar_plataforma(titulo) and not re.sub(r"[^a-z0-9]", "", resto.lower()):
        return "descartar"
    return "jogo"


# Domínios que são do próprio canal / divulgação (não são link de compra).
DOMINIOS_IGNORADOS = ("godg.me", "ofertasnintendo.com.br", "ofertasplaystation.com.br",
                      "t.me", "bit.ly", "chat.whatsapp", "instagram.com", "x.com", "twitter.com")

LOJAS_DOMINIO = {
    "meli.la": "Mercado Livre", "meli.promo": "Mercado Livre", "mercadolivre": "Mercado Livre",
    "amazon": "Amazon", "amzn": "Amazon",
    "magalu": "Magalu", "magazineluiza": "Magalu",
    "kabum": "KaBuM!", "shopee": "Shopee", "aliexpress": "AliExpress",
    "americanas": "Americanas", "casasbahia": "Casas Bahia", "carrefour": "Carrefour",
    "nuuvem": "Nuuvem", "gamerhut": "Gamer Hut",
}

LOJAS_NOMES = re.compile(r"amazon|mercado\s*liv|magalu|magazine|kabum|shopee|aliexpress|americanas|"
                         r"casas\s*bahia|carrefour|nuuvem|gamer\s*hut|submarino|extra|ponto|fast\s*shop", re.I)

# "1.299,90", "299,90", "299" e também "299.90" (ponto decimal, comum em lojas)
PRECO = r"R\$\s?(\d+\.\d{2}(?!\d)|\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
URL = re.compile(r"https?://\S+|\b[\w-]+\.(?:la|com|com\.br|me|ly)/\S+", re.I)


@dataclass
class Oferta:
    jogo: str                  # nome limpo, como exibido
    chave: str                 # nome normalizado p/ comparação
    plataforma: Optional[str]
    preco: float
    preco_de: Optional[float] = None
    loja: Optional[str] = None
    cupom: Optional[str] = None
    pix: bool = False
    frete_gratis: bool = False
    prevenda: bool = False
    link: Optional[str] = None
    tipo: str = "jogo"         # "jogo", "acessorio", "bundle" ou "colecionador"
    plataforma_escrita: bool = True   # False = veio do padrão do canal (a mensagem não dizia)
    extras: dict = field(default_factory=dict)

    @property
    def desconto(self) -> Optional[int]:
        if self.preco_de and self.preco_de > self.preco:
            return round(100 * (1 - self.preco / self.preco_de))
        return None


# ---------------------------------------------------------------- utilidades
def para_float(txt: str) -> float:
    if re.fullmatch(r"\d+\.\d{2}", txt):          # 299.90 → ponto é decimal
        return float(txt)
    return float(txt.replace(".", "").replace(",", "."))


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def limpar_emojis(s: str) -> str:
    # remove emojis/bandeiras e símbolos decorativos
    return re.sub(r"[\U0001F000-\U0001FAFF☀-➿️‍]", "", s).strip()


def detectar_plataforma(texto: str) -> Optional[str]:
    for nome, padrao in PLATAFORMAS:
        if re.search(padrao, texto, re.I):
            return nome
    return None


def normalizar_nome(nome: str) -> str:
    """Gera uma chave de comparação: sem acento, minúscula, sem plataforma/capa/ruído."""
    s = sem_acento(nome.lower())
    for _, padrao in PLATAFORMAS:
        s = re.sub(padrao, " ", s, flags=re.I)
    s = re.sub(r"\b(pre-?venda( d[oa])?|midia fisica|capa (regular|americana|"
               r"brasileira|nacional|exclusiva)|edicao|edition|nintendo|playstation|"
               r"the legend of|para|jogo|game|lacrado|novo)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def extrair_link(texto: str) -> tuple[Optional[str], Optional[str]]:
    """Link do produto. Link logo depois de "resgate o cupom" é da página do cupom: só se não houver outro."""
    achados = []
    for m in URL.finditer(texto):
        url = m.group(0).rstrip(").,")
        if any(d in url.lower() for d in DOMINIOS_IGNORADOS):
            continue
        antes = texto[:m.start()].rstrip().rsplit("\n", 2)[-2:]      # a linha do link e a de cima
        do_cupom = bool(re.search(r"cupo[mn]", " ".join(antes), re.I))
        loja = next((l for d, l in LOJAS_DOMINIO.items() if d in url.lower()), None)
        achados.append((do_cupom, url, loja))
    if not achados:
        return None, None
    _, url, loja = min(achados, key=lambda a: a[0])             # o primeiro que não é de cupom
    return url, loja


def extrair_preco(texto: str) -> tuple[Optional[float], Optional[float]]:
    """Retorna (preço final, preço 'de')."""
    # "NÃO É SEU MENOR VALOR!! FOI R$ 67,31 à vista": preço de outra vez, não o de agora
    texto = re.sub(r"\b(foi|j[aá] (foi|esteve|saiu))\b:?\s*(por\s+)?(r\$\s*)?\d[\d.]*(,\d{2})?(\s*(à|a)\s*vista)?",
                   " ", texto, flags=re.I)
    # valor do cupom e compra mínima: "cupom de R$ 30 ou R$ 40 OFF", "R$ 50 OFF em R$ 149", "20% OFF acima de R$ 99"
    valor = r"(r\$\s*)?\d[\d.]*(,\d{2})?"
    texto = re.sub(valor + r"\s*%?\s*(off|de desconto)\b(\s+(em|nas compras|em compras|acima de|a partir de)"
                   r"(\s+(acima|a partir)\s+de)?\s+" + valor + r")?", " ", texto, flags=re.I)
    texto = re.sub(r"\b(compras?\s+)?(acima|a partir)\s+de\s+" + valor, " ", texto, flags=re.I)
    # preço dividido de combo: "(Cada jogo sai por R$43,32)", "-Cada um sai por R$ 279,90"
    texto = re.sub(r"\bcada\s+(um|jogo|game)\s+sa[ií]\s+(por\s+)?" + valor, " ", texto, flags=re.I)
    # comentário do canal: "jogaram o preço R$100 conto mais caro"
    texto = re.sub(valor + r"\s*(contos?|reais)?\s+mais\s+(caro|barato)", " ", texto, flags=re.I)
    m = re.search(r"\bde:?\s+" + PRECO + r"\s+por:?\s+" + PRECO, texto, re.I)
    if m:
        return para_float(m.group(2)), para_float(m.group(1))
    m = re.search(r"\bpor:?\s+" + PRECO, texto, re.I)
    if m:
        return para_float(m.group(1)), None
    m = re.search(PRECO + r"\s*(?:à|a)\s*vista", texto, re.I)
    if m:
        return para_float(m.group(1)), None
    # último recurso: primeiro R$ que não seja parcela ("4x de R$37")
    for m in re.finditer(PRECO, texto):
        antes = texto[max(0, m.start() - 12):m.start()].lower()
        if re.search(r"\d+\s?x\s?de\s*$", antes) or "de " == antes[-3:]:
            continue
        return para_float(m.group(1)), None
    return None, None


def nome_da_loja(loja: Optional[str]) -> Optional[str]:
    """Nome padrão da loja: "kabum", "KABUM" e "KaBuM!" → "KaBuM!"."""
    if not loja:
        return loja
    simples = re.sub(r"[^a-z]", "", sem_acento(loja.lower()))
    for nome in set(LOJAS_DOMINIO.values()):
        if re.sub(r"[^a-z]", "", sem_acento(nome.lower())) == simples:
            return nome
    if simples in ("magazineluiza", "magazine"):
        return "Magalu"
    return loja


# ---------------------------------------------------------------- formatos
FORMATO_TAG = re.compile(r"\[\s*m[ií]dia\s+f[ií]sica\s*\]\s*(.+?)\s+via\s+(.+)", re.I)
FORMATO_TRACO = re.compile(r"^(.+?)\s+-\s+\(([^)]+)\)\s*$")
FORMATO_VIA = re.compile(r"^(.+?)\s+via\s+(.+)$", re.I)                 # "Nintendo Switch 2 via Shopee"
LOJA_COLCHETES = re.compile(r"^\[\s*([^\]]+?)\s*\]$")                   # "[MERCADO LIVRE]"


# Palavras que aparecem depois de "cupom" e não são o código ("use o cupom AINDA hoje", "cupom de desconto")
NAO_E_CUPOM = {
    "AINDA", "APENAS", "PARA", "AQUI", "ANTERIOR", "APLICOU", "APLICADO", "ESGOTADO", "ESGOTOU", "ESGOTANDO",
    "DESCONTO", "DESCONTOS", "CUPOM", "CUPONS", "COUPON", "VALIDO", "VÁLIDO", "ATIVO", "ATIVADO", "LIBERADO",
    "NOVO", "ABAIXO", "ACIMA", "NESSE", "NESTE", "DESSE", "DESTE", "NAAPP", "PELO", "PELA", "COMO", "QUANDO",
    "TAMBEM", "TAMBÉM", "MAIS", "MENOS", "SITE", "LINK", "PRODUTO", "PAGINA", "PÁGINA", "RESGATE", "RESGATAR",
}


def extrair_cupom(texto: str):
    """Código depois de "cupom". Escrito em minúsculas só vale se tiver número ("cupom para" não é cupom)."""
    for m in re.finditer(r"cupom:?\s*([A-Za-z0-9]{4,})\b", texto, re.I):
        codigo = m.group(1)
        if codigo.upper() in NAO_E_CUPOM:
            continue
        if codigo != codigo.upper() and not re.search(r"\d", codigo):
            continue
        return codigo.upper()
    return None


def extrair(texto: str, plataforma_padrao: Optional[str] = None) -> Optional[Oferta]:
    if not texto:
        return None
    linhas = [limpar_emojis(l) for l in texto.splitlines() if l.strip()]
    if not linhas:
        return None

    titulo = loja = None
    marcado_fisico = False

    # Formato 1: "[Mídia Física] Jogo via Loja"
    for l in linhas[:3]:
        m = FORMATO_TAG.search(l)
        if m:
            titulo, loja, marcado_fisico = m.group(1), m.group(2).strip(), True
            break

    # Formato 2: "Jogo - Plataforma ... - (Loja)"
    if not titulo:
        for l in linhas[:3]:
            m = FORMATO_TRACO.match(l)
            if m:
                titulo, loja = m.group(1), m.group(2).strip()
                break

    # Formato 5 (Promotec Games): "[MERCADOLIVRE] Jogo - PS5", às vezes depois de uma frase de chamada
    if not titulo:
        for l in linhas[:4]:
            m = re.match(r"^\[([^\]]+)\]\s*(\S.+)$", l)
            if m and LOJAS_NOMES.search(m.group(1)) and not re.search(r"m[ií]dia", m.group(1), re.I):
                titulo, loja = m.group(2), m.group(1)
                break

    # Formato 3 (PromoGames): 1ª linha é o produto e a loja vem numa linha "[MERCADO LIVRE]"
    if not titulo:
        loja_col = next((m.group(1) for l in linhas[1:] if (m := LOJA_COLCHETES.match(l))
                         and not re.search(r"m[ií]dia|pr[eé]-?venda|esgot|caiu", m.group(1), re.I)), None)
        if loja_col:
            titulo, loja = linhas[0], loja_col

    # Formato 3b (Desconto em Games): "Jogo - PS5 (Mercado Livre)"
    if not titulo:
        m = re.match(r"^(.+?\s+-\s+.+?)\s*\(([^)]+)\)\s*$", linhas[0])
        if m and detectar_plataforma(m.group(1).rsplit(" - ", 1)[1]) and LOJAS_NOMES.search(m.group(2)):
            titulo, loja = m.group(1), m.group(2).strip()

    # Formato 4: "Produto via Loja" sem a tag (consoles e acessórios nos canais da Nintendo/PlayStation)
    if not titulo:
        m = FORMATO_VIA.match(linhas[0])
        if m:
            titulo, loja = m.group(1), m.group(2).strip()

    if not titulo:
        return None
    tipo = classificar(titulo)
    if tipo == "descartar":
        return None

    preco, preco_de = extrair_preco(texto)
    if not preco or preco < 20:          # descarta valores absurdos/parcelas
        return None

    plataforma = detectar_plataforma(titulo) or plataforma_padrao
    # Jogo sem a tag [Mídia Física] só vale com a plataforma escrita (evita avisos e produtos soltos).
    # Acessório e console não precisam: "Headset HyperX Cloud" não diz plataforma.
    if tipo == "jogo" and not marcado_fisico and not detectar_plataforma(titulo):
        return None

    prevenda = bool(re.search(r"pr[ée]-?venda", texto, re.I))
    nome = re.sub(r"^(\s*\[[^\]]*\]\s*)+", "", titulo)
    nome = re.sub(r"^pr[ée]-?venda\s+(d[oa]\s+)?", "", nome, flags=re.I)
    # tira " - Switch 2 Capa Regular" do final do nome (acessório guarda a cor: "Dualsense - Techno Red")
    if tipo in ("jogo", "bundle", "colecionador"):
        nome = re.split(r"\s+-\s+", nome)[0].strip(" -–")
    else:
        partes = re.split(r"\s+-\s+", re.sub(r"\s+", " ", nome))
        while len(partes) > 1 and detectar_plataforma(partes[-1]) and len(partes[-1]) <= 25:
            partes.pop()                          # "Controle DualSense - PS5" → sem o console no fim
        nome = " - ".join(partes).strip(" -–")
    # "Nintendo Switch 2 - Modelo Importado" vira só "Nintendo Switch 2" depois de limpar: é o console
    if not nome or (tipo == "jogo" and classificar(nome) == "descartar"):
        return None

    link, loja_link = extrair_link(texto)
    cupom = extrair_cupom(texto)

    loja = loja or loja_link
    if loja and loja.isupper():                              # "[MERCADO LIVRE]" → nome do link ou "Mercado Livre"
        loja = loja_link or loja.title()
    if loja and re.match(r"mercado\s*liv", loja, re.I):   # corrige "Mercado Live"
        loja = "Mercado Livre"
    loja = nome_da_loja(loja)
    # loja digital (PlayStation Store, eShop): o monitor é de mídia física
    if re.search(r"playstation\s*store|\beshop\b|microsoft\s*store|xbox\s*store", loja or "", re.I) \
            or re.search(r"store\.playstation\.com|nintendo\.com/.*/store|ec\.nintendo\.com", link or "", re.I):
        return None

    return Oferta(
        jogo=nome,
        chave=normalizar_nome(nome),
        plataforma=plataforma,
        preco=preco,
        preco_de=preco_de,
        loja=loja,
        cupom=cupom,
        pix=bool(re.search(r"\bpix\b", texto, re.I)),
        frete_gratis=bool(re.search(r"frete\s+gr[aá]tis", texto, re.I)),
        prevenda=prevenda,
        link=link,
        tipo=tipo,
        plataforma_escrita=bool(detectar_plataforma(titulo)),
    )


def menciona_esgotado(texto: str) -> bool:
    # "esgotado", "esgotou", "esgotaram" — mas não "antes que esgote", "pode esgotar"
    return bool(re.search(r"\besgot(?:ad[oa]s?|ou|aram)\b", texto or "", re.I))


ROMANOS = {"ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi"}
ROMANOS_NUM = {r: n for n, r in enumerate(["ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi"], 2)}


def numeros_do_nome(chave: str) -> frozenset:
    """Números (também dentro de "2s", "x2") e algarismos romanos: '6', 'vii'. Diferenciam continuações."""
    achados = set()
    for t in chave.split():
        if t in ROMANOS:
            achados.add(str(ROMANOS_NUM[t]))      # "vii" = "7": a lista de desejos casa os dois jeitos
        achados.update(str(int(n)) for n in re.findall(r"\d+", t))
    return frozenset(achados)
