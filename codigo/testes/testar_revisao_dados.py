"""
Casos reais achados na revisão dos dados (nov/2026): valor de cupom lido como preço, loja digital,
console que parecia acessório e post de promoção genérica.
Uso: python codigo/testes/testar_revisao_dados.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # módulos de codigo/
from extrator import classificar, extrair  # noqa: E402

PRECOS = [
    # (mensagem, preço esperado)
    ("""[ Shopee ] Coffee Talk Tokyo - Nintendo switch 2
🔴 RESGATE O CUPOM DE R$ 20 E R$ 40 OFF AQUI:
👉 https://s.shopee.com.br/1qcoJS86Vc
* R$ 303,98 no pix
* R$ 319,97 em até 5x SEM JUROS""", 303.98),
    ("""[ Shopee ] Pré-Venda Marvel's Wolverine - PS5
🔴 Cupom: MEI0D0AN050AF
R$ 50 OFF em R$ 149
RESGATE AQUI: 👉 https://s.shopee.com.br/9AM2zelw5E
COMPRE AQUI:
👉 https://s.shopee.com.br/902d31z3EK
* R$ 329,91 no pix""", 329.91),
    ("""Animal Crossing New Horizons - Nintendo Switch - (Shopee)
Resgate aqui o cupom de R$ 30 ou R$ 40 OFF
👉 https://s.shopee.com.br/W4Dbe5cF8
NS1 👉 https://s.shopee.com.br/6fdtUUXxiZ
R$ 268,89 no PIX""", 268.89),
    ("""Grand Theft Auto V - PS5/PS4 - (Shopee)
Resgate aqui o cupom de 20% ou R$ 30 OFF
👉 https://s.shopee.com.br/W4Dbe5cF8
PS5 👉 https://s.shopee.com.br/2g8rCfnFKb
R$ 132,90 no PIX""", 132.90),
    ("""Battlefield 6 - PlayStation 5 - (KaBum!)
👉 https://desconto.games/fadSw5c
🏷 Cupom: PETECOPETECO
R$ 65,67 à vista""", 65.67),
    ("""Controle preciso e sem fio
[SHOPEE] Controle DualSense Edge Sem Fio - Midnight Black
De: R$ 1.117,89
Por: R$ 899,46 no Pix""", 899.46),
    ("""Assassin’s Creed: The Ezio Collection - PS4

💰 R$ 129,97

Incluí 3 jogos: Assassin's Creed II + Brotherhood + Revelations
(Cada Jogo Saí por R$43,32)

🔗 Link: https://link.amazon/B0c2qm8b4
[AMAZON]""", 129.97),
]
IGNORADAS = [
    # comentário com "R$100 mais caro" e sem preço da oferta
    """[Mídia Física] Zelda Ocarina of Time (capa foil) via Amazon🇧🇷
Tem um loja vendendo dentro do marktplace da Amazon um Zelda Ocarina em capa foil, mas jogaram o preço R$100 conto mais caro. Acesse https://link.amazon/B09INUXRm""",
    # loja digital
    """Resident Evil 2 Remake - PS4/PS5
💰R$ 39,90
🔗Link: https://store.playstation.com/pt-br/product/UP0102-PPSA04288_00-BH2R000000000001
[PLAYSTATION STORE]""",
]
CLASSES = [
    ("PlayStation 5 Pro SSD 2TB", "descartar"),
    ("Console PlayStation 5 Pro 2TB SSD", "descartar"),
    ("Bundle Console Nintendo Switch 2 + Cartão microSD Express 256 GB", "descartar"),
    ("Franquia God of War", "descartar"),
    ("Games Pokémon em promo", "descartar"),
    ("Promoção Jogos Digitais Nintendo Switch", "descartar"),
    ("Jogos Mortal Kombat em oferta", "descartar"),
    ("Tampas do console PlayStation 5 Slim - Coleção Hyperpop", "acessorio"),
    ("Cartão Samsung microSD 256GB Express para Nintendo Switch 2", "acessorio"),
    ("Jogos Vorazes", "jogo"),                      # não confunde com post de promoção
    ("God of War Ragnarök", "jogo"),
]

erros = 0
for texto, esperado in PRECOS:
    o = extrair(texto)
    obtido = round(o.preco, 2) if o else None
    erros += obtido != esperado
    print(("✅" if obtido == esperado else "❌"), f"preço {obtido} (esperado {esperado}):", texto.splitlines()[0][:60])
for texto in IGNORADAS:
    o = extrair(texto)
    erros += o is not None
    print(("✅" if o is None else "❌"), "ignorada:", texto.splitlines()[0][:60], "" if o is None else f"-> {o.preco}")
for titulo, esperado in CLASSES:
    obtido = classificar(titulo)
    erros += obtido != esperado
    print(("✅" if obtido == esperado else "❌"), f"{obtido} (esperado {esperado}):", titulo)
print("\nTudo certo." if not erros else f"\n{erros} caso(s) com problema.")
