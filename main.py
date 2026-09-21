import pygame

from player import Player
from camera import Camera
from tiled_map import TiledMap


pygame.init()

SCREEN_WIDTH = 1100
SCREEN_HEIGHT = 650

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Song to My Bills")

clock = pygame.time.Clock()

tiled_map = TiledMap("assets/maps/cidade.tmx")

player = Player()
all_sprites = pygame.sprite.Group(player)

camera = Camera(
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
    tiled_map.width,
    tiled_map.height
)

running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    all_sprites.update()

    camera.update(player)

    screen.fill((30, 30, 30))

    tiled_map.draw(screen, camera)

    for sprite in all_sprites:
        screen.blit(sprite.image, camera.apply(sprite.rect))

    pygame.display.flip()

    clock.tick(60)

pygame.quit()