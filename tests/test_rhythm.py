import os
import json
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rhythm import RhythmSession, judgment, load_beatmap, load_settings, next_bonus, reward_for, save_settings


BEATMAP = Path(__file__).resolve().parents[1] / "assets/music/cidade_em_pulso.json"
SETTINGS = {"approach": 2.0, "volume": 70, "sfx_volume": 70, "audio_offset": 0, "input_offset": 0,
            "lane_keys": ["d", "f", "j", "k"]}


class RhythmTests(unittest.TestCase):
    def make_session(self, notes, duration=3):
        self.now = 0.0
        session = RhythmSession({"notes": notes, "duration": duration}, SETTINGS.copy(),
                                clock=lambda: self.now)
        session.start()
        return session

    def test_six_windows_and_accuracy_bounds(self):
        self.assertEqual([judgment(x) for x in (0, .07, .11, .15, .20, .24)],
                         ["Perfect", "Great", "Good", "OK", "Meh", "Miss"])
        # Uma nota "meio para fora" do receptor (~0,14 s fora do centro) ainda vale pontos.
        self.assertNotEqual(judgment(0.14), "Miss")
        notes = [{"lane": 0, "time": 1, "duration": 0, "head": None, "tail": None}]
        s = self.make_session(notes)
        self.now = 1
        s.key_down(0)
        s.key_down(0)
        self.assertEqual((s.score, s.combo, s.accuracy, s.judged), (320, 1, 1.0, 1))

    def test_simultaneous_and_missed_notes(self):
        notes = [{"lane": lane, "time": 1, "duration": 0, "head": None, "tail": None}
                 for lane in range(3)]
        s = self.make_session(notes)
        self.now = 1
        s.key_down(0)
        s.key_down(1)
        self.now = 1.25
        s.update()
        s.update()
        self.assertEqual((s.counts["Perfect"], s.counts["Miss"], s.max_combo, s.combo),
                         (2, 1, 2, 0))
        self.assertEqual(s.judged, 3)

    def test_hold_requires_press_and_early_release_is_once(self):
        note = {"lane": 0, "time": 1, "duration": 1, "head": None, "tail": None}
        s = self.make_session([note])
        self.now = 1
        s.key_down(0)
        self.now = 1.5
        s.key_up(0)
        self.now = 3
        s.update()
        s.update()
        self.assertEqual((note["head"], note["tail"], s.counts["Miss"]),
                         ("Perfect", "Miss", 1))

    def test_full_hold_can_be_perfect(self):
        note = {"lane": 0, "time": 1, "duration": 1, "head": None, "tail": None}
        s = self.make_session([note])
        self.now = 1
        s.key_down(0)
        self.now = 2
        s.update()
        s.key_up(0)
        self.assertEqual((s.score, s.accuracy, s.combo), (640, 1.0, 2))

    def test_offsets_are_applied_once(self):
        note = {"lane": 0, "time": 1, "duration": 0, "head": None, "tail": None}
        s = self.make_session([note])
        s.settings["audio_offset"] = 100
        s.settings["input_offset"] = 50
        self.now = 1.15
        self.assertAlmostEqual(s.song_time(), 1.05)
        s.key_down(0)
        self.assertEqual(note["head"], "Perfect")

    def test_reward_and_all_maps(self):
        self.assertEqual(reward_for(1, 1000, 1.25), 1250)
        self.assertEqual(reward_for(0, 1000, 1.25), 0)
        self.assertLess(reward_for(.5, 350, 1), reward_for(.9, 350, 1))
        counts = []
        for level in range(5):
            beatmap = load_beatmap(BEATMAP, level)
            self.assertEqual(beatmap["duration"], 36)
            counts.append(len(beatmap["notes"]))
        self.assertEqual(counts, sorted(counts))
        self.assertTrue(any(n["duration"] for n in load_beatmap(BEATMAP, 4)["notes"]))

    def test_combo_multiplier_events_and_bonus(self):
        notes = [{"lane": i % 4, "time": 1 + i * 0.3, "duration": 0, "head": None, "tail": None} for i in range(60)]
        s = self.make_session(notes)
        for note in notes:
            self.now = note["time"]
            s.key_down(note["lane"])
            s.key_up(note["lane"])
        self.assertEqual(s.multiplier, 3)
        self.assertIn(("multiplier", 2), s.events)
        self.assertIn(("multiplier", 3), s.events)
        self.assertGreater(s.score, s.base_score)
        self.assertEqual(s.accuracy, 1.0)
        self.assertEqual(s.bonus()[1], 4.0)

    def test_bonus_levels(self):
        notes = [{"lane": i % 4, "time": 1 + i * 0.3, "duration": 0, "head": None, "tail": None} for i in range(20)]
        s = self.make_session(notes)
        for i, note in enumerate(notes):
            self.now = note["time"] + (0.07 if i == 3 else 0)  # um Great, nenhum erro
            s.key_down(note["lane"])
            s.key_up(note["lane"])
        self.assertEqual(s.bonus()[0], "Impecável")
        self.assertEqual(s.bonus()[1], 3.2)

    def test_next_bonus_step(self):
        self.assertEqual(next_bonus(None)[0][0], "Afinado")
        self.assertEqual(next_bonus(("Quase perfeito", 2.2))[0][1], 2.6)
        self.assertIsNone(next_bonus(("PERFEITO!", 4.0)))

    def test_bonus_ladder_rewards_near_perfection(self):
        notes = [{"lane": i % 4, "time": 1 + i * 0.3, "duration": 0, "head": None, "tail": None} for i in range(40)]

        def play(offsets, skip=()):
            s = self.make_session([dict(note) for note in notes], duration=20)
            fresh = s.map["notes"]
            for i, note in enumerate(notes):
                if i in skip:
                    continue
                self.now = fresh[i]["time"] + offsets(i)
                s.key_down(fresh[i]["lane"])
                s.key_up(fresh[i]["lane"])
                s.update()  # no jogo roda a cada quadro: notas puladas viram Miss na hora
            self.now = notes[-1]["time"] + 2
            s.update()
            return s

        all_great = play(lambda i: 0.07)                       # 93,75% de precisão, sem erros
        self.assertEqual(all_great.bonus()[0], "Sem erros!")
        near = play(lambda i: 0.0, skip={10})                   # um Miss no meio, resto Perfect
        self.assertGreaterEqual(near.accuracy, 0.95)
        self.assertEqual(near.bonus()[0], "Quase perfeito")
        sloppy = play(lambda i: 0.0 if i % 3 else 0.11, skip={5, 20, 35})  # vários Good e 3 Miss
        self.assertLess(sloppy.accuracy, 0.90)
        self.assertIsNone(sloppy.bonus())

    def test_audio_sync_nudges_the_clock(self):
        s = self.make_session([{"lane": 0, "time": 5, "duration": 0, "head": None, "tail": None}])
        s.started = 0.0
        for step in range(200):
            self.now = 1 + step * 0.016
            s.sync_to_audio(self.now - 0.05)  # o áudio começou 50 ms depois do relógio
        self.assertAlmostEqual(s.sync_correction, 0.05, delta=0.015)

    def test_settings_and_map_offset(self):
        with tempfile.TemporaryDirectory() as folder:
            settings_path = Path(folder) / "settings.json"
            values = SETTINGS | {"audio_offset": -80, "input_offset": 120}
            save_settings(values, settings_path)
            self.assertEqual(load_settings(settings_path), values)
            # Ajustes de versões antigas (sem "version") voltam a sincronia para zero.
            settings_path.write_text(json.dumps({"volume": 40, "audio_offset": 100, "input_offset": 100}))
            old = load_settings(settings_path)
            self.assertEqual((old["volume"], old["audio_offset"], old["input_offset"]), (40, 0, 0))
            self.assertEqual(old["lane_keys"], ["d", "f", "j", "k"])
            # Teclas das pistas: salvas e lidas; combinação inválida volta ao padrão.
            save_settings(SETTINGS | {"lane_keys": ["9", "0", "-", "="]}, settings_path)
            self.assertEqual(load_settings(settings_path)["lane_keys"], ["9", "0", "-", "="])
            for bad in (["a", "a", "b", "c"], ["a", "b"], "dfjk", ["a", "b", "c", "nao-existe"], None):
                settings_path.write_text(json.dumps({"lane_keys": bad}))
                self.assertEqual(load_settings(settings_path)["lane_keys"], ["d", "f", "j", "k"], bad)
            data = json.loads(BEATMAP.read_text(encoding="utf-8"))
            data["audio"] = str(BEATMAP.parent / data["audio"])
            data["offset"] = 0.1
            map_path = Path(folder) / "shifted.json"
            map_path.write_text(json.dumps(data), encoding="utf-8")
            shifted = load_beatmap(map_path, 0)
            self.assertAlmostEqual(shifted["notes"][0]["time"], 2.1)


if __name__ == "__main__":
    unittest.main()
