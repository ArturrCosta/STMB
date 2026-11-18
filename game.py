import logging
import math
import random
import time
from pathlib import Path

import pygame

import savegame
import ui
from audio import AudioManager
from camera import Camera
from navigation import NavGrid
from car import Car
from npc import NPC, Agiota, Capanga, Mugger
from player import Player
from ranking import Ranking
from rhythm import RhythmSession, load_beatmap, load_settings, reward_for, save_settings
from tiled_map import TiledMap


# Coordenadas em pixels do mapa (80 x 60 tiles de 32 px).
# São marcadores provisórios e podem ser movidos quando os prédios finais forem feitos.
ZONES = [
    {"id": "shop", "name": "LOJA", "position": (1300, 1500), "color": (243, 190, 76)},
    {"id": "bar", "name": "BARZINHO", "position": (500, 1300), "color": (229, 119, 76)},
    {"id": "fair", "name": "FEIRA MUSICAL", "position": (1950, 860), "color": (99, 196, 131)},
    {"id": "concert", "name": "CASA DE SHOWS", "position": (500, 550), "color": (181, 132, 230)},
    {"id": "home", "name": "SUA CASA", "position": (650, 1800), "color": (104, 185, 224)},
    {"id": "station", "name": "ESTAÇÃO", "position": (1950, 400), "color": (226, 217, 119)},
]

ITEMS = {
    "chapeu": {"name": "Chapéu", "price": 100, "kind": "roupa"},
    "sapatos": {"name": "Sapatos sociais", "price": 150, "kind": "roupa"},
    "calca": {"name": "Calça social", "price": 200, "kind": "roupa"},
    "blazer": {"name": "Blazer", "price": 300, "kind": "roupa"},
    "fusca": {"name": "Fusca usado", "price": 900, "kind": "veiculo"},
    "passagem": {"name": "Passagem de trem", "price": 2400, "kind": "passagem"},
}

CLOTHING_KEYS = ["chapeu", "sapatos", "calca", "blazer"]
# "level"/"multiplier" afetam o minigame de ritmo (dificuldade do beatmap e
# recompensa). As demais chaves afetam o resto do jogo, conforme pedido no
# enunciado: velocidade (player_speed_mult, agiota_speed), quantidade de
# obstáculos (npc_count) e tempo limite (chase_window, na fuga do agiota).
DIFFICULTIES = {
    "Fácil": {
        "level": 0, "multiplier": 0.85,
        "player_speed_mult": 1.05, "npc_count": 6,
        "agiota_speed": 150, "chase_window": 24.0, "muggers": 2, "mugger_speed": 150,
    },
    "Normal": {
        "level": 1, "multiplier": 1.0,
        "player_speed_mult": 1.0, "npc_count": 9,
        "agiota_speed": 185, "chase_window": 20.0, "muggers": 3, "mugger_speed": 175,
    },
    "Difícil": {
        "level": 2, "multiplier": 1.25,
        "player_speed_mult": 0.97, "npc_count": 13,
        "agiota_speed": 215, "chase_window": 16.0, "muggers": 4, "mugger_speed": 200,
    },
}
DAY_START, DAY_END = 8 * 60, 27 * 60  # o dia vai das 08:00 às 03:00 da madrugada
LATE_HOUR = 22 * 60                      # a partir daqui o jogo lembra de ir dormir
REST_BEFORE = 24 * 60                    # dormir antes da meia-noite deixa o próximo dia "descansado"
CALIBRATION_BEATS, CALIBRATION_INTERVAL, CALIBRATION_LEAD = 14, 0.5, 1.2
SETTINGS_ROWS = ("volume", "sfx_volume", "approach", "audio_offset", "calibrate", "back")
ORANGE_TEXT = (255, 176, 102)
# Volume do som ambiente por tela (0 = mudo; durante o show só toca a música).
AMBIENT_BY_STATE = {
    "menu": 0.5, "help": 0.4, "ranking": 0.4, "end_name": 0.3, "playing": 1.0, "shop": 0.5,
    "sleep_confirm": 0.5, "chase": 1.0, "paused": 0.3, "venue_info": 0.5,
    "rhythm_result": 0.0, "rhythm": 0.0, "settings": 0.3, "calibrate": 0.0,
}
HENCHMEN_PER_MISS = 2      # cada cobrança perdida depois da primeira traz mais 2 capangas
NIGHT_DANGER = 22 * 60     # a partir daqui assaltantes rondam a cidade
ROBBERY_SHARE = 0.4        # parte do dinheiro levada num assalto
ROBBERY_CLOTHES_CHANCE = 0.5  # chance de o assaltante levar também uma peça de roupa
REPEAT_PENALTY = 0.2       # cada show repetido no mesmo local, no mesmo dia, paga 20% menos...
REPEAT_FLOOR = 0.5         # ...até no mínimo metade do cachê
START_MONEY = 400
MUSIC_DIR = Path(__file__).resolve().parent / "assets" / "music"
# Cada local tem a sua música (beatmap JSON). Na fase 2 (feira e casa de shows)
# entra a "energia da plateia": se ela zerar, a apresentação termina sem pagamento.
VENUES = {
    "bar": {"name": "Barzinho", "reward": 280, "level": 0, "required": 0, "phase": 1,
            "song": "musica1.json", "song_title": "Música 1", "crowd": False, "hours": (12, 27),
            "blurb": "Um barzinho acolhedor: a plateia perdoa alguns erros.",
            "rule": "Fase 1 - acerte as notas para ganhar cachê. Sem pressão da plateia."},
    "fair": {"name": "Feira musical", "reward": 520, "level": 1, "required": 1, "phase": 2,
             "song": "musica2.json", "song_title": "Música 2", "crowd": True, "hours": (8, 18),
             "blurb": "A feira está cheia e a plateia exigente. Vista-se bem!",
             "rule": "Fase 2 - a plateia perde energia quando você erra. Se zerar, acabou o show."},
    "concert": {"name": "Casa de shows", "reward": 850, "level": 2, "required": 3, "phase": 2,
                "song": "cidade_em_pulso.json", "song_title": "Cidade em Pulso", "crowd": True, "hours": (19, 27),
                "blurb": "O palco principal da cidade: cachê alto, plateia implacável.",
                "rule": "Fase 2 - a plateia perde energia quando você erra. Se zerar, acabou o show."},
}
DIFFICULTY_TEXT = {
    "Fácil": "Notas espaçadas, agiota lento, 24 s de fuga e 2 assaltantes à noite.",
    "Normal": "Equilibrado: agiota médio, 20 s de fuga e 3 assaltantes à noite.",
    "Difícil": "Mais notas, agiota rápido, só 16 s de fuga e 4 assaltantes à noite.",
}
HELP_LINES = (
    ("Objetivo", "Pague a cobrança diária do agiota tocando nos palcos da cidade."),
    ("Mover", "WASD ou setas.  E: interagir e entrar/sair do Fusca.  I: inventário.  ESC/P: pausar"),
    ("Ritmo", "D F J K nas 4 pistas. Combos dão multiplicador (2X, 3X, 4X) e bônus no cachê."),
    ("Horários", "Feira 08h-18h, Barzinho 12h-03h, Casa de shows 19h-03h. Repetir o local no dia paga menos."),
    ("Noite", "Depois das 22h assaltantes rondam a cidade: a pé, você perde 40% do dinheiro e talvez uma roupa."),
    ("Dormir", "Durma em casa antes das 03:00 (antes da meia-noite = dia seguinte descansado)."),
    ("Loja", "A Feira pede 1 peça de roupa e a Casa de shows pede 3. O Fusca anda rápido (25% mais lento na grama)."),
    ("Cobrança", "Dívida e cobrança sobem 50% ao dia. Sem dinheiro, o agiota caça você (+2 capangas a cada nova falta)."),
    ("Derrota", "Ser pego pelo agiota ou por um capanga encerra o jogo."),
    ("Vitória", "Quite a dívida, compre a passagem e embarque no trem, ou sobreviva 30 dias."),
)


class Game:
    """Controla os estados, regras, interface e progressão do jogo."""

    def __init__(self):
        try:
            self.tiled_map = TiledMap("assets/maps/cidade.tmx")
            self.player = Player()
        except (OSError, ValueError, pygame.error) as error:
            logging.error("Falha ao carregar assets do jogo (mapa ou sprite do jogador): %s", error)
            raise
        self.player.reset_position((1280, 900))
        self.camera = Camera(
            1280,
            720,
            self.tiled_map.width,
            self.tiled_map.height,
        )
        self.ranking = Ranking()
        self.audio = AudioManager()
        self.buttons = []  # áreas clicáveis da tela atual: (retângulo, ação)
        self.clock_fn = time.perf_counter
        self.shows_today = {}  # local -> quantos shows já fez hoje
        self.rested_day = False
        self.reminders = set()
        self.muggers = []
        self.car = None
        self.driving = False
        self.popups = []      # textos grandes animados no show ("2X", "COMBO 50!")
        self.sparks = []      # partículas dos efeitos
        self.toast_kind = "info"
        self.toast_total = 0.0
        self.settings_index = 0
        self.calibration = None
        self.mouse_pos = (-1, -1)
        self.venue_info = None
        self.nav = NavGrid(
            self.tiled_map.solid_rects, self.tiled_map.width, self.tiled_map.height,
            ground=self.tiled_map.is_ground_cell,
        )

        pygame.font.init()
        self.font_title = ui.load_font("Bold", 40)
        self.font_large = ui.load_font("Bold", 26)
        self.font = ui.load_font("Medium", 19)
        self.font_small = ui.load_font("Medium", 15)
        self.font_tiny = ui.load_font("Medium", 13)
        self.font_big_number = ui.load_font("Bold", 30)
        self.font_label = ui.load_font("Bold", 12)
        self.font_huge = ui.load_font("Bold", 110)
        self.font_combo = ui.load_font("Bold", 52)

        self.state = "menu"
        self.menu_index = 0
        self.difficulty_names = list(DIFFICULTIES.keys())
        self.difficulty_index = 1
        self.difficulty = "Normal"
        self.has_save = savegame.has_save()
        self.menu_options = self._build_menu()
        self.paused_from = "playing"
        self.ranking_filter = None  # None = todas as dificuldades
        self.victory_bonus = 0
        self.selected_zone = None
        self.shop_index = 0
        self.shop_stock = []
        self.inventory = []
        self.money = 0
        self.debt = 1000
        self.daily_payment = 200
        self.day = 1
        self.phase = 1
        self.clock_minutes = 8 * 60
        self.score = 0
        self.songs_performed = 0
        self.tired_day = False
        self.toast_text = ""
        self.toast_timer = 0.0
        self.end_result = None
        self.end_reason = ""
        self.result_saved = False
        self.player_name = ""
        self.rank_return_state = "menu"

        # Estado temporário das apresentações.
        self.active_venue = None
        self.rhythm = None
        self.rhythm_settings = load_settings()
        self.audio.set_volume(self.rhythm_settings["sfx_volume"] / 100)
        self.rhythm_result = None
        self.rhythm_target_y = 515
        self.rhythm_lanes = [490, 590, 690, 790]

        # NPCs que caminham pela cidade e o agiota que persegue o jogador
        # quando uma cobrança não é paga.
        self.npcs = []
        self.hunters = []  # agiota + capangas durante a caçada
        self.missed_payments = 0
        self.chase_timer = 0.0
        self.chase_window = 0.0

        self._refresh_shop_stock()

    # ------------------------------------------------------------------
    # Eventos e atualização
    # ------------------------------------------------------------------
    def handle_event(self, event):
        if self.state == "rhythm" and event.type in (pygame.KEYDOWN, pygame.KEYUP):
            self._handle_rhythm_key(event)
            return
        if self.state == "calibrate" and event.type == pygame.KEYDOWN:
            self._handle_calibration_key(event.key)
            return
        if event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos  # já em coordenadas do jogo (convertido em main.py)
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if getattr(event, "button", 1) == 1:
                for rect, action in self.buttons:
                    if rect.collidepoint(event.pos):
                        action()
                        break
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            muted = self.audio.toggle_mute()
            self._set_toast("Som desligado (F2 liga de novo)." if muted else "Som ligado.")
            return
        focus_lost = getattr(pygame, "WINDOWFOCUSLOST", None)
        if focus_lost is not None and event.type == focus_lost and self.state in ("playing", "chase"):
            self._pause()  # tirar o foco da janela pausa o jogo
            return
        if event.type != pygame.KEYDOWN:
            return

        if self.state == "menu":
            self._handle_menu(event.key)
        elif self.state == "help":
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
                self.audio.play("ui_back")
                self.state = "menu"
        elif self.state == "settings":
            self._handle_settings(event.key)
        elif self.state == "playing":
            self._handle_playing(event.key)
        elif self.state == "chase":
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self._pause()
        elif self.state == "shop":
            self._handle_shop(event.key)
        elif self.state == "sleep_confirm":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._confirm_sleep()
            elif event.key in (pygame.K_ESCAPE, pygame.K_e):
                self._cancel_sleep()
        elif self.state == "venue_info":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
                self._confirm_venue()
            elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_q):
                self._cancel_venue()
        elif self.state == "rhythm_result":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.audio.play("ui_confirm")
                self._leave_rhythm_result()
        elif self.state == "paused":
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_p):
                self.state = self.paused_from
            elif event.key == pygame.K_m:
                self._back_to_menu()
        elif self.state == "ranking":
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self._cycle_ranking_filter(-1)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self._cycle_ranking_filter(1)
            elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_m):
                self.state = self.rank_return_state
        elif self.state == "end_name":
            self._handle_name_entry(event)

    def _update_ambient(self, dt):
        """Dia/noite e volume do som ambiente conforme o relógio do jogo e a tela atual."""
        level = AMBIENT_BY_STATE.get(self.state, 0.0)
        hour = (self.clock_minutes / 60) % 24
        if 7 <= hour < 18:
            night = 0.0
        elif 18 <= hour < 20:
            night = (hour - 18) / 2
        elif hour >= 20 or hour < 5:
            night = 1.0
        else:  # 5h-7h: amanhecendo
            night = (7 - hour) / 2
        self.audio.set_ambient(level * (1 - night), level * night)
        self.audio.update(dt)

    def update(self, dt):
        if self.toast_timer > 0:
            self.toast_timer = max(0, self.toast_timer - dt)
        self._update_ambient(dt)

        # O tempo avança enquanto o jogador está no mundo ou em uma atividade.
        if self.state in ("playing", "shop", "rhythm", "chase"):
            self.clock_minutes += dt * 6
            # Se o relógio chegar às 03:00 durante uma música/QTE/perseguição,
            # deixa a atividade terminar e só então inicia o próximo dia.
            if self.clock_minutes >= 27 * 60 and self.state not in ("rhythm", "chase"):
                self._advance_day(slept=False, forced=True)

        if self.state == "calibrate":
            self._update_calibration()

        if self.state == "playing":
            self._update_reminders()
            self._update_npcs(dt)
            self._move_player(dt)
            self._update_muggers(dt)

        elif self.state == "rhythm":
            self._update_rhythm(dt)


        elif self.state == "chase":
            self._update_chase(dt)

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------
    def _build_menu(self):
        options = ["Continuar"] if self.has_save else []
        options += ["Novo jogo", "Dificuldade", "Ranking", "Como jogar", "Ajustes", "Sair"]
        return options

    def _pause(self):
        self.paused_from = self.state
        self.state = "paused"

    def _back_to_menu(self):
        if self.paused_from == "playing":
            self._autosave()
        self.hunters = []
        self.has_save = savegame.has_save()
        self.menu_options = self._build_menu()
        self.menu_index = 0
        self.state = "menu"

    def _cycle_ranking_filter(self, step):
        options = [None] + self.difficulty_names
        index = options.index(self.ranking_filter)
        self.ranking_filter = options[(index + step) % len(options)]

    def _set_difficulty(self, step):
        self.difficulty_index = (self.difficulty_index + step) % len(self.difficulty_names)
        self.difficulty = self.difficulty_names[self.difficulty_index]
        self.audio.play("ui_move")

    def _handle_menu(self, key):
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_index = (self.menu_index - 1) % len(self.menu_options)
            self.audio.play("ui_move")
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_index = (self.menu_index + 1) % len(self.menu_options)
            self.audio.play("ui_move")
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_KP1, pygame.K_KP2, pygame.K_KP3):
            numbers = {pygame.K_1: 0, pygame.K_KP1: 0, pygame.K_2: 1, pygame.K_KP2: 1, pygame.K_3: 2, pygame.K_KP3: 2}
            self.difficulty_index = numbers[key]
            self.difficulty = self.difficulty_names[self.difficulty_index]
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            if self.menu_options[self.menu_index] == "Dificuldade":
                self._set_difficulty(-1 if key in (pygame.K_LEFT, pygame.K_a) else 1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate_menu_option()
        elif key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _activate_menu_option(self):
        self.audio.play("ui_confirm")
        choice = self.menu_options[self.menu_index]
        if choice == "Continuar":
            self._load_saved_game()
        elif choice == "Novo jogo":
            self._start_new_game()
        elif choice == "Dificuldade":
            self._set_difficulty(1)
        elif choice == "Ranking":
            self.end_result = None
            self.result_saved = False
            self.rank_return_state = "menu"
            self.state = "ranking"
        elif choice == "Como jogar":
            self.state = "help"
        elif choice == "Ajustes":
            self.settings_index = 0
            self.state = "settings"
        else:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _click_menu_option(self, index):
        self.menu_index = index
        self._activate_menu_option()

    def _start_new_game(self, announce=True):
        self.player = Player()
        self.player.reset_position((1280, 900))
        self.player.base_speed = round(300 * DIFFICULTIES[self.difficulty]["player_speed_mult"])
        self.inventory = []
        self.money = START_MONEY
        self.debt = 1000
        self.daily_payment = 200
        self.day = 1
        self.phase = 1
        self.clock_minutes = 8 * 60
        self.score = 0
        self.songs_performed = 0
        self.tired_day = False
        self.end_result = None
        self.end_reason = ""
        self.result_saved = False
        self.active_venue = None
        self.rhythm = None
        self.rhythm_result = None
        self.missed_payments = 0
        self.hunters = []
        self.muggers = []
        self.car = None
        self.driving = False
        self.chase_timer = 0.0
        self.chase_window = 0.0
        self.victory_bonus = 0
        self.paused_from = "playing"
        self.shows_today = {}
        self.rested_day = False
        self.reminders = set()
        self._spawn_npcs()
        self._refresh_shop_stock()
        self.camera.update(self.player)

        # O jogo começa depois de pagar a primeira cobrança da manhã.
        self.money -= self.daily_payment
        self.debt = max(0, self.debt - self.daily_payment)
        logging.info("Nova partida. Dificuldade=%s; cobrança inicial paga=%s", self.difficulty, self.daily_payment)
        self.state = "playing"
        if announce:
            self._set_toast(f"Dia 1: cobrança de R$ {self.daily_payment} paga. Vá trabalhar!")

    # ------------------------------------------------------------------
    # NPCs e agiota
    # ------------------------------------------------------------------
    def _spawn_npcs(self):
        """Cria os moradores que passeiam pela cidade; a quantidade varia com a dificuldade."""
        palette = [
            (214, 197, 150), (176, 196, 214), (196, 176, 214),
            (176, 214, 186), (214, 176, 176), (214, 214, 150),
        ]
        count = DIFFICULTIES[self.difficulty]["npc_count"]
        self.npcs = []
        for index in range(count):
            point = self.nav.random_free_point(near=self.player.rect.center, min_distance=140)
            if point is None:
                break
            self.npcs.append(NPC(point, random.uniform(55, 85), self.nav, palette[index % len(palette)]))

    def _body(self):
        """Hitbox de quem está no mapa: o Fusca (dirigindo) ou o personagem a pé."""
        return self.car.hitbox if self.driving and self.car is not None else self.player.hitbox

    def _npc_blockers(self, npc):
        """O que bloqueia um morador: o jogador e os outros moradores."""
        others = [other.hitbox for other in self.npcs if other is not npc]
        return others + [self._body()]

    def _input_direction(self):
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT]),
            (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP]),
        )
        return direction

    def _move_player(self, dt):
        obstacles = self.tiled_map.solid_rects + self._npc_obstacles()
        if self.driving and self.car is not None:
            on_grass = self.tiled_map.is_grass_at(self.car.position)
            self.car.update(dt, self._input_direction(), obstacles,
                            self.tiled_map.width, self.tiled_map.height, on_grass)
            self.player.reset_position((round(self.car.position.x), round(self.car.position.y) - 15))
            self.player.stunned_timer = max(0.0, self.player.stunned_timer - dt)
        else:
            on_grass = self.tiled_map.is_grass_at(self.player.rect.center)
            self.player.tired = self.tired_day
            self.player.rested = self.rested_day
            self.player.update(dt, obstacles, self.tiled_map.width, self.tiled_map.height, on_grass=on_grass)
        self.camera.update(self.player)

    # ---- Fusca
    def _spawn_car_near_shop(self):
        shop = next(zone for zone in ZONES if zone["id"] == "shop")
        point = (self.nav.random_free_point(near=shop["position"], radius_cells=3, min_distance=40)
                 or self.nav.random_free_point(near=shop["position"], radius_cells=8) or shop["position"])
        self.car = Car(point)

    def _car_nearby(self):
        return (self.car is not None and not self.driving
                and self.car.position.distance_to(self.player.hitbox.center) <= 48)

    def _enter_car(self):
        self.driving = True
        self.car.velocity.update(0, 0)
        self.audio.play("ui_confirm")
        logging.info("Jogador entrou no Fusca")

    def _place_player_feet(self, point):
        # Hitbox dos pés fica 39 px abaixo do topo do sprite; centraliza o sprite para os pés caírem no ponto.
        self.player.reset_position((round(point[0]), round(point[1]) - 15))

    def _exit_car(self):
        probe = pygame.Rect(0, 0, 18, 14)
        center = self.car.position
        for dx, dy in ((0, 30), (-36, 0), (36, 0), (0, -30), (-36, 28), (36, 28), (-36, -28), (36, -28), (0, 52)):
            probe.center = (round(center.x + dx), round(center.y + dy))
            inside = 0 <= probe.left and probe.right <= self.tiled_map.width and 0 <= probe.top and probe.bottom <= self.tiled_map.height
            if inside and not any(probe.colliderect(wall) for wall in self.tiled_map.solid_rects):
                self.driving = False
                self.car.velocity.update(0, 0)
                self._place_player_feet(probe.center)
                self.audio.play("ui_back")
                return True
        self.audio.play("error")
        self._set_toast("Sem espaço para sair do carro aqui.", kind="warn")
        return False

    # ---- Assaltantes da madrugada
    def _spawn_muggers(self):
        settings = DIFFICULTIES[self.difficulty]
        self.muggers = []
        for _ in range(settings["muggers"]):
            point = self.nav.random_free_point(near=self.player.rect.center, min_distance=520)
            if point is not None:
                self.muggers.append(Mugger(point, settings["mugger_speed"], self.nav))
        logging.info("Noite: %s assaltantes na cidade", len(self.muggers))

    def _update_muggers(self, dt):
        if self.clock_minutes >= NIGHT_DANGER and "muggers" not in self.reminders:
            self.reminders.add("muggers")
            self._spawn_muggers()
        if not self.muggers:
            return
        body = self._body()
        target = None if self.driving else body.center  # no carro você está a salvo
        for mugger in list(self.muggers):
            blockers = [npc.hitbox for npc in self.npcs] + [m.hitbox for m in self.muggers if m is not mugger]
            mugger.update(dt, blockers, target)
            if target is not None and mugger.hitbox.inflate(6, 6).colliderect(body) and self.player.stunned_timer <= 0:
                self._robbed(mugger)

    def _robbed(self, mugger):
        lost = int(self.money * ROBBERY_SHARE)
        self.money -= lost
        clothes = [item for item in self.inventory if ITEMS[item]["kind"] == "roupa"]
        stolen = random.choice(clothes) if clothes and random.random() < ROBBERY_CLOTHES_CHANCE else None
        if stolen:
            self.inventory.remove(stolen)
        self.player.stun(2.5)
        self.muggers.remove(mugger)  # o assaltante foge com o que levou
        self.audio.play("caught")
        message = f"Assalto! Levaram {ui.money(lost)}"
        message += f" e o seu {ITEMS[stolen]['name'].lower()}." if stolen else "."
        self._set_toast(message + " Fique em casa à noite ou ande de Fusca.", seconds=5, kind="bad")
        logging.info("Jogador assaltado no dia %s: perdeu R$ %s%s", self.day, lost,
                     f" e {stolen}" if stolen else "")

    def _update_npcs(self, dt):
        for npc in self.npcs:
            npc.update(dt, self._npc_blockers(npc))

    def _npc_obstacles(self):
        """Hitboxes dos moradores para a colisão do jogador.

        Quem já está sobreposto ao jogador é ignorado, para que ninguém
        consiga prender o personagem encostando nele.
        """
        return [npc.hitbox for npc in self.npcs if not npc.hitbox.colliderect(self.player.hitbox)]

    def _hunter_spawns(self, count):
        """Cantos (e meios das bordas) do mapa, do mais longe para o mais perto do jogador."""
        w, h = self.tiled_map.width, self.tiled_map.height
        spots = [(60, 60), (w - 60, 60), (60, h - 60), (w - 60, h - 60),
                 (w / 2, 60), (w / 2, h - 60), (60, h / 2), (w - 60, h / 2)]
        spots.sort(key=lambda spot: -math.dist(spot, self.player.rect.center))
        points = []
        for index in range(count):
            corner = spots[index % len(spots)]
            point = (self.nav.random_free_point(near=corner, radius_cells=8)
                     or self.nav.random_free_point(near=corner, radius_cells=20)
                     or self.nav.random_free_point(near=self.player.rect.center, min_distance=300)
                     or corner)
            points.append(point)
        return points

    def _start_chase(self):
        """Cobrança perdida: o agiota (e, a partir da 2ª falta, capangas) caçam o jogador."""
        settings = DIFFICULTIES[self.difficulty]
        self.chase_window = settings["chase_window"]
        self.chase_timer = self.chase_window
        henchmen = HENCHMEN_PER_MISS * max(0, self.missed_payments - 1)
        spawns = self._hunter_spawns(1 + henchmen)
        self.hunters = [Agiota(spawns[0], settings["agiota_speed"], self.nav, role="direct")]
        roles = (("flank", 1), ("flank", -1), ("intercept", 1), ("cutoff", 1), ("direct", 1), ("intercept", -1))
        for index, point in enumerate(spawns[1:]):
            role, side = roles[index % len(roles)]
            speed = settings["agiota_speed"] * random.uniform(0.84, 0.97)
            self.hunters.append(Capanga(point, speed, self.nav, role=role, side=side))
        self._body_prev = pygame.Vector2(self._body().center)
        self._body_velocity = pygame.Vector2()
        for hunter in self.hunters:
            hunter.set_goal(self._body().center)
        self.state = "chase"
        self.audio.play("alarm")
        who = "o agiota" if not henchmen else f"o agiota e {henchmen} capangas"
        self._set_toast(f"Sem dinheiro para a cobrança! {who.capitalize()} estão atrás de você. "
                        f"Sobreviva {int(self.chase_window)}s sem ser pego!" if henchmen else
                        f"Sem dinheiro para a cobrança! O agiota está atrás de você. Sobreviva {int(self.chase_window)}s!",
                        seconds=5, kind="bad")
        logging.info("Caçada iniciada no dia %s (cobrança perdida nº %s, %s capangas)",
                     self.day, self.missed_payments, henchmen)

    def _hunter_target(self, hunter, player, velocity):
        """Para onde cada caçador corre, conforme o papel dele (evita que andem todos juntos)."""
        distance = hunter.position.distance_to(player)
        if hunter.role == "direct" or distance < 150:
            return player
        if hunter.role == "intercept":
            lead = velocity * min(1.3, distance / 260)
            if lead.length() > 320:
                lead.scale_to_length(320)
            target = player + lead
        elif hunter.role == "cutoff" and velocity.length_squared() > 400:
            target = player + velocity.normalize() * 300
        elif hunter.role == "flank":
            toward = player - hunter.position
            side = pygame.Vector2(-toward.y, toward.x).normalize() * hunter.side * min(240, distance * 0.55)
            target = player + side
        else:
            target = player
        target.x = max(16, min(self.tiled_map.width - 16, target.x))
        target.y = max(16, min(self.tiled_map.height - 16, target.y))
        return target

    def _separate_hunters(self):
        """Empurra caçadores muito próximos para lados opostos, sem entrar em prédios."""
        for i, a in enumerate(self.hunters):
            for b in self.hunters[i + 1:]:
                offset = a.position - b.position
                distance = offset.length()
                if distance >= 34:
                    continue
                if distance < 0.01:
                    offset = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                    distance = max(offset.length(), 0.01)
                push = offset / distance * (34 - distance) / 2
                for hunter, step in ((a, push), (b, -push)):
                    candidate = hunter.position + step
                    if self.nav.is_free(self.nav.cell_of(candidate)):
                        hunter.position.update(candidate)
                        hunter._sync_hitbox()

    def _update_chase(self, dt):
        self._update_npcs(dt)
        self._move_player(dt)
        body = self._body()
        player = pygame.Vector2(body.center)
        if dt > 0:
            measured = (player - getattr(self, "_body_prev", player)) / dt
            self._body_velocity = getattr(self, "_body_velocity", pygame.Vector2()) * 0.8 + measured * 0.2
        self._body_prev = player
        blockers = [npc.hitbox for npc in self.npcs]
        for hunter in self.hunters:
            hunter.update(dt, blockers, self._hunter_target(hunter, player, pygame.Vector2(self._body_velocity)))
        self._separate_hunters()
        for hunter in self.hunters:
            if body.colliderect(hunter.hitbox):
                self._resolve_chase(caught=True, by=hunter)
                return
        self.chase_timer -= dt
        if self.chase_timer <= 0:
            self._resolve_chase(caught=False)

    def _resolve_chase(self, caught, by=None):
        self.hunters = []
        if caught:
            who = "um capanga do agiota" if isinstance(by, Capanga) else "o agiota"
            self.audio.play("caught")
            logging.info("Jogador pego por %s no dia %s", who, self.day)
            self._finish_game("derrota", f"Você foi pego por {who} no dia {self.day}.")
            return
        self.audio.play("escape")
        self._set_toast("Você despistou a cobrança por hoje! Mas a dívida continua crescendo.", seconds=4, kind="good")
        logging.info("Jogador escapou da caçada no dia %s", self.day)
        self.state = "playing"

    def _handle_playing(self, key):
        if key == pygame.K_ESCAPE or key == pygame.K_p:
            self._pause()
        elif key in (pygame.K_e, pygame.K_RETURN):
            if self.driving:
                self._exit_car()
                return
            zone = self._nearby_zone()
            car_distance = self.car.position.distance_to(self.player.hitbox.center) if self._car_nearby() else None
            zone_distance = pygame.Vector2(self.player.rect.center).distance_to(zone["position"]) if zone else None
            if car_distance is not None and (zone_distance is None or car_distance < zone_distance):
                self._enter_car()
            elif zone:
                self._interact(zone)
            else:
                self.audio.play("error", 0.6)
                self._set_toast("Chega mais perto de um local para interagir.")
        elif key == pygame.K_i:
            owned = [ITEMS[item]["name"] for item in self.inventory]
            self._set_toast("Inventário vazio." if not owned else "Inventário: " + ", ".join(owned))

    def _nearby_zone(self):
        player_center = pygame.Vector2(self.player.rect.center)
        available = []
        for zone in ZONES:
            distance = player_center.distance_to(zone["position"])
            if distance <= 92:
                available.append((distance, zone))
        return min(available, key=lambda result: result[0])[1] if available else None

    def _interact(self, zone):
        zone_id = zone["id"]
        if zone_id == "shop":
            self.shop_index = 0
            self.audio.play("ui_confirm")
            self.state = "shop"
        elif zone_id in VENUES:
            venue = VENUES[zone_id]
            clothing_count = sum(1 for item in self.inventory if ITEMS[item]["kind"] == "roupa")
            if clothing_count < venue["required"]:
                missing = venue["required"] - clothing_count
                self.audio.play("error")
                self._set_toast(f"Precisa de {missing} peça(s) de roupa a mais para tocar aqui. Passe na loja!", kind="warn")
                return
            self.active_venue = zone_id
            self.venue_info = self._load_venue_info(zone_id)
            self.audio.play("ui_confirm")
            self.state = "venue_info"  # a ficha abre mesmo fechado: ela mostra o horário
        elif zone_id == "home":
            self.audio.play("ui_confirm")
            self.state = "sleep_confirm"
        elif zone_id == "station":
            if "passagem" in self.inventory:
                self._finish_game("vitória", "Você embarcou no trem e escapou da cobrança!")
            else:
                self.audio.play("error")
                self._set_toast("A estação exige uma passagem de trem. Compre na loja.", kind="warn")

    def _refresh_shop_stock(self):
        # As roupas disponíveis mudam diariamente; carro e passagem ficam à venda.
        start = (self.day - 1) % len(CLOTHING_KEYS)
        clothes = [CLOTHING_KEYS[(start + i) % len(CLOTHING_KEYS)] for i in range(3)]
        self.shop_stock = clothes + ["fusca", "passagem"]

    def _handle_shop(self, key):
        if key == pygame.K_ESCAPE:
            self.audio.play("ui_back")
            self.state = "playing"
        elif key in (pygame.K_UP, pygame.K_w) and self.shop_stock:
            self.shop_index = (self.shop_index - 1) % len(self.shop_stock)
            self.audio.play("ui_move")
        elif key in (pygame.K_DOWN, pygame.K_s) and self.shop_stock:
            self.shop_index = (self.shop_index + 1) % len(self.shop_stock)
            self.audio.play("ui_move")
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._buy_selected_item()

    def _buy_selected_item(self):
        if not self.shop_stock:
            self.audio.play("error")
            self._set_toast("A loja está sem estoque hoje.")
            return

        item_key = self.shop_stock[self.shop_index]
        item = ITEMS[item_key]

        if item_key in self.inventory:
            self.audio.play("error")
            self._set_toast("Você já possui esse item.", kind="warn")
            return
        if self.money < item["price"]:
            self.audio.play("error")
            self._set_toast(f"Dinheiro insuficiente. Custa R$ {item['price']}.", kind="bad")
            return

        self.money -= item["price"]
        self.inventory.append(item_key)
        self.shop_stock.pop(self.shop_index)
        if self.shop_stock:
            self.shop_index %= len(self.shop_stock)
        else:
            self.shop_index = 0

        logging.info("Item comprado: %s por R$ %s", item_key, item["price"])
        self.audio.play("spend")
        if item_key == "fusca":
            self._spawn_car_near_shop()
            self._set_toast("Fusca comprado! Ele está estacionado ao lado da loja: chegue perto e aperte E.",
                            seconds=5, kind="good")
            return
        self._set_toast(f"Comprou {item['name']} por {ui.money(item['price'])}.", kind="good")

    def _advance_day(self, slept, forced=False):
        if self.state == "end_name":
            return

        self.rested_day = bool(slept and self.clock_minutes < REST_BEFORE)
        self.shows_today = {}
        self.reminders = set()
        self.muggers = []
        self.day += 1
        self.debt = math.ceil(self.debt * 1.5)
        self.daily_payment = math.ceil(self.daily_payment * 1.5)
        self.clock_minutes = 180 if forced else 8 * 60
        self.tired_day = bool(forced and not slept)
        if self.tired_day:
            self.rested_day = False
        self.player.tired = self.tired_day
        self.player.rested = self.rested_day

        if self.money < self.daily_payment:
            self.missed_payments += 1
            logging.warning(
                "Cobrança de R$ %s não paga no dia %s (cobrança perdida nº %s)",
                self.daily_payment, self.day, self.missed_payments,
            )
            self._start_chase()
            return

        self.money -= self.daily_payment
        self.debt = max(0, self.debt - self.daily_payment)
        self.audio.play("newday")
        self._refresh_shop_stock()
        logging.info(
            "Dia %s: cobrança de R$ %s paga; dinheiro=%s; dívida=%s",
            self.day,
            self.daily_payment,
            self.money,
            self.debt,
        )

        if self.debt <= 0:
            self._finish_game("vitória", "Você quitou a dívida inteira e o agiota não tem mais o que cobrar!")
            return
        if self.day >= 30:
            self._finish_game("vitória", "Você sobreviveu por 30 dias e o agiota morreu de velhice!")
            return

        paid = ui.money(self.daily_payment)
        if forced:
            self._set_toast(f"03:00 e você não dormiu! Dia {self.day}: cobrança de {paid} paga, "
                            "mas hoje você está cansado e anda mais devagar.", seconds=5, kind="warn")
        elif self.rested_day:
            self._set_toast(f"Dia {self.day}: você dormiu cedo e acordou descansado (+10% de velocidade). "
                            f"Cobrança de {paid} paga.", seconds=5, kind="good")
        else:
            self._set_toast(f"Dia {self.day}: cobrança de {paid} paga ao agiota.", seconds=4, kind="info")

        self.state = "playing"
        self._autosave()

    # ------------------------------------------------------------------
    # Minigame de ritmo
    # ------------------------------------------------------------------
    def _load_venue_info(self, venue_id):
        """Dados mostrados na tela do local. Já valida música e fase para avisar antes de entrar."""
        venue = VENUES[venue_id]
        level = DIFFICULTIES[self.difficulty]["level"] + venue["level"]
        info = {"ok": False, "error": "", "level": level + 1, "song": venue["song_title"],
                "max_reward": round(reward_for(1.0, venue["reward"], DIFFICULTIES[self.difficulty]["multiplier"])
                                    * self._pay_factor(venue_id))}
        try:
            beatmap = load_beatmap(MUSIC_DIR / venue["song"], level)
        except Exception as error:  # qualquer falha vira aviso na tela e registro em error.log
            logging.exception("Música de %s indisponível", venue["name"])
            info["error"] = f"{type(error).__name__}: {error}"
            return info
        info.update(ok=True, duration=beatmap["duration"], bpm=beatmap["bpm"], notes=len(beatmap["notes"]))
        return info

    def _pay_factor(self, venue_id):
        """Cachê cai 20% a cada repetição do mesmo local no mesmo dia (mínimo 50%)."""
        return max(REPEAT_FLOOR, 1.0 - REPEAT_PENALTY * self.shows_today.get(venue_id, 0))

    def _venue_status(self, venue_id):
        """(pode tocar agora?, texto curto, cor) conforme o horário de funcionamento."""
        venue = VENUES[venue_id]
        opens, closes = venue["hours"]
        if not opens * 60 <= self.clock_minutes < closes * 60:
            if self.clock_minutes < opens * 60:
                return False, f"Fechado - abre às {opens:02d}:00", ui.MUTED
            return False, "Fechado por hoje", ui.MUTED
        factor = self._pay_factor(venue_id)
        if factor < 1:
            return True, f"Aberto até {closes % 24:02d}:00 - cachê {round(factor * 100)}%", ui.GOLD
        return True, f"Aberto até {closes % 24:02d}:00", ui.GREEN

    def _confirm_venue(self):
        if self.venue_info is None or not self.venue_info["ok"]:
            self.audio.play("error")
            return
        available, reason, _ = self._venue_status(self.active_venue)
        if not available:
            self.audio.play("error")
            self._set_toast(f"{VENUES[self.active_venue]['name']}: {reason.lower()}.", kind="warn")
            self.active_venue = None
            self.state = "playing"
            return
        self.phase = max(self.phase, VENUES[self.active_venue]["phase"])
        self.audio.play("stage_start")
        self._start_rhythm(self.active_venue)

    def _cancel_venue(self):
        self.audio.play("ui_back")
        self.active_venue = None
        self.venue_info = None
        self.state = "playing"

    def _start_rhythm(self, venue_id):
        self.rhythm_result = None
        venue = VENUES[venue_id]
        level = DIFFICULTIES[self.difficulty]["level"] + venue["level"]
        try:
            beatmap = load_beatmap(MUSIC_DIR / venue["song"], level)
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(beatmap["audio"]))
            pygame.mixer.music.set_volume(self.rhythm_settings["volume"] / 100)
            self.rhythm = RhythmSession(beatmap, self.rhythm_settings.copy(), crowd_meter=venue["crowd"])
            pygame.mixer.music.play()
            self.rhythm.start()
        except Exception as error:  # música, mixer ou beatmap: registra tudo e volta ao mapa
            logging.exception("Falha ao iniciar apresentação em %s", venue["name"])
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            self.rhythm = None
            self.active_venue = None
            self.state = "playing"
            self._set_toast(f"Não foi possível iniciar a música ({type(error).__name__}). Veja logs/error.log.", seconds=5)
            return
        self.state = "rhythm"
        logging.info("Começou apresentação em %s (%s), nível %s", venue["name"], venue["song"], level)

    def _update_rhythm(self, dt):
        position = pygame.mixer.music.get_pos() if hasattr(pygame.mixer.music, "get_pos") else -1
        if position and position > 0:
            self.rhythm.sync_to_audio(position / 1000)
        self.rhythm.update()
        self._collect_rhythm_events()
        self._update_effects(dt)
        if not pygame.mixer.music.get_busy() and self.rhythm.song_time() < self.rhythm.map["duration"] - 1.0:
            self._abandon_rhythm("Reprodução interrompida. Sem pagamento.")
        elif self.rhythm.failed:
            self._finish_rhythm(failed=True)
        elif self.rhythm.finished:
            self._finish_rhythm()

    def _handle_rhythm_key(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._abandon_rhythm("Apresentação abandonada: sem pagamento.")
            return
        key_to_lane = {pygame.K_d: 0, pygame.K_f: 1, pygame.K_j: 2, pygame.K_k: 3}
        lane = key_to_lane.get(event.key)
        if lane is not None:
            if event.type == pygame.KEYDOWN:
                self.rhythm.key_down(lane)
            else:
                self.rhythm.key_up(lane)

    def _abandon_rhythm(self, message):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
        self.rhythm = None
        self.active_venue = None
        self.state = "playing"
        self._set_toast(message)

    def _finish_rhythm(self, failed=False):
        pygame.mixer.music.stop()
        venue = VENUES[self.active_venue]
        accuracy = self.rhythm.accuracy
        bonus = None if failed else self.rhythm.bonus()
        factor = self._pay_factor(self.active_venue)
        if failed:  # a plateia vaiou: sem cachê e sem pontos de bônus
            reward, lost_item = 0, None
        else:
            reward = reward_for(accuracy, venue["reward"], DIFFICULTIES[self.difficulty]["multiplier"])
            reward = round(reward * factor * (bonus[1] if bonus else 1.0))
            lost_item = self._lose_random_item() if accuracy < 0.65 else None
            self.score += self.rhythm.score // 10
            self.score += reward // 10
        self.money += reward
        self.shows_today[self.active_venue] = self.shows_today.get(self.active_venue, 0) + 1
        self.audio.play("boo" if failed else "cash" if reward > 0 else "error")
        self.songs_performed += 1
        self.rhythm_result = {"venue": venue["name"], "song": venue["song_title"], "accuracy": accuracy,
                              "score": self.rhythm.score, "combo": self.rhythm.max_combo,
                              "counts": self.rhythm.counts.copy(), "reward": reward,
                              "failed": failed, "crowd": self.rhythm.crowd, "bonus": bonus,
                              "factor": factor,
                              "lost_item": ITEMS[lost_item]["name"] if lost_item else None}
        logging.info(
            "Apresentação %s (%s): precisão=%.2f%%; pontos=%s; pagamento=%s%s",
            venue["name"], venue["song_title"], accuracy * 100, self.rhythm.score, reward,
            "; plateia vaiou" if failed else "",
        )
        self.active_venue = None
        self.rhythm = None
        self.state = "rhythm_result"

    def _leave_rhythm_result(self):
        self.state = "playing"
        self._autosave()

    def _lose_random_item(self):
        """Apresentação ruim: perde uma peça de roupa (Fusca e passagem não se perdem)."""
        clothes = [item for item in self.inventory if ITEMS[item]["kind"] == "roupa"]
        if not clothes:
            return None
        item_key = random.choice(clothes)
        self.inventory.remove(item_key)
        logging.info("Item perdido: %s", item_key)
        return item_key

    # ------------------------------------------------------------------
    # Ajustes e calibração da sincronia
    # ------------------------------------------------------------------
    def _handle_settings(self, key):
        row = SETTINGS_ROWS[self.settings_index]
        if key in (pygame.K_UP, pygame.K_w):
            self.settings_index = (self.settings_index - 1) % len(SETTINGS_ROWS)
            self.audio.play("ui_move")
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.settings_index = (self.settings_index + 1) % len(SETTINGS_ROWS)
            self.audio.play("ui_move")
        elif key in (pygame.K_LEFT, pygame.K_a):
            self._change_setting(row, -1)
        elif key in (pygame.K_RIGHT, pygame.K_d):
            self._change_setting(row, 1)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            if row == "calibrate":
                self._start_calibration()
            elif row == "back":
                self._leave_settings()
            else:
                self._change_setting(row, 1)
        elif key == pygame.K_ESCAPE:
            self._leave_settings()

    def _change_setting(self, row, direction):
        settings = self.rhythm_settings
        if row in ("volume", "sfx_volume"):
            settings[row] = max(0, min(100, settings[row] + 10 * direction))
        elif row == "approach":  # para a direita = notas mais rápidas (menos tempo na tela)
            settings[row] = round(max(1.0, min(3.0, settings[row] - 0.1 * direction)), 2)
        elif row == "audio_offset":
            settings[row] = max(-300, min(300, settings[row] + 10 * direction))
        else:
            return
        self.audio.set_volume(settings["sfx_volume"] / 100)
        self.audio.play("ui_move")
        self._save_rhythm_settings()

    def _save_rhythm_settings(self):
        try:
            save_settings(self.rhythm_settings)
        except OSError as error:
            logging.error("Não foi possível salvar os ajustes: %s", error)

    def _leave_settings(self):
        self.audio.play("ui_back")
        self._save_rhythm_settings()
        self.state = "menu"

    def _start_calibration(self):
        """Toca batidas regulares; o jogador aperta junto com o som e medimos o atraso."""
        self.audio.play("ui_confirm")
        self.calibration = {"start": self.clock_fn() + CALIBRATION_LEAD, "next": 0, "beats": [],
                            "taps": [], "done": False, "result": None, "flash": -10.0}
        self.state = "calibrate"

    def _update_calibration(self):
        calibration, now = self.calibration, self.clock_fn()
        if calibration is None or calibration["done"]:
            return
        while (calibration["next"] < CALIBRATION_BEATS
               and now >= calibration["start"] + calibration["next"] * CALIBRATION_INTERVAL):
            self.audio.play("tick", force=True)
            calibration["beats"].append(now)
            calibration["next"] += 1
        if calibration["next"] >= CALIBRATION_BEATS and now >= calibration["beats"][-1] + 0.6:
            calibration["done"] = True
            calibration["result"] = self._calibration_result()

    def _calibration_result(self):
        """Mediana do atraso entre cada batida e o toque mais próximo (ignora as 3 primeiras)."""
        calibration = self.calibration
        offsets = []
        for beat in calibration["beats"][3:]:
            near = [tap - beat for tap in calibration["taps"] if abs(tap - beat) <= 0.3]
            if near:
                offsets.append(min(near, key=abs))
        if len(offsets) < 6:
            return None
        offsets.sort()
        return int(round(max(-300, min(300, offsets[len(offsets) // 2] * 1000))))

    def _handle_calibration_key(self, key):
        calibration = self.calibration
        if key == pygame.K_ESCAPE:
            self.audio.play("ui_back")
            self.state = "settings"
            return
        if calibration["done"]:
            if key in (pygame.K_RETURN, pygame.K_SPACE):
                if calibration["result"] is None:
                    self._start_calibration()  # poucos toques: tenta de novo
                    return
                self.rhythm_settings["audio_offset"] = calibration["result"]
                self.rhythm_settings["input_offset"] = 0
                self._save_rhythm_settings()
                self.audio.play("success")
                self.state = "settings"
            return
        if key in (pygame.K_SPACE, pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k):
            calibration["taps"].append(self.clock_fn())
            calibration["flash"] = self.clock_fn()

    # ------------------------------------------------------------------
    # Ritmo do dia: lembretes para ir dormir
    # ------------------------------------------------------------------
    def _venues_left_today(self):
        clothes = sum(1 for item in self.inventory if ITEMS[item]["kind"] == "roupa")
        return [venue_id for venue_id, venue in VENUES.items()
                if clothes >= venue["required"] and self.clock_minutes < venue["hours"][1] * 60]

    # ------------------------------------------------------------------
    # Efeitos do show (multiplicador, combo)
    # ------------------------------------------------------------------
    def _collect_rhythm_events(self):
        styles = {2: ((124, 217, 169), "2X"), 3: ((120, 200, 255), "3X"), 4: ((255, 140, 220), "4X")}
        for kind, value in self.rhythm.events:
            if kind == "multiplier":
                color, label = styles.get(value, ((247, 203, 107), f"{value}X"))
                self._add_popup(label, color, big=True, sub_text="MULTIPLICADOR!")
                self._burst(color, 46)
                self.audio.play("success", 0.7)
            elif kind == "combo":
                self._add_popup(f"COMBO {value}!", (247, 203, 107), big=False)
                self._burst((247, 203, 107), 26)
            elif kind == "break":
                self._add_popup("COMBO PERDIDO", (255, 120, 100), big=False, duration=0.8)
        self.rhythm.events.clear()

    def _add_popup(self, text, color, big=False, sub_text=None, duration=1.2):
        self.popups.append({"text": text, "color": color, "big": big, "sub": sub_text,
                            "age": 0.0, "duration": duration})
        self.popups = self.popups[-3:]

    def _burst(self, color, count, center=(640, 330)):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(160, 520)
            self.sparks.append([center[0], center[1], math.cos(angle) * speed, math.sin(angle) * speed,
                                0.0, random.uniform(0.5, 0.9), color, random.randint(2, 5)])

    def _update_effects(self, dt):
        for popup in self.popups:
            popup["age"] += dt
        self.popups = [p for p in self.popups if p["age"] < p["duration"]]
        for spark in self.sparks:
            spark[0] += spark[2] * dt
            spark[1] += spark[3] * dt
            spark[3] += 520 * dt  # gravidade
            spark[4] += dt
        self.sparks = [s for s in self.sparks if s[4] < s[5]]

    def _should_go_home(self):
        return self.clock_minutes >= LATE_HOUR or not self._venues_left_today()

    def _update_reminders(self):
        def once(key, condition, message, kind):
            if condition and key not in self.reminders:
                self.reminders.add(key)
                self._set_toast(message, seconds=5.5, kind=kind)
                self.audio.play("ui_confirm", 0.6)

        once("nothing_left", not self._venues_left_today() and self.clock_minutes < LATE_HOUR,
             "Nenhum palco disponível pelo resto do dia. Vá dormir em casa para começar o próximo (siga a seta).",
             "info")
        once("late", self.clock_minutes >= LATE_HOUR,
             "22:00: assaltantes começam a rondar a cidade! Vá para casa (siga a seta) ou ande de Fusca.", "warn")
        once("very_late", self.clock_minutes >= 25 * 60,
             "01:00: se não dormir até as 03:00, amanhã você estará cansado e mais lento!", "bad")

    # ------------------------------------------------------------------
    # Salvamento
    # ------------------------------------------------------------------
    def _autosave(self):
        if self.state in ("end_name", "menu", "ranking"):
            return
        savegame.save_game({
            "difficulty": self.difficulty, "money": self.money, "debt": self.debt,
            "daily_payment": self.daily_payment, "day": self.day, "phase": self.phase,
            "score": self.score, "songs_performed": self.songs_performed,
            "missed_payments": self.missed_payments, "inventory": list(self.inventory),
            "player_position": list(self.player.rect.center),
            "clock_minutes": round(self.clock_minutes), "tired_day": self.tired_day,
            "rested_day": self.rested_day, "shows_today": dict(self.shows_today),
            "car": [round(self.car.position.x), round(self.car.position.y), round(self.car.heading)] if self.car else None,
        })

    def _load_saved_game(self):
        data = savegame.load_game()
        if data is None or data["difficulty"] not in DIFFICULTIES:
            self.has_save = False
            self.menu_options = self._build_menu()
            self.menu_index = 0
            self._set_toast("Não foi possível carregar o jogo salvo.")
            return
        self.difficulty = data["difficulty"]
        self.difficulty_index = self.difficulty_names.index(self.difficulty)
        self._start_new_game(announce=False)
        self.money, self.debt, self.daily_payment = data["money"], data["debt"], data["daily_payment"]
        self.day, self.phase, self.score = data["day"], data["phase"], data["score"]
        self.songs_performed, self.missed_payments = data["songs_performed"], data["missed_payments"]
        self.inventory = [item for item in data["inventory"] if item in ITEMS]
        self.clock_minutes = float(data.get("clock_minutes", 8 * 60))
        self.tired_day = bool(data.get("tired_day", False))
        self.rested_day = bool(data.get("rested_day", False))
        shows = data.get("shows_today", {})
        self.shows_today = ({k: int(v) for k, v in shows.items() if k in VENUES and isinstance(v, int)}
                            if isinstance(shows, dict) else {})
        if "fusca" in self.inventory:
            car = data.get("car")
            if isinstance(car, list) and len(car) == 3 and all(isinstance(v, (int, float)) for v in car):
                self.car = Car((car[0], car[1]), heading=car[2])
            else:
                self._spawn_car_near_shop()
        self.player.reset_position(tuple(int(v) for v in data["player_position"]))
        self.camera.update(self.player)
        self._refresh_shop_stock()
        self._set_toast(f"Jogo carregado: dia {self.day}.")
        logging.info("Jogo carregado do save (dia %s)", self.day)

    def on_quit(self):
        """Chamado ao fechar a janela: guarda a partida em andamento."""
        if self.state in ("playing", "shop", "sleep_confirm", "chase", "rhythm_result", "paused"):
            self._autosave()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    # ------------------------------------------------------------------
    # Fim de jogo e ranking
    # ------------------------------------------------------------------
    def _finish_game(self, result, reason):
        self.victory_bonus = 0
        if result == "vitória":
            # Escapar mais cedo e com mais dinheiro rende mais pontos.
            self.victory_bonus = 300 + max(0, 30 - self.day) * 20 + max(0, self.money) // 10
            self.score += self.victory_bonus
        savegame.delete_save()
        self.has_save = False
        self.audio.play("win" if result == "vitória" else "lose")
        self.end_result = result
        self.end_reason = reason
        self.result_saved = False
        self.player_name = ""
        self.state = "end_name"
        logging.info("Fim de jogo: %s - %s; score=%s", result, reason, self.score)

    def _after_name_entry(self):
        self.rank_return_state = "menu"
        self.ranking_filter = None
        self.menu_options = self._build_menu()
        self.menu_index = 0
        self.state = "ranking"

    def _handle_name_entry(self, event):
        if event.key == pygame.K_RETURN:
            saved = self.ranking.save(
                self.player_name or "Jogador",
                self.score,
                self.day,
                self.difficulty,
                self.end_result or "fim",
            )
            if saved:
                logging.info("Pontuação salva no ranking")
            else:
                self._set_toast("Não foi possível salvar no ranking (erro no banco de dados).", seconds=4)
            self.result_saved = saved
            self._after_name_entry()
        elif event.key == pygame.K_ESCAPE:
            self._after_name_entry()
        elif event.key == pygame.K_BACKSPACE:
            self.player_name = self.player_name[:-1]
        elif event.unicode and event.unicode.isprintable() and not event.unicode.isspace():
            if len(self.player_name) < 16:
                self.player_name += event.unicode

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------
    def draw(self, screen):
        self.buttons = []
        screen.fill((38, 43, 45))
        self.camera.update(self.player)
        self.tiled_map.draw(screen, self.camera)
        self._draw_characters(screen)
        self._draw_daylight(screen)
        self._draw_zones(screen)
        self._draw_stun_bar(screen)

        if self.state == "menu":
            self._draw_menu(screen)
        elif self.state == "help":
            self._draw_help(screen)
        elif self.state == "settings":
            self._draw_settings(screen)
        elif self.state == "calibrate":
            self._draw_calibration(screen)
        elif self.state == "playing":
            self._draw_hud(screen)
            self._draw_home_arrow(screen)
            self._draw_interaction_prompt(screen)
        elif self.state == "shop":
            self._draw_hud(screen)
            self._draw_shop(screen)
        elif self.state == "sleep_confirm":
            self._draw_hud(screen)
            self._draw_sleep_confirm(screen)
        elif self.state == "rhythm":
            self._draw_rhythm(screen)
        elif self.state == "venue_info":
            self._draw_venue_info(screen)
        elif self.state == "rhythm_result":
            self._draw_rhythm_result(screen)
        elif self.state == "chase":
            self._draw_hud(screen)
            self._draw_chase(screen)
        elif self.state == "paused":
            self._draw_hud(screen)
            self._draw_paused(screen)
        elif self.state == "ranking":
            self._draw_ranking(screen)
        elif self.state == "end_name":
            self._draw_end_name(screen)

        if self.toast_timer > 0 and self.state in ("menu", "settings", "playing", "shop", "sleep_confirm", "chase"):
            self._draw_toast(screen)

    def _daylight(self):
        """Cor e opacidade do "céu" sobre o mapa conforme a hora (pôr do sol, noite, amanhecer)."""
        hour = self.clock_minutes / 60
        if hour < 3:
            hour += 24
        keys = ((3, (12, 18, 60, 130)), (5, (12, 18, 60, 125)), (6.5, (255, 160, 110, 40)), (8, (255, 200, 150, 0)),
                (16.5, (255, 170, 90, 0)), (18, (255, 140, 60, 50)), (19.5, (70, 50, 110, 95)),
                (21, (16, 24, 70, 120)), (27, (12, 18, 60, 130)), (32, (12, 18, 60, 130)))
        for (h0, c0), (h1, c1) in zip(keys, keys[1:]):
            if h0 <= hour <= h1:
                k = (hour - h0) / (h1 - h0)
                return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
        return (10, 15, 45, 140)

    def _draw_daylight(self, screen):
        color = self._daylight()
        if color[3] <= 0:
            return
        if getattr(self, "_tint", None) is None or self._tint.get_size() != screen.get_size():
            self._tint = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        self._tint.fill(color)
        screen.blit(self._tint, (0, 0))

    def _draw_zones(self, screen):
        night = self._daylight()[3] > 80
        for zone in ZONES:
            x = round(zone["position"][0] - self.camera.x)
            y = round(zone["position"][1] - self.camera.y)
            if x < -160 or x > screen.get_width() + 160 or y < -70 or y > screen.get_height() + 70:
                continue
            status = self._venue_status(zone["id"]) if zone["id"] in VENUES else None
            dim = status is not None and not status[0]
            color = tuple(c // 2 + 40 for c in zone["color"]) if dim else zone["color"]
            if night and not dim:  # letreiro aceso à noite
                glow = pygame.Surface((90, 90), pygame.SRCALPHA)
                pygame.draw.circle(glow, color + (60,), (45, 45), 44)
                pygame.draw.circle(glow, color + (90,), (45, 45), 34)
                screen.blit(glow, (x - 45, y - 45))
            pygame.draw.circle(screen, (18, 23, 25), (x, y + 2), 25)
            pygame.draw.circle(screen, color, (x, y), 22)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), 22, 3)

            label = self.font_label.render(zone["name"], True, ui.INK)
            lines = [label]
            if status is not None:
                lines.append(self.font_tiny.render(status[1], True, status[2]))
            width = max(line.get_width() for line in lines) + 16
            height = sum(line.get_height() for line in lines) + 6
            box = pygame.Rect(0, 0, width, height)
            box.midtop = (x, y + 28)
            ui.panel(screen, box, fill=(14, 19, 24, 225), border=None, radius=7)
            top = box.y + 3
            for line in lines:
                screen.blit(line, line.get_rect(midtop=(x, top)))
                top += line.get_height()

    def _draw_player(self, screen, camera):
        pygame.draw.ellipse(screen, (24, 28, 30), self.camera.apply(pygame.Rect(
            self.player.hitbox.centerx - 12, self.player.hitbox.bottom - 5, 24, 9)))
        screen.blit(self.player.image, camera.apply(self.player.rect))

    def _draw_characters(self, screen):
        """Desenha jogador, moradores e agiota ordenados pela altura dos pés (profundidade)."""
        width, height = screen.get_width(), screen.get_height()
        drawables = [] if self.driving else [(self.player.hitbox.bottom, self._draw_player)]
        if self.car is not None:
            drawables.append((self.car.sort_y, self.car.draw))
        for walker in self.npcs + self.hunters + self.muggers:
            x = walker.position.x - self.camera.x
            y = walker.position.y - self.camera.y
            if -60 <= x <= width + 60 and -80 <= y <= height + 80:
                drawables.append((walker.sort_y, walker.draw))
        for _, draw in sorted(drawables, key=lambda item: item[0]):
            draw(screen, self.camera)

    def _draw_edge_arrow(self, screen, world_pos, color, label=None, on_screen=True):
        """Seta na borda da tela apontando para algo fora de vista (agiota, casa...)."""
        width, height = screen.get_width(), screen.get_height()
        x, y = world_pos[0] - self.camera.x, world_pos[1] - self.camera.y
        if 0 <= x <= width and 0 <= y <= height:
            if not on_screen:
                return
            # Está na tela: seta pulando em cima do alvo.
            bounce = abs(math.sin(self.clock_fn() * 5)) * 8
            ui.arrow(screen, (x, y - 34 - bounce), pygame.Vector2(0, 1), color, size=22)
            return
        center = pygame.Vector2(width / 2, height / 2)
        direction = pygame.Vector2(x, y) - center
        if direction.length_squared() == 0:
            return
        direction.normalize_ip()
        top_margin = 150  # não cobrir o HUD
        reach_x = (width / 2 - 40) / max(abs(direction.x), 1e-3)
        reach_y = ((height / 2 - top_margin) if direction.y < 0 else (height / 2 - 90)) / max(abs(direction.y), 1e-3)
        tip = center + direction * min(reach_x, reach_y)
        ui.arrow(screen, tip, direction, color, size=28)
        if label:
            ui.text(screen, label, self.font_label, ui.INK, shadow=True, center=tuple(tip - direction * 44))

    def _draw_agiota_arrow(self, screen):
        for hunter in self.hunters:
            label = "CAPANGA" if isinstance(hunter, Capanga) else "AGIOTA"
            self._draw_edge_arrow(screen, hunter.position, (230, 70, 60), label, on_screen=False)

    def _draw_home_arrow(self, screen):
        if self._should_go_home():
            home = next(zone for zone in ZONES if zone["id"] == "home")
            self._draw_edge_arrow(screen, home["position"], (120, 170, 255), "CASA")

    def _draw_stun_bar(self, screen):
        player = self.player
        if player.stunned_timer <= 0 or not player.stun_duration:
            return
        x = player.rect.centerx - self.camera.x
        top = player.rect.top - self.camera.y
        ratio = player.stunned_timer / player.stun_duration
        bar = pygame.Rect(0, 0, 58, 9)
        bar.midbottom = (x, top - 6)
        ui.panel(screen, bar.inflate(6, 6), fill=(14, 19, 24, 230), border=None, radius=6)
        ui.bar(screen, bar, ratio, (255, 200, 90), back=(60, 50, 40))
        ui.text(screen, f"ATORDOADO {player.stunned_timer:0.1f}s", self.font_label, (255, 214, 120),
                shadow=True, midbottom=(x, bar.y - 4))
        spin = self.clock_fn() * 6
        for k in range(3):  # estrelinhas girando em volta da cabeça
            angle = spin + k * math.tau / 3
            star = (round(x + math.cos(angle) * 14), round(top + 8 + math.sin(angle) * 5))
            pygame.draw.circle(screen, (255, 230, 120), star, 3)

    def _draw_chase(self, screen):
        remaining = max(0.0, self.chase_timer)
        box = pygame.Rect(0, 0, 400, 66)
        box.midbottom = (screen.get_width() // 2, screen.get_height() - 110)
        ui.panel(screen, box, border=(196, 48, 43), width=2)
        title = "FUJA DO AGIOTA!" if len(self.hunters) <= 1 else f"FUJA! {len(self.hunters)} CAÇADORES"
        ui.text(screen, title, self.font_large, (255, 150, 140), midleft=(box.x + 18, box.y + 24))
        ui.text(screen, f"{remaining:0.1f}s", self.font_large, ui.INK, midright=(box.right - 18, box.y + 24))
        ratio = remaining / self.chase_window if self.chase_window else 0.0
        ui.bar(screen, (box.x + 18, box.bottom - 18, box.width - 36, 8), ratio, (230, 70, 60))
        self._draw_agiota_arrow(screen)

    def _period(self):
        minutes = self.clock_minutes
        if minutes < 6 * 60:
            return "Madrugada", (150, 160, 220)
        if minutes < 12 * 60:
            return "Manhã", (255, 214, 120)
        if minutes < 18 * 60:
            return "Tarde", ORANGE_TEXT
        if minutes < 24 * 60:
            return "Noite", (176, 150, 240)
        return "Madrugada", (150, 160, 220)

    def _draw_timeline(self, screen, rect):
        """Linha do dia (08h -> 03h) com períodos coloridos e marcador da hora atual."""
        rect = pygame.Rect(rect)
        span = DAY_END - DAY_START
        segments = ((8, 12, (230, 196, 110)), (12, 18, (226, 150, 80)), (18, 24, (130, 110, 205)), (24, 27, (70, 82, 150)))
        pygame.draw.rect(screen, (40, 50, 58), rect, border_radius=4)
        for start, end, color in segments:
            x0 = rect.x + round(rect.width * (start * 60 - DAY_START) / span)
            x1 = rect.x + round(rect.width * (end * 60 - DAY_START) / span)
            pygame.draw.rect(screen, color, (x0, rect.y, max(1, x1 - x0 - 1), rect.height))
        ratio = max(0.0, min(1.0, (self.clock_minutes - DAY_START) / span))
        mx = rect.x + round(rect.width * ratio)
        pygame.draw.rect(screen, (8, 10, 12, 0), (mx - 2, rect.y - 4, 4, rect.height + 8))
        pygame.draw.rect(screen, ui.INK, (mx - 1, rect.y - 4, 3, rect.height + 8), border_radius=1)
        pygame.draw.polygon(screen, ui.INK, [(mx - 5, rect.y - 8), (mx + 6, rect.y - 8), (mx + 1, rect.y - 3)])
        for hour, label in ((8, "08h"), (12, "12h"), (18, "18h"), (24, "00h"), (27, "03h")):
            x = rect.x + round(rect.width * (hour * 60 - DAY_START) / span)
            ui.text(screen, label, self.font_label, ui.MUTED, midtop=(min(max(x, rect.x + 10), rect.right - 10), rect.bottom + 1))

    def _draw_hud(self, screen):
        hour = (self.clock_minutes / 60) % 24
        period, period_color = self._period()

        # Relógio e dia
        card = ui.panel(screen, (12, 10, 330, 104))
        ui.sky_icon(screen, (card.x + 34, card.y + 38), hour)
        ui.text(screen, f"DIA {self.day}", self.font_label, ui.MUTED, topleft=(card.x + 64, card.y + 10))
        ui.text(screen, self._clock_text(), self.font_big_number, ui.INK, topleft=(card.x + 62, card.y + 20))
        ui.text(screen, period, self.font, period_color, midleft=(card.x + 166, card.y + 40))
        self._draw_timeline(screen, (card.x + 18, card.y + 72, card.width - 36, 8))

        # Dinheiro e dívida
        card = ui.panel(screen, (352, 10, 300, 104))
        ui.text(screen, "DINHEIRO", self.font_label, ui.MUTED, topleft=(card.x + 18, card.y + 10))
        ui.coin(screen, (card.x + 30, card.y + 44))
        ui.text(screen, ui.money(self.money), self.font_big_number, ui.GREEN, midleft=(card.x + 50, card.y + 44))
        ui.text(screen, "DÍVIDA COM O AGIOTA", self.font_label, ui.MUTED, topleft=(card.x + 18, card.y + 68))
        ui.text(screen, ui.money(self.debt), self.font, (255, 160, 140), topright=(card.right - 18, card.y + 66))

        # Próxima cobrança
        next_payment = math.ceil(self.daily_payment * 1.5)
        covered = self.money >= next_payment
        card = ui.panel(screen, (662, 10, 290, 104), border=ui.GREEN if covered else (200, 90, 80))
        ui.text(screen, f"COBRANÇA DO DIA {self.day + 1}", self.font_label, ui.MUTED, topleft=(card.x + 18, card.y + 10))
        ui.text(screen, ui.money(next_payment), self.font_big_number, ORANGE_TEXT, midleft=(card.x + 18, card.y + 44))
        status = "Garantida" if covered else f"Faltam {ui.money(next_payment - self.money)}"
        ui.text(screen, status, self.font_small, ui.GREEN if covered else ui.RED, midright=(card.right - 18, card.y + 44))
        ui.bar(screen, (card.x + 18, card.y + 72, card.width - 36, 8), self.money / max(1, next_payment),
               ui.GREEN if covered else (230, 110, 90))
        ui.text(screen, "paga ao dormir ou às 03:00", self.font_label, ui.MUTED, midtop=(card.centerx, card.y + 83))

        # Progresso
        card = ui.panel(screen, (962, 10, 306, 104))
        ui.text(screen, f"FASE {self.phase}", self.font_label, ui.GOLD, topleft=(card.x + 18, card.y + 10))
        ui.text(screen, self.difficulty.upper(), self.font_label, ui.MUTED, topright=(card.right - 18, card.y + 10))
        ui.text(screen, "Pontos", self.font_small, ui.MUTED, topleft=(card.x + 18, card.y + 28))
        ui.text(screen, f"{self.score:,}".replace(",", "."), self.font, ui.INK, topright=(card.right - 18, card.y + 26))
        clothes = sum(1 for item in self.inventory if ITEMS[item]["kind"] == "roupa")
        ui.text(screen, "Roupas", self.font_small, ui.MUTED, topleft=(card.x + 18, card.y + 52))
        for k in range(3):
            box = pygame.Rect(card.right - 18 - (3 - k) * 22, card.y + 56, 16, 16)
            pygame.draw.rect(screen, ui.GOLD if k < clothes else (50, 60, 68), box, border_radius=4)
        ui.text(screen, "Se faltar", self.font_small, ui.MUTED, topleft=(card.x + 18, card.y + 76))
        next_henchmen = HENCHMEN_PER_MISS * self.missed_payments
        threat = "agiota" if not next_henchmen else f"agiota + {next_henchmen} capangas"
        ui.text(screen, threat, self.font_small, (255, 140, 120) if next_henchmen else ui.INK,
                topright=(card.right - 18, card.y + 76))

        # Etiquetas de estado
        x = 12
        chips = []
        if self.tired_day and not self.driving:
            chips.append(("Cansado: 35% mais lento hoje", ORANGE_TEXT))
        elif self.rested_day and not self.driving:
            chips.append(("Descansado: +10% de velocidade", ui.GREEN))
        if self.driving and self.car is not None and self.car.on_grass:
            chips.append(("Grama: Fusca 25% mais lento", ORANGE_TEXT))
        elif self.driving:
            chips.append(("No Fusca: E para sair", ui.BLUE))
        if self.clock_minutes >= NIGHT_DANGER:
            chips.append(("Noite: assaltantes nas ruas", (255, 120, 140)))
        elif self._should_go_home() and self.state == "playing":
            chips.append(("Hora de ir para casa dormir", (120, 170, 255)))
        for label, color in chips:
            rect = ui.chip(screen, self.font_small, label, color, topleft=(x, 122))
            x = rect.right + 8

    def _draw_key_prompt(self, screen, title_text, detail, detail_color, border):
        title = self.font.render(title_text, True, ui.INK)
        sub_text = self.font_small.render(detail, True, detail_color) if detail else None
        width = 70 + title.get_width() + (sub_text.get_width() + 20 if sub_text else 0)
        box = pygame.Rect(0, 0, width, 48)
        box.midbottom = (screen.get_width() // 2, screen.get_height() - 24)
        ui.panel(screen, box, border=border, width=2, radius=14)
        key = pygame.Rect(box.x + 12, box.y + 10, 28, 28)
        pygame.draw.rect(screen, ui.INK, key, border_radius=6)
        ui.text(screen, "E", self.font, (20, 26, 30), center=key.center)
        screen.blit(title, title.get_rect(midleft=(key.right + 14, box.centery)))
        if sub_text:
            screen.blit(sub_text, sub_text.get_rect(midleft=(key.right + 34 + title.get_width(), box.centery + 1)))

    def _draw_interaction_prompt(self, screen):
        if self.driving:
            speed = round(self.car.speed / 340 * 60) if self.car else 0
            self._draw_key_prompt(screen, "Sair do Fusca", f"{speed} km/h" + ("  (grama: -25%)" if self.car.on_grass else ""),
                                  ORANGE_TEXT if self.car.on_grass else ui.MUTED, Car.BODY_COLOR)
            return
        zone = self._nearby_zone()
        if self._car_nearby() and (not zone or self.car.position.distance_to(self.player.hitbox.center)
                                   < pygame.Vector2(self.player.rect.center).distance_to(zone["position"])):
            self._draw_key_prompt(screen, "Entrar no Fusca", "rápido na rua, 25% mais lento na grama", ui.MUTED,
                                  Car.BODY_COLOR)
            return
        if not zone:
            return
        label = zone["name"].title()
        detail, detail_color = "", ui.MUTED
        venue = VENUES.get(zone["id"])
        if venue:
            have = sum(1 for item in self.inventory if ITEMS[item]["kind"] == "roupa")
            if have < venue["required"]:
                detail, detail_color = f"precisa de {venue['required']} peça(s) de roupa", ui.RED
            else:
                _, detail, detail_color = self._venue_status(zone["id"])
        elif zone["id"] == "home":
            detail = "dormir e encerrar o dia"
        elif zone["id"] == "shop":
            detail = "roupas, Fusca e passagem"
        elif zone["id"] == "station":
            detail = "embarcar (precisa de passagem)"
        title = self.font.render(label, True, ui.INK)
        sub_text = self.font_small.render(detail, True, detail_color) if detail else None
        width = 70 + title.get_width() + (sub_text.get_width() + 20 if sub_text else 0)
        box = pygame.Rect(0, 0, width, 48)
        box.midbottom = (screen.get_width() // 2, screen.get_height() - 24)
        ui.panel(screen, box, border=zone["color"], width=2, radius=14)
        key = pygame.Rect(box.x + 12, box.y + 10, 28, 28)
        pygame.draw.rect(screen, ui.INK, key, border_radius=6)
        ui.text(screen, "E", self.font, (20, 26, 30), center=key.center)
        screen.blit(title, title.get_rect(midleft=(key.right + 14, box.centery)))
        if sub_text:
            screen.blit(sub_text, sub_text.get_rect(midleft=(key.right + 34 + title.get_width(), box.centery + 1)))

    def _draw_menu(self, screen):
        self._draw_overlay(screen, alpha=188)
        box = ui.panel(screen, (330, 60, 620, 600), fill=(16, 22, 28, 240), border=(96, 114, 126), radius=18, width=2)
        ui.text(screen, "SONG TO MY BILLS", self.font_title, ui.GOLD, center=(640, 122))
        ui.text(screen, "Uma cidade, três palcos e uma dívida crescendo.", self.font_small, ui.MUTED, center=(640, 164))

        top, step = 214, 48
        for index, option in enumerate(self.menu_options):
            selected = index == self.menu_index
            row = pygame.Rect(box.x + 60, top + index * step - 20, box.width - 120, 40)
            if selected:
                ui.panel(screen, row, fill=(34, 46, 56, 255), border=ui.GOLD, radius=10)
            label = f"Dificuldade:  < {self.difficulty} >" if option == "Dificuldade" else option
            ui.text(screen, label, self.font_large, ui.GOLD if selected else ui.INK, center=row.center)
            self.buttons.append((row, lambda i=index: self._click_menu_option(i)))

        ui.text(screen, DIFFICULTY_TEXT[self.difficulty], self.font_small, ui.MUTED, center=(640, 572))
        ui.text(screen, "Setas: escolher   |   Laterais ou 1-2-3: dificuldade   |   ENTER: confirmar",
                self.font_small, (150, 165, 174), center=(640, 608))

    def _draw_settings(self, screen):
        self._draw_overlay(screen, alpha=200)
        box = ui.panel(screen, (300, 90, 680, 540), radius=16)
        ui.text(screen, "AJUSTES", self.font_title, ui.GOLD, center=(640, 140))
        s = self.rhythm_settings
        rows = {
            "volume": ("Volume da música", f"{s['volume']}%"),
            "sfx_volume": ("Volume dos efeitos e ambiente", f"{s['sfx_volume']}%"),
            "approach": ("Velocidade das notas", f"{3.2 - s['approach']:.1f}x"),
            "audio_offset": ("Sincronia do áudio", f"{s['audio_offset']:+d} ms"),
            "calibrate": ("Calibrar sincronia automaticamente", ""),
            "back": ("Voltar", ""),
        }
        for index, key in enumerate(SETTINGS_ROWS):
            label, value = rows[key]
            y = 210 + index * 56
            selected = index == self.settings_index
            row = pygame.Rect(box.x + 30, y - 22, box.width - 60, 44)
            if selected:
                ui.panel(screen, row, fill=(34, 46, 56, 255), border=ui.GOLD, radius=10)
            ui.text(screen, label, self.font, ui.GOLD if selected else ui.INK, midleft=(row.x + 18, row.centery))
            if value:
                ui.text(screen, f"<  {value}  >" if selected else value, self.font, ui.INK, midright=(row.right - 18, row.centery))
            self.buttons.append((row, lambda i=index: self._click_setting(i)))
        hint = "Se as notas parecem adiantadas ou atrasadas em relação à música, use a calibração."
        ui.text(screen, hint, self.font_small, ui.MUTED, center=(640, 556))
        ui.text(screen, "Setas: escolher e ajustar   |   ENTER confirmar   |   ESC voltar", self.font_small, ui.MUTED, center=(640, 590))

    def _click_setting(self, index):
        self.settings_index = index
        self._handle_settings(pygame.K_RETURN)

    def _draw_calibration(self, screen):
        self._draw_overlay(screen, alpha=235)
        ui.panel(screen, (290, 110, 700, 500), radius=16)
        ui.text(screen, "CALIBRAR SINCRONIA", self.font_title, ui.GOLD, center=(640, 165))
        calibration = self.calibration
        if not calibration["done"]:
            lines = ("Você vai ouvir batidas regulares.",
                     "Aperte ESPAÇO (ou D F J K) junto com cada batida que ouvir.",
                     "Feche os olhos se quiser: o que importa é o som.")
            for index, line in enumerate(lines):
                ui.text(screen, line, self.font, ui.INK if index == 1 else ui.MUTED, center=(640, 225 + index * 34))
            age = self.clock_fn() - calibration["flash"]
            radius = 46 + (max(0.0, 0.25 - age) * 60 if age < 0.25 else 0)
            pygame.draw.circle(screen, (34, 46, 56), (640, 410), round(radius))
            pygame.draw.circle(screen, ui.GOLD if age < 0.15 else (90, 108, 118), (640, 410), round(radius), 4)
            ui.text(screen, f"{calibration['next']}/{CALIBRATION_BEATS}", self.font_large, ui.INK, center=(640, 410))
            ui.text(screen, "ESC cancela", self.font_small, ui.MUTED, center=(640, 575))
        else:
            result = calibration["result"]
            if result is None:
                ui.text(screen, "Não deu para medir: poucos toques no ritmo.", self.font, ui.RED, center=(640, 300))
                ui.text(screen, "ENTER tenta de novo   |   ESC volta", self.font_small, ui.MUTED, center=(640, 520))
            else:
                ui.text(screen, "Atraso medido", self.font, ui.MUTED, center=(640, 280))
                ui.text(screen, f"{result:+d} ms", self.font_title, ui.GREEN, center=(640, 335))
                ui.text(screen, "As notas e a avaliação dos toques vão compensar esse atraso.", self.font_small,
                        ui.MUTED, center=(640, 400))
                ui.text(screen, "ENTER salvar   |   ESC descartar", self.font, ui.INK, center=(640, 520))

    def _draw_help(self, screen):
        self._draw_overlay(screen, alpha=205)
        ui.panel(screen, (130, 40, 1020, 640), fill=(16, 22, 28, 245), border=(96, 114, 126), radius=18, width=2)
        ui.text(screen, "COMO JOGAR", self.font_title, ui.GOLD, center=(640, 92))
        for index, (title, line) in enumerate(HELP_LINES):
            y = 150 + index * 42
            ui.text(screen, title, self.font, ui.GOLD, midleft=(180, y))
            ui.text(screen, line, self.font_small, ui.INK, midleft=(330, y))
        ui.text(screen, "ENTER ou ESC para voltar", self.font_small, ui.MUTED, center=(640, 648))

    def _draw_shop(self, screen):
        self._draw_overlay(screen, alpha=150)
        box = ui.panel(screen, (300, 150, 680, 500), fill=(16, 22, 28, 245), border=(96, 114, 126), radius=18, width=2)
        ui.text(screen, "LOJA", self.font_title, ui.GOLD, center=(640, 198))
        ui.text(screen, "As roupas à venda mudam a cada dia. Roupas liberam palcos melhores.",
                self.font_small, ui.MUTED, center=(640, 238))
        if not self.shop_stock:
            ui.text(screen, "Sem estoque hoje. Volte amanhã!", self.font, ui.INK, center=(640, 380))
        kinds = {"roupa": "Roupa", "veiculo": "Veículo", "passagem": "Passagem"}
        for index, item_key in enumerate(self.shop_stock):
            item = ITEMS[item_key]
            selected = index == self.shop_index
            row = pygame.Rect(box.x + 40, 276 + index * 52, box.width - 80, 44)
            ui.panel(screen, row, fill=(34, 46, 56, 255) if selected else (24, 32, 40, 255),
                     border=ui.GOLD if selected else None, radius=10)
            ui.text(screen, item["name"], self.font, ui.GOLD if selected else ui.INK, midleft=(row.x + 18, row.centery))
            ui.text(screen, kinds[item["kind"]], self.font_label, ui.MUTED, midleft=(row.x + 250, row.centery))
            owned = item_key in self.inventory
            affordable = self.money >= item["price"]
            price_color = ui.MUTED if owned else (ui.GREEN if affordable else ui.RED)
            ui.text(screen, "Já possui" if owned else ui.money(item["price"]), self.font, price_color,
                    midright=(row.right - 18, row.centery))
            self.buttons.append((row, lambda i=index: self._click_shop_item(i)))
        ui.coin(screen, (box.x + 52, box.bottom - 40))
        ui.text(screen, ui.money(self.money), self.font, ui.GREEN, midleft=(box.x + 70, box.bottom - 40))
        ui.text(screen, "ENTER: comprar   |   ESC: sair", self.font_small, ui.MUTED, midright=(box.right - 40, box.bottom - 40))

    def _click_shop_item(self, index):
        self.shop_index = index
        self._buy_selected_item()

    def _draw_sleep_confirm(self, screen):
        self._draw_overlay(screen, alpha=165)
        box = ui.panel(screen, (320, 190, 640, 360), fill=(16, 22, 28, 245), border=(96, 114, 126), radius=18, width=2)
        ui.text(screen, "DORMIR EM CASA", self.font_title, ui.GOLD, center=(640, 240))
        next_payment = math.ceil(self.daily_payment * 1.5)
        early = self.clock_minutes < REST_BEFORE
        lines = [
            ("O dia acaba e você acorda às 08:00 do dia " + str(self.day + 1) + ".", ui.INK),
            (f"Ao acordar, o agiota cobra {ui.money(next_payment)}." + (" Você tem o dinheiro." if self.money >= next_payment
             else f" Faltam {ui.money(next_payment - self.money)}!"), ui.GREEN if self.money >= next_payment else ui.RED),
            ("Antes da meia-noite: amanhã você acorda descansado (+10% de velocidade)." if early
             else "Já passou da meia-noite: sem bônus de descanso, mas evita o cansaço.", ui.GREEN if early else ORANGE_TEXT),
        ]
        for index, (line, color) in enumerate(lines):
            ui.text(screen, line, self.font_small, color, center=(640, 300 + index * 34))
        confirm = pygame.Rect(box.x + 60, box.bottom - 90, 240, 48)
        cancel = pygame.Rect(box.right - 300, box.bottom - 90, 240, 48)
        self._draw_button(screen, confirm, "ENTER  Dormir", self._confirm_sleep, ui.GREEN)
        self._draw_button(screen, cancel, "ESC  Ainda não", self._cancel_sleep, ui.RED)

    def _confirm_sleep(self):
        self.audio.play("ui_confirm")
        self._advance_day(slept=True)

    def _cancel_sleep(self):
        self.audio.play("ui_back")
        self.state = "playing"

    def _draw_button(self, screen, rect, label, action, color):
        hovered = rect.collidepoint(self.mouse_pos)
        pygame.draw.rect(screen, (34, 46, 54) if hovered else (24, 33, 40), rect, border_radius=10)
        pygame.draw.rect(screen, color, rect, 2, border_radius=10)
        self._text(screen, label, self.font, (245, 247, 248), center=rect.center)
        self.buttons.append((rect, action))

    def _draw_venue_info(self, screen):
        self._draw_overlay(screen, alpha=205)
        venue = VENUES[self.active_venue]
        info = self.venue_info
        self._panel(screen, pygame.Rect(300, 110, 680, 500))
        self._text(screen, venue["name"].upper(), self.font_title, (247, 203, 107), center=(640, 168))
        self._text(screen, venue["blurb"], self.font_small, (205, 217, 223), center=(640, 214))
        self._text(screen, venue["rule"], self.font_small, (160, 176, 185), center=(640, 242))

        available, status_text, status_color = self._venue_status(self.active_venue)
        opens, closes = venue["hours"]
        lines = [("Faixa", info["song"]), ("Nível", f"{info['level']}/5  ({self.difficulty})"),
                 ("Horário", f"{opens:02d}:00 às {closes % 24:02d}:00")]
        if info["ok"]:
            lines.insert(1, ("Duração", f"{info['duration']:.0f} s  |  {info['bpm']:.0f} BPM  |  {info['notes']} notas"))
        lines.append(("Cachê", f"até {ui.money(info['max_reward'])} (precisão) + bônus de até x3"))
        for index, (label, value) in enumerate(lines):
            y = 280 + index * 40
            self._text(screen, label, self.font, (247, 203, 107), (370, y))
            self._text(screen, value, self.font, (236, 240, 242), (510, y))
        if not info["ok"]:
            self._text(screen, "Música indisponível neste momento:", self.font_small, (255, 150, 120), center=(640, 488))
            self._text(screen, info["error"][:90], self.font_tiny, (255, 174, 139), center=(640, 510))
        else:
            ui.chip(screen, self.font_small, status_text, status_color, topleft=(370, 494))

        enter = pygame.Rect(340, 530, 280, 52)
        cancel = pygame.Rect(660, 530, 280, 52)
        self._draw_button(screen, enter, "ENTER  Entrar no palco", self._confirm_venue,
                          (124, 217, 169) if info["ok"] and available else (110, 110, 110))
        self._draw_button(screen, cancel, "ESC  Cancelar", self._cancel_venue, (255, 123, 105))

    def _draw_rhythm(self, screen):
        self._draw_overlay(screen, alpha=228)
        session = self.rhythm
        now = session.song_time()
        duration = session.map["duration"]
        self._text(screen, session.map["title"], self.font_large, (247, 203, 107), center=(640, 55))
        self._text(screen, VENUES[self.active_venue]["name"], self.font_small,
                   (200, 215, 220), center=(640, 91))
        stats = ui.panel(screen, (90, 200, 250, 190), radius=14)
        ui.text(screen, "PONTOS", self.font_label, ui.MUTED, topleft=(stats.x + 20, stats.y + 16))
        ui.text(screen, f"{session.score:,}".replace(",", "."), self.font_large, ui.INK, topleft=(stats.x + 20, stats.y + 30))
        ui.text(screen, "PRECISÃO", self.font_label, ui.MUTED, topleft=(stats.x + 20, stats.y + 74))
        ui.text(screen, f"{session.accuracy * 100:.1f}%", self.font_large, ui.INK, topleft=(stats.x + 20, stats.y + 88))
        ui.text(screen, "COMBO", self.font_label, ui.MUTED, topleft=(stats.x + 20, stats.y + 132))
        ui.text(screen, str(session.combo), self.font_large, ui.GOLD, topleft=(stats.x + 20, stats.y + 146))
        mult = session.multiplier
        mult_colors = {1: ui.MUTED, 2: (124, 217, 169), 3: (120, 200, 255), 4: (255, 140, 220)}
        pill = pygame.Rect(0, 0, 64, 34)
        pill.topright = (stats.right - 18, stats.y + 148)
        ui.panel(screen, pill, fill=(24, 32, 40, 255), border=mult_colors[mult], width=2, radius=10)
        ui.text(screen, f"x{mult}", self.font_large, mult_colors[mult], center=pill.center)
        steps = [25, 50, 100]
        upcoming = next((step for step in steps if session.combo < step), None)
        if upcoming:
            floor = max([0] + [step for step in steps if step <= session.combo])
            ui.bar(screen, (stats.x + 20, stats.bottom - 10, stats.width - 40, 4),
                   (session.combo - floor) / (upcoming - floor), mult_colors.get(mult + 1, ui.GOLD))
        judgment_colors = {"Perfect": (120, 230, 255), "Great": (124, 217, 169), "Good": (200, 230, 120),
                           "OK": (247, 203, 107), "Meh": (255, 170, 102), "Miss": (255, 110, 100)}
        if session.last_judgment and now - session.last_judgment_at < 0.7:
            age = now - session.last_judgment_at
            font = self.font_title if age < 0.08 else self.font_large
            ui.text(screen, session.last_judgment.upper(), font, judgment_colors[session.last_judgment],
                    shadow=True, center=(1040, 325))
        top, target = 130, self.rhythm_target_y
        colors = ((112, 203, 235), (250, 195, 104), (187, 151, 231), (124, 217, 169))
        # Faixa onde o toque ainda vale pontos (janela "Meh"); a parte central é a de acerto perfeito.
        speed_px = (target - top) / session.settings["approach"]
        band = pygame.Surface((400, max(2, round(speed_px * 0.44))), pygame.SRCALPHA)
        band.fill((255, 255, 255, 14))
        pygame.draw.rect(band, (255, 255, 255, 22), (0, band.get_height() // 2 - round(speed_px * 0.05), 400,
                                                     max(2, round(speed_px * 0.1))))
        for lane, x in enumerate(self.rhythm_lanes):
            track = pygame.Rect(x - 48, top, 96, 450)
            pygame.draw.rect(screen, (38, 50, 58) if lane in session.pressed else (25, 34, 41), track)
            pygame.draw.rect(screen, (66, 82, 91), track, 1)
            pygame.draw.circle(screen, colors[lane] if lane in session.pressed else (91, 109, 119),
                               (x, target), 32, 4)
            self._text(screen, "DFJK"[lane], self.font_large, (245, 247, 248), center=(x, 607))
        hit_age = now - session.last_judgment_at
        if session.last_judgment != "Miss" and 0 <= hit_age < 0.32:
            radius = 34 + int(hit_age * 55)
            pygame.draw.circle(screen, colors[session.last_lane],
                               (self.rhythm_lanes[session.last_lane], target), radius, 2)
        screen.blit(band, band.get_rect(center=(640, target)))
        speed = (target - top) / session.settings["approach"]
        clip = screen.get_clip()
        screen.set_clip(pygame.Rect(440, top, 400, target - top + 33))
        for note in session.map["notes"]:
            if note["head"] is not None and (not note["duration"] or note["tail"] is not None):
                continue
            x = self.rhythm_lanes[note["lane"]]
            y = target - (note["time"] - now) * speed
            if note["duration"]:
                end_y = target - (note["time"] + note["duration"] - now) * speed
                if note["tail"] is None and end_y < target + 35 and y > top - 35:
                    body = pygame.Rect(x - 12, int(end_y), 24, max(1, int(y - end_y)))
                    pygame.draw.rect(screen, colors[note["lane"]], body, border_radius=10)
            if note["head"] is None and top - 35 <= y <= target + 35:
                pygame.draw.circle(screen, colors[note["lane"]], (x, int(y)), 27)
                pygame.draw.circle(screen, (245, 248, 249), (x, int(y)), 27, 2)
        screen.set_clip(clip)
        if session.crowd_meter:
            self._draw_crowd_bar(screen, session.crowd)
        pygame.draw.rect(screen, (54, 66, 74), (340, 654, 600, 8), border_radius=4)
        pygame.draw.rect(screen, (247, 203, 107),
                         (340, 654, int(600 * min(1, max(0, now / duration))), 8), border_radius=4)
        self._text(screen, f"{max(0, now):.0f}/{duration:.0f} s  |  ESC abandona",
                   self.font_small, (190, 202, 210), center=(640, 689))
        self._draw_effects(screen)

    def _outlined(self, text, font, color, outline=(10, 12, 16), width=4):
        base = font.render(text, True, color)
        shade = font.render(text, True, outline)
        surface = pygame.Surface((base.get_width() + width * 2, base.get_height() + width * 2), pygame.SRCALPHA)
        for dx in (-width, 0, width):
            for dy in (-width, 0, width):
                if dx or dy:
                    surface.blit(shade, (width + dx, width + dy))
        surface.blit(base, (width, width))
        return surface

    def _draw_effects(self, screen):
        """Popups grandes ("2X", "COMBO 50!") e faíscas, com entrada em "pop" e saída em fade."""
        for x, y, _, _, age, life, color, size in self.sparks:
            radius = max(1, round(size * (1 - age / life)))
            pygame.draw.circle(screen, color, (round(x), round(y)), radius)
        scale_fn = getattr(pygame.transform, "smoothscale", pygame.transform.scale)
        for index, popup in enumerate(self.popups):
            age, duration = popup["age"], popup["duration"]
            if "surface" not in popup:
                popup["surface"] = self._outlined(popup["text"], self.font_huge if popup["big"] else self.font_combo,
                                                  popup["color"])
                if popup["sub"]:
                    popup["sub_surface"] = self._outlined(popup["sub"], self.font_large, ui.INK, width=2)
            pop = 1.0 + 0.7 * max(0.0, 1 - age / 0.14) + 0.04 * math.sin(age * 18) * (age < 0.6)
            alpha = 255 if age < duration - 0.35 else round(255 * max(0.0, (duration - age) / 0.35))
            base = popup["surface"]
            image = scale_fn(base, (max(1, round(base.get_width() * pop)), max(1, round(base.get_height() * pop))))
            image.set_alpha(alpha)
            center_y = (300 if popup["big"] else 420) - round(age * 24) - (len(self.popups) - 1 - index) * 8
            screen.blit(image, image.get_rect(center=(640, center_y)))
            if popup.get("sub_surface") is not None:
                sub_image = popup["sub_surface"]
                sub_image.set_alpha(alpha)
                screen.blit(sub_image, sub_image.get_rect(midtop=(640, center_y + image.get_height() // 2 - 6)))
            if popup["big"] and age < 0.45:  # brilho nas bordas da tela
                glow = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
                strength = round(120 * (1 - age / 0.45))
                for k in range(6):
                    pygame.draw.rect(glow, popup["color"] + (max(0, strength - k * 20),),
                                     glow.get_rect().inflate(-k * 8, -k * 8), 4)
                screen.blit(glow, (0, 0))

    def _draw_crowd_bar(self, screen, crowd):
        """Energia da plateia (fase 2): verde = animada, vermelho = prestes a vaiar."""
        bar = pygame.Rect(884, 130, 24, 450)
        ratio = max(0.0, min(1.0, crowd / 100.0))
        color = (124, 217, 169) if ratio > 0.5 else (247, 203, 107) if ratio > 0.25 else (239, 92, 76)
        pygame.draw.rect(screen, (25, 34, 41), bar, border_radius=8)
        fill = round(bar.height * ratio)
        pygame.draw.rect(screen, color, (bar.x, bar.bottom - fill, bar.width, fill), border_radius=8)
        pygame.draw.rect(screen, (66, 82, 91), bar, 2, border_radius=8)
        self._text(screen, "PLATEIA", self.font_tiny, (200, 215, 220), center=(bar.centerx, bar.y - 14))
        if ratio <= 0.25:
            self._text(screen, "CUIDADO!", self.font_small, (255, 150, 120), center=(bar.centerx + 70, bar.centery))

    def _draw_rhythm_result(self, screen):
        self._draw_overlay(screen, alpha=225)
        box = ui.panel(screen, (280, 70, 720, 590), fill=(16, 22, 28, 245), border=(96, 114, 126), radius=18, width=2)
        result = self.rhythm_result
        if result["failed"]:
            ui.text(screen, "A PLATEIA TE VAIOU!", self.font_title, ui.RED, center=(640, 122))
        else:
            ui.text(screen, "FIM DO SHOW", self.font_title, ui.GOLD, center=(640, 122))
        ui.text(screen, f"{result['venue']}  -  {result['song']}", self.font, ui.MUTED, center=(640, 166))
        ui.text(screen, f"{result['accuracy'] * 100:.1f}%", self.font_combo, ui.INK,
                center=(640, 222))
        ui.text(screen, "PRECISÃO", self.font_label, ui.MUTED, center=(640, 258))
        ui.text(screen, f"Pontos {result['score']:,}".replace(",", ".") + f"     Maior combo {result['combo']}",
                self.font, ui.INK, center=(640, 292))
        counts = result["counts"]
        colors = {"Perfect": (120, 230, 255), "Great": (124, 217, 169), "Good": (200, 230, 120),
                  "OK": (247, 203, 107), "Meh": (255, 170, 102), "Miss": (255, 110, 100)}
        x = 318
        for name, color in colors.items():
            cell = pygame.Rect(x, 318, 100, 52)
            ui.panel(screen, cell, fill=(24, 32, 40, 255), border=None, radius=10)
            ui.text(screen, name.upper(), self.font_label, color, center=(cell.centerx, cell.y + 15))
            ui.text(screen, str(counts[name]), self.font, ui.INK, center=(cell.centerx, cell.y + 36))
            x += 108
        bonus = result.get("bonus")
        if bonus:
            badge = pygame.Rect(0, 0, 440, 62)
            badge.center = (640, 418)
            ui.panel(screen, badge, fill=(40, 34, 18, 255), border=ui.GOLD, width=3, radius=16)
            ui.text(screen, f"{bonus[0].upper()}  x{bonus[1]:g} NO CACHÊ", self.font_large, ui.GOLD, center=badge.center)
        if result["failed"]:
            ui.text(screen, "A energia da plateia zerou: sem cachê.", self.font_large, ORANGE_TEXT, center=(640, 500))
        else:
            ui.text(screen, f"+ {ui.money(result['reward'])}", self.font_combo, ui.GREEN, center=(640, 500))
            notes = []
            if result.get("factor", 1) < 1:
                notes.append(f"local repetido hoje: cachê {round(result['factor'] * 100)}%")
            if not bonus:
                notes.append("dica: sequência de 90% da música dá x1,5; sem erros, x2; tudo Perfect, x3")
            for index, note in enumerate(notes):
                ui.text(screen, note, self.font_small, ui.MUTED, center=(640, 542 + index * 22))
        if result["lost_item"]:
            ui.text(screen, f"Apresentação ruim: perdeu {result['lost_item']}.", self.font_small, ORANGE_TEXT,
                    center=(640, 590))
        ui.text(screen, "ENTER continuar", self.font_small, ui.MUTED, center=(640, 630))

    def _draw_paused(self, screen):
        self._draw_overlay(screen, alpha=190)
        box = pygame.Rect(330, 200, 620, 300)
        self._panel(screen, box)
        self._text(screen, "PAUSADO", self.font_title, (247, 203, 107), center=(640, 275))
        self._text(screen, "ENTER/ESC continuar", self.font, (240, 244, 246), center=(640, 350))
        self._text(screen, "M salvar e voltar ao menu", self.font, (190, 202, 210), center=(640, 400))

    def _draw_end_name(self, screen):
        self._draw_overlay(screen, alpha=205)
        box = pygame.Rect(240, 130, 800, 460)
        self._panel(screen, box, border=(247, 203, 107))
        title = "VOCÊ ESCAPOU!" if self.end_result == "vitória" else "FIM DE JOGO"
        title_color = (121, 222, 157) if self.end_result == "vitória" else (255, 123, 105)
        self._text(screen, title, self.font_title, title_color, center=(640, 205))
        self._text(screen, self.end_reason, self.font, (235, 240, 242), center=(640, 270))
        summary = f"Pontuação: {self.score}   |   Dias: {self.day}   |   Dificuldade: {self.difficulty}"
        self._text(screen, summary, self.font, (247, 203, 107), center=(640, 325))
        if self.victory_bonus:
            self._text(screen, f"Bônus de vitória: +{self.victory_bonus}", self.font_small,
                       (124, 217, 169), center=(640, 355))
        self._text(screen, "Digite seu nome para o ranking:", self.font, (235, 240, 242), center=(640, 390))
        name = self.player_name or "Jogador"
        name_surface = self.font_large.render(name + "_", True, (255, 255, 255))
        name_rect = name_surface.get_rect(center=(640, 440))
        screen.blit(name_surface, name_rect)
        self._text(screen, "ENTER salvar resultado  |  ESC pular", self.font_small, (190, 202, 210), center=(640, 510))

    def _draw_ranking(self, screen):
        self._draw_overlay(screen, alpha=205)
        box = pygame.Rect(130, 45, 1020, 630)
        self._panel(screen, box)
        self._text(screen, "RANKING", self.font_title, (247, 203, 107), center=(640, 95))
        filter_name = self.ranking_filter or "Todas"
        self._text(screen, f"Dificuldade:  <  {filter_name}  >", self.font, (235, 240, 242), center=(640, 142))

        if self.result_saved and self.end_result:
            result_text = "Resultado salvo: " + ("vitória" if self.end_result == "vitória" else "derrota")
            self._text(screen, result_text, self.font_small, (210, 226, 230), center=(640, 172))

        rows = self.ranking.top(10, self.ranking_filter)
        columns = [(160, "#"), (205, "Nome"), (430, "Pontos"), (540, "Dias"), (620, "Dificuldade"),
                   (760, "Resultado"), (890, "Data")]
        for x, label in columns:
            self._text(screen, label, self.font_small, (185, 202, 210), (x, 200))

        if not rows:
            self._text(screen, "Ainda não há pontuações salvas.", self.font, (235, 240, 242), center=(640, 330))
        else:
            for index, row in enumerate(rows):
                name, score, days, difficulty, result, created = row
                y = 235 + index * 36
                color = (247, 203, 107) if index == 0 else (229, 235, 238)
                values = [str(index + 1), name[:16], str(score), str(days), difficulty,
                          result.title(), str(created)[:16]]
                for (x, _), value in zip(columns, values):
                    self._text(screen, value, self.font_small, color, (x, y))

        self._text(screen, "Setas laterais: filtrar por dificuldade   |   ENTER ou ESC: voltar", self.font_small,
                   (190, 202, 210), center=(640, 640))

    def _draw_toast(self, screen):
        colors = {"info": ui.BLUE, "good": ui.GREEN, "bad": ui.RED, "warn": ORANGE_TEXT}
        accent = colors.get(self.toast_kind, ui.BLUE)
        lines = ui.wrap(self.toast_text, self.font_small, 560)
        line_height = self.font_small.get_height()
        width = max(self.font_small.size(line)[0] for line in lines) + 52
        height = line_height * len(lines) + 20
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        ui.panel(surface, surface.get_rect(), fill=(14, 19, 24, 238), border=accent, radius=12)
        pygame.draw.rect(surface, accent, (0, 0, 8, height), border_top_left_radius=12, border_bottom_left_radius=12)
        pygame.draw.circle(surface, accent, (24, height // 2), 5)
        for index, line in enumerate(lines):
            ui.text(surface, line, self.font_small, ui.INK, topleft=(38, 10 + index * line_height))
        elapsed = self.toast_total - self.toast_timer
        fade = min(1.0, elapsed / 0.18, self.toast_timer / 0.4)
        surface.set_alpha(round(255 * max(0.0, fade)))
        slide = round((1 - min(1.0, elapsed / 0.18)) * -12)
        top = 160 if self.state in ("playing", "chase", "shop", "sleep_confirm") else 24
        screen.blit(surface, surface.get_rect(midtop=(screen.get_width() // 2, top + slide)))

    def _draw_overlay(self, screen, alpha=190):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((8, 12, 15, alpha))
        screen.blit(overlay, (0, 0))

    def _panel(self, screen, rect, border=(96, 114, 126)):
        ui.panel(screen, rect, fill=(16, 22, 28, 245), border=border, radius=16, width=2)

    @staticmethod
    def _text(screen, text, font, color, topleft=None, center=None):
        if center is not None:
            return ui.text(screen, text, font, color, center=center)
        return ui.text(screen, text, font, color, topleft=topleft or (0, 0))

    def _clock_text(self):
        total_minutes = int(self.clock_minutes) % (24 * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def _set_toast(self, message, seconds=3.5, kind="info"):
        self.toast_text = message
        self.toast_timer = seconds
        self.toast_total = seconds
        self.toast_kind = kind
