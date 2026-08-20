from decimal import Decimal

import pytest

from scripts import compare_ca_gesco_ca3


def test_noms_et_colonnes_respectent_le_cdc() -> None:
    assert compare_ca_gesco_ca3.NOM_FICHIER == "CompareCA_Gesco_CA3.ods"
    assert compare_ca_gesco_ca3.NOM_FEUILLE == "CompareCA_Gesco_CA3"
    assert compare_ca_gesco_ca3.COLONNES_DESTINATION == (
        "AJ_ANNEE",
        "AJ_MOIS",
        "AJ_TOTAL_TOUS_BOUTIQUE_HT",
        "AJ_TOTAL_TOUS_BOUTIQUE_TVA",
        "AJ_TOTAL_TOUS_BOUTIQUE_TTC",
        "MTT_HT_CA3",
        "MTT_HT_20_CA3",
        "MTT_TVA_20_CA3",
        "AJ_ECART_HT20",
        "AJ_ECART_TVA20",
    )


def test_extraire_recettes_reconstituees_trie_et_preserve_les_montants() -> None:
    donnees = (
        compare_ca_gesco_ca3.COLONNES_SOURCE,
        (2024, 2, 63641.51, 12728.30, 76369.81),
        (2023, 12, -100.00, -20.00, -120.00),
    )

    assert compare_ca_gesco_ca3.extraire_recettes_reconstituees(donnees) == (
        (
            2023,
            12,
            Decimal("-100.0"),
            Decimal("-20.0"),
            Decimal("-120.0"),
        ),
        (
            2024,
            2,
            Decimal("63641.51"),
            Decimal("12728.3"),
            Decimal("76369.81"),
        ),
    )


def test_extraire_recettes_reconstituees_refuse_un_doublon() -> None:
    donnees = (
        compare_ca_gesco_ca3.COLONNES_SOURCE,
        (2024, 2, 1, 2, 3),
        (2024, 2, 4, 5, 6),
    )

    with pytest.raises(ValueError, match="dupliquée"):
        compare_ca_gesco_ca3.extraire_recettes_reconstituees(donnees)


class _Plage:
    def __init__(self) -> None:
        self.data = None
        self.formules = None
        self.CharWeight = None
        self.IsTextWrapped = None
        self.NumberFormat = None

    def setDataArray(self, data: object) -> None:
        self.data = data

    def setFormulaArray(self, formules: object) -> None:
        self.formules = formules


class _Feuille:
    def __init__(self) -> None:
        self.nom = "Sheet1"
        self.plages: dict[tuple[int, int, int, int], _Plage] = {}

    def setName(self, nom: str) -> None:
        self.nom = nom

    def getCellRangeByPosition(self, *position: int) -> _Plage:
        return self.plages.setdefault(position, _Plage())


class _Feuilles:
    def __init__(self, feuille: _Feuille) -> None:
        self.feuille = feuille

    def getByIndex(self, _: int) -> _Feuille:
        return self.feuille


class _Document:
    def __init__(self, feuille: _Feuille) -> None:
        self.feuilles = _Feuilles(feuille)

    def getSheets(self) -> _Feuilles:
        return self.feuilles

    def getNumberFormats(self) -> object:
        return object()


def test_ajouter_feuille_laisse_ca3_vides_et_ecrit_formules_conditionnelles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feuille = _Feuille()
    monkeypatch.setattr(compare_ca_gesco_ca3, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(
        compare_ca_gesco_ca3, "definir_largeur_colonnes", lambda *_: None
    )

    compare_ca_gesco_ca3.ajouter_feuille(
        _Document(feuille),
        ((2024, 2, Decimal("100"), Decimal("20"), Decimal("120")),),
    )

    assert feuille.nom == "CompareCA_Gesco_CA3"
    assert feuille.plages[(0, 1, 4, 1)].data == (
        (2024, 2, 100.0, 20.0, 120.0),
    )
    assert (5, 1, 7, 1) not in feuille.plages
    assert feuille.plages[(8, 1, 9, 1)].formules == (
        ('=IF(G2="";"";C2-G2)', '=IF(H2="";"";D2-H2)'),
    )
    assert feuille.plages[(2, 1, 9, 1)].NumberFormat == 42
