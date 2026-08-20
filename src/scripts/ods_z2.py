"""Génère les feuilles d'entrée Z2 d'un classeur ODS par année et boutique."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from shared.constantes import ANNEES, BOUTIQUES, SEPARATEUR_CSV, FeuilleZ2Transactions
from shared.ods_helpers import (
    connecter_uno,
    copier_feuille,
    definir_largeur_colonnes,
    demarrer_libreoffice,
    ecrire_tableau,
    obtenir_format,
    proprietes,
    python_pyuno_defaut,
    pyuno_disponible,
)

COLONNES_Z2 = (
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
FORMULES_CPLTE_ANNEE_MOIS_Z = (
    '=IF(H{ligne}="";"";YEAR(H{ligne}))',
    '=IF(H{ligne}="";"";TEXT(H{ligne};"YYYY-MM"))',
)
NATURES_TRANSACTION = (
    "CARTES",
    "CHEQUES",
    "CORRECTION",
    "ESPECES",
    "REF./TIROIR",
)
COLONNES_TOTAL_MONTANT_MODE_ZZ1 = (
    "AJ_Année_Z",
    "AJ_Mois_Z",
    *(
        colonne
        for nature in NATURES_TRANSACTION
        for colonne in (f"{nature}_D_QUANTITE", f"{nature}_D_MONTANT")
    ),
)
COLONNES_TOTAL_MONTANT_MODE = COLONNES_TOTAL_MONTANT_MODE_ZZ1
COLONNES_COMPARE_MONTANT = (
    "AJ_Année_Z",
    "AJ_Mois_Z",
    *(
        colonne
        for nature in NATURES_TRANSACTION
        for colonne in (f"{nature}_AJ_ECART_QTE", f"{nature}_AJ_ECART_MONTANT")
    ),
)
FEUILLES_TOTAL_MONTANT_PAR_MODE = {
    "ZZ1": FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ1,
    "ZZ2": FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ2,
    "Z": FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_Z,
}
MODES_Z2_PAR_MODE_BOUTIQUE_ANNEE = {
    ("ZZ1", "MATURIN", 2024): "Z",
    ("ZZ2", "MATURIN", 2024): "Z",
    ("Z", "MASSENA", 2024): "ZZ2",
}
LIGNE_NATURES_TOTAL_MONTANT_MODE_ZZ1 = 0
LIGNE_ENTETES_TOTAL_MONTANT_MODE_ZZ1 = 1
LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1 = 2


def resoudre_mode_z2(mode_demande: str, boutique: str, annee: int) -> str:
    """Retourne le mode Z2 retenu pour une feuille de mode donnée."""
    if mode_demande not in FEUILLES_TOTAL_MONTANT_PAR_MODE:
        raise ValueError(f"Mode Z2 non pris en charge : {mode_demande}")
    return MODES_Z2_PAR_MODE_BOUTIQUE_ANNEE.get(
        (mode_demande, boutique, annee),
        mode_demande,
    )


def ajouter_transactions_0(
    document: Any,
    nom_feuille: str,
    chemin_csv: Path,
) -> None:
    """Crée la feuille Z2 initiale depuis son CSV préparatoire."""
    with chemin_csv.open(encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.DictReader(fichier, delimiter=SEPARATEUR_CSV)
        if tuple(lecteur.fieldnames or ()) != COLONNES_Z2:
            raise ValueError(f"Colonnes inattendues dans {chemin_csv}")
        rows = list(lecteur)

    feuille = document.getSheets().getByIndex(0)
    feuille.setName(nom_feuille)

    plage_entete = feuille.getCellRangeByPosition(0, 0, len(COLONNES_Z2) - 1, 0)
    plage_entete.setDataArray((COLONNES_Z2,))
    plage_entete.CharWeight = 150

    formats = document.getNumberFormats()
    ecrire_tableau(
        feuille,
        rows,
        COLONNES_Z2,
        formats,
        colonnes_texte=COLONNES_TEXTE,
        colonne_date=COLONNE_DATE,
        format_date=FORMAT_DATE,
    )

    if rows:
        derniere_ligne = len(rows)
        index_montant = COLONNES_Z2.index(COLONNE_MONTANT)
        feuille.getCellRangeByPosition(
            index_montant,
            1,
            index_montant,
            derniere_ligne,
        ).NumberFormat = obtenir_format(formats, FORMAT_MONTANT)

    definir_largeur_colonnes(feuille, len(COLONNES_Z2))


def ajouter_CplteAnneeMoisZ(document: Any, boutique: str, annee: int) -> None:
    """Copie la feuille Z2 initiale et y ajoute l'année et le mois de la clôture."""
    feuille = copier_feuille(
        document,
        FeuilleZ2Transactions.TRANSACTIONS.pour(boutique, annee),
        FeuilleZ2Transactions.CPLTE_ANNEE_MOIS.pour(boutique, annee),
    )

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    derniere_ligne = curseur.getRangeAddress().EndRow
    colonne_debut = len(COLONNES_Z2)

    plage_entetes = feuille.getCellRangeByPosition(
        colonne_debut,
        0,
        colonne_debut + len(COLONNES_CPLTE_ANNEE_MOIS_Z) - 1,
        0,
    )
    plage_entetes.setDataArray((COLONNES_CPLTE_ANNEE_MOIS_Z,))
    plage_entetes.CharWeight = 150

    if derniere_ligne >= 1:
        formules = tuple(
            tuple(formule.format(ligne=index_ligne + 1) for formule in FORMULES_CPLTE_ANNEE_MOIS_Z)
            for index_ligne in range(1, derniere_ligne + 1)
        )
        feuille.getCellRangeByPosition(
            colonne_debut,
            1,
            colonne_debut + len(COLONNES_CPLTE_ANNEE_MOIS_Z) - 1,
            derniere_ligne,
        ).setFormulaArray(formules)
        feuille.getCellRangeByPosition(
            colonne_debut,
            1,
            colonne_debut,
            derniere_ligne,
        ).NumberFormat = obtenir_format(document.getNumberFormats(), "0")

    definir_largeur_colonnes(
        feuille,
        len(COLONNES_Z2) + len(COLONNES_CPLTE_ANNEE_MOIS_Z),
    )


def ajouter_TotalMontant(
    document: Any,
    boutique: str,
    annee: int,
    mode_demande: str = "ZZ1",
) -> None:
    """Ajoute le tableau croisé des montants par mois et nature de transaction."""
    import uno

    nom_source = FeuilleZ2Transactions.CPLTE_ANNEE_MOIS.pour(boutique, annee)
    nom_destination = FeuilleZ2Transactions.TD_TOTAL_MOIS_ANNEE_NATURE.pour(
        boutique,
        annee,
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

    champs = descripteur.getDataPilotFields()
    orientation = "com.sun.star.sheet.DataPilotFieldOrientation"
    fonction = "com.sun.star.sheet.GeneralFunction"
    for nom_champ, orientation_champ in (
        ("AJ_Année_Z", "ROW"),
        ("AJ_Mois_Z", "ROW"),
        ("D_DESIGNATION", "COLUMN"),
        ("E_MODE", "PAGE"),
        ("E_FICHIER", "PAGE"),
    ):
        champ = champs.getByIndex(
            (COLONNES_Z2 + COLONNES_CPLTE_ANNEE_MOIS_Z).index(nom_champ)
        )
        champ.setPropertyValue(
            "Orientation",
            uno.Enum(orientation, orientation_champ),
        )
        if nom_champ == "E_MODE":
            champ.setPropertyValue(
                "SelectedPage",
                resoudre_mode_z2(mode_demande, boutique, annee),
            )

    for nom_champ in ("D_QUANTITE", "D_MONTANT"):
        champ = champs.getByIndex(COLONNES_Z2.index(nom_champ))
        champ.setPropertyValue("Orientation", uno.Enum(orientation, "DATA"))
        champ.setPropertyValue("Function", uno.Enum(fonction, "SUM"))
        champ.setPropertyValue("Name", f"Somme - {nom_champ}")

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(feuille_destination, 12)


def _valeur_numerique(valeur: object) -> float:
    """Retourne une valeur Calc numérique, avec zéro pour une cellule vide."""
    if valeur in (None, ""):
        return 0.0
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return float(Decimal(str(valeur)))


def extraire_totaux_mensuels_tcd(
    donnees_tcd: Sequence[Sequence[object]],
) -> tuple[tuple[object, ...], ...]:
    """Extrait les valeurs mensuelles requises depuis la sortie du TCD existant."""
    index_entete = next(
        (
            index
            for index, ligne in enumerate(donnees_tcd)
            if "AJ_Année_Z" in ligne and "AJ_Mois_Z" in ligne and "Data" in ligne
        ),
        None,
    )
    if index_entete is None:
        raise ValueError("En-têtes du tableau croisé Z2 introuvables")

    entetes = donnees_tcd[index_entete]
    index_annee = entetes.index("AJ_Année_Z")
    index_mois = entetes.index("AJ_Mois_Z")
    index_donnees = entetes.index("Data")
    index_nature = {nature: entetes.index(nature) for nature in NATURES_TRANSACTION}
    annee_courante: object = ""
    resultats: list[tuple[object, ...]] = []

    for index_ligne in range(index_entete + 1, len(donnees_tcd) - 1):
        ligne_quantite = donnees_tcd[index_ligne]
        if ligne_quantite[index_donnees] != "Somme - D_QUANTITE":
            continue
        ligne_montant = donnees_tcd[index_ligne + 1]
        if ligne_montant[index_donnees] != "Somme - D_MONTANT":
            raise ValueError("Ligne de montant absente après une ligne de quantité du TCD Z2")

        if ligne_quantite[index_annee] not in (None, ""):
            annee_courante = ligne_quantite[index_annee]
        mois = ligne_quantite[index_mois]
        if annee_courante in (None, "") or mois in (None, ""):
            raise ValueError("Période mensuelle incomplète dans le TCD Z2")

        resultats.append(
            (
                annee_courante,
                mois,
                *(
                    valeur
                    for nature in NATURES_TRANSACTION
                    for valeur in (
                        _valeur_numerique(ligne_quantite[index_nature[nature]]),
                        _valeur_numerique(ligne_montant[index_nature[nature]]),
                    )
                ),
            )
        )
    return tuple(resultats)


def mettre_en_forme_tableau_natures(
    feuille: Any,
    libelle_quantite: str,
    libelle_montant: str,
) -> None:
    """Organise la feuille de totaux selon la présentation contractuelle."""
    derniere_colonne = len(COLONNES_TOTAL_MONTANT_MODE_ZZ1) - 1

    for index_nature, nature in enumerate(NATURES_TRANSACTION):
        colonne_debut = 2 + index_nature * 2
        plage_nature = feuille.getCellRangeByPosition(
            colonne_debut,
            LIGNE_NATURES_TOTAL_MONTANT_MODE_ZZ1,
            colonne_debut + 1,
            LIGNE_NATURES_TOTAL_MONTANT_MODE_ZZ1,
        )
        plage_nature.merge(True)
        feuille.getCellByPosition(
            colonne_debut,
            LIGNE_NATURES_TOTAL_MONTANT_MODE_ZZ1,
        ).String = nature
        plage_nature.CharWeight = 150

    entetes_visuels = (
        "AJ_Année_Z",
        "AJ_Mois_Z",
        *(
            champ
            for _ in NATURES_TRANSACTION
            for champ in (libelle_quantite, libelle_montant)
        ),
    )
    plage_entetes = feuille.getCellRangeByPosition(
        0,
        LIGNE_ENTETES_TOTAL_MONTANT_MODE_ZZ1,
        derniere_colonne,
        LIGNE_ENTETES_TOTAL_MONTANT_MODE_ZZ1,
    )
    plage_entetes.setDataArray((entetes_visuels,))
    plage_entetes.CharWeight = 150


def ajouter_TotalMontant_Mode(
    document: Any,
    boutique: str,
    annee: int,
    mode_demande: str,
) -> None:
    """Copie en valeurs les totaux mensuels du TCD dans une feuille de mode."""
    feuilles = document.getSheets()
    nom_source = FeuilleZ2Transactions.TD_TOTAL_MOIS_ANNEE_NATURE.pour(boutique, annee)
    nom_destination = FEUILLES_TOTAL_MONTANT_PAR_MODE[mode_demande].pour(boutique, annee)
    feuille_source = feuilles.getByName(nom_source)
    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    donnees_tcd = feuille_source.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()
    lignes = extraire_totaux_mensuels_tcd(donnees_tcd)

    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)
    mettre_en_forme_tableau_natures(
        feuille_destination,
        "D_QUANTITE",
        "D_MONTANT",
    )

    if lignes:
        derniere_ligne = len(lignes)
        feuille_destination.getCellRangeByPosition(
            0,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
            len(COLONNES_TOTAL_MONTANT_MODE) - 1,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1 + derniere_ligne - 1,
        ).setDataArray(lignes)
        formats = document.getNumberFormats()
        derniere_ligne_donnees = LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1 + derniere_ligne - 1
        feuille_destination.getCellRangeByPosition(
            0,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
            0,
            derniere_ligne_donnees,
        ).NumberFormat = obtenir_format(formats, "0")
        for index_colonne in range(2, len(COLONNES_TOTAL_MONTANT_MODE), 2):
            feuille_destination.getCellRangeByPosition(
                index_colonne,
                LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
                index_colonne,
                derniere_ligne_donnees,
            ).NumberFormat = obtenir_format(formats, "0")
            feuille_destination.getCellRangeByPosition(
                index_colonne + 1,
                LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
                index_colonne + 1,
                derniere_ligne_donnees,
            ).NumberFormat = obtenir_format(formats, FORMAT_MONTANT)

    definir_largeur_colonnes(feuille_destination, len(COLONNES_TOTAL_MONTANT_MODE))


def ajouter_TotalMontant_ModeZZ1(document: Any, boutique: str, annee: int) -> None:
    """Copie en valeurs les totaux mensuels du TCD sélectionné en mode ZZ1."""
    ajouter_TotalMontant_Mode(document, boutique, annee, "ZZ1")


def ajouter_TotalMontant_ModeZZ2(document: Any, boutique: str, annee: int) -> None:
    """Copie en valeurs les totaux mensuels du TCD sélectionné en mode ZZ2."""
    ajouter_TotalMontant_Mode(document, boutique, annee, "ZZ2")


def ajouter_TotalMontant_ModeZ(document: Any, boutique: str, annee: int) -> None:
    """Copie en valeurs les totaux mensuels du TCD sélectionné en mode Z."""
    ajouter_TotalMontant_Mode(document, boutique, annee, "Z")


def lire_lignes_valeurs_feuille(
    feuille: Any,
    colonnes: Sequence[str],
    ligne_depart: int,
) -> tuple[dict[str, object], ...]:
    """Lit les valeurs d'une feuille de résultats à en-têtes visuels groupés."""
    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    donnees = feuille.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()
    resultats = []
    for ligne in donnees[ligne_depart:]:
        if len(ligne) < len(colonnes) or ligne[0] in (None, "") or ligne[1] in (None, ""):
            continue
        resultats.append(dict(zip(colonnes, ligne, strict=True)))
    return tuple(resultats)


def comparer_lignes_par_periode(
    lignes_gauche: Sequence[dict[str, object]],
    lignes_droite: Sequence[dict[str, object]],
    natures: Sequence[str] = NATURES_TRANSACTION,
) -> tuple[tuple[object, ...], ...]:
    """Compare deux jeux de totaux par année et mois, en conservant toute période."""
    def indexer(lignes: Sequence[dict[str, object]]) -> dict[tuple[int, str], dict[str, object]]:
        resultat = {}
        for ligne in lignes:
            cle = (int(_valeur_numerique(ligne["AJ_Année_Z"])), str(ligne["AJ_Mois_Z"]))
            if cle in resultat:
                raise ValueError(f"Période dupliquée dans une feuille de comparaison : {cle}")
            resultat[cle] = ligne
        return resultat

    gauche_par_periode = indexer(lignes_gauche)
    droite_par_periode = indexer(lignes_droite)
    resultats = []
    for annee, mois in sorted(set(gauche_par_periode) | set(droite_par_periode)):
        gauche = gauche_par_periode.get((annee, mois), {})
        droite = droite_par_periode.get((annee, mois), {})
        resultats.append(
            (
                float(annee),
                mois,
                *(
                    valeur
                    for nature in natures
                    for valeur in (
                        _valeur_numerique(gauche.get(f"{nature}_D_QUANTITE"))
                        - _valeur_numerique(droite.get(f"{nature}_D_QUANTITE")),
                        _valeur_numerique(gauche.get(f"{nature}_D_MONTANT"))
                        - _valeur_numerique(droite.get(f"{nature}_D_MONTANT")),
                    )
                ),
            )
        )
    return tuple(resultats)


def ajouter_CompareMontant(document: Any, boutique: str, annee: int) -> None:
    """Compare en valeurs les feuilles de totaux des modes ZZ1 et ZZ2."""
    feuilles = document.getSheets()
    feuille_zz1 = feuilles.getByName(
        FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ1.pour(boutique, annee)
    )
    feuille_zz2 = feuilles.getByName(
        FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ2.pour(boutique, annee)
    )
    lignes = comparer_lignes_par_periode(
        lire_lignes_valeurs_feuille(
            feuille_zz1,
            COLONNES_TOTAL_MONTANT_MODE,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
        ),
        lire_lignes_valeurs_feuille(
            feuille_zz2,
            COLONNES_TOTAL_MONTANT_MODE,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
        ),
    )
    nom_destination = FeuilleZ2Transactions.COMPARE_MONTANT_ZZ1_VS_ZZ2.pour(
        boutique,
        annee,
    )
    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)
    mettre_en_forme_tableau_natures(
        feuille_destination,
        "AJ_ECART_QTE",
        "AJ_ECART_MONTANT",
    )

    if lignes:
        derniere_ligne = LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1 + len(lignes) - 1
        feuille_destination.getCellRangeByPosition(
            0,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
            len(COLONNES_COMPARE_MONTANT) - 1,
            derniere_ligne,
        ).setDataArray(lignes)
        formats = document.getNumberFormats()
        feuille_destination.getCellRangeByPosition(
            0,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
            0,
            derniere_ligne,
        ).NumberFormat = obtenir_format(formats, "0")
        for index_colonne in range(2, len(COLONNES_COMPARE_MONTANT), 2):
            feuille_destination.getCellRangeByPosition(
                index_colonne,
                LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
                index_colonne,
                derniere_ligne,
            ).NumberFormat = obtenir_format(formats, "0")
            feuille_destination.getCellRangeByPosition(
                index_colonne + 1,
                LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
                index_colonne + 1,
                derniere_ligne,
            ).NumberFormat = obtenir_format(formats, FORMAT_MONTANT)

    definir_largeur_colonnes(feuille_destination, len(COLONNES_COMPARE_MONTANT))


def creer_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    nom_feuille: str,
    chemin_csv: Path,
    *,
    boutique: str,
    annee: int,
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
            document = bureau.loadComponentFromURL(
                "private:factory/scalc", "_blank", 0, ()
            )

            print(f"Création de la feuille {nom_feuille}...")
            ajouter_transactions_0(document, nom_feuille, chemin_csv)
            print(f"Ajout de la feuille CplteAnneeMoisZ pour {annee} {boutique}...")
            ajouter_CplteAnneeMoisZ(document, boutique, annee)
            print(f"Ajout du tableau croisé des montants pour {annee} {boutique}...")
            ajouter_TotalMontant(document, boutique, annee, "ZZ1")
            print(f"Copie des totaux du mode ZZ1 pour {annee} {boutique}...")
            ajouter_TotalMontant_ModeZZ1(document, boutique, annee)
            print(f"Sélection du mode ZZ2 pour {annee} {boutique}...")
            ajouter_TotalMontant(document, boutique, annee, "ZZ2")
            print(f"Copie des totaux du mode ZZ2 pour {annee} {boutique}...")
            ajouter_TotalMontant_ModeZZ2(document, boutique, annee)
            print(f"Sélection du mode Z pour {annee} {boutique}...")
            ajouter_TotalMontant(document, boutique, annee, "Z")
            print(f"Copie des totaux du mode Z pour {annee} {boutique}...")
            ajouter_TotalMontant_ModeZ(document, boutique, annee)
            print(f"Comparaison des montants ZZ1 et ZZ2 pour {annee} {boutique}...")
            ajouter_CompareMontant(document, boutique, annee)

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
    repertoire_staging: Path,
    repertoire_sortie: Path,
    uno: Any,
    soffice: str = "soffice",
) -> dict[tuple[int, str], Path]:
    """Génère les six classeurs Z2 depuis les CSV préparatoires."""
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    resultats: dict[tuple[int, str], Path] = {}
    for annee in ANNEES:
        for boutique in BOUTIQUES:
            nom_feuille = FeuilleZ2Transactions.TRANSACTIONS.pour(boutique, annee)
            chemin_csv = (
                repertoire_staging
                / f"Z2_TransactionsMois_TOUS_{annee}_{boutique}.csv"
            )
            if not chemin_csv.is_file():
                raise FileNotFoundError(f"CSV préparatoire introuvable : {chemin_csv}")
            destination = (
                repertoire_sortie
                / f"TTS_Z2_TransactionsMois_TOUS_{annee}_{boutique}.ods"
            )
            creer_et_enregistrer_classeur(
                uno,
                soffice,
                destination,
                nom_feuille,
                chemin_csv,
                boutique=boutique,
                annee=annee,
            )
            resultats[(annee, boutique)] = destination
    return resultats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staging",
        type=Path,
        default=Path("output/travaux_preliminaires"),
    )
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
            check=False,
        )
        return resultat.returncode
    resultats = generer_classeurs(args.staging, args.sortie, uno, args.soffice)
    for (annee, boutique), chemin in resultats.items():
        print(f"{annee} {boutique} : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
