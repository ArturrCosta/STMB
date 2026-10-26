import logging
from pathlib import Path

import pygame

from game import Game


GAME_WIDTH = 1280
GAME_HEIGHT = 720


def configure_logging():
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        filename="logs/game.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )


def main():
    configure_logging()
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
        game = Game()
        logging.info("Jogo iniciado.")

        while running:
            # Delta time com limite para evitar saltos após minimizar a janela.
            dt = min(clock.tick(60) / 1000.0, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    # No Pygame 2 a superfície de display é redimensionada automaticamente.
                    # Só atualizamos a referência, sem recriar a janela maximizada.
                    screen = pygame.display.get_surface()
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


if __name__ == "__main__":
    main()
