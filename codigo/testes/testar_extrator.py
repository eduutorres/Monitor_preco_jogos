"""Roda o extrator nos exemplos reais dos canais. Uso: python codigo/testes/testar_extrator.py"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))   # módulos de codigo/
from extrator import extrair

EXEMPLOS = [
    ("Switch", """[Mídia Física] Zelda Tears of the Kingdom via Gamer Hut🇧🇷

De R$399 por R$307 + frete grátis
no pagamento via PIX
- Capa americana e jogo em português

Acesse https://meli.la/2qcmWXz e use o cupom 0FERTAH0JE

Pacote de melhorias para Switch 2
Acesse http://bit.ly/3HUJDDx

Faça parte do grupo
ofertasnintendo.com.br"""),

    (None, """Pré-Venda do The Legend of Zelda: Ocarina of Time Remake - Switch 2 Capa Regular - (Mercado Live)

👉 https://meli.la/2P8o4VT
🏷 Cupom: MELIMUSIC10
R$ 387,90 à vista

Obs: O modelo da capa tá descrito no título da pré-venda🤝

🕹 Grupos de Promoções da DG:
👉 https://godg.me/WkQUSso"""),

    ("PS5", """🔥[Mídia Física] Street Fighter 6 Years 1-2 Fighters Edition via Amazon🇧🇷

De R$299 por R$149 + frete grátis
ou em até 4x de R$37 sem juros
- Inclui o jogo base com 18 personagens + 2 DLCs com mais 8 personagens + 4 estágios e novas cores de roupas
- Um dos menores preços históricos

Acesse https://link.amazon/B04N7p5CK

Faça parte do grupo
ofertasplaystation.com.br"""),

    (None, """PRAGMATA - PlayStation 5 - (Mercado Livre)

👉 https://meli.la/abc123
R$ 240,30 à vista"""),

    # --- Promo Games: "Jogo - Plataforma", preço solto e loja entre colchetes ---
    (None, """Silent Hill Townfall - PS5

R$ 244,91
Cupom: OFERTAHOJE

Link: https://meli.la/2e9AFiw
[MERCADO LIVRE]

Mais ofertas em: https://promogamesbr.com"""),

    # --- Promotec Games: frase de chamada, "[LOJA] Jogo - PS5" e "De: / Por:" ---
    (None, """Constrói aventuras heroicas para crianças 🦸

[MERCADOLIVRE] Lego Batman O Legado Do Cavaleiro Das Trevas - PS5

De: R$ 299,90
Por: R$ 221,17

🎟Use o cupom: MELIMUSIC10

🔗 https://meli.promo/s/6o7T53"""),

    # --- bundle / edição de colecionador ---
    (None, """Bundle Until Dawn 1 + 2 - PlayStation 5 (Amazon)
👉 https://desconto.games/BUsvFmH
R$ 408,40 no Pix"""),

    ("Switch", """🔥[Mídia Física] Edição de Colecionador de Zelda Tears of the Kingdom via Amazon🇧🇷

De R$1.499 por R$1.113
Acesse https://amzn.to/abc"""),

    # --- acessórios entram com o tipo marcado; consoles são descartados ---
    (None, """Controle DualSense Midnight Black - PS5 - (Amazon)
👉 https://amzn.to/xyz
R$ 349,90 à vista"""),
    (None, """Bundle PlayStation 5 Slim + 2 Jogos - (Mercado Livre)
R$ 3.499,00 à vista"""),
    ("Switch", """🔥Nintendo Switch 2 (nacional) via Shopee🇧🇷

Por R$ 3.599 no PIX
Acesse https://shopee.com.br/abc"""),
    (None, """Headset Gamer HyperX Cloud Stinger - (Amazon)
R$ 199,90 à vista"""),

    # --- o jogo "MOUSE: P.I. For Hire" não pode cair no filtro de mouse ---
    (None, """MOUSE: P.I. For Hire - PS5 (Amazon)
👉 https://amzn.to/abc
R$ 199,90"""),

    # --- devem ser IGNORADAS ---
    (None, """Mouse Gamer Sem Fio Logitech G305 - (Amazon)
R$ 199,90 à vista"""),
    (None, """Cadeira Gamer DT3 Vita - (Mercado Livre)
R$ 1.299,00 à vista"""),
    ("Switch", """🔥Funko Pop Pokémon Growlithe via Mercado Livre🇧🇷
Por R$ 89,90"""),
    (None, """Notebook Gamer Acer Nitro V15 8GB - (Mercado Livre)
R$ 4.199,00 à vista"""),
    ("Switch", """⚠️Atenção aos prazos de entrega do Mercado Livre nessa época do ano!"""),
    (None, """🎟 Cupom: MELIMUSIC10 Esgotado 😢❌"""),
]

# o que cada exemplo deve virar: (tipo, plataforma, preço, loja) ou None (ignorada)
ESPERADO = [
    ("jogo", "Switch", 307.0, "Gamer Hut"),
    ("jogo", "Switch 2", 387.90, "Mercado Livre"),
    ("jogo", "PS5", 149.0, "Amazon"),
    ("jogo", "PS5", 240.30, "Mercado Livre"),
    ("jogo", "PS5", 244.91, "Mercado Livre"),
    ("jogo", "PS5", 221.17, "Mercado Livre"),
    ("bundle", "PS5", 408.40, "Amazon"),
    ("colecionador", "Switch", 1113.0, "Amazon"),
    ("acessorio", "PS5", 349.90, "Amazon"),
    None,                                   # Bundle PlayStation 5 Slim + 2 jogos (console)
    None,                                   # Nintendo Switch 2 (nacional) (console)
    None,                                   # Headset (fones são descartados)
    ("jogo", "PS5", 199.90, "Amazon"),     # MOUSE: P.I. For Hire
    None, None,                             # mouse e cadeira
    None, None, None, None,
]

erros = 0
for (padrao, texto), esperado in zip(EXEMPLOS, ESPERADO):
    o = extrair(texto, padrao)
    primeira = texto.splitlines()[0][:60]
    obtido = (o.tipo, o.plataforma, round(o.preco, 2), o.loja) if o else None
    ok = obtido == esperado
    erros += not ok
    if o:
        print(f"{'✅' if ok else '❌'} [{o.tipo}] {o.jogo} | {o.plataforma} | R${o.preco:.2f}"
              f"{f' (de R${o.preco_de:.0f}, -{o.desconto}%)' if o.preco_de else ''}"
              f" | {o.loja} | cupom={o.cupom}" + ("" if ok else f"   (esperado {esperado})"))
    else:
        print(f"{'✅' if ok else '❌'} ignorada: {primeira}" + ("" if ok else f"   (esperado {esperado})"))

# Consumer Games: link do cupom vem antes do link do produto; o preço "FOI 260,28" é de outra vez
o = extrair("""[ Shopee ]  Black Myth Wukong - PS5

NÃO É O SEU MENOR VALOR!! FOI 260,28 à VISTA!! MAS É UMA MÍDIA MUITO DIFÍCIL DE ENCONTRAR EM PROMOÇÃO!!

🔴 RESGATE O CUPOM DE 40 OFF AQUI:
👉 https://s.shopee.com.br/3g4dfcKJh7

COMPRE AQUI:
👉 https://s.shopee.com.br/1qcz3rJSyt
- R$ 286,06 no pix
- Loja Gamer Hut✅""")
obtido = o and (o.jogo, o.plataforma, round(o.preco, 2), o.loja, o.link)
esperado = ("Black Myth Wukong", "PS5", 286.06, "Shopee", "https://s.shopee.com.br/1qcz3rJSyt")
erros += obtido != esperado
print(f"{'✅' if obtido == esperado else '❌'} Consumer Games: {obtido}")

# "FOI R$ 67,31 à vista" é o menor de outra vez; o preço de agora é o do pix
o = extrair("""[ Kabum ] The Last Of Us Part 2 Remastered - PS5

🔴 Cupom: JOGANO5DO5
NÃO É SEU MENOR VALOR!! FOI R$ 67,31 à vista BATIDO APENAS UMA VEZ!!

👉 https://tidd.ly/4c7fgXh
* R$ 134,31 no pix
* Consulte o Frete""")
obtido = o and (o.preco, o.cupom)
erros += obtido != (134.31, "JOGANO5DO5")
print(f"{'✅' if obtido == (134.31, 'JOGANO5DO5') else '❌'} Consumer Games (FOI R$ antigo): {obtido}")

print()
print("Tudo certo." if not erros else f"{erros} exemplo(s) com problema.")
