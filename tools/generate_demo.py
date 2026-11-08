"""Gera a faixa original de demonstração e cinco beatmaps fixos (sem dependências)."""

import json
import math
import struct
import wave
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "assets" / "music"
RATE = 22050
DURATION = 36
BPM = 120
BEAT = 60 / BPM
MELODY = (0, 3, 7, 10, 7, 3, 5, 7, 0, 3, 7, 12, 10, 7, 5, 3)


def tone(frequency, phase, duration):
    envelope = min(1, phase * 90) * max(0, 1 - phase / duration) ** 1.5
    return envelope * (math.sin(2 * math.pi * frequency * phase)
                       + 0.22 * math.sin(4 * math.pi * frequency * phase))


def generate_audio():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "cidade_em_pulso.wav"
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        samples = bytearray()
        for i in range(RATE * DURATION):
            t = i / RATE
            beat_index = int(t / BEAT)
            beat_phase = t % BEAT
            eighth_index = int(t / (BEAT / 2))
            eighth_phase = t % (BEAT / 2)
            bar = beat_index // 4
            root = (110, 98, 130.81, 87.31)[bar % 4]
            bass = 0.19 * tone(root, beat_phase, BEAT)
            chord_phase = t % (2 * BEAT)
            chord = sum(0.035 * tone(root * ratio, chord_phase, 2 * BEAT)
                        for ratio in (2, 2.378, 2.996))
            lead_note = MELODY[eighth_index % len(MELODY)]
            lead_frequency = 261.63 * 2 ** (lead_note / 12)
            lead = 0.11 * tone(lead_frequency, eighth_phase, BEAT / 2)
            kick = 0.34 * math.exp(-22 * beat_phase) * math.sin(
                2 * math.pi * (84 - 34 * beat_phase) * beat_phase)
            noise = (((i * 1664525 + 1013904223) & 65535) / 32768 - 1)
            snare = (0.13 * math.exp(-27 * beat_phase) * noise
                     if beat_index % 4 in (1, 3) else 0)
            hat = 0.045 * math.exp(-70 * eighth_phase) * noise
            value = max(-1, min(1, bass + chord + lead + kick + snare + hat))
            samples.extend(struct.pack("<h", int(value * 26000)))
        wav.writeframes(samples)


def generate_maps():
    levels = {}
    for level in range(5):
        notes = []
        lane_ends = [-1.0] * 4

        def add(time, lane, duration=0):
            if time <= lane_ends[lane] + 0.18:
                return
            lane_ends[lane] = time + duration
            item = {"time": round(time, 3), "lane": lane}
            if duration:
                item["duration"] = duration
            notes.append(item)

        for beat in range(4, 68):
            t = beat * BEAT
            lane = (0, 1, 2, 1, 3, 2, 1, 2)[beat % 8]
            hold = 0
            if level == 1 and beat % 32 == 8:
                hold = 0.75
            elif level == 2 and beat % 16 == 8:
                hold = 0.75
            elif level == 3 and beat % 12 == 8:
                hold = 0.75
            elif level == 4 and beat % 8 == 4:
                hold = 0.75
            add(t, lane, hold)
            if level >= 1 and beat % 4 == 0:
                add(t + BEAT / 2, (lane + 1) % 4)
            if level >= 2 and beat % 8 in (0, 4):
                add(t, (lane + 2) % 4)
            if level >= 3 and beat % 2 == 1:
                add(t + BEAT / 2, (lane + 2) % 4)
            if level >= 4 and beat % 4 == 2:
                add(t + BEAT / 2, (lane + 1) % 4)
            if level >= 4 and beat % 16 == 4:
                add(t, (lane + 1) % 4, 0.5)
        levels[str(level)] = sorted(notes, key=lambda n: (n["time"], n["lane"]))
    data = {"title": "Cidade em Pulso", "audio": "cidade_em_pulso.wav",
            "bpm": BPM, "offset": 0, "duration": DURATION, "levels": levels}
    (OUT / "cidade_em_pulso.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate_audio()
    generate_maps()
