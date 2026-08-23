from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import ods_z2
from shared.constantes import FeuilleZ2Transactions


def test_ajouter_transactions_0_lit_le_csv_preparatoire(tmp_path: Path, monkeypatch) -> None:
    chemin_csv = tmp_path / "Z2_TransactionsMois_TOUS_2024_MASSENA.csv"
    chemin_csv.write_text(
        "|".join(ods_z2.COLONNES_Z2)
        + "\nZ102_01_052024_MASSENA.CSV||MC#01|TRANSACTION|FILE102|ZZ1|0077|"
        "2024-06-01|16:16|0001|ESPECES|17|8967.90\n",
        encoding="utf-8-sig",
    )
    rows: list[object] = []

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
    monkeypatch.setattr(
        ods_z2,
        "ecrire_tableau",
        lambda _feuille, lignes, *_args, **_kwargs: rows.extend(lignes),
    )
    monkeypatch.setattr(ods_z2, "obtenir_format", lambda _formats, _format: 42)
    monkeypatch.setattr(ods_z2, "definir_largeur_colonnes", lambda *_: None)

    ods_z2.ajouter_transactions_0(
        document,
        FeuilleZ2Transactions.TRANSACTIONS.pour("MASSENA", 2024),
        chemin_csv,
    )

    assert rows == [{
        "nomfichier": "Z102_01_052024_MASSENA.CSV",
        "E_MODELE": "",
        "E_MACHINE": "MC#01",
        "E_RAPPORT": "TRANSACTION",
        "E_FICHIER": "FILE102",
        "E_MODE": "ZZ1",
        "E_COMPTEUR_Z": "0077",
        "E_DATE": "2024-06-01",
        "E_HEURE": "16:16",
        "D_ENREGISTREMENT": "0001",
        "D_DESIGNATION": "ESPECES",
        "D_QUANTITE": "17",
        "D_MONTANT": "8967.90",
    }]


def test_periode_cloture_depuis_nom_fichier_extrait_le_mois_independamment_de_E_DATE() -> None:
    assert ods_z2.periode_cloture_depuis_nom_fichier(
        "Z102_02_082025_MASSENA.CSV"
    ) == ("2025", "2025-08")


def test_periode_cloture_depuis_nom_fichier_retient_le_dernier_mois_du_lot() -> None:
    assert ods_z2.periode_cloture_depuis_nom_fichier(
        "Z002_01_062025_072025_MATURIN.CSV"
    ) == ("2025", "2025-07")


def test_periode_cloture_depuis_nom_fichier_rejette_un_nom_sans_periode() -> None:
    with pytest.raises(ValueError, match="Période de clôture absente"):
        ods_z2.periode_cloture_depuis_nom_fichier("Z102_MASSENA.CSV")


def test_ajouter_CplteAnneeMoisZ_copie_la_feuille_initiale_et_utilise_nomfichier(
    monkeypatch,
) -> None:
    appels: list[tuple[int, int, int, int]] = []
    entetes: list[tuple[object, ...]] = []
    periodes_ecrites: list[tuple[tuple[object, ...], ...]] = []

    class FaussePlage:
        CharWeight = 0
        NumberFormat = 0

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            entetes.extend(valeurs)

    class FausseFeuille:
        def createCursor(self) -> SimpleNamespace:
            return SimpleNamespace(
                gotoEndOfUsedArea=lambda _: None,
                getRangeAddress=lambda: SimpleNamespace(EndRow=2),
            )

        def getCellRangeByPosition(
            self,
            colonne_debut: int,
            ligne_debut: int,
            colonne_fin: int,
            ligne_fin: int,
        ) -> FaussePlage:
            appels.append((colonne_debut, ligne_debut, colonne_fin, ligne_fin))
            if (colonne_debut, ligne_debut, colonne_fin, ligne_fin) == (0, 0, 12, 2):
                return SimpleNamespace(getDataArray=lambda: (
                    ods_z2.COLONNES_Z2,
                    (
                        "Z102_02_082025_MASSENA.CSV", "", "", "", "", "", "",
                        "2025-09-02", "", "", "", "", "",
                    ),
                    (
                        "Z102_01_052024_MASSENA.CSV", "", "", "", "", "", "",
                        "2024-06-01", "", "", "", "", "",
                    ),
                ))
            if (colonne_debut, ligne_debut, colonne_fin, ligne_fin) == (13, 1, 14, 2):
                return SimpleNamespace(
                    setDataArray=lambda valeurs: periodes_ecrites.append(valeurs)
                )
            return FaussePlage()

    feuille = FausseFeuille()
    copies: list[tuple[str, str]] = []
    document = SimpleNamespace(getNumberFormats=lambda: object())
    monkeypatch.setattr(
        ods_z2,
        "copier_feuille",
        lambda _document, source, destination: copies.append((source, destination)) or feuille,
    )
    monkeypatch.setattr(ods_z2, "obtenir_format", lambda _formats, _format: 42)
    monkeypatch.setattr(ods_z2, "definir_largeur_colonnes", lambda *_: None)

    ods_z2.ajouter_CplteAnneeMoisZ(document, "MASSENA", 2024)

    assert copies == [(
        "Z2_TransactionsMois_TOUS_2024_MASSENA_0",
        "Z2_TransactionsMois_TOUS_2024_MASSENA_CplteAnneeMoisZ",
    )]
    assert entetes == [("AJ_Année_Z", "AJ_Mois_Z")]
    assert periodes_ecrites == [((2025, "2025-08"), (2024, "2024-05"))]
    assert appels == [(13, 0, 14, 0), (0, 0, 12, 2), (13, 1, 14, 2), (13, 1, 13, 2)]


@pytest.mark.parametrize(
    ("mode_demande", "mode_selectionne"),
    (("ZZ1", "ZZ1"), ("ZZ2", "ZZ2"), ("Z", "Z"), (None, None)),
)
def test_ajouter_TotalMontant_cree_un_datapilot_natif_avec_filtres_de_page(
    monkeypatch,
    mode_demande: str | None,
    mode_selectionne: str | None,
) -> None:
    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(Sheet=1, StartColumn=0, StartRow=0, EndColumn=14, EndRow=12)

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
            self.rafraichissements: list[str] = []

        def createDataPilotDescriptor(self) -> FauxDescripteur:
            return self.descripteur

        def hasByName(self, _: str) -> bool:
            return False

        def removeByName(self, _: str) -> None:
            raise AssertionError("Aucun tableau croisé ne devrait exister sur une nouvelle feuille")

        def insertNewByName(self, nom: str, adresse: object, descripteur: object) -> None:
            self.insertions.append((nom, adresse, descripteur))

        def getByName(self, nom: str) -> SimpleNamespace:
            return SimpleNamespace(refresh=lambda: self.rafraichissements.append(nom))

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

    champs = [FauxChamp() for _ in range(15)]
    descripteur = FauxDescripteur(champs)
    feuille_source = FausseFeuille()
    feuille_destination = FausseFeuille(FauxTableaux(descripteur))

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles = {
                "Z2_TransactionsMois_TOUS_2024_MASSENA_CplteAnneeMoisZ": feuille_source
            }

        def getByName(self, nom: str) -> FausseFeuille:
            return self.feuilles[nom]

        def hasByName(self, nom: str) -> bool:
            return nom in self.feuilles

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
    monkeypatch.setattr(ods_z2, "definir_largeur_colonnes", lambda *_: None)
    filtrages: list[tuple[object, str, int, str]] = []
    monkeypatch.setattr(
        ods_z2,
        "appliquer_filtre_mode_data_pilot",
        lambda *arguments: filtrages.append(arguments),
    )
    monkeypatch.setattr(ods_z2, "filtrer_elements_mode_data_pilot", lambda *_: None)
    ods_z2.ajouter_TotalMontant(
        SimpleNamespace(getSheets=lambda: FaussesFeuilles()),
        "MASSENA",
        2024,
        mode_demande,
    )

    assert descripteur.source == SimpleNamespace(
        Sheet=1, StartColumn=0, StartRow=0, EndColumn=14, EndRow=12
    )
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
        *(
            (("UseSelectedPage", True), ("SelectedPage", mode_selectionne))
            if mode_selectionne is not None
            else ()
        ),
    ]
    assert champs[4].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.PAGE")
    ]
    assert champs[11].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
        ("Name", "Somme - D_QUANTITE"),
    ]
    assert champs[12].proprietes == [
        ("Orientation", "com.sun.star.sheet.DataPilotFieldOrientation.DATA"),
        ("Function", "com.sun.star.sheet.GeneralFunction.SUM"),
        ("Name", "Somme - D_MONTANT"),
    ]
    assert feuille_destination.tableaux.insertions == [
        ("TD_TotalMontant_parMoisAnnee_parNatureTransaction", "A1", descripteur)
    ]
    assert filtrages == (
        [
            (
                feuille_destination.tableaux,
                "TD_TotalMontant_parMoisAnnee_parNatureTransaction",
                5,
                mode_selectionne,
            )
        ]
        if mode_selectionne is not None
        else []
    )


def test_exceptions_des_modes_z2_limitees_a_maturin_2024() -> None:
    assert ods_z2.resoudre_mode_z2("ZZ1", "MASSENA", 2024) == "ZZ1"
    assert ods_z2.resoudre_mode_z2("ZZ2", "MASSENA", 2024) == "ZZ2"
    assert ods_z2.resoudre_mode_z2("Z", "MASSENA", 2024) == "Z"
    assert not ods_z2.mode_z2_est_applicable("ZZ1", "MATURIN", 2024)
    assert not ods_z2.mode_z2_est_applicable("ZZ2", "MATURIN", 2024)
    assert ods_z2.mode_z2_est_applicable("Z", "MATURIN", 2024)
    assert ods_z2.mode_z2_est_applicable("ZZ1", "MASSENA", 2024)
    assert ods_z2.mode_z2_est_applicable("ZZ2", "MASSENA", 2024)
    assert not ods_z2.mode_z2_est_applicable("Z", "MASSENA", 2024)


def test_appliquer_filtre_mode_data_pilot_masque_zz1_et_zz2_pour_le_mode_z() -> None:
    class FauxElement:
        def __init__(self, nom: str) -> None:
            self.nom = nom
            self.proprietes: list[tuple[str, bool]] = []

        def getName(self) -> str:
            return self.nom

        def setPropertyValue(self, nom: str, valeur: bool) -> None:
            self.proprietes.append((nom, valeur))

    elements = [FauxElement("Z"), FauxElement("ZZ1"), FauxElement("ZZ2")]
    tableau = SimpleNamespace(
        getDataPilotFields=lambda: SimpleNamespace(
            getByIndex=lambda index: SimpleNamespace(
                getItems=lambda: SimpleNamespace(
                    getCount=lambda: len(elements),
                    getByIndex=lambda index: elements[index],
                )
            )
        ),
        refresh=lambda: rafraichissements.append(True),
    )
    rafraichissements: list[bool] = []
    tableaux = SimpleNamespace(getByName=lambda nom: tableau)

    ods_z2.appliquer_filtre_mode_data_pilot(
        tableaux,
        "TD_TotalMontant_parMoisAnnee_parNatureTransaction",
        5,
        "Z",
    )

    assert [element.proprietes for element in elements] == [
        [("IsHidden", False)],
        [("IsHidden", True)],
        [("IsHidden", True)],
    ]
    assert rafraichissements == [True]


def test_extraire_totaux_mensuels_tcd_reorganise_les_valeurs_du_tcd() -> None:
    donnees_tcd = (
        ("E_MODE", "ZZ1"),
        (
            "AJ_Année_Z",
            "AJ_Mois_Z",
            "Data",
            "CARTES",
            "CHEQUES",
            "CORRECTION",
            "ESPECES",
            "REF./TIROIR",
        ),
        (2024.0, "2024-01", "Somme - D_QUANTITE", 1.0, 2.0, 3.0, 4.0, 5.0),
        ("", "", "Somme - D_MONTANT", 10.5, 20.5, 30.5, 40.5, 50.5),
        ("", "2024-02", "Somme - D_QUANTITE", 6.0, 7.0, 8.0, 9.0, 10.0),
        ("", "", "Somme - D_MONTANT", 60.5, 70.5, 80.5, 90.5, 100.5),
    )

    assert ods_z2.extraire_totaux_mensuels_tcd(donnees_tcd) == (
        (2024.0, "2024-01", 1.0, 10.5, 2.0, 20.5, 3.0, 30.5, 4.0, 40.5, 5.0, 50.5),
        (2024.0, "2024-02", 6.0, 60.5, 7.0, 70.5, 8.0, 80.5, 9.0, 90.5, 10.0, 100.5),
    )


def test_verifier_totaux_mode_tcd_refuse_juin_2025_sans_ligne_source_z() -> None:
    totaux_tcd = (
        (2025.0, "2025-06", 512.0, 5369.03, 2.0, 0.80, 0.0, 0.0, 238.0, 1316.15, 0.0, 0.0),
    )

    with pytest.raises(RuntimeError, match="mode Z.*2025-06"):
        ods_z2.verifier_totaux_mode_tcd(totaux_tcd, (), "Z")

    ods_z2.verifier_totaux_mode_tcd(
        ((2025.0, "2025-06", *(0.0 for _ in range(10))),),
        (),
        "Z",
    )


def test_comparer_lignes_par_periode_rapproche_trie_et_conserve_les_mois_absents() -> None:
    lignes_zz1 = (
        {
            "AJ_Année_Z": 2024.0,
            "AJ_Mois_Z": "2024-02",
            "CARTES_D_QUANTITE": 5.0,
            "CARTES_D_MONTANT": 100.0,
        },
        {
            "AJ_Année_Z": 2024.0,
            "AJ_Mois_Z": "2024-01",
            "CARTES_D_QUANTITE": 1.0,
            "CARTES_D_MONTANT": 10.0,
        },
    )
    lignes_zz2 = (
        {
            "AJ_Année_Z": 2024.0,
            "AJ_Mois_Z": "2024-03",
            "CARTES_D_QUANTITE": 3.0,
            "CARTES_D_MONTANT": 50.0,
        },
        {
            "AJ_Année_Z": 2024.0,
            "AJ_Mois_Z": "2024-01",
            "CARTES_D_QUANTITE": 2.0,
            "CARTES_D_MONTANT": 3.0,
        },
    )

    assert ods_z2.comparer_lignes_par_periode(lignes_zz1, lignes_zz2) == (
        (2024.0, "2024-01", -1.0, 7.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (2024.0, "2024-02", 5.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (2024.0, "2024-03", -3.0, -50.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    )


def test_ajouter_CompareMontant_cree_la_feuille_de_comparaison(monkeypatch) -> None:
    ecritures: list[tuple[tuple[object, ...], ...]] = []
    assert ods_z2.COLONNES_COMPARE_MONTANT == (
        "AJ_Année_Z",
        "AJ_Mois_Z",
        "CARTES_AJ_ECART_QTE",
        "CARTES_AJ_ECART_MONTANT",
        "CHEQUES_AJ_ECART_QTE",
        "CHEQUES_AJ_ECART_MONTANT",
        "CORRECTION_AJ_ECART_QTE",
        "CORRECTION_AJ_ECART_MONTANT",
        "ESPECES_AJ_ECART_QTE",
        "ESPECES_AJ_ECART_MONTANT",
        "REF./TIROIR_AJ_ECART_QTE",
        "REF./TIROIR_AJ_ECART_MONTANT",
    )

    class FaussePlage:
        CharWeight = 0
        NumberFormat = 0

        def merge(self, _: bool) -> None:
            pass

        def setDataArray(self, valeurs: tuple[tuple[object, ...], ...]) -> None:
            ecritures.append(valeurs)

    class FausseFeuille:
        def getCellRangeByPosition(self, *_: int) -> FaussePlage:
            return FaussePlage()

        def getCellByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(String="")

    feuille_zz1 = object()
    feuille_zz2 = object()
    destination = FausseFeuille()

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles: dict[str, object] = {
                "Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ1": feuille_zz1,
                "Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ2": feuille_zz2,
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

    monkeypatch.setattr(
        ods_z2,
        "lire_lignes_valeurs_feuille",
        lambda *_: ({"AJ_Année_Z": 2024.0, "AJ_Mois_Z": "2024-01"},),
    )
    monkeypatch.setattr(
        ods_z2,
        "comparer_lignes_par_periode",
        lambda *_: ((2024.0, "2024-01", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0),),
    )
    monkeypatch.setattr(ods_z2, "obtenir_format", lambda _formats, _format: 42)
    monkeypatch.setattr(ods_z2, "definir_largeur_colonnes", lambda *_: None)
    feuilles = FaussesFeuilles()
    ods_z2.ajouter_CompareMontant(
        SimpleNamespace(getSheets=lambda: feuilles, getNumberFormats=lambda: object()),
        "MASSENA",
        2024,
    )

    assert "Compare_Montant_MASSENA_Z2_ModeZZ1vsModeZZ2_2024" in feuilles.feuilles
    assert ecritures[-1] == ((2024.0, "2024-01", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0),)


def test_ajouter_TotalMontant_ModeZZ1_copie_uniquement_des_valeurs_du_tcd(
    monkeypatch,
) -> None:
    donnees_tcd = (
        ("AJ_Année_Z", "AJ_Mois_Z", "Data", "CARTES", "CHEQUES", "CORRECTION", "ESPECES", "REF./TIROIR"),
        (2024.0, "2024-01", "Somme - D_QUANTITE", 1.0, 2.0, 3.0, 4.0, 5.0),
        ("", "", "Somme - D_MONTANT", 10.0, 20.0, 30.0, 40.0, 50.0),
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
                    EndColumn=7,
                    EndRow=2,
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
        def getCellRangeByPosition(self, *_: int) -> FaussePlageDestination:
            return FaussePlageDestination()

        def getCellByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(String="")

        def getRows(self) -> SimpleNamespace:
            return SimpleNamespace(getByIndex=lambda _: SimpleNamespace(Height=0))

    source = FausseFeuilleSource()
    destination = FausseFeuilleDestination()

    class FaussesFeuilles:
        def __init__(self) -> None:
            self.feuilles: dict[str, object] = {
                "TD_TotalMontant_parMoisAnnee_parNatureTransaction": source
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

    monkeypatch.setattr(ods_z2, "obtenir_format", lambda _formats, _format: 42)
    monkeypatch.setattr(ods_z2, "definir_largeur_colonnes", lambda *_: None)
    feuilles = FaussesFeuilles()
    document = SimpleNamespace(
        getSheets=lambda: feuilles,
        getNumberFormats=lambda: object(),
    )
    ods_z2.ajouter_TotalMontant_ModeZZ1(document, "MASSENA", 2024)
    ods_z2.ajouter_TotalMontant_ModeZZ2(document, "MASSENA", 2024)
    ods_z2.ajouter_TotalMontant_ModeZ(document, "MASSENA", 2024)

    ecritures_attendues = [
        ((
            "AJ_Année_Z",
            "AJ_Mois_Z",
            "D_QUANTITE",
            "D_MONTANT",
            "D_QUANTITE",
            "D_MONTANT",
            "D_QUANTITE",
            "D_MONTANT",
            "D_QUANTITE",
            "D_MONTANT",
            "D_QUANTITE",
            "D_MONTANT",
        ),),
        ((2024.0, "2024-01", 1.0, 10.0, 2.0, 20.0, 3.0, 30.0, 4.0, 40.0, 5.0, 50.0),),
    ]
    assert ecritures == ecritures_attendues * 2
    assert "Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ2" in feuilles.feuilles
    assert "Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZ" not in feuilles.feuilles


def test_generer_classeurs_utilise_les_csv_z2_et_les_noms_contractuels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    staging = tmp_path / "travaux_preliminaires"
    staging.mkdir()
    for annee in (2023, 2024, 2025):
        for boutique in ("MASSENA", "MATURIN"):
            (staging / f"Z2_TransactionsMois_TOUS_{annee}_{boutique}.csv").write_text(
                "|".join(ods_z2.COLONNES_Z2) + "\n",
                encoding="utf-8-sig",
            )

    appels: list[tuple[str, Path]] = []

    def creer(
        _: object,
        __: str,
        destination: Path,
        nom_feuille: str,
        chemin_csv: Path,
        *,
        boutique: str,
        annee: int,
    ) -> None:
        appels.append((nom_feuille, chemin_csv))
        assert nom_feuille == FeuilleZ2Transactions.TRANSACTIONS.pour(boutique, annee)
        destination.write_bytes(b"ods")

    monkeypatch.setattr(ods_z2, "creer_et_enregistrer_classeur", creer)
    resultats = ods_z2.generer_classeurs(staging, tmp_path / "sortie", uno=object())

    assert set(resultats) == {
        (annee, boutique)
        for annee in (2023, 2024, 2025)
        for boutique in ("MASSENA", "MATURIN")
    }
    assert {nom_feuille for nom_feuille, _ in appels} == {
        FeuilleZ2Transactions.TRANSACTIONS.pour(boutique, annee)
        for annee in (2023, 2024, 2025)
        for boutique in ("MASSENA", "MATURIN")
    }
    assert {chemin.name for chemin in resultats.values()} == {
        f"TTS_Z2_TransactionsMois_TOUS_{annee}_{boutique}.ods"
        for annee in (2023, 2024, 2025)
        for boutique in ("MASSENA", "MATURIN")
    }
