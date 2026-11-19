import logging

import pygame
import pytmx

# Camadas que formam o chão caminhável da cidade.
WALKABLE_LAYERS = ("ground", "grass", "roads")


class TiledMap:
    def __init__(self, filename):
        self.tmx_data = pytmx.load_pygame(filename)
        self.width = self.tmx_data.width * self.tmx_data.tilewidth
        self.height = self.tmx_data.height * self.tmx_data.tileheight
        self.tile_width = self.tmx_data.tilewidth
        self.tile_height = self.tmx_data.tileheight

        self.solid_rects = []
        self.grass_tiles = set()
        self.ground_tiles = set()
        self._read_collision_data()
        # Só dá para andar na grama e no asfalto: todo o resto do mapa (o "vazio" que os PNGs dos
        # prédios não cobrem) vira parede para o jogador, o Fusca e os NPCs.
        self.void_rects = self._build_void_rects()
        self.solid_rects.extend(self.void_rects)
        self._surface = None  # mapa inteiro pré-renderizado (criado sob demanda)

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

                if layer_name.lower() in WALKABLE_LAYERS:
                    for x, y, gid in layer:
                        if gid:
                            self.ground_tiles.add((x, y))

            elif isinstance(layer, pytmx.TiledObjectGroup) and layer_name.lower() == "buildings":
                # Só os prédios bloqueiam o movimento; itens futuros não serão paredes.
                for obj in layer:
                    if not obj.gid:
                        continue

                    tile = self.tmx_data.get_tile_image_by_gid(obj.gid)
                    if tile:
                        self.solid_rects.append(self._tile_object_rect(obj, tile))

    def _build_void_rects(self):
        """Células sem chão (rua/grama) agrupadas no menor número possível de retângulos."""
        if not self.ground_tiles:
            return []
        cols, rows = self.tmx_data.width, self.tmx_data.height
        runs = {}  # (início, fim) da faixa de colunas -> {"top": linha inicial, "rows": quantidade}
        finished = []
        for row in range(rows):
            spans, col = [], 0
            while col < cols:
                if (col, row) in self.ground_tiles:
                    col += 1
                    continue
                start = col
                while col < cols and (col, row) not in self.ground_tiles:
                    col += 1
                spans.append((start, col))
            current = {}
            for span in spans:  # faixa igual à da linha de cima: continua o mesmo retângulo
                current[span] = runs.pop(span, {"top": row})
            finished.extend((span, info["top"], row) for span, info in runs.items())
            runs = current
        finished.extend((span, info["top"], rows) for span, info in runs.items())
        tw, th = self.tile_width, self.tile_height
        return [pygame.Rect(a * tw, top * th, (b - a) * tw, (bottom - top) * th)
                for (a, b), top, bottom in finished]

    def is_grass_at(self, position):
        tile_x = int(position[0] // self.tile_width)
        tile_y = int(position[1] // self.tile_height)
        return (tile_x, tile_y) in self.grass_tiles

    def is_ground_cell(self, cell_x, cell_y):
        """True se a célula tem chão (rua, grama ou terra); fora do chão é "vazio"."""
        if not self.ground_tiles:
            return True
        return (cell_x, cell_y) in self.ground_tiles

    def draw(self, screen, camera):
        """Desenha só o trecho visível de um mapa pré-renderizado.

        Percorrer todas as 4.800 células e os objetos a cada quadro era o
        maior custo do jogo; agora o mapa inteiro é desenhado uma única vez.
        """
        if self._surface is None:
            self._surface = self._prerender() or False  # False = falhou; não tenta de novo
        if self._surface is False:  # sem memória para o mapa inteiro: desenho direto
            self._draw_direct(screen, camera)
            return
        view = pygame.Rect(int(camera.x), int(camera.y), screen.get_width(), screen.get_height())
        screen.blit(self._surface, (0, 0), area=view)

    def _prerender(self):
        try:
            surface = pygame.Surface((self.width, self.height))
        except (pygame.error, MemoryError) as error:
            logging.error("Não foi possível pré-renderizar o mapa: %s", error)
            return None
        if pygame.display.get_surface() is not None:
            surface = surface.convert()
        surface.fill((38, 43, 45))
        self._draw_direct(surface, _OriginCamera())
        return surface

    def _draw_direct(self, screen, camera):
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


class _OriginCamera:
    """Câmera fixa em (0, 0), usada para desenhar o mapa inteiro de uma vez."""

    x = 0
    y = 0
