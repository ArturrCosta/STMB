import os
import json
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rhythm import RhythmSession, judgment, load_beatmap, load_settings, reward_for, save_settings


BEATMAP = Path(__file__).resolve().parents[1] / "assets/music/cidade_em_pulso.json"
SETTINGS = {"approach": 2.0, "volume": 70, "audio_offset": 0, "input_offset": 0}


class RhythmTests(unittest.TestCase):
    def make_session(self, notes, duration=3):
        self.now = 0.0
        session = RhythmSession({"notes": notes, "duration": duration}, SETTINGS.copy(),
                                clock=lambda: self.now)
        session.start()
        return session

    def test_six_windows_and_accuracy_bounds(self):
        self.assertEqual([judgment(x) for x in (0, .06, .10, .13, .17, .19)],
                         ["Perfect", "Great", "Good", "OK", "Meh", "Miss"])
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
        self.now = 1.2
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

    def test_settings_and_map_offset(self):
        with tempfile.TemporaryDirectory() as folder:
            settings_path = Path(folder) / "settings.json"
            values = SETTINGS | {"audio_offset": -80, "input_offset": 120}
            save_settings(values, settings_path)
            self.assertEqual(load_settings(settings_path), values)
            data = json.loads(BEATMAP.read_text(encoding="utf-8"))
            data["audio"] = str(BEATMAP.parent / data["audio"])
            data["offset"] = 0.1
            map_path = Path(folder) / "shifted.json"
            map_path.write_text(json.dumps(data), encoding="utf-8")
            shifted = load_beatmap(map_path, 0)
            self.assertAlmostEqual(shifted["notes"][0]["time"], 2.1)


if __name__ == "__main__":
    unittest.main()
