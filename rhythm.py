"""Beatmaps e julgamento temporal do minigame 4K."""

import json
import math
import time
import wave
from pathlib import Path

import pygame


POINTS = {"Perfect": 320, "Great": 300, "Good": 200, "OK": 100, "Meh": 50, "Miss": 0}
# Limites inclusivos, em segundos. O último limite também vale para perdas automáticas.
# Janelas generosas: uma nota que ainda encosta no receptor (meio para fora) ainda vale pontos.
WINDOWS = ((0.050, "Perfect"), (0.090, "Great"), (0.130, "Good"),
           (0.175, "OK"), (0.220, "Meh"))
MAX_WINDOW = WINDOWS[-1][0]
# Espaço mínimo entre o fim de uma nota e a próxima na mesma pista (regra dos beatmaps).
MIN_LANE_GAP = 0.18
# Tolerância entre a duração declarada no JSON e a duração real do áudio. Decodificadores
# de MP3/OGG podem divergir alguns centésimos de segundo (padding do codificador).
DURATION_TOLERANCE = 0.25
# "Medidor de plateia": só reprova a apresentação nos locais que o ativam (fase 2).
CROWD_START = 60.0
CROWD_DELTA = {"Perfect": 2.0, "Great": 1.5, "Good": 0.8, "OK": 0.0, "Meh": -2.5, "Miss": -7.0}
# Multiplicador de pontos pelo combo atual: (combo mínimo, multiplicador).
MULTIPLIER_STEPS = ((100, 4), (50, 3), (25, 2), (0, 1))
COMBO_MILESTONES = (25, 50, 75, 100, 150, 200, 300)
# Bônus no cachê ao fim da música (vale o maior): (nome, multiplicador). A escada valoriza
# chegar perto da perfeição: cada degrau a mais de precisão paga bem mais que o anterior.
BONUS_TUNED = ("Afinado", 1.4)                 # precisão >= 90%
BONUS_GOLD = ("Sequência de ouro", 1.8)        # combo máximo >= 90% das notas
BONUS_NEAR = ("Quase perfeito", 2.2)           # precisão >= 95%
BONUS_FULL = ("Sem erros!", 2.6)               # nenhum Miss
BONUS_FLAWLESS = ("Impecável", 3.2)            # nenhum Miss e precisão >= 97%
BONUS_PERFECT = ("PERFEITO!", 4.0)             # tudo Perfect
# Degraus em ordem crescente, com o que é preciso para cada um (mostrado no resultado).
BONUS_LADDER = ((BONUS_TUNED, "90% de precisão"), (BONUS_GOLD, "combo de 90% da música"),
                (BONUS_NEAR, "95% de precisão"), (BONUS_FULL, "nenhum Miss"),
                (BONUS_FLAWLESS, "nenhum Miss e 97% de precisão"), (BONUS_PERFECT, "tudo Perfect"))


def next_bonus(current):
    """Próximo degrau acima de `current` (ou o primeiro, se None): ((nome, mult), requisito) ou None."""
    value = current[1] if current else 0
    return next(((bonus, need) for bonus, need in BONUS_LADDER if bonus[1] > value), None)
# Correção do relógio pela posição real da música (pygame.mixer.music.get_pos).
SYNC_DEADZONE = 0.012
SYNC_STEP = 0.004
SYNC_LIMIT = 0.25
SETTINGS_PATH = Path("data/rhythm_settings.json")
SETTINGS_VERSION = 2
# Teclas das 4 pistas (nomes do pygame.key.name), da esquerda para a direita. O jogador pode trocá-las em Ajustes.
DEFAULT_LANE_KEYS = ("d", "f", "j", "k")
DEFAULT_SETTINGS = {"approach": 2.0, "volume": 70, "sfx_volume": 70, "audio_offset": 0, "input_offset": 0,
                    "lane_keys": list(DEFAULT_LANE_KEYS)}


def lane_key_codes(names):
    """Códigos do pygame para os nomes das 4 pistas; None se algum nome for inválido ou repetido."""
    try:
        codes = tuple(pygame.key.key_code(str(name)) for name in names)
    except (ValueError, TypeError, pygame.error):
        return None
    return codes if len(codes) == 4 and len(set(codes)) == 4 else None


def valid_lane_keys(names):
    """Lista de 4 nomes de teclas válida (e sem repetição) ou o padrão D F J K."""
    if isinstance(names, (list, tuple)) and lane_key_codes(names) is not None:
        return [str(name) for name in names]
    return list(DEFAULT_LANE_KEYS)


def load_settings(path=SETTINGS_PATH):
    settings = DEFAULT_SETTINGS.copy()
    try:
        saved = json.loads(Path(path).read_text(encoding="utf-8"))
        for name in settings:
            if name != "lane_keys" and name in saved and isinstance(saved[name], (int, float)):
                settings[name] = saved[name]
        settings["lane_keys"] = saved.get("lane_keys", settings["lane_keys"])
        if saved.get("version") != SETTINGS_VERSION:
            # Ajustes de sincronia antigos (de antes da calibração automática) deixavam as
            # notas fora do tempo; voltam ao padrão e o jogador pode calibrar em Ajustes.
            settings["audio_offset"] = settings["input_offset"] = 0
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    settings["lane_keys"] = valid_lane_keys(settings["lane_keys"])
    settings["approach"] = max(1.0, min(3.0, float(settings["approach"])))
    settings["volume"] = max(0, min(100, int(settings["volume"])))
    settings["sfx_volume"] = max(0, min(100, int(settings["sfx_volume"])))
    for name in ("audio_offset", "input_offset"):
        settings[name] = max(-250, min(250, int(settings[name])))
    return settings


def save_settings(settings, path=SETTINGS_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(settings, version=SETTINGS_VERSION)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


_DURATION_CACHE = {}


def _audio_duration(audio_path):
    """Duração real do arquivo de áudio, em segundos, para qualquer formato.

    O conteúdo do arquivo é que manda, não a extensão: primeiro tenta ler como WAV PCM
    com o módulo padrão `wave` (rápido e sem depender do mixer); se o arquivo não for um
    WAV válido — por exemplo um MP3 salvo com extensão ".wav" — decodifica com
    `pygame.mixer.Sound` (SDL_mixer: MP3, OGG, FLAC...). O resultado fica em cache, pois
    decodificar uma música inteira a cada apresentação seria desperdício.
    """
    audio_path = Path(audio_path)
    stat = audio_path.stat()  # FileNotFoundError se o arquivo não existir
    key = (str(audio_path), stat.st_mtime_ns, stat.st_size)
    if key in _DURATION_CACHE:
        return _DURATION_CACHE[key]
    try:
        with wave.open(str(audio_path), "rb") as wav:
            duration = wav.getnframes() / wav.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        duration = pygame.mixer.Sound(str(audio_path)).get_length()
    _DURATION_CACHE[key] = duration
    return duration


def load_beatmap(path, level):
    """Retorna mapa validado; cada pista não pode conter notas sobrepostas.

    Se a música não tiver exatamente o nível pedido, usa o nível disponível mais próximo,
    de modo que uma música nova possa trazer só alguns níveis.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        audio = path.parent / data["audio"]
        title = data["title"]
        duration = float(data["duration"])
        bpm = float(data["bpm"])
        levels = data["levels"]
    except KeyError as error:
        raise ValueError(f"Campo obrigatório ausente no beatmap: {error}") from error
    try:
        audio_duration = _audio_duration(audio)
    except (wave.Error, EOFError, ZeroDivisionError, OSError, pygame.error) as error:
        raise ValueError(f"Arquivo de áudio inválido ({audio.name}): {error}") from error
    offset = float(data.get("offset", 0))
    if not (math.isfinite(duration) and duration > 0
            and abs(duration - audio_duration) <= DURATION_TOLERANCE
            and math.isfinite(bpm) and bpm > 0 and math.isfinite(offset)):
        raise ValueError(
            f"Duração do beatmap ({duration:.2f}s) incompatível com o áudio ({audio_duration:.2f}s)")
    available = sorted(int(key) for key in levels)
    if not available:
        raise ValueError("Beatmap sem níveis")
    chosen = min(available, key=lambda key: (abs(key - level), key))
    notes = []
    lane_ends = [-1.0] * 4
    for item in sorted(levels[str(chosen)], key=lambda n: (n["time"], n["lane"])):
        lane, start = item["lane"], float(item["time"]) + offset
        hold = float(item.get("duration", 0))
        if (type(lane) is not int or lane not in range(4) or not math.isfinite(start)
                or not math.isfinite(hold) or start < 0 or hold < 0):
            raise ValueError("Nota inválida no beatmap")
        if start <= lane_ends[lane] + MIN_LANE_GAP or start + hold > duration - 0.25:
            raise ValueError("Notas sobrepostas ou fora da música")
        lane_ends[lane] = start + hold
        notes.append({"lane": lane, "time": start, "duration": hold,
                      "head": None, "tail": None})
    if not notes:
        raise ValueError("Beatmap vazio")
    return {"title": title, "bpm": bpm,
            "offset": offset, "duration": duration,
            "audio": audio, "notes": notes, "level": chosen}


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
    def __init__(self, beatmap, settings, clock=time.perf_counter, crowd_meter=False):
        self.map = beatmap
        self.settings = settings
        self.clock = clock
        # Com o medidor ligado (palcos da fase 2), a plateia vaia o músico que erra demais.
        self.crowd_meter = crowd_meter
        self.crowd = CROWD_START
        self.failed = False
        self.started = None
        self.pressed = set()
        self.combo = 0
        self.max_combo = 0
        self.score = 0           # pontos com multiplicador (placar e ranking)
        self.base_score = 0      # pontos sem multiplicador (precisão)
        self.events = []         # ("multiplier", 2) / ("combo", 50) / ("break", 37): efeitos na tela
        self._sync_errors = []
        self.sync_correction = 0.0
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
        return max(0.0, min(1.0, self.base_score / (self.judged * 320))) if self.judged else 1.0

    @property
    def multiplier(self):
        return next(mult for minimum, mult in MULTIPLIER_STEPS if self.combo >= minimum)

    def bonus(self):
        """Maior bônus conquistado na música (nome, multiplicador do cachê) ou None."""
        if not self.judged:
            return None
        accuracy, no_miss = self.accuracy, self.counts["Miss"] == 0
        earned = [bonus for bonus, ok in (
            (BONUS_PERFECT, self.counts["Perfect"] == self.judged),
            (BONUS_FLAWLESS, no_miss and accuracy >= 0.97),
            (BONUS_FULL, no_miss),
            (BONUS_NEAR, accuracy >= 0.95),
            (BONUS_GOLD, self.max_combo >= 0.9 * self.total),
            (BONUS_TUNED, accuracy >= 0.90),
        ) if ok]
        return max(earned, key=lambda bonus: bonus[1]) if earned else None

    def sync_to_audio(self, audio_seconds):
        """Puxa o relógio aos poucos para a posição real da música, evitando que deslize."""
        if self.started is None or audio_seconds <= 0:
            return
        elapsed = self.clock() - self.started
        if elapsed < 0.4:
            return
        self._sync_errors.append(elapsed - audio_seconds)
        self._sync_errors = self._sync_errors[-31:]
        if len(self._sync_errors) < 9:
            return
        error = sorted(self._sync_errors)[len(self._sync_errors) // 2]
        if abs(error) > SYNC_DEADZONE:
            step = max(-SYNC_STEP, min(SYNC_STEP, error * 0.1))
            if abs(self.sync_correction + step) <= SYNC_LIMIT:
                self.started += step
                self.sync_correction += step
                self._sync_errors = [e - step for e in self._sync_errors]

    def _judge(self, note, part, name):
        if note[part] is not None:
            return
        note[part] = name
        self.counts[name] += 1
        previous_multiplier, previous_combo = self.multiplier, self.combo
        self.combo = 0 if name == "Miss" else self.combo + 1
        self.base_score += POINTS[name]
        self.score += POINTS[name] * self.multiplier
        if self.multiplier > previous_multiplier:
            self.events.append(("multiplier", self.multiplier))
        elif self.combo in COMBO_MILESTONES:
            self.events.append(("combo", self.combo))
        if name == "Miss" and previous_combo >= 25:
            self.events.append(("break", previous_combo))
        self.max_combo = max(self.max_combo, self.combo)
        self.last_judgment = name
        self.last_judgment_at = self.song_time()
        self.last_lane = note["lane"]
        self.crowd = max(0.0, min(100.0, self.crowd + CROWD_DELTA[name]))
        if self.crowd_meter and self.crowd <= 0:
            self.failed = True

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
