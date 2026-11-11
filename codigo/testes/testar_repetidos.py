"""Testa quando dois nomes são o mesmo jogo (pares reais dos canais). Uso: python codigo/testes/testar_repetidos.py"""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))   # módulos de codigo/
from semelhanca import mesmo_jogo

IGUAIS = [
    ("Ratchet & Clank", "Ratchet and Clank"),
    ("Zelda Tears of the Kingdom", "Legend Of Zelda Tears Of The Kingdom"),
    ("Metroid Prime 4 Beyond (nacional)", "Metroid Prime 4: Beyond"),
    ("Animal Crossing: New Horizons NS2 (nacional)", "Animal Crossing: New Horizons"),
    ("Captain Toad: Treasure Tracker", "Captain Toad: Treasure Tracker (Japonês)"),
    ("Clair Obscur Expedition 33", "Clair Obscur: Expedition 33 Europeu"),
    ("Assassin's Creed Black Flag", "Assassin's Creed Black Flag Resynced"),
    ("Tomb Raider I-III", "Tomb Raider I-III Remastered"),
    ("Sillent Hill: Townfall", "Silent Hill Townfall Day One Edition"),
    ("Skull and Bones", "Skull e Bones"),
    ("Final Fantasy VII Rebirth", "Final Fantasy VII Rebirth Day One"),
    ("Call Of Duty: Modern Warfare 3", "Call Of Duty: Modern Warfare 3 Activision"),
    ("Silksong", "Silksong em mídia física"),
    ("Marvel Tokon: Fighting Souls", "Marvel Tokon: Fighting Souls liberada"),
    ("Ghost of Tsushima", "Ghost Of Tsushima Edição Padrão"),
    ("Cyberpunk 2077 Ultimate Edition", "Cyberpunk 2077 Ultimate Edition + Brindes"),
    ("Super Mario Galaxy 1 + 2", "Super Mario Galaxy 1 + 2 nacional"),
    ("Ratchet & Clank Hits", "Ratchet & Clank"),
    ("Ace Combat 8 Wings Of Theve", "Ace Combat 8 Wings Of Theve PS5/XBOX SX"),
    ("Sonic Racing CrossWorlds", "Sonic Racing CrossWorlds Launch Edition"),
    ("Final Fantasy X-X2 HD", "Final Fantasy X-X2 HD Remaster"),
    ("Pokémon Scarlet Violet", "Pokémon Scarlet | Pokémon Violet"),
    ("Steelbook Control Resonant", "Steelbook Control Resonant liberado"),
    ("The Last of Us Part 2 Remastered", "The Last of Us Part II Remastered"),
    ("The Last Of Us Part I", "The Last of Us Part 1"),
    ("Grand Theft Auto V", "Grand Theft Auto 5"),
    ("Final Fantasy VII Rebirth", "Final Fantasy 7 Rebirth"),
    ("Kingdom Hearts Collection I ~ III", "Kingdom Hearts Collection 1-3"),
    ("I Am Setsuna", "I Am Setsuna (nacional)"),
]
DIFERENTES = [
    ("Puyo Puyo Tetris", "Puyo Puyo Tetris 2S"),
    ("Resident Evil 4", "Resident Evil 4 Gold Edition"),
    ("Elden Ring Nightreign", "Elden Ring Nightreign Seekers Edition"),
    ("Fatal Fury City Of The Wolves", "Fatal Fury City of the Wolves Special Edition"),
    ("Hollow Knight + Brindes", "Hollow Knight Silksong + Brindes"),
    ("Mega Man Legacy Collection", "Mega Man Star Force Legacy Collection"),
    ("Final Fantasy VII Rebirth", "Final Fantasy VII Remake E Rebirth"),
    ("Robocop Rogue City Collection", "Robocop Rogue City Collection (Steelbook)"),
    ("Tomb Raider IV-VI Remastered", "Edição Deluxe de Tomb Raider IV-VI Remastered"),
    ("Street Fighter 5", "Street Fighter 6"),
    ("Marvel Cosmic Invasion", "Marvel Cosmic Invasion Deluxe Edition"),
    ("Final Fantasy VII Rebirth", "Final Fantasy XVI"),
    ("Mario Kart 8 Deluxe", "Mario Kart World"),
    ("Shin Megami Tensei V", "Shin Megami Tensei V: Vengeance"),
    ("Hollow Knight", "Hollow Knight Silksong"),
    ("Dragon Quest II", "Dragon Quest III"),
    ("The Last of Us Part 2", "The Last of Us Part I"),
    ("Final Fantasy X", "Final Fantasy 9"),
]
ACESSORIOS_DIFERENTES = [
    ("Controle sem fio DualSense", "Controle DualSense Sem Fio - Cosmic Red"),
    ("Controle Sem Fio Dualsense - Techno Red", "Controle DualSense Sem Fio - Cosmic Red"),
]

erros = 0
for a, b in IGUAIS:
    ok = mesmo_jogo(a, b)
    erros += not ok
    print(("✅" if ok else "❌"), "iguais:", a, "|", b)
for a, b in DIFERENTES:
    ok = not mesmo_jogo(a, b)
    erros += not ok
    print(("✅" if ok else "❌"), "diferentes:", a, "|", b)
for a, b in ACESSORIOS_DIFERENTES:
    ok = not mesmo_jogo(a, b, acessorio=True)
    erros += not ok
    print(("✅" if ok else "❌"), "acessórios diferentes:", a, "|", b)
print("\nTudo certo." if not erros else f"\n{erros} caso(s) com problema.")
