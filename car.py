"""O Fusca: um veículo de verdade no mapa.

Depois de comprado, ele fica estacionado perto da loja. O jogador entra e sai
com E; o carro fica parado onde foi deixado. Na rua ele é bem mais rápido que
a pé; na grama perde 25% da velocidade (e levanta poeira).
"""

import math
import random

import pygame

ROAD_SPEED = 340
GRASS_FACTOR = 0.75
ACCELERATION = 620
BRAKING = 900


class Car:
    HITBOX_SIZE = (34, 24)
    BODY_COLOR = (92, 172, 214)

    _sprite = None
    _shadow = None

    def __init__(self, position, heading=0.0):
        self.position = pygame.Vector2(position)
        self.velocity = pygame.Vector2()
        self.heading = heading  # graus; 0 = direita, 90 = cima
        self.on_grass = False
        self.dust = []  # partículas: [x, y, idade]
        self.hitbox = pygame.Rect(0, 0, *self.HITBOX_SIZE)
        self._sync_hitbox()

    def _sync_hitbox(self):
        self.hitbox.center = (round(self.position.x), round(self.position.y))

    @property
    def sort_y(self):
        return self.hitbox.bottom

    @property
    def speed(self):
        return self.velocity.length()

    def max_speed(self):
        return ROAD_SPEED * (GRASS_FACTOR if self.on_grass else 1.0)

    def update(self, dt, direction, obstacles, world_width, world_height, on_grass):
        """Acelera na direção pedida (Vector2, pode ser zero) e colide com obstáculos por eixo."""
        self.on_grass = on_grass
        dt = min(max(dt, 0.0), 0.05)
        target = pygame.Vector2(direction)
        if target.length_squared() > 0:
            target = target.normalize() * self.max_speed()
        rate = ACCELERATION if target.length_squared() > 0 else BRAKING
        delta = target - self.velocity
        if delta.length() > rate * dt:
            delta.scale_to_length(rate * dt)
        self.velocity += delta
        if self.velocity.length() > self.max_speed():  # entrou na grama: freia até o limite
            self.velocity.scale_to_length(max(self.max_speed(), self.velocity.length() - BRAKING * dt))

        for axis in ("x", "y"):
            step = getattr(self.velocity, axis) * dt
            if not step:
                continue
            previous = getattr(self.position, axis)
            setattr(self.position, axis, previous + step)
            self.position.x = max(self.HITBOX_SIZE[0] / 2, min(world_width - self.HITBOX_SIZE[0] / 2, self.position.x))
            self.position.y = max(self.HITBOX_SIZE[1] / 2, min(world_height - self.HITBOX_SIZE[1] / 2, self.position.y))
            self._sync_hitbox()
            if any(self.hitbox.colliderect(wall) for wall in obstacles):
                setattr(self.position, axis, previous)
                setattr(self.velocity, axis, 0.0)
                self._sync_hitbox()

        if self.velocity.length() > 25:
            self.heading = math.degrees(math.atan2(-self.velocity.y, self.velocity.x))
        self._update_dust(dt)

    def _update_dust(self, dt):
        for particle in self.dust:
            particle[2] += dt
        self.dust = [p for p in self.dust if p[2] < 0.6]
        if self.on_grass and self.velocity.length() > 40 and random.random() < 0.6:
            back = pygame.Vector2(math.cos(math.radians(self.heading)), -math.sin(math.radians(self.heading)))
            spot = self.position - back * 28
            self.dust.append([spot.x + random.uniform(-6, 6), spot.y + random.uniform(-4, 6), 0.0])

    # ------------------------------------------------------------------
    @classmethod
    def _base_sprite(cls):
        """Fusca visto de cima, apontando para a direita (desenhado uma vez)."""
        if cls._sprite is None:
            sprite = pygame.Surface((48, 30), pygame.SRCALPHA)
            for wx in (9, 33):  # rodas
                pygame.draw.rect(sprite, (25, 25, 28), pygame.Rect(wx, 1, 8, 5), border_radius=2)
                pygame.draw.rect(sprite, (25, 25, 28), pygame.Rect(wx, 24, 8, 5), border_radius=2)
            pygame.draw.ellipse(sprite, cls.BODY_COLOR, pygame.Rect(2, 4, 44, 22))
            pygame.draw.ellipse(sprite, (60, 120, 160), pygame.Rect(2, 4, 44, 22), 2)
            pygame.draw.ellipse(sprite, (70, 140, 180), pygame.Rect(13, 6, 22, 18))  # teto
            pygame.draw.rect(sprite, (190, 225, 245), pygame.Rect(30, 9, 5, 12), border_radius=2)  # para-brisa
            pygame.draw.rect(sprite, (160, 200, 225), pygame.Rect(13, 10, 4, 10), border_radius=2)  # vidro traseiro
            pygame.draw.circle(sprite, (255, 240, 170), (44, 9), 2)  # faróis
            pygame.draw.circle(sprite, (255, 240, 170), (44, 21), 2)
            # Desenhado pequeno e ampliado sem suavização: fica no estilo pixel art e maior que uma pessoa.
            cls._sprite = pygame.transform.scale(sprite, (72, 45))
        return cls._sprite

    @classmethod
    def _shadow_sprite(cls):
        """Sombra no formato do carro (gira junto com ele)."""
        if cls._shadow is None:
            shadow = pygame.Surface((72, 45), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (10, 12, 14, 120), pygame.Rect(2, 6, 68, 36))
            cls._shadow = shadow
        return cls._shadow

    def draw(self, screen, camera):
        for x, y, age in self.dust:
            radius = round(3 + age * 10)
            alpha = max(0, round(150 * (1 - age / 0.6)))
            puff = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(puff, (170, 150, 110, alpha), (radius + 1, radius + 1), radius)
            screen.blit(puff, (round(x - camera.x) - radius, round(y - camera.y) - radius))
        x = round(self.position.x - camera.x)
        y = round(self.position.y - camera.y)
        angle = round(self.heading / 45) * 45  # 8 direções: fica nítido em pixel art
        shadow = pygame.transform.rotate(self._shadow_sprite(), angle)
        screen.blit(shadow, shadow.get_rect(center=(x + 3, y + 4)))
        image = pygame.transform.rotate(self._base_sprite(), angle)
        screen.blit(image, image.get_rect(center=(x, y - 6)))
