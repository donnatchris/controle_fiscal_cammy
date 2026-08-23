from types import SimpleNamespace

import pytest

from scripts import compare_1
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
    formats_demandes: list[str] = []
    dates = {
        1: SimpleNamespace(String="2024-01-01", Value=45292),
        2: SimpleNamespace(String="", Value=0),
    }
    monkeypatch.setattr(
        compare_1,
        "copier_feuille",
        lambda _document, source, destination: copies.append((source, destination)) or feuille,
    )
    monkeypatch.setattr(
        compare_1,
        "obtenir_format",
        lambda _formats, format_chaine: formats_demandes.append(format_chaine) or 42,
    )
    monkeypatch.setattr(compare_1, "definir_largeur_colonnes", lambda *_: None)

    compare_1.ajouter_CplteAnneeMoisTotal(
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
    assert formats_demandes == ["0,00"]
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

    monkeypatch.setattr(compare_1, "copier_feuille", lambda *_: FausseFeuille())

    with pytest.raises(ValueError, match="E_DATE_TICKET"):
        compare_1.ajouter_CplteAnneeMoisTotal(object(), "MASSENA")


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
            self.champ_disposition_donnees = FauxChamp()
            self.proprietes: list[tuple[str, object]] = []
            self.source: object | None = None

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

        def setSourceRange(self, source: object) -> None:
            self.source = source

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda index: self.champs[index])

        def getDataLayoutField(self) -> FauxChamp:
            return self.champ_disposition_donnees

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
                *compare_1.COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT,
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
    monkeypatch.setattr(compare_1, "definir_largeur_colonnes", lambda *_: None)

    compare_1.ajouter_TotalEnctTtc(
        SimpleNamespace(getSheets=lambda: feuilles), "MASSENA"
    )

    assert descripteur.source == SimpleNamespace(
        Sheet=2, StartColumn=0, StartRow=0, EndColumn=21, EndRow=3
    )
    assert descripteur.proprietes == [
        ("RowGrand", False), ("ColumnGrand", False), ("ShowFilterButton", False),
    ]
    assert champs[20].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
        ("RepeatItemLabels", True),
    ]
    assert champs[21].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    for nom_champ in compare_1.CHAMPS_DONNEES_TOTAL_ENCT_TTC:
        champ = champs[COLONNES_ENTETES.index(nom_champ)]
        assert champ.proprietes == [
            ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
            ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
            ("Name", f"Somme - {nom_champ}"),
        ]
    assert descripteur.champ_disposition_donnees.proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.COLUMN")
    ]
    indexes_configures = {
        20,
        21,
        *(COLONNES_ENTETES.index(nom) for nom in compare_1.CHAMPS_DONNEES_TOTAL_ENCT_TTC),
    }
    assert all(
        not champ.proprietes
        for index, champ in enumerate(champs)
        if index not in indexes_configures
    )
    assert destination.tableaux.insertions == [
        ("TD_TotalEnctTtc_ParAnneeMois", "A1", descripteur)
    ]


def test_ajouter_encts_mensuels_copie_les_valeurs_du_tcd(monkeypatch) -> None:
    class FausseCellule:
        def __init__(self) -> None:
            self.String = ""

    class FausseFeuille:
        def __init__(self) -> None:
            self.cellules: dict[tuple[int, int], FausseCellule] = {}
            self.lignes_supprimees: list[tuple[int, int]] = []

        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(StartColumn=0, StartRow=0, EndColumn=5, EndRow=1),
            )

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(getDataArray=lambda: (
                ("", "", "Data", "", "", ""),
                ("AJ_ANNEE", "AJ_MOIS", "", "Somme - E_TTC", "Somme - E_MDP_CB", "Somme - E_MDP_CHEQUES"),
                ("2024", "2024-01", "", 120.0, 100.0, 0.0),
            ))

        def getCellByPosition(self, colonne: int, ligne: int) -> FausseCellule:
            return self.cellules.setdefault((colonne, ligne), FausseCellule())

        def getRows(self) -> SimpleNamespace:
            return SimpleNamespace(
                removeByIndex=lambda index, nombre: self.lignes_supprimees.append((index, nombre))
            )

    destination = FausseFeuille()
    copies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        compare_1,
        "copier_valeurs_feuille",
        lambda _document, source, cible: copies.append((source, cible)) or destination,
    )
    monkeypatch.setattr(compare_1, "definir_largeur_colonnes", lambda *_: None)

    compare_1.ajouter_encts_mensuels(object(), "MASSENA")

    assert copies == [
        ("TD_TotalEnctTtc_ParAnneeMois", "enct_mensuels_MASSENA_232425")
    ]
    assert destination.getCellByPosition(2, 0).String == ""
    assert destination.lignes_supprimees == [(0, 1)]


def test_comparer_z2_mode_retenu_et_ej_par_periode_laisse_vides_les_sources_absentes() -> None:
    lignes_z2 = (
        {
            "AJ_Année_Z": 2024.0,
            "AJ_Mois_Z": "2024-02",
            "CARTES_D_MONTANT": 100.0,
            "CHEQUES_D_MONTANT": 20.0,
            "ESPECES_D_MONTANT": 30.0,
        },
        {
            "AJ_Année_Z": 2023.0,
            "AJ_Mois_Z": "2023-12",
            "CARTES_D_MONTANT": 999.0,
        },
        {
            "AJ_Année_Z": 2024.0,
            "AJ_Mois_Z": "2024-03",
            "CARTES_D_MONTANT": 5.0,
        },
    )
    lignes_ej = (
        {
            "AJ_ANNEE": "2024",
            "AJ_MOIS": "2024-01",
            "Somme - E_MDP_CB": 10.0,
            "Somme - E_MDP_CHEQUES": 2.0,
            "Somme - E_MDP_ESPECES": 3.0,
        },
        {
            "AJ_ANNEE": "2024",
            "AJ_MOIS": "2024-02",
            "Somme - E_MDP_CB": 40.0,
            "Somme - E_MDP_CHEQUES": "",
            "Somme - E_MDP_ESPECES": 45.0,
        },
    )

    assert compare_1.comparer_z2_mode_retenu_et_ej_par_periode(
        lignes_z2, lignes_ej, 2024
    ) == (
        (2024.0, "2024-01", "", "", "", "", "", ""),
        (2024.0, "2024-02", "", 60.0, "", 20.0, "", -15.0),
        (2024.0, "2024-03", "", "", "", "", "", ""),
    )


@pytest.mark.parametrize(
    ("boutique", "mode", "nom_attendu"),
    [
        ("MASSENA", "ZZ1", "Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2024"),
        ("MATURIN", "Z", "Compare_Montant_MATURIN_Z2ModeZVsEJ_2024"),
    ],
)
def test_ajouter_comparaison_z2_ej_ecrit_une_feuille_autonome(
    monkeypatch, boutique: str, mode: str, nom_attendu: str
) -> None:
    ecritures: list[tuple[tuple[object, ...], ...]] = []
    assert compare_1.COLONNES_COMPARE_MONTANT_Z2_EJ == (
        "AJ_Année_Z",
        "AJ_Mois_Z",
        "CARTES_AJ_ECART_QTE",
        "CARTES_AJ_ECART_MONTANT",
        "CHEQUES_AJ_ECART_QTE",
        "CHEQUES_AJ_ECART_MONTANT",
        "ESPECES_AJ_ECART_QTE",
        "ESPECES_AJ_ECART_MONTANT",
    )

    class FaussePlage:
        CharWeight = 0
        NumberFormat = 0

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            ecritures.append(valeurs)

    class FausseFeuille:
        nom = "Feuille1"

        def setName(self, nom: str) -> None:
            self.nom = nom

        def getCellRangeByPosition(self, *_: int) -> FaussePlage:
            return FaussePlage()

    destination = FausseFeuille()

    feuilles_ej = SimpleNamespace(
        getByName=lambda nom: object()
        if nom == f"enct_mensuels_{boutique}_232425"
        else pytest.fail(f"Feuille EJ inattendue : {nom}")
    )
    nom_source = (
        f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_Mode{mode}"
    )
    feuilles_z2 = SimpleNamespace(
        hasByName=lambda nom: nom == nom_source,
        getByName=lambda nom: object()
        if nom == nom_source
        else pytest.fail(f"Feuille Z2 inattendue : {nom}")
    )
    monkeypatch.setattr(
        compare_1,
        "lire_lignes_valeurs_feuille",
        lambda *_: ({"AJ_Année_Z": 2024.0, "AJ_Mois_Z": "2024-02", "CARTES_D_MONTANT": 8.0},),
    )
    monkeypatch.setattr(
        compare_1,
        "_lire_lignes_encts_mensuels",
        lambda *_: ({"AJ_ANNEE": "2024", "AJ_MOIS": "2024-02", "Somme - E_MDP_CB": 3.0},),
    )
    monkeypatch.setattr(compare_1, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(compare_1, "definir_largeur_colonnes", lambda *_: None)

    document_destination = SimpleNamespace(
        getSheets=lambda: SimpleNamespace(getByIndex=lambda _: destination),
        getNumberFormats=lambda: object(),
    )
    compare_1.ajouter_comparaison_z2_ej(
        document_destination,
        SimpleNamespace(getSheets=lambda: feuilles_ej),
        SimpleNamespace(getSheets=lambda: feuilles_z2),
        boutique,
        2024,
    )

    assert destination.nom == nom_attendu
    assert ecritures == [
        (compare_1.COLONNES_COMPARE_MONTANT_Z2_EJ,),
        ((2024.0, "2024-02", "", 5.0, "", 0.0, "", 0.0),),
    ]


def test_noms_des_six_classeurs_z2_ej_sont_les_noms_des_feuilles() -> None:
    assert {
        f"{compare_1._nom_comparaison_z2_ej(boutique, annee)}.ods"
        for boutique in ("MASSENA", "MATURIN")
        for annee in (2023, 2024, 2025)
    } == {
        *(f"Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_{annee}.ods" for annee in (2023, 2024, 2025)),
        *(f"Compare_Montant_MATURIN_Z2ModeZVsEJ_{annee}.ods" for annee in (2023, 2024, 2025)),
    }


def test_enrichir_classeurs_applique_l_enrichissement_aux_deux_boutiques(
    tmp_path, monkeypatch
) -> None:
    appels: list[tuple[object, str, Path, str]] = []
    monkeypatch.setattr(
        compare_1,
        "enrichir_et_enregistrer_classeur",
        lambda uno, soffice, destination, *, boutique: appels.append(
            (uno, soffice, destination, boutique)
        ),
    )

    resultats = compare_1.enrichir_classeurs(tmp_path, uno=object())

    assert [appel[2].name for appel in appels] == [
        "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        "TTS_EJ_ENTETES_TICKETS_MATURIN.ods",
    ]
    assert [appel[3] for appel in appels] == ["MASSENA", "MATURIN"]
    assert resultats == {
        "MASSENA": tmp_path / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        "MATURIN": tmp_path / "TTS_EJ_ENTETES_TICKETS_MATURIN.ods",
    }
