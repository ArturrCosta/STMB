"""Elementos visuais reaproveitáveis: fontes, textos com sombra, painéis, barras e ícones.

A fonte é a Poppins (assets/fonts, licença SIL OFL 1.1), bem mais legível que a
fonte padrão do pygame. Se o arquivo faltar, o erro vai para logs/error.log e o
jogo usa a fonte padrão.
"""

import logging
import math
from pathlib import Path

import pygame

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# Paleta da interface.
INK = (240, 244, 246)
MUTED = (168, 182, 191)
GOLD = (247, 203, 107)
GREEN = (124, 217, 169)
RED = (255, 123, 105)
ORANGE = (255, 170, 102)
BLUE = (120, 190, 240)
PURPLE = (176, 150, 240)
PANEL = (16, 22, 28, 228)
PANEL_BORDER = (64, 80, 92)

_font_warned = False


def load_font(weight, size):
    """Poppins no peso pedido (Regular, Medium, Bold); fonte padrão se não encontrar."""
    global _font_warned
    path = FONT_DIR / f"Poppins-{weight}.ttf"
    try:
        return pygame.font.Font(str(path), size)
    except (OSError, pygame.error) as error:
        if not _font_warned:
            logging.error("Fonte %s indisponível, usando a padrão: %s", path.name, error)
            _font_warned = True
        return pygame.font.Font(None, int(size * 1.45))


def money(value):
    """R$ 1.250 (separador de milhar brasileiro)."""
    sign = "-" if value < 0 else ""
    return f"{sign}R$ {abs(int(value)):,}".replace(",", ".")


def text(screen, content, font, color, shadow=False, **anchor):
    """Desenha texto ancorado (topleft=, center=, midleft=, midright=, topright=...)."""
    image = font.render(str(content), True, color)
    rect = image.get_rect()
    if anchor:
        (name, value), = anchor.items()
        setattr(rect, name, value)
    if shadow:
        shade = font.render(str(content), True, (8, 10, 12))
        screen.blit(shade, rect.move(1, 2))
    screen.blit(image, rect)
    return rect


def wrap(content, font, max_width):
    """Quebra o texto em linhas que cabem em `max_width` pixels."""
    lines, current = [], ""
    for word in str(content).split():
        candidate = f"{current} {word}".strip()
        if current and font.size(candidate)[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def panel(screen, rect, fill=PANEL, border=PANEL_BORDER, radius=12, width=1):
    """Retângulo arredondado semitransparente (com cantos realmente arredondados)."""
    rect = pygame.Rect(rect)
    surface = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(surface, fill, surface.get_rect(), border_radius=radius)
    screen.blit(surface, rect.topleft)
    if border is not None and width:
        pygame.draw.rect(screen, border, rect, width, border_radius=radius)
    return rect


def bar(screen, rect, ratio, color, back=(40, 50, 58), radius=None):
    rect = pygame.Rect(rect)
    radius = rect.height // 2 if radius is None else radius
    pygame.draw.rect(screen, back, rect, border_radius=radius)
    fill = round(rect.width * max(0.0, min(1.0, ratio)))
    if fill > 0:
        pygame.draw.rect(screen, color, (rect.x, rect.y, max(fill, min(rect.width, radius * 2)), rect.height),
                         border_radius=radius)
    return rect


def chip(screen, font, content, color, topleft=None, right=None, y=None):
    """Etiqueta arredondada com bolinha colorida. Use `topleft` ou (`right`, `y`)."""
    label = font.render(content, True, INK)
    width, height = label.get_width() + 34, label.get_height() + 8
    rect = pygame.Rect(0, 0, width, height)
    if topleft is not None:
        rect.topleft = topleft
    else:
        rect.topright = (right, y)
    panel(screen, rect, fill=(16, 22, 28, 220), border=color, radius=height // 2)
    pygame.draw.circle(screen, color, (rect.x + 14, rect.centery), 5)
    screen.blit(label, (rect.x + 25, rect.y + 4))
    return rect


def coin(screen, center, radius=11):
    x, y = center
    pygame.draw.circle(screen, (196, 150, 50), (x, y + 1), radius)
    pygame.draw.circle(screen, (247, 203, 107), (x, y), radius)
    pygame.draw.circle(screen, (255, 230, 160), (x, y), radius - 3, 2)


def sky_icon(screen, center, hour, radius=16):
    """Sol de dia, lua à noite (com a cor do céu daquele horário por trás)."""
    x, y = center
    if 6 <= hour < 18:
        pygame.draw.circle(screen, (255, 210, 90), (x, y), radius - 4)
        for k in range(8):
            angle = k * math.pi / 4
            inner = (x + math.cos(angle) * (radius - 1), y + math.sin(angle) * (radius - 1))
            outer = (x + math.cos(angle) * (radius + 4), y + math.sin(angle) * (radius + 4))
            pygame.draw.line(screen, (255, 210, 90), inner, outer, 2)
    else:
        pygame.draw.circle(screen, (226, 230, 245), (x, y), radius - 2)
        pygame.draw.circle(screen, (16, 22, 28), (x + 6, y - 4), radius - 4)


def arrow(screen, tip, direction, color, size=26):
    """Seta triangular apontando em `direction` (Vector2 normalizado) com a ponta em `tip`."""
    tip = pygame.Vector2(tip)
    side = pygame.Vector2(-direction.y, direction.x)
    points = [tip, tip - direction * size + side * size / 2, tip - direction * size - side * size / 2]
    points = [(round(p.x), round(p.y)) for p in points]
    pygame.draw.polygon(screen, color, points)
    pygame.draw.polygon(screen, (255, 255, 255), points, 2)
