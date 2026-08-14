import argparse
import sqlite3

from decimal import Decimal
from pathlib import Path

from classes.z import Z
from shared.constantes import (
    BOUTIQUES,
    CHEMIN_DB,
    PREFIXES_FICHIERS_Z1,
)
from shared.database import ouvrir_base_existante


TABLES_GEREES = ("z1_entetes", "z1_lignes")


# ============================================================
# BASE DE DONNEES
# ============================================================


def trouver_tables_gerees(
    connection: sqlite3.Connection,
) -> list[str]:
    """Retourne les tables Z1 qui existent deja dans la base."""
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name IN (?, ?)
        """,
        TABLES_GEREES,
    ).fetchall()
    tables_trouvees = {row[0] for row in rows}
    return [
        table
        for table in TABLES_GEREES
        if table in tables_trouvees
    ]


def supprimer_tables_gerees(
    connection: sqlite3.Connection,
) -> None:
    """Supprime uniquement les tables Z1, enfant puis parent."""
    connection.execute("DROP TABLE IF EXISTS z1_lignes")
    connection.execute("DROP TABLE IF EXISTS z1_entetes")


def creer_tables(connection: sqlite3.Connection) -> None:
    """Cree les tables necessaires au stockage des fichiers Z1."""
    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        CREATE TABLE z1_entetes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nom_fichier TEXT NOT NULL,
            boutique TEXT NOT NULL,

            E_MODELE TEXT NOT NULL,
            E_MACHINE TEXT NOT NULL,
            E_RAPPORT TEXT NOT NULL,
            E_FICHIER TEXT NOT NULL,
            E_MODE TEXT NOT NULL,
            E_COMPTEUR_Z TEXT NOT NULL,
            E_DATE TEXT NOT NULL,
            E_HEURE TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE z1_lignes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            z1_entete_id INTEGER NOT NULL,

            D_ENREGISTREMENT TEXT NOT NULL,
            D_DESIGNATION TEXT NOT NULL,
            D_QUANTITE INTEGER NOT NULL,
            D_MONTANT TEXT NOT NULL,

            FOREIGN KEY (z1_entete_id)
                REFERENCES z1_entetes(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.commit()


def decimal_vers_db(value: Decimal) -> str:
    """Convertit un Decimal en texte sans perte de precision."""
    return str(value)


def inserer_z1(
    connection: sqlite3.Connection,
    z1: Z,
) -> int:
    """Insere un entete Z1 puis toutes ses lignes."""
    curseur = connection.execute(
        """
        INSERT INTO z1_entetes (
            nom_fichier,
            boutique,
            E_MODELE,
            E_MACHINE,
            E_RAPPORT,
            E_FICHIER,
            E_MODE,
            E_COMPTEUR_Z,
            E_DATE,
            E_HEURE
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            z1.header.nom_fichier,
            z1.boutique,
            z1.header.E_MODELE,
            z1.header.E_MACHINE,
            z1.header.E_RAPPORT,
            z1.header.E_FICHIER,
            z1.header.E_MODE,
            z1.header.E_COMPTEUR_Z,
            z1.header.E_DATE.isoformat(),
            z1.header.E_HEURE,
        ),
    )

    z1_entete_id = curseur.lastrowid
    if z1_entete_id is None:
        raise RuntimeError(
            "Impossible de recuperer l'identifiant de l'entete Z1"
        )

    connection.executemany(
        """
        INSERT INTO z1_lignes (
            z1_entete_id,
            D_ENREGISTREMENT,
            D_DESIGNATION,
            D_QUANTITE,
            D_MONTANT
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                z1_entete_id,
                ligne.D_ENREGISTREMENT,
                ligne.D_DESIGNATION,
                ligne.D_QUANTITE,
                decimal_vers_db(ligne.D_MONTANT),
            )
            for ligne in z1.lines
        ],
    )

    return z1_entete_id


# ============================================================
# TRAITEMENT DES FICHIERS Z1
# ============================================================


def est_fichier_z1(chemin_fichier: Path) -> bool:
    """Indique si le nom correspond a l'un des prefixes Z1 retenus."""
    nom_fichier = chemin_fichier.name.upper()
    return (
        chemin_fichier.is_file()
        and chemin_fichier.suffix.upper() == ".CSV"
        and nom_fichier.startswith(PREFIXES_FICHIERS_Z1)
    )


def determiner_boutique(chemin_fichier: Path) -> str:
    """Determine l'unique boutique presente dans le chemin du fichier."""
    boutiques_trouvees = [
        boutique
        for boutique in BOUTIQUES
        if boutique in str(chemin_fichier).upper()
    ]
    if len(boutiques_trouvees) != 1:
        raise ValueError(
            "Impossible de determiner la boutique pour le fichier "
            f"{chemin_fichier} "
            f"(boutiques trouvees : {boutiques_trouvees})"
        )
    return boutiques_trouvees[0]


def traiter_fichier(
    connection: sqlite3.Connection,
    chemin_fichier: Path,
) -> None:
    """Parse et enregistre un fichier Z1."""
    raw = chemin_fichier.read_text(
        encoding="cp1252",
        errors="replace",
    )
    z1 = Z.from_raw(
        boutique=determiner_boutique(chemin_fichier),
        nom_fichier=chemin_fichier.name,
        raw=raw,
    )
    inserer_z1(connection, z1)


def traiter_repertoire(
    connection: sqlite3.Connection,
    chemin_repertoire: Path,
) -> int:
    """Explore recursivement un repertoire et enregistre ses fichiers Z1."""
    fichiers = sorted(
        chemin
        for chemin in chemin_repertoire.rglob("*")
        if est_fichier_z1(chemin)
    )

    for chemin_fichier in fichiers:
        print(f"Traitement du fichier : {chemin_fichier}")
        traiter_fichier(
            connection=connection,
            chemin_fichier=chemin_fichier,
        )

    connection.commit()
    print(f"Fichiers Z1 enregistres : {len(fichiers)}")
    return len(fichiers)


# ============================================================
# MAIN
# ============================================================


def main(argv: list[str] | None = None) -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "chemin_repertoire",
        help="Chemin du repertoire contenant les fichiers sources",
    )
    parser.add_argument(
        "chemin_base",
        help="Chemin vers la base de donnees SQLite",
        nargs="?",
        default=CHEMIN_DB,
    )
    args = parser.parse_args(argv)

    chemin_repertoire = Path(args.chemin_repertoire)
    chemin_base = Path(args.chemin_base)
    with ouvrir_base_existante(chemin_base) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        tables_existantes = trouver_tables_gerees(connection)

        if tables_existantes:
            print(
                "ATTENTION : les tables suivantes existent deja "
                f"dans la base : {', '.join(tables_existantes)}."
            )
            confirmation = input(
                "Voulez-vous supprimer et recreer ces tables ? (o/N) "
            )
            if confirmation.strip().lower() != "o":
                print("Abandon du traitement.")
                return False
            supprimer_tables_gerees(connection)

        creer_tables(connection)
        traiter_repertoire(
            connection=connection,
            chemin_repertoire=chemin_repertoire,
        )

    return True


if __name__ == "__main__":
    main()
