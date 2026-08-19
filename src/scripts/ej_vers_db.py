import argparse
import sqlite3
from decimal import Decimal
from pathlib import Path

# À adapter selon le nom réel de ton fichier
from classes.ticket import EjTicket
from shared.constantes import BOUTIQUES, CHEMIN_DB, SEPARATEUR_TICKET
from shared.database import ouvrir_base_existante

tickets_ignores: dict[str, int] = {}
TABLES_GEREES = ("tickets", "lignes_ticket")


# ============================================================
# BASE DE DONNÉES
# ============================================================


def trouver_tables_gerees(
    connection: sqlite3.Connection,
) -> list[str]:
    """Retourne les tables gérées qui existent déjà dans la base."""
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
    """Supprime uniquement les tables de tickets, enfant puis parent."""
    connection.execute("DROP TABLE IF EXISTS lignes_ticket")
    connection.execute("DROP TABLE IF EXISTS tickets")


def creer_base(connection: sqlite3.Connection) -> None:
    """
    Crée les tables nécessaires.

    Cette fonction n'est appelée qu'une seule fois,
    au lancement du programme.
    """

    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nomFichier TEXT NOT NULL,
            boutique TEXT NOT NULL,
            type TEXT NOT NULL,
            evenement TEXT,
            signature TEXT,

            E_NUM_INTERNE TEXT NOT NULL,
            E_NUM_TICKET TEXT,
            E_DATE_TICKET TEXT NOT NULL,
            E_HEURE_TICKET TEXT NOT NULL,

            E_HT1 TEXT,
            E_HT2 TEXT,
            E_HT3 TEXT,
            E_HT4 TEXT,

            E_TVA1 TEXT,
            E_TVA2 TEXT,
            E_TVA3 TEXT,
            E_TVA4 TEXT,

            E_HT_NON_TAXABLE TEXT,

            E_TTC TEXT,

            E_MDP_CB TEXT,
            E_MDP_ESPECES TEXT,
            E_MDP_CHEQUES TEXT,

            UNIQUE (boutique, E_NUM_INTERNE)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE lignes_ticket (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ticket_id INTEGER NOT NULL,

            D_QUANTITE_ARTICLE TEXT DEFAULT NULL,
            D_LIBELLE_ARTICLE TEXT DEFAULT NULL,
            D_TAUX_TVA_ARTICLE TEXT DEFAULT NULL,
            D_MONTANT_ARTICLE TEXT DEFAULT NULL,

            D_CORRECTION TEXT DEFAULT NULL,
            D_AUTRE_INFO TEXT DEFAULT NULL,

            FOREIGN KEY (ticket_id)
                REFERENCES tickets(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.commit()


def decimal_vers_db(value: Decimal | None) -> str | None:
    """
    Convertit un Decimal pour stockage SQLite.

    None reste None et sera donc stocké en NULL.
    """
    if value is None:
        return None

    return str(value)


def inserer_ticket(
    connection: sqlite3.Connection,
    ticket: EjTicket,
) -> int:
    """
    Insère un ticket puis toutes ses lignes.

    Les lignes sont liées au ticket grâce à ticket_id.
    """

    curseur = connection.execute(
        """
        INSERT INTO tickets (
            nomFichier,
            boutique,
            type,
            evenement,
            signature,

            E_NUM_INTERNE,
            E_NUM_TICKET,
            E_DATE_TICKET,
            E_HEURE_TICKET,

            E_HT1,
            E_HT2,
            E_HT3,
            E_HT4,

            E_TVA1,
            E_TVA2,
            E_TVA3,
            E_TVA4,

            E_HT_NON_TAXABLE,

            E_TTC,

            E_MDP_CB,
            E_MDP_ESPECES,
            E_MDP_CHEQUES
        )
        VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?,
            ?,
            ?, ?, ?
        )
        """,
        (
            ticket.entete.nomFichier,
            ticket.entete.boutique,
            ticket.entete.type,
            ticket.entete.evenement,
            ticket.entete.signature,
            ticket.entete.E_NUM_INTERNE,
            ticket.entete.E_NUM_TICKET,
            ticket.entete.E_DATE_TICKET.isoformat(),
            ticket.entete.E_HEURE_TICKET,
            decimal_vers_db(ticket.entete.E_HT1),
            decimal_vers_db(ticket.entete.E_HT2),
            decimal_vers_db(ticket.entete.E_HT3),
            decimal_vers_db(ticket.entete.E_HT4),
            decimal_vers_db(ticket.entete.E_TVA1),
            decimal_vers_db(ticket.entete.E_TVA2),
            decimal_vers_db(ticket.entete.E_TVA3),
            decimal_vers_db(ticket.entete.E_TVA4),
            decimal_vers_db(ticket.entete.E_HT_NON_TAXABLE),
            decimal_vers_db(ticket.entete.E_TTC),
            decimal_vers_db(ticket.entete.E_MDP_CB),
            decimal_vers_db(ticket.entete.E_MDP_ESPECES),
            decimal_vers_db(ticket.entete.E_MDP_CHEQUES),
        ),
    )

    ticket_id = curseur.lastrowid

    if ticket_id is None:
        raise RuntimeError("Impossible de récupérer l'identifiant du ticket")

    connection.executemany(
        """
        INSERT INTO lignes_ticket (
            ticket_id,

            D_QUANTITE_ARTICLE,
            D_LIBELLE_ARTICLE,
            D_TAUX_TVA_ARTICLE,
            D_MONTANT_ARTICLE,

            D_CORRECTION,
            D_AUTRE_INFO
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                ticket_id,
                ligne.D_QUANTITE_ARTICLE,
                ligne.D_LIBELLE_ARTICLE,
                ligne.D_TAUX_TVA_ARTICLE,
                decimal_vers_db(ligne.D_MONTANT_ARTICLE),
                decimal_vers_db(ligne.D_CORRECTION),
                ligne.D_AUTRE_INFO,
            )
            for ligne in ticket.lignes_articles
        ],
    )

    return ticket_id


# ============================================================
# TRAITEMENT DES BLOCS EJ
# ============================================================


def traiter_fichier(
    connection: sqlite3.Connection,
    boutique: str,
    chemin_fichier: Path,
) -> tuple[int, int]:
    """
    Parse et enregistre tous les tickets d'un fichier EJ.
    """

    contenu = chemin_fichier.read_text(
        encoding="cp1252",
        errors="replace",
    )

    blocs = contenu.split(SEPARATEUR_TICKET)

    nombre_enregistres = 0
    nombre_ignores = 0

    for bloc in blocs[1:]:
        raw_ticket = f"{SEPARATEUR_TICKET}{bloc}"

        ticket = EjTicket.from_raw_data(
            nom_fichier=chemin_fichier.name,
            boutique=boutique,
            raw_data=raw_ticket,
        )

        inserer_ticket(connection, ticket)

        nombre_enregistres += 1

    return nombre_enregistres, nombre_ignores


# ============================================================
# TRAITEMENT DU RÉPERTOIRE
# ============================================================


def traiter_repertoire(
    connection: sqlite3.Connection,
    chemin_repertoire: Path,
) -> None:
    fichiers = sorted(chemin_repertoire.rglob("EJ*.TXT"))

    fichiers_ignores = 0
    fichiers_traites = 0

    total_tickets_enregistres = 0
    total_tickets_ignores = 0

    for chemin_fichier in fichiers:
        boutiques_trouvees = [
            boutique
            for boutique in BOUTIQUES
            if boutique in str(chemin_fichier).upper()
        ]

        if not boutiques_trouvees or len(boutiques_trouvees) > 1:
            print(
                f"[EJ] Ignoré : {chemin_fichier} "
                f"(boutiques trouvées : {boutiques_trouvees})"
            )

            fichiers_ignores += 1
            continue

        boutique = boutiques_trouvees[0]

        nombre_enregistres, nombre_ignores = traiter_fichier(
            connection=connection,
            boutique=boutique,
            chemin_fichier=chemin_fichier,
        )

        total_tickets_enregistres += nombre_enregistres
        total_tickets_ignores += nombre_ignores

        fichiers_traites += 1

        print(
            f"[EJ] {chemin_fichier} : "
            f"{nombre_enregistres} enregistrés, "
            f"{nombre_ignores} ignorés"
        )

    # Un seul commit global une fois
    # tout le répertoire traité.
    connection.commit()

    print(
        "[EJ] Terminé : "
        f"{fichiers_traites} fichiers traités, "
        f"{fichiers_ignores} ignorés, "
        f"{total_tickets_enregistres} tickets enregistrés, "
        f"{total_tickets_ignores} ignorés"
    )


# ============================================================
# MAIN
# ============================================================


def main(argv: list[str] | None = None) -> bool:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "chemin_repertoire",
        help=("Chemin vers le répertoire contenant les fichiers EJ"),
    )

    parser.add_argument(
        "chemin_base",
        help="Chemin vers la base de données SQLite",
        nargs="?",
        default=CHEMIN_DB,
    )

    args = parser.parse_args(argv)

    chemin_repertoire = Path(args.chemin_repertoire)

    chemin_base = Path(args.chemin_base)

    # --------------------------------------------------------
    # UNE SEULE CONNEXION
    # --------------------------------------------------------

    with ouvrir_base_existante(chemin_base) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        tables_existantes = trouver_tables_gerees(connection)

        if tables_existantes:
            print(
                "ATTENTION : les tables suivantes existent "
                "déjà dans la base : "
                f"{', '.join(tables_existantes)}."
            )

            confirmation = input("Voulez-vous supprimer et recréer ces tables ? (o/N) ")

            if confirmation.lower() != "o":
                print("Abandon du traitement.")
                return False

            supprimer_tables_gerees(connection)

        # ----------------------------------------------------
        # BASE CRÉÉE UNE SEULE FOIS
        # ----------------------------------------------------

        creer_base(connection)

        # ----------------------------------------------------
        # PUIS TRAITEMENT DE TOUS LES FICHIERS
        # ----------------------------------------------------

        traiter_repertoire(
            connection=connection,
            chemin_repertoire=chemin_repertoire,
        )

    return True


if __name__ == "__main__":
    main()
