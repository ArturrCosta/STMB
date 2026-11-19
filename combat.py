"""Revólver do jogador: projéteis e os caídos (quem levou tiro cai e some aos poucos).

O revólver é comprado na loja (o dobro da passagem de trem) e fica equipado. Com ele o
jogador atira com F (para onde está olhando) ou com o clique do mouse (na direção do
cursor). O tiro para nas paredes e acerta o agiota, os capangas e os assaltantes; os
moradores não entram na conta.
"""

import math

import pygame

BULLET_SPEED = 980       # px/s
BULLET_RANGE = 560       # alcance em px
SHOT_COOLDOWN = 0.38     # segundos entre tiros
FALLEN_LIFETIME = 2.2    # segundos que o corpo fica no chão antes de sumir


class Bullet:
    def __init__(self, origin, direction):
        self.position = pygame.Vector2(origin)
        self.velocity = pygame.Vector2(direction).normalize() * BULLET_SPEED
        self.travelled = 0.0
        self.alive = True

    def update(self, dt, walls):
        """Anda em passos curtos (não atravessa parede fina). Devolve o ponto de impacto na parede, se houver."""
        steps = max(1, math.ceil(self.velocity.length() * dt / 10))
        step = self.velocity * dt / steps
        for _ in range(steps):
            self.position += step
            self.travelled += step.length()
            point = (round(self.position.x), round(self.position.y))
            if any(wall.collidepoint(point) for wall in walls):
                self.alive = False
                return pygame.Vector2(self.position)
            if self.travelled >= BULLET_RANGE:
                self.alive = False
                return None
        return None

    def hits(self, hitbox):
        return hitbox.inflate(8, 10).collidepoint(round(self.position.x), round(self.position.y))

    def draw(self, screen, camera):
        head = self.position - pygame.Vector2(camera.x, camera.y)
        tail = head - self.velocity.normalize() * 12
        pygame.draw.line(screen, (255, 214, 120), (round(tail.x), round(tail.y)), (round(head.x), round(head.y)), 3)
        pygame.draw.circle(screen, (255, 250, 220), (round(head.x), round(head.y)), 2)


class Fallen:
    """Quem levou tiro: o desenho do personagem deitado, sumindo aos poucos."""

    def __init__(self, walker):
        self.position = pygame.Vector2(walker.position)
        self.age = 0.0
        # Desenha o personagem uma vez numa superfície pequena e deita a imagem.
        canvas = pygame.Surface((60, 64), pygame.SRCALPHA)
        offset = _Offset(walker.position.x - 30, walker.position.y - 56)
        walker.moving = False
        walker.draw(canvas, offset)
        self.image = pygame.transform.rotate(canvas, -90 if walker.facing != "left" else 90)

    @property
    def done(self):
        return self.age >= FALLEN_LIFETIME

    @property
    def sort_y(self):
        return self.position.y - 10  # fica por baixo de quem está em pé

    def update(self, dt):
        self.age += dt

    def draw(self, screen, camera):
        alpha = 255 if self.age < FALLEN_LIFETIME - 0.8 else round(255 * max(0.0, (FALLEN_LIFETIME - self.age) / 0.8))
        self.image.set_alpha(alpha)
        rect = self.image.get_rect(center=(round(self.position.x - camera.x), round(self.position.y - camera.y - 6)))
        screen.blit(self.image, rect)


class _Offset:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def draw_revolver(screen, hand, direction):
    """Revólver na mão do jogador, apontado para `direction` (Vector2 normalizado)."""
    direction = pygame.Vector2(direction)
    if direction.length_squared() == 0:
        return
    direction = direction.normalize()
    side = pygame.Vector2(-direction.y, direction.x)
    start = pygame.Vector2(hand)
    end = start + direction * 13
    grip = start - side * 4 * (1 if direction.x >= 0 else -1) - direction * 2
    pygame.draw.line(screen, (36, 36, 40), (round(start.x), round(start.y)), (round(end.x), round(end.y)), 4)
    pygame.draw.line(screen, (90, 92, 98), (round(start.x), round(start.y)), (round(end.x), round(end.y)), 1)
    pygame.draw.line(screen, (88, 58, 36), (round(start.x), round(start.y)), (round(grip.x), round(grip.y)), 4)
