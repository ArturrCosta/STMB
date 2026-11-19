"""Testes de integração do jogo (sem janela real: SDL "dummy").

Os testes não leem nem gravam o ranking, as configurações de ritmo ou o save
do jogador: tudo isso é substituído por valores/arquivos temporários.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import savegame
from game import DIFFICULTIES, HENCHMEN_PER_MISS, SETTINGS_ROWS, VIEW_SIZE, VENUES, Game
from ranking import Ranking
from traps import Trap
from npc import Capanga
from rhythm import DEFAULT_SETTINGS


class GameTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 720))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.audio = MagicMock()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patches = [
            patch("game.Ranking", side_effect=lambda: Ranking(Path(self.tmp.name) / "ranking.db")),
            patch("game.load_settings", side_effect=lambda: DEFAULT_SETTINGS.copy()),
            patch("game.save_settings"),
            patch("game.AudioManager", return_value=self.audio),
            patch.object(savegame, "SAVE_PATH", Path(self.tmp.name) / "save.json"),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.game = Game()
        self.game._start_new_game()
        self.game.clock_minutes = 13 * 60  # todos os palcos com horário aberto exceto a casa de shows
        self.surface = pygame.Surface((1280, 720))

    def tearDown(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def key(self, key):
        self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))


class RhythmTests(GameTestCase):
    def test_start_draw_finish_and_restart(self):
        game = self.game
        game.active_venue = "bar"
        game._start_rhythm("bar")
        self.assertEqual(game.state, "rhythm")
        self.assertTrue(pygame.mixer.music.get_busy())
        game.draw(self.surface)
        self.key(pygame.K_d)
        game.handle_event(pygame.event.Event(pygame.KEYUP, key=pygame.K_d))
        game.rhythm.started = time.perf_counter() - (game.rhythm.map["duration"] + 1)
        game.update(0)
        self.assertEqual(game.state, "rhythm_result")
        self.assertFalse(pygame.mixer.music.get_busy())
        self.assertEqual(game.songs_performed, 1)
        self.assertEqual(game.rhythm_result["reward"], 0)
        game.draw(self.surface)
        with patch("game.random.random", return_value=1):
            game._leave_rhythm_result()
        self.assertEqual(game.state, "playing")
        game.active_venue = "bar"
        game._start_rhythm("bar")
        self.assertEqual(game.rhythm.judged, 0)
        game._abandon_rhythm("teste")
        self.assertEqual(game.songs_performed, 1)
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_each_venue_plays_its_own_song(self):
        expected = {"bar": "Música 1", "fair": "Música 2", "concert": "Cidade em Pulso"}
        for venue_id, song_title in expected.items():
            self.assertEqual(VENUES[venue_id]["song_title"], song_title)
        self.assertEqual(VENUES["bar"]["song"], "musica1.json")
        self.assertEqual(VENUES["fair"]["song"], "musica2.json")
        self.assertEqual(VENUES["concert"]["song"], "cidade_em_pulso.json")
        for venue_id in expected:
            self.game.active_venue = venue_id
            self.game._start_rhythm(venue_id)
            self.assertEqual(self.game.state, "rhythm", venue_id)
            self.assertTrue(str(self.game.rhythm.map["audio"]).endswith(
                VENUES[venue_id]["song"].replace(".json", ".wav")), venue_id)
            self.game.draw(self.surface)
            self.game._abandon_rhythm("teste")
            self.game.draw(self.surface)

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
        current[0] = session.map["duration"] + 0.1
        game.update(0)
        self.assertEqual(game.state, "rhythm_result")
        self.assertEqual(game.rhythm_result["accuracy"], 1.0,
                         [(n["time"], n["lane"], n["head"], n["tail"])
                          for n in session.map["notes"] if n["head"] == "Miss" or n["tail"] == "Miss"])
        self.assertEqual(game.rhythm_result["reward"], 280 * 4)  # cachê cheio x4 (tudo Perfect)
        self.assertEqual(game.money, initial_money + 280 * 4)
        self.assertGreater(game.score, 0)

    def test_crowd_boos_the_show_in_phase_two(self):
        game = self.game
        initial_money = game.money
        game.inventory = ["chapeu"]
        game._interact({"id": "fair"})
        self.assertEqual(game.state, "venue_info")
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "rhythm")
        self.assertEqual(game.phase, 2)
        session = game.rhythm
        self.assertTrue(session.crowd_meter)
        current = [0.0]
        session.clock = lambda: current[0]
        session.started = 0.0
        while game.state == "rhythm" and current[0] < session.map["duration"]:
            current[0] += 0.25  # ninguém aperta nada: as notas viram Miss
            game.update(0)
            game.draw(self.surface)
        self.assertEqual(game.state, "rhythm_result")
        self.assertTrue(game.rhythm_result["failed"])
        self.assertEqual(game.rhythm_result["reward"], 0)
        self.assertEqual(game.money, initial_money)
        game.draw(self.surface)

    def test_bar_has_no_crowd_meter(self):
        self.game.active_venue = "bar"
        self.game._start_rhythm("bar")
        self.assertFalse(self.game.rhythm.crowd_meter)

    def test_missing_map_returns_without_payment(self):
        game = self.game
        initial_money = game.money
        with patch("game.load_beatmap", side_effect=FileNotFoundError("faltando")), patch("game.logging.error"):
            game._start_rhythm("bar")
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.money, initial_money)
        self.assertEqual(game.songs_performed, 0)

    def test_venue_info_screen_confirm_and_cancel(self):
        game = self.game
        game._interact({"id": "bar"})
        self.assertEqual(game.state, "venue_info")
        self.assertTrue(game.venue_info["ok"])
        self.assertGreater(game.venue_info["notes"], 0)
        game.draw(self.surface)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "playing")
        self.assertIsNone(game.active_venue)
        game._interact({"id": "bar"})
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "rhythm")
        self.assertAlmostEqual(pygame.mixer.music.get_volume(), game.rhythm_settings["volume"] / 100, delta=0.01)

    def test_venue_info_buttons_work_with_the_mouse(self):
        game = self.game
        game._interact({"id": "bar"})
        game.draw(self.surface)
        cancel = [rect for rect, action in game.buttons if action == game._cancel_venue][0]
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=cancel.center, button=1))
        self.assertEqual(game.state, "playing")
        game._interact({"id": "bar"})
        game.draw(self.surface)
        enter = [rect for rect, action in game.buttons if action == game._confirm_venue][0]
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=enter.center, button=1))
        self.assertEqual(game.state, "rhythm")

    def test_unavailable_song_is_explained_and_blocks_entry(self):
        game = self.game
        with patch("game.load_beatmap", side_effect=ValueError("áudio quebrado")), patch("game.logging.exception"):
            game._interact({"id": "bar"})
        self.assertFalse(game.venue_info["ok"])
        game.draw(self.surface)
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "venue_info")  # não entra sem música
        self.audio.play.assert_any_call("error")

    def test_unexpected_error_starting_the_song_is_logged_not_fatal(self):
        game = self.game
        with patch("game.RhythmSession", side_effect=RuntimeError("boom")), patch("game.logging.exception") as log:
            game._start_rhythm("bar")
        self.assertEqual(game.state, "playing")
        log.assert_called()
        self.assertIn("RuntimeError", game.toast_text)

    def test_locked_venue_needs_clothes(self):
        self.game.inventory = []
        self.game._interact({"id": "concert"})
        self.assertEqual(self.game.state, "playing")


class SoundTests(GameTestCase):
    def test_actions_play_the_right_effects(self):
        game = self.game
        game.money = 10 ** 5
        game.shop_stock = ["chapeu"]
        game.state = "shop"
        game._buy_selected_item()
        self.audio.play.assert_any_call("spend")
        game.money = 0
        game.shop_stock = ["blazer"]
        game._buy_selected_item()
        self.audio.play.assert_any_call("error")
        game._start_chase()
        self.audio.play.assert_any_call("alarm")
        game._finish_game("vitória", "teste")
        self.audio.play.assert_any_call("win")

    def test_ambient_follows_the_clock_and_screen(self):
        game = self.game
        game.clock_minutes = 12 * 60
        game.update(0.016)
        day, night = self.audio.set_ambient.call_args[0]
        self.assertGreater(day, 0.9)
        self.assertEqual(night, 0)
        game.clock_minutes = 22 * 60
        game.update(0.016)
        day, night = self.audio.set_ambient.call_args[0]
        self.assertEqual(day, 0)
        self.assertGreater(night, 0.9)
        game.state = "rhythm"
        game.rhythm = None
        game._update_ambient(0.016)
        self.assertEqual(self.audio.set_ambient.call_args[0], (0, 0))


class AudioManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_all_sound_files_load_and_play(self):
        from audio import AMBIENCES, EFFECTS, AudioManager
        manager = AudioManager()
        self.assertTrue(manager.enabled)
        self.assertEqual(set(manager.sounds), set(EFFECTS + AMBIENCES))
        for name in EFFECTS:
            manager.play(name)
        manager.set_ambient(1, 0)
        for _ in range(30):
            manager.update(0.1)
        manager.toggle_mute()
        manager.update(0.1)
        manager.stop_all()

    def test_missing_folder_is_logged_and_silent(self):
        from audio import AudioManager
        with patch("audio.logging.error") as error:
            manager = AudioManager(folder=Path(tempfile.gettempdir()) / "nao_existe_stmb")
        self.assertFalse(manager.enabled)
        manager.play("cash")  # não pode lançar exceção
        manager.update(0.1)
        error.assert_called()


class DayRhythmTests(GameTestCase):
    def test_result_screen_goes_straight_back_to_the_city(self):
        game = self.game
        game.active_venue = "bar"
        game._start_rhythm("bar")
        game.rhythm.started = time.perf_counter() - (game.rhythm.map["duration"] + 1)
        game.update(0)
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "playing")  # sem evento do cobrador

    def test_repeating_a_venue_pays_less_but_is_allowed(self):
        game = self.game
        self.assertEqual(game._pay_factor("bar"), 1.0)
        game.shows_today = {"bar": 2}
        self.assertAlmostEqual(game._pay_factor("bar"), 0.6)
        self.assertTrue(game._venue_status("bar")[0])
        game.shows_today = {"bar": 9}
        self.assertEqual(game._pay_factor("bar"), 0.5)
        game.money = 10 ** 5
        game._pay_now()
        game._advance_day(slept=True)
        self.assertEqual(game.shows_today, {})

    def test_opening_hours(self):
        game = self.game
        game.clock_minutes = 9 * 60
        self.assertFalse(game._venue_status("bar")[0])
        self.assertTrue(game._venue_status("fair")[0])
        game.clock_minutes = 23 * 60
        self.assertTrue(game._venue_status("bar")[0])
        self.assertFalse(game._venue_status("fair")[0])
        game.inventory = ["chapeu", "calca", "blazer"]
        self.assertTrue(game._venue_status("concert")[0])

    def test_finishing_a_show_counts_the_venue(self):
        game = self.game
        for expected in (1, 2):
            game.active_venue = "bar"
            game._start_rhythm("bar")
            game.rhythm.started = time.perf_counter() - (game.rhythm.map["duration"] + 1)
            game.update(0)
            self.assertEqual(game.shows_today["bar"], expected)
            game._leave_rhythm_result()

    def test_late_reminders_and_home_arrow(self):
        game = self.game
        game.clock_minutes = 22 * 60 + 1
        game.update(0.016)
        self.assertIn("late", game.reminders)
        self.assertTrue(game._should_go_home())
        game.draw(self.surface)

    def test_sleeping_early_gives_rest_and_staying_up_tires(self):
        game = self.game
        game.money = 10 ** 5
        game.clock_minutes = 21 * 60
        game._pay_now()
        game._advance_day(slept=True)
        self.assertTrue(game.rested_day)
        self.assertFalse(game.tired_day)
        game._pay_now()
        game.clock_minutes = 27 * 60
        game.update(0.016)
        self.assertTrue(game.tired_day)
        self.assertFalse(game.rested_day)

    def test_daylight_tint_changes_with_the_clock(self):
        game = self.game
        game.clock_minutes = 12 * 60
        self.assertEqual(game._daylight()[3], 0)
        game.clock_minutes = 23 * 60
        self.assertGreater(game._daylight()[3], 80)

    def test_muggers_can_steal_clothes(self):
        game = self.game
        game.money = 1000
        game.inventory = ["chapeu", "fusca"]
        game.clock_minutes = 22 * 60 + 5
        game.update(0.016)
        with patch("game.random.random", return_value=0.1):
            game._robbed(game.muggers[0])
        self.assertEqual(game.inventory, ["fusca"])  # só roupa: o Fusca não é roubado
        self.assertIn("chapéu", game.toast_text)
        game.player.stunned_timer = 0
        game.inventory = ["calca"]
        with patch("game.random.random", return_value=0.9):
            game._robbed(game.muggers[0])
        self.assertEqual(game.inventory, ["calca"])

    def test_muggers_appear_at_night_and_rob(self):
        game = self.game
        game.money = 1000
        game.clock_minutes = 22 * 60 + 5
        game.update(0.016)
        self.assertEqual(len(game.muggers), 3)  # Normal
        mugger = game.muggers[0]
        mugger.chasing = True
        mugger.position.update(game.player.hitbox.center)
        mugger._sync_hitbox()
        game.update(0.016)
        self.assertEqual(game.money, 600)
        self.assertNotIn(mugger, game.muggers)
        self.assertGreater(game.player.stun_duration, 0)
        game.draw(self.surface)
        game._advance_day(slept=True)
        self.assertEqual(game.muggers, [])


class CarTests(GameTestCase):
    def buy_car(self):
        game = self.game
        game.money = 5000
        game.shop_stock = ["fusca"]
        game.shop_index = 0
        game._buy_selected_item()
        self.assertIsNotNone(game.car)
        return game.car

    def test_buy_enter_drive_and_park(self):
        game = self.game
        car = self.buy_car()
        game.state = "playing"
        game._place_player_feet(car.position + pygame.Vector2(0, 30))
        self.assertTrue(game._car_nearby())
        self.key(pygame.K_e)
        self.assertTrue(game.driving)
        start = pygame.Vector2(car.position)
        # O Fusca nasce na rua ao lado da loja (a parede fica à direita): dirige para a esquerda.
        with patch.object(game, "_input_direction", return_value=pygame.Vector2(-1, 0)):
            for _ in range(40):
                game.update(0.05)
        self.assertNotEqual(car.position, start)
        game.draw(self.surface)
        for _ in range(20):
            game.update(0.05)  # solta o acelerador: freia
        parked = pygame.Vector2(car.position)
        self.key(pygame.K_e)
        self.assertFalse(game.driving)
        self.assertLess(parked.distance_to(game.player.hitbox.center), 70)
        for _ in range(10):
            game.update(0.05)
        self.assertEqual(car.position, parked)  # ficou onde foi deixado

    def test_grass_slows_the_car_by_a_quarter(self):
        car = self.buy_car()
        self.assertAlmostEqual(car.max_speed() / 340, 1.0)
        car.on_grass = True
        self.assertAlmostEqual(car.max_speed() / 340, 0.75)

    def test_car_is_saved_and_restored(self):
        game = self.game
        car = self.buy_car()
        car.position.update(1000, 1000)
        game.state = "playing"
        game._autosave()
        game.car = None
        game.state = "menu"
        game.has_save = True
        game.menu_options = game._build_menu()
        game.menu_index = game.menu_options.index("Continuar")
        self.key(pygame.K_RETURN)
        self.assertIsNotNone(game.car)
        self.assertEqual(tuple(game.car.position), (1000, 1000))

    def test_muggers_ignore_a_driving_player(self):
        game = self.game
        self.buy_car()
        game.driving = True
        game.money = 1000
        game.clock_minutes = 22 * 60 + 5
        game.update(0.016)
        mugger = game.muggers[0]
        mugger.position.update(game.car.position)
        mugger._sync_hitbox()
        game.update(0.016)
        self.assertEqual(game.money, 1000)


class ComboTests(GameTestCase):
    def play_perfect(self, venue="bar"):
        game = self.game
        game.active_venue = venue
        game._start_rhythm(venue)
        current = [0.0]
        session = game.rhythm
        session.clock = lambda: current[0]
        session.started = 0.0
        events = []
        for note in session.map["notes"]:
            events.append((note["time"], 1, note["lane"]))
            events.append((note["time"] + note["duration"], 0, note["lane"]))
        popups = 0
        for at, action, lane in sorted(events, key=lambda event: (event[0], -event[1])):
            current[0] = at
            game.update(0)
            popups = max(popups, len(game.popups))
            (session.key_down if action else session.key_up)(lane)
        current[0] = session.map["duration"] + 0.1
        game.update(0)
        return popups

    def test_multiplier_popups_and_perfect_bonus(self):
        popups = self.play_perfect()
        game = self.game
        self.assertGreater(popups, 0)
        self.assertEqual(game.rhythm_result["bonus"][1], 4.0)  # tudo Perfect = x4
        self.assertEqual(game.rhythm_result["reward"], 280 * 4)
        game.draw(self.surface)

    def test_effects_draw_during_the_show(self):
        game = self.game
        game.active_venue = "bar"
        game._start_rhythm("bar")
        game._add_popup("2X", (124, 217, 169), big=True, sub_text="MULTIPLICADOR!")
        game._burst((124, 217, 169), 20)
        game.draw(self.surface)
        for _ in range(40):
            game._update_effects(0.05)
        self.assertEqual(game.popups, [])
        self.assertEqual(game.sparks, [])


class CityTests(GameTestCase):
    def test_every_place_is_reachable_after_the_new_buildings(self):
        game = self.game
        from game import ZONES
        start = game.player.hitbox.center
        for zone in ZONES:
            path = game.nav.find_path(start, zone["position"])
            self.assertTrue(path, zone["id"])
            probe = pygame.Rect(0, 0, 18, 14)
            free_spot = False
            for dx in range(-40, 41, 8):
                for dy in range(-40, 41, 8):
                    probe.center = (zone["position"][0] + dx, zone["position"][1] + dy)
                    if not any(probe.colliderect(r) for r in game.tiled_map.solid_rects):
                        free_spot = True
            self.assertTrue(free_spot, f"{zone['id']}: sem lugar livre perto do ponto de interação")

    def test_new_game_starts_broke_and_slower(self):
        game = self.game
        self.assertEqual(game.money, 0)
        self.assertEqual(game.debt, 1000)
        self.assertEqual(game.player.base_speed, 225)  # Normal: 300 -> 225 (-25%)
        self.assertEqual(DIFFICULTIES["Normal"]["agiota_speed"], 148)  # 185 -> 148 (-20%)

    def test_camera_is_zoomed_in(self):
        game = self.game
        self.assertEqual((game.camera.width, game.camera.height), VIEW_SIZE)
        self.assertLess(VIEW_SIZE[0], 1280)
        game.player.reset_position((1280, 900))
        game.draw(self.surface)
        self.assertAlmostEqual(game.zoom, 1280 / VIEW_SIZE[0])
        x, y = game._to_screen(game.player.rect.center)
        self.assertAlmostEqual(x, 640, delta=2)
        self.assertAlmostEqual(y, 360, delta=2)

    def test_new_buildings_are_solid(self):
        game = self.game
        for point in ((500, 300), (250, 1450), (800, 1800), (1450, 1500), (2250, 800)):
            self.assertTrue(any(r.collidepoint(point) for r in game.tiled_map.solid_rects), point)


    def test_only_grass_and_road_are_walkable(self):
        game = self.game
        tmap = game.tiled_map
        for y in range(tmap.tmx_data.height):
            for x in range(tmap.tmx_data.width):
                cell = pygame.Rect(x * 32 + 8, y * 32 + 8, 16, 16)
                blocked = any(cell.colliderect(r) for r in tmap.solid_rects)
                if (x, y) not in tmap.ground_tiles:
                    self.assertTrue(blocked, f"célula sem chão ({x},{y}) deveria ser parede")
        # Rua e grama continuam livres, e o jogador não consegue entrar no vazio andando.
        road = (640, 1100)   # avenida vertical
        grass = (1000, 800)
        for point in (road, grass):
            probe = pygame.Rect(0, 0, 18, 14)
            probe.center = point
            self.assertFalse(any(probe.colliderect(r) for r in tmap.solid_rects), point)
        # Andando em todas as direções por um bom tempo, os pés nunca saem da rua/grama.
        game.player.reset_position((road[0], road[1] - 15))
        directions = (pygame.K_a, pygame.K_w, pygame.K_d, pygame.K_s, pygame.K_a, pygame.K_s)
        try:
            for key in directions:
                pygame.key.pressed.add(key)
                for _ in range(120):
                    game.player.update(0.05, tmap.solid_rects, tmap.width, tmap.height)
                    box = game.player.hitbox
                    for corner in (box.topleft, (box.right - 1, box.top), (box.left, box.bottom - 1),
                                   (box.right - 1, box.bottom - 1)):
                        cell = (min(corner[0], tmap.width - 1) // 32, min(corner[1], tmap.height - 1) // 32)
                        self.assertIn(cell, tmap.ground_tiles, corner)
                pygame.key.pressed.discard(key)
        finally:
            pygame.key.pressed.clear()

    def test_player_saved_inside_a_wall_is_moved_out_on_load(self):
        game = self.game
        game.player.reset_position((1200, 1700))     # dentro do bloco vazio ao sul da avenida
        self.assertTrue(any(game.player.hitbox.colliderect(r) for r in game.tiled_map.solid_rects))
        game._rescue_from_walls()
        self.assertFalse(any(game.player.hitbox.colliderect(r) for r in game.tiled_map.solid_rects))


class SettingsTests(GameTestCase):
    def test_settings_screen_changes_and_saves(self):
        game = self.game
        game.state = "settings"
        game.settings_index = SETTINGS_ROWS.index("audio_offset")
        self.key(pygame.K_RIGHT)
        self.assertEqual(game.rhythm_settings["audio_offset"], 10)
        game.settings_index = SETTINGS_ROWS.index("sfx_volume")
        self.key(pygame.K_LEFT)
        self.assertEqual(game.rhythm_settings["sfx_volume"], 60)
        self.audio.set_volume.assert_called_with(0.6)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "menu")

    def test_default_lane_keys_are_d_f_j_k(self):
        game = self.game
        self.assertEqual(game.lane_codes, (pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k))
        self.assertEqual(game.lane_labels, ["D", "F", "J", "K"])

    def test_rebind_lane_keys_from_settings(self):
        game = self.game
        game.state = "settings"
        game.settings_index = SETTINGS_ROWS.index("keys")
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "rebind")
        game.draw(self.surface)
        self.key(pygame.K_RETURN)          # tecla reservada: recusada, continua na pista 1
        self.assertEqual(game.rebind["slot"], 0)
        for code in (pygame.K_9, pygame.K_0, pygame.K_MINUS, pygame.K_EQUALS):
            game.draw(self.surface)
            self.key(code)
        self.assertEqual(game.state, "settings")
        self.assertEqual(game.lane_codes, (pygame.K_9, pygame.K_0, pygame.K_MINUS, pygame.K_EQUALS))
        self.assertEqual(game.lane_labels, ["9", "0", "-", "="])
        self.assertEqual(game.rhythm_settings["lane_keys"], ["9", "0", "-", "="])
        # O ritmo passa a responder às novas teclas e ignora as antigas.
        game.active_venue = "bar"
        game._start_rhythm("bar")
        game.rhythm.pressed.clear()
        self.key(pygame.K_d)
        self.assertNotIn(0, game.rhythm.pressed)
        self.key(pygame.K_9)
        self.assertIn(0, game.rhythm.pressed)
        game.draw(self.surface)

    def test_rebind_swaps_a_key_already_used_and_can_be_cancelled(self):
        game = self.game
        game._start_rebind()
        self.key(pygame.K_f)               # F estava na pista 2: ela recebe o D
        self.assertEqual(game.rebind["keys"][:2], ["f", "d"])
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "settings")
        self.assertEqual(game.rhythm_settings["lane_keys"], ["d", "f", "j", "k"])

    def test_restore_default_lane_keys(self):
        game = self.game
        self.assertTrue(game._set_lane_keys(["9", "0", "-", "="]))
        self.assertFalse(game._set_lane_keys(["a", "a", "b", "c"]))   # repetidas
        self.assertFalse(game._set_lane_keys(["a", "b", "c", "tecla-inexistente"]))
        self.assertEqual(game.rhythm_settings["lane_keys"], ["9", "0", "-", "="])
        game.state = "settings"
        game.settings_index = SETTINGS_ROWS.index("keys_reset")
        self.key(pygame.K_RETURN)
        self.assertEqual(game.lane_labels, ["D", "F", "J", "K"])

    def test_calibration_measures_the_delay(self):
        game = self.game
        now = [100.0]
        game.clock_fn = lambda: now[0]
        game.state = "settings"
        game._start_calibration()
        self.assertEqual(game.state, "calibrate")
        while not game.calibration["done"]:
            game.update(0.01)
            beats = game.calibration["beats"]
            if beats and now[0] - beats[-1] >= 0.08 and len(game.calibration["taps"]) < len(beats):
                self.key(pygame.K_SPACE)  # o jogador aperta 80 ms depois de ouvir
            now[0] += 0.01
            game.draw(self.surface)
        self.assertAlmostEqual(game.calibration["result"], 80, delta=12)
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "settings")
        self.assertAlmostEqual(game.rhythm_settings["audio_offset"], 80, delta=12)
        self.assertEqual(game.rhythm_settings["input_offset"], 0)

    def test_calibration_without_taps_asks_to_retry(self):
        game = self.game
        now = [0.0]
        game.clock_fn = lambda: now[0]
        game._start_calibration()
        while not game.calibration["done"]:
            now[0] += 0.05
            game.update(0.05)
        self.assertIsNone(game.calibration["result"])
        game.draw(self.surface)
        self.key(pygame.K_RETURN)
        self.assertFalse(game.calibration["done"])  # recomeçou


class DebtAndChaseTests(GameTestCase):
    def test_missed_payments_bring_more_henchmen_but_never_end_the_game(self):
        game = self.game
        game.money = 0
        for missed in range(1, 5):
            game._advance_day(slept=True)
            self.assertEqual(game.state, "chase")
            self.assertEqual(game.missed_payments, missed)
            self.assertEqual(len(game.hunters), 1 + HENCHMEN_PER_MISS * (missed - 1))
            self.assertEqual(sum(isinstance(h, Capanga) for h in game.hunters), HENCHMEN_PER_MISS * (missed - 1))
            game.draw(self.surface)
            game._resolve_chase(caught=False)
            self.assertEqual(game.state, "playing")

    def test_hunters_start_from_different_corners(self):
        game = self.game
        game.missed_payments = 2
        game._start_chase()
        positions = [h.position for h in game.hunters]
        self.assertEqual(len(positions), 3)
        for i, a in enumerate(positions):
            for b in positions[i + 1:]:
                self.assertGreater(a.distance_to(b), 400)

    def test_paying_is_a_choice(self):
        game = self.game
        game.money = 1000
        self.key(pygame.K_b)
        self.assertTrue(game.paid_next)
        self.assertEqual(game.money, 700)          # cobrança do dia 2: R$ 300
        self.key(pygame.K_b)                       # não paga duas vezes
        self.assertEqual(game.money, 700)
        game._advance_day(slept=True)
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.money, 700)
        self.assertEqual(game.debt, 1000 * 3 // 2 - 300)
        self.assertFalse(game.paid_next)
        self.assertEqual(game.stats["payments"], 1)
        # Mesmo com dinheiro de sobra, quem não paga é caçado.
        game.money = 10 ** 5
        game._advance_day(slept=True)
        self.assertEqual(game.state, "chase")
        self.assertEqual(game.missed_payments, 1)
        self.assertEqual(game.money, 10 ** 5)

    def test_pay_button_in_the_hud_and_in_the_sleep_screen(self):
        game = self.game
        game.money = 1000
        game.state = "playing"
        game.draw(self.surface)
        button = next(rect for rect, action in game.buttons
                      if getattr(action, "__name__", "") == "_pay_now")
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=button.center, button=1))
        self.assertTrue(game.paid_next)
        game.draw(self.surface)
        # Na tela de dormir também dá para pagar com B.
        game.paid_next = False
        game.money = 1000
        game.state = "sleep_confirm"
        game.draw(self.surface)
        self.key(pygame.K_b)
        self.assertTrue(game.paid_next)
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.day, 2)

    def test_evening_reminder_to_pay(self):
        game = self.game
        game.money = 1000
        game.state = "playing"
        game.clock_minutes = 20 * 60 + 1
        game.update(0.016)
        self.assertIn("pay", game.reminders)
        self.assertIn("aperte B", game.toast_text)

    def type_text(self, text):
        for char in text:
            self.game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=char))

    def test_secret_code_gives_unlimited_money(self):
        game = self.game
        game.state = "playing"
        game.money = 120
        self.type_text("grxgrana")
        self.assertTrue(game.cheat_money)
        self.assertGreaterEqual(game.money, 999_999)
        game.shop_stock, game.shop_index = ["arma"], 0
        game._buy_selected_item()
        game.update(0.016)
        self.assertGreaterEqual(game.money, 999_999)          # gastou e encheu de novo
        self.assertIn("arma", game.inventory)
        game._finish_game("vitória", "teste", ending="trem")
        self.assertLess(game.victory_bonus, 2000)             # o dinheiro do código não vira pontos

    def test_secret_code_toggles_off(self):
        game = self.game
        game.state = "playing"
        game.money = 120
        self.type_text("GRANA")
        self.type_text("grana")
        self.assertFalse(game.cheat_money)
        self.assertEqual(game.money, 120)

    def test_not_enough_money_cannot_pay(self):
        game = self.game
        game.money = 100
        self.assertFalse(game._pay_now())
        self.assertFalse(game.paid_next)
        self.audio.play.assert_any_call("error")

    def test_train_is_a_victory(self):
        game = self.game
        from game import ZONES
        game.inventory = ["passagem"]
        game._interact(next(zone for zone in ZONES if zone["id"] == "station"))
        self.assertEqual((game.state, game.end_result, game.end_ending), ("end_name", "vitória", "trem"))

    def test_being_caught_ends_the_game(self):
        game = self.game
        game.missed_payments = 2
        game._start_chase()
        capanga = game.hunters[1]
        capanga.position.update(game.player.hitbox.center)
        capanga._sync_hitbox()
        game.update(0.016)
        self.assertEqual(game.state, "end_name")
        self.assertEqual(game.end_result, "derrota")
        self.assertIn("capanga", game.end_reason)

    def test_chase_timeout_escapes_and_can_be_paused(self):
        game = self.game
        game._start_chase()
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "paused")
        before = game.chase_timer
        game.update(1.0)
        self.assertEqual(game.chase_timer, before)  # pausado: o tempo não corre
        game.draw(self.surface)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "chase")
        game.chase_timer = 0.01
        for hunter in game.hunters:
            hunter.position.update(game.player.hitbox.center[0] + 900, game.player.hitbox.center[1])
            hunter._sync_hitbox()
        game.update(0.05)
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.hunters, [])

    def test_agiota_gets_closer_following_a_path(self):
        game = self.game
        game._start_chase()
        agiota = game.hunters[0]
        start = agiota.position.distance_to(game.player.rect.center)
        for _ in range(120):
            game.update(0.05)
            if game.state != "chase":
                break
        self.assertTrue(game.state != "chase" or agiota.position.distance_to(game.player.rect.center) < start)
        game.draw(self.surface)

    def test_hunters_aim_ahead_of_a_running_player(self):
        game = self.game
        game.missed_payments = 2
        game._start_chase()
        player = pygame.Vector2(1280, 860)
        running = pygame.Vector2(225, 0)               # correndo para a direita
        roles = {hunter.role for hunter in game.hunters}
        self.assertIn("intercept", roles)
        self.assertIn("cutoff", roles)
        for hunter in game.hunters:
            hunter.position.update(player.x - 300, player.y + 120)  # vindo de trás
            target = game._hunter_target(hunter, pygame.Vector2(player), pygame.Vector2(running))
            self.assertGreater(target.x, player.x + 20, hunter.role)  # todos miram à frente
        intercept = next(h for h in game.hunters if h.role == "intercept")
        target = game._hunter_target(intercept, pygame.Vector2(player), pygame.Vector2(running))
        self.assertGreater(target.x, player.x + 150)                 # bem à frente
        # Parado (ou colado), vão direto no jogador.
        self.assertEqual(game._hunter_target(intercept, pygame.Vector2(player), pygame.Vector2()), player)

    def test_hunters_have_different_roles_and_do_not_stack(self):
        game = self.game
        game.missed_payments = 3
        game._start_chase()
        roles = {hunter.role for hunter in game.hunters}
        self.assertGreaterEqual(len(roles), 3)
        for hunter in game.hunters:  # todos no mesmo ponto
            hunter.position.update(1280, 640)
            hunter._sync_hitbox()
        for _ in range(10):
            game._separate_hunters()
        positions = [h.position for h in game.hunters]
        self.assertGreater(min(a.distance_to(b) for i, a in enumerate(positions) for b in positions[i + 1:]), 5)

    def _far_hunter(self, game, index=0, dx=400):
        hunter = game.hunters[index]
        center = game.player.hitbox.center
        hunter.position.update(center[0] + dx, center[1])
        hunter._sync_hitbox()
        return hunter

    def test_hunters_drop_traps_every_couple_of_seconds(self):
        game = self.game
        game.missed_payments = 2
        game._start_chase()
        self.assertEqual(game.traps, [])
        for index in range(len(game.hunters)):
            self._far_hunter(game, index, dx=200 + index * 80)
            game.hunters[index].trap_timer = 0.0
        game._update_traps(0.01, game._body())
        self.assertEqual(len(game.traps), len(game.hunters))  # um de cada
        interval = DIFFICULTIES[game.difficulty]["trap_interval"]
        self.assertEqual(interval, 2.0)
        for hunter in game.hunters:
            self.assertTrue(0.85 * interval - 0.01 <= hunter.trap_timer <= 1.2 * interval)
        # Caçador colado no jogador não larga armadilha (ele vai é pegar).
        close = game.hunters[0]
        close.position.update(game.player.hitbox.center[0] + 30, game.player.hitbox.center[1])
        close._sync_hitbox()
        close.trap_timer = 0.0
        before = len(game.traps)
        game._update_traps(0.01, game._body())
        self.assertEqual(len(game.traps), before)
        # Somem sozinhas depois de um tempo.
        for _ in range(110):
            for hunter in game.hunters:
                hunter.trap_timer = 99
            game._update_traps(0.1, game._body())
        self.assertEqual(game.traps, [])

    def test_trap_paralyzes_for_one_second_only_after_arming(self):
        game = self.game
        game._start_chase()
        hunter = self._far_hunter(game)
        hunter.trap_timer = 0.0
        game._update_traps(0.01, game._body())
        trap = game.traps[0]
        hunter.trap_timer = 99
        # Ainda caindo (não armada): pisar em cima não prende.
        game._place_player_feet(trap.position)
        game._update_traps(0.01, game._body())
        self.assertEqual(game.player.stunned_timer, 0)
        game.draw(self.surface)
        game._update_traps(0.5, game._body())
        self.assertAlmostEqual(game.player.stunned_timer, 1.0)
        self.assertEqual(game.stun_label, "PRESO")
        self.assertNotIn(trap, game.traps)
        self.audio.play.assert_any_call("trap")
        game.draw(self.surface)
        # Preso: não anda mesmo apertando as teclas, e solta depois de 1 s.
        start = pygame.Vector2(game.player.rect.topleft)
        pygame.key.pressed.add(pygame.K_d)
        try:
            game.player.update(0.5, [], game.tiled_map.width, game.tiled_map.height)
            self.assertEqual(pygame.Vector2(game.player.rect.topleft), start)
            game.player.update(0.6, [], game.tiled_map.width, game.tiled_map.height)
            game.player.update(0.05, [], game.tiled_map.width, game.tiled_map.height)
            self.assertNotEqual(pygame.Vector2(game.player.rect.topleft), start)
        finally:
            pygame.key.pressed.clear()

    def test_trap_stops_the_car(self):
        game = self.game
        car = CarTests.buy_car(self)
        game._enter_car()
        game._start_chase()
        car.velocity.update(300, 0)
        trap = Trap(car.position)
        trap.age = 1.0
        game.traps = [trap]
        for hunter in game.hunters:
            hunter.trap_timer = 99
        game._update_traps(0.01, game._body())
        self.assertEqual(car.velocity.length(), 0)
        self.assertAlmostEqual(game.player.stunned_timer, 1.0)
        start = pygame.Vector2(car.position)
        with patch.object(game, "_input_direction", return_value=pygame.Vector2(1, 0)):
            game._move_player(0.05)
        self.assertEqual(car.position, start)

    def test_traps_disappear_when_the_chase_ends(self):
        game = self.game
        game._start_chase()
        game.traps = [Trap((100, 100))]
        game._resolve_chase(caught=False)
        self.assertEqual(game.traps, [])

    # ---- revólver
    def arm(self):
        game = self.game
        game.money = 10 ** 5
        game.shop_stock = ["arma"]
        game.shop_index = 0
        game._buy_selected_item()
        self.assertTrue(game._armed())
        return game

    def place(self, walker, offset):
        center = self.game.player.hitbox.center
        walker.position.update(center[0] + offset[0], center[1] + offset[1])
        walker._sync_hitbox()

    def fire_at(self, walker, frames=40):
        game = self.game
        self.assertTrue(game._shoot(self.game._body_rect(walker).center))
        for _ in range(frames):
            game._update_combat(0.016)

    def test_revolver_costs_twice_the_train_ticket(self):
        from game import ITEMS
        self.assertEqual(ITEMS["arma"]["price"], 2 * ITEMS["passagem"]["price"])
        self.assertIn("arma", self.game.shop_stock)
        game = self.arm()
        self.assertEqual(game.money, 10 ** 5 - 4800)

    def test_shooting_the_agiota_scares_the_henchmen_and_sleeping_wins(self):
        game = self.arm()
        game.player.reset_position((1280, 860))
        game.missed_payments = 2
        game._start_chase()
        agiota, *henchmen = game.hunters
        self.place(agiota, (130, 0))
        for index, capanga in enumerate(henchmen):
            self.place(capanga, (-600 - index * 60, 300))
        score = game.score
        game.draw(self.surface)
        self.fire_at(agiota)
        self.assertTrue(game.agiota_dead)
        self.assertEqual(game.state, "playing")
        self.assertEqual(game.hunters, [])
        self.assertEqual(len(game.fleeing), len(henchmen))
        self.assertGreaterEqual(game.score, score + 2000)
        self.assertEqual(game.debt, 0)
        self.assertEqual(game.stats["agiota"], 1)
        game.draw(self.surface)
        for _ in range(12 * 20):                    # os capangas somem fugindo
            game._update_combat(0.05)
        self.assertEqual(game.fleeing, [])
        self.assertEqual(game.fallen, [])
        # Dormir encerra o jogo com vitória.
        game.state = "sleep_confirm"
        game.draw(self.surface)
        self.key(pygame.K_RETURN)
        self.assertEqual((game.state, game.end_result, game.end_ending), ("end_name", "vitória", "agiota"))

    def test_staying_awake_after_the_agiota_keeps_the_game_going(self):
        game = self.game
        game._agiota_down()
        game.money = 0
        for day in range(2, 5):
            game._advance_day(slept=False, forced=True)
            self.assertEqual(game.state, "playing")      # sem cobrança, sem caçada
            self.assertEqual(game.day, day)
        self.assertEqual(game.missed_payments, 0)
        self.assertFalse(game._pay_now())
        game.state = "sleep_confirm"
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "playing")

    def test_shooting_a_capanga_keeps_the_chase(self):
        game = self.arm()
        game.player.reset_position((1280, 860))
        game.missed_payments = 2
        game._start_chase()
        agiota, capanga, other = game.hunters
        self.place(agiota, (-700, 300))
        self.place(other, (700, 300))
        self.place(capanga, (0, 140))
        self.fire_at(capanga)
        self.assertNotIn(capanga, game.hunters)
        self.assertEqual(game.state, "chase")
        self.assertFalse(game.agiota_dead)
        self.assertEqual(game.stats["capangas"], 1)

    def test_bullets_stop_at_walls_and_need_cooldown(self):
        game = self.arm()
        game.missed_payments = 1
        game._start_chase()
        agiota = game.hunters[0]
        game.player.reset_position((560, 1330))     # rua em frente ao Barzinho
        agiota.position.update(560, 1700)           # atrás do prédio
        agiota._sync_hitbox()
        self.assertTrue(game._shoot(game._body_rect(agiota).center))
        self.assertFalse(game._shoot((560, 1700)))   # recarga
        for _ in range(60):
            game._update_combat(0.016)
        self.assertFalse(game.agiota_dead)
        self.assertEqual(game.bullets, [])

    def test_cannot_shoot_without_the_gun_or_from_the_car(self):
        game = self.game
        game.state = "playing"
        self.assertFalse(game._shoot((0, 0)))
        game.inventory.append("arma")
        game.driving = True
        self.assertFalse(game._shoot((0, 0)))
        game.driving = False
        self.key(pygame.K_f)
        self.assertEqual(len(game.bullets), 1)
        self.audio.play.assert_any_call("shot")

    def test_click_shoots_toward_the_cursor(self):
        game = self.arm()
        game.state = "playing"
        game.draw(self.surface)
        target = (1100, 360)  # à direita do jogador na tela
        game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=target, button=1))
        self.assertEqual(len(game.bullets), 1)
        self.assertGreater(game.bullets[0].velocity.x, 0)
        self.assertAlmostEqual(game.bullets[0].velocity.y, 0, delta=60)

    def test_npcs_piled_on_each_other_do_not_freeze(self):
        game = self.game
        crowd = game.npcs[:4]
        for npc in crowd:  # todos no mesmo ponto, como no bug do "bolo" de moradores
            npc.position.update(1500, 750)
            npc._sync_hitbox()
            npc.path, npc.pause_timer = [], 0.01
        game.player.reset_position((400, 300))
        for _ in range(int(6 / 0.05)):
            game._update_npcs(0.05)
        positions = [pygame.Vector2(npc.position) for npc in crowd]
        moved = [p.distance_to((1500, 750)) > 40 for p in positions]
        self.assertGreaterEqual(sum(moved), 3, positions)

    def test_npcs_walking_into_each_other_get_unstuck(self):
        game = self.game
        a, b = game.npcs[:2]
        game.npcs = [a, b]
        a.position.update(1400, 1290)      # avenida de baixo, um de frente para o outro
        b.position.update(1440, 1290)
        for npc, goal in ((a, (1700, 1290)), (b, (1100, 1290))):
            npc._sync_hitbox()
            npc.pause_timer = 0
            npc.set_goal(goal)
        game.player.reset_position((400, 300))
        for _ in range(int(6 / 0.05)):
            for npc in (a, b):
                npc._follow_path(0.05, game._npc_blockers(npc))
        self.assertGreater(a.position.x, b.position.x + 60)   # passaram um pelo outro
        self.assertGreater(a.position.x, 1500)
        self.assertLess(b.position.x, 1340)

    def test_npcs_heading_to_the_same_point_from_opposite_sides(self):
        # Bug real: dois moradores encostados, cada um de um lado, indo para o mesmo ponto do
        # caminho. O passo "fantasma" de 1e-16 px no outro eixo contava como andar e o
        # destravamento nunca disparava.
        game = self.game
        a, b = game.npcs[:2]
        game.npcs = [a, b]
        game.player.reset_position((400, 300))
        for npc, x in ((a, 1128.77), (b, 1144.78)):
            npc.position.update(x, 1104.0000000000002)
            npc._sync_hitbox()
            npc.pause_timer = 0
            npc.path = [(1136.0, 1104.0), (1136.0, 1300.0)]
        start = (pygame.Vector2(a.position), pygame.Vector2(b.position))
        for _ in range(int(6 / 0.05)):
            game._update_npcs(0.05)
        # Antes da correção os dois ficavam parados para sempre (0 px).
        self.assertGreater(min(a.position.distance_to(start[0]), b.position.distance_to(start[1])), 24)

    def test_player_is_not_trapped_by_overlapping_npc(self):
        game = self.game
        npc = game.npcs[0]
        npc.position.update(game.player.hitbox.center)
        npc._sync_hitbox()
        self.assertNotIn(npc.hitbox, game._npc_obstacles())


class MenuAndSaveTests(GameTestCase):
    def test_menu_options_draw_and_difficulty_cycle(self):
        game = self.game
        game.state = "menu"
        game.menu_options = game._build_menu()
        game.draw(self.surface)
        game.menu_index = game.menu_options.index("Dificuldade")
        self.key(pygame.K_RIGHT)
        self.assertEqual(game.difficulty, "Difícil")
        self.key(pygame.K_1)
        self.assertEqual(game.difficulty, "Fácil")
        game.menu_index = game.menu_options.index("Como jogar")
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "help")
        game.draw(self.surface)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "menu")
        game.menu_index = game.menu_options.index("Ranking")
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "ranking")
        game.draw(self.surface)

    def test_pause_saves_and_continue_restores(self):
        game = self.game
        game.money, game.debt, game.day = 777, 1234, 4
        game.inventory = ["chapeu", "blazer"]
        self.key(pygame.K_p)
        self.key(pygame.K_m)
        self.assertEqual(game.state, "menu")
        self.assertIn("Continuar", game.menu_options)
        game.money, game.day, game.inventory = 0, 1, []
        game.menu_index = game.menu_options.index("Continuar")
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "playing")
        self.assertEqual((game.money, game.debt, game.day), (777, 1234, 4))
        self.assertEqual(game.inventory, ["chapeu", "blazer"])

    def test_save_keeps_payment_agiota_and_stats(self):
        game = self.game
        game.money = 1000
        game._pay_now()
        game.stats["shows"] = 7
        game.agiota_dead = True
        game.state = "playing"
        game._autosave()
        game.paid_next, game.agiota_dead, game.stats = False, False, {}
        game._load_saved_game()
        self.assertTrue(game.paid_next)
        self.assertTrue(game.agiota_dead)
        self.assertEqual(game.stats["shows"], 7)
        self.assertEqual(game.stats["payments"], 1)

    def test_end_screen_saves_stats_and_highlights_the_ranking(self):
        game = self.game
        game.stats.update(shows=4, earned=2300, best_accuracy=0.962, best_combo=180, best_bonus="Quase perfeito",
                          best_bonus_mult=2.2, payments=2, chases=1, escapes=1, traps=3)
        game.score = 5400
        game._finish_game("vitória", "Teste de trem", ending="trem")
        game.draw(self.surface)
        for char in "Ana":
            game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=char))
        self.key(pygame.K_RETURN)
        self.assertEqual(game.state, "ranking")
        self.assertTrue(game.result_saved)
        self.assertEqual(game.last_rank_position, 1)
        row = game.ranking.top(1)[0]
        self.assertEqual((row["nome"], row["final"], row["shows"], row["combo"]), ("Ana", "trem", 4, 180))
        self.assertAlmostEqual(row["precisao"], 0.962)
        game.draw(self.surface)
        self.key(pygame.K_DOWN)
        game._cycle_ranking_filter(1)
        game.draw(self.surface)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(game.state, "menu")

    def test_finishing_the_game_deletes_the_save(self):
        self.game._autosave()
        self.assertTrue(savegame.has_save())
        self.game._finish_game("derrota", "teste")
        self.assertFalse(savegame.has_save())

    def test_corrupt_save_is_ignored_and_logged(self):
        savegame.SAVE_PATH.write_text("{isso não é json", encoding="utf-8")
        with patch("savegame.logging.error") as error:
            self.assertIsNone(savegame.load_game())
        error.assert_called()

    def test_every_state_can_be_drawn(self):
        game = self.game
        game.venue_info = {"ok": True, "level": 2, "song": "Música 1", "max_reward": 300,
                           "duration": 29.0, "bpm": 120.0, "notes": 60}
        for state in ("playing", "shop", "sleep_confirm", "venue_info", "paused", "ranking", "end_name",
                      "menu", "help", "settings"):
            game.state = state
            game.active_venue = "bar"
            game.end_result = "vitória"
            game.draw(self.surface)
        game.rhythm_result = {"venue": "Barzinho", "song": "Música 1", "accuracy": 0.9, "score": 1000, "combo": 20,
                              "counts": {k: 1 for k in ("Perfect", "Great", "Good", "OK", "Meh", "Miss")},
                              "reward": 300, "failed": False, "crowd": 50, "lost_item": "Chapéu"}
        game.state = "rhythm_result"
        game.draw(self.surface)

    def test_day_runs_without_errors_for_a_while(self):
        game = self.game
        for _ in range(600):
            game.update(0.05)
            game.draw(self.surface)
        self.assertEqual(game.state, "playing")


if __name__ == "__main__":
    unittest.main()
