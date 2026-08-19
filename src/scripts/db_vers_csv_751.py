"""Prépare, depuis SQLite, les CSV contractuels du dossier 751."""

from __future__ import annotations

import argparse
import csv
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from shared.constantes import CHEMIN_DB, SEPARATEUR_CSV

BOUTIQUES = ("MASSENA", "MATURIN")
ANNEES = (2023, 2024, 2025)
COLONNES_EJ = [
    "nomfichier",
    "E_NUM_INTERNE",
    "E_NUM_TICKET",
    "E_DATE_TICKET",
    "E_HEURE_TICKET",
    "E_HT1",
    "E_HT2",
    "E_HT3",
    "E_HT4",
    "E_TVA1",
    "E_TVA2",
    "E_TVA3",
    "E_TVA4",
    "E_HT_NON_TAXABLE",
    "E_TTC",
    "E_MDP_CB",
    "E_MDP_ESPECES",
    "E_MDP_CHEQUES",
]
COLONNES_LIGNES = COLONNES_EJ + [
    "D_QUANTITE_ARTICLE",
    "D_LIBELLE_ARTICLE",
    "D_TAUX_TVA_ARTICLE",
    "D_MONTANT_ARTICLE",
    "D_CORRECTION",
    "D_AUTRE_INFO",
]
COLONNES_Z = [
    "nomfichier",
    "E_MODELE",
    "E_MACHINE",
    "E_RAPPORT",
    "E_FICHIER",
    "E_MODE",
    "E_COMPTEUR_Z",
    "E_DATE",
    "E_HEURE",
    "D_ENREGISTREMENT",
    "D_DESIGNATION",
    "D_QUANTITE",
    "D_MONTANT",
]
CHAMPS_MONETAIRES_EJ = {
    "E_HT1",
    "E_HT2",
    "E_HT3",
    "E_HT4",
    "E_TVA1",
    "E_TVA2",
    "E_TVA3",
    "E_TVA4",
    "E_HT_NON_TAXABLE",
    "E_TTC",
    "E_MDP_CB",
    "E_MDP_ESPECES",
    "E_MDP_CHEQUES",
    "D_MONTANT_ARTICLE",
    "D_CORRECTION",
}
CHAMPS_IDENTIFIANTS_EJ = {"E_NUM_INTERNE", "E_NUM_TICKET"}
CHAMPS_IDENTIFIANTS_Z = {"E_COMPTEUR_Z", "D_ENREGISTREMENT"}


def decimal(value: object | None) -> Decimal:
    return Decimal(str(value)) if value not in (None, "") else Decimal(0)


def format_decimal(value: object | None) -> str:
    return "" if value in (None, "") else format(decimal(value), ".2f")


def format_entier(value: object | None) -> str:
    """Formate une quantité entière sans lui appliquer un format monétaire."""
    if value in (None, ""):
        return ""
    nombre = Decimal(str(value))
    entier = nombre.to_integral_value()
    if not nombre.is_finite() or nombre != entier:
        raise ValueError(
            f"Quantité non entière impossible à exporter sans perte : {value!r}"
        )
    return format(entier, "f")


def format_date_iso(value: object | None) -> str:
    """Retourne une date au format contractuel YYYY-MM-DD."""
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    texte = str(value).strip()
    for format_source in ("%Y-%m-%d", "%Y%m%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texte, format_source).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Date impossible à exporter au format YYYY-MM-DD : {value!r}")


def verifier_identifiants_textuels(
    row: Mapping[str, object],
    champs: Iterable[str],
) -> None:
    """Refuse une valeur déjà numérisée, dont les zéros initiaux seraient irrécupérables."""
    for champ in champs:
        valeur = row.get(champ)
        if valeur not in (None, "") and not isinstance(valeur, str):
            raise TypeError(f"{champ} doit rester du texte, valeur reçue : {valeur!r}")


def ecrire_csv(
    chemin: Path, colonnes: Sequence[str], rows: Iterable[Mapping[str, object]]
) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.DictWriter(
            fichier,
            fieldnames=colonnes,
            delimiter=SEPARATEUR_CSV,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    colonne: "" if row.get(colonne) is None else row.get(colonne)
                    for colonne in colonnes
                }
            )


def rows_dict(
    connection: sqlite3.Connection, query: str, params: tuple = ()
) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(query, params)]


def normaliser_ej(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        verifier_identifiants_textuels(row, CHAMPS_IDENTIFIANTS_EJ)
        row["E_DATE_TICKET"] = format_date_iso(row["E_DATE_TICKET"])
        for champ in CHAMPS_MONETAIRES_EJ:
            if champ in row:
                row[champ] = format_decimal(row[champ])
    return rows


def normaliser_z(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        verifier_identifiants_textuels(row, CHAMPS_IDENTIFIANTS_Z)
        row["E_DATE"] = format_date_iso(row["E_DATE"])
        row["D_QUANTITE"] = format_entier(row["D_QUANTITE"])
        row["D_MONTANT"] = format_decimal(row["D_MONTANT"])
    return rows


def exporter_ej(connection: sqlite3.Connection, staging: Path) -> dict[str, int]:
    compteurs: dict[str, int] = {}
    for boutique in BOUTIQUES:
        entetes = rows_dict(
            connection,
            """
            SELECT nomFichier AS nomfichier, E_NUM_INTERNE, E_NUM_TICKET, E_DATE_TICKET,
                   E_HEURE_TICKET, E_HT1, E_HT2, E_HT3, E_HT4, E_TVA1, E_TVA2,
                   E_TVA3, E_TVA4, E_HT_NON_TAXABLE, E_TTC, E_MDP_CB,
                   E_MDP_ESPECES, E_MDP_CHEQUES
            FROM tickets
            WHERE boutique = ? AND type IN ('REG', '_R_F')
              AND NULLIF(TRIM(E_NUM_TICKET), '') IS NOT NULL
            ORDER BY E_DATE_TICKET, E_HEURE_TICKET, E_NUM_INTERNE
            """,
            (boutique,),
        )
        lignes = rows_dict(
            connection,
            """
            SELECT t.nomFichier AS nomfichier, t.E_NUM_INTERNE, t.E_NUM_TICKET,
                   t.E_DATE_TICKET, t.E_HEURE_TICKET, t.E_HT1, t.E_HT2, t.E_HT3,
                   t.E_HT4, t.E_TVA1, t.E_TVA2, t.E_TVA3, t.E_TVA4,
                   t.E_HT_NON_TAXABLE, t.E_TTC, t.E_MDP_CB, t.E_MDP_ESPECES,
                   t.E_MDP_CHEQUES, l.D_QUANTITE_ARTICLE, l.D_LIBELLE_ARTICLE,
                   l.D_TAUX_TVA_ARTICLE, l.D_MONTANT_ARTICLE, l.D_CORRECTION,
                   l.D_AUTRE_INFO
            FROM lignes_ticket l JOIN tickets t ON t.id = l.ticket_id
            WHERE t.boutique = ? AND t.type IN ('REG', '_R_F')
              AND NULLIF(TRIM(t.E_NUM_TICKET), '') IS NOT NULL
            ORDER BY t.E_DATE_TICKET, t.E_HEURE_TICKET, t.E_NUM_INTERNE, l.id
            """,
            (boutique,),
        )
        normaliser_ej(entetes)
        normaliser_ej(lignes)
        ecrire_csv(staging / f"EJ_ENTETES_TICKETS_{boutique}.csv", COLONNES_EJ, entetes)
        ecrire_csv(
            staging / f"EJ_LIGNES_TICKETS_{boutique}.csv", COLONNES_LIGNES, lignes
        )
        compteurs[f"entetes_{boutique}"] = len(entetes)
        compteurs[f"lignes_{boutique}"] = len(lignes)
    return compteurs


def charger_z(connection: sqlite3.Connection, niveau: int) -> list[dict[str, object]]:
    return rows_dict(
        connection,
        f"""
        SELECT e.nom_fichier AS nomfichier, e.boutique, e.E_MODELE, e.E_MACHINE,
               e.E_RAPPORT, e.E_FICHIER, e.E_MODE, e.E_COMPTEUR_Z, e.E_DATE,
               e.E_HEURE, l.D_ENREGISTREMENT, l.D_DESIGNATION, l.D_QUANTITE,
               l.D_MONTANT
        FROM z{niveau}_lignes l
        JOIN z{niveau}_entetes e ON e.id = l.z{niveau}_entete_id
        ORDER BY e.boutique, e.nom_fichier, l.id
        """,
    )


def exporter_z(connection: sqlite3.Connection, staging: Path) -> None:
    jeux = {1: charger_z(connection, 1), 2: charger_z(connection, 2)}
    for niveau, rows in jeux.items():
        normaliser_z(rows)
        for boutique in BOUTIQUES:
            for annee in ANNEES:
                selection = [
                    row
                    for row in rows
                    if row["boutique"] == boutique
                    and str(annee) in str(row["nomfichier"])
                ]
                prefixe = (
                    "Z1_SyntheseMois_TOUS"
                    if niveau == 1
                    else "Z2_TransactionsMois_TOUS"
                )
                ecrire_csv(
                    staging / f"{prefixe}_{annee}_{boutique}.csv", COLONNES_Z, selection
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(CHEMIN_DB))
    parser.add_argument("--staging", type=Path, required=True)
    args = parser.parse_args(argv)

    with sqlite3.connect(args.base) as connection:
        connection.row_factory = sqlite3.Row
        compteurs = exporter_ej(connection, args.staging)
        exporter_z(connection, args.staging)

    attendu = {
        "entetes_MASSENA": 1_153,
        "entetes_MATURIN": 722,
        "lignes_MASSENA": 2_521,
        "lignes_MATURIN": 1_610,
    }
    if compteurs != attendu:
        raise RuntimeError(
            f"Volumes EJ inattendus : attendu={attendu}, obtenu={compteurs}"
        )
    print(compteurs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
