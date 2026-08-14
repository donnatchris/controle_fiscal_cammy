from datetime import date
from decimal import Decimal

import pytest

from classes.z import Z, ZHeader, ZLine


def test_z_header_from_raw_parse_un_header_valide():
    raw = (
        '"MODELE          ","                "\n'
        '"MACHINE         ","MC#01   "\n'
        '"RAPPORT         ","FONC FIXES  "\n'
        '"FICHIER         ","FILE101"\n'
        '"MODE            ","ZZ1 "\n'
        '"COMPTEUR Z      ","0061"\n'
        '"DATE            ","31-01-2023"\n'
        '"HEURE           ","18:44"\n'
    )

    header = ZHeader.from_raw(
        nom_fichier="Z310123.csv",
        raw=raw,
    )

    assert header.nom_fichier == "Z310123.csv"
    assert header.E_MODELE == ""
    assert header.E_MACHINE == "MC#01"
    assert header.E_RAPPORT == "FONC FIXES"
    assert header.E_FICHIER == "FILE101"
    assert header.E_MODE == "ZZ1"
    assert header.E_COMPTEUR_Z == "0061"
    assert header.E_DATE == date(2023, 1, 31)
    assert header.E_HEURE == "18:44"


def test_z_header_from_raw_refuse_un_header_trop_court():
    raw = (
        '"MODELE",""\n'
        '"MACHINE","MC#01"\n'
    )

    with pytest.raises(
        ValueError,
        match="Le header doit contenir au moins 8 lignes",
    ):
        ZHeader.from_raw(
            nom_fichier="Z310123.csv",
            raw=raw,
        )


def test_z_header_from_raw_refuse_une_ligne_avec_mauvais_nombre_de_tokens():
    raw = (
        '"MODELE",""\n'
        '"MACHINE","MC#01","TOKEN_EN_TROP"\n'
        '"RAPPORT","FONC FIXES"\n'
        '"FICHIER","FILE101"\n'
        '"MODE","ZZ1"\n'
        '"COMPTEUR Z","0061"\n'
        '"DATE","31-01-2023"\n'
        '"HEURE","18:44"\n'
    )

    with pytest.raises(
        ValueError,
        match="ne contient pas exactement 2 tokens",
    ):
        ZHeader.from_raw(
            nom_fichier="Z310123.csv",
            raw=raw,
        )


def test_z_header_from_raw_refuse_une_cle_inattendue():
    raw = (
        '"MODELE",""\n'
        '"MAUVAISE_CLE","MC#01"\n'
        '"RAPPORT","FONC FIXES"\n'
        '"FICHIER","FILE101"\n'
        '"MODE","ZZ1"\n'
        '"COMPTEUR Z","0061"\n'
        '"DATE","31-01-2023"\n'
        '"HEURE","18:44"\n'
    )

    with pytest.raises(
        ValueError,
        match="clé attendue 'MACHINE'",
    ):
        ZHeader.from_raw(
            nom_fichier="Z310123.csv",
            raw=raw,
        )


def test_z_header_from_raw_refuse_une_date_invalide():
    raw = (
        '"MODELE",""\n'
        '"MACHINE","MC#01"\n'
        '"RAPPORT","FONC FIXES"\n'
        '"FICHIER","FILE101"\n'
        '"MODE","ZZ1"\n'
        '"COMPTEUR Z","0061"\n'
        '"DATE","31/01/2023"\n'
        '"HEURE","18:44"\n'
    )

    with pytest.raises(ValueError):
        ZHeader.from_raw(
            nom_fichier="Z310123.csv",
            raw=raw,
        )


def test_z_line_from_row_parse_une_ligne_valide():
    row = [
        "0001",
        "CA BRUT     ",
        "294",
        "76,369.80",
    ]

    ligne = ZLine.from_row(row)

    assert ligne.D_ENREGISTREMENT == "0001"
    assert ligne.D_DESIGNATION == "CA BRUT"
    assert ligne.D_QUANTITE == 294
    assert ligne.D_MONTANT == Decimal("76369.80")


def test_z_line_from_row_refuse_une_ligne_avec_mauvais_nombre_de_colonnes():
    row = [
        "0001",
        "CA BRUT",
        "294",
    ]

    with pytest.raises(
        ValueError,
        match="exactement 4 colonnes",
    ):
        ZLine.from_row(row)


def test_z_line_from_row_refuse_une_quantite_non_numerique():
    row = [
        "0001",
        "CA BRUT",
        "abc",
        "76,369.80",
    ]

    with pytest.raises(ValueError):
        ZLine.from_row(row)


def test_z_from_raw_parse_un_fichier_complet():
    raw = (
        '"MODELE          ","                "\n'
        '"MACHINE         ","MC#01   "\n'
        '"RAPPORT         ","FONC FIXES  "\n'
        '"FICHIER         ","FILE101"\n'
        '"MODE            ","ZZ1 "\n'
        '"COMPTEUR Z      ","0061"\n'
        '"DATE            ","31-01-2023"\n'
        '"HEURE           ","18:44"\n'
        "\n"
        '"ENREGISTREMENT  ","DESIGNATION     ","QUANTITE/No     ","MONTANT         "\n'
        '"0001","CA BRUT","294","76,369.80"\n'
        '"0002","CA NET","121","76,369.80"\n'
        '"0003","ESP.TIROIR","0","54,942.80"\n'
    )

    z = Z.from_raw(
        boutique="MASSENA",
        nom_fichier="Z310123.csv",
        raw=raw,
    )

    assert z.boutique == "MASSENA"

    assert z.header.nom_fichier == "Z310123.csv"
    assert z.header.E_MACHINE == "MC#01"
    assert z.header.E_DATE == date(2023, 1, 31)

    assert len(z.lines) == 3

    assert z.lines[0].D_ENREGISTREMENT == "0001"
    assert z.lines[0].D_DESIGNATION == "CA BRUT"
    assert z.lines[0].D_QUANTITE == 294
    assert z.lines[0].D_MONTANT == Decimal("76369.80")

    assert z.lines[2].D_DESIGNATION == "ESP.TIROIR"
    assert z.lines[2].D_MONTANT == Decimal("54942.80")


def test_z_from_raw_refuse_des_colonnes_csv_inattendues():
    raw = (
        '"MODELE",""\n'
        '"MACHINE","MC#01"\n'
        '"RAPPORT","FONC FIXES"\n'
        '"FICHIER","FILE101"\n'
        '"MODE","ZZ1"\n'
        '"COMPTEUR Z","0061"\n'
        '"DATE","31-01-2023"\n'
        '"HEURE","18:44"\n'
        "\n"
        '"ENREGISTREMENT","MAUVAISE_COLONNE","QUANTITE/No","MONTANT"\n'
        '"0001","CA BRUT","294","76,369.80"\n'
    )

    with pytest.raises(
        ValueError,
        match="Les colonnes ne correspondent pas",
    ):
        Z.from_raw(
            boutique="MASSENA",
            nom_fichier="Z310123.csv",
            raw=raw,
        )


def test_z_from_raw_accepte_les_montants_contenant_une_virgule():
    raw = (
        '"MODELE",""\n'
        '"MACHINE","MC#01"\n'
        '"RAPPORT","FONC FIXES"\n'
        '"FICHIER","FILE101"\n'
        '"MODE","ZZ1"\n'
        '"COMPTEUR Z","0061"\n'
        '"DATE","31-01-2023"\n'
        '"HEURE","18:44"\n'
        "\n"
        '"ENREGISTREMENT","DESIGNATION","QUANTITE/No","MONTANT"\n'
        '"0001","CA BRUT","294","76,369.80"\n'
    )

    z = Z.from_raw(
        boutique="MASSENA",
        nom_fichier="Z310123.csv",
        raw=raw,
    )

    assert z.lines[0].D_MONTANT == Decimal("76369.80")
