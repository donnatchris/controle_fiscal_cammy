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

from scripts.ods_z2 import (
    COLONNES_TOTAL_MONTANT_MODE,
    LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
    lire_lignes_valeurs_feuille,
)
from shared.constantes import ANNEES, BOUTIQUES, FeuilleEjEntetes, FeuilleZ2Transactions
from shared.ods_helpers import (
    connecter_uno,
    copier_feuille,
    copier_valeurs_feuille,
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
# Les formats sont créés avec une locale fr-FR : la virgule est le séparateur
# décimal. Avec ``0.00``, Calc interprète le point comme un séparateur de
# milliers et affiche les montants divisés par 100, malgré une valeur correcte.
FORMAT_NOMBRE = "0,00"
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
NATURES_COMPARE_Z2_EJ = ("CARTES", "CHEQUES", "ESPECES")
COLONNES_COMPARE_MONTANT_Z2_EJ = (
    "AJ_Année_Z",
    "AJ_Mois_Z",
    *(
        colonne
        for nature in NATURES_COMPARE_Z2_EJ
        for colonne in (f"{nature}_AJ_ECART_QTE", f"{nature}_AJ_ECART_MONTANT")
    ),
)
CHAMPS_MONTANT_EJ_PAR_NATURE = {
    "CARTES": "Somme - E_MDP_CB",
    "CHEQUES": "Somme - E_MDP_CHEQUES",
    "ESPECES": "Somme - E_MDP_ESPECES",
}
MODE_Z2_PAR_BOUTIQUE = {"MASSENA": "ZZ1", "MATURIN": "Z"}


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
        champ = champs.getByIndex(index_colonnes[nom_champ])
        champ.setPropertyValue("Orientation", uno.Enum(orientation, "ROW"))
        if nom_champ == "AJ_ANNEE":
            # Affiche l'année sur chaque ligne mensuelle du DataPilot.
            champ.setPropertyValue("RepeatItemLabels", True)
    for nom_champ in CHAMPS_DONNEES_TOTAL_ENCT_TTC:
        champ = champs.getByIndex(index_colonnes[nom_champ])
        champ.setPropertyValue("Orientation", uno.Enum(orientation, "DATA"))
        champ.setPropertyValue("Function", uno.Enum(fonction, "SUM"))
        champ.setPropertyValue("Name", f"Somme - {nom_champ}")
    descripteur.getDataLayoutField().setPropertyValue(
        "Orientation", uno.Enum(orientation, "COLUMN")
    )

    tableaux.insertNewByName(
        nom_destination,
        feuille_destination.getCellByPosition(0, 0).CellAddress,
        descripteur,
    )
    definir_largeur_colonnes(
        feuille_destination,
        len(CHAMPS_LIGNES_TOTAL_ENCT_TTC) + len(CHAMPS_DONNEES_TOTAL_ENCT_TTC),
    )


def ajouter_encts_mensuels(document: Any, boutique: str) -> None:
    """Copie en valeurs le DataPilot aplati sans son étiquette technique Data."""
    feuille_destination = copier_valeurs_feuille(
        document,
        FeuilleEjEntetes.TD_TOTAL_ENCT.pour(boutique),
        FeuilleEjEntetes.ENCT_MENSUELS.pour(boutique),
    )
    curseur = feuille_destination.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    valeurs = feuille_destination.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()
    for index_ligne, ligne in enumerate(valeurs):
        for index_colonne, valeur in enumerate(ligne):
            if valeur == "Data":
                feuille_destination.getCellByPosition(index_colonne, index_ligne).String = ""
    if valeurs and all(valeur in (None, "", "Data") for valeur in valeurs[0]):
        feuille_destination.getRows().removeByIndex(0, 1)
    definir_largeur_colonnes(
        feuille_destination,
        len(CHAMPS_LIGNES_TOTAL_ENCT_TTC) + len(CHAMPS_DONNEES_TOTAL_ENCT_TTC),
    )


def _valeur_decimal(valeur: object | None) -> Decimal:
    """Retourne zéro pour une valeur absente, sinon un montant exact."""
    if valeur in (None, ""):
        return Decimal()
    return Decimal(str(valeur))


def _cle_periode(ligne: dict[str, object], annee: str, mois: str) -> tuple[int, str]:
    """Normalise les clés de période Z2 et EJ pour un rapprochement logique."""
    return int(_valeur_decimal(ligne[annee])), str(ligne[mois])


def _lire_lignes_encts_mensuels(feuille: Any) -> tuple[dict[str, object], ...]:
    """Lit les montants mensuels EJ depuis la feuille copiée en valeurs."""
    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    donnees = feuille.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()
    champs = ("AJ_ANNEE", "AJ_MOIS", *CHAMPS_MONTANT_EJ_PAR_NATURE.values())
    index_entete = next(
        (index for index, ligne in enumerate(donnees) if all(champ in ligne for champ in champs)),
        None,
    )
    if index_entete is None:
        raise ValueError("En-têtes des encaissements mensuels EJ introuvables")

    index_colonnes = {str(nom): index for index, nom in enumerate(donnees[index_entete])}
    return tuple(
        {champ: ligne[index_colonnes[champ]] for champ in champs}
        for ligne in donnees[index_entete + 1 :]
        if ligne[index_colonnes["AJ_ANNEE"]] not in (None, "")
        and ligne[index_colonnes["AJ_MOIS"]] not in (None, "")
    )


def comparer_z2_mode_retenu_et_ej_par_periode(
    lignes_z2: tuple[dict[str, object], ...],
    lignes_ej: tuple[dict[str, object], ...],
    annee: int,
) -> tuple[tuple[object, ...], ...]:
    """Compare les montants du mode Z2 retenu et EJ, sans quantité EJ inventée."""
    def indexer(
        lignes: tuple[dict[str, object], ...], annee_champ: str, mois_champ: str
    ) -> dict[tuple[int, str], dict[str, object]]:
        resultat = {}
        for ligne in lignes:
            cle = _cle_periode(ligne, annee_champ, mois_champ)
            if cle[0] != annee:
                continue
            if cle in resultat:
                raise ValueError(f"Période dupliquée dans une feuille de comparaison : {cle}")
            resultat[cle] = ligne
        return resultat

    z2_par_periode = indexer(lignes_z2, "AJ_Année_Z", "AJ_Mois_Z")
    ej_par_periode = indexer(lignes_ej, "AJ_ANNEE", "AJ_MOIS")
    resultats = []
    for periode in sorted(set(z2_par_periode) | set(ej_par_periode)):
        z2 = z2_par_periode.get(periode, {})
        ej = ej_par_periode.get(periode, {})
        resultats.append(
            (
                float(periode[0]),
                periode[1],
                *(
                    valeur
                    for nature in NATURES_COMPARE_Z2_EJ
                    for valeur in (
                        "",  # Aucune quantité de règlement comparable n'est disponible côté EJ.
                        float(
                            _valeur_decimal(z2.get(f"{nature}_D_MONTANT"))
                            - _valeur_decimal(ej.get(CHAMPS_MONTANT_EJ_PAR_NATURE[nature]))
                        ),
                    )
                ),
            )
        )
    return tuple(resultats)


def _nom_comparaison_z2_ej(boutique: str, annee: int) -> str:
    constante = (
        FeuilleEjEntetes.COMPARE_Z2_MODE_ZZ1_VS_EJ
        if MODE_Z2_PAR_BOUTIQUE[boutique] == "ZZ1"
        else FeuilleEjEntetes.COMPARE_Z2_MODE_Z_VS_EJ
    )
    return constante.pour(boutique, annee)


def ajouter_comparaison_z2_ej(
    document_destination: Any,
    document_ej: Any,
    document_z2: Any,
    boutique: str,
    annee: int,
) -> None:
    """Écrit dans un classeur autonome les écarts mensuels entre Z2 et EJ."""
    feuilles_ej = document_ej.getSheets()
    feuilles_z2 = document_z2.getSheets()
    constante_source = (
        FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ1
        if MODE_Z2_PAR_BOUTIQUE[boutique] == "ZZ1"
        else FeuilleZ2Transactions.Z2_TOTAL_MOIS_ANNEE_NATURE_MODE_Z
    )
    nom_feuille_z2 = constante_source.pour(boutique, annee)
    if feuilles_z2.hasByName(nom_feuille_z2) is False:
        raise ValueError(
            f"Comparaison Z2/EJ non applicable pour {annee} {boutique} : "
            f"feuille Z2 absente ({nom_feuille_z2})."
        )
    feuille_z2 = feuilles_z2.getByName(nom_feuille_z2)
    feuille_ej = feuilles_ej.getByName(FeuilleEjEntetes.ENCT_MENSUELS.pour(boutique))
    lignes = comparer_z2_mode_retenu_et_ej_par_periode(
        lire_lignes_valeurs_feuille(
            feuille_z2,
            COLONNES_TOTAL_MONTANT_MODE,
            LIGNE_DONNEES_TOTAL_MONTANT_MODE_ZZ1,
        ),
        _lire_lignes_encts_mensuels(feuille_ej),
        annee,
    )

    nom_destination = _nom_comparaison_z2_ej(boutique, annee)
    feuilles_destination = document_destination.getSheets()
    feuille_destination = feuilles_destination.getByIndex(0)
    feuille_destination.setName(nom_destination)
    plage_entetes = feuille_destination.getCellRangeByPosition(
        0, 0, len(COLONNES_COMPARE_MONTANT_Z2_EJ) - 1, 0
    )
    plage_entetes.setDataArray((COLONNES_COMPARE_MONTANT_Z2_EJ,))
    plage_entetes.CharWeight = 150

    if lignes:
        derniere_ligne = len(lignes)
        feuille_destination.getCellRangeByPosition(
            0, 1, len(COLONNES_COMPARE_MONTANT_Z2_EJ) - 1, derniere_ligne
        ).setDataArray(lignes)
        formats = document_destination.getNumberFormats()
        feuille_destination.getCellRangeByPosition(0, 1, 0, derniere_ligne).NumberFormat = (
            obtenir_format(formats, "0")
        )
        for index_colonne in range(3, len(COLONNES_COMPARE_MONTANT_Z2_EJ), 2):
            feuille_destination.getCellRangeByPosition(
                index_colonne, 1, index_colonne, derniere_ligne
            ).NumberFormat = obtenir_format(formats, FORMAT_NOMBRE)
    definir_largeur_colonnes(feuille_destination, len(COLONNES_COMPARE_MONTANT_Z2_EJ))


def supprimer_comparaisons_z2_ej_integrees(document_ej: Any, boutique: str) -> None:
    """Retire les anciennes comparaisons inter-classeurs du classeur EJ."""
    feuilles = document_ej.getSheets()
    prefixe = f"Compare_Montant_{boutique}_Z2Mode"
    for nom in tuple(feuilles.getElementNames()):
        if str(nom).startswith(prefixe) and str(nom).lower().endswith(
            tuple(f"vsej_{annee}" for annee in ANNEES)
        ):
            feuilles.removeByName(nom)


def enregistrer_comparaison_z2_ej(
    uno: Any,
    bureau: Any,
    document_ej: Any,
    document_z2: Any,
    repertoire_temporaire: Path,
    repertoire_sortie: Path,
    boutique: str,
    annee: int,
) -> Path:
    """Crée atomiquement un ODS autonome contenant une unique comparaison."""
    nom_feuille = _nom_comparaison_z2_ej(boutique, annee)
    destination = repertoire_sortie / f"{nom_feuille}.ods"
    temporaire_ods = repertoire_temporaire / destination.name
    document_destination = bureau.loadComponentFromURL(
        "private:factory/scalc", "_blank", 0, ()
    )
    try:
        ajouter_comparaison_z2_ej(
            document_destination,
            document_ej,
            document_z2,
            boutique,
            annee,
        )
        document_destination.storeAsURL(
            uno.systemPathToFileUrl(str(temporaire_ods)),
            proprietes(uno, FilterName="calc8"),
        )
    finally:
        document_destination.close(True)
    if not temporaire_ods.is_file():
        raise RuntimeError(f"PyUNO n'a pas produit le fichier attendu : {temporaire_ods}")
    os.replace(temporaire_ods, destination)
    return destination


def enrichir_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    *,
    boutique: str,
) -> None:
    """Enrichit l'ODS EJ et génère séparément les comparaisons Z2/EJ."""
    if not destination.is_file():
        raise FileNotFoundError(f"Classeur ODS introuvable : {destination}")

    with tempfile.TemporaryDirectory(
        prefix=".ods-ej-entetes-2-", dir=destination.parent
    ) as nom_temporaire:
        temporaire = Path(nom_temporaire)
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
            supprimer_comparaisons_z2_ej_integrees(document, boutique)
            for annee in ANNEES:
                chemin_z2 = destination.parent / (
                    f"TTS_Z2_TransactionsMois_TOUS_{annee}_{boutique}.ods"
                )
                if not chemin_z2.is_file():
                    raise FileNotFoundError(f"Classeur ODS Z2 introuvable : {chemin_z2}")
                document_z2 = bureau.loadComponentFromURL(
                    uno.systemPathToFileUrl(str(chemin_z2)),
                    "_blank",
                    0,
                    proprietes(uno, Hidden=True, ReadOnly=True),
                )
                try:
                    chemin_comparaison = enregistrer_comparaison_z2_ej(
                        uno,
                        bureau,
                        document,
                        document_z2,
                        temporaire,
                        destination.parent,
                        boutique,
                        annee,
                    )
                    print(f"Comparaison Z2/EJ : {chemin_comparaison}")
                finally:
                    document_z2.close(True)
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
        os.replace(temporaire_ods, destination)


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
