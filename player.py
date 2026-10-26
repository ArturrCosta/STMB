import pygame


class Player(pygame.sprite.Sprite):
    """Personagem controlado pelas teclas WASD."""

    def __init__(self):
        super().__init__()

        # Placeholder simples até o sprite definitivo ficar pronto.
        self.image = pygame.Surface((18, 24), pygame.SRCALPHA)
        self.image.fill((255, 255, 255))

        self.rect = self.image.get_rect()
        self.rect.center = (1280, 900)
        self.position = pygame.Vector2(self.rect.topleft)

        self.base_speed = 190  # pixels por segundo
        self.has_car = False
        self.tired = False

    def reset_position(self, center):
        self.rect.center = center
        self.position.update(self.rect.topleft)

    def update(self, dt, solid_rects, world_width, world_height, on_grass=False):
        """Move o jogador com colisão simples em cada eixo."""
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(0, 0)

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            direction.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction.x += 1

        if direction.length_squared() == 0:
            return

        direction = direction.normalize()
        speed = self.base_speed

        # O Fusca acelera nas ruas, mas é ruim de dirigir na grama.
        if self.has_car:
            speed = 300 if not on_grass else 170

        if self.tired:
            speed *= 0.65

        movement = direction * speed * min(dt, 0.05)

        # Movimento horizontal separado do vertical evita atravessar cantos.
        old_x = self.position.x
        self.position.x += movement.x
        self.rect.x = round(self.position.x)
        self._keep_inside_world(world_width, world_height)

        if any(self.rect.colliderect(wall) for wall in solid_rects):
            self.position.x = old_x
            self.rect.x = round(old_x)

        old_y = self.position.y
        self.position.y += movement.y
        self.rect.y = round(self.position.y)
        self._keep_inside_world(world_width, world_height)

        if any(self.rect.colliderect(wall) for wall in solid_rects):
            self.position.y = old_y
            self.rect.y = round(old_y)

        # Mantém a posição decimal alinhada ao retângulo após limites/colisões.
        self.position.update(self.rect.topleft)

    def _keep_inside_world(self, world_width, world_height):
        self.rect.left = max(0, self.rect.left)
        self.rect.top = max(0, self.rect.top)
        self.rect.right = min(world_width, self.rect.right)
        self.rect.bottom = min(world_height, self.rect.bottom)
