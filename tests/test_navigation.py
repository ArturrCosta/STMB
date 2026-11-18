import unittest

import pygame

from navigation import NavGrid


class NavGridTests(unittest.TestCase):
    def setUp(self):
        # Mundo de 20 x 10 células com uma parede vertical que deixa só uma passagem em cima.
        self.wall = pygame.Rect(320, 96, 32, 224)
        self.nav = NavGrid([self.wall], 640, 320)

    def test_wall_blocks_cells_but_open_ground_is_free(self):
        self.assertFalse(self.nav.is_free(self.nav.cell_of((336, 200))))
        self.assertTrue(self.nav.is_free(self.nav.cell_of((100, 100))))

    def test_path_goes_around_the_wall_and_never_crosses_it(self):
        path = self.nav.find_path((100, 250), (560, 250))
        self.assertTrue(path)
        self.assertEqual(path[-1], (560, 250))
        probe = pygame.Rect(0, 0, 18, 14)
        for x, y in path:
            probe.center = (round(x), round(y))
            self.assertFalse(probe.colliderect(self.wall), (x, y))
        self.assertTrue(any(y < 96 for _, y in path), "o caminho precisa passar pela abertura de cima")

    def test_no_path_when_goal_is_sealed(self):
        walls = [pygame.Rect(0, 0, 640, 320).inflate(-0, -0)]
        nav = NavGrid([pygame.Rect(320, 0, 32, 320)], 640, 320)
        self.assertEqual(nav.find_path((100, 100), (500, 100)), [])
        self.assertTrue(walls)

    def test_ground_callback_blocks_void_cells(self):
        nav = NavGrid([], 640, 320, ground=lambda col, row: col < 10)
        self.assertFalse(nav.is_free((15, 3)))
        self.assertTrue(nav.is_free((3, 3)))
        point = nav.random_free_point()
        self.assertLess(point[0], 330)

    def test_random_point_respects_minimum_distance(self):
        for _ in range(20):
            point = self.nav.random_free_point(near=(100, 100), min_distance=200)
            self.assertGreaterEqual(((point[0] - 100) ** 2 + (point[1] - 100) ** 2) ** 0.5, 200)


if __name__ == "__main__":
    unittest.main()
