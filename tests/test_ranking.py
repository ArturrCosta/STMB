import sqlite3
import tempfile
import unittest
from pathlib import Path

from ranking import Ranking


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ranking.db"

    def test_old_database_is_replaced_by_the_new_one(self):
        connection = sqlite3.connect(self.path)  # banco da versão 1 (sem estatísticas)
        with connection:
            connection.execute("CREATE TABLE ranking (id INTEGER PRIMARY KEY, nome TEXT, pontuacao INTEGER, "
                               "dias INTEGER, dificuldade TEXT, resultado TEXT, criado_em TEXT)")
            connection.execute("INSERT INTO ranking VALUES (1, 'Velho', 99, 3, 'Normal', 'derrota', 'x')")
        connection.close()
        ranking = Ranking(self.path)
        self.assertTrue(ranking.available)
        self.assertEqual(ranking.top(), [])
        self.assertIsNotNone(ranking.save("Novo", 10, 1, "Normal", "derrota", "pego", {"shows": 2}))
        self.assertEqual(ranking.top()[0]["shows"], 2)
        # Abrir de novo não apaga mais nada.
        self.assertEqual(len(Ranking(self.path).top()), 1)

    def test_save_top_position_and_records(self):
        ranking = Ranking(self.path)
        a = ranking.save("Ana", 500, 4, "Normal", "vitória", "trem", {"best_accuracy": 0.95, "best_combo": 120})
        b = ranking.save("Bia", 900, 2, "Difícil", "vitória", "agiota", {"best_accuracy": 0.81, "best_combo": 300,
                                                                          "agiota": 1, "capangas": 3})
        c = ranking.save("  Caio   da   Silva  muito longo  ", 100, 9, "Fácil", "derrota", "capanga", {})
        rows = ranking.top()
        self.assertEqual([row["nome"] for row in rows], ["Bia", "Ana", "Caio da Silva mu"])
        self.assertEqual((ranking.position(b), ranking.position(a), ranking.position(c)), (1, 2, 3))
        self.assertEqual(ranking.position(a, "Normal"), 1)
        self.assertEqual(ranking.top(difficulty="Fácil")[0]["final"], "capanga")
        records = ranking.records()
        self.assertEqual((records["games"], records["wins"]), (3, 2))
        self.assertEqual(records["score"], ("Bia", 900))
        self.assertEqual(records["accuracy"], ("Ana", 0.95))
        self.assertEqual(records["combo"], ("Bia", 300))
        self.assertEqual(records["days"][1], 9)
        self.assertEqual(ranking.records("Normal")["games"], 1)

    def test_broken_database_does_not_crash(self):
        self.path.write_text("isto não é um banco sqlite")
        ranking = Ranking(self.path)
        self.assertFalse(ranking.available)
        self.assertIsNone(ranking.save("X", 1, 1, "Normal", "derrota"))
        self.assertEqual(ranking.top(), [])
        self.assertEqual(ranking.records()["games"], 0)


if __name__ == "__main__":
    unittest.main()
