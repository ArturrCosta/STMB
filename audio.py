"""Efeitos sonoros e sons ambiente (assets/sounds/*.wav, gerados por tools/make_sfx.py).

Tudo aqui é opcional: se o mixer ou algum arquivo falhar, o erro vai para
logs/error.log e o jogo continua em silêncio, sem travar. A música das
apresentações usa `pygame.mixer.music` e não passa por esta classe.
"""

import logging
from pathlib import Path

import pygame

SOUND_DIR = Path(__file__).resolve().parent / "assets" / "sounds"
EFFECTS = (
    "ui_move", "ui_confirm", "ui_back", "error", "cash", "spend", "stage_start", "success", "boo",
    "newday", "alarm", "caught", "escape", "win", "lose", "tick", "trap", "shot",
)
AMBIENCES = ("ambient_day", "ambient_night")
EFFECT_VOLUME = 0.7
AMBIENT_VOLUME = 0.35
FADE_SPEED = 1.2  # variação máxima de volume por segundo nas transições


class AudioManager:
    def __init__(self, folder=SOUND_DIR):
        self.enabled = False
        self.muted = False
        self.volume = 0.7  # volume geral de efeitos e ambiente (Ajustes)
        self.sounds = {}
        self._channels = {}
        self._levels = {name: 0.0 for name in AMBIENCES}
        self._targets = {name: 0.0 for name in AMBIENCES}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
        except (pygame.error, AttributeError) as error:
            logging.error("Áudio indisponível (mixer não iniciou): %s", error)
            return
        for name in EFFECTS + AMBIENCES:
            try:
                self.sounds[name] = pygame.mixer.Sound(str(Path(folder) / f"{name}.wav"))
            except (OSError, pygame.error) as error:
                logging.error("Falha ao carregar o som '%s': %s", name, error)
        self.enabled = bool(self.sounds)

    # ------------------------------------------------------------------
    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))

    def play(self, name, volume=1.0, force=False):
        """Toca um efeito curto. `force` toca mesmo silenciado (ex.: batidas da calibração)."""
        sound = self.sounds.get(name)
        if not self.enabled or (self.muted and not force) or sound is None:
            return
        try:
            level = EFFECT_VOLUME * volume * (self.volume if not force else max(self.volume, 0.5))
            sound.set_volume(max(0.0, min(1.0, level)))
            sound.play()
        except pygame.error as error:
            logging.error("Falha ao tocar o som '%s': %s", name, error)

    def set_ambient(self, day, night):
        """Define o quanto cada ambiente (0 a 1) deve estar audível; o volume muda aos poucos."""
        self._targets["ambient_day"] = max(0.0, min(1.0, day))
        self._targets["ambient_night"] = max(0.0, min(1.0, night))

    def update(self, dt):
        if not self.enabled:
            return
        for name in AMBIENCES:
            sound = self.sounds.get(name)
            if sound is None:
                continue
            target = 0.0 if self.muted else self._targets[name]
            level = self._levels[name]
            step = FADE_SPEED * dt
            level = min(target, level + step) if level < target else max(target, level - step)
            self._levels[name] = level
            channel = self._channels.get(name)
            try:
                if level > 0 and (channel is None or not channel.get_busy()):
                    channel = sound.play(loops=-1)
                    self._channels[name] = channel
                if channel is not None:
                    channel.set_volume(level * AMBIENT_VOLUME * self.volume / 0.7)
                    if level <= 0:
                        channel.stop()
                        self._channels[name] = None
            except pygame.error as error:
                logging.error("Falha no som ambiente '%s': %s", name, error)

    def toggle_mute(self):
        self.muted = not self.muted
        return self.muted

    def stop_all(self):
        if self.enabled:
            pygame.mixer.stop()
        self._channels = {}
