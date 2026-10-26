"""Ranking persistente usando SQLite (incluído na biblioteca padrão do Python)."""

import sqlite3
from pathlib import Path


class Ranking:
    def __init__(self, database_path="data/ranking.db"):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _create_table(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ranking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    pontuacao INTEGER NOT NULL,
                    dias INTEGER NOT NULL,
                    dificuldade TEXT NOT NULL,
                    resultado TEXT NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save(self, name, score, days, difficulty, result):
        safe_name = " ".join(name.strip().split())[:16] or "Jogador"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ranking (nome, pontuacao, dias, dificuldade, resultado)
                VALUES (?, ?, ?, ?, ?)
                """,
                (safe_name, int(score), int(days), difficulty, result),
            )

    def top(self, limit=10):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT nome, pontuacao, dias, dificuldade, resultado, criado_em
                FROM ranking
                ORDER BY pontuacao DESC, dias DESC, id ASC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        return rows
