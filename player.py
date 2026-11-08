from pathlib import Path

import pygame


class Player(pygame.sprite.Sprite):
    """Personagem controlado por WASD/setas, com animação em 4 direções."""

    # O arquivo possui 4 colunas x 3 linhas, com células de 32 x 48 px.
    FRAME_WIDTH = 32
    FRAME_HEIGHT = 48
    FRAMES_PER_ROW = 4

    # Índices das linhas no PNG:
    # 0 = frente/baixo, 1 = costas/cima, 2 = perfil olhando para a esquerda.
    ROW_BY_DIRECTION = {
        "down": 0,
        "up": 1,
        "left": 2,
        "right": 2,
    }

    def __init__(self, sprite_sheet_path=None):
        super().__init__()

        if sprite_sheet_path is None:
            sprite_sheet_path = (
                Path(__file__).resolve().parent
                / "assets"
                / "images"
                / "player.png"
            )
        else:
            sprite_sheet_path = Path(sprite_sheet_path)

        if not sprite_sheet_path.is_file():
            raise FileNotFoundError(
                f"Sprite do jogador não encontrado: {sprite_sheet_path}\n"
                "Coloque o PNG em assets/images/player.png."
            )

        sheet = pygame.image.load(str(sprite_sheet_path))
        if pygame.display.get_surface() is not None:
            sheet = sheet.convert_alpha()

        expected_size = (
            self.FRAME_WIDTH * self.FRAMES_PER_ROW,
            self.FRAME_HEIGHT * 3,
        )
        if sheet.get_size() != expected_size:
            raise ValueError(
                "O sprite sheet precisa ter 128x144 px "
                f"(4 colunas x 3 linhas de 32x48). Recebido: {sheet.get_size()}"
            )

        # Separa os 12 quadros do PNG em três animações de caminhada.
        self.animations = []
        for row in range(3):
            frames = []
            for column in range(self.FRAMES_PER_ROW):
                frame_rect = pygame.Rect(
                    column * self.FRAME_WIDTH,
                    row * self.FRAME_HEIGHT,
                    self.FRAME_WIDTH,
                    self.FRAME_HEIGHT,
                )
                frames.append(sheet.subsurface(frame_rect).copy())
            self.animations.append(frames)

        # A imagem original do perfil olha para a esquerda.
        # Criamos uma versão espelhada para andar para a direita.
        self.right_frames = [
            pygame.transform.flip(frame, True, False)
            for frame in self.animations[2]
        ]

        self.facing = "down"
        self.frame_index = 0
        self.animation_timer = 0.0
        self.frame_duration = 0.12  # aproximadamente 8,3 quadros por segundo
        self.is_moving = False

        self.image = self.animations[0][0]
        self.rect = self.image.get_rect()
        self.rect.center = (1280, 900)
        self.position = pygame.Vector2(self.rect.topleft)

        # A imagem mede 32x48, mas a colisão fica concentrada nos pés.
        # Isso evita que cabeça e tronco prendam o jogador nas paredes.
        self.hitbox = pygame.Rect(0, 0, 18, 14)
        self._sync_hitbox()

        self.base_speed = 300  # pixels por segundo
        self.has_car = False
        self.tired = False

    def reset_position(self, center):
        """Reposiciona o personagem usando o centro da imagem."""
        self.rect.center = center
        self.position.update(self.rect.topleft)
        self._sync_hitbox()

    def update(
        self,
        dt,
        solid_rects,
        world_width,
        world_height,
        on_grass=False,
    ):
        """Move o jogador, verifica colisões e atualiza o quadro da animação."""
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

        # Atualiza a direção mesmo quando o personagem está encostado numa parede.
        if direction.length_squared() > 0:
            self._update_facing(direction)
            direction.normalize_ip()

            speed = self.base_speed

            # O Fusca acelera nas ruas, mas é ruim de dirigir na grama.
            if self.has_car:
                speed = 300 if not on_grass else 170

            if self.tired:
                speed *= 0.65

            # Limita dt para evitar saltos grandes após uma queda de FPS.
            movement = direction * speed * min(max(dt, 0.0), 0.05)
            start_position = self.position.copy()

            # Movimento horizontal separado do vertical evita atravessar cantos.
            old_x = self.position.x
            self.position.x += movement.x
            self.rect.x = round(self.position.x)
            self._keep_inside_world(world_width, world_height)
            self._sync_hitbox()

            if any(self.hitbox.colliderect(wall) for wall in solid_rects):
                self.position.x = old_x
                self.rect.x = round(old_x)
                self._sync_hitbox()

            old_y = self.position.y
            self.position.y += movement.y
            self.rect.y = round(self.position.y)
            self._keep_inside_world(world_width, world_height)
            self._sync_hitbox()

            if any(self.hitbox.colliderect(wall) for wall in solid_rects):
                self.position.y = old_y
                self.rect.y = round(old_y)
                self._sync_hitbox()

            # Mantém a posição decimal alinhada ao retângulo após limites/colisões.
            self.position.update(self.rect.topleft)
            self.is_moving = self.position.distance_to(start_position) > 0.1
        else:
            self.is_moving = False

        self._update_animation(dt)

    def _update_facing(self, direction):
        """Escolhe a direção visual dominante, inclusive durante diagonais."""
        if abs(direction.x) > abs(direction.y):
            self.facing = "right" if direction.x > 0 else "left"
        else:
            self.facing = "down" if direction.y > 0 else "up"

    def _update_animation(self, dt):
        if self.is_moving:
            self.animation_timer += min(max(dt, 0.0), 0.05)
            while self.animation_timer >= self.frame_duration:
                self.animation_timer -= self.frame_duration
                self.frame_index = (self.frame_index + 1) % self.FRAMES_PER_ROW
        else:
            # Quadro zero é a pose parada de cada direção.
            self.frame_index = 0
            self.animation_timer = 0.0

        row = self.ROW_BY_DIRECTION[self.facing]
        if self.facing == "right":
            self.image = self.right_frames[self.frame_index]
        else:
            self.image = self.animations[row][self.frame_index]

    def _sync_hitbox(self):
        """Posiciona a hitbox pequena na região dos pés do sprite."""
        self.hitbox.topleft = (self.rect.x + 7, self.rect.y + 32)

    def _keep_inside_world(self, world_width, world_height):
        self.rect.left = max(0, self.rect.left)
        self.rect.top = max(0, self.rect.top)
        self.rect.right = min(world_width, self.rect.right)
        self.rect.bottom = min(world_height, self.rect.bottom)
