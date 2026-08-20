from pathlib import Path
from types import SimpleNamespace

from scripts import ods_z1
from shared.constantes import FeuilleZ1SyntheseMois


def test_add_Synthese_0_copie_le_csv_preparatoire(tmp_path: Path, monkeypatch) -> None:
    chemin_csv = tmp_path / "Z1_SyntheseMois_TOUS_2024_MASSENA.csv"
    chemin_csv.write_text(
        "|".join(ods_z1.COLONNES_Z1)
        + "\nZ101_01_052024_MASSENA.CSV||MC#01|SYNTHESE|FILE101|ZZ1|0077|"
        "2024-06-01|16:16|0001|CA BRUT|17|8967.90\n",
        encoding="utf-8-sig",
    )
    lignes: list[object] = []

    class FausseFeuille:
        def setName(self, _: str) -> None:
            pass

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(setDataArray=lambda _: None, CharWeight=0, NumberFormat=0)

    feuille = FausseFeuille()
    document = SimpleNamespace(
        getSheets=lambda: SimpleNamespace(getByIndex=lambda _: feuille),
        getNumberFormats=lambda: object(),
    )
    monkeypatch.setattr(ods_z1, "ecrire_tableau", lambda _f, rows, *_a, **_kw: lignes.extend(rows))
    monkeypatch.setattr(ods_z1, "obtenir_format", lambda _formats, _format: 42)
    monkeypatch.setattr(ods_z1, "definir_largeur_colonnes", lambda *_: None)

    ods_z1.add_Synthese_0(
        document,
        FeuilleZ1SyntheseMois.SYNTHESE_MOIS.pour("MASSENA", 2024),
        chemin_csv,
    )

    assert lignes == [{
        "nomfichier": "Z101_01_052024_MASSENA.CSV",
        "E_MODELE": "",
        "E_MACHINE": "MC#01",
        "E_RAPPORT": "SYNTHESE",
        "E_FICHIER": "FILE101",
        "E_MODE": "ZZ1",
        "E_COMPTEUR_Z": "0077",
        "E_DATE": "2024-06-01",
        "E_HEURE": "16:16",
        "D_ENREGISTREMENT": "0001",
        "D_DESIGNATION": "CA BRUT",
        "D_QUANTITE": "17",
        "D_MONTANT": "8967.90",
    }]


def test_ajouter_Cplte_copie_la_feuille_initiale_et_ajoute_la_periode_du_nom_fichier(
    monkeypatch,
) -> None:
    entetes: list[tuple[object, ...]] = []
    periodes: list[tuple[object, ...]] = []

    class FaussePlage:
        CharWeight = 0

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            if valeurs == (("AJ_Année_Z", "AJ_Mois_Z"),):
                entetes.extend(valeurs)
            else:
                periodes.extend(valeurs)

        def getDataArray(self) -> tuple[tuple[object, ...], ...]:
            return (
                ods_z1.COLONNES_Z1,
                ("Z101_01_052024_MASSENA.CSV",) + ("",) * 12,
                ("Z201_05A_122023_MASSENA.CSV",) + ("",) * 12,
            )

    class FausseFeuille:
        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(EndRow=2, EndColumn=12),
            )

        def getCellRangeByPosition(self, *_: int) -> FaussePlage:
            return FaussePlage()

    feuille = FausseFeuille()
    copies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        ods_z1,
        "copier_feuille",
        lambda _document, source, destination: copies.append((source, destination)) or feuille,
    )
    monkeypatch.setattr(ods_z1, "definir_largeur_colonnes", lambda *_: None)

    ods_z1.ajouter_Cplte(SimpleNamespace(), "MASSENA", 2024)

    assert copies == [(
        "Z1_SyntheseMois_TOUS_2024_MASSENA_0",
        "Z1_SyntheseMois_TOUS_2024_MASSENA_CplteAnneeMoisZ",
    )]
    assert entetes == [("AJ_Année_Z", "AJ_Mois_Z")]
    assert periodes == [("2024", "2024-05"), ("2023", "2023-12")]


def test_periode_cloture_depuis_nom_fichier_refuse_un_nom_sans_periode() -> None:
    try:
        ods_z1.periode_cloture_depuis_nom_fichier("Z101_SANS_DATE.CSV")
    except ValueError as erreur:
        assert "Période de clôture absente" in str(erreur)
    else:
        raise AssertionError("Le nom de fichier sans période doit être refusé")


def test_ajouter_TD_OccurenceEfichier_cree_un_veritable_datapilot(monkeypatch) -> None:
    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxChamps:
        def __init__(self, champs: list[FauxChamp]) -> None:
            self.champs = champs

        def getByIndex(self, index: int) -> FauxChamp:
            return self.champs[index]

    class FauxDescripteur:
        def __init__(self, champs: list[FauxChamp]) -> None:
            self.champs = FauxChamps(champs)
            self.proprietes: list[tuple[str, object]] = []
            self.source: object | None = None

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

        def setSourceRange(self, source: object) -> None:
            self.source = source

        def getDataPilotFields(self) -> FauxChamps:
            return self.champs

    class FauxTableaux:
        def __init__(self, descripteur: FauxDescripteur) -> None:
            self.descripteur = descripteur
            self.insertions: list[tuple[str, object, FauxDescripteur]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def removeByName(self, _: str) -> None:
            raise AssertionError("Aucun DataPilot préexistant")

        def insertNewByName(
            self, nom: str, cellule: object, descripteur: FauxDescripteur
        ) -> None:
            self.insertions.append((nom, cellule, descripteur))

    class FausseFeuille:
        def __init__(self, tableaux: FauxTableaux | None = None) -> None:
            self.tableaux = tableaux

        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: "SOURCE_A1:O20",
            )

        def getDataPilotTables(self) -> FauxTableaux:
            assert self.tableaux is not None
            return self.tableaux

        def getCellByPosition(self, _: int, __: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    champs = [FauxChamp() for _ in range(15)]
    descripteur = FauxDescripteur(champs)
    tableaux = FauxTableaux(descripteur)
    feuille_source = FausseFeuille()
    feuille_destination = FausseFeuille(tableaux)

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {
                "Z1_SyntheseMois_TOUS_2024_MASSENA_CplteAnneeMoisZ": feuille_source
            }

        def getByName(self, nom: str) -> FausseFeuille:
            return self.feuilles[nom]

        def hasByName(self, nom: str) -> bool:
            return nom in self.feuilles

        def getElementNames(self) -> tuple[str, ...]:
            return tuple(self.feuilles)

        def removeByName(self, nom: str) -> None:
            del self.feuilles[nom]

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = feuille_destination

    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, value: f"{enum}.{value}"),
    )
    monkeypatch.setattr(ods_z1, "definir_largeur_colonnes", lambda *_: None)

    ods_z1.ajouter_TD_OccurenceEfichier(
        SimpleNamespace(getSheets=lambda: FaussesFeuilles()),
        "MASSENA",
        2024,
    )

    assert descripteur.source == "SOURCE_A1:O20"
    assert descripteur.proprietes == [("RowGrand", False), ("ColumnGrand", False)]
    assert champs[13].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    assert champs[14].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    assert champs[7].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    assert champs[4].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.COLUMN")
    ]
    assert champs[5].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.COLUMN"),
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.COUNT"),
        ("Name", "Compter - E_MODE"),
    ]
    assert tableaux.insertions == [(
        "TD_OccurenceEfichierEmodeParMoisAnnée_2024",
        "A1",
        descripteur,
    )]


def test_ajouter_TD_TotalMontant_cree_un_datapilot_avec_filtre_mode(monkeypatch) -> None:
    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxChamps:
        def __init__(self, champs: list[FauxChamp]) -> None:
            self.champs = champs

        def getByIndex(self, index: int) -> FauxChamp:
            return self.champs[index]

    class FauxDescripteur:
        def __init__(self, champs: list[FauxChamp]) -> None:
            self.champs = FauxChamps(champs)
            self.proprietes: list[tuple[str, object]] = []
            self.source: object | None = None

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

        def setSourceRange(self, source: object) -> None:
            self.source = source

        def getDataPilotFields(self) -> FauxChamps:
            return self.champs

    class FauxTableaux:
        def __init__(self, descripteur: FauxDescripteur) -> None:
            self.descripteur = descripteur
            self.insertions: list[tuple[str, object, FauxDescripteur]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def removeByName(self, _: str) -> None:
            raise AssertionError("Aucun DataPilot préexistant")

        def insertNewByName(
            self, nom: str, cellule: object, descripteur: FauxDescripteur
        ) -> None:
            self.insertions.append((nom, cellule, descripteur))

    class FausseFeuille:
        def __init__(self, tableaux: FauxTableaux | None = None) -> None:
            self.tableaux = tableaux

        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: "SOURCE_A1:O20",
            )

        def getDataPilotTables(self) -> FauxTableaux:
            assert self.tableaux is not None
            return self.tableaux

        def getCellByPosition(self, _: int, __: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    champs = [FauxChamp() for _ in range(15)]
    descripteur = FauxDescripteur(champs)
    tableaux = FauxTableaux(descripteur)
    feuille_source = FausseFeuille()
    feuille_destination = FausseFeuille(tableaux)

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {
                "Z1_SyntheseMois_TOUS_2024_MASSENA_CplteAnneeMoisZ": feuille_source
            }

        def getByName(self, nom: str) -> FausseFeuille:
            return self.feuilles[nom]

        def hasByName(self, nom: str) -> bool:
            return nom in self.feuilles

        def getElementNames(self) -> tuple[str, ...]:
            return tuple(self.feuilles)

        def removeByName(self, nom: str) -> None:
            del self.feuilles[nom]

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = feuille_destination

    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, value: f"{enum}.{value}"),
    )
    monkeypatch.setattr(ods_z1, "definir_largeur_colonnes", lambda *_: None)

    ods_z1.ajouter_TD_TotalMontant(
        SimpleNamespace(getSheets=lambda: FaussesFeuilles()),
        "MASSENA",
        2024,
    )

    assert descripteur.source == "SOURCE_A1:O20"
    assert descripteur.proprietes == [("RowGrand", False), ("ColumnGrand", False)]
    assert champs[13].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    assert champs[14].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW")
    ]
    assert champs[10].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.COLUMN")
    ]
    assert champs[5].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.PAGE"),
        ("UseSelectedPage", False),
    ]
    assert champs[12].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
        ("Name", "Somme - D_MONTANT"),
    ]
    assert tableaux.insertions == [(
        "TD_Z1_TotalMontantParMoisAnnee_2024",
        "A1",
        descripteur,
    )]


def test_extraire_totaux_mensuels_z1_tcd_met_les_designations_a_lhorizontale() -> None:
    donnees_tcd = (
        ("E_MODE", "ZZ1", "", "", "", "", "", "", ""),
        (
            "AJ_Année_Z",
            "AJ_Mois_Z",
            "CA BRUT",
            "CA NET",
            "CB.TIROIR",
            "CHQ.TIROIR",
            "ESP.TIROIR",
            "HORS TAXE 1",
            "TVA 1",
        ),
        ("2024", "2024-01", 100.0, 90.0, 50.0, 10.0, 30.0, 75.0, 15.0),
        ("", "2024-02", 200.0, 180.0, 80.0, 20.0, 80.0, 150.0, 30.0),
        ("Total Résultat", "", 300.0, 270.0, 130.0, 30.0, 110.0, 225.0, 45.0),
    )

    assert ods_z1.extraire_totaux_mensuels_z1_tcd(donnees_tcd) == (
        ("2024", "2024-01", 100.0, 90.0, 50.0, 10.0, 30.0, 75.0, 15.0),
        ("2024", "2024-02", 200.0, 180.0, 80.0, 20.0, 80.0, 150.0, 30.0),
    )


def test_selectionner_mode_tcd_active_et_applique_le_filtre_zz1(monkeypatch) -> None:
    proprietes: list[tuple[str, object]] = []
    champ = SimpleNamespace(
        setPropertyValue=lambda nom, valeur: proprietes.append((nom, valeur))
    )
    tableau = SimpleNamespace(
        getDataPilotFields=lambda: SimpleNamespace(getByIndex=lambda _: champ)
    )
    tableaux = SimpleNamespace(getByName=lambda _: tableau)
    feuille = SimpleNamespace(getDataPilotTables=lambda: tableaux)
    filtrages: list[tuple[object, str, int, str]] = []
    monkeypatch.setattr(
        ods_z1,
        "appliquer_filtre_mode_data_pilot",
        lambda *arguments: filtrages.append(arguments),
    )

    ods_z1.selectionner_mode_tcd(feuille, "TD_Z1_2024", "ZZ1")

    assert proprietes == [("UseSelectedPage", True), ("SelectedPage", "ZZ1")]
    assert filtrages == [(tableaux, "TD_Z1_2024", 5, "ZZ1")]


def test_ajouter_Total_modeZZ1_copie_uniquement_les_valeurs_du_tcd(monkeypatch) -> None:
    donnees_tcd = (
        (
            "AJ_Année_Z",
            "AJ_Mois_Z",
            "CA BRUT",
            "CA NET",
            "CB.TIROIR",
            "CHQ.TIROIR",
            "ESP.TIROIR",
            "HORS TAXE 1",
            "TVA 1",
        ),
        ("2024", "2024-01", 100.0, 90.0, 50.0, 10.0, 30.0, 75.0, 15.0),
    )
    ecritures: list[tuple[tuple[object, ...], ...]] = []

    class FaussePlageSource:
        def getDataArray(self) -> tuple[tuple[object, ...], ...]:
            return donnees_tcd

    class FausseFeuilleSource:
        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(
                    StartColumn=0,
                    StartRow=0,
                    EndColumn=8,
                    EndRow=1,
                ),
            )

        def getCellRangeByPosition(self, *_: int) -> FaussePlageSource:
            return FaussePlageSource()

    class FaussePlageDestination:
        CharWeight = 0
        NumberFormat = 0

        def merge(self, _: bool) -> None:
            pass

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            ecritures.append(valeurs)

    class FausseFeuilleDestination:
        def __init__(self) -> None:
            self.cellules: dict[tuple[int, int], SimpleNamespace] = {}

        def getCellRangeByPosition(self, *_: int) -> FaussePlageDestination:
            return FaussePlageDestination()

        def getCellByPosition(self, colonne: int, ligne: int) -> SimpleNamespace:
            return self.cellules.setdefault(
                (colonne, ligne),
                SimpleNamespace(String=""),
            )

    source = FausseFeuilleSource()
    destination = FausseFeuilleDestination()

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles: dict[str, object] = {
                "TD_Z1_TotalMontantParMoisAnnee_2024": source
            }

        def getByName(self, nom: str) -> object:
            return self.feuilles[nom]

        def hasByName(self, nom: str) -> bool:
            return nom in self.feuilles

        def removeByName(self, nom: str) -> None:
            del self.feuilles[nom]

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = destination

    selections: list[tuple[object, str, str]] = []
    monkeypatch.setattr(
        ods_z1,
        "selectionner_mode_tcd",
        lambda *arguments: selections.append(arguments),
    )
    monkeypatch.setattr(ods_z1, "obtenir_format", lambda *_: 42)
    monkeypatch.setattr(ods_z1, "definir_largeur_colonnes", lambda *_: None)
    feuilles = FaussesFeuilles()
    document = SimpleNamespace(
        getSheets=lambda: feuilles,
        getNumberFormats=lambda: object(),
    )

    ods_z1.ajouter_Total_modeZZ1(document, "MASSENA", 2024)

    assert selections == [(source, "TD_Z1_TotalMontantParMoisAnnee_2024", "ZZ1")]
    assert "Z1_TotalMontantParMoisAnnee_2024_ModeZZ1" in feuilles.feuilles
    assert destination.cellules[(0, 0)].String == "E_MODE"
    assert destination.cellules[(8, 0)].String == "ZZ1"
    assert ecritures == [
        (ods_z1.COLONNES_TOTAL_MONTANT_MODE_ZZ1,),
        (("2024", "2024-01", 100.0, 90.0, 50.0, 10.0, 30.0, 75.0, 15.0),),
    ]


def test_ajouter_Total_modeZZ1_ne_cree_rien_pour_maturin_2024() -> None:
    document = SimpleNamespace(
        getSheets=lambda: (_ for _ in ()).throw(
            AssertionError("Aucune feuille ne doit être consultée")
        )
    )

    ods_z1.ajouter_Total_modeZZ1(document, "MATURIN", 2024)


def test_ajouter_Total_modeZZ2_et_Z_utilisent_le_mode_correspondant(monkeypatch) -> None:
    appels: list[tuple[object, str, int, str]] = []
    monkeypatch.setattr(
        ods_z1,
        "ajouter_Total_mode",
        lambda *arguments: appels.append(arguments),
    )
    document = object()

    ods_z1.ajouter_Total_modeZZ2(document, "MATURIN", 2025)
    ods_z1.ajouter_Total_modeZ(document, "MATURIN", 2025)

    assert appels == [
        (document, "MATURIN", 2025, "ZZ2"),
        (document, "MATURIN", 2025, "Z"),
    ]


def test_ajouter_Total_modes_exclus_ne_creent_rien() -> None:
    document = SimpleNamespace(
        getSheets=lambda: (_ for _ in ()).throw(
            AssertionError("Aucune feuille ne doit être consultée")
        )
    )

    ods_z1.ajouter_Total_modeZZ1(document, "MATURIN", 2024)
    ods_z1.ajouter_Total_modeZZ2(document, "MATURIN", 2024)
    ods_z1.ajouter_Total_modeZ(document, "MASSENA", 2024)


def test_exceptions_de_modes_z1_sont_limitees_aux_regles_demandes() -> None:
    assert ods_z1.EXCEPTIONS_MODE_Z1 == {
        ("ZZ1", "MATURIN", 2024),
        ("ZZ2", "MATURIN", 2024),
        ("Z", "MASSENA", 2024),
    }


def test_generer_classeurs_utilise_les_csv_z1_et_les_noms_contractuels(
    tmp_path: Path, monkeypatch
) -> None:
    staging = tmp_path / "travaux_preliminaires"
    staging.mkdir()
    for annee in (2023, 2024, 2025):
        for boutique in ("MASSENA", "MATURIN"):
            (staging / f"Z1_SyntheseMois_TOUS_{annee}_{boutique}.csv").write_text(
                "|".join(ods_z1.COLONNES_Z1) + "\n", encoding="utf-8-sig"
            )

    appels: list[tuple[str, Path]] = []

    def creer(
        _uno: object,
        _soffice: str,
        destination: Path,
        nom_feuille: str,
        chemin_csv: Path,
        *,
        boutique: str,
        annee: int,
    ) -> None:
        appels.append((nom_feuille, chemin_csv))
        assert nom_feuille == FeuilleZ1SyntheseMois.SYNTHESE_MOIS.pour(boutique, annee)
        destination.write_bytes(b"ods")

    monkeypatch.setattr(ods_z1, "creer_et_enregistrer_classeur", creer)
    resultats = ods_z1.generer_classeurs(staging, tmp_path / "sortie", uno=object())

    assert {nom_feuille for nom_feuille, _ in appels} == {
        FeuilleZ1SyntheseMois.SYNTHESE_MOIS.pour(boutique, annee)
        for annee in (2023, 2024, 2025)
        for boutique in ("MASSENA", "MATURIN")
    }
    assert {chemin.name for chemin in resultats.values()} == {
        f"TTS_Z1_SyntheseMois_TOUS_{annee}_{boutique}.ods"
        for annee in (2023, 2024, 2025)
        for boutique in ("MASSENA", "MATURIN")
    }
