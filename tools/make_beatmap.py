"""Gera o beatmap (JSON) de uma música a partir do próprio áudio.

Uso (na pasta principal do projeto):

    python tools/make_beatmap.py assets/music/minha_musica.wav --title "Minha Música"

O áudio pode ser WAV ou MP3 (o conteúdo é detectado, não a extensão). O script:

1. mede a duração e estima o BPM e a fase da grade de batidas (ou usa --bpm/--offset);
2. detecta onde há "acontecimentos" na música em três faixas de frequência
   (graves = bumbo/baixo, médios = caixa/melodia, agudos = chimbal/pratos);
3. coloca notas só onde a música realmente tem batida, quantizadas na grade de
   semicolcheias, e espalha-as pelas quatro pistas conforme a faixa de frequência;
4. escreve cinco níveis de dificuldade (0 a 4) com a mesma estrutura de
   `assets/music/cidade_em_pulso.json`.

Dependência extra, usada só por esta ferramenta (não pelo jogo): numpy
(`python -m pip install numpy`). Para decodificar MP3 usa o FFmpeg, se estiver instalado,
ou o próprio Pygame como alternativa.
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np


ANALYSIS_RATE = 22050
N_FFT = 1024
HOP = 128
# Atraso sistemático (s) entre o instante real de um ataque e o pico do fluxo espectral,
# calibrado com a faixa sintética "Cidade em Pulso" (início das batidas conhecido).
ONSET_LAG = -0.0125
BANDS = {"low": (30, 180), "mid": (180, 1500), "high": (1500, 8000)}
CHORD_PAIRS = ((0, 2), (1, 3), (0, 3), (1, 2), (0, 1), (2, 3))
MIN_LANE_GAP = 0.20      # o jogo exige > 0,18 s entre notas da mesma pista
END_MARGIN = 1.5         # silêncio de segurança antes do fim da música (s)

# Parâmetros por nível (0 = mais fácil, 4 = mais difícil):
#   density      notas por segundo desejadas (acordes contam uma nota por pista);
#   subs         divisões da batida permitidas: 4 = tempos, 2 = contratempos, 1 = semicolcheias;
#   chord_gap    mínimo de semicolcheias entre acordes (None = sem acordes);
#   lane_gap     intervalo mínimo (s) entre duas notas da mesma pista;
#   per_beat     máximo de posições com nota dentro de uma mesma batida (evita rajadas);
#   holds        quantidade de notas longas.
LEVELS = {
    0: dict(density=1.7, min_bar=2, subs=(4,), per_beat=1, chord_gap=None, lane_gap=0.50, holds=0),
    1: dict(density=2.2, min_bar=3, subs=(4, 2), per_beat=2, chord_gap=None, lane_gap=0.35, holds=2),
    2: dict(density=2.8, min_bar=4, subs=(4, 2), per_beat=2, chord_gap=64, lane_gap=0.30, holds=4),
    3: dict(density=3.5, min_bar=5, subs=(4, 2, 1), per_beat=3, chord_gap=44, lane_gap=0.25, holds=5),
    4: dict(density=4.2, min_bar=6, subs=(4, 2, 1), per_beat=3, chord_gap=26, lane_gap=0.20, holds=8),
}
BAND_WEIGHT = {"low": 1.0, "mid": 1.0, "high": 0.55}   # chimbais soam o tempo todo: pesam menos
SLOT_BONUS = {4: 0.9, 2: 0.35, 1: 0.0}                  # tempos fortes valem mais que contratempos
MIN_STRENGTH = 0.9                                      # abaixo disso é silêncio/ruído de fundo
ONSET_WINDOW = 0.045   # só vira nota a posição da grade que tem um ataque real a até 45 ms
ONSET_SENSITIVITY = 1.0  # quanto o pico precisa se destacar do entorno (em desvios robustos)
ONSET_GLOBAL_Z = 0.8     # e quanto precisa ser forte em relação à música inteira (desvios-padrão)
HOLD_BEATS = 1.5        # comprimento padrão; o real acompanha quanto o som se sustenta
HOLD_RANGE = (1.0, 4.0)  # notas longas entre 1 e 4 batidas
RELAXED_STRENGTH = 1.45  # trechos calmos: aceita ataques só "locais" se a posição for bem marcada

# ----------------------------------------------------------------------------- áudio
def _resample(samples, rate):
    if rate == ANALYSIS_RATE:
        return samples
    if rate % ANALYSIS_RATE == 0:
        k = rate // ANALYSIS_RATE
        usable = len(samples) // k * k
        return samples[:usable].reshape(-1, k).mean(axis=1)
    n_out = int(len(samples) * ANALYSIS_RATE / rate)
    return np.interp(np.arange(n_out) * rate / ANALYSIS_RATE, np.arange(len(samples)), samples)


def _read_wav_pcm(path):
    with wave.open(str(path), "rb") as wav:
        channels, width, rate = wav.getnchannels(), wav.getsampwidth(), wav.getframerate()
        raw = wav.readframes(wav.getnframes())
    if width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648
    else:
        raise wave.Error(f"WAV de {8 * width} bits não suportado")
    return data.reshape(-1, channels).mean(axis=1), rate


def _decode_with_ffmpeg(path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado")
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / "decoded.wav"
        subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(path), "-ac", "1",
                        "-ar", str(ANALYSIS_RATE), str(out)], check=True)
        return _read_wav_pcm(out)


def _decode_with_pygame(path):
    import pygame
    pygame.mixer.init(frequency=ANALYSIS_RATE, size=-16, channels=1)
    sound = pygame.mixer.Sound(str(path))
    data = pygame.sndarray.array(sound).astype(np.float32) / 32768
    freq = pygame.mixer.get_init()[0]
    return data.reshape(len(data), -1).mean(axis=1), freq


def load_audio(path):
    """Retorna (amostras mono em 22,05 kHz, duração em segundos)."""
    path = Path(path)
    try:
        samples, rate = _read_wav_pcm(path)
    except (wave.Error, EOFError):
        try:
            samples, rate = _decode_with_ffmpeg(path)
        except (RuntimeError, subprocess.CalledProcessError):
            samples, rate = _decode_with_pygame(path)
    duration = len(samples) / rate
    return _resample(samples.astype(np.float32), rate), duration


# ----------------------------------------------------------------------------- análise
def spectrogram(samples):
    """Magnitude do espectro em janelas deslizantes (calculado em blocos para poupar memória)."""
    pad = N_FFT // 2
    padded = np.pad(samples, (pad, pad))
    frames = np.lib.stride_tricks.sliding_window_view(padded, N_FFT)[::HOP]
    window = np.hanning(N_FFT).astype(np.float32)
    chunks = [np.abs(np.fft.rfft(frames[i:i + 2048] * window, axis=1)).astype(np.float32)
              for i in range(0, len(frames), 2048)]
    return np.concatenate(chunks), np.fft.rfftfreq(N_FFT, 1 / ANALYSIS_RATE)


def band_flux(spectrum, freqs):
    """Fluxo espectral (aumento de energia) por faixa e para o espectro todo.

    Retorna ({faixa: vetor}, vetor_total, passo_em_segundos); o vetor `i` descreve o
    instante i * passo.
    """
    log_spec = np.log1p(spectrum * 100)
    rise = np.maximum(np.diff(log_spec, axis=0, prepend=log_spec[:1]), 0)
    out = {name: rise[:, (freqs >= lo) & (freqs < hi)].sum(axis=1) for name, (lo, hi) in BANDS.items()}
    return out, rise.sum(axis=1), HOP / ANALYSIS_RATE, rise


def band_energy(spectrum, freqs, lo, hi, smooth=0.03):
    """Envelope de energia de uma faixa de frequência, na mesma escala de tempo do fluxo."""
    energy = spectrum[:, (freqs >= lo) & (freqs < hi)].sum(axis=1)
    width = max(1, int(smooth / (HOP / ANALYSIS_RATE)))
    return np.convolve(energy, np.ones(width) / width, mode="same")


def _comb_score(flux, step, period, phase, duration):
    """Média do fluxo nos instantes `phase + n * period` (interpolação linear)."""
    times = np.arange(phase, duration - 0.05, period)
    pos = times / step
    idx = np.clip(pos.astype(int), 0, len(flux) - 2)
    frac = pos - idx
    return float((flux[idx] * (1 - frac) + flux[idx + 1] * frac).mean())


def _smooth(flux, frames=7):
    kernel = np.hanning(frames + 2)[1:-1]
    return np.convolve(flux, kernel / kernel.sum(), mode="same")


def _best_phase(flux, step, period, duration, resolution):
    phases = np.arange(0, period, resolution)
    scores = [_comb_score(flux, step, period, ph, duration) for ph in phases]
    best = int(np.argmax(scores))
    return float(phases[best]), float(scores[best])


def _wrap(phase, period):
    """Leva a fase para (-período/2, período/2]: o `offset` fica o mais perto possível de 0."""
    phase %= period
    return phase - period if phase > period / 2 else phase


def estimate_tempo(flux, step, duration, bpm_range=(70.0, 180.0)):
    """Busca em grade fina o par (BPM, fase) cujas batidas coincidem com mais energia.

    Um pequeno viés para andamentos entre 90 e 150 BPM evita o erro clássico de oitava/razão
    (por exemplo, escolher 80 BPM para uma música de 120 BPM com acentos a cada 3 colcheias).
    """
    smooth = _smooth(flux)
    best = (-1.0, 120.0, 0.0)
    for bpm in np.arange(bpm_range[0], bpm_range[1], 0.25):
        period = 60.0 / bpm
        phase, score = _best_phase(smooth, step, period, duration, 0.008)
        weighted = score * math.exp(-0.5 * (math.log2(bpm / 115.0) / 0.6) ** 2)
        if weighted > best[0]:
            best = (weighted, float(bpm), phase)
    _, bpm, _ = best
    # Refinamento: BPM em passos de 0,02 e fase em passos de 1 ms.
    best = (-1.0, bpm, 0.0)
    for b in np.arange(bpm - 0.4, bpm + 0.4, 0.02):
        period = 60.0 / b
        phase, score = _best_phase(smooth, step, period, duration, 0.002)
        if score > best[0]:
            best = (score, float(b), phase)
    _, bpm, _ = best
    if abs(bpm - round(bpm)) < 0.25:  # quase todas as músicas têm BPM inteiro
        bpm = float(round(bpm))
    period = 60.0 / bpm
    phase = estimate_tempo_phase(flux, step, duration, period)
    return bpm, phase


def estimate_tempo_phase(flux, step, duration, period):
    """Fase da grade (em segundos) para um período já conhecido."""
    smooth = _smooth(flux, frames=5)
    phase, _ = _best_phase(smooth, step, period, duration, 0.001)
    return _wrap(phase, period)


def _strength_at(flux, step, times, window):
    """Maior valor do fluxo numa janela ±`window` ao redor de cada instante."""
    out = np.zeros(len(times))
    half = max(1, int(round(window / step)))
    for i, t in enumerate(times):
        c = int(round(t / step))
        lo, hi = max(0, c - half), min(len(flux), c + half + 1)
        out[i] = flux[lo:hi].max() if hi > lo else 0.0
    return out


class Analysis:
    def __init__(self, samples, duration, bpm=None, offset=None):
        self.samples = samples
        self.duration = duration
        spectrum, freqs = spectrogram(samples)
        flux, total, self.step, self.rise = band_flux(spectrum, freqs)
        self.freqs = freqs
        lag = int(round(ONSET_LAG / self.step))  # pico do fluxo ocorre um pouco depois do ataque
        self.flux = {name: np.roll(values, -lag) for name, values in flux.items()}
        total = np.roll(total, -lag)
        self.total = total
        if bpm is None:
            bpm, estimated_phase = estimate_tempo(total, self.step, duration)
        else:
            estimated_phase = estimate_tempo_phase(total, self.step, duration, 60.0 / bpm)
        self.bpm = float(bpm)
        self.offset = float(estimated_phase if offset is None else offset)
        self.period = 60.0 / self.bpm
        self.energy_mid = band_energy(spectrum, freqs, *BANDS["mid"])
        self.refs = {name: float(np.percentile(values[values > 0], 90)) if (values > 0).any() else 1.0
                     for name, values in self.flux.items()}

    def slot_centroids(self, sixteenth_count):
        """Altura média (Hz, escala logarítmica) do que "entra" em cada semicolcheia.

        Serve para distribuir as notas pelas pistas: sons graves à esquerda, agudos à direita.
        """
        grid = self.period / 4
        usable = (self.freqs >= 40) & (self.freqs <= 8000)
        log_f = np.log(self.freqs[usable])
        half = max(1, int(round(0.03 / self.step)))
        out = np.full(sixteenth_count, np.nan)
        for k in range(sixteenth_count):
            c = int(round((self.offset + k * grid) / self.step))
            lo, hi = max(0, c - half), min(len(self.rise), c + half + 1)
            if hi <= lo:
                continue
            weights = self.rise[lo:hi][:, usable].sum(axis=0)
            if weights.sum() > 0:
                out[k] = float((weights * log_f).sum() / weights.sum())
        return out

    def slot_strengths(self, sixteenth_count):
        """Força normalizada (por faixa) de cada semicolcheia da grade."""
        grid = self.period / 4
        times = self.offset + np.arange(sixteenth_count) * grid
        window = min(0.035, grid / 3)
        return {name: _strength_at(values, self.step, times, window) / self.refs[name]
                for name, values in self.flux.items()}


# ----------------------------------------------------------------------------- charting
def onset_times(analysis, use_global=True):
    """Instantes dos ataques reais: picos locais do fluxo espectral que se destacam do entorno.

    A força de uma posição da grade (slot_strengths) mede "quanta energia nova há perto",
    o que também é alto em trechos ruidosos ou sustentados. Aqui exigimos um pico de verdade,
    para que nenhuma nota caia num lugar onde não se ouve nada começar.
    """
    flux = np.asarray(analysis.total, dtype=float)
    step = analysis.step
    radius = max(1, int(round(0.03 / step)))       # pico precisa ser o maior em ±30 ms
    context = max(radius + 1, int(round(0.4 / step)))
    times = []
    global_mean, global_std = float(flux.mean()), float(flux.std()) + 1e-9
    for i in range(radius, len(flux) - radius):
        value = flux[i]
        if value <= 0 or value < flux[i - radius:i + radius + 1].max():
            continue
        if use_global and (value - global_mean) / global_std < ONSET_GLOBAL_Z:
            continue  # ataque fraco demais para a música como um todo
        around = flux[max(0, i - context):i + context + 1]
        median = np.median(around)
        spread = np.median(np.abs(around - median)) + 1e-9
        if value >= median + ONSET_SENSITIVITY * 1.4826 * spread:
            times.append(i * step + ONSET_LAG)
    return np.array(times)


def sustain_length(analysis, t, period, limit):
    """Por quanto tempo (s) o som iniciado em `t` continua soando, arredondado a meias batidas."""
    env = analysis.energy_mid
    step = analysis.step
    start = int(round((t + 0.06) / step))
    if start >= len(env) or env[start] <= 0:
        return 0.0
    level = env[start]
    end = start
    max_end = min(len(env) - 1, int(round(min(limit, t + HOLD_RANGE[1] * period) / step)))
    while end < max_end and env[end] >= 0.45 * level:
        end += 1
    seconds = end * step - t
    beats = np.floor(seconds / (period / 2)) / 2
    beats = min(HOLD_RANGE[1], beats)
    return round(beats * period, 3) if beats >= HOLD_RANGE[0] else 0.0


def last_sound_time(analysis, fraction=0.15):
    """Último instante em que a música ainda tem volume (para tratar o encerramento)."""
    env = analysis.energy_mid
    loud = np.nonzero(env >= fraction * np.median(env[env > 0]))[0] if (env > 0).any() else []
    return float(loud[-1] * analysis.step) if len(loud) else analysis.duration


def _subdivision(k):
    return 4 if k % 4 == 0 else (2 if k % 2 == 0 else 1)


def build_levels(analysis, first_beat, last_time, density_scale=1.0, ending=0.0):
    """Monta os cinco níveis escolhendo, por ordem de destaque musical, onde ficam as notas.

    Em vez de limiares fixos (que dependem do volume/estilo de cada música), cada nível
    recebe um orçamento de notas por segundo e fica com as semicolcheias mais marcantes da
    música dentro das divisões permitidas. Assim os níveis são "aninhados" (o mais difícil
    contém o mais fácil) e a densidade é previsível para qualquer faixa.
    """
    period = analysis.period
    grid = period / 4
    slots = int((last_time - analysis.offset) / grid) + 1
    strengths = analysis.slot_strengths(slots)
    weighted = {name: strengths[name] * BAND_WEIGHT[name] for name in BANDS}
    salience = np.max([weighted[name] for name in BANDS], axis=0)
    onsets = onset_times(analysis)
    local_onsets = onset_times(analysis, use_global=False)
    ranking = {}
    for k in range(first_beat * 4, slots):
        t = analysis.offset + k * grid
        if t > last_time or salience[k] < MIN_STRENGTH:
            continue
        strong = len(onsets) and np.min(np.abs(onsets - t)) <= ONSET_WINDOW
        # Trechos calmos (melodia ligada): vale um ataque que se destaca só no próprio trecho,
        # desde que a posição da grade seja bem marcada.
        soft = (salience[k] >= RELAXED_STRENGTH and len(local_onsets)
                and np.min(np.abs(local_onsets - t)) <= ONSET_WINDOW)
        if not (strong or soft):
            continue  # nada começa aqui de verdade: não é lugar de nota
        ranking[k] = salience[k] + SLOT_BONUS[_subdivision(k)]
    centroids = analysis.slot_centroids(slots)
    total_flux = analysis.total
    median_flux = float(np.median(total_flux[total_flux > 0])) if (total_flux > 0).any() else 1.0
    playable = max(1.0, last_time - (analysis.offset + first_beat * period))

    levels = {}
    for level, spec in LEVELS.items():
        budget = spec["density"] * density_scale * playable
        pool = sorted((k for k in ranking if _subdivision(k) in spec["subs"]),
                      key=lambda k: -ranking[k])
        chosen, used, chord_slots, per_beat = {}, 0.0, [], {}
        # 1ª passada: cada compasso com música ganha um mínimo de notas (trechos calmos não
        # ficam vazios só porque os trechos fortes "gastaram" o orçamento).
        per_bar = {}
        for k in pool:
            if per_bar.get(k // 16, 0) >= spec["min_bar"] or per_beat.get(k // 4, 0) >= 1:
                continue
            per_bar[k // 16] = per_bar.get(k // 16, 0) + 1
            per_beat[k // 4] = per_beat.get(k // 4, 0) + 1
            chosen[k] = (sorted(BANDS, key=lambda n: -weighted[n][k]), False)
            used += 1
        for k in pool:
            if k in chosen:
                continue
            if used >= budget:
                break
            if per_beat.get(k // 4, 0) >= spec["per_beat"]:
                continue
            per_beat[k // 4] = per_beat.get(k // 4, 0) + 1
            bands = sorted(BANDS, key=lambda n: -weighted[n][k])
            chord = (spec["chord_gap"] is not None and _subdivision(k) >= 2 - (level >= 3)
                     and weighted[bands[1]][k] >= 1.6 and weighted[bands[0]][k] >= 2.2
                     and all(abs(k - other) >= spec["chord_gap"] for other in chord_slots))
            if chord:
                chord_slots.append(k)
            chosen[k] = (bands, chord)
            used += 2 if chord else 1

        # Encerramento: no fim da música, todas as batidas que ainda soam viram notas
        # (longas, acompanhando o som), e nos níveis altos entram também as colcheias.
        ending_slots = set()
        if ending > 0:
            sound_end = min(last_sound_time(analysis), last_time)
            start_k = int(np.ceil((sound_end - ending - analysis.offset) / grid))
            for k in range(max(start_k, first_beat * 4), slots):
                t = analysis.offset + k * grid
                if t > sound_end - 0.15:
                    break
                wanted = (k % 4 == 0 and (level >= 1 or k % 8 == 0)) or (level >= 3 and k % 2 == 0)
                if wanted and salience[k] >= 0.6:
                    bands = sorted(BANDS, key=lambda n: -weighted[n][k])
                    chosen.setdefault(k, (bands, False))
                    if k % 4 == 0:
                        ending_slots.add(k)

        # Notas longas: nos tempos fortes com a música mais "vazia" logo depois; o comprimento
        # acompanha por quanto tempo o som realmente se sustenta.
        hold_slots = {}
        length = round(HOLD_BEATS * period, 3)
        for k in sorted(ending_slots):
            t = analysis.offset + k * grid
            sustain = sustain_length(analysis, t, period, last_time)
            hold_slots[k] = max(round(period * HOLD_RANGE[0], 3), min(sustain or period, round(period * 2, 3)))
        quiet = []
        for k, (bands, chord) in chosen.items():
            t = analysis.offset + k * grid
            if k % 4 or chord or t + length > last_time:
                continue
            lo = int(round((t + 0.1) / analysis.step))
            hi = int(round((t + length - 0.1) / analysis.step))
            if hi > lo:
                quiet.append((float(total_flux[lo:hi].mean()) / median_flux, k))
        regular_holds = 0
        for _, k in sorted(quiet):
            if regular_holds >= spec["holds"]:
                break
            if k not in hold_slots and all(abs(k - other) >= 32 for other in hold_slots if other not in ending_slots):
                t = analysis.offset + k * grid
                hold_slots[k] = sustain_length(analysis, t, period, last_time) or length
                regular_holds += 1

        # Quartis das alturas das notas escolhidas: cada pista recebe ~25% das notas do nível.
        pitched = [centroids[k] for k in chosen if not np.isnan(centroids[k])]
        edges = np.percentile(pitched, [25, 50, 75]) if pitched else np.array([6.0, 6.5, 7.0])
        levels[str(level)] = _assign_lanes(analysis, chosen, hold_slots, spec, grid, centroids, edges)
    return levels


def _assign_lanes(analysis, chosen, hold_slots, spec, grid, centroids, edges):
    notes, lane_end = [], [-9.0] * 4
    previous_lane, previous_time = None, -9.0
    gap = max(spec["lane_gap"], MIN_LANE_GAP)

    def free(lane, t):
        return t - lane_end[lane] >= gap

    for k in sorted(chosen):
        bands, chord = chosen[k]
        t = analysis.offset + k * grid
        rel = round(k * grid, 3)
        centroid = centroids[k]
        main = int(np.searchsorted(edges, centroid)) if not np.isnan(centroid) else 1 + (k // 4) % 2
        if chord:
            options = [pair for pair in CHORD_PAIRS if main in pair and free(pair[0], t)
                       and free(pair[1], t) and (abs(pair[0] - pair[1]) > 1 or k % 8 == 0)]
            if options:
                pair = options[(k // 4) % len(options)]
                for lane in pair:
                    notes.append({"time": rel, "lane": lane})
                    lane_end[lane] = t
                previous_lane, previous_time = pair[1], t
                continue
        # Pista pelo registro (grave -> esquerda); se ocupada ou repetida, a vizinha mais livre.
        order = sorted(range(4), key=lambda l: (abs(l - main), -abs(l - (previous_lane if previous_lane is not None else main))))
        if previous_lane is not None and t - previous_time < 0.3 and order[0] == previous_lane:
            order.append(order.pop(0))   # evita repetir a mesma pista em sequência rápida
        lane = next((l for l in order if free(l, t)), None)
        if lane is None:
            continue
        item = {"time": rel, "lane": lane}
        if k in hold_slots:
            item["duration"] = hold_slots[k]
        notes.append(item)
        lane_end[lane] = t + item.get("duration", 0)
        previous_lane, previous_time = lane, t
    return sorted(notes, key=lambda n: (n["time"], n["lane"]))


def build_beatmap(analysis, title, audio_name, first_beat=4, density_scale=1.0, ending=0.0):
    last_time = analysis.duration - END_MARGIN
    levels = build_levels(analysis, first_beat, last_time, density_scale, ending)
    return {"title": title, "audio": audio_name, "bpm": round(analysis.bpm, 2),
            "offset": round(analysis.offset, 3), "duration": round(analysis.duration, 3),
            "levels": levels}


def validate(beatmap):
    """Mesmas regras do `rhythm.load_beatmap`; retorna lista de problemas."""
    problems = []
    offset, duration = beatmap["offset"], beatmap["duration"]
    counts = []
    for key, notes in beatmap["levels"].items():
        lane_end = [-1.0] * 4
        for note in sorted(notes, key=lambda n: (n["time"], n["lane"])):
            start, hold = note["time"] + offset, note.get("duration", 0)
            if start <= lane_end[note["lane"]] + 0.18 or start + hold > duration - 0.25:
                problems.append(f"nível {key}: nota inválida em {start:.3f}s (pista {note['lane']})")
            lane_end[note["lane"]] = start + hold
        counts.append(len(notes))
    if counts != sorted(counts):
        problems.append(f"quantidade de notas não cresce com o nível: {counts}")
    return problems


def summary(beatmap):
    lines = [f"  BPM {beatmap['bpm']}  offset {beatmap['offset']}s  duração {beatmap['duration']}s"]
    for key, notes in beatmap["levels"].items():
        holds = sum(1 for n in notes if n.get("duration"))
        lines.append(f"  nível {key}: {len(notes):3d} notas ({len(notes) / beatmap['duration']:.2f}/s), "
                     f"{holds} longas")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Gera o beatmap JSON de uma música (WAV/MP3).")
    parser.add_argument("audio", help="arquivo de áudio (dentro de assets/music, de preferência)")
    parser.add_argument("--title", help="título exibido no jogo (padrão: nome do arquivo)")
    parser.add_argument("--out", help="JSON de saída (padrão: mesmo nome do áudio, com .json)")
    parser.add_argument("--bpm", type=float, help="BPM, se já souber (senão é estimado)")
    parser.add_argument("--offset", type=float,
                        help="segundo em que cai a primeira batida (senão é estimado)")
    parser.add_argument("--density", type=float, default=1.0,
                        help="multiplicador de dificuldade (0.8 = mais leve, 1.2 = mais denso)")
    parser.add_argument("--first-beat", type=int, default=4,
                        help="batida em que as notas podem começar (padrão 4 = introdução curta)")
    parser.add_argument("--ending", type=float, default=0.0,
                        help="segundos finais tratados como encerramento: mais notas e notas longas")
    args = parser.parse_args(argv)

    audio = Path(args.audio)
    samples, duration = load_audio(audio)
    analysis = Analysis(samples, duration, bpm=args.bpm, offset=args.offset)
    title = args.title or audio.stem.replace("_", " ").title()
    beatmap = build_beatmap(analysis, title, audio.name, first_beat=args.first_beat,
                          density_scale=args.density, ending=args.ending)
    problems = validate(beatmap)
    out = Path(args.out) if args.out else audio.with_suffix(".json")
    out.write_text(json.dumps(beatmap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{audio.name} -> {out}")
    print(summary(beatmap))
    if problems:
        print("ATENÇÃO:\n  " + "\n  ".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
