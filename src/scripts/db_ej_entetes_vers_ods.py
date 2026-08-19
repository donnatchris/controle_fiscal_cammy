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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from shared.constantes import BOUTIQUES, CHEMIN_DB, FeuilleEjEntetes
from shared.ods_helpers import (
    copier_feuille,
    ecrire_tableau,
    obtenir_format,
    optimiser_largeur_colonnes,
)

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
    "nomfichier",
    "E_NUM_INTERNE",
    "E_NUM_TICKET",
    "E_DATE_TICKET",
    "E_HEURE_TICKET",
    "E_HT1",
    "E_HT2",
    "E_HT3",
    "E_HT4",
    "E_TVA1",
    "E_TVA2",
    "E_TVA3",
    "E_TVA4",
    "E_HT_NON_TAXABLE",
    "E_TTC",
    "E_MDP_CB",
    "E_MDP_ESPECES",
    "E_MDP_CHEQUES",
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
COLONNES_TEXTE_SEQUENTIALITE = {
    "nomfichier",
    "E_NUM_INTERNE",
    "E_NUM_TICKET",
    "E_HEURE_TICKET",
}
FORMULE_TROU_NUM_TICKET = (
    '=IF(OR(C{ligne}="";C{ligne_precedente}="");"";'
    'IFERROR(VALUE(C{ligne})-VALUE(C{ligne_precedente});""))'
)


def charger_entetes(
    connection: sqlite3.Connection, boutique: str
) -> list[dict[str, object]]:
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
        raise FileNotFoundError(
            "LibreOffice introuvable : installez ou indiquez soffice."
        )
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


def ajouter_TriCrstNumInterne(
    document: Any,
    nom_feuille_source: str,
    boutique: str,
) -> None:
    """Copie la feuille source puis trie la copie par E_NUM_INTERNE croissant."""

    from com.sun.star.util import SortField

    nom_feuille_destination = FeuilleEjEntetes.TRI_NUM_INTERNE.pour(boutique)

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

    feuille = copier_feuille(
        document,
        FeuilleEjEntetes.TRI_NUM_INTERNE.pour(boutique),
        FeuilleEjEntetes.CTRL_COHERENCE.pour(boutique),
    )

    formats = document.getNumberFormats()
    format_nombre = obtenir_format(formats, FORMAT_NOMBRE)

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    derniere_ligne = curseur.getRangeAddress().EndRow

    colonne_debut = len(COLONNES_ENTETES)

    plage_entetes = feuille.getCellRangeByPosition(
        colonne_debut,
        0,
        colonne_debut + len(COLONNES_CTRL_COHERENCE_ENTETE) - 1,
        0,
    )

    plage_entetes.setDataArray(
        (COLONNES_CTRL_COHERENCE_ENTETE,)
    )

    if derniere_ligne >= 1:
        formules = tuple(
            tuple(
                formule.format(ligne=index_ligne + 1)
                for formule in FORMULES_CTRL_COHERENCE_ENTETE
            )
            for index_ligne in range(1, derniere_ligne + 1)
        )

        plage_formules = feuille.getCellRangeByPosition(
            colonne_debut,
            1,
            colonne_debut + len(FORMULES_CTRL_COHERENCE_ENTETE) - 1,
            derniere_ligne,
        )

        plage_formules.setFormulaArray(formules)
        plage_formules.NumberFormat = format_nombre

    optimiser_largeur_colonnes(feuille)


def ajouter_sequentialite(document: Any, boutique: str) -> None:
    """Copie en valeurs les identifiants requis et ajoute les trous de tickets."""

    feuilles = document.getSheets()

    feuille_source = feuilles.getByName(FeuilleEjEntetes.CTRL_COHERENCE.pour(boutique))

    feuilles.insertNewByName(
        FeuilleEjEntetes.SEQUENTIALITE.pour(boutique),
        feuilles.getCount(),
    )

    feuille_destination = feuilles.getByName(FeuilleEjEntetes.SEQUENTIALITE.pour(boutique))

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    derniere_ligne = curseur.getRangeAddress().EndRow

    plage_entetes = feuille_destination.getCellRangeByPosition(
        0,
        0,
        len(COLONNES_SEQUENTIALITE) - 1,
        0,
    )

    plage_entetes.setDataArray((COLONNES_SEQUENTIALITE,))
    plage_entetes.CharWeight = 150

    if derniere_ligne < 1:
        return

    # A:E copiées EN VALEURS en un seul bloc.
    plage_source = feuille_source.getCellRangeByPosition(
        0,
        1,
        4,
        derniere_ligne,
    )

    plage_destination = feuille_destination.getCellRangeByPosition(
        0,
        1,
        4,
        derniere_ligne,
    )

    plage_destination.setDataArray(plage_source.getDataArray())

    # Rétablit le format date sur E_DATE_TICKET.
    index_date = COLONNES_SEQUENTIALITE.index("E_DATE_TICKET")

    plage_dates = feuille_destination.getCellRangeByPosition(
        index_date,
        1,
        index_date,
        derniere_ligne,
    )

    plage_dates.NumberFormat = obtenir_format(
        document.getNumberFormats(),
        FORMAT_DATE,
    )

    # AJ_TROU_NUM_TICKET
    if derniere_ligne >= 2:
        formules = tuple(
            (
                FORMULE_TROU_NUM_TICKET.format(
                    ligne=index_ligne + 1,
                    ligne_precedente=index_ligne,
                ),
            )
            for index_ligne in range(2, derniere_ligne + 1)
        )

        plage_formules = feuille_destination.getCellRangeByPosition(
            5,
            2,
            5,
            derniere_ligne,
        )

        plage_formules.setFormulaArray(formules)

        plage_formules.NumberFormat = obtenir_format(
            document.getNumberFormats(),
            "0",
        )

    optimiser_largeur_colonnes(feuille_destination)


def ajouter_TD_OccurenceNumInterne(document: Any, boutique: str) -> None:
    """Ajoute un tableau croisé Calc comptant les occurrences de numéros internes."""
    import uno

    nom_source = FeuilleEjEntetes.SEQUENTIALITE.pour(boutique)
    nom_destination = FeuilleEjEntetes.TD_OCCURRENCE_NUM_INTERNE.pour(boutique)
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
    champ_donnees.setPropertyValue(
        "Name",
        "Compter - E_NUM_INTERNE",
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
    feuille = copier_feuille(
        document,
        FeuilleEjEntetes.TD_OCCURRENCE_NUM_INTERNE.pour(boutique),
        FeuilleEjEntetes.DOUBLON_NUM_INTERNE.pour(boutique),
    )
    optimiser_largeur_colonnes(feuille)


def ajouter_TD_OccurenceNumTicket(document: Any, boutique: str) -> None:
    """Ajoute un tableau croisé Calc comptant les occurrences de numéros internes."""
    import uno

    nom_source = FeuilleEjEntetes.SEQUENTIALITE.pour(boutique)
    nom_destination = FeuilleEjEntetes.TD_OCCURRENCE_NUM_TICKET.pour(boutique)
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
    champ_donnees.setPropertyValue(
        "Name",
        "Compter - E_NUM_TICKET",
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
    feuille = copier_feuille(
        document,
        FeuilleEjEntetes.TD_OCCURRENCE_NUM_TICKET.pour(boutique),
        FeuilleEjEntetes.DOUBLON_NUM_TICKET.pour(boutique),
    )
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
    with tempfile.TemporaryDirectory(
        prefix="libreoffice-751-"
    ) as repertoire_temporaire:
        temporaire = Path(repertoire_temporaire)
        processus = demarrer_libreoffice(soffice, temporaire / "profil")
        document = None
        try:
            contexte = connecter_uno(uno)
            bureau = contexte.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", contexte
            )
            document = bureau.loadComponentFromURL(
                "private:factory/scalc", "_blank", 0, ()
            )
            feuilles = document.getSheets()

            # Création de la feuille d'entêtes EJ
            print(f"Création de la feuille d'entêtes EJ pour la boutique {boutique}...")
            feuille = feuilles.getByIndex(0)
            feuille.setName(nom_feuille)
            plage_entete = feuille.getCellRangeByPosition(
                0, 0, len(COLONNES_ENTETES) - 1, 0
            )
            plage_entete.setDataArray((COLONNES_ENTETES,))
            plage_entete.CharWeight = 150
            formats = document.getNumberFormats()
            ecrire_tableau(
                feuille,
                rows,
                COLONNES_ENTETES,
                formats,
                colonnes_texte=COLONNES_TEXTE,
                colonne_date=COLONNE_DATE,
                format_date=FORMAT_DATE,
            )
            # Création de la feuille d'entêtes EJ triée par E_NUM_INTERNE
            ajouter_TriCrstNumInterne(
                document,
                nom_feuille_source=nom_feuille,
                boutique=boutique,
            )
            # Création de la feuille d'entêtes EJ avec calculs de cohérence
            print(
                f"Ajout des calculs de cohérence d'entête pour la boutique {boutique}..."
            )
            ajouter_CtrlCoherenceEntete(document, boutique)
            # Création de la feuille d'entêtes EJ dédiée aux ruptures de tickets
            print(
                f"Ajout de la feuille de sequentialité pour la boutique {boutique}..."
            )
            ajouter_sequentialite(document, boutique)
            # Création du tableau croisé des occurrences de numéros internes
            print(
                f"Ajout du tableau croisé des occurrences de numéros internes pour la boutique {boutique}..."
            )
            ajouter_TD_OccurenceNumInterne(document, boutique)
            # Création de la feuille listant les doublons de numéros internes
            print(
                f"Ajout de la feuille listant les doublons de numéros internes pour la boutique {boutique}..."
            )
            ajouter_DoublonNumInterne(document, boutique)
            # Création du tableau croisé des occurrences de numéros de tickets
            print(
                f"Ajout du tableau croisé des occurrences de numéros de tickets pour la boutique {boutique}..."
            )
            ajouter_TD_OccurenceNumTicket(document, boutique)
            # Création de la feuille listant les doublons de numéros de tickets
            print(
                f"Ajout de la feuille listant les doublons de numéros de tickets pour la boutique {boutique}..."
            )
            ajouter_DoublonTicket(document, boutique)

            temporaire_ods = temporaire / destination.name
            document.storeAsURL(
                uno.systemPathToFileUrl(str(temporaire_ods)),
                proprietes(uno, FilterName="calc8"),
            )
            if not temporaire_ods.is_file():
                raise RuntimeError(
                    f"PyUNO n'a pas produit le fichier attendu : {temporaire_ods}"
                )
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
            nom_feuille = FeuilleEjEntetes.ENTETES.pour(boutique)
            rows = charger_entetes(connection, boutique)
            destination = repertoire_sortie / f"EJ_ENTETES_TICKETS_{boutique}.ods"
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
        environnement["PYTHONPATH"] = (
            racine_src + os.pathsep + environnement.get("PYTHONPATH", "")
        )
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
