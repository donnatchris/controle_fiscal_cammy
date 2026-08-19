import csv
import sqlite3

from datetime import date
from decimal import Decimal
from pathlib import Path

from classes.ticket import EjEnteteTicket, EjLigneTicket, EjTicket
from scripts import db_vers_csv_751, ej_vers_db
from shared.constantes import SEPARATEUR_CSV


def ticket(numero: str, facture: str) -> EjTicket:
    return EjTicket(
        entete=EjEnteteTicket(
            nomFichier="EJ020123.TXT", boutique="MASSENA", E_NUM_INTERNE=numero,
            E_DATE_TICKET=date(2023, 1, 2), E_HEURE_TICKET="11:25", type="REG",
            E_NUM_TICKET=facture, E_HT1=Decimal("100.00"), E_TVA1=Decimal("20.00"), E_TTC=Decimal("120.00"),
        ),
        lignes_articles=[EjLigneTicket(
            D_QUANTITE_ARTICLE=1, D_TAUX_TVA_ARTICLE="T1", D_MONTANT_ARTICLE=Decimal("120.00"),
        )],
    )


def lire_csv(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=SEPARATEUR_CSV))


def test_export_ej_respecte_le_contrat_csv(tmp_path: Path) -> None:
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        ej_vers_db.creer_base(connection)
        ej_vers_db.inserer_ticket(connection, ticket("000001", "000900"))
        compteurs = db_vers_csv_751.exporter_ej(connection, tmp_path)

    entetes = lire_csv(tmp_path / "EJ_ENTETES_TICKETS_MASSENA.csv")
    assert compteurs["entetes_MASSENA"] == 1
    assert list(entetes[0]) == db_vers_csv_751.COLONNES_EJ
    assert entetes[0]["E_NUM_INTERNE"] == "000001"
    assert entetes[0]["E_DATE_TICKET"] == "2023-01-02"


def test_normaliser_z_preserve_identifiants_quantite_entiere_et_date_iso() -> None:
    lignes = [{"E_COMPTEUR_Z": "0021", "E_DATE": "01-04-2023", "D_ENREGISTREMENT": "0001", "D_QUANTITE": "75.00", "D_MONTANT": Decimal("25372.00")}]
    db_vers_csv_751.normaliser_z(lignes)
    assert lignes[0] == {"E_COMPTEUR_Z": "0021", "E_DATE": "2023-04-01", "D_ENREGISTREMENT": "0001", "D_QUANTITE": "75", "D_MONTANT": "25372.00"}


def test_periodes_fichier_conserve_une_periode_multi_mois() -> None:
    assert db_vers_csv_751.periodes_fichier("Z101_01_042025_052025_062025_MASSENA.CSV") == ["2025-04", "2025-05", "2025-06"]
