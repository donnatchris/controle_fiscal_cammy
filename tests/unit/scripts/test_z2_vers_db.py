import sqlite3
import sys

from pathlib import Path

import pytest

from scripts import z2_vers_db


RAW_Z2 = (
    '"MODELE          ","                "\n'
    '"MACHINE         ","MC#01   "\n'
    '"RAPPORT         ","FONC FIXES  "\n'
    '"FICHIER         ","FILE002"\n'
    '"MODE            ","Z   "\n'
    '"COMPTEUR Z      ","0021"\n'
    '"DATE            ","01-04-2023"\n'
    '"HEURE           ","13:48"\n'
    "\n"
    '"ENREGISTREMENT  ","DESIGNATION     ","QUANTITE/No     ","MONTANT         "\n'
    '"0001","VENTES","75","25,372.00"\n'
    '"0002","RETOURS","1","-125.50"\n'
)


def test_traiter_repertoire_enregistre_recursivement_les_prefixes_retenus(
    tmp_path: Path,
) -> None:
    repertoire = tmp_path / "fichiers_sources" / "2023_MASSENA"
    sous_repertoire = repertoire / "01-23_MASSENA"
    sous_repertoire.mkdir(parents=True)

    for nom_fichier in (
        "Z002_01_012023_MASSENA.CSV",
        "Z102_01_012023_MASSENA.CSV",
        "Z202_01_012023_MASSENA.CSV",
    ):
        (sous_repertoire / nom_fichier).write_text(
            RAW_Z2,
            encoding="cp1252",
        )

    (sous_repertoire / "Z001_01_012023_MASSENA.CSV").write_text(
        "fichier qui doit etre ignore",
        encoding="cp1252",
    )

    with sqlite3.connect(":memory:") as connection:
        z2_vers_db.creer_tables(connection)
        nombre_fichiers = z2_vers_db.traiter_repertoire(
            connection=connection,
            chemin_repertoire=tmp_path / "fichiers_sources",
        )
        nombre_entetes = connection.execute(
            "SELECT COUNT(*) FROM z2_entetes"
        ).fetchone()[0]
        nombre_lignes = connection.execute(
            "SELECT COUNT(*) FROM z2_lignes"
        ).fetchone()[0]
        montant_retour = connection.execute(
            "SELECT D_MONTANT FROM z2_lignes WHERE D_DESIGNATION = 'RETOURS'"
        ).fetchone()[0]

    assert nombre_fichiers == 3
    assert nombre_entetes == 3
    assert nombre_lignes == 6
    assert montant_retour == "-125.50"


def test_determiner_boutique_ignore_le_chemin_avant_la_racine_sources(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "MASSENA" / "fichiers_sources"
    chemin_fichier = sources / "2023_MATURIN" / "Z002.CSV"

    assert z2_vers_db.determiner_boutique(chemin_fichier, sources) == "MATURIN"


def test_traiter_repertoire_sarrete_sur_un_fichier_invalide(
    tmp_path: Path,
) -> None:
    repertoire = tmp_path / "2023_MASSENA"
    repertoire.mkdir()
    (repertoire / "Z002_invalide.CSV").write_text(
        "invalide",
        encoding="cp1252",
    )
    (repertoire / "Z102_valide.CSV").write_text(
        RAW_Z2,
        encoding="cp1252",
    )

    with sqlite3.connect(":memory:") as connection:
        z2_vers_db.creer_tables(connection)

        with pytest.raises(ValueError):
            z2_vers_db.traiter_repertoire(
                connection=connection,
                chemin_repertoire=tmp_path,
            )

        nombre_entetes = connection.execute(
            "SELECT COUNT(*) FROM z2_entetes"
        ).fetchone()[0]

    assert nombre_entetes == 0


def test_main_recree_les_tables_z2_sans_supprimer_les_tables_ej_ni_z1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "base.sqlite"
    with sqlite3.connect(chemin_base) as connection:
        z2_vers_db.creer_tables(connection)
        connection.execute("CREATE TABLE tickets (valeur TEXT)")
        connection.execute("INSERT INTO tickets VALUES ('conservee')")
        connection.execute("CREATE TABLE z1_entetes (valeur TEXT)")
        connection.execute("INSERT INTO z1_entetes VALUES ('conservee')")
        connection.execute(
            """
            INSERT INTO z2_entetes (
                nom_fichier, boutique, E_MODELE, E_MACHINE,
                E_RAPPORT, E_FICHIER, E_MODE, E_COMPTEUR_Z,
                E_DATE, E_HEURE
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ancien.csv",
                "MASSENA",
                "",
                "M",
                "R",
                "F",
                "Z",
                "1",
                "2023-01-01",
                "10:00",
            ),
        )
        connection.commit()

    monkeypatch.setattr(
        sys,
        "argv",
        ["z2_vers_db", str(tmp_path), str(chemin_base)],
    )
    monkeypatch.setattr("builtins.input", lambda _: "o")
    monkeypatch.setattr(
        z2_vers_db,
        "traiter_repertoire",
        lambda **_: 0,
    )

    z2_vers_db.main()

    with sqlite3.connect(chemin_base) as connection:
        nombre_entetes = connection.execute(
            "SELECT COUNT(*) FROM z2_entetes"
        ).fetchone()[0]
        valeur_ej = connection.execute(
            "SELECT valeur FROM tickets"
        ).fetchone()[0]
        valeur_z1 = connection.execute(
            "SELECT valeur FROM z1_entetes"
        ).fetchone()[0]

    assert nombre_entetes == 0
    assert valeur_ej == "conservee"
    assert valeur_z1 == "conservee"


def test_main_conserve_les_tables_z2_si_confirmation_refusee(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chemin_base = tmp_path / "base.sqlite"
    with sqlite3.connect(chemin_base) as connection:
        z2_vers_db.creer_tables(connection)

    monkeypatch.setattr(
        sys,
        "argv",
        ["z2_vers_db", str(tmp_path), str(chemin_base)],
    )
    monkeypatch.setattr("builtins.input", lambda _: "n")
    monkeypatch.setattr(
        z2_vers_db,
        "traiter_repertoire",
        lambda **_: pytest.fail("Le traitement ne devait pas demarrer"),
    )

    z2_vers_db.main()

    with sqlite3.connect(chemin_base) as connection:
        assert z2_vers_db.trouver_tables_gerees(connection) == [
            "z2_entetes",
            "z2_lignes",
        ]
