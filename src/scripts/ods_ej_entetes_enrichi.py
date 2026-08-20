"""Enrichit les feuilles d'entêtes EJ nécessaires aux agrégats mensuels."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from shared.constantes import BOUTIQUES, FeuilleEjEntetes
from shared.ods_helpers import (
    connecter_uno,
    copier_feuille,
    definir_largeur_colonnes,
    demarrer_libreoffice,
    obtenir_format,
    proprietes,
    python_pyuno_defaut,
    pyuno_disponible,
)


COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT = (
    "AJ_TOTAL_HT",
    "AJ_TOTAL_TVA_20",
    "AJ_ANNEE",
    "AJ_MOIS",
)
FORMAT_NOMBRE = "0.00"
DATE_ORIGINE_CALC = date(1899, 12, 30)
COLONNES_REQUISES = (
    "E_HT1",
    "E_HT2",
    "E_HT3",
    "E_HT4",
    "E_HT_NON_TAXABLE",
    "E_TVA1",
    "E_DATE_TICKET",
)
CHAMPS_LIGNES_TOTAL_ENCT_TTC = ("AJ_ANNEE", "AJ_MOIS")
CHAMPS_DONNEES_TOTAL_ENCT_TTC = (
    "E_TTC",
    "E_MDP_CB",
    "E_MDP_CHEQUES",
    "E_MDP_ESPECES",
)
COLONNES_ENCTS_MENSUELS = (
    *CHAMPS_LIGNES_TOTAL_ENCT_TTC,
    *CHAMPS_DONNEES_TOTAL_ENCT_TTC,
)


def _lettre_colonne(index: int) -> str:
    """Retourne la référence Calc (A, B, ..., AA) d'un index de colonne zéro-indexé."""
    resultat = ""
    index += 1
    while index:
        index, reste = divmod(index - 1, 26)
        resultat = chr(ord("A") + reste) + resultat
    return resultat


def _annee_mois_depuis_date_calc(cellule: Any) -> tuple[str, str]:
    """Retourne année et mois texte depuis une cellule date Calc non vide."""
    if cellule.String == "" and cellule.Value == 0:
        return "", ""
    date_ticket = DATE_ORIGINE_CALC + timedelta(days=cellule.Value)
    return date_ticket.strftime("%Y"), date_ticket.strftime("%Y-%m")


def ajouter_CplteAnneeMoisTotal(document: Any, boutique: str) -> None:
    """Copie les entêtes EJ triées et ajoute les montants et périodes mensuels.

    ``E_DATE_TICKET`` est une date Calc, donc une valeur numérique UNO avec un
    format de date ; les deux colonnes de période reçoivent des chaînes texte
    calculées en Python, sans formule Calc.
    """
    feuille = copier_feuille(
        document,
        FeuilleEjEntetes.TRI_NUM_INTERNE.pour(boutique),
        FeuilleEjEntetes.CPLTE_ANNEE_MOIS.pour(boutique),
    )

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    derniere_ligne = adresse.EndRow
    entetes_source = feuille.getCellRangeByPosition(
        0, 0, adresse.EndColumn, 0
    ).getDataArray()[0]
    index_colonnes = {str(nom): index for index, nom in enumerate(entetes_source)}
    manquantes = set(COLONNES_REQUISES) - index_colonnes.keys()
    if manquantes:
        raise ValueError(
            "Colonnes requises absentes de la feuille d'entêtes EJ : "
            + ", ".join(sorted(manquantes))
        )

    colonne_debut = adresse.EndColumn + 1
    plage_entetes = feuille.getCellRangeByPosition(
        colonne_debut,
        0,
        colonne_debut + len(COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT) - 1,
        0,
    )
    plage_entetes.setDataArray((COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT,))
    plage_entetes.CharWeight = 150

    if derniere_ligne >= 1:
        references = {nom: _lettre_colonne(index) for nom, index in index_colonnes.items()}
        formules = tuple(
            (
                "=SUM("
                f"{references['E_HT1']}{ligne}:{references['E_HT4']}{ligne};"
                f"{references['E_HT_NON_TAXABLE']}{ligne})",
                f"={references['E_TVA1']}{ligne}",
            )
            for ligne in range(2, derniere_ligne + 2)
        )
        plage_formules = feuille.getCellRangeByPosition(
            colonne_debut,
            1,
            colonne_debut + 1,
            derniere_ligne,
        )
        plage_formules.setFormulaArray(formules)
        index_date = index_colonnes["E_DATE_TICKET"]
        periodes = tuple(
            _annee_mois_depuis_date_calc(feuille.getCellByPosition(index_date, ligne))
            for ligne in range(1, derniere_ligne + 1)
        )
        feuille.getCellRangeByPosition(
            colonne_debut + 2,
            1,
            colonne_debut + 3,
            derniere_ligne,
        ).setDataArray(periodes)
        feuille.getCellRangeByPosition(
            colonne_debut,
            1,
            colonne_debut + 1,
            derniere_ligne,
        ).NumberFormat = obtenir_format(document.getNumberFormats(), FORMAT_NOMBRE)

    definir_largeur_colonnes(
        feuille,
        colonne_debut + len(COLONNES_CPLTE_ANNEE_MOIS_TOTAL_HT),
    )


def ajouter_TotalEnctTtc(document: Any, boutique: str) -> None:
    """Ajoute le DataPilot des encaissements TTC par année et mois."""
    import uno

    nom_source = FeuilleEjEntetes.CPLTE_ANNEE_MOIS.pour(boutique)
    nom_destination = FeuilleEjEntetes.TD_TOTAL_ENCT.pour(boutique)
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(nom_source)
    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse_source = curseur.getRangeAddress()
    entetes_source = feuille_source.getCellRangeByPosition(
        adresse_source.StartColumn,
        adresse_source.StartRow,
        adresse_source.EndColumn,
        adresse_source.StartRow,
    ).getDataArray()[0]
    index_colonnes = {str(nom): index for index, nom in enumerate(entetes_source)}
    champs_requis = set(CHAMPS_LIGNES_TOTAL_ENCT_TTC + CHAMPS_DONNEES_TOTAL_ENCT_TTC)
    manquants = champs_requis - index_colonnes.keys()
    if manquants:
        raise ValueError(
            "Champs requis absents de la feuille d'entêtes EJ enrichie : "
            + ", ".join(sorted(manquants))
        )

    if feuilles.hasByName(nom_destination):
        index_destination = feuilles.getElementNames().index(nom_destination)
        feuilles.removeByName(nom_destination)
    else:
        index_destination = feuilles.getCount()
    feuilles.insertNewByName(nom_destination, index_destination)
    feuille_destination = feuilles.getByName(nom_destination)

    tableaux = feuille_destination.getDataPilotTables()
    descripteur = tableaux.createDataPilotDescriptor()
    descripteur.setPropertyValue("RowGrand", False)
    descripteur.setPropertyValue("ColumnGrand", False)
    descripteur.setPropertyValue("ShowFilterButton", False)
    descripteur.setSourceRange(adresse_source)

    champs = descripteur.getDataPilotFields()
    orientation = "com.sun.star.sheet.DataPilotFieldOrientation"
    fonction = "com.sun.star.sheet.GeneralFunction"
    for nom_champ in CHAMPS_LIGNES_TOTAL_ENCT_TTC:
        champs.getByIndex(index_colonnes[nom_champ]).setPropertyValue(
            "Orientation", uno.Enum(orientation, "ROW")
        )
    for nom_champ in CHAMPS_DONNEES_TOTAL_ENCT_TTC:
        champ = champs.getByIndex(index_colonnes[nom_champ])
        champ.setPropertyValue("Orientation", uno.Enum(orientation, "DATA"))
        champ.setPropertyValue("Function", uno.Enum(fonction, "SUM"))
        champ.setPropertyValue("Name", f"Somme - {nom_champ}")

    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(
        feuille_destination,
        len(CHAMPS_LIGNES_TOTAL_ENCT_TTC) + len(CHAMPS_DONNEES_TOTAL_ENCT_TTC),
    )


def _valeur_numerique(valeur: object) -> float:
    """Retourne une valeur numérique Calc, avec zéro pour les cellules vides."""
    if valeur in (None, ""):
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return float(Decimal(str(valeur)))


def extraire_encts_mensuels_tcd(
    donnees_tcd: tuple[tuple[object, ...], ...],
) -> tuple[tuple[object, ...], ...]:
    """Aplatit les quatre lignes de données du DataPilot pour chaque mois."""
    index_entete = next(
        (
            index
            for index, ligne in enumerate(donnees_tcd)
            if all(champ in ligne for champ in (*CHAMPS_LIGNES_TOTAL_ENCT_TTC, "Data"))
        ),
        None,
    )
    if index_entete is None:
        raise ValueError("En-têtes du tableau croisé des encaissements introuvables")

    entetes = donnees_tcd[index_entete]
    index_annee = entetes.index("AJ_ANNEE")
    index_mois = entetes.index("AJ_MOIS")
    index_donnees = entetes.index("Data")
    index_valeur = index_donnees + 1
    annee_courante: object = ""
    resultats: list[tuple[object, ...]] = []

    for index_ligne, ligne in enumerate(donnees_tcd[index_entete + 1 :], index_entete + 1):
        if ligne[index_donnees] != "Somme - E_TTC":
            continue
        lignes_mois = donnees_tcd[index_ligne : index_ligne + len(CHAMPS_DONNEES_TOTAL_ENCT_TTC)]
        if len(lignes_mois) != len(CHAMPS_DONNEES_TOTAL_ENCT_TTC):
            raise ValueError("Lignes de règlements incomplètes dans le TCD des encaissements")
        libelles = tuple(ligne_mois[index_donnees] for ligne_mois in lignes_mois)
        libelles_attendus = tuple(f"Somme - {champ}" for champ in CHAMPS_DONNEES_TOTAL_ENCT_TTC)
        if libelles != libelles_attendus:
            raise ValueError("Ordre des montants inattendu dans le TCD des encaissements")

        if ligne[index_annee] not in (None, ""):
            annee_courante = ligne[index_annee]
        mois = ligne[index_mois]
        if annee_courante in (None, "") or mois in (None, ""):
            raise ValueError("Période mensuelle incomplète dans le TCD des encaissements")
        resultats.append(
            (
                str(annee_courante),
                str(mois),
                *(_valeur_numerique(ligne_mois[index_valeur]) for ligne_mois in lignes_mois),
            )
        )
    return tuple(resultats)


def ajouter_encts_mensuels(document: Any, boutique: str) -> None:
    """Copie en valeurs les cumuls mensuels aplatis du DataPilot des encaissements."""
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(FeuilleEjEntetes.TD_TOTAL_ENCT.pour(boutique))
    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    donnees_tcd = feuille_source.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()
    lignes = extraire_encts_mensuels_tcd(donnees_tcd)

    nom_destination = FeuilleEjEntetes.ENCT_MENSUELS.pour(boutique)
    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)
    plage_entetes = feuille_destination.getCellRangeByPosition(
        0, 0, len(COLONNES_ENCTS_MENSUELS) - 1, 0
    )
    plage_entetes.setDataArray((COLONNES_ENCTS_MENSUELS,))
    plage_entetes.CharWeight = 150

    if lignes:
        derniere_ligne = len(lignes)
        feuille_destination.getCellRangeByPosition(
            0,
            1,
            len(COLONNES_ENCTS_MENSUELS) - 1,
            derniere_ligne,
        ).setDataArray(lignes)
        feuille_destination.getCellRangeByPosition(
            2,
            1,
            len(COLONNES_ENCTS_MENSUELS) - 1,
            derniere_ligne,
        ).NumberFormat = obtenir_format(document.getNumberFormats(), FORMAT_NOMBRE)

    definir_largeur_colonnes(feuille_destination, len(COLONNES_ENCTS_MENSUELS))


def enrichir_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    *,
    boutique: str,
) -> None:
    """Ajoute la feuille enrichie à un classeur ODS, puis le remplace atomiquement."""
    if not destination.is_file():
        raise FileNotFoundError(f"Classeur ODS introuvable : {destination}")

    with tempfile.TemporaryDirectory(prefix="libreoffice-751-") as repertoire_temporaire:
        temporaire = Path(repertoire_temporaire)
        temporaire_ods = temporaire / destination.name
        shutil.copy2(destination, temporaire_ods)
        processus = demarrer_libreoffice(soffice, temporaire / "profil")
        document = None
        try:
            contexte = connecter_uno(uno)
            bureau = contexte.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", contexte
            )
            document = bureau.loadComponentFromURL(
                uno.systemPathToFileUrl(str(temporaire_ods)),
                "_blank",
                0,
                proprietes(uno, Hidden=True),
            )
            ajouter_CplteAnneeMoisTotal(document, boutique)
            ajouter_TotalEnctTtc(document, boutique)
            ajouter_encts_mensuels(document, boutique)
            document.store()
        finally:
            if document is not None:
                document.close(True)
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()
                processus.wait(timeout=5)

        if not temporaire_ods.is_file():
            raise RuntimeError(f"PyUNO n'a pas produit le fichier attendu : {temporaire_ods}")
        shutil.move(temporaire_ods, destination)


def enrichir_classeurs(
    repertoire_sortie: Path,
    uno: Any,
    soffice: str = "soffice",
) -> dict[str, Path]:
    """Enrichit les deux classeurs ODS d'entêtes EJ déjà générés."""
    resultats: dict[str, Path] = {}
    for boutique in BOUTIQUES:
        destination = repertoire_sortie / f"TTS_EJ_ENTETES_TICKETS_{boutique}.ods"
        enrichir_et_enregistrer_classeur(
            uno,
            soffice,
            destination,
            boutique=boutique,
        )
        resultats[boutique] = destination
    return resultats


def main(argv: list[str] | None = None) -> int:
    """Enrichit les classeurs EJ existants via LibreOffice headless et PyUNO."""
    parser = argparse.ArgumentParser(description=__doc__)
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
        environnement["PYTHONPATH"] = racine_src + os.pathsep + environnement.get(
            "PYTHONPATH", ""
        )
        resultat = subprocess.run(
            [str(python_uno), str(Path(__file__).resolve()), *arguments_relais],
            env=environnement,
        )
        return resultat.returncode

    resultats = enrichir_classeurs(args.sortie, uno, args.soffice)
    for boutique, chemin in resultats.items():
        print(f"{boutique} : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
