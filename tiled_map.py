import pygame
import pytmx


class TiledMap:
    def __init__(self, filename):
        self.tmx_data = pytmx.load_pygame(filename)

        self.width = self.tmx_data.width * self.tmx_data.tilewidth
        self.height = self.tmx_data.height * self.tmx_data.tileheight

    def draw(self, screen, camera):
        for layer in self.tmx_data.visible_layers:
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    tile = self.tmx_data.get_tile_image_by_gid(gid)

                    if tile:
                        screen.blit(
                            tile,
                            (
                                x * self.tmx_data.tilewidth - camera.x,
                                y * self.tmx_data.tileheight - camera.y
                            )
                        )