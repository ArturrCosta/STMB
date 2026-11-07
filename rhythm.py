"""Beatmaps e julgamento temporal do minigame 4K."""

import json
import math
import time
import wave
from pathlib import Path


POINTS = {"Perfect": 320, "Great": 300, "Good": 200, "OK": 100, "Meh": 50, "Miss": 0}
# Limites inclusivos, em segundos. O último limite também vale para perdas automáticas.
WINDOWS = ((0.045, "Perfect"), (0.080, "Great"), (0.115, "Good"),
           (0.150, "OK"), (0.180, "Meh"))
MAX_WINDOW = WINDOWS[-1][0]
SETTINGS_PATH = Path("data/rhythm_settings.json")
DEFAULT_SETTINGS = {"approach": 2.0, "volume": 70, "audio_offset": 0, "input_offset": 0}


def load_settings(path=SETTINGS_PATH):
    settings = DEFAULT_SETTINGS.copy()
    try:
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        for name in settings:
            if name in saved and isinstance(saved[name], (int, float)):
                settings[name] = saved[name]
    except (OSError, ValueError, TypeError):
        pass
    settings["approach"] = max(1.0, min(3.0, float(settings["approach"])))
    settings["volume"] = max(0, min(100, int(settings["volume"])))
    for name in ("audio_offset", "input_offset"):
        settings[name] = max(-250, min(250, int(settings[name])))
    return settings


def save_settings(settings, path=SETTINGS_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


def load_beatmap(path, level):
    """Retorna mapa validado; cada pista não pode conter notas sobrepostas."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    audio = path.parent / data["audio"]
    try:
        with wave.open(str(audio), "rb") as wav:
            audio_duration = wav.getnframes() / wav.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError) as error:
        raise ValueError("Arquivo de áudio inválido") from error
    duration = float(data["duration"])
    bpm = float(data["bpm"])
    offset = float(data.get("offset", 0))
    if not (math.isfinite(duration) and duration > 0
            and abs(duration - audio_duration) <= 0.1
            and math.isfinite(bpm) and bpm > 0 and math.isfinite(offset)):
        raise ValueError("Duração do beatmap incompatível com o áudio")
    notes = []
    lane_ends = [-1.0] * 4
    for item in sorted(data["levels"][str(level)], key=lambda n: (n["time"], n["lane"])):
        lane, start = item["lane"], float(item["time"]) + offset
        hold = float(item.get("duration", 0))
        if (type(lane) is not int or lane not in range(4) or not math.isfinite(start)
                or not math.isfinite(hold) or start < 0 or hold < 0):
            raise ValueError("Nota inválida no beatmap")
        if start <= lane_ends[lane] + MAX_WINDOW or start + hold > duration - 0.25:
            raise ValueError("Notas sobrepostas ou fora da música")
        lane_ends[lane] = start + hold
        notes.append({"lane": lane, "time": start, "duration": hold,
                      "head": None, "tail": None})
    if not notes:
        raise ValueError("Beatmap vazio")
    return {"title": data["title"], "bpm": bpm,
            "offset": offset, "duration": duration,
            "audio": audio, "notes": notes, "level": level}


def judgment(error):
    for limit, name in WINDOWS:
        if abs(error) <= limit:
            return name
    return "Miss"


def reward_for(accuracy, base, multiplier):
    """Pagamento máximo é o valor do local vezes a dificuldade escolhida."""
    accuracy = max(0.0, min(1.0, accuracy))
    return max(0, round(base * multiplier * accuracy ** 2))


class RhythmSession:
    def __init__(self, beatmap, settings, clock=time.perf_counter):
        self.map = beatmap
        self.settings = settings
        self.clock = clock
        self.started = None
        self.pressed = set()
        self.combo = 0
        self.max_combo = 0
        self.score = 0
        self.counts = {name: 0 for name in POINTS}
        self.last_judgment = None
        self.last_judgment_at = -10.0
        self.last_lane = None

    def start(self):
        self.started = self.clock()

    def song_time(self):
        # O mixer pode atrasar ou reportar get_pos impreciso: um relógio monotônico
        # governa tanto o desenho quanto o julgamento. Offset positivo atrasa o mapa.
        return self.clock() - self.started - self.settings["audio_offset"] / 1000

    def input_time(self):
        # Offset positivo compensa uma entrada percebida tardiamente.
        return self.song_time() - self.settings["input_offset"] / 1000

    @property
    def total(self):
        return sum(1 + bool(note["duration"]) for note in self.map["notes"])

    @property
    def judged(self):
        return sum(self.counts.values())

    @property
    def accuracy(self):
        return max(0.0, min(1.0, self.score / (self.judged * 320))) if self.judged else 1.0

    def _judge(self, note, part, name):
        if note[part] is not None:
            return
        note[part] = name
        self.counts[name] += 1
        self.score += POINTS[name]
        self.combo = 0 if name == "Miss" else self.combo + 1
        self.max_combo = max(self.max_combo, self.combo)
        self.last_judgment = name
        self.last_judgment_at = self.song_time()
        self.last_lane = note["lane"]

    def key_down(self, lane):
        if lane in self.pressed:
            return
        self.pressed.add(lane)
        now = self.input_time()
        candidates = [n for n in self.map["notes"] if n["lane"] == lane
                      and n["head"] is None and abs(n["time"] - now) <= MAX_WINDOW]
        if candidates:
            note = min(candidates, key=lambda n: abs(n["time"] - now))
            self._judge(note, "head", judgment(now - note["time"]))

    def key_up(self, lane):
        if lane not in self.pressed:
            return
        self.pressed.remove(lane)
        now = self.input_time()
        for note in self.map["notes"]:
            if note["lane"] == lane and note["duration"] and note["head"] not in (None, "Miss") and note["tail"] is None:
                self._judge(note, "tail", judgment(now - note["time"] - note["duration"]))
                break

    def update(self):
        now = self.input_time()
        for note in self.map["notes"]:
            if note["head"] is None and now > note["time"] + MAX_WINDOW:
                self._judge(note, "head", "Miss")
                if note["duration"]:
                    self._judge(note, "tail", "Miss")
            elif note["duration"] and note["head"] not in (None, "Miss") and note["tail"] is None:
                end = note["time"] + note["duration"]
                if now >= end and note["lane"] in self.pressed:
                    self._judge(note, "tail", "Perfect")
                elif now > end + MAX_WINDOW:
                    self._judge(note, "tail", "Miss")

    @property
    def finished(self):
        return (self.judged == self.total and self.song_time() >= self.map["duration"]
                and self.clock() - self.started >= self.map["duration"])
