import logging
import sys

import pygame

from game import Game
from log_setup import configure_logging


GAME_WIDTH = 1280
GAME_HEIGHT = 720


def window_to_game(position):
    """Posição do mouse na janela -> posição na superfície 1280x720 (None se cair na faixa preta)."""
    window_width, window_height = pygame.display.get_surface().get_size()
    scale = min(window_width / GAME_WIDTH, window_height / GAME_HEIGHT)
    offset_x = (window_width - GAME_WIDTH * scale) / 2
    offset_y = (window_height - GAME_HEIGHT * scale) / 2
    x = (position[0] - offset_x) / scale
    y = (position[1] - offset_y) / scale
    if 0 <= x < GAME_WIDTH and 0 <= y < GAME_HEIGHT:
        return int(x), int(y)
    return None


def main():
    configure_logging()
    logging.info("Iniciando Song to My Bills.")
    pygame.init()
    pygame.display.set_caption("Song to My Bills")

    screen = pygame.display.set_mode(
        (GAME_WIDTH, GAME_HEIGHT),
        pygame.RESIZABLE,
    )

    # Maximiza a janela sem entrar no modo exclusivo de tela cheia.
    try:
        from pygame._sdl2 import Window
        Window.from_display_module().maximize()
    except (ImportError, pygame.error, AttributeError):
        logging.warning("Não foi possível maximizar a janela automaticamente.")

    game_surface = pygame.Surface((GAME_WIDTH, GAME_HEIGHT))
    clock = pygame.time.Clock()
    running = True

    try:
        try:
            game = Game()
        except (OSError, ValueError, KeyError, pygame.error) as error:
            # Mapa/sprites ausentes ou corrompidos: registra em logs/error.log e sai sem "travar".
            logging.critical("Não foi possível iniciar o jogo (falha ao carregar assets): %s", error)
            print(f"Erro ao carregar os arquivos do jogo: {error}\nVeja logs/error.log.", file=sys.stderr)
            return 1
        logging.info("Jogo iniciado.")

        while running:
            # Delta time com limite para evitar saltos após minimizar a janela.
            dt = min(clock.tick(60) / 1000.0, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game.on_quit()
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    # No Pygame 2 a superfície de display é redimensionada automaticamente.
                    # Só atualizamos a referência, sem recriar a janela maximizada.
                    screen = pygame.display.get_surface()
                elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION):
                    # O jogo é desenhado em 1280x720 e depois escalado para a janela:
                    # converte a posição do mouse de volta para as coordenadas do jogo.
                    position = window_to_game(event.pos)
                    if position is not None:
                        fields = {"pos": position}
                        if event.type == pygame.MOUSEBUTTONDOWN:
                            fields["button"] = event.button
                        game.handle_event(pygame.event.Event(event.type, **fields))
                else:
                    game.handle_event(event)

            game.update(dt)
            game.draw(game_surface)

            screen = pygame.display.get_surface()
            window_width, window_height = screen.get_size()
            scale = min(
                window_width / GAME_WIDTH,
                window_height / GAME_HEIGHT,
            )
            scaled_width = max(1, int(GAME_WIDTH * scale))
            scaled_height = max(1, int(GAME_HEIGHT * scale))

            scaled_surface = pygame.transform.scale(
                game_surface,
                (scaled_width, scaled_height),
            )
            screen.fill((0, 0, 0))
            screen.blit(
                scaled_surface,
                (
                    (window_width - scaled_width) // 2,
                    (window_height - scaled_height) // 2,
                ),
            )
            pygame.display.flip()

    except Exception:
        logging.exception("Erro não tratado no loop principal.")
        raise
    finally:
        pygame.quit()
        logging.info("Jogo encerrado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
