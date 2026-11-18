"""Configuração dos arquivos de log.

* logs/game.log  - tudo o que acontece (INFO ou mais): partidas, compras, músicas;
* logs/error.log - só problemas (WARNING ou mais): falha ao carregar assets,
  exceções e acessos inválidos ao banco de dados.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def configure_logging(log_dir="logs"):
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):  # evita linhas duplicadas se for chamado de novo
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(FORMAT)
    for filename, level in (("game.log", logging.INFO), ("error.log", logging.WARNING)):
        handler = RotatingFileHandler(directory / filename, maxBytes=512_000, backupCount=2, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    def log_uncaught(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical("Exceção não tratada", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = log_uncaught
    return root
