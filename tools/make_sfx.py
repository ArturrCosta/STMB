"""Gera os efeitos e sons ambiente do jogo em assets/sounds/ (só biblioteca padrão).

Uso:  python tools/make_sfx.py

Todos os sons são sintetizados (ondas, ruído filtrado e envelopes), então não há
direitos autorais envolvidos e dá para ajustar os parâmetros abaixo e gerar de novo.
Para usar sons próprios, basta substituir os .wav (mesmos nomes) em assets/sounds/.
"""

import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "assets" / "sounds"
rng = random.Random(7)  # semente fixa: o resultado é sempre o mesmo


def n(seconds):
    return int(seconds * RATE)


def env(i, total, attack=0.005, release=0.05):
    t, a, r = i / RATE, attack, release
    left = (total - i) / RATE
    return min(1.0, t / a if a else 1.0, left / r if r else 1.0)


def tone(freq, seconds, volume=0.5, shape="sine", decay=6.0, attack=0.004, glide=None):
    """Nota com decaimento exponencial. `glide` = frequência final (deslizando)."""
    total, phase, out = n(seconds), 0.0, []
    for i in range(total):
        f = freq if glide is None else freq + (glide - freq) * i / total
        phase += 2 * math.pi * f / RATE
        if shape == "sine":
            s = math.sin(phase)
        elif shape == "square":
            s = 1.0 if math.sin(phase) >= 0 else -1.0
        elif shape == "saw":
            s = ((phase / (2 * math.pi)) % 1.0) * 2 - 1
        else:  # triangle
            s = 2 * abs(((phase / (2 * math.pi)) % 1.0) * 2 - 1) - 1
        out.append(s * volume * math.exp(-decay * i / total)
                   * env(i, total, attack, 0.02))
    return out


def noise(seconds, volume=0.5, decay=8.0):
    total = n(seconds)
    return [rng.uniform(-1, 1) * volume * math.exp(-decay * i / RATE) * env(i, total, 0.002, 0.02)
            for i in range(total)]


def lowpass(samples, cutoff):
    alpha = 1 - math.exp(-2 * math.pi * cutoff / RATE)
    y, out = 0.0, []
    for s in samples:
        y += alpha * (s - y)
        out.append(y)
    return out


def mix(*tracks):
    length = max(len(t) for t in tracks)
    return [sum(t[i] for t in tracks if i < len(t)) for i in range(length)]


def delay(samples, seconds):
    return [0.0] * n(seconds) + samples


def concat(*tracks):
    out = []
    for t in tracks:
        out += t
    return out


def save(name, samples, peak=0.85):
    biggest = max(1e-9, max(abs(s) for s in samples))
    gain = min(1.0, peak / biggest) if biggest > peak else 1.0
    OUT.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT / f"{name}.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s * gain)) * 32767)) for s in samples))
    print(f"{name}.wav  {len(samples) / RATE:5.2f}s")


def periodic(seconds, make):
    """Ruído contínuo que emenda sem estalo: filtra 3 repetições e guarda a do meio."""
    total = n(seconds)
    base = make(total)
    stream = base + base + base
    return stream[total:2 * total]


def bird_phrase(base, notes, rng):
    """Frase curta de passarinho: notas senoidais com subida rápida e leve vibrato."""
    out = []
    for k in range(notes):
        f0 = base * rng.uniform(0.92, 1.08)
        length = rng.uniform(0.05, 0.09)
        total = n(length)
        phase, note = 0.0, []
        for i in range(total):
            x = i / total
            f = f0 * (1 + 0.25 * x) * (1 + 0.015 * math.sin(2 * math.pi * 38 * i / RATE))
            phase += 2 * math.pi * f / RATE
            note.append(math.sin(phase) * math.sin(math.pi * x) ** 2)
        out += note + [0.0] * n(rng.uniform(0.04, 0.09))
    return out


def ambient_day(seconds=16.0):
    """Manhã/tarde tranquila: só alguns passarinhos espaçados, sem ruído de fundo."""
    total = n(seconds)
    tracks = [[0.0] * total]
    calls = ((0.8, 3000, 3), (3.9, 3600, 2), (6.5, 2700, 4), (10.2, 3300, 3), (13.1, 2900, 2))
    for start, base, notes in calls:
        phrase = [v * 0.22 for v in bird_phrase(base, notes, rng)]
        tracks.append(delay(phrase, start))
        # resposta de outro pássaro, mais longe (mais baixo)
        echo = [v * 0.10 for v in bird_phrase(base * 1.2, max(2, notes - 1), rng)]
        tracks.append(delay(echo, start + 1.1))
    out = mix(*tracks)[:total]
    return out + [0.0] * (total - len(out))


def ambient_night(seconds=16.0):
    total = n(seconds)
    raw = [rng.uniform(-1, 1) for _ in range(total)]
    wind = lowpass(raw * 3, 220)[total:2 * total]
    tracks = [[w * 4.0 * 0.22 for w in wind]]
    cycle = 1.0                                              # grilos: trilos repetidos
    for k in range(int(seconds / cycle)):
        for pulse in range(5):
            tracks.append(delay(tone(4300 + (k % 3) * 120, 0.03, 0.045, "sine", decay=2.0), k * cycle + 0.30 + pulse * 0.06))
        for pulse in range(4):
            tracks.append(delay(tone(3900, 0.03, 0.035, "sine", decay=2.0), k * cycle + 0.68 + pulse * 0.07))
    out = mix(*tracks)[:total]
    return out + [0.0] * (total - len(out))


def main():
    save("ui_move", tone(880, 0.05, 0.35, "triangle", decay=5))
    save("ui_confirm", concat(tone(660, 0.07, 0.4, "triangle"), tone(990, 0.12, 0.4, "triangle", decay=5)))
    save("ui_back", concat(tone(620, 0.07, 0.35, "triangle"), tone(420, 0.1, 0.35, "triangle", decay=5)))
    save("error", mix(tone(150, 0.22, 0.4, "square", decay=3), tone(158, 0.22, 0.3, "square", decay=3)))
    save("cash", mix(tone(1318, 0.45, 0.35, "sine", decay=7),
                     delay(tone(1760, 0.5, 0.35, "sine", decay=7), 0.08),
                     delay(tone(2637, 0.4, 0.18, "sine", decay=9), 0.08)))
    save("spend", concat(tone(740, 0.08, 0.4, "triangle", decay=4),
                         tone(560, 0.08, 0.4, "triangle", decay=4),
                         tone(410, 0.16, 0.4, "triangle", decay=5)))
    save("stage_start", mix(tone(220, 0.5, 0.35, "saw", decay=2, glide=660),
                            lowpass(noise(0.5, 0.5, 4), 3000)))
    save("success", concat(*[tone(f, 0.16, 0.4, "triangle", decay=4) for f in (523, 659, 784)],
                           mix(tone(1047, 0.6, 0.4, "triangle", decay=4), tone(784, 0.6, 0.25, "sine", decay=4))))
    save("boo", mix(tone(220, 0.9, 0.4, "saw", decay=1.5, glide=110),
                    lowpass(noise(0.9, 0.5, 2.5), 700)))
    save("newday", mix(tone(784, 1.1, 0.35, "sine", decay=3), tone(1568, 1.1, 0.15, "sine", decay=3),
                       delay(tone(1047, 1.1, 0.3, "sine", decay=3), 0.35)))
    save("alarm", concat(*[tone(f, 0.22, 0.4, "square", decay=1.5) for f in (880, 660, 880, 660)]))
    save("caught", mix(tone(140, 0.55, 0.6, "sine", decay=4, glide=55),
                       lowpass(noise(0.35, 0.8, 9), 1500)))
    save("escape", concat(*[tone(f, 0.08, 0.35, "triangle", decay=3) for f in (392, 523, 659, 784, 1047)]))
    save("tick", mix(tone(1500, 0.06, 0.5, "sine", decay=9), lowpass(noise(0.02, 0.3, 60), 5000)))
    save("win", concat(*[tone(f, 0.2, 0.4, "triangle", decay=3) for f in (523, 659, 784, 1047)],
                       mix(tone(1047, 0.9, 0.4, "triangle", decay=3), tone(659, 0.9, 0.3, "sine", decay=3),
                           tone(784, 0.9, 0.3, "sine", decay=3))))
    save("lose", concat(*[tone(f, 0.28, 0.4, "triangle", decay=3) for f in (392, 349, 311)],
                        tone(196, 0.9, 0.4, "triangle", decay=2.5)))
    save("ambient_day", ambient_day(), peak=0.3)
    save("ambient_night", ambient_night(), peak=0.6)


if __name__ == "__main__":
    main()
