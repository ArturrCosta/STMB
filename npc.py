"""Moradores que passeiam pela cidade e o agiota que persegue o jogador.

Todos os personagens andam sobre a grade de navegação (`navigation.NavGrid`):
o caminho é calculado com A* e seguido ponto a ponto, então ninguém fica preso
atrás de um prédio. O desenho é procedural (corpo, cabeça, pernas animadas),
o que dispensa sprite sheets extras; para usar arte própria basta trocar
`Walker.draw` por um carregamento de sprites, como em `player.Player`.
"""

import math
import random

import pygame

SKIN_TONES = ((235, 196, 160), (214, 168, 128), (176, 128, 92), (128, 90, 62))
HAIR_COLORS = ((40, 30, 26), (92, 62, 36), (170, 120, 60), (200, 200, 205), (30, 30, 34))


class Walker:
    """Base para quem anda seguindo um caminho de A* pela cidade."""

    HITBOX_SIZE = (16, 12)
    REPATH_STUCK_SECONDS = 0.8

    def __init__(self, position, speed, nav):
        self.position = pygame.Vector2(position)
        self.speed = speed
        self.nav = nav
        self.path = []
        self.facing = "down"
        self.walk_phase = random.uniform(0, math.tau)
        self.moving = False
        self.blocked_time = 0.0
        self.stuck_total = 0.0   # tempo travado somando várias tentativas (não zera ao refazer o caminho)
        self.ghost_timer = 0.0   # destravando: atravessa os outros por um instante
        self.hitbox = pygame.Rect(0, 0, *self.HITBOX_SIZE)
        self._sync_hitbox()

    def _sync_hitbox(self):
        self.hitbox.center = (round(self.position.x), round(self.position.y))

    @property
    def sort_y(self):
        return self.hitbox.bottom

    # ------------------------------------------------------------------
    def set_goal(self, point):
        self.path = self.nav.find_path(self.position, point)
        self.blocked_time = 0.0

    GHOST_AFTER = 1.2       # travado por mais que isso (somando tentativas): atravessa os outros
    GHOST_SECONDS = 0.9

    def _follow_path(self, dt, blockers):
        """Anda um passo no caminho. `blockers` são hitboxes móveis (jogador, outros NPCs).

        Quem já está encostado/sobreposto não bloqueia (senão dois moradores que se
        sobrepõem nunca mais conseguem se mexer), e quem fica travado tempo demais
        (um bolo de gente se empurrando) atravessa os outros por um instante.
        """
        self.moving = False
        if not self.path:
            return
        if self.ghost_timer > 0:
            self.ghost_timer -= dt
            blockers = []
        else:
            blockers = [other for other in blockers if not other.colliderect(self.hitbox)]
        target = pygame.Vector2(self.path[0])
        to_target = target - self.position
        distance = to_target.length()
        if distance < 3:
            self.path.pop(0)
            return

        step = to_target.normalize() * min(self.speed * dt, distance)
        moved = False
        for axis in ("x", "y"):
            previous = getattr(self.position, axis)
            setattr(self.position, axis, previous + getattr(step, axis))
            self._sync_hitbox()
            if any(self.hitbox.colliderect(other) for other in blockers):
                setattr(self.position, axis, previous)
                self._sync_hitbox()
            elif abs(getattr(step, axis)) > 0.05:  # passos minúsculos (ruído de float) não contam como andar
                moved = True

        if moved:
            self.moving = True
            self.blocked_time = 0.0
            self.stuck_total = 0.0
            self.walk_phase += dt * 11
            if abs(step.x) > abs(step.y):
                self.facing = "right" if step.x > 0 else "left"
            else:
                self.facing = "down" if step.y > 0 else "up"
        else:
            self.blocked_time += dt
            self.stuck_total += dt
            if self.stuck_total > self.GHOST_AFTER:
                self.stuck_total = 0.0
                self.ghost_timer = self.GHOST_SECONDS

    def update(self, dt, blockers):
        raise NotImplementedError

    # ------------------------------------------------------------------
    def draw(self, screen, camera):
        x = round(self.position.x) - camera.x
        y = round(self.position.y) - camera.y
        self._draw_body(screen, x, y)

    def _draw_body(self, screen, x, y):
        raise NotImplementedError

    def _draw_legs(self, screen, x, y, color):
        swing = math.sin(self.walk_phase) * 4 if self.moving else 0
        pygame.draw.rect(screen, color, pygame.Rect(x - 5, round(y - 8 + max(0, -swing) * 0.3), 4, 9 + round(swing / 2)))
        pygame.draw.rect(screen, color, pygame.Rect(x + 1, round(y - 8 + max(0, swing) * 0.3), 4, 9 - round(swing / 2)))


class NPC(Walker):
    """Morador que vai de ponto em ponto, parando um pouco entre uma caminhada e outra."""

    PAUSE_RANGE = (1.0, 3.5)
    WANDER_CELLS = 9

    def __init__(self, position, speed, nav, color=(214, 197, 150)):
        super().__init__(position, speed, nav)
        self.color = color
        self.skin = random.choice(SKIN_TONES)
        self.hair = random.choice(HAIR_COLORS)
        self.pause_timer = random.uniform(*self.PAUSE_RANGE)

    def _choose_destination(self):
        point = self.nav.random_free_point(near=self.position, radius_cells=self.WANDER_CELLS, min_distance=64)
        if point is not None:
            self.set_goal(point)

    def update(self, dt, blockers):
        if self.pause_timer > 0:
            self.pause_timer -= dt
            self.moving = False
            if self.pause_timer <= 0:
                self._choose_destination()
                if not self.path:
                    self.pause_timer = random.uniform(*self.PAUSE_RANGE)
            return
        if not self.path:
            self.pause_timer = random.uniform(*self.PAUSE_RANGE)
            self.moving = False
            return
        self._follow_path(dt, blockers)
        if self.blocked_time > self.REPATH_STUCK_SECONDS:
            # Esbarrou em alguém: espera um instante e escolhe outro destino.
            self.path = []
            self.pause_timer = random.uniform(0.4, 1.0)

    def _draw_body(self, screen, x, y):
        pygame.draw.ellipse(screen, (24, 28, 30), pygame.Rect(x - 10, y - 2, 20, 8))
        self._draw_legs(screen, x, y, (52, 58, 78))
        torso = pygame.Rect(x - 7, y - 22, 14, 15)
        pygame.draw.rect(screen, self.color, torso, border_radius=4)
        pygame.draw.rect(screen, (40, 32, 26), torso, 1, border_radius=4)
        pygame.draw.circle(screen, self.skin, (x, y - 28), 7)
        pygame.draw.circle(screen, (40, 32, 26), (x, y - 28), 7, 1)
        if self.facing != "down":
            pygame.draw.circle(screen, self.hair, (x, y - 31), 6)
            pygame.draw.circle(screen, self.skin, (x + (3 if self.facing == "right" else -3 if self.facing == "left" else 0), y - 27), 4)
        else:
            pygame.draw.rect(screen, self.hair, pygame.Rect(x - 6, y - 35, 12, 5), border_radius=3)


class Agiota(Walker):
    """O agiota: calcula uma rota até o jogador e a refaz a cada fração de segundo."""

    HITBOX_SIZE = (18, 14)
    REPATH_INTERVAL = 0.35

    def __init__(self, position, speed, nav, role="direct", side=1):
        super().__init__(position, speed, nav)
        # Papel na caçada: "direct" vai reto no jogador, "flank" cerca por um dos lados,
        # "intercept" mira onde o jogador vai estar e "cutoff" tenta fechar o caminho lá na frente.
        self.role = role
        self.side = side
        self.repath_interval = self.REPATH_INTERVAL * random.uniform(0.8, 1.35)
        self.repath_timer = random.uniform(0, self.repath_interval)

    def update(self, dt, blockers, target):
        self.repath_timer -= dt
        if self.repath_timer <= 0 or self.blocked_time > 0.3:
            self.repath_timer = self.repath_interval
            self.set_goal(target)
        self._follow_path(dt, blockers)

    def _draw_body(self, screen, x, y):
        pygame.draw.ellipse(screen, (24, 28, 30), pygame.Rect(x - 12, y - 3, 24, 9))
        self._draw_legs(screen, x, y, (24, 24, 30))
        coat = pygame.Rect(x - 9, y - 25, 18, 19)
        pygame.draw.rect(screen, (34, 34, 44), coat, border_radius=4)
        pygame.draw.rect(screen, (160, 40, 40), pygame.Rect(x - 2, y - 24, 4, 12))  # gravata
        pygame.draw.circle(screen, (222, 182, 146), (x, y - 31), 7)
        pygame.draw.ellipse(screen, (20, 20, 24), pygame.Rect(x - 12, y - 38, 24, 7))  # aba do chapéu
        pygame.draw.rect(screen, (20, 20, 24), pygame.Rect(x - 7, y - 46, 14, 10), border_radius=3)
        pygame.draw.rect(screen, (196, 48, 43), pygame.Rect(x - 7, y - 40, 14, 3))
        pygame.draw.circle(screen, (255, 214, 92), (x, y - 14), 18, 1)  # aura de perigo


class Capanga(Agiota):
    """Capanga do agiota: mesma IA de perseguição, visual diferente (careca, regata, óculos)."""

    def _draw_body(self, screen, x, y):
        pygame.draw.ellipse(screen, (24, 28, 30), pygame.Rect(x - 13, y - 3, 26, 9))
        self._draw_legs(screen, x, y, (40, 40, 52))
        body = pygame.Rect(x - 10, y - 25, 20, 19)
        pygame.draw.rect(screen, (30, 30, 34), body, border_radius=5)
        pygame.draw.rect(screen, (196, 160, 130), pygame.Rect(x - 13, y - 23, 4, 11), border_radius=2)  # braços
        pygame.draw.rect(screen, (196, 160, 130), pygame.Rect(x + 9, y - 23, 4, 11), border_radius=2)
        pygame.draw.circle(screen, (206, 168, 136), (x, y - 31), 7)
        pygame.draw.rect(screen, (15, 15, 18), pygame.Rect(x - 6, y - 33, 12, 3))  # óculos escuros
        pygame.draw.circle(screen, (255, 120, 90), (x, y - 14), 18, 1)


class Mugger(NPC):
    """Assaltante da madrugada: passeia e, se avistar o jogador a pé, corre atrás para roubar."""

    SIGHT = 250
    GIVE_UP = 480
    REPATH_INTERVAL = 0.4

    def __init__(self, position, speed, nav):
        super().__init__(position, speed * 0.6, nav, color=(70, 58, 96))
        self.run_speed = speed
        self.walk_speed = speed * 0.6
        self.chasing = False
        self.repath_timer = 0.0

    def update(self, dt, blockers, player_position=None):
        distance = self.position.distance_to(player_position) if player_position is not None else 1e9
        if not self.chasing and distance < self.SIGHT:
            self.chasing = True
        elif self.chasing and distance > self.GIVE_UP:
            self.chasing = False
            self.path = []
        if self.chasing:
            self.speed = self.run_speed
            self.repath_timer -= dt
            if self.repath_timer <= 0 or not self.path:
                self.repath_timer = self.REPATH_INTERVAL
                self.set_goal(player_position)
            self._follow_path(dt, blockers)
        else:
            self.speed = self.walk_speed
            super().update(dt, blockers)

    def _draw_body(self, screen, x, y):
        pygame.draw.ellipse(screen, (24, 28, 30), pygame.Rect(x - 10, y - 2, 20, 8))
        self._draw_legs(screen, x, y, (28, 28, 36))
        pygame.draw.rect(screen, (58, 48, 82), pygame.Rect(x - 8, y - 23, 16, 16), border_radius=5)  # moletom
        pygame.draw.circle(screen, (58, 48, 82), (x, y - 29), 8)  # capuz
        pygame.draw.rect(screen, (20, 20, 24), pygame.Rect(x - 5, y - 30, 10, 5), border_radius=2)  # máscara
        pygame.draw.circle(screen, (240, 240, 240), (x - 2, y - 28), 1)
        pygame.draw.circle(screen, (240, 240, 240), (x + 2, y - 28), 1)
        if self.chasing:  # "!" de alerta
            pygame.draw.rect(screen, (255, 90, 80), pygame.Rect(x - 2, y - 52, 4, 10), border_radius=2)
            pygame.draw.circle(screen, (255, 90, 80), (x, y - 38), 2)
