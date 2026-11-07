import os
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from game import Game


class GameRhythmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 720))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        with patch("game.Ranking"):
            self.game = Game()
        self.game._start_new_game()

    def tearDown(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def test_start_draw_finish_and_restart(self):
        game = self.game
        game.active_venue = "bar"
        game._start_rhythm("bar")
        self.assertEqual(game.state, "rhythm")
        self.assertTrue(pygame.mixer.music.get_busy())
        game.draw(pygame.Surface((1280, 720)))
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
        game.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_d))
        game.rhythm.started = time.perf_counter() - 37
        game.update(0)
        self.assertEqual(game.state, "rhythm_result")
        self.assertFalse(pygame.mixer.music.get_busy())
        self.assertEqual(game.songs_performed, 1)
        self.assertEqual(game.rhythm_result["reward"], 0)
        game.draw(pygame.Surface((1280, 720)))
        with patch("game.random.random", return_value=1):
            game._leave_rhythm_result()
        self.assertEqual(game.state, "playing")
        game.active_venue = "bar"
        game._start_rhythm("bar")
        self.assertEqual(game.rhythm.judged, 0)
        game._abandon_rhythm("teste")
        self.assertEqual(game.songs_performed, 1)
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_full_map_perfect_reward(self):
        game = self.game
        initial_money = game.money
        game.active_venue = "bar"
        game._start_rhythm("bar")
        current = [0.0]
        session = game.rhythm
        session.clock = lambda: current[0]
        session.started = 0.0
        events = []
        for note in session.map["notes"]:
            events.append((note["time"], 1, note["lane"]))
            events.append((note["time"] + note["duration"], 0, note["lane"]))
        for at, action, lane in sorted(events, key=lambda event: (event[0], -event[1])):
            current[0] = at
            session.update()
            (session.key_down if action else session.key_up)(lane)
        current[0] = 36.1
        game.update(0)
        self.assertEqual(game.state, "rhythm_result")
        self.assertEqual(game.rhythm_result["accuracy"], 1.0,
                         [(n["time"], n["lane"], n["head"], n["tail"])
                          for n in session.map["notes"] if n["head"] == "Miss" or n["tail"] == "Miss"])
        self.assertEqual(game.rhythm_result["reward"], 350)
        self.assertEqual(game.money, initial_money + 350)
        self.assertGreater(game.score, 0)

    def test_missing_map_returns_without_payment(self):
        game = self.game
        initial_money = game.money
        with patch("game.load_beatmap", side_effect=FileNotFoundError("faltando")), patch("game.logging.error"):
            game._start_rhythm("bar")
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.money, initial_money)
        self.assertEqual(game.songs_performed, 0)

    def test_setup_changes_volume_and_starts_song(self):
        game = self.game
        game._interact({"id": "bar"})
        self.assertEqual(game.state, "rhythm_setup")
        game.draw(pygame.Surface((1280, 720)))
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        with patch("game.save_settings"):
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        self.assertEqual(game.rhythm_settings["volume"], 80)
        game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(game.state, "rhythm")
        self.assertAlmostEqual(pygame.mixer.music.get_volume(), 0.8, delta=0.01)


if __name__ == "__main__":
    unittest.main()
