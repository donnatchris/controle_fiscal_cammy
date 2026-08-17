import csv
import sqlite3

from datetime import date
from decimal import Decimal
from pathlib import Path

from classes.ticket import EjEnteteTicket, EjLigneTicket, EjTicket
from scripts import db_ej_vers_xlsx, db_vers_csv_751, ej_vers_db
from scripts.construire_classeurs_751 import (
    format_colonne,
    lire_csv as lire_csv_classeurs,
    nettoyer_nom,
    periodes_reference,
)
from scripts.generer_rapport_fiscal_751 import lire_csv as lire_csv_rapport
from shared.constantes import SEPARATEUR_CSV


def ticket(*, numero: str, type_ticket: str = "REG", facture: str | None = None) -> EjTicket:
    return EjTicket(
        entete=EjEnteteTicket(
            nomFichier="EJ020123.TXT",
            boutique="MASSENA",
            E_NUM_INTERNE=numero,
            E_DATE_TICKET=date(2023, 1, 2),
            E_HEURE_TICKET="11:25",
            type=type_ticket,
            E_NUM_TICKET=facture,
            E_HT1=Decimal("100.00") if facture else None,
            E_TVA1=Decimal("20.00") if facture else None,
            E_TTC=Decimal("120.00") if facture else None,
        ),
        lignes_articles=[
            EjLigneTicket(
                D_QUANTITE_ARTICLE=1,
                D_LIBELLE_ARTICLE=None,
                D_TAUX_TVA_ARTICLE="T1",
                D_MONTANT_ARTICLE=Decimal("120.00"),
            )
        ] if facture else [],
    )


def lire_csv(chemin: Path) -> list[dict[str, str]]:
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=SEPARATEUR_CSV))


def test_generateur_et_lecteurs_csv_utilisent_le_separateur_partage(
    tmp_path: Path,
) -> None:
    chemin = tmp_path / "export.csv"
    lignes = [{"E_NUM_INTERNE": "000001", "E_DATE_TICKET": "2023-01-02"}]

    db_vers_csv_751.ecrire_csv(
        chemin,
        ["E_NUM_INTERNE", "E_DATE_TICKET"],
        lignes,
    )

    assert chemin.read_text(encoding="utf-8-sig").splitlines()[0] == (
        f"E_NUM_INTERNE{SEPARATEUR_CSV}E_DATE_TICKET"
    )
    assert lire_csv_classeurs(chemin) == lignes
    assert lire_csv_rapport(chemin) == lignes


def test_export_ej_filtre_uniquement_les_ventes_et_respecte_le_contrat(tmp_path: Path) -> None:
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        ej_vers_db.creer_base(connection)
        ej_vers_db.inserer_ticket(connection, ticket(numero="000001", facture="000900"))
        ej_vers_db.inserer_ticket(connection, ticket(numero="000002", facture=None))
        ej_vers_db.inserer_ticket(connection, ticket(numero="000003", type_ticket="X"))
        compteurs = db_vers_csv_751.exporter_ej(connection, tmp_path)

    entetes = lire_csv(tmp_path / "EJ_ENTETES_TICKETS_MASSENA.csv")
    lignes = lire_csv(tmp_path / "EJ_LIGNES_TICKETS_MASSENA.csv")
    assert compteurs["entetes_MASSENA"] == 1
    assert compteurs["lignes_MASSENA"] == 1
    assert list(entetes[0]) == db_vers_csv_751.COLONNES_EJ
    assert entetes[0]["nomfichier"] == "EJ020123.TXT"
    assert entetes[0]["E_NUM_INTERNE"] == "000001"
    assert entetes[0]["E_NUM_TICKET"] == "000900"
    assert entetes[0]["E_DATE_TICKET"] == "2023-01-02"
    assert entetes[0]["E_HT2"] == ""
    assert lignes[0]["D_TAUX_TVA_ARTICLE"] == "T1"
    assert lignes[0]["D_LIBELLE_ARTICLE"] == ""
    assert ";" not in (tmp_path / "EJ_ENTETES_TICKETS_MASSENA.csv").read_text(
        encoding="utf-8-sig"
    ).splitlines()[0]


def test_normaliser_z_preserve_identifiants_quantite_entiere_et_date_iso() -> None:
    lignes = [{
        "E_COMPTEUR_Z": "0021",
        "E_DATE": "01-04-2023",
        "D_ENREGISTREMENT": "0001",
        "D_QUANTITE": "75.00",
        "D_MONTANT": Decimal("25372.00"),
    }]

    db_vers_csv_751.normaliser_z(lignes)

    assert lignes == [{
        "E_COMPTEUR_Z": "0021",
        "E_DATE": "2023-04-01",
        "D_ENREGISTREMENT": "0001",
        "D_QUANTITE": "75",
        "D_MONTANT": "25372.00",
    }]


def test_format_entier_refuse_une_quantite_decimale() -> None:
    try:
        db_vers_csv_751.format_entier("1.5")
    except ValueError as exc:
        assert "non entière" in str(exc)
    else:
        raise AssertionError("Une quantité décimale aurait dû être refusée")


def test_periodes_fichier_conserve_une_periode_multi_mois() -> None:
    assert db_vers_csv_751.periodes_fichier(
        "Z101_01_042025_052025_062025_MASSENA.CSV"
    ) == ["2025-04", "2025-05", "2025-06"]


def test_constructeur_python_conserve_periodes_et_noms_excel() -> None:
    assert periodes_reference(
        "Z101_01_042025_052025_062025_MASSENA.CSV"
    ) == ["2025-04", "2025-05", "2025-06"]
    assert nettoyer_nom("REF./TIROIR") == "REF__TIROIR"
    assert format_colonne("E_DATE") == "yyyy-mm-dd"
    assert format_colonne("D_QUANTITE") == "0"


def test_verifier_dossier_exige_les_18_classeurs_et_autorise_le_rapport(
    tmp_path: Path,
) -> None:
    repertoire = tmp_path
    for nom in db_ej_vers_xlsx.NOMS_CLASSEURS_ATTENDUS:
        (repertoire / nom).touch()

    classeurs = db_ej_vers_xlsx.verifier_dossier_classeurs(tmp_path)

    assert len(classeurs) == 18

    (repertoire / "RAPPORT_ANALYSE_FISCALE_751.pdf").touch()
    assert len(db_ej_vers_xlsx.verifier_dossier_classeurs(tmp_path)) == 18

    (repertoire / "diagnostic.ndjson").touch()
    try:
        db_ej_vers_xlsx.verifier_dossier_classeurs(tmp_path)
    except RuntimeError as exc:
        assert "diagnostic.ndjson" in str(exc)
    else:
        raise AssertionError("Un fichier non contractuel aurait dû être refusé")


def test_nettoyer_ancienne_sortie_ne_supprime_pas_un_fichier_inconnu(
    tmp_path: Path,
) -> None:
    ancien = tmp_path / "livraison_reprise"
    ancien.mkdir()
    (ancien / "ancien.txt").write_text("généré", encoding="utf-8")
    inconnu = tmp_path / "fichier_utilisateur.txt"
    inconnu.write_text("à préserver", encoding="utf-8")

    db_ej_vers_xlsx.nettoyer_ancienne_sortie(tmp_path)

    assert not ancien.exists()
    assert inconnu.read_text(encoding="utf-8") == "à préserver"
