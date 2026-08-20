"""Génère les feuilles d'entrée Z1 d'un classeur ODS par année et boutique."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from scripts.ods_z2 import appliquer_filtre_mode_data_pilot
from shared.constantes import ANNEES, BOUTIQUES, SEPARATEUR_CSV, FeuilleZ1SyntheseMois
from shared.ods_helpers import (
    demarrer_libreoffice,
    connecter_uno,
    copier_feuille,
    definir_largeur_colonnes,
    ecrire_tableau,
    obtenir_format,
    proprietes,
    python_pyuno_defaut,
    pyuno_disponible,
)
from shared.rapport_execution import enregistrer_compteur_traitement

COLONNES_Z1 = (
    "nomfichier",
    "E_MODELE",
    "E_MACHINE",
    "E_RAPPORT",
    "E_FICHIER",
    "E_MODE",
    "E_COMPTEUR_Z",
    "E_DATE",
    "E_HEURE",
    "D_ENREGISTREMENT",
    "D_DESIGNATION",
    "D_QUANTITE",
    "D_MONTANT",
)
COLONNES_TEXTE = {
    "nomfichier",
    "E_MODELE",
    "E_MACHINE",
    "E_RAPPORT",
    "E_FICHIER",
    "E_MODE",
    "E_COMPTEUR_Z",
    "E_HEURE",
    "D_ENREGISTREMENT",
    "D_DESIGNATION",
}
COLONNE_DATE = "E_DATE"
COLONNE_MONTANT = "D_MONTANT"
FORMAT_DATE = "YYYY-MM-DD"
FORMAT_MONTANT = "0.00"
COLONNES_CPLTE_ANNEE_MOIS_Z = ("AJ_Année_Z", "AJ_Mois_Z")
MOTIF_PERIODE_NOM_FICHIER = re.compile(
    r"_(?P<mois>0[1-9]|1[0-2])(?P<annee>\d{4})(?:_|\s*\.)",
    re.IGNORECASE,
)
DESIGNATIONS_TOTAL_MONTANT = (
    "CA BRUT",
    "CA NET",
    "CB.TIROIR",
    "CHQ.TIROIR",
    "ESP.TIROIR",
    "HORS TAXES 1",
    "TVA 1",
)
ALIASES_DESIGNATIONS_TOTAL_MONTANT = {
    designation: (designation,)
    for designation in DESIGNATIONS_TOTAL_MONTANT
}
# Le libellé contractuel est au pluriel, tandis que les fichiers Z1 fournis
# contiennent systématiquement « HORS TAXE 1 » au singulier.
ALIASES_DESIGNATIONS_TOTAL_MONTANT["HORS TAXES 1"] = (
    "HORS TAXES 1",
    "HORS TAXE 1",
)
COLONNES_TOTAL_MONTANT_MODE_ZZ1 = (
    "AJ_Année_Z",
    "AJ_Mois_Z",
    *DESIGNATIONS_TOTAL_MONTANT,
)
FEUILLES_TOTAL_MONTANT_PAR_MODE = {
    "ZZ1": FeuilleZ1SyntheseMois.Z1_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ1,
    "ZZ2": FeuilleZ1SyntheseMois.Z1_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ2,
    "Z": FeuilleZ1SyntheseMois.Z1_TOTAL_MOIS_ANNEE_NATURE_MODE_Z,
}
EXCEPTIONS_MODE_Z1 = {
    ("ZZ1", "MATURIN", 2024),
    ("ZZ2", "MATURIN", 2024),
    ("Z", "MASSENA", 2024),
}


def add_Synthese_0(document: Any, nom_feuille: str, chemin_csv: Path) -> None:
    """Crée la feuille Z1 initiale en copiant les données du CSV préparatoire."""
    with chemin_csv.open(encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.DictReader(fichier, delimiter=SEPARATEUR_CSV)
        if tuple(lecteur.fieldnames or ()) != COLONNES_Z1:
            raise ValueError(f"Colonnes inattendues dans {chemin_csv}")
        lignes = list(lecteur)

    feuille = document.getSheets().getByIndex(0)
    feuille.setName(nom_feuille)

    plage_entete = feuille.getCellRangeByPosition(0, 0, len(COLONNES_Z1) - 1, 0)
    plage_entete.setDataArray((COLONNES_Z1,))
    plage_entete.CharWeight = 150

    formats = document.getNumberFormats()
    ecrire_tableau(
        feuille,
        lignes,
        COLONNES_Z1,
        formats,
        colonnes_texte=COLONNES_TEXTE,
        colonne_date=COLONNE_DATE,
        format_date=FORMAT_DATE,
    )
    if lignes:
        derniere_ligne = len(lignes)
        index_montant = COLONNES_Z1.index(COLONNE_MONTANT)
        feuille.getCellRangeByPosition(
            index_montant, 1, index_montant, derniere_ligne
        ).NumberFormat = obtenir_format(formats, FORMAT_MONTANT)

    definir_largeur_colonnes(feuille, len(COLONNES_Z1))


def periode_cloture_depuis_nom_fichier(nom_fichier: object) -> tuple[str, str]:
    """Extrait l'année et le mois de clôture du nom d'un rapport Z1."""
    correspondance = MOTIF_PERIODE_NOM_FICHIER.search(str(nom_fichier))
    if correspondance is None:
        raise ValueError(f"Période de clôture absente du nom de fichier : {nom_fichier}")
    annee = correspondance.group("annee")
    return annee, f"{annee}-{correspondance.group('mois')}"


def ajouter_Cplte(document: Any, boutique: str, annee: int) -> None:
    """Copie la feuille Z1 initiale et complète sa période de clôture en texte."""
    feuille = copier_feuille(
        document,
        FeuilleZ1SyntheseMois.SYNTHESE_MOIS.pour(boutique, annee),
        FeuilleZ1SyntheseMois.CPLTE_ANNEE_MOIS.pour(boutique, annee),
    )
    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    derniere_ligne = adresse.EndRow
    colonne_debut = len(COLONNES_Z1)

    plage_entetes = feuille.getCellRangeByPosition(
        colonne_debut,
        0,
        colonne_debut + len(COLONNES_CPLTE_ANNEE_MOIS_Z) - 1,
        0,
    )
    plage_entetes.setDataArray((COLONNES_CPLTE_ANNEE_MOIS_Z,))
    plage_entetes.CharWeight = 150

    if derniere_ligne >= 1:
        donnees = feuille.getCellRangeByPosition(0, 0, adresse.EndColumn, derniere_ligne).getDataArray()
        entetes = tuple(str(entete) for entete in donnees[0])
        try:
            index_nom_fichier = entetes.index("nomfichier")
        except ValueError as erreur:
            raise ValueError("Colonne nomfichier absente de la feuille Z1 source") from erreur
        periodes = tuple(
            periode_cloture_depuis_nom_fichier(ligne[index_nom_fichier])
            for ligne in donnees[1:]
        )
        feuille.getCellRangeByPosition(
            colonne_debut,
            1,
            colonne_debut + len(COLONNES_CPLTE_ANNEE_MOIS_Z) - 1,
            derniere_ligne,
        ).setDataArray(periodes)

    definir_largeur_colonnes(
        feuille,
        len(COLONNES_Z1) + len(COLONNES_CPLTE_ANNEE_MOIS_Z),
    )


def ajouter_TD_OccurenceEfichier(document: Any, boutique: str, annee: int) -> None:
    """Ajoute le DataPilot des occurrences E_FICHIER/E_MODE par clôture."""
    import uno

    nom_source = FeuilleZ1SyntheseMois.CPLTE_ANNEE_MOIS.pour(boutique, annee)
    nom_destination = (
        FeuilleZ1SyntheseMois.TD_OCCURENCE_E_FICHIER_E_MODE.pour(boutique, annee)
    )
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(nom_source)
    if feuilles.hasByName(nom_destination):
        index_destination = feuilles.getElementNames().index(nom_destination)
        feuilles.removeByName(nom_destination)
    else:
        index_destination = feuilles.getCount()
    feuilles.insertNewByName(nom_destination, index_destination)
    feuille_destination = feuilles.getByName(nom_destination)

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    tableaux = feuille_destination.getDataPilotTables()
    descripteur = tableaux.createDataPilotDescriptor()
    descripteur.setPropertyValue("RowGrand", False)
    descripteur.setPropertyValue("ColumnGrand", False)
    descripteur.setSourceRange(curseur.getRangeAddress())

    colonnes_source = COLONNES_Z1 + COLONNES_CPLTE_ANNEE_MOIS_Z
    champs = descripteur.getDataPilotFields()
    orientation = "com.sun.star.sheet.DataPilotFieldOrientation"
    fonction = "com.sun.star.sheet.GeneralFunction"
    for nom_champ, orientation_champ in (
        ("AJ_Année_Z", "ROW"),
        ("AJ_Mois_Z", "ROW"),
        ("E_DATE", "ROW"),
        ("E_FICHIER", "COLUMN"),
        ("E_MODE", "COLUMN"),
    ):
        champ = champs.getByIndex(colonnes_source.index(nom_champ))
        champ.setPropertyValue(
            "Orientation",
            uno.Enum(orientation, orientation_champ),
        )

    champ_donnees = champs.getByIndex(COLONNES_Z1.index("E_MODE"))
    champ_donnees.setPropertyValue(
        "Orientation",
        uno.Enum(orientation, "DATA"),
    )
    champ_donnees.setPropertyValue(
        "Function",
        uno.Enum(fonction, "COUNT"),
    )
    champ_donnees.setPropertyValue("Name", "Compter - E_MODE")

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(feuille_destination, 8)


def ajouter_TD_TotalMontant(document: Any, boutique: str, annee: int) -> None:
    """Ajoute le DataPilot des montants Z1 par mois et désignation."""
    import uno

    nom_source = FeuilleZ1SyntheseMois.CPLTE_ANNEE_MOIS.pour(boutique, annee)
    nom_destination = (
        FeuilleZ1SyntheseMois.TD_TOTAL_MONTANT_PAR_MOIS_ANNEE.pour(
            boutique,
            annee,
        )
    )
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(nom_source)
    if feuilles.hasByName(nom_destination):
        index_destination = feuilles.getElementNames().index(nom_destination)
        feuilles.removeByName(nom_destination)
    else:
        index_destination = feuilles.getCount()
    feuilles.insertNewByName(nom_destination, index_destination)
    feuille_destination = feuilles.getByName(nom_destination)

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    tableaux = feuille_destination.getDataPilotTables()
    descripteur = tableaux.createDataPilotDescriptor()
    descripteur.setPropertyValue("RowGrand", False)
    descripteur.setPropertyValue("ColumnGrand", False)
    descripteur.setSourceRange(curseur.getRangeAddress())

    colonnes_source = COLONNES_Z1 + COLONNES_CPLTE_ANNEE_MOIS_Z
    champs = descripteur.getDataPilotFields()
    orientation = "com.sun.star.sheet.DataPilotFieldOrientation"
    fonction = "com.sun.star.sheet.GeneralFunction"
    for nom_champ, orientation_champ in (
        ("AJ_Année_Z", "ROW"),
        ("AJ_Mois_Z", "ROW"),
        ("D_DESIGNATION", "COLUMN"),
        ("E_MODE", "PAGE"),
    ):
        champ = champs.getByIndex(colonnes_source.index(nom_champ))
        champ.setPropertyValue(
            "Orientation",
            uno.Enum(orientation, orientation_champ),
        )
        if nom_champ == "E_MODE":
            champ.setPropertyValue("UseSelectedPage", False)

    champ_montant = champs.getByIndex(COLONNES_Z1.index("D_MONTANT"))
    champ_montant.setPropertyValue(
        "Orientation",
        uno.Enum(orientation, "DATA"),
    )
    champ_montant.setPropertyValue(
        "Function",
        uno.Enum(fonction, "SUM"),
    )
    champ_montant.setPropertyValue("Name", "Somme - D_MONTANT")

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(feuille_destination, 12)


def selectionner_mode_tcd(
    feuille: Any,
    nom_tableau: str,
    mode_selectionne: str,
) -> None:
    """Sélectionne un mode dans le filtre de page E_MODE puis rafraîchit le TCD."""
    tableaux = feuille.getDataPilotTables()
    tableau = tableaux.getByName(nom_tableau)
    champ_mode = tableau.getDataPilotFields().getByIndex(
        COLONNES_Z1.index("E_MODE")
    )
    champ_mode.setPropertyValue("UseSelectedPage", True)
    champ_mode.setPropertyValue("SelectedPage", mode_selectionne)
    appliquer_filtre_mode_data_pilot(
        tableaux,
        nom_tableau,
        COLONNES_Z1.index("E_MODE"),
        mode_selectionne,
    )


def resoudre_mode_z1(mode_demande: str, boutique: str, annee: int) -> str:
    """Retourne le mode Z1 retenu pour une feuille de mode."""
    if mode_demande not in FEUILLES_TOTAL_MONTANT_PAR_MODE:
        raise ValueError(f"Mode Z1 non pris en charge : {mode_demande}")
    return mode_demande


def _valeur_montant_tcd(valeur: object) -> float:
    """Convertit une valeur de montant du TCD, en conservant les cellules vides à zéro."""
    if valeur in (None, ""):
        return 0.0
    return float(Decimal(str(valeur)))


def extraire_totaux_mensuels_z1_tcd(
    donnees_tcd: Sequence[Sequence[object]],
) -> tuple[tuple[object, ...], ...]:
    """Extrait horizontalement les montants Z1 requis depuis le TCD filtré."""
    index_entete = None
    entetes_normalisees: tuple[str, ...] = ()
    for index, ligne in enumerate(donnees_tcd):
        entetes = tuple(str(valeur).strip() for valeur in ligne)
        if (
            "AJ_Année_Z" in entetes
            and "AJ_Mois_Z" in entetes
            and all(
                any(alias in entetes for alias in ALIASES_DESIGNATIONS_TOTAL_MONTANT[designation])
                for designation in DESIGNATIONS_TOTAL_MONTANT
            )
        ):
            index_entete = index
            entetes_normalisees = entetes
            break
    if index_entete is None:
        raise ValueError("En-têtes du tableau croisé Z1 introuvables ou incomplets")

    index_annee = entetes_normalisees.index("AJ_Année_Z")
    index_mois = entetes_normalisees.index("AJ_Mois_Z")
    index_designations = tuple(
        next(
            entetes_normalisees.index(alias)
            for alias in ALIASES_DESIGNATIONS_TOTAL_MONTANT[designation]
            if alias in entetes_normalisees
        )
        for designation in DESIGNATIONS_TOTAL_MONTANT
    )
    index_maximum = max(index_annee, index_mois, *index_designations)
    annee_courante = ""
    periodes_vues: set[tuple[str, str]] = set()
    resultats = []
    for ligne in donnees_tcd[index_entete + 1 :]:
        if len(ligne) <= index_maximum:
            continue
        if ligne[index_annee] not in (None, ""):
            annee_courante = str(ligne[index_annee]).strip()
        mois = str(ligne[index_mois]).strip()
        if not annee_courante or not mois:
            continue
        periode = (annee_courante, mois)
        if periode in periodes_vues:
            raise ValueError(f"Période dupliquée dans le TCD Z1 : {periode}")
        periodes_vues.add(periode)
        resultats.append(
            (
                *periode,
                *(
                    _valeur_montant_tcd(ligne[index_designation])
                    for index_designation in index_designations
                ),
            )
        )
    return tuple(resultats)


def ajouter_Total_mode(
    document: Any,
    boutique: str,
    annee: int,
    mode: str,
) -> None:
    """Copie en valeurs les montants mensuels Z1 du mode sélectionné."""
    if mode not in FEUILLES_TOTAL_MONTANT_PAR_MODE:
        raise ValueError(f"Mode Z1 non pris en charge : {mode}")
    if (mode, boutique, annee) in EXCEPTIONS_MODE_Z1:
        return

    feuilles = document.getSheets()
    nom_source = FeuilleZ1SyntheseMois.TD_TOTAL_MONTANT_PAR_MOIS_ANNEE.pour(
        boutique,
        annee,
    )
    nom_destination = FEUILLES_TOTAL_MONTANT_PAR_MODE[mode].pour(
        boutique,
        annee,
    )
    feuille_source = feuilles.getByName(nom_source)
    selectionner_mode_tcd(
        feuille_source,
        nom_source,
        resoudre_mode_z1(mode, boutique, annee),
    )

    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    donnees_tcd = feuille_source.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()
    lignes = extraire_totaux_mensuels_z1_tcd(donnees_tcd)

    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)

    derniere_colonne = len(COLONNES_TOTAL_MONTANT_MODE_ZZ1) - 1
    plage_mode = feuille_destination.getCellRangeByPosition(
        0,
        0,
        derniere_colonne - 1,
        0,
    )
    plage_mode.merge(True)
    feuille_destination.getCellByPosition(0, 0).String = "E_MODE"
    cellule_mode = feuille_destination.getCellByPosition(derniere_colonne, 0)
    cellule_mode.String = mode

    plage_entetes = feuille_destination.getCellRangeByPosition(
        0,
        1,
        derniere_colonne,
        1,
    )
    plage_entetes.setDataArray((COLONNES_TOTAL_MONTANT_MODE_ZZ1,))
    plage_entetes.CharWeight = 150

    if lignes:
        derniere_ligne = len(lignes)
        feuille_destination.getCellRangeByPosition(
            0,
            2,
            derniere_colonne,
            derniere_ligne + 1,
        ).setDataArray(lignes)
        format_montant = obtenir_format(document.getNumberFormats(), FORMAT_MONTANT)
        feuille_destination.getCellRangeByPosition(
            2,
            2,
            derniere_colonne,
            derniere_ligne + 1,
        ).NumberFormat = format_montant

    definir_largeur_colonnes(
        feuille_destination,
        len(COLONNES_TOTAL_MONTANT_MODE_ZZ1),
    )


def ajouter_Total_modeZZ1(document: Any, boutique: str, annee: int) -> None:
    """Copie en valeurs les montants mensuels Z1 du mode ZZ1."""
    ajouter_Total_mode(document, boutique, annee, "ZZ1")


def ajouter_Total_modeZZ2(document: Any, boutique: str, annee: int) -> None:
    """Copie en valeurs les montants mensuels Z1 du mode ZZ2."""
    ajouter_Total_mode(document, boutique, annee, "ZZ2")


def ajouter_Total_modeZ(document: Any, boutique: str, annee: int) -> None:
    """Copie en valeurs les montants mensuels Z1 du mode Z."""
    ajouter_Total_mode(document, boutique, annee, "Z")


def _donnees_utilisees(feuille: Any) -> tuple[tuple[object, ...], ...]:
    """Lit la zone utilisée d'une feuille Calc sous forme de valeurs."""
    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    return feuille.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()


def compter_lignes_cplte_retenues(
    document: Any,
    boutique: str,
    annee: int,
    *,
    mode: str | None = None,
    designations: Sequence[str] | None = None,
) -> int:
    """Compte les lignes Z1 lues et retenues avant l'agrégation du TCD."""
    feuille = document.getSheets().getByName(
        FeuilleZ1SyntheseMois.CPLTE_ANNEE_MOIS.pour(boutique, annee)
    )
    donnees = _donnees_utilisees(feuille)
    if not donnees:
        return 0
    index = {str(nom): position for position, nom in enumerate(donnees[0])}
    resultat = 0
    for ligne in donnees[1:]:
        if not any(valeur not in (None, "") for valeur in ligne):
            continue
        if mode is not None and str(ligne[index["E_MODE"]]) != mode:
            continue
        if (
            designations is not None
            and str(ligne[index["D_DESIGNATION"]]) not in designations
        ):
            continue
        resultat += 1
    return resultat


def enregistrer_compteurs_tableaux_tries_z1(
    document: Any,
    destination: Path,
    boutique: str,
    annee: int,
    chemin_mesures_execution: Path | None,
    chemin_csv: Path,
) -> None:
    """Enregistre les compteurs Z1 au moment où les TCD sont effectivement filtrés."""
    lus = compter_lignes_cplte_retenues(document, boutique, annee)
    modes = tuple(
        mode
        for mode in ("ZZ1", "ZZ2", "Z")
        if (mode, boutique, annee) not in EXCEPTIONS_MODE_Z1
    )
    if modes:
        mode_tcd = modes[-1]
        enregistrer_compteur_traitement(
            chemin_mesures_execution,
            fichier=destination.name,
            feuille=FeuilleZ1SyntheseMois.TD_TOTAL_MONTANT_PAR_MOIS_ANNEE.pour(
                boutique, annee
            ),
            lus=lus,
            selectionnes=compter_lignes_cplte_retenues(
                document, boutique, annee, mode=mode_tcd
            ),
            source_metier=str(chemin_csv),
        )
    for mode in modes:
        designations_retenues = tuple(
            alias
            for designation in DESIGNATIONS_TOTAL_MONTANT
            for alias in ALIASES_DESIGNATIONS_TOTAL_MONTANT[designation]
        )
        enregistrer_compteur_traitement(
            chemin_mesures_execution,
            fichier=destination.name,
            feuille=FEUILLES_TOTAL_MONTANT_PAR_MODE[mode].pour(boutique, annee),
            lus=lus,
            selectionnes=compter_lignes_cplte_retenues(
                document,
                boutique,
                annee,
                mode=mode,
                designations=designations_retenues,
            ),
            source_metier=str(chemin_csv),
        )


def creer_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    nom_feuille: str,
    chemin_csv: Path,
    *,
    boutique: str,
    annee: int,
    chemin_mesures_execution: Path | None = None,
) -> None:
    """Crée directement le document Calc via PyUNO et enregistre l'ODS."""
    with tempfile.TemporaryDirectory(prefix="libreoffice-751-") as repertoire_temporaire:
        temporaire = Path(repertoire_temporaire)
        processus = demarrer_libreoffice(soffice, temporaire / "profil")
        document = None
        try:
            contexte = connecter_uno(uno)
            bureau = contexte.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", contexte
            )
            document = bureau.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
            print(f"Création de la feuille {nom_feuille}...")
            add_Synthese_0(document, nom_feuille, chemin_csv)
            print("Ajout de la feuille CplteAnneeMoisZ...")
            ajouter_Cplte(document, boutique, annee)
            print("Ajout du tableau croisé des occurrences E_FICHIER/E_MODE...")
            ajouter_TD_OccurenceEfichier(document, boutique, annee)
            print("Ajout du tableau croisé des montants Z1...")
            ajouter_TD_TotalMontant(document, boutique, annee)
            for mode, ajouter_total_mode in (
                ("ZZ1", ajouter_Total_modeZZ1),
                ("ZZ2", ajouter_Total_modeZZ2),
                ("Z", ajouter_Total_modeZ),
            ):
                if (mode, boutique, annee) in EXCEPTIONS_MODE_Z1:
                    print(f"Feuille Mode{mode} non applicable pour {annee} {boutique}.")
                else:
                    print(f"Copie en valeurs des montants Z1 du mode {mode}...")
                    ajouter_total_mode(document, boutique, annee)

            enregistrer_compteurs_tableaux_tries_z1(
                document,
                destination,
                boutique,
                annee,
                chemin_mesures_execution,
                chemin_csv,
            )

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
    repertoire_staging: Path,
    repertoire_sortie: Path,
    uno: Any,
    soffice: str = "soffice",
    chemin_mesures_execution: Path | None = None,
) -> dict[tuple[int, str], Path]:
    """Génère les six classeurs Z1 depuis les CSV préparatoires."""
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    resultats: dict[tuple[int, str], Path] = {}
    for annee in ANNEES:
        for boutique in BOUTIQUES:
            nom_feuille = FeuilleZ1SyntheseMois.SYNTHESE_MOIS.pour(boutique, annee)
            chemin_csv = repertoire_staging / f"Z1_SyntheseMois_TOUS_{annee}_{boutique}.csv"
            if not chemin_csv.is_file():
                raise FileNotFoundError(f"CSV préparatoire introuvable : {chemin_csv}")
            destination = repertoire_sortie / f"TTS_Z1_SyntheseMois_TOUS_{annee}_{boutique}.ods"
            arguments_mesures = (
                {"chemin_mesures_execution": chemin_mesures_execution}
                if chemin_mesures_execution is not None
                else {}
            )
            creer_et_enregistrer_classeur(
                uno,
                soffice,
                destination,
                nom_feuille,
                chemin_csv,
                boutique=boutique,
                annee=annee,
                **arguments_mesures,
            )
            resultats[(annee, boutique)] = destination
    return resultats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, default=Path("output/travaux_preliminaires"))
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--soffice", default="soffice")
    parser.add_argument("--python-uno", type=Path, default=None)
    parser.add_argument("--mesures-execution", type=Path, default=None)
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
            check=False,
        )
        return resultat.returncode

    resultats = generer_classeurs(
        args.staging,
        args.sortie,
        uno,
        args.soffice,
        chemin_mesures_execution=args.mesures_execution,
    )
    for (annee, boutique), chemin in resultats.items():
        print(f"{annee} {boutique} : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
