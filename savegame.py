"""Salvamento simples da partida em data/savegame.json (opcional no enunciado)."""

import json
import logging
from pathlib import Path

SAVE_PATH = Path("data") / "savegame.json"
SAVE_VERSION = 1

_FIELDS = {
    "difficulty": str, "money": int, "debt": int, "daily_payment": int, "day": int,
    "phase": int, "score": int, "songs_performed": int, "missed_payments": int,
    "inventory": list, "player_position": list,
}


def save_game(data, path=None):
    """Grava o dicionário `data`. Devolve True se conseguiu."""
    payload = dict(data, version=SAVE_VERSION)
    try:
        path = Path(path or SAVE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as error:
        logging.error("Não foi possível salvar a partida: %s", error)
        return False
    return True


def load_game(path=None):
    """Lê e valida o save. Devolve None se não existir ou se estiver corrompido."""
    path = Path(path or SAVE_PATH)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            raise ValueError("versão de save desconhecida")
        for key, kind in _FIELDS.items():
            if not isinstance(data.get(key), kind) or isinstance(data.get(key), bool):
                raise ValueError(f"campo inválido: {key}")
        if len(data["player_position"]) != 2 or not all(isinstance(v, (int, float)) for v in data["player_position"]):
            raise ValueError("campo inválido: player_position")
        if not all(isinstance(item, str) for item in data["inventory"]):
            raise ValueError("campo inválido: inventory")
    except (OSError, ValueError) as error:
        logging.error("Save ignorado (arquivo inválido): %s", error)
        return None
    return data


def has_save(path=None):
    return load_game(path) is not None


def delete_save(path=None):
    try:
        Path(path or SAVE_PATH).unlink(missing_ok=True)
    except OSError as error:
        logging.error("Não foi possível apagar o save: %s", error)
