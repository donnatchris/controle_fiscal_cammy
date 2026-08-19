"""Génère la feuille d'entrée des lignes EJ d'un classeur ODS par boutique."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from shared.constantes import BOUTIQUES, FeuilleEjTickets, SEPARATEUR_CSV
from shared.ods_helpers import (
    connecter_uno,
    copier_feuille,
    copier_valeurs_feuille,
    demarrer_libreoffice,
    ecrire_tableau,
    definir_largeur_colonnes,
    proprietes,
    python_pyuno_defaut,
    pyuno_disponible,
)

COLONNES_TICKETS = (
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
    "D_QUANTITE_ARTICLE",
    "D_LIBELLE_ARTICLE",
    "D_TAUX_TVA_ARTICLE",
    "D_MONTANT_ARTICLE",
    "D_CORRECTION",
    "D_AUTRE_INFO",
)
COLONNES_TEXTE = {
    "nomfichier",
    "E_NUM_INTERNE",
    "E_NUM_TICKET",
    "E_HEURE_TICKET",
    "D_LIBELLE_ARTICLE",
    "D_TAUX_TVA_ARTICLE",
    "D_AUTRE_INFO",
}
COLONNE_DATE = "E_DATE_TICKET"
FORMAT_DATE = "YYYY-MM-DD"


def ajouter_tickets_0(document: Any, nom_feuille: str, chemin_csv: Path) -> None:
    """Crée la feuille initiale des lignes EJ depuis son CSV préparatoire."""
    with chemin_csv.open(encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.DictReader(fichier, delimiter=SEPARATEUR_CSV)
        if tuple(lecteur.fieldnames or ()) != COLONNES_TICKETS:
            raise ValueError(f"Colonnes inattendues dans {chemin_csv}")
        rows = list(lecteur)

    feuille = document.getSheets().getByIndex(0)
    feuille.setName(nom_feuille)
    plage_entete = feuille.getCellRangeByPosition(0, 0, len(COLONNES_TICKETS) - 1, 0)
    plage_entete.setDataArray((COLONNES_TICKETS,))
    plage_entete.CharWeight = 150
    ecrire_tableau(
        feuille,
        rows,
        COLONNES_TICKETS,
        document.getNumberFormats(),
        colonnes_texte=COLONNES_TEXTE,
        colonne_date=COLONNE_DATE,
        format_date=FORMAT_DATE,
    )
    definir_largeur_colonnes(feuille, len(COLONNES_TICKETS))


def ajouter_TriCrstNumInterne(
    document: Any,
    nom_feuille_source: str,
    boutique: str,
) -> None:
    """Copie la feuille source puis trie la copie par E_NUM_INTERNE croissant."""

    from com.sun.star.util import SortField

    nom_feuille_destination = FeuilleEjTickets.TRI_NUM_INTERNE.pour(boutique)

    feuille = copier_feuille(
        document,
        nom_feuille_source,
        nom_feuille_destination,
    )

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    plage = curseur

    champ_tri = SortField()
    champ_tri.Field = COLONNES_TICKETS.index("E_NUM_INTERNE")
    champ_tri.SortAscending = True

    descripteur_tri = plage.createSortDescriptor()

    for propriete in descripteur_tri:
        if propriete.Name == "SortFields":
            propriete.Value = (champ_tri,)
        elif propriete.Name == "ContainsHeader":
            propriete.Value = True

    plage.sort(descripteur_tri)
    definir_largeur_colonnes(feuille, len(COLONNES_TICKETS))


def ajouter_CtrlCoherenceEntete(document: Any, boutique: str) -> None:
    """Copie la feuille de lignes triée dans la feuille de contrôle de cohérence."""

    feuille = copier_feuille(
        document,
        FeuilleEjTickets.TRI_NUM_INTERNE.pour(boutique),
        FeuilleEjTickets.CTRL_COHERENCE.pour(boutique),
    )
    definir_largeur_colonnes(feuille, len(COLONNES_TICKETS))


def ajouter_TotalLigneParNumTickets(document: Any, boutique: str) -> None:
    """Ajoute le tableau croisé des lignes et montants par numéro de ticket."""
    import uno

    nom_source = FeuilleEjTickets.CTRL_COHERENCE.pour(boutique)
    nom_destination = FeuilleEjTickets.TD_TOTAL_LIGNES.pour(boutique)
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

    champs = descripteur.getDataPilotFields()
    for colonne in ("E_NUM_TICKET", "E_TTC"):
        champs.getByIndex(COLONNES_TICKETS.index(colonne)).setPropertyValue(
            "Orientation",
            uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW"),
        )

    for colonne, fonction, nom in (
        ("D_LIBELLE_ARTICLE", "COUNT", "Compter - D_LIBELLE_ARTICLE"),
        ("D_MONTANT_ARTICLE", "SUM", "Somme - D_MONTANT_ARTICLE"),
        ("D_CORRECTION", "SUM", "Somme - D_CORRECTION"),
    ):
        champ = champs.getByIndex(COLONNES_TICKETS.index(colonne))
        champ.setPropertyValue(
            "Orientation",
            uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA"),
        )
        champ.setPropertyValue(
            "Function",
            uno.Enum("com.sun.star.sheet.GeneralFunction", fonction),
        )
        champ.setPropertyValue("Name", nom)

    champ_disposition_donnees = descripteur.getDataLayoutField()
    champ_disposition_donnees.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "COLUMN"),
    )

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(feuille_destination, 5)


def ajouter_OccurenceLibelleArticle(document: Any, boutique: str) -> None:
    """Ajoute le tableau croisé des occurrences de libellés d'articles."""
    import uno

    nom_source = FeuilleEjTickets.CTRL_COHERENCE.pour(boutique)
    nom_destination = FeuilleEjTickets.TD_OCCURENCE_ARTICLE.pour(boutique)
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

    index_libelle = COLONNES_TICKETS.index("D_LIBELLE_ARTICLE")
    champs = descripteur.getDataPilotFields()
    champs.getByIndex(index_libelle).setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW"),
    )
    champ_donnees = champs.getByIndex(index_libelle)
    champ_donnees.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA"),
    )
    champ_donnees.setPropertyValue(
        "Function",
        uno.Enum("com.sun.star.sheet.GeneralFunction", "COUNT"),
    )
    champ_donnees.setPropertyValue("Name", "Compter - D_LIBELLE_ARTICLE")

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(feuille_destination, 2)


def ajouter_OccurenceTxTvaArticle(document: Any, boutique: str) -> None:
    """Ajoute le tableau croisé des occurrences de taux de TVA des articles."""
    import uno

    nom_source = FeuilleEjTickets.CTRL_COHERENCE.pour(boutique)
    nom_destination = FeuilleEjTickets.TD_OCCURRENCE_TVA.pour(boutique)
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

    index_taux_tva = COLONNES_TICKETS.index("D_TAUX_TVA_ARTICLE")
    champs = descripteur.getDataPilotFields()
    champs.getByIndex(index_taux_tva).setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW"),
    )
    champ_donnees = champs.getByIndex(index_taux_tva)
    champ_donnees.setPropertyValue(
        "Orientation",
        uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA"),
    )
    champ_donnees.setPropertyValue(
        "Function",
        uno.Enum("com.sun.star.sheet.GeneralFunction", "COUNT"),
    )
    champ_donnees.setPropertyValue("Name", "Compter - D_TAUX_TVA_ARTICLE")

    if tableaux.hasByName(nom_destination):
        tableaux.removeByName(nom_destination)
    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(feuille_destination, 2)


def ajouter_CtrlCoherenceEnteteLigne(document: Any, boutique: str) -> None:
    """Copie les valeurs du TCD, nettoie ses en-têtes et calcule l'écart TTC."""
    feuille = copier_valeurs_feuille(
        document,
        FeuilleEjTickets.TD_TOTAL_LIGNES.pour(boutique),
        FeuilleEjTickets.CONTROLE_COHERENCE.pour(boutique),
    )

    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    valeurs_tcd = feuille.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()

    if _supprimer_ligne_data_tcd(feuille, valeurs_tcd):
        curseur = feuille.createCursor()
        curseur.gotoEndOfUsedArea(True)
        adresse = curseur.getRangeAddress()
        valeurs_tcd = feuille.getCellRangeByPosition(
            adresse.StartColumn,
            adresse.StartRow,
            adresse.EndColumn,
            adresse.EndRow,
        ).getDataArray()

    index_ttc, ligne_entete_ttc = _position_entete_tcd(valeurs_tcd, "E_TTC")
    index_montant, ligne_entete_montant = _position_entete_tcd(
        valeurs_tcd,
        "Somme - D_MONTANT_ARTICLE",
        champ="D_MONTANT_ARTICLE",
    )
    index_correction, ligne_entete_correction = _position_entete_tcd(
        valeurs_tcd,
        "Somme - D_CORRECTION",
        champ="D_CORRECTION",
    )
    index_ecart = adresse.EndColumn - adresse.StartColumn + 1
    feuille.getCellByPosition(index_ecart, 0).String = "AJ_ECART_TTC"

    premiere_ligne_donnees = max(
        ligne_entete_ttc,
        ligne_entete_montant,
        ligne_entete_correction,
    ) + 1
    for ligne in range(premiere_ligne_donnees, adresse.EndRow + 1):
        reference_ttc = _lettre_colonne(index_ttc) + str(ligne + 1)
        reference_montant = _lettre_colonne(index_montant) + str(ligne + 1)
        reference_correction = _lettre_colonne(index_correction) + str(ligne + 1)
        feuille.getCellByPosition(index_ecart, ligne).Formula = (
            f"={reference_ttc}-({reference_montant}+{reference_correction})"
        )

    definir_largeur_colonnes(feuille, index_ecart + 1)


def _lettre_colonne(index: int) -> str:
    """Convertit l'index de colonne Calc (base 0) en référence A1."""
    resultat = ""
    while True:
        index, reste = divmod(index, 26)
        resultat = chr(ord("A") + reste) + resultat
        if index == 0:
            return resultat
        index -= 1


def _position_entete_tcd(
    valeurs: tuple[tuple[object, ...], ...],
    nom_attendu: str,
    *,
    champ: str | None = None,
) -> tuple[int, int]:
    """Trouve la position d'un en-tête de TCD malgré son formatage par Calc."""
    attendu_normalise = _normaliser_entete_tcd(nom_attendu)
    champ_normalise = _normaliser_entete_tcd(champ) if champ is not None else None
    for ligne, valeurs_ligne in enumerate(valeurs):
        for colonne, entete in enumerate(valeurs_ligne):
            entete_normalise = _normaliser_entete_tcd(entete)
            if entete_normalise == attendu_normalise:
                return colonne, ligne
            if champ_normalise is not None and champ_normalise in entete_normalise:
                return colonne, ligne
    raise ValueError(
        f"Colonne du TCD introuvable : {nom_attendu}; valeurs présentes : {valeurs}"
    )


def _normaliser_entete_tcd(valeur: object) -> str:
    """Normalise un libellé de TCD pour neutraliser espaces et soulignés Calc."""
    return "".join(
        caractere for caractere in str(valeur).upper() if caractere.isalnum()
    )


def _supprimer_ligne_data_tcd(
    feuille: Any,
    valeurs: tuple[tuple[object, ...], ...],
) -> bool:
    """Fusionne les en-têtes du TCD puis retire sa ligne synthétique Data."""
    ligne_data = next(
        (
            ligne
            for ligne, valeurs_ligne in enumerate(valeurs)
            if any(_normaliser_entete_tcd(valeur) == "DATA" for valeur in valeurs_ligne)
        ),
        None,
    )
    if ligne_data is None:
        return False

    lignes_mesures = {
        _position_entete_tcd(valeurs, nom, champ=champ)[1]
        for nom, champ in (
            ("Compter - D_LIBELLE_ARTICLE", "D_LIBELLE_ARTICLE"),
            ("Somme - D_MONTANT_ARTICLE", "D_MONTANT_ARTICLE"),
            ("Somme - D_CORRECTION", "D_CORRECTION"),
        )
    }
    if len(lignes_mesures) != 1:
        return False
    ligne_entetes = lignes_mesures.pop()
    if ligne_entetes <= ligne_data:
        return False

    for colonne, valeur in enumerate(valeurs[ligne_data]):
        if valeur in (None, "") or _normaliser_entete_tcd(valeur) == "DATA":
            continue
        if valeurs[ligne_entetes][colonne] in (None, ""):
            feuille.getCellByPosition(colonne, ligne_entetes).String = str(valeur)

    feuille.getRows().removeByIndex(ligne_data, 1)
    return True


def creer_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    nom_feuille: str,
    chemin_csv: Path,
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
            bureau = contexte.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", contexte
            )
            document = bureau.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
            ajouter_tickets_0(document, nom_feuille, chemin_csv)
            ajouter_TriCrstNumInterne(
                document,
                nom_feuille_source=nom_feuille,
                boutique=boutique,
            )
            ajouter_CtrlCoherenceEntete(document, boutique)
            ajouter_OccurenceLibelleArticle(document, boutique)
            ajouter_OccurenceTxTvaArticle(document, boutique)
            ajouter_TotalLigneParNumTickets(document, boutique)
            ajouter_CtrlCoherenceEnteteLigne(document, boutique)

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
) -> dict[str, Path]:
    """Génère les deux classeurs de lignes EJ depuis les CSV préparatoires."""
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    resultats: dict[str, Path] = {}
    for boutique in BOUTIQUES:
        chemin_csv = repertoire_staging / f"EJ_LIGNES_TICKETS_{boutique}.csv"
        if not chemin_csv.is_file():
            raise FileNotFoundError(f"CSV préparatoire introuvable : {chemin_csv}")
        destination = repertoire_sortie / f"TTS_EJ_LIGNES_TICKETS_{boutique}.ods"
        creer_et_enregistrer_classeur(
            uno,
            soffice,
            destination,
            FeuilleEjTickets.TICKETS.pour(boutique),
            chemin_csv,
            boutique=boutique,
        )
        resultats[boutique] = destination
    return resultats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, default=Path("output/travaux_preliminaires"))
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--soffice", default="soffice")
    parser.add_argument("--python-uno", type=Path, default=None)
    args = parser.parse_args(argv)
    uno = pyuno_disponible()
    if uno is None:
        python_uno = args.python_uno or python_pyuno_defaut()
        environnement = os.environ.copy()
        racine_src = str(Path(__file__).resolve().parents[1])
        environnement["PYTHONPATH"] = racine_src + os.pathsep + environnement.get("PYTHONPATH", "")
        return subprocess.run(
            [str(python_uno), str(Path(__file__).resolve()), *(argv or sys.argv[1:])],
            env=environnement,
        ).returncode

    resultats = generer_classeurs(args.staging, args.sortie, uno, args.soffice)
    for boutique, chemin in resultats.items():
        print(f"{boutique} : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
