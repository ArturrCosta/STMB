import pygame
import pytmx


class TiledMap:
    def __init__(self, filename):
        self.tmx_data = pytmx.load_pygame(filename)
        self.width = self.tmx_data.width * self.tmx_data.tilewidth
        self.height = self.tmx_data.height * self.tmx_data.tileheight
        self.tile_width = self.tmx_data.tilewidth
        self.tile_height = self.tmx_data.tileheight

        self.solid_rects = []
        self.grass_tiles = set()
        self._read_collision_data()

    def _read_collision_data(self):
        """Lê a camada Collision e usa prédios sem rotação como obstáculos."""
        for layer in self.tmx_data.visible_layers:
            layer_name = getattr(layer, "name", "") or ""

            if isinstance(layer, pytmx.TiledTileLayer):
                if layer_name.lower() == "collision":
                    for x, y, gid in layer:
                        if gid:
                            self.solid_rects.append(
                                pygame.Rect(
                                    x * self.tile_width,
                                    y * self.tile_height,
                                    self.tile_width,
                                    self.tile_height,
                                )
                            )

                if layer_name.lower() == "grass":
                    for x, y, gid in layer:
                        if gid:
                            self.grass_tiles.add((x, y))

            elif isinstance(layer, pytmx.TiledObjectGroup) and layer_name.lower() == "buildings":
                # Só os prédios bloqueiam o movimento; itens futuros não serão paredes.
                for obj in layer:
                    if not obj.gid or obj.rotation != 0:
                        continue

                    tile = self.tmx_data.get_tile_image_by_gid(obj.gid)
                    if tile:
                        self.solid_rects.append(
                            pygame.Rect(
                                round(obj.x),
                                round(obj.y),
                                tile.get_width(),
                                tile.get_height(),
                            )
                        )

    def is_grass_at(self, position):
        tile_x = int(position[0] // self.tile_width)
        tile_y = int(position[1] // self.tile_height)
        return (tile_x, tile_y) in self.grass_tiles

    def draw(self, screen, camera):
        for layer in self.tmx_data.visible_layers:

            # Camadas normais de tiles.
            if isinstance(layer, pytmx.TiledTileLayer):
                for x, y, gid in layer:
                    tile = self.tmx_data.get_tile_image_by_gid(gid)
                    if tile:
                        screen.blit(
                            tile,
                            (
                                x * self.tile_width - camera.x,
                                y * self.tile_height - camera.y,
                            ),
                        )

            # Camadas de objetos (prédios grandes em imagens únicas).
            elif isinstance(layer, pytmx.TiledObjectGroup):
                for obj in layer:
                    if not obj.gid:
                        continue

                    tile = self.tmx_data.get_tile_image_by_gid(obj.gid)
                    if not tile:
                        continue

                    # Mantém o posicionamento conhecido das casas sem rotação.
                    if obj.rotation == 0:
                        screen.blit(
                            tile,
                            (obj.x - camera.x, obj.y - camera.y),
                        )
                    else:
                        # A rotação é calculada em torno do canto de origem do objeto.
                        angle = -obj.rotation
                        rotated_tile = pygame.transform.rotate(tile, angle)

                        pivot = pygame.Vector2(obj.x, obj.y + tile.get_height())
                        offset = pygame.Vector2(
                            tile.get_width() / 2,
                            -tile.get_height() / 2,
                        )
                        offset = offset.rotate(-angle)
                        center = pivot + offset

                        rect = rotated_tile.get_rect(center=center)
                        rect.x -= camera.x
                        rect.y -= camera.y
                        screen.blit(rotated_tile, rect)
