"""NPCs que caminham pela cidade e o agiota que persegue o jogador em dívida.

Nenhum dos dois ainda tem sprite próprio: por enquanto são desenhados como
marcadores simples (um círculo com sombra), no mesmo estilo provisório já
usado nos pontos de interesse do mapa (`ZONES`, em `game.py`). Quando
houver arte própria para os moradores, basta trocar o método `draw` por um
carregamento de sprite sheet (seguindo o mesmo padrão de `player.Player`);
o resto da classe (movimento, colisão, perseguição) não precisa mudar.
"""

import random

import pygame


class NPC:
    """Morador que vagueia pela cidade; também funciona como obstáculo leve."""

    HITBOX_SIZE = (16, 12)
    PAUSE_RANGE = (1.0, 3.0)
    WANDER_RADIUS = 220
    WORLD_MARGIN = 24

    def __init__(self, position, speed=70, color=(214, 197, 150)):
        self.position = pygame.Vector2(position)
        self.speed = speed
        self.color = color
        self.target = pygame.Vector2(position)
        self.pause_timer = random.uniform(*self.PAUSE_RANGE)
        self.hitbox = pygame.Rect(0, 0, *self.HITBOX_SIZE)
        self._sync_hitbox()

    def _sync_hitbox(self):
        self.hitbox.center = (round(self.position.x), round(self.position.y))

    def _pick_new_target(self, world_width, world_height, solid_rects):
        """Escolhe um novo ponto próximo e livre de obstáculos para caminhar até."""
        for _ in range(20):
            candidate = self.position + pygame.Vector2(
                random.uniform(-self.WANDER_RADIUS, self.WANDER_RADIUS),
                random.uniform(-self.WANDER_RADIUS, self.WANDER_RADIUS),
            )
            candidate.x = max(self.WORLD_MARGIN, min(world_width - self.WORLD_MARGIN, candidate.x))
            candidate.y = max(self.WORLD_MARGIN, min(world_height - self.WORLD_MARGIN, candidate.y))
            probe = self.hitbox.copy()
            probe.center = (round(candidate.x), round(candidate.y))
            if not any(probe.colliderect(wall) for wall in solid_rects):
                self.target = candidate
                return
        self.target = self.position.copy()

    def update(self, dt, solid_rects, world_width, world_height):
        """Anda em direção a `self.target`, parando periodicamente para parecer natural."""
        if self.pause_timer > 0:
            self.pause_timer -= dt
            if self.pause_timer <= 0:
                self._pick_new_target(world_width, world_height, solid_rects)
            return

        to_target = self.target - self.position
        distance = to_target.length()
        if distance < 4:
            self.pause_timer = random.uniform(*self.PAUSE_RANGE)
            return

        step = to_target.normalize() * min(self.speed * dt, distance)

        # Movimento separado por eixo, igual ao do jogador: evita atravessar
        # cantos de prédios quando colide num dos dois eixos.
        old_x = self.position.x
        self.position.x += step.x
        self._sync_hitbox()
        if any(self.hitbox.colliderect(wall) for wall in solid_rects):
            self.position.x = old_x
            self._sync_hitbox()
            self.pause_timer = 0.3  # esbarrou; tenta outro caminho em breve

        old_y = self.position.y
        self.position.y += step.y
        self._sync_hitbox()
        if any(self.hitbox.colliderect(wall) for wall in solid_rects):
            self.position.y = old_y
            self._sync_hitbox()
            self.pause_timer = 0.3

    def draw(self, screen, camera):
        x = round(self.position.x) - camera.x
        y = round(self.position.y) - camera.y
        pygame.draw.ellipse(screen, (25, 25, 25), pygame.Rect(x - 9, y + 7, 18, 7))
        pygame.draw.circle(screen, self.color, (x, y), 10)
        pygame.draw.circle(screen, (40, 32, 26), (x, y), 10, width=2)


class Agiota(NPC):
    """NPC especial que persegue ativamente o jogador numa cobrança perdida."""

    HITBOX_SIZE = (18, 14)

    def __init__(self, position, speed):
        super().__init__(position, speed=speed, color=(196, 48, 43))
        self.pause_timer = 0.0

    def update(self, dt, solid_rects, world_width, world_height, player_position):
        # Sempre mira a posição atual do jogador, em vez de vaguear.
        self.target = pygame.Vector2(player_position)
        super().update(dt, solid_rects, world_width, world_height)

    def draw(self, screen, camera):
        super().draw(screen, camera)
        x = round(self.position.x) - camera.x
        y = round(self.position.y) - camera.y
        pygame.draw.circle(screen, (255, 214, 92), (x, y), 13, width=2)
