"""Desenha os prédios que faltavam na cidade e os coloca no mapa do Tiled.

Uso:  python tools/make_buildings.py          (precisa do Pillow: pip install pillow)

Gera em assets/images/buildings/:
    casa_shows.png, barzinho.png, casa_jogador.png, loja.png, feira.png
e, em assets/maps/, um .tsx para cada um. Também acrescenta os prédios à camada de
objetos "Buildings" do cidade.tmx (só na primeira vez; rodar de novo apenas redesenha).

O estilo segue o das casas que já existiam: cores chapadas, sem contorno, telhado com
"tijolinhos" e placas com letras de pixel grande. As fachadas são desenhadas de frente
(porta embaixo); no mapa elas são giradas para a porta ficar virada para a rua do ponto
de interação, como já era feito com as outras casas.
"""

import random
import re
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
IMAGES = ROOT / "assets" / "images" / "buildings"
MAPS = ROOT / "assets" / "maps"
rng = random.Random(42)

# Fonte de pixel 5x7 só com as letras usadas nas placas.
FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    " ": ["00000"] * 7,
}


def pixel_text(draw, text, center, scale, color, shadow=None):
    width = len(text) * 6 * scale - scale
    x0 = round(center[0] - width / 2)
    y0 = round(center[1] - 7 * scale / 2)
    for layer, offset, fill in ((0, scale // 2, shadow), (1, 0, color)):
        if fill is None:
            continue
        for index, char in enumerate(text):
            for row, bits in enumerate(FONT[char]):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        x = x0 + index * 6 * scale + col * scale + offset
                        y = y0 + row * scale + offset
                        draw.rectangle((x, y, x + scale - 1, y + scale - 1), fill=fill)


def brick_roof(draw, width, top, bottom, color, dark, inset=96):
    """Telhado em trapézio com "tijolinhos" (igual às casas existentes)."""
    draw.polygon([(inset, top), (width - inset, top), (width, bottom), (0, bottom)], fill=color)
    for _ in range(width // 9):
        y = rng.randint(top + 6, bottom - 6)
        span = inset * (bottom - y) / (bottom - top)
        x = rng.randint(round(span) + 4, round(width - span) - 20)
        draw.rectangle((x, y, x + rng.choice((10, 12, 14)), y + 4), fill=dark)


def window(draw, box, glass=(95, 205, 228), frame=(104, 45, 24), cross=True):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=frame)
    draw.rectangle((x0 + 6, y0 + 6, x1 - 6, y1 - 6), fill=glass)
    if cross:
        draw.rectangle(((x0 + x1) // 2 - 3, y0 + 6, (x0 + x1) // 2 + 3, y1 - 6), fill=frame)


def door(draw, center_x, bottom, width=64, height=104, color=(85, 60, 43), frame=(143, 86, 59), knob=(251, 242, 54)):
    x0 = center_x - width // 2
    draw.rectangle((x0 - 8, bottom - height - 8, x0 + width + 8, bottom), fill=frame)
    draw.rectangle((x0, bottom - height, x0 + width, bottom), fill=color)
    draw.rectangle((x0 + width - 16, bottom - height // 2, x0 + width - 8, bottom - height // 2 + 8), fill=knob)


# ----------------------------------------------------------------------------- prédios
def casa_de_shows():
    w, h = 704, 416
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, 56), fill=(58, 50, 70))                      # laje
    for x in (40, 600):
        d.rectangle((x, 12, x + 64, 44), fill=(120, 120, 130))           # ar-condicionado
        d.rectangle((x + 8, 20, x + 56, 36), fill=(90, 90, 100))
    d.rectangle((0, 56, w, h), fill=(92, 54, 128))                      # fachada
    for x in range(0, w, 88):
        d.rectangle((x, 56, x + 12, h), fill=(78, 44, 108))              # pilastras
    d.rectangle((0, 56, w, 68), fill=(70, 40, 98))
    # letreiro com lâmpadas
    d.rectangle((112, 92, 592, 208), fill=(36, 28, 48))
    for x in range(124, 592, 20):
        for y in (102, 198):
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 228, 120))
    for y in range(122, 190, 20):
        for x in (124, 580):
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(255, 228, 120))
    pixel_text(d, "CASA DE SHOWS", (352, 150), 5, (247, 203, 107), shadow=(150, 60, 40))
    # cartazes
    for x0, color in ((44, (229, 119, 76)), (580, (99, 196, 131))):
        d.rectangle((x0, 236, x0 + 80, 344), fill=(240, 232, 214))
        d.rectangle((x0 + 8, 244, x0 + 72, 300), fill=color)
        d.ellipse((x0 + 22, 276, x0 + 38, 292), fill=(36, 28, 48))         # nota musical
        d.rectangle((x0 + 34, 252, x0 + 38, 284), fill=(36, 28, 48))
        d.rectangle((x0 + 34, 252, x0 + 54, 258), fill=(36, 28, 48))
        d.rectangle((x0 + 12, 312, x0 + 68, 318), fill=(120, 110, 100))
        d.rectangle((x0 + 12, 326, x0 + 52, 332), fill=(120, 110, 100))
    # bilheteria e portas duplas vermelhas (centro em x=340: a frente do ponto de interação)
    d.rectangle((168, 296, 236, 368), fill=(36, 28, 48))
    d.rectangle((176, 304, 228, 340), fill=(255, 214, 140))
    d.rectangle((176, 346, 228, 352), fill=(120, 80, 60))
    d.rectangle((270, 272, 410, h), fill=(60, 30, 40))
    d.rectangle((278, 280, 338, h), fill=(170, 40, 50))
    d.rectangle((342, 280, 402, h), fill=(170, 40, 50))
    d.rectangle((326, 340, 332, 356), fill=(251, 242, 54))
    d.rectangle((348, 340, 354, 356), fill=(251, 242, 54))
    d.polygon([(250, 272), (430, 272), (410, 244), (270, 244)], fill=(200, 60, 70))  # toldinho
    for x in range(270, 410, 28):
        d.rectangle((x, 244, x + 13, 272), fill=(240, 232, 214))
    return img


def barzinho():
    """Fachada virada para cima (a porta encosta na rua de cima): desenha e espelha na vertical."""
    w, h = 576, 256
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    brick_roof(d, w, 0, 80, (161, 68, 35), (123, 56, 32), inset=80)
    d.rectangle((0, 80, w, 88), fill=(208, 194, 150))
    d.rectangle((0, 88, w, h), fill=(214, 140, 80))                     # parede
    d.rectangle((0, 88, w, 96), fill=(190, 120, 64))
    # toldo listrado verde e branco
    d.rectangle((24, 112, 432, 140), fill=(70, 150, 90))
    for x in range(24, 432, 32):
        d.rectangle((x, 112, x + 15, 140), fill=(240, 232, 214))
    for x in range(24, 432, 16):
        d.polygon([(x, 140), (x + 16, 140), (x + 8, 150)], fill=(70, 150, 90) if (x // 16) % 2 == 0 else (240, 232, 214))
    # vitrines com luz quente e garrafas
    for x0 in (40, 232):
        d.rectangle((x0, 160, x0 + 176, 240), fill=(120, 70, 40))
        d.rectangle((x0 + 8, 168, x0 + 168, 232), fill=(255, 214, 140))
        for bx in range(x0 + 20, x0 + 160, 22):
            d.rectangle((bx, 200, bx + 8, 232), fill=(70, 120, 60) if bx % 3 else (120, 50, 40))
            d.rectangle((bx + 2, 192, bx + 6, 200), fill=(70, 120, 60) if bx % 3 else (120, 50, 40))
        d.rectangle((x0 + 8, 224, x0 + 168, 232), fill=(120, 70, 40))     # balcão
    door(d, 500, h, width=60, height=96, color=(110, 60, 36), frame=(80, 44, 26))
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    d = ImageDraw.Draw(img)
    # letreiro neon sobre o telhado (desenhado depois de espelhar para o texto ficar legível)
    d.rectangle((196, 186, 380, 244), fill=(40, 24, 36))
    d.rectangle((200, 190, 376, 240), fill=(56, 32, 50))
    pixel_text(d, "BAR", (288, 215), 6, (255, 110, 190), shadow=(120, 30, 80))
    return img


def casa_jogador():
    w, h = 256, 224
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    brick_roof(d, w, 0, 84, (170, 68, 33), (132, 62, 25), inset=56)
    d.rectangle((0, 84, w, 92), fill=(255, 242, 228))
    d.rectangle((0, 92, w, h), fill=(110, 168, 206))                    # parede azul
    window(d, (20, 116, 84, 172))
    window(d, (190, 116, 246, 172))
    door(d, 136, h, width=52, height=92, color=(132, 62, 25), frame=(255, 242, 228))
    d.rectangle((92, 196, 106, 224), fill=(160, 90, 60))                # vaso de flores
    for fx, color in ((94, (255, 110, 120)), (100, (255, 220, 90)), (104, (255, 255, 255))):
        d.ellipse((fx - 4, 186, fx + 4, 194), fill=color)
    d.rectangle((20, 184, 84, 196), fill=(97, 142, 30))                 # canteiro
    return img


def loja():
    w, h = 256, 256
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, 44), fill=(70, 74, 82))                        # laje
    d.rectangle((0, 44, w, h), fill=(64, 146, 146))                     # parede verde-água
    d.rectangle((0, 44, w, 52), fill=(50, 120, 120))
    # placa com ícone de camiseta (sem texto: o prédio fica girado no mapa)
    d.rectangle((88, 58, 168, 104), fill=(240, 232, 214))
    d.polygon([(110, 66), (146, 66), (158, 76), (150, 84), (144, 80), (144, 98), (112, 98), (112, 80),
               (106, 84), (98, 76)], fill=(229, 119, 76))
    # toldo listrado
    d.rectangle((8, 112, 248, 134), fill=(200, 60, 70))
    for x in range(8, 248, 24):
        d.rectangle((x, 112, x + 11, 134), fill=(240, 232, 214))
    # vitrines com cabide, camisa e chapéu
    for x0 in (12, 156):
        d.rectangle((x0, 148, x0 + 88, 238), fill=(50, 120, 120))
        d.rectangle((x0 + 6, 154, x0 + 82, 232), fill=(190, 230, 235))
        d.rectangle((x0 + 20, 166, x0 + 68, 168), fill=(120, 110, 100))
        d.polygon([(x0 + 30, 172), (x0 + 58, 172), (x0 + 66, 180), (x0 + 60, 186), (x0 + 56, 184), (x0 + 56, 214),
                   (x0 + 32, 214), (x0 + 32, 184), (x0 + 28, 186), (x0 + 22, 180)],
                  fill=(92, 54, 128) if x0 < 100 else (229, 119, 76))
        d.rectangle((x0 + 30, 222, x0 + 58, 226), fill=(60, 50, 40))
    door(d, 124, h, width=44, height=96, color=(170, 215, 225), frame=(50, 120, 120), knob=(80, 80, 80))
    return img


def feira():
    """Praça vista de cima: barracas, palco, bandeirolas e a placa da feira (entrada à esquerda)."""
    w, h = 576, 288
    img = Image.new("RGBA", (w, h), (205, 190, 160, 255))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 32):                                           # piso de pedra
        for y in range(0, h, 32):
            if (x // 32 + y // 32) % 2:
                d.rectangle((x, y, x + 31, y + 31), fill=(196, 180, 150))
    for y0 in (0, h - 12):                                              # grade em cima e embaixo
        d.rectangle((0, y0, w, y0 + 12), fill=(110, 80, 56))
        for x in range(4, w, 16):
            d.rectangle((x, y0 + 2, x + 6, y0 + 10), fill=(150, 112, 76))
    d.rectangle((w - 12, 0, w, h), fill=(110, 80, 56))
    # placa
    d.rectangle((24, 22, 380, 70), fill=(36, 28, 48))
    pixel_text(d, "FEIRA MUSICAL", (202, 46), 4, (247, 203, 107), shadow=(150, 60, 40))
    # bandeirolas
    colors = [(229, 119, 76), (99, 196, 131), (104, 185, 224), (247, 203, 107), (181, 132, 230)]
    for row, y in enumerate((84, 268)):
        d.line((0, y, w - 12, y - 4), fill=(80, 60, 40), width=2)
        for index, x in enumerate(range(8, w - 24, 22)):
            d.polygon([(x, y), (x + 14, y), (x + 7, y + (12 if row == 0 else -12))], fill=colors[index % 5])
    # barracas (lonas listradas vistas de cima)
    for x0, y0, color in ((40, 104, (200, 60, 70)), (176, 104, (60, 110, 180)), (40, 184, (230, 170, 50)),
                          (176, 184, (99, 160, 100))):
        d.rectangle((x0 + 6, y0 + 6, x0 + 118, y0 + 70), fill=(150, 135, 110))   # sombra
        d.rectangle((x0, y0, x0 + 112, y0 + 64), fill=color)
        for x in range(x0, x0 + 112, 16):
            d.rectangle((x, y0, x + 7, y0 + 64), fill=(240, 232, 214))
        d.rectangle((x0, y0 + 28, x0 + 112, y0 + 36), fill=tuple(max(0, c - 40) for c in color))
    # palco com caixas de som e luzes
    d.rectangle((336, 96, 556, 260), fill=(110, 75, 50))
    for y in range(100, 260, 14):
        d.line((340, y, 552, y), fill=(95, 64, 42), width=2)
    for x0 in (344, 516):
        d.rectangle((x0, 104, x0 + 32, 140), fill=(24, 24, 28))
        d.ellipse((x0 + 6, 110, x0 + 26, 130), fill=(70, 70, 80))
    d.rectangle((436, 170, 442, 200), fill=(40, 40, 44))                  # pedestal do microfone
    d.ellipse((432, 160, 446, 174), fill=(60, 60, 66))
    for x, color in ((380, (255, 110, 190)), (440, (247, 203, 107)), (500, (104, 185, 224))):
        d.ellipse((x - 18, 214, x + 18, 250), fill=color + (255,))
    # notas musicais pintadas no chão
    for x, y in ((300, 140), (300, 230)):
        d.ellipse((x - 10, y + 10, x + 6, y + 22), fill=(181, 132, 230))
        d.rectangle((x + 2, y - 10, x + 6, y + 16), fill=(181, 132, 230))
        d.rectangle((x + 2, y - 10, x + 16, y - 4), fill=(181, 132, 230))
    return img


# Nome, função de desenho e posição no mapa. Para objetos de tile do Tiled, (x, y) é o canto
# inferior esquerdo da imagem; com rotation=90 a fachada gira no sentido horário e a porta
# (embaixo na imagem) fica virada para a esquerda.
BUILDINGS = (
    ("casa_shows", casa_de_shows, dict(x=160, y=544)),
    ("barzinho", barzinho, dict(x=0, y=1600)),
    ("casa_jogador", casa_jogador, dict(x=704, y=1664, rotation=90)),
    ("loja", loja, dict(x=1344, y=1376, rotation=90)),
    ("feira", feira, dict(x=1984, y=960)),
)


def update_map(sizes):
    tmx = MAPS / "cidade.tmx"
    text = tmx.read_text(encoding="utf-8")
    if 'source="casa_shows.tsx"' in text:
        print("cidade.tmx já tem os prédios novos; só as imagens foram redesenhadas.")
        return
    first = max(int(g) for g in re.findall(r'<tileset firstgid="(\d+)"', text)) + 1
    next_id = int(re.search(r'nextobjectid="(\d+)"', text).group(1))
    tilesets, objects = [], []
    for index, (name, _, place) in enumerate(BUILDINGS):
        width, height = sizes[name]
        gid = first + index
        tilesets.append(f' <tileset firstgid="{gid}" source="{name}.tsx"/>')
        rotation = f' rotation="{place["rotation"]}"' if place.get("rotation") else ""
        objects.append(f'  <object id="{next_id + index}" name="{name}" gid="{gid}" x="{place["x"]}" '
                       f'y="{place["y"]}" width="{width}" height="{height}"{rotation}/>')
    last_tileset = list(re.finditer(r' <tileset firstgid="\d+" source="[^"]+"/>', text))[-1]
    text = text[:last_tileset.end()] + "\n" + "\n".join(tilesets) + text[last_tileset.end():]
    group = re.search(r'<objectgroup id="\d+" name="Buildings">.*?</objectgroup>', text, re.S)
    closing = text.rfind("\n", 0, group.end() - len("</objectgroup>")) + 1  # início da linha do fechamento
    text = text[:closing] + "\n".join(objects) + "\n" + text[closing:]
    text = re.sub(r'nextobjectid="\d+"', f'nextobjectid="{next_id + len(BUILDINGS)}"', text, count=1)
    tmx.write_text(text, encoding="utf-8")
    print(f"cidade.tmx: {len(BUILDINGS)} prédios adicionados (gids {first}-{first + len(BUILDINGS) - 1}).")


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for name, draw, _ in BUILDINGS:
        image = draw()
        image.save(IMAGES / f"{name}.png")
        sizes[name] = image.size
        (MAPS / f"{name}.tsx").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<tileset version="1.10" tiledversion="1.12.2" name="{name}" tilewidth="{image.width}" '
            f'tileheight="{image.height}" tilecount="1" columns="1">\n'
            f' <image source="../images/buildings/{name}.png" width="{image.width}" height="{image.height}"/>\n'
            '</tileset>\n', encoding="utf-8")
        print(f"{name}.png {image.size}")
    update_map(sizes)


if __name__ == "__main__":
    main()
