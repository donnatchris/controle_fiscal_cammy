from pathlib import Path
from types import SimpleNamespace

from scripts import ods_ej_entetes


def test_ajouter_tri_construit_le_nom_de_feuille_depuis_la_boutique(
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
        ods_ej_entetes,
        "copier_feuille",
        lambda _document, _source, destination: destinations.append(destination) or FausseFeuille(),
    )
    monkeypatch.setattr(ods_ej_entetes, "definir_largeur_colonnes", lambda *_: None)
    monkeypatch.setitem(
        __import__("sys").modules,
        "com.sun.star.util",
        SimpleNamespace(SortField=lambda: SimpleNamespace(Field=None, SortAscending=None)),
    )

    ods_ej_entetes.ajouter_TriCrstNumInterne(
        document=object(),
        nom_feuille_source="ENTETES_TICKETS_MASSENA_0",
        boutique="MASSENA",
    )

    assert destinations == ["ENTETES_TICKETS_MASSENA_TriCrstNumInterne"]


def test_ajouter_ctrl_coherence_entete_copie_la_feuille_triee_et_ajoute_les_formules(
    monkeypatch,
) -> None:
    destinations: list[tuple[str, str]] = []

    class FausseCellule:
        String = ""
        Formula = ""
        NumberFormat = None

        def __init__(self) -> None:
            self.String = ""
            self.Formula = ""
            self.NumberFormat = None

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(EndRow=2)

    class FausseFeuille:
        def __init__(self) -> None:
            self.cellules: dict[tuple[int, int], FausseCellule] = {}

        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

        def getCellByPosition(self, colonne: int, ligne: int) -> FausseCellule:
            return self.cellules.setdefault((colonne, ligne), FausseCellule())

        def getCellRangeByPosition(
            self, debut_colonne: int, debut_ligne: int, fin_colonne: int, fin_ligne: int
        ) -> SimpleNamespace:
            def set_data_array(donnees: tuple[tuple[object, ...], ...]) -> None:
                for decalage_ligne, valeurs in enumerate(donnees):
                    for decalage_colonne, valeur in enumerate(valeurs):
                        self.getCellByPosition(
                            debut_colonne + decalage_colonne, debut_ligne + decalage_ligne
                        ).String = str(valeur)

            def set_formula_array(formules: tuple[tuple[str, ...], ...]) -> None:
                for decalage_ligne, valeurs in enumerate(formules):
                    for decalage_colonne, valeur in enumerate(valeurs):
                        self.getCellByPosition(
                            debut_colonne + decalage_colonne, debut_ligne + decalage_ligne
                        ).Formula = valeur

            feuille = self

            class FaussePlage:
                def setDataArray(self, donnees: tuple[tuple[object, ...], ...]) -> None:
                    set_data_array(donnees)

                def setFormulaArray(self, formules: tuple[tuple[str, ...], ...]) -> None:
                    set_formula_array(formules)

                @property
                def NumberFormat(self) -> None:
                    return None

                @NumberFormat.setter
                def NumberFormat(self, valeur: int) -> None:
                    for ligne in range(debut_ligne, fin_ligne + 1):
                        for colonne in range(debut_colonne, fin_colonne + 1):
                            feuille.getCellByPosition(colonne, ligne).NumberFormat = valeur

            return FaussePlage()

    feuille = FausseFeuille()
    formats_demandes: list[str] = []
    monkeypatch.setattr(
        ods_ej_entetes,
        "copier_feuille",
        lambda _document, source, destination: destinations.append((source, destination)) or feuille,
    )
    monkeypatch.setattr(
        ods_ej_entetes,
        "obtenir_format",
        lambda _formats, format_chaine: formats_demandes.append(format_chaine) or 42,
    )
    monkeypatch.setattr(ods_ej_entetes, "definir_largeur_colonnes", lambda *_: None)

    ods_ej_entetes.ajouter_CtrlCoherenceEntete(
        document=SimpleNamespace(getNumberFormats=lambda: object()),
        boutique="MASSENA",
    )

    assert destinations == [(
        "ENTETES_TICKETS_MASSENA_TriCrstNumInterne",
        "ENTETES_TICKETS_MASSENA_CtrlCoherenceEntete",
    )]
    assert [feuille.getCellByPosition(index, 0).String for index in range(18, 23)] == list(
        ods_ej_entetes.COLONNES_CTRL_COHERENCE_ENTETE
    )
    assert [feuille.getCellByPosition(index, 1).Formula for index in range(18, 23)] == [
        "=F2*20%", "=J2-S2", "=F2+J2", "=O2-U2", "=O2-(P2+R2)",
    ]
    assert [feuille.getCellByPosition(index, 2).Formula for index in range(18, 23)] == [
        "=F3*20%", "=J3-S3", "=F3+J3", "=O3-U3", "=O3-(P3+R3)",
    ]
    assert [feuille.getCellByPosition(index, 1).NumberFormat for index in range(18, 23)] == [42] * 5
    assert formats_demandes == ["0,00"]


def test_ajouter_sequentialite_copie_uniquement_les_colonnes_demandees_en_valeur(
    monkeypatch,
) -> None:
    class FausseCellule:
        def __init__(self, texte: str = "", valeur: float = 0, formule: str = "") -> None:
            self.String = texte
            self.Value = valeur
            self.Formula = formule
            self.NumberFormat = 0
            self.CharWeight = 0

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(EndRow=5)

    class FausseFeuille:
        def __init__(self) -> None:
            self.cellules: dict[tuple[int, int], FausseCellule] = {}

        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

        def getCellByPosition(self, colonne: int, ligne: int) -> FausseCellule:
            return self.cellules.setdefault((colonne, ligne), FausseCellule())

        def getCellRangeByPosition(
            self, debut_colonne: int, debut_ligne: int, fin_colonne: int, fin_ligne: int
        ) -> SimpleNamespace:
            def set_data_array(donnees: tuple[tuple[object, ...], ...]) -> None:
                for decalage_ligne, valeurs in enumerate(donnees):
                    for decalage_colonne, valeur in enumerate(valeurs):
                        cellule = self.getCellByPosition(
                            debut_colonne + decalage_colonne, debut_ligne + decalage_ligne
                        )
                        if isinstance(valeur, str):
                            cellule.String = valeur
                        else:
                            cellule.Value = valeur

            def get_data_array() -> tuple[tuple[object, ...], ...]:
                return tuple(
                    tuple(
                        cellule.String if cellule.String else cellule.Value
                        for cellule in (
                            self.getCellByPosition(colonne, ligne)
                            for colonne in range(debut_colonne, fin_colonne + 1)
                        )
                    )
                    for ligne in range(debut_ligne, fin_ligne + 1)
                )

            def set_formula_array(formules: tuple[tuple[str, ...], ...]) -> None:
                for decalage_ligne, valeurs in enumerate(formules):
                    for decalage_colonne, valeur in enumerate(valeurs):
                        self.getCellByPosition(
                            debut_colonne + decalage_colonne, debut_ligne + decalage_ligne
                        ).Formula = valeur

            feuille = self

            class FaussePlage:
                CharWeight = 0

                def setDataArray(self, donnees: tuple[tuple[object, ...], ...]) -> None:
                    set_data_array(donnees)

                def getDataArray(self) -> tuple[tuple[object, ...], ...]:
                    return get_data_array()

                def setFormulaArray(self, formules: tuple[tuple[str, ...], ...]) -> None:
                    set_formula_array(formules)

                @property
                def NumberFormat(self) -> None:
                    return None

                @NumberFormat.setter
                def NumberFormat(self, valeur: int) -> None:
                    for ligne in range(debut_ligne, fin_ligne + 1):
                        for colonne in range(debut_colonne, fin_colonne + 1):
                            feuille.getCellByPosition(colonne, ligne).NumberFormat = valeur

            return FaussePlage()

    class FaussesFeuilles:
        def __init__(self, source: FausseFeuille) -> None:
            self.feuilles = {"ENTETES_TICKETS_MASSENA_CtrlCoherenceEntete": source}

        def getByName(self, nom: str) -> FausseFeuille:
            return self.feuilles[nom]

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = FausseFeuille()

    source = FausseFeuille()
    tickets = ["000010", "000012", "", "ABC", "000020"]
    for ligne, ticket in enumerate(tickets, start=1):
        source.getCellByPosition(0, ligne).String = f"EJ{ligne}.TXT"
        source.getCellByPosition(1, ligne).String = f"{ligne:06d}"
        source.getCellByPosition(2, ligne).String = ticket
        source.getCellByPosition(3, ligne).Value = 45_000 + ligne
        source.getCellByPosition(3, ligne).Formula = str(45_000 + ligne)
        source.getCellByPosition(3, ligne).NumberFormat = 24
        source.getCellByPosition(4, ligne).String = "11:25"
    feuilles = FaussesFeuilles(source)
    document = SimpleNamespace(getSheets=lambda: feuilles, getNumberFormats=lambda: object())
    monkeypatch.setattr(ods_ej_entetes, "obtenir_format", lambda _formats, _format: 42)
    monkeypatch.setattr(ods_ej_entetes, "definir_largeur_colonnes", lambda *_: None)

    ods_ej_entetes.ajouter_sequentialite(document, "MASSENA")

    destination = feuilles.getByName("ENTETES_TICKETS_MASSENA_sequentialite")
    assert [destination.getCellByPosition(index, 0).String for index in range(6)] == list(
        ods_ej_entetes.COLONNES_SEQUENTIALITE
    )
    assert destination.getCellByPosition(2, 1).String == "000010"
    assert destination.getCellByPosition(3, 1).Value == 45_001
    assert destination.getCellByPosition(3, 1).Formula == ""
    assert destination.getCellByPosition(5, 1).Formula == ""
    assert destination.getCellByPosition(5, 1).String == ""
    assert destination.getCellByPosition(5, 2).Formula == (
        '=IF(OR(C3="";C2="");"";IFERROR(VALUE(C3)-VALUE(C2);""))'
    )
    assert destination.getCellByPosition(5, 2).NumberFormat == 42
    assert [destination.getCellByPosition(5, ligne).Formula for ligne in range(3, 6)] == [
        '=IF(OR(C4="";C3="");"";IFERROR(VALUE(C4)-VALUE(C3);""))',
        '=IF(OR(C5="";C4="");"";IFERROR(VALUE(C5)-VALUE(C4);""))',
        '=IF(OR(C6="";C5="");"";IFERROR(VALUE(C6)-VALUE(C5);""))',
    ]


def test_ajouter_td_occurrence_num_interne_cree_un_datapilot_natif(
    monkeypatch,
) -> None:
    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(Sheet=3, StartColumn=0, StartRow=0, EndColumn=5, EndRow=12)

    class FauxChamp:
        def __init__(self) -> None:
            self.proprietes: list[tuple[str, object]] = []

        def setPropertyValue(self, nom: str, valeur: object) -> None:
            self.proprietes.append((nom, valeur))

    class FauxDescripteur:
        def __init__(self, champ: FauxChamp) -> None:
            self.champ = champ
            self.source = None

        def setSourceRange(self, source: object) -> None:
            self.source = source

        def setPropertyValue(self, _: str, __: object) -> None:
            pass

        def getDataPilotFields(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda _: self.champ)

    class FauxTableaux:
        def __init__(self, descripteur: FauxDescripteur) -> None:
            self.descripteur = descripteur
            self.insertions: list[tuple[str, object, object]] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def removeByName(self, _: str) -> None:
            raise AssertionError("Aucun tableau croisé ne devrait exister sur une nouvelle feuille")

        def insertNewByName(self, nom: str, adresse: object, descripteur: object) -> None:
            self.insertions.append((nom, adresse, descripteur))

    class FausseFeuille:
        def __init__(self, tableaux: FauxTableaux | None = None) -> None:
            self.tableaux = tableaux

        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

        def getDataPilotTables(self) -> FauxTableaux:
            assert self.tableaux is not None
            return self.tableaux

        def getCellByPosition(self, _: int, __: int) -> SimpleNamespace:
            return SimpleNamespace(CellAddress="A1")

    champ = FauxChamp()
    descripteur = FauxDescripteur(champ)
    feuille_source = FausseFeuille()
    feuille_destination = FausseFeuille(FauxTableaux(descripteur))

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {"ENTETES_TICKETS_MASSENA_sequentialite": feuille_source}

        def getByName(self, nom: str) -> FausseFeuille:
            return self.feuilles[nom]

        def hasByName(self, _: str) -> bool:
            return False

        def removeByName(self, _: str) -> None:
            raise AssertionError("La feuille de destination ne doit pas déjà exister")

        def getCount(self) -> int:
            return len(self.feuilles)

        def insertNewByName(self, nom: str, _: int) -> None:
            self.feuilles[nom] = feuille_destination

    monkeypatch.setitem(
        __import__("sys").modules,
        "uno",
        SimpleNamespace(Enum=lambda enum, value: f"{enum}.{value}"),
    )
    feuilles = FaussesFeuilles()
    monkeypatch.setattr(ods_ej_entetes, "definir_largeur_colonnes", lambda *_: None)
    ods_ej_entetes.ajouter_TD_OccurenceNumInterne(
        SimpleNamespace(getSheets=lambda: feuilles), "MASSENA"
    )

    assert descripteur.source == SimpleNamespace(
        Sheet=3, StartColumn=0, StartRow=0, EndColumn=5, EndRow=12
    )
    assert champ.proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.ROW"),
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.COUNT"),
        ("Name", "Compter - E_NUM_INTERNE"),
    ]
    assert feuille_destination.tableaux.insertions == [
        ("TD_OccurenceNumInterne", "A1", descripteur)
    ]


def test_ajouter_entetes_0_lit_le_csv_preparatoire(tmp_path: Path, monkeypatch) -> None:
    chemin_csv = tmp_path / "EJ_ENTETES_TICKETS_MASSENA.csv"
    chemin_csv.write_text(
        "|".join(ods_ej_entetes.COLONNES_ENTETES)
        + "\nEJ010123.TXT|000001|000010|2023-01-02|11:25|100.00||||20.00|||||120.00|120.00||\n",
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
        ods_ej_entetes,
        "ecrire_tableau",
        lambda _feuille, lignes, *_args, **_kwargs: rows.extend(lignes),
    )
    monkeypatch.setattr(ods_ej_entetes, "definir_largeur_colonnes", lambda *_: None)

    ods_ej_entetes.ajouter_entetes_0(
        document,
        "ENTETES_TICKETS_MASSENA_0",
        chemin_csv,
    )

    assert rows == [{
        "nomfichier": "EJ010123.TXT",
        "E_NUM_INTERNE": "000001",
        "E_NUM_TICKET": "000010",
        "E_DATE_TICKET": "2023-01-02",
        "E_HEURE_TICKET": "11:25",
        "E_HT1": "100.00",
        "E_HT2": "",
        "E_HT3": "",
        "E_HT4": "",
        "E_TVA1": "20.00",
        "E_TVA2": "",
        "E_TVA3": "",
        "E_TVA4": "",
        "E_HT_NON_TAXABLE": "",
        "E_TTC": "120.00",
        "E_MDP_CB": "120.00",
        "E_MDP_ESPECES": "",
        "E_MDP_CHEQUES": "",
    }]


def test_generer_classeurs_produit_uniquement_les_deux_ods_depuis_les_csv(
    tmp_path: Path, monkeypatch
) -> None:
    staging = tmp_path / "travaux_preliminaires"
    staging.mkdir()
    for boutique in ("MASSENA", "MATURIN"):
        (staging / f"EJ_ENTETES_TICKETS_{boutique}.csv").write_text(
            "|".join(ods_ej_entetes.COLONNES_ENTETES) + "\n",
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
        assert boutique in {"MASSENA", "MATURIN"}
        assert chemin_csv == staging / f"EJ_ENTETES_TICKETS_{boutique}.csv"
        destination.write_bytes(b"ods")

    monkeypatch.setattr(ods_ej_entetes, "creer_et_enregistrer_classeur", creer)
    resultats = ods_ej_entetes.generer_classeurs(
        staging, tmp_path / "sortie", uno=object()
    )
    assert {chemin.name for chemin in resultats.values()} == {
        "TTS_EJ_ENTETES_TICKETS_MASSENA.ods", "TTS_EJ_ENTETES_TICKETS_MATURIN.ods",
    }
    assert {chemin.name for chemin in (tmp_path / "sortie").iterdir()} == {
        "TTS_EJ_ENTETES_TICKETS_MASSENA.ods", "TTS_EJ_ENTETES_TICKETS_MATURIN.ods",
    }
