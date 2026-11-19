"""Ranking persistente usando SQLite (incluído na biblioteca padrão do Python).

Versão 2 do banco: além de nome, pontos, dias e dificuldade, cada partida guarda como
terminou (trem, agiota derrubado ou pego) e as estatísticas do jogador (shows, cachê,
melhor precisão, maior combo, fugas, abatidos...). Um banco da versão antiga é apagado
e recriado na primeira vez que o jogo abre (o ranking recomeça do zero).
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 2

# Coluna do banco -> chave em game.stats (as demais vêm de argumentos de save()).
STAT_COLUMNS = {
    "shows": "shows", "ganho": "earned", "precisao": "best_accuracy", "combo": "best_combo",
    "bonus": "best_bonus", "pagamentos": "payments", "fugas": "escapes", "armadilhas": "traps",
    "assaltos": "robberies", "capangas": "capangas", "agiota": "agiota", "tiros": "shots", "acertos": "hits",
}

ENDINGS = {"trem": "Fugiu de trem", "agiota": "Derrubou o agiota", "pego": "Pego pelo agiota",
           "capanga": "Pego por capanga"}


class Ranking:
    def __init__(self, database_path="data/ranking.db"):
        self.database_path = Path(database_path)
        self.available = True
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._create_table()
        except (OSError, sqlite3.Error) as error:
            # O jogo continua funcionando sem ranking; o erro fica registrado em logs/error.log.
            logging.error("Ranking indisponível (%s): %s", self.database_path, error)
            self.available = False

    @contextmanager
    def _connect(self):
        """Conexão que confirma a transação (ou desfaz, se der erro) e sempre fecha o arquivo."""
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _create_table(self):
        try:
            with self._connect() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version < SCHEMA_VERSION:
                    old = connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ranking'").fetchone()
                    if old:
                        logging.info("Ranking antigo (versão %s) apagado: o novo guarda mais estatísticas", version)
                    connection.execute("DROP TABLE IF EXISTS ranking")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ranking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        nome TEXT NOT NULL,
                        pontuacao INTEGER NOT NULL,
                        dias INTEGER NOT NULL,
                        dificuldade TEXT NOT NULL,
                        resultado TEXT NOT NULL,
                        final TEXT NOT NULL DEFAULT '',
                        shows INTEGER NOT NULL DEFAULT 0,
                        ganho INTEGER NOT NULL DEFAULT 0,
                        precisao REAL NOT NULL DEFAULT 0,
                        combo INTEGER NOT NULL DEFAULT 0,
                        bonus TEXT NOT NULL DEFAULT '',
                        pagamentos INTEGER NOT NULL DEFAULT 0,
                        fugas INTEGER NOT NULL DEFAULT 0,
                        armadilhas INTEGER NOT NULL DEFAULT 0,
                        assaltos INTEGER NOT NULL DEFAULT 0,
                        capangas INTEGER NOT NULL DEFAULT 0,
                        agiota INTEGER NOT NULL DEFAULT 0,
                        tiros INTEGER NOT NULL DEFAULT 0,
                        acertos INTEGER NOT NULL DEFAULT 0,
                        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except sqlite3.Error as error:
            logging.error("Tentativa inválida de acesso ao banco de dados (criar tabela de ranking): %s", error)
            raise

    def save(self, name, score, days, difficulty, result, ending="", stats=None):
        """Salva uma partida. Devolve o id da linha (para destacá-la) ou None se o banco falhar."""
        safe_name = " ".join(name.strip().split())[:16] or "Jogador"
        if not self.available:
            return None
        stats = stats or {}
        values = {column: stats.get(key, 0) for column, key in STAT_COLUMNS.items()}
        values["bonus"] = str(values["bonus"] or "")
        columns = ["nome", "pontuacao", "dias", "dificuldade", "resultado", "final"] + list(values)
        params = [safe_name, int(score), int(days), difficulty, result, ending] + list(values.values())
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    f"INSERT INTO ranking ({', '.join(columns)}, criado_em) "
                    f"VALUES ({', '.join('?' * len(columns))}, datetime('now', 'localtime'))",
                    params,
                )
            return cursor.lastrowid
        except sqlite3.Error as error:
            logging.error("Tentativa inválida de acesso ao banco de dados (salvar pontuação): %s", error)
            return None

    def _where(self, difficulty):
        return ("WHERE dificuldade = ? ", (difficulty,)) if difficulty else ("", ())

    def top(self, limit=10, difficulty=None):
        """Melhores partidas (opcionalmente de uma dificuldade) como dicionários; [] se o banco falhar."""
        if not self.available:
            return []
        where, params = self._where(difficulty)
        query = f"SELECT * FROM ranking {where}ORDER BY pontuacao DESC, dias DESC, id ASC LIMIT ?"
        try:
            with self._connect() as connection:
                return [dict(row) for row in connection.execute(query, params + (int(limit),)).fetchall()]
        except sqlite3.Error as error:
            logging.error("Tentativa inválida de acesso ao banco de dados (consultar ranking): %s", error)
            return []

    def position(self, entry_id, difficulty=None):
        """Colocação (1 = primeiro) de uma partida salva, no filtro dado; None se não achar."""
        if not self.available or entry_id is None:
            return None
        where, params = self._where(difficulty)
        query = f"SELECT id FROM ranking {where}ORDER BY pontuacao DESC, dias DESC, id ASC"
        try:
            with self._connect() as connection:
                ids = [row["id"] for row in connection.execute(query, params).fetchall()]
        except sqlite3.Error as error:
            logging.error("Tentativa inválida de acesso ao banco de dados (posição no ranking): %s", error)
            return None
        return ids.index(entry_id) + 1 if entry_id in ids else None

    def records(self, difficulty=None):
        """Recordes do filtro: partidas, vitórias e quem tem a melhor pontuação, precisão, combo e dias."""
        empty = {"games": 0, "wins": 0, "score": None, "accuracy": None, "combo": None, "days": None}
        if not self.available:
            return empty
        where, params = self._where(difficulty)
        try:
            with self._connect() as connection:
                total = connection.execute(
                    f"SELECT COUNT(*) AS n, SUM(resultado = 'vitória') AS v FROM ranking {where}", params).fetchone()
                records = {"games": total["n"] or 0, "wins": total["v"] or 0}
                for key, column in (("score", "pontuacao"), ("accuracy", "precisao"), ("combo", "combo"),
                                    ("days", "dias")):
                    row = connection.execute(
                        f"SELECT nome, {column} AS valor FROM ranking {where}ORDER BY {column} DESC, id ASC LIMIT 1",
                        params).fetchone()
                    records[key] = (row["nome"], row["valor"]) if row else None
                return records
        except sqlite3.Error as error:
            logging.error("Tentativa inválida de acesso ao banco de dados (recordes do ranking): %s", error)
            return empty
