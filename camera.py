import pygame


class Camera:
    def __init__(self, width, height, world_width, world_height):
        self.width = width
        self.height = height

        self.world_width = world_width
        self.world_height = world_height

        self.x = 0
        self.y = 0

    def update(self, player):
        self.x = player.rect.centerx - self.width // 2
        self.y = player.rect.centery - self.height // 2

        # Impede a câmera de sair dos limites do mundo
        self.x = max(0, min(self.x, self.world_width - self.width))
        self.y = max(0, min(self.y, self.world_height - self.height))

    def apply(self, rect):
        return rect.move(-self.x, -self.y)