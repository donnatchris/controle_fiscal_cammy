from decimal import Decimal
from datetime import date

import pytest

from classes.ticket import EjTicket


def test_from_raw_data_parse_ticket_complet() -> None:
    raw_data = """1-----------------------
REG  02-01-2023 11:25
004517
1 DEPT001 T1 €299.00
HORS TAXE 1 €249.17
TVA 1 €49.83
TOTAL €299.00
CARTES €299.00
FACTURE No. 003562
2-----------------------
SIGNATURE_LIGNE_1
SIGNATURE_LIGNE_2
"""

    ticket = EjTicket.from_raw_data(
        nom_fichier="EJ020123.TXT",
        boutique="MASSENA",
        raw_data=raw_data,
    )

    entete = ticket.entete

    assert entete.nomFichier == "EJ020123.TXT"
    assert entete.boutique == "MASSENA"

    assert entete.type == "REG"
    assert entete.evenement is None

    assert entete.E_NUM_INTERNE == "004517"
    assert entete.E_DATE_TICKET == date(2023, 1, 2)
    assert entete.E_HEURE_TICKET == "11:25"
    assert entete.E_NUM_TICKET == "003562"

    assert entete.E_HT1 == Decimal("249.17")
    assert entete.E_HT2 is None
    assert entete.E_HT3 is None
    assert entete.E_HT4 is None

    assert entete.E_TVA1 == Decimal("49.83")
    assert entete.E_TVA2 is None
    assert entete.E_TVA3 is None
    assert entete.E_TVA4 is None

    assert entete.E_TTC == Decimal("299.00")

    assert entete.E_MDP_CB == Decimal("299.00")
    assert entete.E_MDP_ESPECES is None
    assert entete.E_MDP_CHEQUES is None

    assert entete.signature == (
        "SIGNATURE_LIGNE_1\n"
        "SIGNATURE_LIGNE_2"
    )

    assert len(ticket.lignes_articles) == 1

    ligne = ticket.lignes_articles[0]

    assert ligne.D_QUANTITE_ARTICLE == 1
    assert ligne.D_LIBELLE_ARTICLE == "DEPT001"
    assert ligne.D_TAUX_TVA_ARTICLE == "T1"
    assert ligne.D_MONTANT_ARTICLE == Decimal("299.00")

    assert ligne.D_CORRECTION is None
    assert ligne.D_AUTRE_INFO is None


def test_from_raw_data_conserve_deux_articles_identiques_sans_libelle() -> None:
    raw_data = """1-----------------------
REG  03-10-2023 15:05
001344
 1           T1  €329.00
 1           T1  €329.00
HORS TAXE 1 €548.33
TVA 1 €109.67
TOTAL €658.00
CARTES €658.00
FACTURE No. 000847
2-----------------------
SIGNATURE
"""

    ticket = EjTicket.from_raw_data(
        nom_fichier="EJ021123.TXT",
        boutique="MATURIN",
        raw_data=raw_data,
    )

    assert len(ticket.lignes_articles) == 2
    assert [ligne.D_LIBELLE_ARTICLE for ligne in ticket.lignes_articles] == [
        None,
        None,
    ]
    assert [ligne.D_TAUX_TVA_ARTICLE for ligne in ticket.lignes_articles] == [
        "T1",
        "T1",
    ]
    assert [ligne.D_MONTANT_ARTICLE for ligne in ticket.lignes_articles] == [
        Decimal("329.00"),
        Decimal("329.00"),
    ]


def test_from_raw_data_normalise_un_retour_en_montants_negatifs() -> None:
    raw_data = """1-----------------------
_R_F  05-01-2023 12:30
004800
1 DEPT001 T1 €329.00
1 DEPT002 T1 €229.00
CORRECTION -10.00
HORS TAXE 1 €465.00
TVA 1 €93.00
TOTAL €558.00
CARTES €558.00
FACTURE No. 003904
2-----------------------
SIGNATURE
"""

    ticket = EjTicket.from_raw_data(
        nom_fichier="EJ050123.TXT",
        boutique="MASSENA",
        raw_data=raw_data,
    )

    assert ticket.entete.E_HT1 == Decimal("-465.00")
    assert ticket.entete.E_TVA1 == Decimal("-93.00")
    assert ticket.entete.E_TTC == Decimal("-558.00")
    assert ticket.entete.E_MDP_CB == Decimal("-558.00")
    assert [ligne.D_QUANTITE_ARTICLE for ligne in ticket.lignes_articles[:2]] == [1, 1]
    assert [ligne.D_MONTANT_ARTICLE for ligne in ticket.lignes_articles[:2]] == [
        Decimal("-329.00"),
        Decimal("-229.00"),
    ]
    assert ticket.lignes_articles[2].D_CORRECTION == Decimal("-10.00")


def test_from_raw_data_parse_evenement_tiroir() -> None:
    raw_data = """1-----------------------
REG  02-01-2023 11:41
000975
REF./TIROIR .........
2-----------------------
SIGNATURE
"""

    ticket = EjTicket.from_raw_data(
        nom_fichier="EJ020123.TXT",
        boutique="MASSENA",
        raw_data=raw_data,
    )

    assert ticket.entete.type == "REG"
    assert ticket.entete.evenement == "REF./TIROIR"
    assert ticket.entete.E_NUM_INTERNE == "000975"

    assert ticket.entete.E_TTC is None
    assert ticket.entete.E_NUM_TICKET is None

    assert ticket.lignes_articles == []


def test_from_raw_data_refuse_ticket_vide() -> None:
    with pytest.raises(
        ValueError,
        match="Le ticket est vide",
    ):
        EjTicket.from_raw_data(
            nom_fichier="EJ020123.TXT",
            boutique="MASSENA",
            raw_data="",
        )


def test_from_raw_data_refuse_entete_invalide() -> None:
    raw_data = """1-----------------------
NIMPORTE QUOI
004517
"""

    with pytest.raises(
        ValueError,
        match="Entête de ticket invalide",
    ):
        EjTicket.from_raw_data(
            nom_fichier="EJ020123.TXT",
            boutique="MASSENA",
            raw_data=raw_data,
        )


def test_from_raw_data_refuse_une_heure_invalide() -> None:
    raw_data = """1-----------------------
REG  02-01-2023 99:99
004517
"""

    with pytest.raises(
        ValueError,
        match="Heure de ticket invalide",
    ):
        EjTicket.from_raw_data(
            nom_fichier="EJ020123.TXT",
            boutique="MASSENA",
            raw_data=raw_data,
        )


@pytest.mark.parametrize("type_ticket", ["Z", "XZ", "X"])
def test_from_raw_data_conserve_la_signature_des_autres_types(
    type_ticket: str,
) -> None:
    raw_data = f"""1-----------------------
{type_ticket}  02-01-2023 11:25
004517
DONNEE SPECIFIQUE AU TYPE
2-----------------------
SIGNATURE
"""

    ticket = EjTicket.from_raw_data(
        nom_fichier="EJ020123.TXT",
        boutique="MASSENA",
        raw_data=raw_data,
    )

    assert ticket.entete.type == type_ticket
    assert ticket.entete.signature == "SIGNATURE"
    assert ticket.lignes_articles == []


@pytest.mark.parametrize(
    "last_line",
    [
        "HORS TAXE",
        "TOTAL",
        "NON TAXABLE",
        "CORRECTION",
        "1 ARTICLE",
    ],
)
def test_from_raw_data_refuse_un_bloc_tronque(last_line: str) -> None:
    raw_data = f"""1-----------------------
REG  02-01-2023 11:25
004517
{last_line}
"""

    with pytest.raises(ValueError, match="invalide"):
        EjTicket.from_raw_data(
            nom_fichier="EJ020123.TXT",
            boutique="MASSENA",
            raw_data=raw_data,
        )
