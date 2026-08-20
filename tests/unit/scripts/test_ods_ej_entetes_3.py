from types import SimpleNamespace

import pytest

from scripts import compare_2
from scripts.ods_ej_entetes import COLONNES_ENTETES
from scripts.compare_1 import COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT


class FauxChamp:
    def __init__(self) -> None:
        self.proprietes: list[tuple[str, object]] = []

    def setPropertyValue(self, nom: str, valeur: object) -> None:
        self.proprietes.append((nom, valeur))


def test_ajouter_TotalHtTvaTtc_cree_le_datapilot_demande(monkeypatch) -> None:
    adresse_source = SimpleNamespace(
        Sheet=2, StartColumn=0, StartRow=0, EndColumn=21, EndRow=3
    )
    entetes = (*COLONNES_ENTETES, *COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT)
    champs = [FauxChamp() for _ in entetes]

    class FauxDescripteur:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []
            self.disposition = FauxChamp()
            self.source = None

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

        def setSourceRange(self, source: object) -> None:
            self.source = source

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda index: champs[index])

        def getDataLayoutField(self) -> FauxChamp:
            return self.disposition

    descripteur = FauxDescripteur()
    insertions: list[tuple[str, object, object]] = []
    tableaux = SimpleNamespace(
        createDataPilotDescriptor=lambda: descripteur,
        insertNewByName=lambda nom, cellule, desc: insertions.append((nom, cellule, desc)),
    )
    source = SimpleNamespace(
        createCursor=lambda: SimpleNamespace(
            gotoEndOfUsedArea=lambda _: None,
            getRangeAddress=lambda: adresse_source,
        ),
        getCellRangeByPosition=lambda *_: SimpleNamespace(
            getDataArray=lambda: (entetes,)
        ),
    )
    destination = SimpleNamespace(
        getDataPilotTables=lambda: tableaux,
        getCellByPosition=lambda *_: SimpleNamespace(CellAddress="A1"),
    )

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {
                "ENTETES_TICKETS_MASSENA_CplteAnneeMoisTotalHT": source
            }

        def getByName(self, nom: str) -> object:
            return self.feuilles[nom]

        def hasByName(self, nom: str) -> bool:
            return nom in self.feuilles

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = destination

    feuilles = FaussesFeuilles()
    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, valeur: f"{enum}.{valeur}"),
    )
    monkeypatch.setattr(compare_2, "definir_largeur_colonnes", lambda *_: None)

    compare_2.ajouter_TotalHtTvaTtc(
        SimpleNamespace(getSheets=lambda: feuilles), "MASSENA"
    )

    assert descripteur.source == adresse_source
    assert descripteur.proprietes == [
        ("RowGrand", False),
        ("ColumnGrand", False),
        ("ShowFilterButton", False),
    ]
    assert champs[entetes.index("AJ_ANNEE")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
        ("RepeatItemLabels", True),
    ]
    assert champs[entetes.index("AJ_MOIS")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    for nom_champ in compare_2.CHAMPS_DONNEES_TOTAL_HT_TVA_TTC:
        assert champs[entetes.index(nom_champ)].proprietes == [
            ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
            ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
            ("Name", f"Somme - {nom_champ}"),
        ]
    assert descripteur.disposition.proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.COLUMN")
    ]
    assert insertions == [("TD_TotalHtTvaTtc_ParAnneeMois", "A1", descripteur)]


def test_extraire_recettes_du_datapilot_aplatit_repete_et_trie(monkeypatch) -> None:
    donnees = (
        ("", "", "Data", "", "", ""),
        (
            "AJ_ANNEE",
            "AJ_MOIS",
            "",
            "Somme - AJ_TOTAL_HT",
            "Somme - AJ_TOTAL_TVA_20",
            "Somme - E_TTC",
        ),
        ("2024", "2024-02", "", 20.0, 4.0, 24.0),
        ("", "2024-01", "", 10.0, 2.0, 12.0),
    )
    monkeypatch.setattr(compare_2, "_donnees_utilisees", lambda _: donnees)

    assert compare_2.extraire_recettes_du_datapilot(object()) == (
        ("2024", "2024-01", 10.0, 2.0, 12.0),
        ("2024", "2024-02", 20.0, 4.0, 24.0),
    )


def test_extraire_recettes_du_datapilot_refuse_un_montant_non_numerique(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        compare_2,
        "_donnees_utilisees",
        lambda _: (
            compare_2.COLONNES_RECETTES_MENSUELLES,
            ("2024", "2024-01", "12,00", 2.0, 14.0),
        ),
    )

    with pytest.raises(ValueError, match="Montant non numérique"):
        compare_2.extraire_recettes_du_datapilot(object())


def test_ajouter_recettes_mensuelles_ecrit_exactement_les_valeurs_du_tcd(
    monkeypatch,
) -> None:
    lignes = (
        ("2023", "2023-01", 100.0, 20.0, 120.0),
        ("2024", "2024-01", 200.0, 40.0, 240.0),
    )
    ecritures: dict[tuple[int, int, int, int], tuple[tuple[object, ...], ...]] = {}
    formats_demandes: list[str] = []

    class FaussePlage:
        CharWeight = 0
        NumberFormat = 0

        def __init__(self, coordonnees: tuple[int, int, int, int]) -> None:
            self.coordonnees = coordonnees

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            ecritures[self.coordonnees] = valeurs

    destination = SimpleNamespace(
        getCellRangeByPosition=lambda *coordonnees: FaussePlage(coordonnees)
    )

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {"TD_TotalHtTvaTtc_ParAnneeMois": object()}

        def getByName(self, nom: str) -> object:
            return self.feuilles[nom]

        def hasByName(self, nom: str) -> bool:
            return nom in self.feuilles

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = destination

    feuilles = FaussesFeuilles()
    monkeypatch.setattr(
        compare_2, "extraire_recettes_du_datapilot", lambda _: lignes
    )
    monkeypatch.setattr(
        compare_2,
        "obtenir_format",
        lambda _formats, format_chaine: formats_demandes.append(format_chaine) or 42,
    )
    monkeypatch.setattr(compare_2, "definir_largeur_colonnes", lambda *_: None)
    monkeypatch.setattr(
        compare_2,
        "_donnees_utilisees",
        lambda _: (compare_2.COLONNES_RECETTES_MENSUELLES, *lignes),
    )

    compare_2.ajouter_recettes_mensuelles(
        SimpleNamespace(getSheets=lambda: feuilles, getNumberFormats=lambda: object()),
        "MASSENA",
    )

    assert ecritures[(0, 0, 4, 0)] == (
        compare_2.COLONNES_RECETTES_MENSUELLES,
    )
    assert ecritures[(0, 1, 4, 2)] == lignes
    assert formats_demandes == ["0,00"]
    assert "recettes_mensuelles_MASSENA_232425" in feuilles.feuilles


def test_ajouter_feuilles_recettes_enchaine_tcd_puis_copie(monkeypatch) -> None:
    appels: list[tuple[str, str]] = []
    monkeypatch.setattr(
        compare_2,
        "ajouter_TotalHtTvaTtc",
        lambda _, boutique: appels.append(("tcd", boutique)),
    )
    monkeypatch.setattr(
        compare_2,
        "ajouter_recettes_mensuelles",
        lambda _, boutique: appels.append(("recettes", boutique)),
    )

    compare_2.ajouter_feuilles_recettes(object(), "MATURIN")

    assert appels == [("tcd", "MATURIN"), ("recettes", "MATURIN")]


def test_enrichir_classeurs_traite_les_deux_boutiques(tmp_path, monkeypatch) -> None:
    appels: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        compare_2,
        "enrichir_et_enregistrer_classeur",
        lambda _uno, _soffice, destination, *, boutique: appels.append(
            (destination, boutique)
        ),
    )

    resultats = compare_2.enrichir_classeurs(tmp_path, uno=object())

    assert appels == [
        (tmp_path / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods", "MASSENA"),
        (tmp_path / "TTS_EJ_ENTETES_TICKETS_MATURIN.ods", "MATURIN"),
    ]
    assert set(resultats) == {"MASSENA", "MATURIN"}
