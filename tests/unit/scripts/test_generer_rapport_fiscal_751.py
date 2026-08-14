import sqlite3

from scripts.generer_rapport_fiscal_751 import analyser_sequences


def test_sequence_exhaustive_explique_les_sauts_des_ventes() -> None:
    connexion = sqlite3.connect(":memory:")
    connexion.row_factory = sqlite3.Row
    connexion.execute(
        """
        CREATE TABLE tickets (
            boutique TEXT, type TEXT, E_NUM_INTERNE TEXT, E_NUM_TICKET TEXT,
            E_DATE_TICKET TEXT, E_HEURE_TICKET TEXT
        )
        """
    )
    connexion.executemany(
        "INSERT INTO tickets VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("MASSENA", "REG", "000001", "000101", "2023-01-01", "10:00"),
            ("MASSENA", "X", "000002", None, "2023-01-01", "10:01"),
            ("MASSENA", "REG", "000003", "000102", "2023-01-01", "10:02"),
        ],
    )

    resultat = analyser_sequences(connexion.execute("SELECT * FROM tickets").fetchall())
    massena = resultat["MASSENA"]

    assert massena["interne_absents_exhaustif"] == 0
    assert massena["numeros_absents_ventes"] == 1
    assert massena["absents_expliques"] is True
    assert massena["ticket_absents"] == 0
    assert massena["regressions_chronologiques"] == 0
