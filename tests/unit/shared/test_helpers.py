from types import SimpleNamespace

from shared.constantes import LARGEUR_COLONNE_DEFAUT
from shared.ods_helpers import copier_valeurs_feuille, convertir_valeur_tableau, definir_largeur_colonnes


def test_convertir_valeur_tableau_utilise_la_configuration_des_colonnes() -> None:
    assert convertir_valeur_tableau(
        "000012",
        "numero",
        colonnes_texte={"numero"},
    ) == "000012"
    assert convertir_valeur_tableau(
        "2023-01-02",
        "date",
        colonne_date="date",
    ) == 44_928.0
    assert convertir_valeur_tableau("12.50", "montant") == 12.5


def test_definir_largeur_colonnes_applique_la_largeur_par_defaut() -> None:
    colonnes = [SimpleNamespace(Width=None) for _ in range(3)]
    feuille = SimpleNamespace(
        getColumns=lambda: SimpleNamespace(getByIndex=lambda index: colonnes[index])
    )

    definir_largeur_colonnes(feuille, 2)

    assert [colonne.Width for colonne in colonnes] == [
        LARGEUR_COLONNE_DEFAUT,
        LARGEUR_COLONNE_DEFAUT,
        None,
    ]


def test_copier_valeurs_feuille_ne_copie_que_les_valeurs_utilisees() -> None:
    valeurs = (("entete",), (12.5,))
    ecritures: list[tuple[tuple[int, int, int, int], object]] = []

    class FauxCurseur:
        def gotoEndOfUsedArea(self, _: bool) -> None:
            pass

        def getRangeAddress(self) -> SimpleNamespace:
            return SimpleNamespace(StartColumn=0, StartRow=0, EndColumn=0, EndRow=1)

    class FausseSource:
        def createCursor(self) -> FauxCurseur:
            return FauxCurseur()

        def getCellRangeByPosition(self, *_: int) -> SimpleNamespace:
            return SimpleNamespace(getDataArray=lambda: valeurs)

    class FausseDestination:
        def getCellRangeByPosition(self, *bornes: int) -> SimpleNamespace:
            return SimpleNamespace(setDataArray=lambda donnees: ecritures.append((bornes, donnees)))

    source = FausseSource()
    destination = FausseDestination()
    feuilles = SimpleNamespace(
        getByName=lambda nom: source if nom == "source" else destination,
        hasByName=lambda _: False,
        insertNewByName=lambda *_: None,
        getCount=lambda: 1,
    )

    resultat = copier_valeurs_feuille(SimpleNamespace(getSheets=lambda: feuilles), "source", "destination")

    assert resultat is destination
    assert ecritures == [((0, 0, 0, 1), valeurs)]
