from types import SimpleNamespace

import pytest

from scripts import ods_ej_entetes_enrichi
from scripts.ods_ej_entetes import COLONNES_ENTETES


def test_ajouter_CplteAnneeMoisTotal_copie_la_feuille_triee_et_ajoute_les_colonnes(
    monkeypatch,
) -> None:
    copies: list[tuple[str, str]] = []

    class FaussePlage:
        def __init__(self, coordonnees: tuple[int, int, int, int]) -> None:
            self.coordonnees = coordonnees
            self.CharWeight = 0
            self.NumberFormat = 0

        def getDataArray(self) -> tuple[tuple[object, ...], ...]:
            return (COLONNES_ENTETES,)

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            if self.coordonnees == (18, 0, 21, 0):
                entetes.extend(valeurs)
            else:
                periodes.extend(valeurs)

        def setFormulaArray(self, valeurs: tuple[tuple[str, ...], ...]) -> None:
            formules.extend(valeurs)

    class FausseFeuille:
        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(EndColumn=17, EndRow=2),
            )

        def getCellRangeByPosition(self, *coordonnees: int) -> FaussePlage:
            appels.append(coordonnees)
            return FaussePlage(coordonnees)

        def getCellByPosition(self, colonne: int, ligne: int) -> SimpleNamespace:
            assert colonne == 3
            return dates[ligne]

    feuille = FausseFeuille()
    appels: list[tuple[int, int, int, int]] = []
    entetes: list[tuple[object, ...]] = []
    formules: list[tuple[str, ...]] = []
    periodes: list[tuple[object, ...]] = []
    dates = {
        1: SimpleNamespace(String="2024-01-01", Value=45292),
        2: SimpleNamespace(String="", Value=0),
    }
    monkeypatch.setattr(
        ods_ej_entetes_enrichi,
        "copier_feuille",
        lambda _document, source, destination: copies.append((source, destination)) or feuille,
    )
    monkeypatch.setattr(ods_ej_entetes_enrichi, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(ods_ej_entetes_enrichi, "definir_largeur_colonnes", lambda *_: None)

    ods_ej_entetes_enrichi.ajouter_CplteAnneeMoisTotal(
        SimpleNamespace(getNumberFormats=lambda: object()), "MASSENA"
    )

    assert copies == [(
        "ENTETES_TICKETS_MASSENA_TriCrstNumInterne",
        "ENTETES_TICKETS_MASSENA_CplteAnneeMoisTotalHT",
    )]
    assert entetes == [(
        "AJ_TOTAL_HT", "AJ_TOTAL_TVA_20", "AJ_ANNEE", "AJ_MOIS",
    )]
    assert formules == [
        (
            "=SUM(F2:I2;N2)",
            "=J2",
        ),
        (
            "=SUM(F3:I3;N3)",
            "=J3",
        ),
    ]
    assert periodes == [("2024", "2024-01"), ("", "")]
    assert appels == [
        (0, 0, 17, 0),
        (18, 0, 21, 0),
        (18, 1, 19, 2),
        (20, 1, 21, 2),
        (18, 1, 19, 2),
    ]


def test_ajouter_CplteAnneeMoisTotal_refuse_une_feuille_source_incomplete(
    monkeypatch,
) -> None:
    class FausseFeuille:
        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(EndColumn=0, EndRow=0),
            )

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(getDataArray=lambda: (("E_HT1",),))

    monkeypatch.setattr(ods_ej_entetes_enrichi, "copier_feuille", lambda *_: FausseFeuille())

    with pytest.raises(ValueError, match="E_DATE_TICKET"):
        ods_ej_entetes_enrichi.ajouter_CplteAnneeMoisTotal(object(), "MASSENA")


def test_ajouter_TotalEnctTtc_cree_un_datapilot_par_annee_et_mois(
    monkeypatch,
) -> None:
    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(Sheet=2, StartColumn=0, StartRow=0, EndColumn=21, EndRow=3)

    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxDescripteur:
        def __init__(self, champs: list[FauxChamp]) -> None:
            self.champs = champs
            self.proprietes: list[tuple[str, object]] = []
            self.source: object | None = None

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

        def setSourceRange(self, source: object) -> None:
            self.source = source

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda index: self.champs[index])

    class FauxTableaux:
        def __init__(self, descripteur: FauxDescripteur) -> None:
            self.descripteur = descripteur
            self.insertions: list[tuple[str, object, object]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def insertNewByName(self, nom: str, adresse: object, descripteur: object) -> None:
            self.insertions.append((nom, adresse, descripteur))

    class FausseFeuilleSource:
        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(getDataArray=lambda: ((
                *COLONNES_ENTETES,
                *ods_ej_entetes_enrichi.COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT,
            ),))

    class FausseFeuilleDestination:
        def __init__(self, tableaux: FauxTableaux) -> None:
            self.tableaux = tableaux

        def getDataPilotTables(self) -> FauxTableaux:
            return self.tableaux

        def getCellByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    champs = [FauxChamp() for _ in range(22)]
    descripteur = FauxDescripteur(champs)
    destination = FausseFeuilleDestination(FauxTableaux(descripteur))
    source = FausseFeuilleSource()

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {
                "ENTETES_TICKETS_MASSENA_CplteAnneeMoisTotalHT": source,
            }

        def getByName(self, nom: str) -> object:
            return self.feuilles[nom]

        def hasByName(self, _: str) -> bool:
            return False

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
    monkeypatch.setattr(ods_ej_entetes_enrichi, "definir_largeur_colonnes", lambda *_: None)

    ods_ej_entetes_enrichi.ajouter_TotalEnctTtc(
        SimpleNamespace(getSheets=lambda: feuilles), "MASSENA"
    )

    assert descripteur.source == SimpleNamespace(
        Sheet=2, StartColumn=0, StartRow=0, EndColumn=21, EndRow=3
    )
    assert descripteur.proprietes == [
        ("RowGrand", False), ("ColumnGrand", False), ("ShowFilterButton", False),
    ]
    assert champs[20].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    assert champs[21].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    for nom_champ in ods_ej_entetes_enrichi.CHAMPS_DONNEES_TOTAL_ENCT_TTC:
        champ = champs[COLONNES_ENTETES.index(nom_champ)]
        assert champ.proprietes == [
            ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
            ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
            ("Name", f"Somme - {nom_champ}"),
        ]
    indexes_configures = {
        20,
        21,
        *(COLONNES_ENTETES.index(nom) for nom in ods_ej_entetes_enrichi.CHAMPS_DONNEES_TOTAL_ENCT_TTC),
    }
    assert all(
        not champ.proprietes
        for index, champ in enumerate(champs)
        if index not in indexes_configures
    )
    assert destination.tableaux.insertions == [
        ("TD_TotalEnctTtc_ParAnneeMois", "A1", descripteur)
    ]


def test_extraire_encts_mensuels_tcd_aplatit_les_quatre_sommes_par_mois() -> None:
    donnees_tcd = (
        ("AJ_ANNEE", "AJ_MOIS", "Data", "Résultat"),
        ("2024", "2024-01", "Somme - E_TTC", 120.0),
        ("", "", "Somme - E_MDP_CB", 100.0),
        ("", "", "Somme - E_MDP_CHEQUES", ""),
        ("", "", "Somme - E_MDP_ESPECES", 20.0),
        ("", "2024-02", "Somme - E_TTC", 60.0),
        ("", "", "Somme - E_MDP_CB", 50.0),
        ("", "", "Somme - E_MDP_CHEQUES", 10.0),
        ("", "", "Somme - E_MDP_ESPECES", ""),
        ("Résultat", "", "", 180.0),
    )

    assert ods_ej_entetes_enrichi.extraire_encts_mensuels_tcd(donnees_tcd) == (
        ("2024", "2024-01", 120.0, 100.0, 0.0, 20.0),
        ("2024", "2024-02", 60.0, 50.0, 10.0, 0.0),
    )


def test_ajouter_encts_mensuels_cree_une_feuille_de_valeurs_aplatie(monkeypatch) -> None:
    donnees_tcd = (
        ("AJ_ANNEE", "AJ_MOIS", "Data", "Résultat"),
        ("2024", "2024-01", "Somme - E_TTC", 120.0),
        ("", "", "Somme - E_MDP_CB", 100.0),
        ("", "", "Somme - E_MDP_CHEQUES", 0.0),
        ("", "", "Somme - E_MDP_ESPECES", 20.0),
    )
    ecritures: list[tuple[int, int, int, int, tuple[tuple[object, ...], ...]]] = []

    class FaussePlage:
        CharWeight = 0
        NumberFormat = 0

        def getDataArray(self) -> tuple[tuple[object, ...], ...]:
            return donnees_tcd

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            ecritures.append((*coordonnees_courantes, valeurs))

    class FausseFeuille:
        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(StartColumn=0, StartRow=0, EndColumn=3, EndRow=4),
            )

        def getCellRangeByPosition(self, *coordonnees: int) -> FaussePlage:
            nonlocal coordonnees_courantes
            coordonnees_courantes = coordonnees
            return FaussePlage()

    source = FausseFeuille()
    destination = FausseFeuille()
    coordonnees_courantes = (0, 0, 0, 0)

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {"TD_TotalEnctTtc_ParAnneeMois": source}

        def getByName(self, nom: str) -> FausseFeuille:
            return self.feuilles[nom]

        def hasByName(self, _: str) -> bool:
            return False

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = destination

    monkeypatch.setattr(ods_ej_entetes_enrichi, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(ods_ej_entetes_enrichi, "definir_largeur_colonnes", lambda *_: None)
    ods_ej_entetes_enrichi.ajouter_encts_mensuels(
        SimpleNamespace(getSheets=lambda: FaussesFeuilles(), getNumberFormats=lambda: object()),
        "MASSENA",
    )

    assert ecritures == [
        (0, 0, 5, 0, (ods_ej_entetes_enrichi.COLONNES_ENCTS_MENSUELS,)),
        (0, 1, 5, 1, (("2024", "2024-01", 120.0, 100.0, 0.0, 20.0),)),
    ]


def test_enrichir_classeurs_applique_l_enrichissement_aux_deux_boutiques(
    tmp_path, monkeypatch
) -> None:
    appels: list[tuple[object, str, Path, str]] = []
    monkeypatch.setattr(
        ods_ej_entetes_enrichi,
        "enrichir_et_enregistrer_classeur",
        lambda uno, soffice, destination, *, boutique: appels.append(
            (uno, soffice, destination, boutique)
        ),
    )

    resultats = ods_ej_entetes_enrichi.enrichir_classeurs(tmp_path, uno=object())

    assert [appel[2].name for appel in appels] == [
        "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        "TTS_EJ_ENTETES_TICKETS_MATURIN.ods",
    ]
    assert [appel[3] for appel in appels] == ["MASSENA", "MATURIN"]
    assert resultats == {
        "MASSENA": tmp_path / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        "MATURIN": tmp_path / "TTS_EJ_ENTETES_TICKETS_MATURIN.ods",
    }
