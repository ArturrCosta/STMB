import pygame
import pytmx


class TiledMap:

    def __init__(self, filename):
        self.tmx_data = pytmx.load_pygame(filename)

        self.width = self.tmx_data.width * self.tmx_data.tilewidth
        self.height = self.tmx_data.height * self.tmx_data.tileheight

    def draw(self, screen, camera):
        for layer in self.tmx_data.visible_layers:

            # Camadas normais de tiles
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

            # Camadas de objetos
            elif isinstance(layer, pytmx.TiledObjectGroup):
                for obj in layer:

                    if not obj.gid:
                        continue

                    tile = self.tmx_data.get_tile_image_by_gid(obj.gid)

                    if not tile:
                        continue

                    # Casas sem rotação
                    if obj.rotation == 0:
                        screen.blit(
                            tile,
                            (
                                obj.x - camera.x,
                                obj.y - camera.y
                            )
                        )

                    # Casas rotacionadas
                    else:
                        # Converte a rotação do Tiled para a rotação do Pygame
                        angle = -obj.rotation

                        # Gira a imagem
                        rotated_tile = pygame.transform.rotate(tile, angle)

                        # Ponto de rotação: canto inferior esquerdo
                        pivot = pygame.Vector2(
                            obj.x,
                            obj.y + tile.get_height()
                        )

                        # Distância do pivot até o centro da imagem original
                        offset = pygame.Vector2(
                            tile.get_width() / 2,
                            -tile.get_height() / 2
                        )

                        # IMPORTANTE:
                        # Vector2.rotate usa o sentido oposto ao transform.rotate
                        offset = offset.rotate(-angle)

                        # Novo centro da imagem
                        center = pivot + offset

                        rect = rotated_tile.get_rect(center=center)

                        # Câmera
                        rect.x -= camera.x
                        rect.y -= camera.y

                        screen.blit(rotated_tile, rect)