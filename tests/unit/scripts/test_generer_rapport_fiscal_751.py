import sqlite3
from pathlib import Path

from scripts.generer_rapport_fiscal_751 import analyser_sequences, verifier_livraison
from scripts.db_ej_vers_xlsx import NOMS_CLASSEURS_ATTENDUS


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


def test_verifier_livraison_exige_excel_et_autorise_les_travaux_preliminaires(
    tmp_path: Path,
) -> None:
    (tmp_path / "RAPPORT_ANALYSE_FISCALE_751.pdf").write_bytes(b"rapport")
    (tmp_path / "travaux_preliminaires").mkdir()
    excel = tmp_path / "excel"
    excel.mkdir()
    for nom in NOMS_CLASSEURS_ATTENDUS:
        (excel / nom).touch()

    verifier_livraison(tmp_path)
