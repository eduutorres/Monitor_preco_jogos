"""
Testa a leitura do Deku Deals com páginas de exemplo (sem internet).
Uso: python codigo/testes/testar_deku.py
Para testar de verdade com a internet: python codigo/testes/testar_deku.py "Astro Bot" PS5
"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))   # módulos de codigo/
import sys

import deku

VARIAS_PLATAFORMAS = """
<h4>Current prices</h4>
<table>
<tr><td><a href="#">PlayStation Store</a></td><td><a href="#">PS4 Digital</a></td>
    <td><a href="#"><span>R$41,58</span><span>-80%</span></a><div>Sale ends October 22</div></td></tr>
<tr><td><a href="#">Nintendo eShop</a></td><td><a href="#">Switch Digital</a></td>
    <td><a href="#"><span>R$49,99</span><span>-80%</span></a><div>Matches previous low</div></td></tr>
<tr><td><a>Steam</a></td><td><a>Steam Digital</a></td><td><a>R$119,00</a></td></tr>
<tr><td><a>Microsoft Store</a></td><td><a>Xbox One Digital</a></td><td><a>R$207,90</a></td></tr>
</table>
<h3>Price history</h3>
<table><tr><th>All time low</th><th></th></tr>
<tr><td>PS4</td><td>R$41,58</td><td>(-80%)</td></tr>
<tr><td>Switch</td><td>R$49,99</td><td>(-80%)</td></tr>
<tr><td>Steam</td><td>R$17,85</td><td>(-85%)</td></tr>
<tr><td>Xbox One</td><td>R$41,58</td><td>(-80%)</td></tr>
</table><div>dekudeals.com</div><div>Time range</div>
<ul><li><strong>MSRP:</strong> R$249,95</li></ul>
"""

UMA_PLATAFORMA = """
<h4>Current prices</h4>
<ul><li><a href="x">PlayStation Store</a> <a href="x">PS5 Digital</a> <a href="x">R$339,90</a></li></ul>
<h3>Price history</h3>
<table><tr><th><strong>All time low</strong></th><th></th></tr>
<tr><td>R$224,33</td><td>(-34%)</td></tr></table><div>Time range</div>
<ul><li><strong>MSRP:</strong> R$339,90</li></ul>
"""

SWITCH2 = """
<h4>Current prices</h4>
<ul><li><a>Nintendo eShop</a> <a>Switch 2 Digital</a> <a>R$1.299,90</a></li></ul>
<table><tr><th>All time low</th></tr><tr><td>R$1.099,90</td><td>(-15%)</td></tr></table>
"""

COMBINADO = """
<h4>Current prices</h4>
<ul><li><a>PlayStation Store</a> <a>PS5 / PS4 Digital</a> <a>R$74,85</a><span>-70%</span></li>
<li><a>Nintendo eShop</a> <a>Switch 2 Digital</a> <a>R$259,90</a></li>
<li><a>Nintendo eShop</a> <a>Switch Digital</a> <a>R$259,90</a></li>
<li><a>Microsoft Store</a> <a>Xbox X|S / Xbox One Digital</a> <a>R$259,90</a></li></ul>
<h3>Price history</h3>
<table><tr><th>All time low</th></tr>
<tr><td>PS5 / PS4</td><td>R$74,85</td><td>(-70%)</td></tr>
<tr><td>Switch 2</td><td>R$90,96</td><td>(-65%)</td></tr>
<tr><td>Switch</td><td>R$90,96</td><td>(-65%)</td></tr>
<tr><td>Xbox X|S / Xbox One</td><td>R$77,97</td><td>(-70%)</td></tr>
</table><div>dekudeals.com</div>
"""

BUSCA = """<a href="/items/astro-bot">ASTRO BOT</a><a href="/items/astro-bot-rescue-mission">x</a>
<a href="/items/astro-bot">ASTRO BOT</a>"""

erros = 0


def confere(nome, obtido, esperado):
    global erros
    ok = obtido == esperado
    erros += not ok
    print(("✅" if ok else "❌"), nome, "→", obtido, "" if ok else f"(esperado {esperado})")


confere("PS4 numa página com várias", deku.ler_pagina(VARIAS_PLATAFORMAS, "PS4"),
        {"preco_atual": 41.58, "menor_preco": 41.58, "msrp": 249.95})
confere("Switch numa página com várias", deku.ler_pagina(VARIAS_PLATAFORMAS, "Switch"),
        {"preco_atual": 49.99, "menor_preco": 49.99, "msrp": 249.95})
confere("PS5 não existe nessa página", deku.ler_pagina(VARIAS_PLATAFORMAS, "PS5"), None)
confere("Página de uma plataforma só", deku.ler_pagina(UMA_PLATAFORMA, "PS5"),
        {"preco_atual": 339.90, "menor_preco": 224.33, "msrp": 339.90})
confere("Switch 2 não confunde com Switch", deku.ler_pagina(SWITCH2, "Switch"), None)
confere("PS5 em rótulo combinado 'PS5 / PS4'", deku.ler_pagina(COMBINADO, "PS5"),
        {"preco_atual": 74.85, "menor_preco": 74.85, "msrp": None})
confere("PS4 em rótulo combinado 'PS5 / PS4'", deku.ler_pagina(COMBINADO, "PS4"),
        {"preco_atual": 74.85, "menor_preco": 74.85, "msrp": None})
confere("Switch 2 ao lado de rótulo combinado", deku.ler_pagina(COMBINADO, "Switch 2"),
        {"preco_atual": 259.90, "menor_preco": 90.96, "msrp": None})
confere("Xbox Series em 'Xbox X|S / Xbox One'", deku.ler_pagina(COMBINADO, "Xbox Series"),
        {"preco_atual": 259.90, "menor_preco": 77.97, "msrp": None})
confere("Switch 2 com milhar", deku.ler_pagina(SWITCH2, "Switch 2"),
        {"preco_atual": 1299.90, "menor_preco": 1099.90, "msrp": None})
confere("Busca", deku.ler_busca(BUSCA), [("astro-bot", "astro bot"), ("astro-bot-rescue-mission", "astro bot rescue mission")])
confere("Slug", deku.slugify("Pokémon Legends: Z-A"), "pokemon-legends-z-a")
confere("Link colado", deku.slug_de_url("https://www.dekudeals.com/items/astro-bot?country=br"), "astro-bot")

# fluxo completo com "internet" falsa
def falso(caminho, params):
    return BUSCA if caminho == "/search" else (UMA_PLATAFORMA if caminho == "/items/astro-bot" else "")
url, dados, erro = deku.consultar("ASTRO BOT", "astro bot", "PS5", baixar=falso)
confere("Consulta completa", (url, dados and dados["menor_preco"], erro),
        ("https://www.dekudeals.com/items/astro-bot", 224.33, None))

v = deku.veredito(199.0, 199.0, {"preco_atual": 339.90, "menor_preco": 224.33})
confere("Veredito físico", v["tipo"], "fisico")
print("  ", v["texto"])
v = deku.veredito(260.0, 240.0, {"preco_atual": 339.90, "menor_preco": 224.33})
confere("Veredito físico hoje", v["tipo"], "fisico_hoje")
print("  ", v["texto"])
v = deku.veredito(300.0, 250.0, {"preco_atual": 249.90, "menor_preco": 199.90})
confere("Veredito digital", v["tipo"], "digital")
print("  ", v["texto"])

if len(sys.argv) >= 2:
    print("\nConsultando o Deku Deals de verdade...")
    nome, plat = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    from extrator import normalizar_nome
    print(deku.consultar(nome, normalizar_nome(nome), plat))

sys.exit(1 if erros else 0)
