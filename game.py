import logging
import math
import random
from pathlib import Path

import pygame

from camera import Camera
from npc import NPC, Agiota
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
    "chapeu": {"name": "Chapéu", "price": 120, "kind": "roupa"},
    "sapatos": {"name": "Sapatos sociais", "price": 160, "kind": "roupa"},
    "calca": {"name": "Calça social", "price": 220, "kind": "roupa"},
    "blazer": {"name": "Blazer", "price": 350, "kind": "roupa"},
    "fusca": {"name": "Fusca usado", "price": 1800, "kind": "veiculo"},
    "passagem": {"name": "Passagem de trem", "price": 2500, "kind": "passagem"},
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
        "agiota_speed": 150, "chase_window": 26.0,
    },
    "Normal": {
        "level": 1, "multiplier": 1.0,
        "player_speed_mult": 1.0, "npc_count": 9,
        "agiota_speed": 185, "chase_window": 20.0,
    },
    "Difícil": {
        "level": 2, "multiplier": 1.25,
        "player_speed_mult": 0.97, "npc_count": 13,
        "agiota_speed": 215, "chase_window": 15.0,
    },
}
MAX_MISSED_PAYMENTS = 3  # cobranças perdidas toleradas antes da derrota definitiva
VENUES = {
    "bar": {"name": "Barzinho", "reward": 350, "level": 0, "required": 0},
    "fair": {"name": "Feira musical", "reward": 650, "level": 1, "required": 1},
    "concert": {"name": "Casa de shows", "reward": 1000, "level": 2, "required": 3},
}


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

        pygame.font.init()
        self.font_title = pygame.font.Font(None, 66)
        self.font_large = pygame.font.Font(None, 42)
        self.font = pygame.font.Font(None, 30)
        self.font_small = pygame.font.Font(None, 22)
        self.font_tiny = pygame.font.Font(None, 18)

        self.state = "menu"
        self.menu_options = ["Jogar", "Ranking", "Sair"]
        self.menu_index = 0
        self.difficulty_names = list(DIFFICULTIES.keys())
        self.difficulty_index = 1
        self.difficulty = "Normal"
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
        self.rhythm_setting_index = 0
        self.rhythm_result = None
        self.rhythm_target_y = 515
        self.rhythm_lanes = [490, 590, 690, 790]
        self.collector_timer = 0.0
        self.collector_reaction_delay = 0.0

        # NPCs que caminham pela cidade e o agiota que persegue o jogador
        # quando uma cobrança não é paga.
        self.npcs = []
        self.agiota = None
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
        if event.type != pygame.KEYDOWN:
            return

        if self.state == "menu":
            self._handle_menu(event.key)
        elif self.state == "difficulty":
            self._handle_difficulty(event.key)
        elif self.state == "playing":
            self._handle_playing(event.key)
        elif self.state == "shop":
            self._handle_shop(event.key)
        elif self.state == "sleep_confirm":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._advance_day(slept=True)
            elif event.key in (pygame.K_ESCAPE, pygame.K_e):
                self.state = "playing"
        elif self.state == "rhythm_setup":
            self._handle_rhythm_setup(event.key)
        elif self.state == "rhythm_result":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self._leave_rhythm_result()
        elif self.state == "collector":
            self._handle_collector_key(event.key)
        elif self.state == "paused":
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_p):
                self.state = "playing"
            elif event.key == pygame.K_m:
                self.state = "menu"
        elif self.state == "ranking":
            if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_m):
                self.state = self.rank_return_state
        elif self.state == "end_name":
            self._handle_name_entry(event)

    def update(self, dt):
        if self.toast_timer > 0:
            self.toast_timer = max(0, self.toast_timer - dt)

        # O tempo avança enquanto o jogador está no mundo ou em uma atividade.
        if self.state in ("playing", "shop", "rhythm", "collector", "chase"):
            self.clock_minutes += dt * 6
            # Se o relógio chegar às 03:00 durante uma música/QTE/perseguição,
            # deixa a atividade terminar e só então inicia o próximo dia.
            if self.clock_minutes >= 27 * 60 and self.state not in ("rhythm", "collector", "chase"):
                self._advance_day(slept=False, forced=True)

        if self.state == "playing":
            self._update_npcs(dt)
            on_grass = self.tiled_map.is_grass_at(self.player.rect.center)
            self.player.has_car = "fusca" in self.inventory
            self.player.tired = self.tired_day
            obstacles = self.tiled_map.solid_rects + self._npc_obstacles()
            self.player.update(
                dt,
                obstacles,
                self.tiled_map.width,
                self.tiled_map.height,
                on_grass=on_grass,
            )
            self.camera.update(self.player)

        elif self.state == "rhythm":
            self._update_rhythm(dt)

        elif self.state == "collector":
            self.collector_timer -= dt
            if self.collector_timer <= 0:
                self._resolve_collector(success=False)

        elif self.state == "chase":
            self._update_chase(dt)

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------
    def _handle_menu(self, key):
        if key in (pygame.K_UP, pygame.K_w):
            self.menu_index = (self.menu_index - 1) % len(self.menu_options)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.menu_index = (self.menu_index + 1) % len(self.menu_options)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            choice = self.menu_options[self.menu_index]
            if choice == "Jogar":
                self.state = "difficulty"
            elif choice == "Ranking":
                self.end_result = None
                self.result_saved = False
                self.rank_return_state = "menu"
                self.state = "ranking"
            else:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _handle_difficulty(self, key):
        if key in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
            self.difficulty_index = (self.difficulty_index - 1) % len(self.difficulty_names)
        elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_DOWN, pygame.K_s):
            self.difficulty_index = (self.difficulty_index + 1) % len(self.difficulty_names)
        elif key in (pygame.K_1, pygame.K_KP1):
            self.difficulty_index = 0
        elif key in (pygame.K_2, pygame.K_KP2):
            self.difficulty_index = 1
        elif key in (pygame.K_3, pygame.K_KP3):
            self.difficulty_index = 2
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.difficulty = self.difficulty_names[self.difficulty_index]
            self._start_new_game()
        elif key == pygame.K_ESCAPE:
            self.state = "menu"

    def _start_new_game(self):
        self.player = Player()
        self.player.reset_position((1280, 900))
        self.player.base_speed = round(300 * DIFFICULTIES[self.difficulty]["player_speed_mult"])
        self.inventory = []
        self.money = 500
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
        self.agiota = None
        self.chase_timer = 0.0
        self.chase_window = 0.0
        self._spawn_npcs()
        self._refresh_shop_stock()
        self.camera.update(self.player)

        # O jogo começa depois de pagar a primeira cobrança da manhã.
        self.money -= self.daily_payment
        self.debt = max(0, self.debt - self.daily_payment)
        logging.info("Nova partida. Dificuldade=%s; cobrança inicial paga=%s", self.difficulty, self.daily_payment)
        self.state = "playing"
        self._set_toast(f"Dia 1: cobrança de R$ {self.daily_payment} paga. Vá trabalhar!")

    # ------------------------------------------------------------------
    # NPCs e agiota
    # ------------------------------------------------------------------
    def _random_walkable_point(self, reference=None, min_distance=0):
        """Sorteia um ponto do mapa livre de obstáculos (rejection sampling).

        Se `reference`/`min_distance` forem informados, evita pontos perto
        demais de `reference` (usado para não gerar o agiota em cima do
        jogador).
        """
        probe = pygame.Rect(0, 0, 18, 14)
        for _ in range(50):
            x = random.uniform(40, self.tiled_map.width - 40)
            y = random.uniform(40, self.tiled_map.height - 40)
            if reference is not None and math.dist((x, y), reference) < min_distance:
                continue
            probe.center = (round(x), round(y))
            if not any(probe.colliderect(wall) for wall in self.tiled_map.solid_rects):
                return (x, y)
        return tuple(reference) if reference is not None else tuple(self.player.rect.center)

    def _spawn_npcs(self):
        """Cria os moradores que caminham pela cidade; a quantidade varia com a dificuldade."""
        palette = [
            (214, 197, 150), (176, 196, 214), (196, 176, 214),
            (176, 214, 186), (214, 176, 176), (214, 214, 150),
        ]
        count = DIFFICULTIES[self.difficulty]["npc_count"]
        self.npcs = []
        for index in range(count):
            point = self._random_walkable_point()
            color = palette[index % len(palette)]
            self.npcs.append(NPC(point, speed=random.uniform(55, 85), color=color))

    def _update_npcs(self, dt):
        for npc in self.npcs:
            npc.update(dt, self.tiled_map.solid_rects, self.tiled_map.width, self.tiled_map.height)

    def _npc_obstacles(self):
        """Hitboxes dos NPCs, para somar aos prédios na checagem de colisão."""
        return [npc.hitbox for npc in self.npcs]

    def _start_chase(self):
        """Substitui a derrota instantânea: o agiota persegue o jogador pela cidade."""
        settings = DIFFICULTIES[self.difficulty]
        self.chase_window = settings["chase_window"]
        self.chase_timer = self.chase_window
        spawn = self._random_walkable_point(reference=self.player.rect.center, min_distance=260)
        self.agiota = Agiota(spawn, speed=settings["agiota_speed"])
        self.state = "chase"
        self._set_toast(
            f"Não deu pra pagar a cobrança de hoje! Fuja do agiota por {int(self.chase_window)}s.",
            seconds=4.5,
        )
        logging.info(
            "Perseguição do agiota iniciada no dia %s (cobrança perdida nº %s)",
            self.day, self.missed_payments,
        )

    def _update_chase(self, dt):
        self._update_npcs(dt)

        obstacles = self.tiled_map.solid_rects + self._npc_obstacles()
        on_grass = self.tiled_map.is_grass_at(self.player.rect.center)
        self.player.has_car = "fusca" in self.inventory
        self.player.tired = self.tired_day
        self.player.update(dt, obstacles, self.tiled_map.width, self.tiled_map.height, on_grass=on_grass)
        self.camera.update(self.player)

        self.agiota.update(dt, obstacles, self.tiled_map.width, self.tiled_map.height, self.player.rect.center)

        if self.player.hitbox.colliderect(self.agiota.hitbox):
            self._resolve_chase(caught=True)
            return

        self.chase_timer -= dt
        if self.chase_timer <= 0:
            self._resolve_chase(caught=False)

    def _resolve_chase(self, caught):
        if caught:
            lost_money = self.money // 2
            self.money -= lost_money
            lost_item = self._lose_random_item()
            self.player.stun(2.5)
            message = f"O agiota te alcançou: perdeu R$ {lost_money}."
            if lost_item:
                message += f" Também perdeu {ITEMS[lost_item]['name']}."
            message += " Você ficou atordoado por alguns segundos."
            self._set_toast(message, seconds=5)
            logging.info("Agiota alcançou o jogador no dia %s; perdeu R$ %s", self.day, lost_money)
        else:
            self._set_toast("Você escapou do agiota por hoje! Mas a dívida continua pendente.", seconds=4)
            logging.info("Jogador escapou do agiota no dia %s", self.day)

        self.agiota = None
        self.state = "playing"

    # ------------------------------------------------------------------
    # Mundo e interações
    # ------------------------------------------------------------------
    def _handle_playing(self, key):
        if key == pygame.K_ESCAPE or key == pygame.K_p:
            self.state = "paused"
        elif key in (pygame.K_e, pygame.K_RETURN):
            zone = self._nearby_zone()
            if zone:
                self._interact(zone)
            else:
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
            self.state = "shop"
        elif zone_id in VENUES:
            venue = VENUES[zone_id]
            clothing_count = sum(1 for item in self.inventory if ITEMS[item]["kind"] == "roupa")
            if clothing_count < venue["required"]:
                missing = venue["required"] - clothing_count
                self._set_toast(f"Precisa de {missing} peça(s) de roupa/acessório a mais para entrar.")
                return
            if zone_id in ("fair", "concert"):
                self.phase = 2
            self.active_venue = zone_id
            self.rhythm_setting_index = 0
            self.state = "rhythm_setup"
        elif zone_id == "home":
            self.state = "sleep_confirm"
        elif zone_id == "station":
            if "passagem" in self.inventory:
                self._finish_game("vitória", "Você embarcou no trem e escapou da cobrança!")
            else:
                self._set_toast("A estação exige uma passagem de trem. Compre na loja.")

    def _refresh_shop_stock(self):
        # As roupas disponíveis mudam diariamente; carro e passagem ficam à venda.
        start = (self.day - 1) % len(CLOTHING_KEYS)
        clothes = [CLOTHING_KEYS[(start + i) % len(CLOTHING_KEYS)] for i in range(3)]
        self.shop_stock = clothes + ["fusca", "passagem"]

    def _handle_shop(self, key):
        if key == pygame.K_ESCAPE:
            self.state = "playing"
        elif key in (pygame.K_UP, pygame.K_w):
            self.shop_index = (self.shop_index - 1) % len(self.shop_stock)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.shop_index = (self.shop_index + 1) % len(self.shop_stock)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._buy_selected_item()

    def _buy_selected_item(self):
        if not self.shop_stock:
            self._set_toast("A loja está sem estoque hoje.")
            return

        item_key = self.shop_stock[self.shop_index]
        item = ITEMS[item_key]

        if item_key in self.inventory:
            self._set_toast("Você já possui esse item.")
            return
        if self.money < item["price"]:
            self._set_toast(f"Dinheiro insuficiente. Custa R$ {item['price']}.")
            return

        self.money -= item["price"]
        self.inventory.append(item_key)
        self.shop_stock.pop(self.shop_index)
        if self.shop_stock:
            self.shop_index %= len(self.shop_stock)
        else:
            self.shop_index = 0

        logging.info("Item comprado: %s por R$ %s", item_key, item["price"])
        self._set_toast(f"Comprou {item['name']} por R$ {item['price']}.")

    def _advance_day(self, slept, forced=False):
        if self.state == "end_name":
            return

        self.day += 1
        self.debt = math.ceil(self.debt * 1.5)
        self.daily_payment = math.ceil(self.daily_payment * 1.5)
        self.clock_minutes = 180 if forced else 8 * 60
        self.tired_day = bool(forced and not slept)
        self.player.tired = self.tired_day

        if self.money < self.daily_payment:
            self.missed_payments += 1
            logging.warning(
                "Cobrança de R$ %s não paga no dia %s (cobrança perdida nº %s)",
                self.daily_payment, self.day, self.missed_payments,
            )
            if self.missed_payments > MAX_MISSED_PAYMENTS:
                self._finish_game(
                    "derrota",
                    f"O agiota perdeu a paciência: {self.missed_payments} cobranças seguidas "
                    f"sem pagamento, até o dia {self.day}.",
                )
                return
            self._start_chase()
            return

        self.money -= self.daily_payment
        self.debt = max(0, self.debt - self.daily_payment)
        self._refresh_shop_stock()
        logging.info(
            "Dia %s: cobrança de R$ %s paga; dinheiro=%s; dívida=%s",
            self.day,
            self.daily_payment,
            self.money,
            self.debt,
        )

        if self.day >= 30:
            self._finish_game("vitória", "Você sobreviveu por 30 dias e o agiota morreu de velhice!")
            return

        if forced:
            self._set_toast(
                f"São 03:00! Começou o dia {self.day}; você está cansado e anda mais devagar."
            )
        else:
            self._set_toast(f"Dia {self.day}. Cobrança paga: R$ {self.daily_payment}.")

        self.state = "playing"

    # ------------------------------------------------------------------
    # Minigame de ritmo
    # ------------------------------------------------------------------
    def _handle_rhythm_setup(self, key):
        names = ("approach", "volume", "audio_offset", "input_offset")
        if key in (pygame.K_UP, pygame.K_w):
            self.rhythm_setting_index = (self.rhythm_setting_index - 1) % len(names)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.rhythm_setting_index = (self.rhythm_setting_index + 1) % len(names)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT):
            name = names[self.rhythm_setting_index]
            direction = -1 if key == pygame.K_LEFT else 1
            step = 0.2 if name == "approach" else 10
            limits = {"approach": (1.0, 3.0), "volume": (0, 100),
                      "audio_offset": (-250, 250), "input_offset": (-250, 250)}
            low, high = limits[name]
            self.rhythm_settings[name] = max(low, min(high, round(self.rhythm_settings[name] + direction * step, 2)))
            try:
                save_settings(self.rhythm_settings)
            except OSError as error:
                logging.warning("Não foi possível salvar configurações de ritmo: %s", error)
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._start_rhythm(self.active_venue)
        elif key == pygame.K_ESCAPE:
            self.active_venue = None
            self.state = "playing"

    def _start_rhythm(self, venue_id):
        self.rhythm_result = None
        level = DIFFICULTIES[self.difficulty]["level"] + VENUES[venue_id]["level"]
        songs = sorted(Path("assets/music").glob("*.json"))
        try:
            if not songs:
                raise FileNotFoundError("Nenhum beatmap em assets/music")
            beatmap = load_beatmap(songs[self.songs_performed % len(songs)], level)
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(beatmap["audio"]))
            pygame.mixer.music.set_volume(self.rhythm_settings["volume"] / 100)
            self.rhythm = RhythmSession(beatmap, self.rhythm_settings.copy())
            pygame.mixer.music.play()
            self.rhythm.start()
        except (OSError, ValueError, KeyError, TypeError, pygame.error) as error:
            logging.error("Falha ao iniciar apresentação: %s", error)
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            self.rhythm = None
            self.active_venue = None
            self.state = "playing"
            self._set_toast("Não foi possível carregar a música ou o beatmap. Sem pagamento.")
            return
        self.state = "rhythm"
        logging.info("Começou apresentação em %s, nível %s", VENUES[venue_id]["name"], level)

    def _update_rhythm(self, dt):
        self.rhythm.update()
        if not pygame.mixer.music.get_busy() and self.rhythm.song_time() < self.rhythm.map["duration"] - 1.0:
            self._abandon_rhythm("Reprodução interrompida. Sem pagamento.")
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

    def _finish_rhythm(self):
        pygame.mixer.music.stop()
        venue = VENUES[self.active_venue]
        accuracy = self.rhythm.accuracy
        reward = reward_for(accuracy, venue["reward"], DIFFICULTIES[self.difficulty]["multiplier"])
        lost_item = self._lose_random_item() if accuracy < 0.65 else None
        self.money += reward
        self.score += self.rhythm.score // 10
        self.score += reward // 10
        self.songs_performed += 1
        self.rhythm_result = {"venue": venue["name"], "accuracy": accuracy,
                              "score": self.rhythm.score, "combo": self.rhythm.max_combo,
                              "counts": self.rhythm.counts.copy(), "reward": reward,
                              "lost_item": ITEMS[lost_item]["name"] if lost_item else None}
        logging.info(
            "Apresentação %s: precisão=%.2f%%; pontos=%s; pagamento=%s",
            venue["name"], accuracy * 100, self.rhythm.score, reward,
        )
        self.active_venue = None
        self.rhythm = None
        self.state = "rhythm_result"

    def _leave_rhythm_result(self):
        self.state = "playing"
        # O cobrador aparece em aproximadamente 30% das apresentações.
        if random.random() < 0.30:
            self.state = "collector"
            self.collector_timer = 1.6
            self.collector_reaction_delay = 0.30
            logging.info("Evento do cobrador iniciado")

    # ------------------------------------------------------------------
    # Evento do cobrador (QTE)
    # ------------------------------------------------------------------
    def _handle_collector_key(self, key):
        if key in (pygame.K_SPACE, pygame.K_RETURN) and self.collector_timer > self.collector_reaction_delay:
            self._resolve_collector(success=True)

    def _resolve_collector(self, success):
        if self.state != "collector":
            return

        if success:
            self.score += 75
            self._set_toast("Você reagiu a tempo e escapou do cobrador!", seconds=3.5)
            logging.info("Jogador escapou do cobrador")
        else:
            lost_money = self.money // 2
            self.money -= lost_money
            lost_item = self._lose_random_item()
            message = f"O cobrador te pegou: perdeu R$ {lost_money}."
            if lost_item:
                message += f" Também perdeu {ITEMS[lost_item]['name']}."
            self._set_toast(message, seconds=4.5)
            logging.info("Jogador foi pego pelo cobrador e perdeu R$ %s", lost_money)

        self.state = "playing"

    def _lose_random_item(self):
        if not self.inventory:
            return None
        item_key = random.choice(self.inventory)
        self.inventory.remove(item_key)
        logging.info("Item perdido: %s", item_key)
        return item_key

    # ------------------------------------------------------------------
    # Fim de jogo e ranking
    # ------------------------------------------------------------------
    def _finish_game(self, result, reason):
        self.end_result = result
        self.end_reason = reason
        self.result_saved = False
        self.player_name = ""
        self.state = "end_name"
        logging.info("Fim de jogo: %s - %s; score=%s", result, reason, self.score)

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
            self.rank_return_state = "menu"
            self.state = "ranking"
        elif event.key == pygame.K_ESCAPE:
            self.rank_return_state = "menu"
            self.state = "ranking"
        elif event.key == pygame.K_BACKSPACE:
            self.player_name = self.player_name[:-1]
        elif event.unicode and event.unicode.isprintable() and not event.unicode.isspace():
            if len(self.player_name) < 16:
                self.player_name += event.unicode

    # ------------------------------------------------------------------
    # Renderização
    # ------------------------------------------------------------------
    def draw(self, screen):
        screen.fill((38, 43, 45))
        self.camera.update(self.player)
        self.tiled_map.draw(screen, self.camera)
        self._draw_zones(screen)
        self._draw_npcs(screen)
        screen.blit(self.player.image, self.camera.apply(self.player.rect))
        if self.agiota is not None:
            self.agiota.draw(screen, self.camera)

        if self.state == "menu":
            self._draw_menu(screen)
        elif self.state == "difficulty":
            self._draw_difficulty(screen)
        elif self.state == "playing":
            self._draw_hud(screen)
            self._draw_interaction_prompt(screen)
        elif self.state == "shop":
            self._draw_hud(screen)
            self._draw_shop(screen)
        elif self.state == "sleep_confirm":
            self._draw_hud(screen)
            self._draw_sleep_confirm(screen)
        elif self.state == "rhythm":
            self._draw_rhythm(screen)
        elif self.state == "rhythm_setup":
            self._draw_rhythm_setup(screen)
        elif self.state == "rhythm_result":
            self._draw_rhythm_result(screen)
        elif self.state == "collector":
            self._draw_hud(screen)
            self._draw_collector(screen)
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

        if self.toast_timer > 0 and self.state in ("playing", "shop", "sleep_confirm", "chase"):
            self._draw_toast(screen)

    def _draw_zones(self, screen):
        for zone in ZONES:
            x = round(zone["position"][0] - self.camera.x)
            y = round(zone["position"][1] - self.camera.y)
            if x < -160 or x > screen.get_width() + 160 or y < -70 or y > screen.get_height() + 70:
                continue

            pygame.draw.circle(screen, (18, 23, 25), (x, y), 26)
            pygame.draw.circle(screen, zone["color"], (x, y), 22)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), 22, 3)
            label = self.font_tiny.render(zone["name"], True, (255, 255, 255))
            label_rect = label.get_rect(center=(x, y + 39))
            bg = label_rect.inflate(12, 6)
            pygame.draw.rect(screen, (19, 24, 28), bg, border_radius=5)
            screen.blit(label, label_rect)

    def _draw_npcs(self, screen):
        for npc in self.npcs:
            x = npc.position.x - self.camera.x
            y = npc.position.y - self.camera.y
            if -40 <= x <= screen.get_width() + 40 and -40 <= y <= screen.get_height() + 40:
                npc.draw(screen, self.camera)

    def _draw_chase(self, screen):
        # Posicionado bem acima do toast (que some sozinho após alguns
        # segundos) para não sobrepor o aviso inicial da perseguição.
        remaining = max(0.0, self.chase_timer)
        text = self.font.render(f"FUJA DO AGIOTA!  {remaining:0.1f}s", True, (255, 150, 140))
        rect = text.get_rect(center=(screen.get_width() // 2, screen.get_height() - 160))
        panel = rect.inflate(32, 18)
        pygame.draw.rect(screen, (20, 25, 29), panel, border_radius=10)
        pygame.draw.rect(screen, (196, 48, 43), panel, 2, border_radius=10)
        screen.blit(text, rect)

        bar_width = 300
        ratio = max(0.0, min(1.0, remaining / self.chase_window)) if self.chase_window else 0.0
        bar_rect = pygame.Rect(0, 0, bar_width, 10)
        bar_rect.center = (screen.get_width() // 2, screen.get_height() - 188)
        pygame.draw.rect(screen, (40, 40, 40), bar_rect, border_radius=5)
        fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, round(bar_width * ratio), 10)
        pygame.draw.rect(screen, (196, 48, 43), fill_rect, border_radius=5)

    def _draw_hud(self, screen):
        panel = pygame.Surface((screen.get_width(), 74), pygame.SRCALPHA)
        panel.fill((13, 18, 22, 218))
        screen.blit(panel, (0, 0))

        clock_text = self._clock_text()
        self._text(screen, f"DIA {self.day}  |  {clock_text}", self.font, (255, 255, 255), (18, 10))
        self._text(screen, f"Dinheiro: R$ {self.money}    Dívida: R$ {self.debt}", self.font, (255, 224, 143), (18, 40))

        clothes = sum(1 for item in self.inventory if ITEMS[item]["kind"] == "roupa")
        right_text = f"Fase {self.phase}   |   Roupa: {clothes}/3   |   Pontos: {self.score}   |   {self.difficulty}"
        rendered = self.font_small.render(right_text, True, (230, 235, 238))
        screen.blit(rendered, (screen.get_width() - rendered.get_width() - 18, 15))

        if self.tired_day:
            tired = self.font_small.render("CANSADO: velocidade reduzida", True, (255, 150, 120))
            screen.blit(tired, (screen.get_width() - tired.get_width() - 18, 44))
        elif self.missed_payments > 0:
            warning = self.font_small.render(
                f"Cobranças perdidas: {self.missed_payments}/{MAX_MISSED_PAYMENTS}",
                True, (255, 150, 120),
            )
            screen.blit(warning, (screen.get_width() - warning.get_width() - 18, 44))

    def _draw_interaction_prompt(self, screen):
        zone = self._nearby_zone()
        if not zone:
            return
        text = self.font.render(f"E  -  Interagir: {zone['name'].title()}", True, (255, 255, 255))
        rect = text.get_rect(center=(screen.get_width() // 2, screen.get_height() - 50))
        panel = rect.inflate(32, 18)
        pygame.draw.rect(screen, (20, 25, 29), panel, border_radius=10)
        pygame.draw.rect(screen, zone["color"], panel, 2, border_radius=10)
        screen.blit(text, rect)

    def _draw_menu(self, screen):
        self._draw_overlay(screen, alpha=188)
        box = pygame.Rect(260, 85, 760, 550)
        self._panel(screen, box)
        self._text(screen, "SONG TO MY BILLS", self.font_title, (247, 203, 107), center=(640, 160))
        self._text(screen, "Uma cidade, três palcos e uma dívida crescendo.", self.font, (230, 235, 238), center=(640, 214))

        for index, option in enumerate(self.menu_options):
            selected = index == self.menu_index
            color = (247, 203, 107) if selected else (224, 230, 234)
            prefix = ">  " if selected else "   "
            self._text(screen, prefix + option, self.font_large, color, center=(640, 330 + index * 62))

        self._text(screen, "WASD/setas: mover   |   E: interagir   |   ESC: pausar", self.font_small, (190, 202, 210), center=(640, 560))
        self._text(screen, "Protótipo jogável - arte e marcadores ainda provisórios", self.font_small, (165, 180, 188), center=(640, 600))

    def _draw_difficulty(self, screen):
        self._draw_overlay(screen, alpha=190)
        box = pygame.Rect(260, 100, 760, 520)
        self._panel(screen, box)
        self._text(screen, "ESCOLHA A DIFICULDADE", self.font_title, (247, 203, 107), center=(640, 175))

        descriptions = {
            "Fácil": "Menos notas e mais tempo para acertar.",
            "Normal": "Desafio equilibrado.",
            "Difícil": "Mais notas e sequência mais rápida.",
        }
        for index, name in enumerate(self.difficulty_names):
            selected = index == self.difficulty_index
            color = (247, 203, 107) if selected else (225, 230, 234)
            self._text(screen, f"{index + 1}. {name}", self.font_large, color, center=(640, 295 + index * 65))
            self._text(screen, descriptions[name], self.font_small, (185, 197, 205), center=(640, 325 + index * 65))

        self._text(screen, "ENTER para começar  |  ESC para voltar", self.font, (255, 255, 255), center=(640, 550))

    def _draw_shop(self, screen):
        box = pygame.Rect(260, 90, 760, 550)
        self._panel(screen, box)
        self._text(screen, "LOJA DE ROUPAS E ITENS", self.font_title, (247, 203, 107), center=(640, 145))
        self._text(screen, f"Seu dinheiro: R$ {self.money}   |   O estoque muda a cada dia", self.font_small, (220, 229, 233), center=(640, 185))

        if not self.shop_stock:
            self._text(screen, "Sem estoque disponível.", self.font, (255, 255, 255), center=(640, 300))
        else:
            for index, item_key in enumerate(self.shop_stock):
                item = ITEMS[item_key]
                selected = index == self.shop_index
                color = (247, 203, 107) if selected else (228, 234, 237)
                prefix = "> " if selected else "  "
                owned = " (já possui)" if item_key in self.inventory else ""
                line = f"{prefix}{item['name']} - R$ {item['price']}{owned}"
                self._text(screen, line, self.font, color, topleft=(360, 235 + index * 48))

        self._text(screen, "ENTER comprar  |  ↑/↓ escolher  |  ESC sair", self.font_small, (190, 202, 210), center=(640, 590))

    def _draw_sleep_confirm(self, screen):
        self._draw_overlay(screen, alpha=165)
        box = pygame.Rect(280, 210, 720, 300)
        self._panel(screen, box)
        self._text(screen, "DESCANSAR EM CASA", self.font_title, (247, 203, 107), center=(640, 270))
        self._text(screen, "Dormir encerra o dia e adianta o relógio para 08:00.", self.font, (235, 239, 241), center=(640, 335))
        self._text(screen, "A cobrança aumenta 50% a cada dia.", self.font, (255, 174, 139), center=(640, 375))
        self._text(screen, "ENTER confirmar  |  ESC cancelar", self.font, (255, 255, 255), center=(640, 445))

    def _draw_rhythm_setup(self, screen):
        self._draw_overlay(screen, alpha=220)
        self._panel(screen, pygame.Rect(300, 120, 680, 490))
        venue = VENUES[self.active_venue]
        level = DIFFICULTIES[self.difficulty]["level"] + venue["level"] + 1
        self._text(screen, f"{venue['name'].upper()}  |  NÍVEL {level}/5", self.font_large,
                   (247, 203, 107), center=(640, 175))
        self._text(screen, "AJUSTES MUSICAIS", self.font, (236, 240, 242), center=(640, 225))
        s = self.rhythm_settings
        rows = (f"Velocidade visual: {s['approach']:.1f} s",
                f"Volume: {s['volume']}%",
                f"Offset de áudio: {s['audio_offset']:+d} ms",
                f"Offset de entrada: {s['input_offset']:+d} ms")
        for index, row in enumerate(rows):
            color = (247, 203, 107) if index == self.rhythm_setting_index else (225, 232, 236)
            self._text(screen, (">  " if index == self.rhythm_setting_index else "   ") + row,
                       self.font, color, topleft=(380, 280 + index * 50))
        self._text(screen, "↑/↓ selecionar   ←/→ ajustar", self.font_small,
                   (190, 202, 210), center=(640, 515))
        self._text(screen, "ENTER tocar   |   ESC cancelar", self.font_small,
                   (190, 202, 210), center=(640, 550))

    def _draw_rhythm(self, screen):
        self._draw_overlay(screen, alpha=228)
        session = self.rhythm
        now = session.song_time()
        duration = session.map["duration"]
        self._text(screen, session.map["title"], self.font_large, (247, 203, 107), center=(640, 55))
        self._text(screen, VENUES[self.active_venue]["name"], self.font_small,
                   (200, 215, 220), center=(640, 91))
        self._text(screen, f"Pontos  {session.score}", self.font, (240, 244, 246), topleft=(80, 245))
        self._text(screen, f"Precisão  {session.accuracy * 100:.2f}%", self.font,
                   (240, 244, 246), topleft=(80, 285))
        self._text(screen, f"Combo  {session.combo}", self.font_large,
                   (247, 203, 107), topleft=(80, 345))
        if session.last_judgment and now - session.last_judgment_at < 0.7:
            self._text(screen, session.last_judgment.upper(), self.font_large,
                       (255, 224, 143), center=(1010, 325))
        top, target = 130, self.rhythm_target_y
        colors = ((112, 203, 235), (250, 195, 104), (187, 151, 231), (124, 217, 169))
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
        pygame.draw.rect(screen, (54, 66, 74), (340, 654, 600, 8), border_radius=4)
        pygame.draw.rect(screen, (247, 203, 107),
                         (340, 654, int(600 * min(1, max(0, now / duration))), 8), border_radius=4)
        self._text(screen, f"{max(0, now):.0f}/{duration:.0f} s  |  ESC abandona",
                   self.font_small, (190, 202, 210), center=(640, 689))

    def _draw_rhythm_result(self, screen):
        self._draw_overlay(screen, alpha=225)
        self._panel(screen, pygame.Rect(280, 90, 720, 555))
        result = self.rhythm_result
        self._text(screen, "RESULTADO DA APRESENTAÇÃO", self.font_large,
                   (247, 203, 107), center=(640, 150))
        self._text(screen, result["venue"], self.font, (230, 237, 240), center=(640, 198))
        self._text(screen, f"Precisão  {result['accuracy'] * 100:.2f}%", self.font_large,
                   (240, 244, 246), center=(640, 265))
        self._text(screen, f"Pontos  {result['score']}    |    Maior combo  {result['combo']}",
                   self.font, (240, 244, 246), center=(640, 320))
        counts = result["counts"]
        self._text(screen, "Perfect  {Perfect}   Great  {Great}   Good  {Good}".format(**counts),
                   self.font_small, (200, 215, 220), center=(640, 382))
        self._text(screen, "OK  {OK}   Meh  {Meh}   Miss  {Miss}".format(**counts),
                   self.font_small, (200, 215, 220), center=(640, 416))
        self._text(screen, f"Recebeu R$ {result['reward']}", self.font_large,
                   (124, 217, 169), center=(640, 485))
        if result["lost_item"]:
            self._text(screen, f"Apresentação ruim: perdeu {result['lost_item']}.",
                       self.font_small, (255, 174, 139), center=(640, 530))
        self._text(screen, "ENTER continuar", self.font_small,
                   (190, 202, 210), center=(640, 594))

    def _draw_collector(self, screen):
        self._draw_overlay(screen, alpha=212)
        box = pygame.Rect(250, 190, 780, 340)
        self._panel(screen, box, border=(215, 78, 65))
        self._text(screen, "O COBRADOR TE VIU!", self.font_title, (255, 107, 91), center=(640, 260))
        self._text(screen, "Pressione ESPAÇO agora para tentar escapar.", self.font, (248, 241, 237), center=(640, 330))
        self._text(screen, "Se falhar, perde metade do dinheiro e um item aleatório.", self.font_small, (240, 185, 177), center=(640, 375))
        bar = pygame.Rect(390, 425, 500, 24)
        pygame.draw.rect(screen, (65, 35, 36), bar, border_radius=10)
        fill_width = int(bar.width * max(0, self.collector_timer / 1.6))
        pygame.draw.rect(screen, (239, 92, 76), (bar.x, bar.y, fill_width, bar.height), border_radius=10)

    def _draw_paused(self, screen):
        self._draw_overlay(screen, alpha=190)
        box = pygame.Rect(330, 200, 620, 300)
        self._panel(screen, box)
        self._text(screen, "PAUSADO", self.font_title, (247, 203, 107), center=(640, 275))
        self._text(screen, "ENTER/ESC continuar", self.font, (240, 244, 246), center=(640, 350))
        self._text(screen, "M voltar ao menu", self.font, (190, 202, 210), center=(640, 400))

    def _draw_end_name(self, screen):
        self._draw_overlay(screen, alpha=205)
        box = pygame.Rect(240, 130, 800, 460)
        self._panel(screen, box, border=(247, 203, 107))
        title = "VOCÊ ESCAPOU!" if self.end_result == "vitória" else "FIM DE JOGO"
        title_color = (121, 222, 157) if self.end_result == "vitória" else (255, 123, 105)
        self._text(screen, title, self.font_title, title_color, center=(640, 205))
        self._text(screen, self.end_reason, self.font, (235, 240, 242), center=(640, 270))
        self._text(screen, f"Pontuação: {self.score}   |   Dias: {self.day}   |   Dificuldade: {self.difficulty}", self.font, (247, 203, 107), center=(640, 325))
        self._text(screen, "Digite seu nome para o ranking:", self.font, (235, 240, 242), center=(640, 390))
        name = self.player_name or "Jogador"
        name_surface = self.font_large.render(name + "_", True, (255, 255, 255))
        name_rect = name_surface.get_rect(center=(640, 440))
        screen.blit(name_surface, name_rect)
        self._text(screen, "ENTER salvar resultado  |  ESC pular", self.font_small, (190, 202, 210), center=(640, 510))

    def _draw_ranking(self, screen):
        self._draw_overlay(screen, alpha=205)
        box = pygame.Rect(170, 55, 940, 610)
        self._panel(screen, box)
        self._text(screen, "RANKING", self.font_title, (247, 203, 107), center=(640, 105))

        if self.result_saved and self.end_result:
            result_text = "Resultado salvo: " + ("vitória" if self.end_result == "vitória" else "derrota")
            self._text(screen, result_text, self.font_small, (210, 226, 230), center=(640, 145))

        rows = self.ranking.top(10)
        columns = [(220, "#"), (285, "Nome"), (570, "Pontos"), (690, "Dias"), (775, "Nível"), (900, "Resultado")]
        for x, label in columns:
            self._text(screen, label, self.font_small, (185, 202, 210), (x, 185))

        if not rows:
            self._text(screen, "Ainda não há pontuações salvas.", self.font, (235, 240, 242), center=(640, 320))
        else:
            for index, row in enumerate(rows):
                name, score, days, difficulty, result, created = row
                y = 225 + index * 34
                color = (247, 203, 107) if index == 0 else (229, 235, 238)
                values = [str(index + 1), name[:18], str(score), str(days), difficulty, result.title()]
                for (x, _), value in zip(columns, values):
                    self._text(screen, value, self.font_small, color, (x, y))

        self._text(screen, "ENTER ou ESC para voltar ao menu", self.font, (235, 240, 242), center=(640, 610))

    def _draw_toast(self, screen):
        max_width = 1000
        text = self.font_small.render(self.toast_text, True, (255, 255, 255))
        if text.get_width() > max_width:
            text = self.font_tiny.render(self.toast_text, True, (255, 255, 255))
        rect = text.get_rect(center=(screen.get_width() // 2, screen.get_height() - 105))
        panel = rect.inflate(30, 20)
        pygame.draw.rect(screen, (18, 24, 28), panel, border_radius=9)
        pygame.draw.rect(screen, (247, 203, 107), panel, 2, border_radius=9)
        screen.blit(text, rect)

    def _draw_overlay(self, screen, alpha=190):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((8, 12, 15, alpha))
        screen.blit(overlay, (0, 0))

    def _panel(self, screen, rect, border=(113, 132, 143)):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((19, 27, 33, 245))
        screen.blit(panel, rect.topleft)
        pygame.draw.rect(screen, border, rect, 2, border_radius=14)

    @staticmethod
    def _text(screen, text, font, color, topleft=None, center=None):
        image = font.render(str(text), True, color)
        rect = image.get_rect()
        if center is not None:
            rect.center = center
        elif topleft is not None:
            rect.topleft = topleft
        screen.blit(image, rect)

    def _clock_text(self):
        total_minutes = int(self.clock_minutes) % (24 * 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def _set_toast(self, message, seconds=3.0):
        self.toast_text = message
        self.toast_timer = seconds
