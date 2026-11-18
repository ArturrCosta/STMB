"""Grade de navegação e busca de caminhos (A*) para NPCs e para o agiota.

O mapa de 80 x 60 tiles vira uma grade de células de 32 px. Uma célula só é
"livre" se uma hitbox de personagem centrada nela não encosta em nenhum
obstáculo e se ela tem chão (rua, grama ou terra). Assim o agiota contorna
prédios em vez de ficar preso atrás deles, e os moradores só passeiam por
lugares onde realmente dá para andar.
"""

import heapq
import math
import random


DIAGONAL_COST = math.sqrt(2)
NEIGHBORS = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
    (1, 1, DIAGONAL_COST), (1, -1, DIAGONAL_COST),
    (-1, 1, DIAGONAL_COST), (-1, -1, DIAGONAL_COST),
)


class NavGrid:
    def __init__(self, solid_rects, world_width, world_height, cell=32,
                 body=(18, 14), ground=None):
        """`ground(cx, cy) -> bool` diz se a célula tem chão (opcional)."""
        self.cell = cell
        self.cols = max(1, math.ceil(world_width / cell))
        self.rows = max(1, math.ceil(world_height / cell))
        self.blocked = [[False] * self.cols for _ in range(self.rows)]

        for rect in solid_rects:
            grown = rect.inflate(body[0], body[1])
            first_col = max(0, grown.left // cell - 1)
            last_col = min(self.cols - 1, grown.right // cell + 1)
            first_row = max(0, grown.top // cell - 1)
            last_row = min(self.rows - 1, grown.bottom // cell + 1)
            for row in range(first_row, last_row + 1):
                for col in range(first_col, last_col + 1):
                    center = ((col + 0.5) * cell, (row + 0.5) * cell)
                    if grown.left <= center[0] < grown.right and grown.top <= center[1] < grown.bottom:
                        self.blocked[row][col] = True

        if ground is not None:
            for row in range(self.rows):
                for col in range(self.cols):
                    if not ground(col, row):
                        self.blocked[row][col] = True

    # ------------------------------------------------------------------
    def cell_of(self, point):
        col = min(self.cols - 1, max(0, int(point[0] // self.cell)))
        row = min(self.rows - 1, max(0, int(point[1] // self.cell)))
        return col, row

    def center_of(self, cell):
        return ((cell[0] + 0.5) * self.cell, (cell[1] + 0.5) * self.cell)

    def is_free(self, cell):
        col, row = cell
        return 0 <= col < self.cols and 0 <= row < self.rows and not self.blocked[row][col]

    def nearest_free(self, cell, max_radius=6):
        """Célula livre mais próxima de `cell` (ela mesma, se já for livre)."""
        if self.is_free(cell):
            return cell
        for radius in range(1, max_radius + 1):
            best, best_distance = None, None
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    candidate = (cell[0] + dx, cell[1] + dy)
                    if self.is_free(candidate):
                        distance = dx * dx + dy * dy
                        if best is None or distance < best_distance:
                            best, best_distance = candidate, distance
            if best is not None:
                return best
        return None

    def free_cells(self):
        return [(col, row) for row in range(self.rows) for col in range(self.cols)
                if not self.blocked[row][col]]

    def random_free_point(self, near=None, radius_cells=None, min_distance=0, rng=random):
        """Ponto (em pixels) no centro de uma célula livre, opcionalmente perto/longe de `near`."""
        cells = self.free_cells()
        if not cells:
            return None
        if near is not None:
            near_cell = self.cell_of(near)
            if radius_cells is not None:
                cells = [c for c in cells
                         if abs(c[0] - near_cell[0]) <= radius_cells and abs(c[1] - near_cell[1]) <= radius_cells]
            if min_distance:
                cells = [c for c in cells if math.dist(self.center_of(c), near) >= min_distance]
        if not cells:
            return None
        return self.center_of(rng.choice(cells))

    # ------------------------------------------------------------------
    def find_path(self, start, goal, max_nodes=6000):
        """A* em 8 direções, sem "cortar" quinas. Devolve pontos em pixels.

        O último ponto é exatamente `goal`. Devolve [] se não houver caminho.
        """
        start_cell = self.nearest_free(self.cell_of(start))
        goal_cell = self.nearest_free(self.cell_of(goal))
        if start_cell is None or goal_cell is None:
            return []
        if start_cell == goal_cell:
            return [tuple(goal)]

        def heuristic(cell):
            dx, dy = abs(cell[0] - goal_cell[0]), abs(cell[1] - goal_cell[1])
            return (dx + dy) + (DIAGONAL_COST - 2) * min(dx, dy)

        counter = 0
        open_heap = [(heuristic(start_cell), 0.0, counter, start_cell)]
        best_cost = {start_cell: 0.0}
        parent = {}
        closed = set()
        expanded = 0
        while open_heap and expanded < max_nodes:
            _, cost, _, cell = heapq.heappop(open_heap)
            if cell in closed:
                continue
            if cell == goal_cell:
                break
            closed.add(cell)
            expanded += 1
            for dx, dy, step in NEIGHBORS:
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt in closed or not self.is_free(nxt):
                    continue
                if dx and dy and not (self.is_free((cell[0] + dx, cell[1]))
                                      and self.is_free((cell[0], cell[1] + dy))):
                    continue
                new_cost = cost + step
                if new_cost < best_cost.get(nxt, float("inf")):
                    best_cost[nxt] = new_cost
                    parent[nxt] = cell
                    counter += 1
                    heapq.heappush(open_heap, (new_cost + heuristic(nxt), new_cost, counter, nxt))

        if goal_cell not in parent:
            return []
        cells = [goal_cell]
        while cells[-1] != start_cell:
            cells.append(parent[cells[-1]])
        cells.reverse()
        points = [self.center_of(c) for c in cells[1:]]
        if points:
            points[-1] = tuple(goal)
        return points
