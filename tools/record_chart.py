"""Gravador de fases: crie o beatmap de uma música tocando junto com ela.

Uso (na pasta do projeto, com o ambiente virtual ativo):

    python tools/record_chart.py assets/music/musica1.wav
    python tools/record_chart.py assets/music/nova.wav --title "Nova" --bpm 120 --offset 0.05

Aperte D, F, J e K no ritmo da música, como se estivesse jogando (segure a tecla
para criar notas longas). Ao terminar, cada toque é encaixado na semicolcheia mais
próxima da batida e o JSON é salvo ao lado do áudio com os 5 níveis: a gravação vira
o nível mais difícil e os mais fáceis ficam com as notas dos tempos mais fortes.
O JSON antigo, se existir, é guardado como .bak.json.

O BPM e o offset vêm do JSON que já existe; para uma música nova informe --bpm e
--offset ou instale o numpy (requirements-dev.txt) para detectar automaticamente.
O atraso de áudio calibrado no jogo (Ajustes) também é aplicado aqui.
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LANE_KEYS = "dfjk"
HOLD_MIN = 0.35        # segurar mais que isso vira nota longa
LANE_GAP = 0.18        # mesma regra do jogo entre notas da mesma pista
END_MARGIN = 0.25
LEVEL_SHARE = {0: 0.40, 1: 0.55, 2: 0.70, 3: 0.85, 4: 1.0}


def _priority(slot):
    """Tempo forte primeiro: cabeça de compasso > batida > colcheia > semicolcheia."""
    if slot % 16 == 0:
        return 4
    if slot % 4 == 0:
        return 3
    if slot % 2 == 0:
        return 2
    return 1


def snap_and_build(presses, bpm, offset, duration):
    """Transforma toques gravados em níveis 0-4.

    `presses`: lista de (pista, início, fim) em segundos desde o começo da música.
    Retorna o dicionário de níveis no formato do beatmap (tempos relativos ao offset).
    """
    grid = 60.0 / bpm / 4
    notes = {}
    for lane, start, end in presses:
        if lane not in range(4):
            continue
        slot = round((start - offset) / grid)
        if slot < 0:
            continue
        held = end - start
        length = max(1, round(held / grid)) * grid if held >= HOLD_MIN else 0.0
        notes.setdefault((slot, lane), length)  # toque repetido no mesmo lugar conta uma vez

    ordered = sorted(notes.items(), key=lambda item: (item[0][0], item[0][1]))
    lane_end = [-1.0] * 4
    accepted = []
    for (slot, lane), length in ordered:
        start = offset + slot * grid
        if start <= lane_end[lane] + LANE_GAP:
            continue
        if start + length > duration - END_MARGIN:
            if start > duration - END_MARGIN:
                continue
            length = 0.0
        lane_end[lane] = start + length
        accepted.append({"slot": slot, "lane": lane, "length": length})

    ranked = sorted(accepted, key=lambda n: (-_priority(n["slot"]), n["slot"], n["lane"]))
    levels = {}
    for level, share in LEVEL_SHARE.items():
        keep = ranked[:max(1, round(len(ranked) * share))] if ranked else []
        if level <= 1:  # níveis fáceis: no máximo uma nota por instante
            seen, single = set(), []
            for note in sorted(keep, key=lambda n: (n["slot"], n["lane"])):
                if note["slot"] not in seen:
                    seen.add(note["slot"])
                    single.append(note)
            keep = single
        level_notes = []
        for note in sorted(keep, key=lambda n: (n["slot"], n["lane"])):
            item = {"time": round(note["slot"] * grid, 3), "lane": note["lane"]}
            if note["length"]:
                item["duration"] = round(note["length"], 3)
            level_notes.append(item)
        levels[str(level)] = level_notes
    return levels


def _tempo_for(audio_path, out_path, args):
    """BPM/offset/título: argumentos > JSON existente > detecção com numpy."""
    existing = {}
    if out_path.is_file():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
    bpm = args.bpm or existing.get("bpm")
    offset = args.offset if args.offset is not None else existing.get("offset")
    title = args.title or existing.get("title") or audio_path.stem
    if bpm is None or offset is None:
        try:
            sys.path.insert(0, str(ROOT / "tools"))
            import make_beatmap
            samples, duration = make_beatmap.load_audio(str(audio_path))
            analysis = make_beatmap.Analysis(samples, duration)
            bpm = bpm or round(analysis.bpm, 2)
            offset = offset if offset is not None else round(analysis.offset, 3)
        except ImportError:
            raise SystemExit("Informe --bpm e --offset (ou instale o numpy para detectar sozinho).")
    return float(bpm), float(offset), title


def record(audio_path, bpm, offset, title):
    """Abre uma janela, toca a música e devolve (toques, duração) ou None se cancelar."""
    import pygame
    from rhythm import _audio_duration, load_settings

    settings = load_settings()
    latency = settings["audio_offset"] / 1000
    duration = _audio_duration(audio_path)
    pygame.init()
    screen = pygame.display.set_mode((900, 520))
    pygame.display.set_caption(f"Gravar fase - {title}")
    font = pygame.font.Font(str(ROOT / "assets" / "fonts" / "Poppins-Medium.ttf"), 22)
    big = pygame.font.Font(str(ROOT / "assets" / "fonts" / "Poppins-Bold.ttf"), 48)
    clock = pygame.time.Clock()
    pygame.mixer.music.load(str(audio_path))
    pygame.mixer.music.set_volume(settings["volume"] / 100)

    lead_in = 3.0
    begin = time.perf_counter() + lead_in
    playing = False
    held, presses = {}, []
    beat = 60.0 / bpm
    while True:
        now = time.perf_counter()
        if not playing and now >= begin:
            pygame.mixer.music.play()
            begin = time.perf_counter()
            playing = True
        song_time = now - begin - latency
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.mixer.music.stop()
                pygame.quit()
                return None
            if event.type in (pygame.KEYDOWN, pygame.KEYUP) and playing:
                name = pygame.key.name(event.key)
                if name in LANE_KEYS:
                    lane = LANE_KEYS.index(name)
                    if event.type == pygame.KEYDOWN:
                        held[lane] = song_time
                    elif lane in held:
                        presses.append((lane, held.pop(lane), song_time))
        if playing and song_time > duration + 0.3:
            for lane, start in held.items():
                presses.append((lane, start, duration))
            pygame.mixer.music.stop()
            pygame.quit()
            return presses, duration

        screen.fill((16, 22, 28))
        header = f"{title}  |  {bpm:g} BPM  |  D F J K no ritmo  |  ESC cancela"
        screen.blit(font.render(header, True, (200, 210, 216)), (30, 24))
        if not playing:
            count = big.render(str(int(begin - now) + 1), True, (247, 203, 107))
            screen.blit(count, count.get_rect(center=(450, 260)))
        else:
            pulse = 1 - ((song_time - offset) % beat) / beat if song_time > offset else 0
            pygame.draw.circle(screen, (60 + round(120 * pulse), 70, 80), (450, 120), 18)
            for lane in range(4):
                x = 210 + lane * 160
                lit = lane in held
                pygame.draw.rect(screen, (247, 203, 107) if lit else (40, 52, 60), (x - 60, 200, 120, 200), border_radius=14)
                label = big.render(LANE_KEYS[lane].upper(), True, (20, 26, 30) if lit else (230, 236, 240))
                screen.blit(label, label.get_rect(center=(x, 300)))
            progress = max(0.0, min(1.0, song_time / duration))
            pygame.draw.rect(screen, (40, 52, 60), (30, 460, 840, 10), border_radius=5)
            pygame.draw.rect(screen, (247, 203, 107), (30, 460, round(840 * progress), 10), border_radius=5)
            info = f"{len(presses) + len(held)} notas gravadas   {max(0.0, song_time):.1f}/{duration:.1f} s"
            screen.blit(font.render(info, True, (200, 210, 216)), (30, 420))
        pygame.display.flip()
        clock.tick(240)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", help="arquivo de áudio (WAV de preferência)")
    parser.add_argument("--out", help="JSON de saída (padrão: mesmo nome do áudio)")
    parser.add_argument("--title")
    parser.add_argument("--bpm", type=float)
    parser.add_argument("--offset", type=float)
    args = parser.parse_args(argv)

    audio_path = Path(args.audio).resolve()
    out_path = Path(args.out).resolve() if args.out else audio_path.with_suffix(".json")
    bpm, offset, title = _tempo_for(audio_path, out_path, args)
    result = record(audio_path, bpm, offset, title)
    if result is None:
        print("Gravação cancelada; nada foi salvo.")
        return 1
    presses, duration = result
    levels = snap_and_build(presses, bpm, offset, duration)
    if not levels["4"]:
        print("Nenhuma nota gravada; nada foi salvo.")
        return 1
    if out_path.is_file():
        shutil.copy(out_path, out_path.with_suffix(".bak.json"))
    data = {"title": title, "audio": audio_path.name, "bpm": bpm, "offset": round(offset, 3),
            "duration": round(duration, 3), "levels": levels}
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = ", ".join(f"nível {k}: {len(v)}" for k, v in levels.items())
    print(f"Salvo em {out_path} ({counts}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
