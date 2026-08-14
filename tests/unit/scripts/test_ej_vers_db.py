import sqlite3
import sys

from pathlib import Path

import pytest

from scripts import ej_vers_db


def table_existe(connection: sqlite3.Connection, nom: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (nom,),
    ).fetchone()
    return row is not None


def executer_main(
    monkeypatch: pytest.MonkeyPatch,
    chemin_base: Path,
    confirmation: str | None,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["ej_vers_db", str(chemin_base.parent), str(chemin_base)],
    )
    monkeypatch.setattr(
        ej_vers_db,
        "traiter_repertoire",
        lambda **_: None,
    )

    if confirmation is None:
        def refuser_toute_question(_: str) -> str:
            raise AssertionError("Aucune confirmation ne devait être demandée")

        monkeypatch.setattr("builtins.input", refuser_toute_question)
    else:
        monkeypatch.setattr("builtins.input", lambda _: confirmation)

    ej_vers_db.main()


def test_main_refuse_de_creer_la_base_si_elle_nexiste_pas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "nouvelle_base.sqlite"

    with pytest.raises(
        FileNotFoundError,
        match="Lancez le traitement principal",
    ):
        executer_main(monkeypatch, chemin_base, confirmation=None)

    assert not chemin_base.exists()


def test_main_ne_modifie_pas_les_tables_si_confirmation_refusee(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "base_existante.sqlite"
    with sqlite3.connect(chemin_base) as connection:
        ej_vers_db.creer_base(connection)
        connection.execute(
            """
            INSERT INTO tickets (
                nomFichier, boutique, type, E_NUM_INTERNE,
                E_DATE_TICKET, E_HEURE_TICKET
            ) VALUES ('EJ.TXT', 'MASSENA', 'REG', '1', '2023-01-01', '10:00')
            """
        )
        connection.commit()

    executer_main(monkeypatch, chemin_base, confirmation="n")

    with sqlite3.connect(chemin_base) as connection:
        nombre_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets"
        ).fetchone()[0]
    assert nombre_tickets == 1


def test_main_recree_les_tables_apres_confirmation_sans_effacer_la_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "base_existante.sqlite"
    with sqlite3.connect(chemin_base) as connection:
        ej_vers_db.creer_base(connection)
        connection.execute("CREATE TABLE autre_table (valeur TEXT)")
        connection.execute("INSERT INTO autre_table VALUES ('conservee')")
        connection.execute(
            """
            INSERT INTO tickets (
                nomFichier, boutique, type, E_NUM_INTERNE,
                E_DATE_TICKET, E_HEURE_TICKET
            ) VALUES ('EJ.TXT', 'MASSENA', 'REG', '1', '2023-01-01', '10:00')
            """
        )
        connection.commit()

    executer_main(monkeypatch, chemin_base, confirmation="o")

    with sqlite3.connect(chemin_base) as connection:
        nombre_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets"
        ).fetchone()[0]
        valeur_conservee = connection.execute(
            "SELECT valeur FROM autre_table"
        ).fetchone()[0]

    assert nombre_tickets == 0
    assert valeur_conservee == "conservee"


def test_traiter_repertoire_produit_des_logs_compacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repertoire = tmp_path / "2023_MASSENA"
    repertoire.mkdir()
    chemin_fichier = repertoire / "EJ310123.TXT"
    chemin_fichier.write_text("", encoding="cp1252")
    monkeypatch.setattr(
        ej_vers_db,
        "traiter_fichier",
        lambda **_: (2, 0),
    )

    with sqlite3.connect(":memory:") as connection:
        ej_vers_db.traiter_repertoire(connection, tmp_path)

    lignes = capsys.readouterr().out.splitlines()
    assert lignes == [
        f"[EJ] {chemin_fichier} : 2 enregistrés, 0 ignorés",
        (
            "[EJ] Terminé : 1 fichiers traités, 0 ignorés, "
            "2 tickets enregistrés, 0 ignorés"
        ),
    ]
