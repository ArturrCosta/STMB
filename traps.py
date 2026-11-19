"""Armadilhas que o agiota e os capangas largam pelo caminho durante a caçada.

Cada caçador solta uma armadilha de tempos em tempos onde está pisando. Ela leva
um instante para armar (cai no chão girando), fica alguns segundos no mapa e some
piscando. Quem pisa numa armadilha armada fica preso por TRAP_STUN segundos: a pé
o personagem para, de Fusca o pneu prende e o carro para na hora.
"""

import math
import random

import pygame

TRAP_STUN = 1.0          # segundos preso
TRAP_ARM_TIME = 0.45     # tempo até armar depois de cair (dá para ver ela caindo)
TRAP_LIFETIME = 10.0     # segundos no mapa até sumir
TRAP_MAX = 16            # máximo no mapa (a mais antiga some primeiro)
TRAP_SPACING = 46        # distância mínima entre duas armadilhas
TRAP_SAFE_DISTANCE = 70  # caçador colado no jogador não larga armadilha (ele vai é pegar)


class Trap:
    SIZE = (24, 16)

    def __init__(self, position):
        self.position = pygame.Vector2(position)
        self.age = 0.0
        self.spin = random.uniform(0, math.tau)
        self.rect = pygame.Rect(0, 0, *self.SIZE)
        self.rect.center = (round(self.position.x), round(self.position.y))

    @property
    def armed(self):
        return self.age >= TRAP_ARM_TIME

    @property
    def expired(self):
        return self.age >= TRAP_LIFETIME

    def update(self, dt):
        self.age += dt

    def triggers(self, body):
        """True se a hitbox `body` (pés do jogador ou o Fusca) pisou na armadilha armada."""
        return self.armed and body.colliderect(self.rect)

    def draw(self, screen, camera):
        x = round(self.position.x - camera.x)
        y = round(self.position.y - camera.y)
        if x < -30 or y < -30 or x > screen.get_width() + 30 or y > screen.get_height() + 30:
            return
        remaining = TRAP_LIFETIME - self.age
        if remaining < 1.5 and int(remaining * 8) % 2 == 0:
            return  # pisca antes de sumir
        if not self.armed:
            # Caindo: começa pequena e alta, gira e "assenta" no chão.
            k = self.age / TRAP_ARM_TIME
            scale = 0.4 + 0.6 * k
            lift = round((1 - k) * 18)
        else:
            scale, lift = 1.0, 0
        w, h = round(26 * scale), round(14 * scale)
        pygame.draw.ellipse(screen, (24, 28, 30), pygame.Rect(x - w // 2, y - h // 2 + 2, w, h))  # sombra
        y -= lift
        body = pygame.Rect(x - w // 2, y - h // 2, w, h)
        pygame.draw.ellipse(screen, (92, 98, 104), body)              # aro de metal
        pygame.draw.ellipse(screen, (40, 44, 48), body, max(1, round(2 * scale)))
        # Dentes da mandíbula (aberta) em volta do aro.
        teeth = 8
        for k in range(teeth):
            angle = self.spin * (0 if self.armed else 1) + k * math.tau / teeth
            cx, cy = x + math.cos(angle) * w * 0.42, y + math.sin(angle) * h * 0.42
            tip = (x + math.cos(angle) * w * 0.62, y + math.sin(angle) * h * 0.66)
            side = pygame.Vector2(-math.sin(angle), math.cos(angle)) * 2.5 * scale
            points = [(cx + side.x, cy + side.y), (cx - side.x, cy - side.y), tip]
            pygame.draw.polygon(screen, (200, 206, 212), [(round(a), round(b)) for a, b in points])
        # Gatilho no centro: vermelho pulsando quando armada.
        if self.armed:
            pulse = 0.5 + 0.5 * math.sin(self.age * 9)
            color = (200 + round(55 * pulse), 50, 40)
            pygame.draw.circle(screen, color, (x, y), max(2, round(4 * scale)))
        else:
            pygame.draw.circle(screen, (140, 120, 90), (x, y), max(2, round(3 * scale)))
