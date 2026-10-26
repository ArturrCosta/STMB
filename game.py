import logging
import math
import random

import pygame

from camera import Camera
from player import Player
from ranking import Ranking
from tiled_map import TiledMap


# Coordenadas em pixels do mapa (80 x 60 tiles de 32 px).
# São marcadores provisórios e podem ser movidos quando os prédios finais forem feitos.
ZONES = [
    {"id": "shop", "name": "LOJA", "position": (640, 570), "color": (243, 190, 76)},
    {"id": "bar", "name": "BARZINHO", "position": (900, 710), "color": (229, 119, 76)},
    {"id": "fair", "name": "FEIRA MUSICAL", "position": (1280, 1030), "color": (99, 196, 131)},
    {"id": "concert", "name": "CASA DE SHOWS", "position": (1730, 710), "color": (181, 132, 230)},
    {"id": "home", "name": "SUA CASA", "position": (300, 1150), "color": (104, 185, 224)},
    {"id": "station", "name": "ESTAÇÃO", "position": (1280, 1540), "color": (226, 217, 119)},
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
DIFFICULTIES = {
    "Fácil": {"speed": 175, "spawn": 0.78, "notes": 7, "multiplier": 0.85},
    "Normal": {"speed": 215, "spawn": 0.68, "notes": 9, "multiplier": 1.0},
    "Difícil": {"speed": 255, "spawn": 0.58, "notes": 12, "multiplier": 1.25},
}
VENUES = {
    "bar": {"name": "Barzinho", "reward": 350, "level": 0, "required": 0},
    "fair": {"name": "Feira musical", "reward": 650, "level": 1, "required": 1},
    "concert": {"name": "Casa de shows", "reward": 1000, "level": 2, "required": 3},
}


class Game:
    """Controla os estados, regras, interface e progressão do jogo."""

    def __init__(self):
        self.tiled_map = TiledMap("assets/maps/cidade.tmx")
        self.player = Player()
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

        # Dados temporários do minigame de ritmo.
        self.active_venue = None
        self.rhythm_notes = []
        self.rhythm_spawned = 0
        self.rhythm_total = 0
        self.rhythm_hits = 0
        self.rhythm_perfects = 0
        self.rhythm_misses = 0
        self.rhythm_spawn_timer = 0.0
        self.rhythm_note_speed = 210
        self.rhythm_spawn_interval = 0.7
        self.rhythm_target_y = 515
        self.rhythm_hit_window = 42
        self.rhythm_lanes = [440, 640, 840]
        self.collector_timer = 0.0
        self.collector_reaction_delay = 0.0

        self._refresh_shop_stock()

    # ------------------------------------------------------------------
    # Eventos e atualização
    # ------------------------------------------------------------------
    def handle_event(self, event):
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
        elif self.state == "rhythm":
            self._handle_rhythm_key(event.key)
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
        if self.state in ("playing", "shop", "rhythm", "collector"):
            self.clock_minutes += dt * 6
            # Se o relógio chegar às 03:00 durante uma música/QTE, deixa a
            # atividade terminar e só então inicia o próximo dia.
            if self.clock_minutes >= 27 * 60 and self.state not in ("rhythm", "collector"):
                self._advance_day(slept=False, forced=True)

        if self.state == "playing":
            on_grass = self.tiled_map.is_grass_at(self.player.rect.center)
            self.player.has_car = "fusca" in self.inventory
            self.player.tired = self.tired_day
            self.player.update(
                dt,
                self.tiled_map.solid_rects,
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
        self._refresh_shop_stock()
        self.camera.update(self.player)

        # O jogo começa depois de pagar a primeira cobrança da manhã.
        self.money -= self.daily_payment
        self.debt = max(0, self.debt - self.daily_payment)
        logging.info("Nova partida. Dificuldade=%s; cobrança inicial paga=%s", self.difficulty, self.daily_payment)
        self.state = "playing"
        self._set_toast(f"Dia 1: cobrança de R$ {self.daily_payment} paga. Vá trabalhar!")

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
            self._start_rhythm(zone_id)
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
            self._finish_game(
                "derrota",
                f"Não conseguiu pagar a cobrança de R$ {self.daily_payment} no dia {self.day}.",
            )
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
    def _start_rhythm(self, venue_id):
        self.active_venue = venue_id
        venue = VENUES[venue_id]
        difficulty = DIFFICULTIES[self.difficulty]

        # A dificuldade do local soma-se à dificuldade escolhida no menu.
        venue_factor = 1 + venue["level"] * 0.18
        self.rhythm_total = max(5, round(difficulty["notes"] * venue_factor))
        self.rhythm_note_speed = difficulty["speed"] * venue_factor
        self.rhythm_spawn_interval = difficulty["spawn"] / venue_factor
        self.rhythm_notes = []
        self.rhythm_spawned = 0
        self.rhythm_hits = 0
        self.rhythm_perfects = 0
        self.rhythm_misses = 0
        self.rhythm_spawn_timer = 0.15
        self.state = "rhythm"
        logging.info("Começou apresentação em %s", venue["name"])

    def _update_rhythm(self, dt):
        if self.rhythm_spawned < self.rhythm_total:
            self.rhythm_spawn_timer += dt
            if self.rhythm_spawn_timer >= self.rhythm_spawn_interval:
                self.rhythm_spawn_timer -= self.rhythm_spawn_interval
                self.rhythm_notes.append(
                    {"lane": random.randrange(3), "y": 155.0, "hit": False}
                )
                self.rhythm_spawned += 1

        for note in self.rhythm_notes[:]:
            note["y"] += self.rhythm_note_speed * dt
            if note["y"] > self.rhythm_target_y + self.rhythm_hit_window:
                self.rhythm_notes.remove(note)
                self.rhythm_misses += 1

        if self.rhythm_spawned >= self.rhythm_total and not self.rhythm_notes:
            self._finish_rhythm()

    def _handle_rhythm_key(self, key):
        key_to_lane = {pygame.K_a: 0, pygame.K_s: 1, pygame.K_d: 2}
        if key == pygame.K_ESCAPE:
            self._set_toast("Apresentação abandonada: sem pagamento.")
            self.active_venue = None
            self.state = "playing"
            return

        if key not in key_to_lane:
            return

        lane = key_to_lane[key]
        candidates = [
            note for note in self.rhythm_notes
            if note["lane"] == lane
            and abs(note["y"] - self.rhythm_target_y) <= self.rhythm_hit_window
        ]
        if not candidates:
            return

        note = min(candidates, key=lambda candidate: abs(candidate["y"] - self.rhythm_target_y))
        distance = abs(note["y"] - self.rhythm_target_y)
        self.rhythm_notes.remove(note)
        self.rhythm_hits += 1
        self.score += 100
        if distance <= 15:
            self.rhythm_perfects += 1
            self.score += 50

    def _finish_rhythm(self):
        venue_id = self.active_venue
        venue = VENUES[venue_id]
        accuracy = self.rhythm_hits / max(1, self.rhythm_total)
        perfect_bonus = self.rhythm_perfects * 20
        reward = 0

        if self.rhythm_hits == self.rhythm_total:
            reward = venue["reward"] + perfect_bonus
            message = f"Show perfeito! Recebeu R$ {reward} (bônus de precisão incluído)."
        elif accuracy >= 0.65:
            reward = venue["reward"] // 2
            message = f"Boa apresentação! Recebeu R$ {reward}. Acerte todas para ganhar o total."
        else:
            message = "Apresentação ruim: sem pagamento."
            lost_item = self._lose_random_item()
            if lost_item:
                message += f" Você perdeu {ITEMS[lost_item]['name']}!"

        self.money += reward
        self.score += reward // 10
        self.songs_performed += 1
        logging.info(
            "Apresentação %s: hits=%s/%s; perfeitas=%s; pagamento=%s",
            venue["name"], self.rhythm_hits, self.rhythm_total,
            self.rhythm_perfects, reward,
        )
        self.active_venue = None
        self.state = "playing"
        self._set_toast(message, seconds=4.5)

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
            self.ranking.save(
                self.player_name or "Jogador",
                self.score,
                self.day,
                self.difficulty,
                self.end_result or "fim",
            )
            logging.info("Pontuação salva no ranking")
            self.result_saved = True
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
        screen.blit(self.player.image, self.camera.apply(self.player.rect))

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
        elif self.state == "collector":
            self._draw_hud(screen)
            self._draw_collector(screen)
        elif self.state == "paused":
            self._draw_hud(screen)
            self._draw_paused(screen)
        elif self.state == "ranking":
            self._draw_ranking(screen)
        elif self.state == "end_name":
            self._draw_end_name(screen)

        if self.toast_timer > 0 and self.state in ("playing", "shop", "sleep_confirm"):
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

    def _draw_rhythm(self, screen):
        self._draw_overlay(screen, alpha=205)
        venue = VENUES[self.active_venue]
        self._text(screen, venue["name"].upper(), self.font_title, (247, 203, 107), center=(640, 70))
        self._text(screen, "Acerte A, S ou D quando a nota chegar à linha!", self.font, (238, 242, 244), center=(640, 120))

        top = 150
        bottom = 570
        for lane_index, lane_x in enumerate(self.rhythm_lanes):
            track = pygame.Rect(lane_x - 70, top, 140, bottom - top)
            pygame.draw.rect(screen, (26, 34, 41), track, border_radius=12)
            pygame.draw.rect(screen, (91, 108, 118), track, 2, border_radius=12)
            pygame.draw.line(screen, (247, 203, 107), (lane_x - 65, self.rhythm_target_y), (lane_x + 65, self.rhythm_target_y), 4)
            key_label = self.font_large.render("ASD"[lane_index], True, (255, 255, 255))
            key_rect = key_label.get_rect(center=(lane_x, 600))
            screen.blit(key_label, key_rect)

        lane_colors = [(100, 198, 240), (249, 191, 88), (203, 133, 235)]
        for note in self.rhythm_notes:
            x = self.rhythm_lanes[note["lane"]]
            rect = pygame.Rect(x - 48, int(note["y"]) - 15, 96, 30)
            pygame.draw.rect(screen, lane_colors[note["lane"]], rect, border_radius=8)
            pygame.draw.rect(screen, (255, 255, 255), rect, 2, border_radius=8)

        self._text(screen, f"Acertos: {self.rhythm_hits}   Perfeitos: {self.rhythm_perfects}   Erros: {self.rhythm_misses}", self.font_small, (238, 242, 244), center=(640, 660))
        self._text(screen, f"Notas: {self.rhythm_spawned}/{self.rhythm_total}   |   ESC abandona", self.font_small, (190, 202, 210), center=(640, 690))

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
