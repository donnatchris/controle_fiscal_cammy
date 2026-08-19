"""Génère les deux feuilles d'entrée EJ d'un classeur ODS par boutique."""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from shared.constantes import BOUTIQUES, CHEMIN_DB, NOM_COMPLET, resoudre_classeur_751


# SELECT de référence : il constitue la source directe des feuilles *_0.
SQL_ENTETES_TICKETS = """
    SELECT
        nomFichier AS nomfichier,
        E_NUM_INTERNE,
        E_NUM_TICKET,
        E_DATE_TICKET,
        E_HEURE_TICKET,
        E_HT1,
        E_HT2,
        E_HT3,
        E_HT4,
        E_TVA1,
        E_TVA2,
        E_TVA3,
        E_TVA4,
        E_HT_NON_TAXABLE,
        E_TTC,
        E_MDP_CB,
        E_MDP_ESPECES,
        E_MDP_CHEQUES
    FROM tickets
    WHERE boutique = ?
      AND type IN ('REG', '_R_F')
      AND NULLIF(TRIM(E_NUM_TICKET), '') IS NOT NULL
    ORDER BY E_DATE_TICKET, E_HEURE_TICKET, E_NUM_INTERNE
"""

COLONNES_ENTETES = (
    "nomfichier", "E_NUM_INTERNE", "E_NUM_TICKET", "E_DATE_TICKET", "E_HEURE_TICKET",
    "E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_TVA1", "E_TVA2", "E_TVA3", "E_TVA4",
    "E_HT_NON_TAXABLE", "E_TTC", "E_MDP_CB", "E_MDP_ESPECES", "E_MDP_CHEQUES",
)
COLONNES_TEXTE = {"nomfichier", "E_NUM_INTERNE", "E_NUM_TICKET", "E_HEURE_TICKET"}
COLONNE_DATE = "E_DATE_TICKET"
FORMAT_DATE = "YYYY-MM-DD"
FORMAT_NOMBRE = "0.00"
PORT_UNO = 2002

COLONNES_CTRL_COHERENCE_ENTETE = (
    "AJ_TVA1_CALCULE",
    "AJ_ECART_TVA1",
    "AJ_TTC_CALCULE",
    "AJ_ECART_TTC",
    "AJ_SOLDE_DU",
)
FORMULES_CTRL_COHERENCE_ENTETE = (
    "=F{ligne}*20%",
    "=J{ligne}-S{ligne}",
    "=F{ligne}+J{ligne}",
    "=O{ligne}-U{ligne}",
    "=O{ligne}-(P{ligne}+R{ligne})",
)
COLONNES_SEQUENTIALITE = (
    "nomfichier",
    "E_NUM_INTERNE",
    "E_NUM_TICKET",
    "E_DATE_TICKET",
    "E_HEURE_TICKET",
    "AJ_TROU_NUM_TICKET",
)
COLONNES_TEXTE_SEQUENTIALITE = {"nomfichier", "E_NUM_INTERNE", "E_NUM_TICKET", "E_HEURE_TICKET"}
FORMULE_TROU_NUM_TICKET = (
    '=IF(OR(C{ligne}="";C{ligne_precedente}="");"";'
    'IFERROR(VALUE(C{ligne})-VALUE(C{ligne_precedente});""))'
)


def charger_entetes(connection: sqlite3.Connection, boutique: str) -> list[dict[str, object]]:
    """Lit uniquement les entêtes de vente destinés à la feuille *_0 demandée."""
    return [dict(row) for row in connection.execute(SQL_ENTETES_TICKETS, (boutique,))]


def proprietes(uno: Any, **valeurs: object) -> tuple[Any, ...]:
    """Crée un tuple de PropertyValue UNO à partir d'un dictionnaire de valeurs."""
    resultat = []
    for nom, valeur in valeurs.items():
        propriete = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        propriete.Name = nom
        propriete.Value = valeur
        resultat.append(propriete)
    return tuple(resultat)


def demarrer_libreoffice(soffice: str, profil: Path) -> subprocess.Popen[str]:
    """Démarre une instance Calc isolée, pilotée exclusivement par PyUNO."""
    executable = shutil.which(soffice) if Path(soffice).name == soffice else soffice
    if not executable:
        raise FileNotFoundError("LibreOffice introuvable : installez ou indiquez soffice.")
    return subprocess.Popen(
        [
            executable,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            f"--accept=socket,host=127.0.0.1,port={PORT_UNO};urp;StarOffice.ComponentContext",
            f"-env:UserInstallation={profil.as_uri()}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def connecter_uno(uno: Any, delai_secondes: float = 15) -> Any:
    """Se connecte à l'instance LibreOffice via PyUNO, avec un délai d'attente."""
    contexte_local = uno.getComponentContext()
    resolveur = contexte_local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", contexte_local
    )
    url = f"uno:socket,host=127.0.0.1,port={PORT_UNO};urp;StarOffice.ComponentContext"
    fin = time.monotonic() + delai_secondes
    while time.monotonic() < fin:
        try:
            return resolveur.resolve(url)
        except Exception:  # LibreOffice ouvre le socket de manière asynchrone.
            time.sleep(0.1)
    raise RuntimeError("Impossible de se connecter à LibreOffice via PyUNO.")


def obtenir_format(formats, format_chaine: str) -> int:
    """Retourne la clé de format UNO correspondant à la chaîne donnée."""
    from com.sun.star.lang import Locale

    locale = Locale()
    locale.Language = "fr"
    locale.Country = "FR"

    cle = formats.queryKey(format_chaine, locale, False)

    if cle == -1:
        cle = formats.addNew(format_chaine, locale)

    return cle


def ecrire_valeur(
    cellule: Any,
    valeur: object | None,
    colonne: str,
    formats: Any,
) -> None:
    """Écrit la valeur dans la cellule UNO, en choisissant le type et le format."""
    if valeur in (None, ""):
        return

    texte = str(valeur)

    if colonne in COLONNES_TEXTE:
        cellule.String = texte

    elif colonne == COLONNE_DATE:
        valeur_date = date.fromisoformat(texte)

        cellule.Value = (
            valeur_date - date(1899, 12, 30)
        ).days

        cellule.NumberFormat = obtenir_format(
            formats,
            FORMAT_DATE,
        )

    else:
        # L'API UNO attend un double.
        cellule.Value = float(Decimal(texte))


def optimiser_largeur_colonnes(feuille: Any) -> None:
    """Optimise la largeur de toutes les colonnes de la feuille."""
    colonnes = feuille.getColumns()

    for index in range(colonnes.getCount()):
        colonnes.getByIndex(index).OptimalWidth = True


def copier_feuille(
    document: Any,
    nom_source: str,
    nom_destination: str,
) -> Any:
    """Copie une feuille et retourne la nouvelle feuille."""
    feuilles = document.getSheets()

    feuilles.copyByName(
        nom_source,
        nom_destination,
        feuilles.getCount(),
    )

    return feuilles.getByName(nom_destination)


def ajouter_TriCrstNumInterne(
    document: Any,
    nom_feuille_source: str,
    boutique: str,
) -> None:
    """Copie la feuille source puis trie la copie par E_NUM_INTERNE croissant."""

    from com.sun.star.util import SortField

    nom_feuille_destination = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)[1]

    feuille = copier_feuille(
        document,
        nom_feuille_source,
        nom_feuille_destination,
    )

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    plage = curseur

    champ_tri = SortField()
    champ_tri.Field = COLONNES_ENTETES.index("E_NUM_INTERNE")
    champ_tri.SortAscending = True

    descripteur_tri = plage.createSortDescriptor()

    for propriete in descripteur_tri:
        if propriete.Name == "SortFields":
            propriete.Value = (champ_tri,)
        elif propriete.Name == "ContainsHeader":
            propriete.Value = True

    plage.sort(descripteur_tri)
    optimiser_largeur_colonnes(feuille)



def ajouter_CtrlCoherenceEntete(document: Any, boutique: str) -> None:
    """Copie la feuille triée et ajoute les calculs de cohérence d'entête."""
    noms_feuilles = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)
    feuille = copier_feuille(document, noms_feuilles[1], noms_feuilles[2])
    formats = document.getNumberFormats()
    format_nombre = obtenir_format(formats, FORMAT_NOMBRE)

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    derniere_ligne = curseur.getRangeAddress().EndRow
    colonne_debut = len(COLONNES_ENTETES)

    for index, colonne in enumerate(COLONNES_CTRL_COHERENCE_ENTETE):
        feuille.getCellByPosition(colonne_debut + index, 0).String = colonne

    for index_ligne in range(1, derniere_ligne + 1):
        ligne_calc = index_ligne + 1
        for index_colonne, formule in enumerate(FORMULES_CTRL_COHERENCE_ENTETE):
            cellule = feuille.getCellByPosition(colonne_debut + index_colonne, index_ligne)
            cellule.Formula = formule.format(ligne=ligne_calc)
            cellule.NumberFormat = format_nombre
    optimiser_largeur_colonnes(feuille)



def ajouter_sequentialite(document: Any, boutique: str) -> None:
    """Copie en valeurs les identifiants requis et ajoute les trous de tickets."""
    noms_feuilles = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(noms_feuilles[2])
    feuilles.insertNewByName(noms_feuilles[3], feuilles.getCount())
    feuille_destination = feuilles.getByName(noms_feuilles[3])
    format_entier = obtenir_format(
        document.getNumberFormats(),
        "0",
    )

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    derniere_ligne = curseur.getRangeAddress().EndRow

    for index_colonne, colonne in enumerate(COLONNES_SEQUENTIALITE):
        cellule = feuille_destination.getCellByPosition(index_colonne, 0)
        cellule.String = colonne
        cellule.CharWeight = 150

    for index_ligne in range(1, derniere_ligne + 1):
        for index_colonne, colonne in enumerate(COLONNES_SEQUENTIALITE[:-1]):
            source = feuille_source.getCellByPosition(index_colonne, index_ligne)
            destination = feuille_destination.getCellByPosition(index_colonne, index_ligne)
            destination.NumberFormat = source.NumberFormat
            if colonne in COLONNES_TEXTE_SEQUENTIALITE:
                destination.String = source.String
            elif source.Formula:
                destination.Value = source.Value

        if index_ligne == 1:
            continue
        cellule_trou = feuille_destination.getCellByPosition(5, index_ligne)
        cellule_trou.Formula = FORMULE_TROU_NUM_TICKET.format(
            ligne=index_ligne + 1,
            ligne_precedente=index_ligne,
        )
        cellule_trou.NumberFormat = format_entier
    optimiser_largeur_colonnes(feuille_destination)


def ajouter_TD_OccurenceNumInterne(document: Any, boutique: str) -> None:
    """Ajoute un tableau croisé Calc comptant les occurrences de numéros internes."""
    import uno

    noms_feuilles = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)
    nom_source = noms_feuilles[3]
    nom_destination = noms_feuilles[4]
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(nom_source)
    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    tableaux = feuille_destination.getDataPilotTables()
    descripteur = tableaux.createDataPilotDescriptor()
    descripteur.setPropertyValue("RowGrand", False)
    descripteur.setPropertyValue("ColumnGrand", False)
    descripteur.setPropertyValue("ShowFilterButton", False)
    descripteur.setSourceRange(curseur.getRangeAddress())

    index_num_interne = COLONNES_SEQUENTIALITE.index("E_NUM_INTERNE")
    champs = descripteur.getDataPilotFields()
    champ_ligne = champs.getByIndex(index_num_interne)
    champ_ligne.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW"),
    )
    champ_donnees = champs.getByIndex(index_num_interne)
    champ_donnees.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA"),
    )
    champ_donnees.setPropertyValue(
        "Function",
        uno.Enum("com.sun.star.sheet.GeneralFunction", "COUNT"),
    )

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    optimiser_largeur_colonnes(feuille_destination)


def ajouter_DoublonNumInterne(document: Any, boutique: str) -> None:
    """Ajoute une feuille Calc listant les doublons de numéros internes."""
    noms_feuilles = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)
    feuille = copier_feuille(document, noms_feuilles[4], noms_feuilles[5])
    optimiser_largeur_colonnes(feuille)


def ajouter_TD_OccurenceNumTicket(document: Any, boutique: str) -> None:
    """Ajoute un tableau croisé Calc comptant les occurrences de numéros internes."""
    import uno

    noms_feuilles = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)
    nom_source = noms_feuilles[3]
    nom_destination = noms_feuilles[6]
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(nom_source)
    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    tableaux = feuille_destination.getDataPilotTables()
    descripteur = tableaux.createDataPilotDescriptor()
    descripteur.setPropertyValue("RowGrand", False)
    descripteur.setPropertyValue("ColumnGrand", False)
    descripteur.setPropertyValue("ShowFilterButton", False)
    descripteur.setSourceRange(curseur.getRangeAddress())

    index_num_interne = COLONNES_SEQUENTIALITE.index("E_NUM_TICKET")
    champs = descripteur.getDataPilotFields()
    champ_ligne = champs.getByIndex(index_num_interne)
    champ_ligne.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW"),
    )
    champ_donnees = champs.getByIndex(index_num_interne)
    champ_donnees.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA"),
    )
    champ_donnees.setPropertyValue(
        "Function",
        uno.Enum("com.sun.star.sheet.GeneralFunction", "COUNT"),
    )

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    optimiser_largeur_colonnes(feuille_destination)


def ajouter_DoublonTicket(document: Any, boutique: str) -> None:
    """Ajoute une feuille Calc listant les doublons de numéros de tickets."""
    noms_feuilles = resoudre_classeur_751(
        "ej_entetes", boutique=boutique
    ).noms_feuilles(NOM_COMPLET)
    feuille = copier_feuille(document, noms_feuilles[6], noms_feuilles[7])
    optimiser_largeur_colonnes(feuille)


def creer_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    nom_feuille: str,
    rows: list[Mapping[str, object]],
    *,
    boutique: str,
) -> None:
    """Crée directement le document Calc via PyUNO et enregistre l'ODS."""
    with tempfile.TemporaryDirectory(prefix="libreoffice-751-") as repertoire_temporaire:
        temporaire = Path(repertoire_temporaire)
        processus = demarrer_libreoffice(soffice, temporaire / "profil")
        document = None
        try:
            contexte = connecter_uno(uno)
            bureau = contexte.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", contexte)
            document = bureau.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
            feuilles = document.getSheets()

            # Création de la feuille d'entêtes EJ
            print(f"Création de la feuille d'entêtes EJ pour la boutique {boutique}...")
            feuille = feuilles.getByIndex(0)
            feuille.setName(nom_feuille)
            plage_entete = feuille.getCellRangeByPosition(0, 0, len(COLONNES_ENTETES) - 1, 0)
            plage_entete.setDataArray((COLONNES_ENTETES,))
            plage_entete.CharWeight = 150
            formats = document.getNumberFormats()
            for index_ligne, row in enumerate(rows, start=1):
                for index_colonne, colonne in enumerate(COLONNES_ENTETES):
                    ecrire_valeur(feuille.getCellByPosition(index_colonne, index_ligne), row.get(colonne), colonne, formats)
            # Création de la feuille d'entêtes EJ triée par E_NUM_INTERNE
            ajouter_TriCrstNumInterne(
                document,
                nom_feuille_source=nom_feuille,
                boutique=boutique,
            )
            # Création de la feuille d'entêtes EJ avec calculs de cohérence
            print(f"Ajout des calculs de cohérence d'entête pour la boutique {boutique}...")
            ajouter_CtrlCoherenceEntete(document, boutique)
            # Création de la feuille d'entêtes EJ dédiée aux ruptures de tickets
            print(f"Ajout de la feuille de sequentialité pour la boutique {boutique}...")
            ajouter_sequentialite(document, boutique)
            # Création du tableau croisé des occurrences de numéros internes
            print(f"Ajout du tableau croisé des occurrences de numéros internes pour la boutique {boutique}...")
            ajouter_TD_OccurenceNumInterne(document, boutique)
            # Création de la feuille listant les doublons de numéros internes
            print(f"Ajout de la feuille listant les doublons de numéros internes pour la boutique {boutique}...")
            ajouter_DoublonNumInterne(document, boutique)
            # Création du tableau croisé des occurrences de numéros de tickets
            print(f"Ajout du tableau croisé des occurrences de numéros de tickets pour la boutique {boutique}...")
            ajouter_TD_OccurenceNumTicket(document, boutique)
            # Création de la feuille listant les doublons de numéros de tickets
            print(f"Ajout de la feuille listant les doublons de numéros de tickets pour la boutique {boutique}...")
            ajouter_DoublonTicket(document, boutique)
            
            temporaire_ods = temporaire / destination.name
            document.storeAsURL(
                uno.systemPathToFileUrl(str(temporaire_ods)),
                proprietes(uno, FilterName="calc8"),
            )
            if not temporaire_ods.is_file():
                raise RuntimeError(f"PyUNO n'a pas produit le fichier attendu : {temporaire_ods}")
            shutil.move(temporaire_ods, destination)
        finally:
            if document is not None:
                document.close(True)
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()
                processus.wait(timeout=5)


def generer_classeurs(
    chemin_base: Path,
    repertoire_sortie: Path,
    uno: Any,
    soffice: str = "soffice",
) -> dict[str, Path]:
    """Génère uniquement les deux classeurs d'entêtes EJ et leur feuille *_0."""
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    resultats: dict[str, Path] = {}
    with sqlite3.connect(chemin_base) as connection:
        connection.row_factory = sqlite3.Row
        for boutique in BOUTIQUES:
            definition = resoudre_classeur_751("ej_entetes", boutique=boutique)
            nom_feuille = definition.noms_feuilles(NOM_COMPLET)[0]
            rows = charger_entetes(connection, boutique)
            destination = repertoire_sortie / definition.nom_fichier
            creer_et_enregistrer_classeur(
                uno,
                soffice,
                destination,
                nom_feuille,
                rows,
                boutique=boutique,
            )
            resultats[boutique] = destination
    return resultats


def pyuno_disponible() -> Any | None:
    try:
        import uno
    except ModuleNotFoundError:
        return None
    return uno


def python_pyuno_defaut() -> Path:
    chemin = os.environ.get("LIBREOFFICE_PYTHON")
    if chemin:
        return Path(chemin)
    candidat_macos = Path("/Applications/LibreOffice.app/Contents/Resources/python")
    if candidat_macos.is_file():
        return candidat_macos
    raise FileNotFoundError(
        "Interpréteur Python PyUNO introuvable : indiquez --python-uno ou LIBREOFFICE_PYTHON."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(CHEMIN_DB))
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--soffice", default="soffice")
    parser.add_argument("--python-uno", type=Path, default=None)
    args = parser.parse_args(argv)
    uno = pyuno_disponible()
    if uno is None:
        python_uno = args.python_uno or python_pyuno_defaut()
        arguments_relais = list(argv or sys.argv[1:])
        if args.soffice == "soffice" and not shutil.which("soffice"):
            soffice_macos = python_uno.parent.parent / "MacOS" / "soffice"
            if soffice_macos.is_file():
                arguments_relais.extend(["--soffice", str(soffice_macos)])
        environnement = os.environ.copy()
        racine_src = str(Path(__file__).resolve().parents[1])
        environnement["PYTHONPATH"] = racine_src + os.pathsep + environnement.get("PYTHONPATH", "")
        resultat = subprocess.run(
            [str(python_uno), str(Path(__file__).resolve()), *arguments_relais],
            env=environnement,
        )
        return resultat.returncode
    resultats = generer_classeurs(args.base, args.sortie, uno, args.soffice)
    for boutique, chemin in resultats.items():
        print(f"{boutique} : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
