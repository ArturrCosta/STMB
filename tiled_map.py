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

    def _tile_object_rect(self, obj, tile, rotated_tile=None):
        """Retorna a área ocupada pelo tile, respeitando a rotação do Tiled.

        A mesma transformação é usada na renderização e na colisão para que
        o obstáculo coincida com a posição visual do prédio no mapa.
        """
        if obj.rotation == 0:
            return pygame.Rect(
                round(obj.x),
                round(obj.y),
                tile.get_width(),
                tile.get_height(),
            )

        angle = -obj.rotation
        if rotated_tile is None:
            rotated_tile = pygame.transform.rotate(tile, angle)

        # O tile object do Tiled gira em torno do ponto de origem usado
        # pelo desenho atual: o canto inferior esquerdo da imagem original.
        pivot = pygame.Vector2(obj.x, obj.y + tile.get_height())
        offset = pygame.Vector2(
            tile.get_width() / 2,
            -tile.get_height() / 2,
        )
        offset = offset.rotate(-angle)
        center = pivot + offset

        return rotated_tile.get_rect(center=center)

    def _read_collision_data(self):
        """Lê a camada Collision e transforma todos os prédios em obstáculos."""
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
                    if not obj.gid:
                        continue

                    tile = self.tmx_data.get_tile_image_by_gid(obj.gid)
                    if tile:
                        self.solid_rects.append(self._tile_object_rect(obj, tile))

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

                    # Usa a mesma geometria calculada para a colisão.
                    if obj.rotation == 0:
                        screen.blit(
                            tile,
                            (obj.x - camera.x, obj.y - camera.y),
                        )
                    else:
                        rotated_tile = pygame.transform.rotate(tile, -obj.rotation)
                        rect = self._tile_object_rect(obj, tile, rotated_tile)
                        rect.x -= camera.x
                        rect.y -= camera.y
                        screen.blit(rotated_tile, rect)
