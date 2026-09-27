import pygame
from pygame._sdl2 import Window

from player import Player
from camera import Camera
from tiled_map import TiledMap


pygame.init()

# =========================================================
# RESOLUÇÃO INTERNA DO JOGO
# =========================================================

GAME_WIDTH = 1280
GAME_HEIGHT = 720

# Cria a janela
screen = pygame.display.set_mode(
    (GAME_WIDTH, GAME_HEIGHT),
    pygame.RESIZABLE
)

pygame.display.set_caption("Song to My Bills")

# Maximiza a janela
window = Window.from_display_module()
window.maximize()

clock = pygame.time.Clock()

# =========================================================
# SUPERFÍCIE INTERNA
# =========================================================

game_surface = pygame.Surface(
    (GAME_WIDTH, GAME_HEIGHT)
)

# =========================================================
# MAPA
# =========================================================

tiled_map = TiledMap("assets/maps/cidade.tmx")

# =========================================================
# PLAYER
# =========================================================

player = Player()

all_sprites = pygame.sprite.Group(player)

# =========================================================
# CÂMERA
# =========================================================

camera = Camera(
    GAME_WIDTH,
    GAME_HEIGHT,
    tiled_map.width,
    tiled_map.height
)

# =========================================================
# LOOP PRINCIPAL
# =========================================================

running = True

while running:

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

    # Atualiza jogador
    all_sprites.update()

    # Atualiza câmera
    camera.update(player)

    # =====================================================
    # DESENHA O JOGO NA RESOLUÇÃO INTERNA
    # =====================================================

    game_surface.fill((30, 30, 30))

    tiled_map.draw(
        game_surface,
        camera
    )

    for sprite in all_sprites:

        game_surface.blit(
            sprite.image,
            camera.apply(sprite.rect)
        )

    # =====================================================
    # PEGA O TAMANHO ATUAL DA JANELA
    # =====================================================

    window_width, window_height = pygame.display.get_window_size()

    # =====================================================
    # CALCULA A ESCALA SEM DISTORCER
    # =====================================================

    scale_x = window_width / GAME_WIDTH
    scale_y = window_height / GAME_HEIGHT

    scale = min(scale_x, scale_y)

    new_width = int(GAME_WIDTH * scale)
    new_height = int(GAME_HEIGHT * scale)

    # Redimensiona o jogo
    scaled_surface = pygame.transform.scale(
        game_surface,
        (new_width, new_height)
    )

    # =====================================================
    # CENTRALIZA NA JANELA
    # =====================================================

    screen.fill((0, 0, 0))

    x = (window_width - new_width) // 2
    y = (window_height - new_height) // 2

    screen.blit(
        scaled_surface,
        (x, y)
    )

    pygame.display.flip()

    clock.tick(60)


pygame.quit()