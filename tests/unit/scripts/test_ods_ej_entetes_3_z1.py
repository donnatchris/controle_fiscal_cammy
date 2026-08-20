from decimal import Decimal
from types import SimpleNamespace

import pytest

from scripts import compare_2
from shared.constantes import FeuilleZ1SyntheseMois


ENTETES_Z1 = (
    "AJ_Année_Z",
    "AJ_Mois_Z",
    "CA NET",
    "HORS TAXES 1",
    "TVA 1",
)
ENTETES_EJ = (
    "AJ_ANNEE",
    "AJ_MOIS",
    "Somme - E_TTC",
    "Somme - AJ_TOTAL_HT",
    "Somme - AJ_TOTAL_TVA_20",
)


def test_modes_et_noms_exacts_des_six_feuilles() -> None:
    assert compare_2.MODE_Z1_PAR_BOUTIQUE == {
        "MASSENA": "ZZ1",
        "MATURIN": "Z",
    }
    assert {
        compare_2._nom_feuille_comparaison_z1_ej(boutique, annee)
        for boutique in ("MASSENA", "MATURIN")
        for annee in (2023, 2024, 2025)
    } == {
        "Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2023",
        "Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2024",
        "Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2025",
        "Compare_Montant_MATURIN_Z1ModeZvsEJ_2023",
        "Compare_Montant_MATURIN_Z1ModeZvsEJ_2024",
        "Compare_Montant_MATURIN_Z1ModeZvsEJ_2025",
    }
    assert compare_2._nom_feuille_z1("MASSENA", 2024).endswith("ModeZZ1")
    assert compare_2._nom_feuille_z1("MATURIN", 2024).endswith("ModeZ")


def test_noms_des_six_classeurs_z1_ej_sont_les_noms_des_feuilles() -> None:
    assert {
        f"{compare_2._nom_feuille_comparaison_z1_ej(boutique, annee)}.ods"
        for boutique in ("MASSENA", "MATURIN")
        for annee in (2023, 2024, 2025)
    } == {
        *(f"Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_{annee}.ods" for annee in (2023, 2024, 2025)),
        *(f"Compare_Montant_MATURIN_Z1ModeZvsEJ_{annee}.ods" for annee in (2023, 2024, 2025)),
    }


def test_comparaison_joint_exactement_annee_mois_trie_et_repete_annee() -> None:
    z1 = (
        ENTETES_Z1,
        (2024, "2024-02", "120.00", "100.00", "20.00"),
        (2024, "2024-01", "60.00", "50.00", "10.00"),
        (2023, "2024-01", "999", "999", "999"),
    )
    ej = (
        ENTETES_EJ,
        (2024, "2024-01", "60.00", "49.00", "11.00"),
        (2024, "2024-02", "119.00", "101.00", "19.00"),
    )

    resultat = compare_2.comparer_montants_mensuels_z1_ej(z1, ej, 2024)

    assert resultat.lignes == (
        ("2024", "2024-01", Decimal("0.00"), Decimal("1.00"), Decimal("-1.00")),
        ("2024", "2024-02", Decimal("1.00"), Decimal("-1.00"), Decimal("1.00")),
    )
    assert all(ligne[0] == "2024" for ligne in resultat.lignes)


def test_comparaison_conserve_negatifs_et_produit_un_ecart_nul_exact() -> None:
    resultat = compare_2.comparer_montants_mensuels_z1_ej(
        (ENTETES_Z1, (2025, "2025-01", "-120.10", "-100.10", "-20.00")),
        (ENTETES_EJ, (2025, "2025-01", "-120.10", "-101.10", "-19.00")),
        2025,
    )

    assert resultat.lignes == (
        ("2025", "2025-01", Decimal("0.00"), Decimal("1.00"), Decimal("-1.00")),
    )


@pytest.mark.parametrize("source", ["z1", "ej"])
def test_comparaison_refuse_les_periodes_dupliquees(source: str) -> None:
    z1 = (ENTETES_Z1, (2024, "2024-01", 12, 10, 2))
    ej = (ENTETES_EJ, (2024, "2024-01", 12, 10, 2))
    if source == "z1":
        z1 = (*z1, z1[-1])
    else:
        ej = (*ej, ej[-1])

    with pytest.raises(ValueError, match="Période dupliquée"):
        compare_2.comparer_montants_mensuels_z1_ej(z1, ej, 2024)


def test_mois_absents_sont_conserves_avec_ecarts_vides_et_controles() -> None:
    resultat = compare_2.comparer_montants_mensuels_z1_ej(
        (
            ENTETES_Z1,
            (2023, "2023-01", 12, 10, 2),
            (2023, "2023-03", 36, 30, 6),
        ),
        (
            ENTETES_EJ,
            (2023, "2023-01", 12, 10, 2),
            (2023, "2023-02", 24, 20, 4),
        ),
        2023,
    )

    assert resultat.lignes == (
        ("2023", "2023-01", Decimal("0"), Decimal("0"), Decimal("0")),
        ("2023", "2023-02", "", "", ""),
        ("2023", "2023-03", "", "", ""),
    )
    assert resultat.periodes_absentes_z1 == (("2023", "2023-02"),)
    assert resultat.periodes_absentes_ej == (("2023", "2023-03"),)


def test_ajouter_feuille_ecrit_cinq_colonnes_en_valeurs_sans_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ecritures: list[tuple[tuple[object, ...], ...]] = []

    class Plage:
        CharWeight = 0
        NumberFormat = 0

        def setDataArray(self, valeurs):
            ecritures.append(valeurs)

    destination = SimpleNamespace(
        nom="Feuille1",
        setName=lambda nom: setattr(destination, "nom", nom),
        getCellRangeByPosition=lambda *_: Plage(),
    )

    feuilles_ej = SimpleNamespace(getByName=lambda _: object())
    feuilles_z1 = SimpleNamespace(getByName=lambda _: object())
    document_destination = SimpleNamespace(
        getSheets=lambda: SimpleNamespace(getByIndex=lambda _: destination),
        getNumberFormats=lambda: object(),
    )
    document_ej = SimpleNamespace(getSheets=lambda: feuilles_ej)
    document_z1 = SimpleNamespace(getSheets=lambda: feuilles_z1)
    resultat = compare_2.ResultatComparaisonZ1Ej(
        lignes=(("2024", "2024-01", Decimal("0"), Decimal("1.25"), Decimal("-1.25")),),
        periodes_absentes_z1=(),
        periodes_absentes_ej=(),
    )
    monkeypatch.setattr(
        compare_2,
        "comparer_montants_mensuels_z1_ej",
        lambda *_: resultat,
    )
    monkeypatch.setattr(compare_2, "_donnees_utilisees", lambda _: ())
    monkeypatch.setattr(compare_2, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(compare_2, "definir_largeur_colonnes", lambda *_: None)

    compare_2.ajouter_feuille_comparaison_z1_ej(
        document_destination, document_ej, document_z1, "MASSENA", 2024
    )

    assert destination.nom == "Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2024"
    assert ecritures == [
        (compare_2.COLONNES_COMPARAISON_Z1_EJ,),
        (("2024", "2024-01", 0.0, 1.25, -1.25),),
    ]
    assert compare_2.COLONNES_COMPARAISON_Z1_EJ == (
        "AJ_Année_Z",
        "AJ_Mois_Z",
        "AJ_ECART_CA_TTC",
        "AJ_ECART_HORS_TAXE_1",
        "AJ_ECART_TVA1",
    )
    assert "Observation" not in repr(ecritures)
    assert "=" not in repr(ecritures)


def test_constantes_de_fichiers_ods() -> None:
    assert FeuilleZ1SyntheseMois.FICHIER_ODS.pour("MASSENA", 2023) == (
        "TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods"
    )
    assert FeuilleZ1SyntheseMois.FICHIER_ODS_EJ_ENTETES.pour("MATURIN", 2023) == (
        "TTS_EJ_ENTETES_TICKETS_MATURIN.ods"
    )
