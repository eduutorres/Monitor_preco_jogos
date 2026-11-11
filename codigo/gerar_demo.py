"""
Cria um banco de demonstração (demo.db) com 6 meses de ofertas fictícias,
para você ver o painel antes de o monitor juntar dados reais.
Uso:  python gerar_demo.py   e depois   python api.py --demo
"""
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import shutil

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from raiz import RAIZ
import banco
import deku
from extrator import Oferta, normalizar_nome

CAMINHO = RAIZ / "demo.db"
CAPAS = RAIZ / "capas_demo"
FAIXA = {"Switch": (230, 0, 18), "Switch 2": (230, 0, 18), "PS5": (0, 70, 160),
         "PS4": (0, 55, 145), "Xbox Series": (16, 124, 16)}
PALETAS = [((32, 46, 92), (240, 120, 60)), ((20, 90, 80), (250, 210, 90)),
           ((70, 30, 90), (240, 90, 140)), ((15, 30, 40), (90, 200, 230)),
           ((110, 40, 30), (250, 180, 80)), ((30, 60, 30), (190, 230, 120))]


def fonte(tam):
    for nome in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(nome, tam)
        except OSError:
            pass
    return ImageFont.load_default(size=tam)


def capa_ficticia(nome, plataforma, semente):
    """Arte abstrata no formato de uma caixa de jogo (só para a demonstração)."""
    rnd = random.Random(semente)
    w, h = 420, 600 if plataforma in ("Switch", "Switch 2") else 520
    a, b = rnd.choice(PALETAS)
    img = Image.new("RGB", (w, h), a)
    d = ImageDraw.Draw(img)
    for y in range(h):                                   # degradê
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(a[i] * (1 - t) + b[i] * t * 0.55) for i in range(3)))
    for _ in range(7):                                   # formas
        r = rnd.randint(40, 180)
        x, y = rnd.randint(-60, w), rnd.randint(40, h)
        cor = tuple(min(255, int(c * rnd.uniform(0.7, 1.15))) for c in b)
        d.ellipse([x - r, y - r, x + r, y + r], fill=cor + (0,))
    img = img.filter(ImageFilter.GaussianBlur(18))
    d = ImageDraw.Draw(img)
    faixa = 54
    d.rectangle([0, 0, w, faixa], fill=FAIXA.get(plataforma, (60, 60, 60)) if "Switch" in (plataforma or "") else (250, 250, 250))
    d.text((18, faixa / 2), plataforma or "", font=fonte(24), anchor="lm",
           fill=(255, 255, 255) if "Switch" in (plataforma or "") else FAIXA.get(plataforma, (30, 30, 30)))
    palavras, linhas, atual = nome.upper().split(), [], ""
    for p in palavras:
        if len(atual + " " + p) > 14 and atual:
            linhas.append(atual); atual = p
        else:
            atual = (atual + " " + p).strip()
    linhas.append(atual)
    f = fonte(40)
    y0 = h - 40 - 46 * len(linhas)
    for i, l in enumerate(linhas):
        d.text((w / 2 + 2, y0 + i * 46 + 2), l, font=f, anchor="mt", fill=(0, 0, 0))
        d.text((w / 2, y0 + i * 46), l, font=f, anchor="mt", fill=(255, 255, 255))
    return img


LOJAS = ["Amazon", "Mercado Livre", "Magalu", "KaBuM!", "Gamer Hut", "Americanas"]
JOGOS = [  # nome, plataforma, preço cheio, preço "normal" de promo
    ("Zelda Tears of the Kingdom", "Switch", 399, 320),
    ("The Legend of Zelda: Ocarina of Time Remake", "Switch 2", 449, 390),
    ("Mario Kart World", "Switch 2", 499, 410),
    ("Donkey Kong Bananza", "Switch 2", 449, 380),
    ("Super Mario Bros. Wonder", "Switch", 349, 260),
    ("Metroid Prime 4 Beyond", "Switch 2", 449, 370),
    ("Pokémon Legends Z-A", "Switch", 349, 290),
    ("Street Fighter 6 Years 1-2 Fighters Edition", "PS5", 299, 190),
    ("Pragmata", "PS5", 349, 260),
    ("Ghost of Yotei", "PS5", 349, 290),
    ("Astro Bot", "PS5", 299, 210),
    ("Death Stranding 2", "PS5", 349, 250),
    ("Elden Ring", "PS5", 249, 160),
    ("Final Fantasy VII Rebirth", "PS5", 299, 170),
    ("Resident Evil Requiem", "PS5", 349, 300),
    ("Hollow Knight Silksong", "Switch", 199, 160),
    ("Forza Horizon 5", "Xbox Series", 249, 150),
    ("God of War Ragnarök", "PS4", 199, 120),
]


def main():
    if CAMINHO.exists():
        os.remove(CAMINHO)
    db = banco.conectar(str(CAMINHO))
    shutil.rmtree(CAPAS, ignore_errors=True)
    CAPAS.mkdir()
    random.seed(7)
    agora = datetime.now(timezone.utc)
    msg_id = 1
    for nome, plat, cheio, normal in JOGOS:
        n = random.randint(4, 16)
        datas = sorted(agora - timedelta(days=random.uniform(0, 180), hours=random.uniform(0, 23))
                       for _ in range(n))
        for i, data in enumerate(datas):
            preco = round(normal * random.uniform(0.85, 1.12))
            if random.random() < 0.12:                      # promoções relâmpago
                preco = round(normal * random.uniform(0.62, 0.78))
            if i == n - 1 and random.random() < 0.35:       # alguns estão no menor preço agora
                preco = round(normal * 0.66)
            o = Oferta(jogo=nome, chave=normalizar_nome(nome), plataforma=plat,
                       preco=float(preco) - 0.10 * random.choice([0, 0, 1]),
                       preco_de=float(cheio) if random.random() < 0.6 else None,
                       loja=random.choice(LOJAS),
                       cupom=random.choice([None, None, "OFERTAHOJE", "MELI10"]),
                       pix=random.random() < 0.4, frete_gratis=random.random() < 0.6,
                       link="https://exemplo.com/oferta")
            banco.registrar_oferta(db, o, -1001, msg_id, data, f"https://t.me/canal/{msg_id}")
            msg_id += 1
        if nome not in ("Hollow Knight Silksong", "Pragmata"):   # dois sem capa, p/ ver o modelo
            jogo_id = banco.obter_ou_criar_jogo(db, o)
            capa_ficticia(nome, plat, nome).save(CAPAS / f"{jogo_id}.jpg", quality=85)
            banco.definir_capa(db, jogo_id, f"{jogo_id}.jpg")
    # preços digitais fictícios (no uso real vêm do Deku Deals)
    rnd = random.Random(3)
    for j in db.execute("SELECT * FROM jogos").fetchall():
        cheio = next(c for n, _, c, _ in JOGOS if n == j["nome"])
        if j["nome"] == "Pragmata":
            deku.salvar(db, j["id"], None, None, "Não achei este jogo no Deku Deals. Cole o link da página dele no painel.")
            continue
        atual = round(cheio * rnd.choice([1, 1, 0.75, 0.6]) - 0.1, 2)
        deku.salvar(db, j["id"], "https://www.dekudeals.com/items/" + deku.slugify(j["nome"]),
                    {"preco_atual": atual, "menor_preco": round(min(atual, cheio * rnd.uniform(0.45, 0.8)), 2),
                     "msrp": float(cheio)}, None)
    banco.adicionar_desejo(db, "Mario Kart World", normalizar_nome("Mario Kart World"), "Switch 2", 380)
    banco.adicionar_desejo(db, "Elden Ring", normalizar_nome("Elden Ring"), "PS5", 120)
    banco.adicionar_desejo(db, "Ghost of Yotei", normalizar_nome("Ghost of Yotei"), None, 200)
    print(f"✅ {CAMINHO.name} criado. Agora rode:  python api.py --demo")


if __name__ == "__main__":
    main()
