import sqlite3
import sys

from pathlib import Path

import pytest

from scripts import z1_vers_db


RAW_Z1 = (
    '"MODELE          ","                "\n'
    '"MACHINE         ","MC#01   "\n'
    '"RAPPORT         ","FONC FIXES  "\n'
    '"FICHIER         ","FILE001"\n'
    '"MODE            ","Z   "\n'
    '"COMPTEUR Z      ","0021"\n'
    '"DATE            ","01-04-2023"\n'
    '"HEURE           ","13:48"\n'
    "\n"
    '"ENREGISTREMENT  ","DESIGNATION     ","QUANTITE/No     ","MONTANT         "\n'
    '"0001","CA BRUT     ","75","25,372.00"\n'
    '"0002","CA NET      ","25","25,372.00"\n'
)


def test_traiter_repertoire_enregistre_recursivement_les_prefixes_retenus(
    tmp_path: Path,
) -> None:
    repertoire = tmp_path / "fichiers_sources" / "2023_MASSENA"
    sous_repertoire = repertoire / "01-23_MASSENA"
    sous_repertoire.mkdir(parents=True)

    for nom_fichier in (
        "Z001_01_012023_MASSENA.CSV",
        "Z101_01_012023_MASSENA.CSV",
        "Z201_01_012023_MASSENA.CSV",
    ):
        (sous_repertoire / nom_fichier).write_text(
            RAW_Z1,
            encoding="cp1252",
        )

    (sous_repertoire / "Z002_01_012023_MASSENA.CSV").write_text(
        "fichier qui doit etre ignore",
        encoding="cp1252",
    )

    with sqlite3.connect(":memory:") as connection:
        z1_vers_db.creer_tables(connection)
        nombre_fichiers = z1_vers_db.traiter_repertoire(
            connection=connection,
            chemin_repertoire=tmp_path / "fichiers_sources",
        )
        nombre_entetes = connection.execute(
            "SELECT COUNT(*) FROM z1_entetes"
        ).fetchone()[0]
        nombre_lignes = connection.execute(
            "SELECT COUNT(*) FROM z1_lignes"
        ).fetchone()[0]

    assert nombre_fichiers == 3
    assert nombre_entetes == 3
    assert nombre_lignes == 6


def test_traiter_repertoire_sarrete_sur_un_fichier_invalide(
    tmp_path: Path,
) -> None:
    repertoire = tmp_path / "2023_MASSENA"
    repertoire.mkdir()
    (repertoire / "Z001_invalide.CSV").write_text(
        "invalide",
        encoding="cp1252",
    )
    (repertoire / "Z101_valide.CSV").write_text(
        RAW_Z1,
        encoding="cp1252",
    )

    with sqlite3.connect(":memory:") as connection:
        z1_vers_db.creer_tables(connection)

        with pytest.raises(ValueError):
            z1_vers_db.traiter_repertoire(
                connection=connection,
                chemin_repertoire=tmp_path,
            )

        nombre_entetes = connection.execute(
            "SELECT COUNT(*) FROM z1_entetes"
        ).fetchone()[0]

    assert nombre_entetes == 0


def test_main_recree_les_tables_z1_sans_supprimer_les_tables_ej(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "base.sqlite"
    with sqlite3.connect(chemin_base) as connection:
        z1_vers_db.creer_tables(connection)
        connection.execute("CREATE TABLE tickets (valeur TEXT)")
        connection.execute("INSERT INTO tickets VALUES ('conservee')")
        connection.execute(
            """
            INSERT INTO z1_entetes (
                nom_fichier, boutique, E_MODELE, E_MACHINE,
                E_RAPPORT, E_FICHIER, E_MODE, E_COMPTEUR_Z,
                E_DATE, E_HEURE
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("ancien.csv", "MASSENA", "", "M", "R", "F", "Z", "1", "2023-01-01", "10:00"),
        )
        connection.commit()

    monkeypatch.setattr(
        sys,
        "argv",
        ["z1_vers_db", str(tmp_path), str(chemin_base)],
    )
    monkeypatch.setattr("builtins.input", lambda _: "o")
    monkeypatch.setattr(
        z1_vers_db,
        "traiter_repertoire",
        lambda **_: 0,
    )

    z1_vers_db.main()

    with sqlite3.connect(chemin_base) as connection:
        nombre_entetes = connection.execute(
            "SELECT COUNT(*) FROM z1_entetes"
        ).fetchone()[0]
        valeur_ej = connection.execute(
            "SELECT valeur FROM tickets"
        ).fetchone()[0]

    assert nombre_entetes == 0
    assert valeur_ej == "conservee"


def test_main_conserve_les_tables_z1_si_confirmation_refusee(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "base.sqlite"
    with sqlite3.connect(chemin_base) as connection:
        z1_vers_db.creer_tables(connection)

    monkeypatch.setattr(
        sys,
        "argv",
        ["z1_vers_db", str(tmp_path), str(chemin_base)],
    )
    monkeypatch.setattr("builtins.input", lambda _: "n")
    monkeypatch.setattr(
        z1_vers_db,
        "traiter_repertoire",
        lambda **_: pytest.fail("Le traitement ne devait pas demarrer"),
    )

    z1_vers_db.main()

    with sqlite3.connect(chemin_base) as connection:
        assert z1_vers_db.trouver_tables_gerees(connection) == [
            "z1_entetes",
            "z1_lignes",
        ]
