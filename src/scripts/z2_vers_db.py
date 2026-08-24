import argparse
import sqlite3
from decimal import Decimal
from pathlib import Path

from classes.z import Z
from shared.constantes import (
    CHEMIN_DB,
    PREFIXES_FICHIERS_Z2,
)
from shared.database import ouvrir_base_existante
from shared.sources import trouver_boutiques_dans_sources

TABLES_GEREES = ("z2_entetes", "z2_lignes")


# ============================================================
# BASE DE DONNEES
# ============================================================


def trouver_tables_gerees(
    connection: sqlite3.Connection,
) -> list[str]:
    """Retourne les tables Z2 qui existent deja dans la base."""
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
    return [table for table in TABLES_GEREES if table in tables_trouvees]


def supprimer_tables_gerees(
    connection: sqlite3.Connection,
) -> None:
    """Supprime uniquement les tables Z2, enfant puis parent."""
    connection.execute("DROP TABLE IF EXISTS z2_lignes")
    connection.execute("DROP TABLE IF EXISTS z2_entetes")


def creer_tables(connection: sqlite3.Connection) -> None:
    """Cree les tables necessaires au stockage des fichiers Z2."""
    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        CREATE TABLE z2_entetes (
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
        CREATE TABLE z2_lignes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            z2_entete_id INTEGER NOT NULL,

            D_ENREGISTREMENT TEXT NOT NULL,
            D_DESIGNATION TEXT NOT NULL,
            D_QUANTITE INTEGER NOT NULL,
            D_MONTANT TEXT NOT NULL,

            FOREIGN KEY (z2_entete_id)
                REFERENCES z2_entetes(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.commit()


def decimal_vers_db(value: Decimal) -> str:
    """Convertit un Decimal en texte sans perte de precision."""
    return str(value)


def inserer_z2(
    connection: sqlite3.Connection,
    z2: Z,
) -> int:
    """Insere un entete Z2 puis toutes ses lignes."""
    curseur = connection.execute(
        """
        INSERT INTO z2_entetes (
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
            z2.header.nom_fichier,
            z2.boutique,
            z2.header.E_MODELE,
            z2.header.E_MACHINE,
            z2.header.E_RAPPORT,
            z2.header.E_FICHIER,
            z2.header.E_MODE,
            z2.header.E_COMPTEUR_Z,
            z2.header.E_DATE.isoformat(),
            z2.header.E_HEURE,
        ),
    )

    z2_entete_id = curseur.lastrowid
    if z2_entete_id is None:
        raise RuntimeError("Impossible de recuperer l'identifiant de l'entete Z2")

    connection.executemany(
        """
        INSERT INTO z2_lignes (
            z2_entete_id,
            D_ENREGISTREMENT,
            D_DESIGNATION,
            D_QUANTITE,
            D_MONTANT
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                z2_entete_id,
                ligne.D_ENREGISTREMENT,
                ligne.D_DESIGNATION,
                ligne.D_QUANTITE,
                decimal_vers_db(ligne.D_MONTANT),
            )
            for ligne in z2.lines
        ],
    )

    return z2_entete_id


# ============================================================
# TRAITEMENT DES FICHIERS Z2
# ============================================================


def est_fichier_z2(chemin_fichier: Path) -> bool:
    """Indique si le nom correspond a l'un des prefixes Z2 retenus."""
    nom_fichier = chemin_fichier.name.upper()
    return (
        chemin_fichier.is_file()
        and chemin_fichier.suffix.upper() == ".CSV"
        and nom_fichier.startswith(PREFIXES_FICHIERS_Z2)
    )


def determiner_boutique(
    chemin_fichier: Path,
    chemin_repertoire: Path,
) -> str:
    """Determine la boutique depuis la seule arborescence des sources."""
    boutiques_trouvees = trouver_boutiques_dans_sources(
        chemin_fichier,
        chemin_repertoire,
    )
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
    chemin_repertoire: Path,
) -> None:
    """Parse et enregistre un fichier Z2."""
    raw = chemin_fichier.read_text(
        encoding="cp1252",
        errors="replace",
    )
    z2 = Z.from_raw(
        boutique=determiner_boutique(chemin_fichier, chemin_repertoire),
        nom_fichier=chemin_fichier.name,
        raw=raw,
    )
    inserer_z2(connection, z2)


def traiter_repertoire(
    connection: sqlite3.Connection,
    chemin_repertoire: Path,
) -> int:
    """Explore recursivement un repertoire et enregistre ses fichiers Z2."""
    fichiers = sorted(
        chemin for chemin in chemin_repertoire.rglob("*") if est_fichier_z2(chemin)
    )

    for chemin_fichier in fichiers:
        print(f"Traitement du fichier : {chemin_fichier}")
        traiter_fichier(
            connection=connection,
            chemin_fichier=chemin_fichier,
            chemin_repertoire=chemin_repertoire,
        )

    connection.commit()
    print(f"Fichiers Z2 enregistres : {len(fichiers)}")
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
            confirmation = input("Voulez-vous supprimer et recreer ces tables ? (o/N) ")
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
