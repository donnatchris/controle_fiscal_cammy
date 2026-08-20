from decimal import Decimal

import pytest

from scripts import recettes_mensuelles


ENTETES = recettes_mensuelles.COLONNES_SOURCE


def test_noms_du_classeur_et_de_la_feuille_respectent_le_cdc() -> None:
    assert recettes_mensuelles.NOM_FICHIER == (
        "recettes_mensuelles_tous_boutique_232425.ods"
    )
    assert recettes_mensuelles.NOM_FEUILLE == (
        "recettes_mensuelles_tous_boutique_232425"
    )


def test_indexer_recettes_normalise_periode_et_conserve_montants_complets() -> None:
    resultat = recettes_mensuelles.indexer_recettes(
        (
            ENTETES,
            (2024.0, "2024-02", 63641.51, 12728.30, 76369.81),
        ),
        "MASSENA",
    )

    assert resultat == {
        (2024, 2): (
            Decimal("63641.51"),
            Decimal("12728.3"),
            Decimal("76369.81"),
        )
    }


def test_indexer_recettes_refuse_une_periode_dupliquee() -> None:
    donnees = (
        ENTETES,
        (2024, "2024-02", 1, 2, 3),
        (2024, "2024-02", 4, 5, 6),
    )

    with pytest.raises(ValueError, match="dupliquée"):
        recettes_mensuelles.indexer_recettes(donnees, "MATURIN")


def test_consolider_recettes_joint_et_trie_les_deux_boutiques() -> None:
    recettes = {
        "MASSENA": {
            (2024, 2): (Decimal("10"), Decimal("2"), Decimal("12")),
            (2023, 12): (Decimal("20"), Decimal("4"), Decimal("24")),
        },
        "MATURIN": {
            (2023, 12): (Decimal("30"), Decimal("6"), Decimal("36")),
            (2024, 2): (Decimal("40"), Decimal("8"), Decimal("48")),
        },
    }

    assert recettes_mensuelles.consolider_recettes(recettes) == (
        (
            2023,
            12,
            Decimal("20"),
            Decimal("4"),
            Decimal("24"),
            Decimal("30"),
            Decimal("6"),
            Decimal("36"),
        ),
        (
            2024,
            2,
            Decimal("10"),
            Decimal("2"),
            Decimal("12"),
            Decimal("40"),
            Decimal("8"),
            Decimal("48"),
        ),
    )


def test_consolider_recettes_refuse_une_periode_absente() -> None:
    recettes = {
        "MASSENA": {(2024, 2): (Decimal("1"),) * 3},
        "MATURIN": {},
    }

    with pytest.raises(ValueError, match="Périodes non concordantes"):
        recettes_mensuelles.consolider_recettes(recettes)


class _Plage:
    def __init__(self) -> None:
        self.data = None
        self.formules = None
        self.CharWeight = None
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


def test_ajouter_feuille_ecrit_des_formules_calc(monkeypatch: pytest.MonkeyPatch) -> None:
    feuille = _Feuille()
    monkeypatch.setattr(recettes_mensuelles, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(recettes_mensuelles, "definir_largeur_colonnes", lambda *_: None)

    recettes_mensuelles.ajouter_feuille(
        _Document(feuille),
        ((2024, 2, *(Decimal(str(valeur)) for valeur in range(1, 7))),),
    )

    assert feuille.nom == recettes_mensuelles.NOM_FEUILLE
    assert feuille.plages[(8, 1, 10, 1)].formules == (
        ("=C2+F2", "=D2+G2", "=E2+H2"),
    )
    assert feuille.plages[(2, 1, 10, 1)].NumberFormat == 42
