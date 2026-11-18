"""Confere os arquivos de dados do jogo: fases rítmicas, tilesets e gerador de fases."""

import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from rhythm import load_beatmap

ROOT = Path(__file__).resolve().parent.parent
MUSIC = ROOT / "assets" / "music"
MAPS = ROOT / "assets" / "maps"


class BeatmapFileTests(unittest.TestCase):
    def test_every_beatmap_loads_on_every_level(self):
        paths = sorted(MUSIC.glob("*.json"))
        self.assertGreaterEqual(len(paths), 3)
        for path in paths:
            counts = []
            for level in range(5):
                beatmap = load_beatmap(path, level)
                self.assertEqual(beatmap["level"], level, path.name)
                self.assertTrue(Path(beatmap["audio"]).is_file(), path.name)
                counts.append(len(beatmap["notes"]))
            self.assertEqual(counts, sorted(counts), f"{path.name}: níveis devem ter mais notas a cada nível")
            self.assertGreater(counts[0], 20, path.name)

    def test_fair_song_has_notes_in_the_calm_part_and_long_notes_at_the_end(self):
        data = json.loads((MUSIC / "musica2.json").read_text(encoding="utf-8"))
        offset = data["offset"]
        for level in ("1", "2", "3"):
            notes = data["levels"][level]
            calm = [n for n in notes if 9 <= n["time"] + offset <= 13]
            self.assertGreaterEqual(len(calm), 4, level)
            ending = [n for n in notes if n["time"] + offset >= 30]
            self.assertGreaterEqual(sum(1 for n in ending if n.get("duration")), 3, level)

    def test_venue_songs_exist(self):
        from game import VENUES
        for venue in VENUES.values():
            self.assertTrue((MUSIC / venue["song"]).is_file(), venue["song"])


class AudioFileTests(unittest.TestCase):
    def test_music_files_are_real_wav(self):
        """MP3 com extensão .wav dependia de como cada computador decodifica; aqui só PCM de verdade."""
        import wave
        for path in sorted(MUSIC.glob("*.wav")):
            with wave.open(str(path), "rb") as wav:
                self.assertGreater(wav.getnframes(), 0, path.name)

    def test_sound_effects_are_present_and_valid(self):
        import wave
        from audio import AMBIENCES, EFFECTS
        for name in EFFECTS + AMBIENCES:
            path = ROOT / "assets" / "sounds" / f"{name}.wav"
            with wave.open(str(path), "rb") as wav:
                self.assertGreater(wav.getnframes(), 100, name)


class RecorderTests(unittest.TestCase):
    def test_recorded_taps_snap_to_the_beat_and_load_in_the_game(self):
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "tools"))
        import record_chart

        bpm, offset, duration = 120.0, 0.1, 20.0
        presses = []
        for beat in range(4, 36):  # uma nota por batida, com erro humano de até 30 ms
            start = offset + beat * 0.5 + (0.03 if beat % 3 else -0.02)
            presses.append((beat % 4, start, start + (0.6 if beat % 8 == 0 else 0.1)))
        presses.append((1, offset + 6.25 + 0.01, offset + 6.3))  # contratempo
        levels = record_chart.snap_and_build(presses, bpm, offset, duration)
        times = [n["time"] for n in levels["4"]]
        self.assertTrue(all(abs((t / 0.125) - round(t / 0.125)) < 1e-6 for t in times))  # na grade
        self.assertIn(6.25, times)
        self.assertTrue(any(n.get("duration") for n in levels["4"]))
        counts = [len(levels[str(level)]) for level in range(5)]
        self.assertEqual(counts, sorted(counts))
        data = {"title": "T", "audio": str(MUSIC / "cidade_em_pulso.wav"), "bpm": bpm, "offset": offset,
                "duration": 36.0, "levels": levels}
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "gravada.json"
            target.write_text(json.dumps(data), encoding="utf-8")
            for level in range(5):
                self.assertTrue(load_beatmap(target, level)["notes"])


class MapAssetTests(unittest.TestCase):
    def test_every_tileset_image_is_inside_the_project(self):
        """Tilesets apontando para pastas externas quebram o jogo em outros computadores."""
        for tsx in sorted(MAPS.glob("*.tsx")):
            for image in ET.parse(tsx).getroot().iter("image"):
                target = (tsx.parent / image.get("source")).resolve()
                self.assertTrue(target.is_file(), f"{tsx.name}: {image.get('source')}")
                self.assertTrue(str(target).startswith(str(ROOT)), f"{tsx.name} usa arquivo fora do projeto")

    def test_map_references_only_existing_tilesets(self):
        root = ET.parse(MAPS / "cidade.tmx").getroot()
        for tileset in root.iter("tileset"):
            self.assertTrue((MAPS / tileset.get("source")).is_file(), tileset.get("source"))


class BeatmapToolTests(unittest.TestCase):
    def test_generator_output_is_accepted_by_the_loader(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy não instalado (só é preciso para tools/make_beatmap.py)")
        import sys
        import tempfile
        sys.path.insert(0, str(ROOT / "tools"))
        import make_beatmap

        samples, duration = make_beatmap.load_audio(str(MUSIC / "cidade_em_pulso.wav"))
        analysis = make_beatmap.Analysis(samples, duration)
        data = make_beatmap.build_beatmap(analysis, "Teste", "cidade_em_pulso.wav")
        self.assertAlmostEqual(analysis.bpm, 120, delta=1)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "teste.json"
            target.write_text(json.dumps(data), encoding="utf-8")
            # O áudio é procurado ao lado do JSON; copia a referência para a pasta de músicas.
            data["audio"] = str(MUSIC / "cidade_em_pulso.wav")
            target.write_text(json.dumps(data), encoding="utf-8")
            for level in range(5):
                self.assertTrue(load_beatmap(target, level)["notes"])


if __name__ == "__main__":
    unittest.main()
