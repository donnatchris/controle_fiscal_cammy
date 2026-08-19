from pathlib import Path
from types import SimpleNamespace

from scripts import db_ej_tickets_vers_ods


def test_position_entete_tcd_accepte_la_ligne_data_et_le_formatage_calc() -> None:
    assert db_ej_tickets_vers_ods._position_entete_tcd(
        (
            ("E_NUM_TICKET", "E_TTC", "Data", "", ""),
            ("", "", "Compter", "Somme - D_MONTANT ARTICLE", "Somme - D_CORRECTION"),
        ),
        "Somme - D_MONTANT_ARTICLE",
        champ="D_MONTANT_ARTICLE",
    ) == (3, 1)


def test_supprimer_ligne_data_tcd_fusionne_les_entetes_avant_suppression() -> None:
    valeurs = (
        ("E_NUM_TICKET", "E_TTC", "Data", "", ""),
        (
            "",
            "",
            "Compter - D_LIBELLE_ARTICLE",
            "Somme - D_MONTANT_ARTICLE",
            "Somme - D_CORRECTION",
        ),
        ("000609", 897, 3, 897, ""),
    )
    cellules: dict[tuple[int, int], SimpleNamespace] = {}
    suppressions: list[tuple[int, int]] = []
    feuille = SimpleNamespace(
        getCellByPosition=lambda colonne, ligne: cellules.setdefault(
            (colonne, ligne), SimpleNamespace(String="")
        ),
        getRows=lambda: SimpleNamespace(
            removeByIndex=lambda ligne, nombre: suppressions.append((ligne, nombre))
        ),
    )

    supprimee = db_ej_tickets_vers_ods._supprimer_ligne_data_tcd(feuille, valeurs)

    assert supprimee is True
    assert cellules[(0, 1)].String == "E_NUM_TICKET"
    assert cellules[(1, 1)].String == "E_TTC"
    assert suppressions == [(0, 1)]


def test_ajouter_tri_copie_la_feuille_0_dans_la_feuille_de_controle(
    monkeypatch,
) -> None:
    destinations: list[str] = []

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def createSortDescriptor(self) -> tuple[object, ...]:
            return ()

        def sort(self, _: tuple[object, ...]) -> None:
            pass

    class FausseFeuille:
        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "copier_feuille",
        lambda _document, _source, destination: destinations.append(destination) or FausseFeuille(),
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "definir_largeur_colonnes",
        lambda *_: None,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "com.sun.star.util",
        SimpleNamespace(SortField=lambda: SimpleNamespace(Field=None, SortAscending=None)),
    )

    db_ej_tickets_vers_ods.ajouter_TriCrstNumInterne(
        document=object(),
        nom_feuille_source="LIGNES_TICKETS_MASSENA_0",
        boutique="MASSENA",
    )

    assert destinations == ["LIGNES_TICKETS_MASSENA_TriCrstNumInterne"]


def test_ajouter_ctrl_coherence_entete_copie_la_feuille_lignes_triee(
    monkeypatch,
) -> None:
    destinations: list[tuple[str, str]] = []

    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "copier_feuille",
        lambda _document, source, destination: destinations.append((source, destination)) or object(),
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "definir_largeur_colonnes",
        lambda *_: None,
    )

    db_ej_tickets_vers_ods.ajouter_CtrlCoherenceEntete(
        document=object(),
        boutique="MASSENA",
    )

    assert destinations == [(
        "LIGNES_TICKETS_MASSENA_TriCrstNumInterne",
        "LIGNES_TICKETS_MASSENA_CtrlCoherenceLigne",
    )]


def test_ajouter_total_ligne_par_num_tickets_cree_un_datapilot_natif(
    monkeypatch,
) -> None:
    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxDescripteur:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []
            self.champs = [FauxChamp() for _ in db_ej_tickets_vers_ods.COLONNES_TICKETS]
            self.champ_disposition_donnees = FauxChamp()
            self.plage_source = None

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

        def setSourceRange(self, plage: object) -> None:
            self.plage_source = plage

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda index: self.champs[index])

        def getDataLayoutField(self) -> FauxChamp:
            return self.champ_disposition_donnees

    class FauxTableaux:
        def __init__(self) -> None:
            self.descripteur = FauxDescripteur()
            self.insertions: list[tuple[str, object, FauxDescripteur]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def insertNewByName(self, nom: str, cellule: object, desc: FauxDescripteur) -> None:
            self.insertions.append((nom, cellule, desc))

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> str:
            return "A1:X2"

    class FausseFeuilleSource:
        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

    class FausseFeuilleDestination:
        def __init__(self) -> None:
            self.tableaux = FauxTableaux()

        def getDataPilotTables(self) -> FauxTableaux:
            return self.tableaux

        def getCellByPosition(self, _: int, __: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    source = FausseFeuilleSource()
    destination = FausseFeuilleDestination()
    feuilles = SimpleNamespace(
        getByName=lambda nom: source if nom.endswith("CtrlCoherenceLigne") else destination,
        hasByName=lambda _: False,
        insertNewByName=lambda *_: None,
        getCount=lambda: 2,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, valeur: f"{enum}.{valeur}"),
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "definir_largeur_colonnes",
        lambda *_: None,
    )

    db_ej_tickets_vers_ods.ajouter_TotalLigneParNumTickets(
        SimpleNamespace(getSheets=lambda: feuilles),
        "MASSENA",
    )

    champs = destination.tableaux.descripteur.champs
    assert champs[db_ej_tickets_vers_ods.COLONNES_TICKETS.index("E_NUM_TICKET")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
    ]
    assert champs[db_ej_tickets_vers_ods.COLONNES_TICKETS.index("E_TTC")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
    ]
    assert champs[db_ej_tickets_vers_ods.COLONNES_TICKETS.index("D_LIBELLE_ARTICLE")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.COUNT"),
        ("Name", "Compter - D_LIBELLE_ARTICLE"),
    ]
    assert champs[db_ej_tickets_vers_ods.COLONNES_TICKETS.index("D_MONTANT_ARTICLE")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
        ("Name", "Somme - D_MONTANT_ARTICLE"),
    ]
    assert champs[db_ej_tickets_vers_ods.COLONNES_TICKETS.index("D_CORRECTION")].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
        ("Name", "Somme - D_CORRECTION"),
    ]
    assert destination.tableaux.descripteur.champ_disposition_donnees.proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.COLUMN"),
    ]


def test_ajouter_occurrence_libelle_article_cree_un_datapilot_natif(
    monkeypatch,
) -> None:
    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxDescripteur:
        def __init__(self) -> None:
            self.champs = [FauxChamp() for _ in db_ej_tickets_vers_ods.COLONNES_TICKETS]

        def setPropertyValue(self, _: str, __: object) -> None:
            pass

        def setSourceRange(self, _: object) -> None:
            pass

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda index: self.champs[index])

    class FauxTableaux:
        def __init__(self) -> None:
            self.descripteur = FauxDescripteur()
            self.insertions: list[tuple[str, object, FauxDescripteur]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def insertNewByName(self, nom: str, cellule: object, desc: FauxDescripteur) -> None:
            self.insertions.append((nom, cellule, desc))

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> str:
            return "A1:X2"

    class FausseFeuilleSource:
        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

    class FausseFeuilleDestination:
        def __init__(self) -> None:
            self.tableaux = FauxTableaux()

        def getDataPilotTables(self) -> FauxTableaux:
            return self.tableaux

        def getCellByPosition(self, _: int, __: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    source = FausseFeuilleSource()
    destination = FausseFeuilleDestination()
    feuilles = SimpleNamespace(
        getByName=lambda nom: source if nom.endswith("CtrlCoherenceLigne") else destination,
        hasByName=lambda _: False,
        insertNewByName=lambda *_: None,
        getCount=lambda: 2,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, valeur: f"{enum}.{valeur}"),
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "definir_largeur_colonnes",
        lambda *_: None,
    )

    db_ej_tickets_vers_ods.ajouter_OccurenceLibelleArticle(
        SimpleNamespace(getSheets=lambda: feuilles),
        "MASSENA",
    )

    champ = destination.tableaux.descripteur.champs[
        db_ej_tickets_vers_ods.COLONNES_TICKETS.index("D_LIBELLE_ARTICLE")
    ]
    assert champ.proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.COUNT"),
        ("Name", "Compter - D_LIBELLE_ARTICLE"),
    ]
    assert destination.tableaux.insertions == [
        ("TD_OccurenceLibelleArticle", "A1", destination.tableaux.descripteur)
    ]


def test_ajouter_occurrence_tx_tva_article_cree_un_datapilot_natif(
    monkeypatch,
) -> None:
    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxDescripteur:
        def __init__(self) -> None:
            self.champs = [FauxChamp() for _ in db_ej_tickets_vers_ods.COLONNES_TICKETS]

        def setPropertyValue(self, _: str, __: object) -> None:
            pass

        def setSourceRange(self, _: object) -> None:
            pass

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda index: self.champs[index])

    class FauxTableaux:
        def __init__(self) -> None:
            self.descripteur = FauxDescripteur()
            self.insertions: list[tuple[str, object, FauxDescripteur]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def insertNewByName(self, nom: str, cellule: object, desc: FauxDescripteur) -> None:
            self.insertions.append((nom, cellule, desc))

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> str:
            return "A1:X2"

    class FausseFeuilleSource:
        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

    class FausseFeuilleDestination:
        def __init__(self) -> None:
            self.tableaux = FauxTableaux()

        def getDataPilotTables(self) -> FauxTableaux:
            return self.tableaux

        def getCellByPosition(self, _: int, __: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    source = FausseFeuilleSource()
    destination = FausseFeuilleDestination()
    feuilles = SimpleNamespace(
        getByName=lambda nom: source if nom.endswith("CtrlCoherenceLigne") else destination,
        hasByName=lambda _: False,
        insertNewByName=lambda *_: None,
        getCount=lambda: 2,
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, valeur: f"{enum}.{valeur}"),
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "definir_largeur_colonnes",
        lambda *_: None,
    )

    db_ej_tickets_vers_ods.ajouter_OccurenceTxTvaArticle(
        SimpleNamespace(getSheets=lambda: feuilles),
        "MASSENA",
    )

    champ = destination.tableaux.descripteur.champs[
        db_ej_tickets_vers_ods.COLONNES_TICKETS.index("D_TAUX_TVA_ARTICLE")
    ]
    assert champ.proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.COUNT"),
        ("Name", "Compter - D_TAUX_TVA_ARTICLE"),
    ]
    assert destination.tableaux.insertions == [
        ("TD_OccurenceTxTvaArticle", "A1", destination.tableaux.descripteur)
    ]


def test_ajouter_ctrl_coherence_entete_ligne_copie_les_valeurs_et_ajoute_les_ecarts(
    monkeypatch,
) -> None:
    entetes = (
        "E_NUM_TICKET",
        "E_TTC",
        "Compter - D_LIBELLE_ARTICLE",
        "Somme - D_MONTANT_ARTICLE",
        "Somme - D_CORRECTION",
    )
    copies: list[tuple[str, str]] = []

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(StartColumn=0, StartRow=0, EndColumn=4, EndRow=2)

    class FausseCellule:
        def __init__(self) -> None:
            self.String = ""
            self.Formula = ""

    class FausseFeuille:
        def __init__(self) -> None:
            self.cellules: dict[tuple[int, int], FausseCellule] = {}

        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

        def getCellByPosition(self, colonne: int, ligne: int) -> FausseCellule:
            return self.cellules.setdefault((colonne, ligne), FausseCellule())

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(getDataArray=lambda: (entetes,))

    feuille = FausseFeuille()
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "copier_valeurs_feuille",
        lambda _document, source, destination: copies.append((source, destination)) or feuille,
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "definir_largeur_colonnes",
        lambda *_: None,
    )

    db_ej_tickets_vers_ods.ajouter_CtrlCoherenceEnteteLigne(object(), "MASSENA")

    assert copies == [(
        "TD_TotalLignesParNumTicket",
        "CtrlCoherence_EnteteLigne",
    )]
    assert feuille.getCellByPosition(5, 0).String == "AJ_ECART_TTC"
    assert feuille.getCellByPosition(5, 1).Formula == "=B2-(D2+E2)"
    assert feuille.getCellByPosition(5, 2).Formula == "=B3-(D3+E3)"


def test_ajouter_tickets_0_lit_le_csv_preparatoire(tmp_path: Path, monkeypatch) -> None:
    chemin_csv = tmp_path / "EJ_LIGNES_TICKETS_MASSENA.csv"
    chemin_csv.write_text(
        "|".join(db_ej_tickets_vers_ods.COLONNES_TICKETS)
        + "\nEJ010123.TXT|000001|000010|2023-01-02|11:25|100.00||||20.00|||||120.00|120.00|||1|ARTICLE|T1|100.00||\n",
        encoding="utf-8-sig",
    )
    rows: list[object] = []

    class FausseFeuille:
        def setName(self, _: str) -> None:
            pass

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(setDataArray=lambda _: None, CharWeight=0)

    feuille = FausseFeuille()
    document = SimpleNamespace(
        getSheets=lambda: SimpleNamespace(getByIndex=lambda _: feuille),
        getNumberFormats=lambda: object(),
    )
    monkeypatch.setattr(
        db_ej_tickets_vers_ods,
        "ecrire_tableau",
        lambda _feuille, lignes, *_args, **_kwargs: rows.extend(lignes),
    )
    monkeypatch.setattr(db_ej_tickets_vers_ods, "definir_largeur_colonnes", lambda *_: None)

    db_ej_tickets_vers_ods.ajouter_tickets_0(
        document,
        "LIGNES_TICKETS_MASSENA_0",
        chemin_csv,
    )

    assert rows[0]["E_NUM_INTERNE"] == "000001"
    assert rows[0]["D_LIBELLE_ARTICLE"] == "ARTICLE"


def test_generer_classeurs_utilise_les_csv_lignes(tmp_path: Path, monkeypatch) -> None:
    staging = tmp_path / "travaux_preliminaires"
    staging.mkdir()
    for boutique in ("MASSENA", "MATURIN"):
        (staging / f"EJ_LIGNES_TICKETS_{boutique}.csv").write_text(
            "|".join(db_ej_tickets_vers_ods.COLONNES_TICKETS) + "\n",
            encoding="utf-8-sig",
        )

    def creer(
        _: object,
        __: str,
        destination: Path,
        ___: str,
        chemin_csv: Path,
        *,
        boutique: str,
    ) -> None:
        assert boutique == destination.stem.split("_")[-1]
        assert chemin_csv == staging / f"EJ_LIGNES_TICKETS_{destination.stem.split('_')[-1]}.csv"
        destination.write_bytes(b"ods")

    monkeypatch.setattr(db_ej_tickets_vers_ods, "creer_et_enregistrer_classeur", creer)
    resultats = db_ej_tickets_vers_ods.generer_classeurs(
        staging, tmp_path / "sortie", uno=object()
    )

    assert {chemin.name for chemin in resultats.values()} == {
        "TTS_EJ_LIGNES_TICKETS_MASSENA.ods",
        "TTS_EJ_LIGNES_TICKETS_MATURIN.ods",
    }
