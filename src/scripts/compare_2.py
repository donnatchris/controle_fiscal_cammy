"""Ajoute les recettes mensuelles EJ puis leur comparaison avec les montants Z1."""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Sequence

from shared.constantes import (
    ANNEES,
    BOUTIQUES,
    FeuilleEjEntetes,
    FeuilleZ1SyntheseMois,
)
from shared.ods_helpers import (
    connecter_uno,
    definir_largeur_colonnes,
    demarrer_libreoffice,
    obtenir_format,
    proprietes,
    python_pyuno_defaut,
    pyuno_disponible,
)


CHAMPS_LIGNES_TOTAL_HT_TVA_TTC = ("AJ_ANNEE", "AJ_MOIS")
CHAMPS_DONNEES_TOTAL_HT_TVA_TTC = (
    "AJ_TOTAL_HT",
    "AJ_TOTAL_TVA_20",
    "E_TTC",
)
COLONNES_RECETTES_MENSUELLES = (
    *CHAMPS_LIGNES_TOTAL_HT_TVA_TTC,
    *(f"Somme - {champ}" for champ in CHAMPS_DONNEES_TOTAL_HT_TVA_TTC),
)
# ``obtenir_format`` utilise fr-FR, donc le code de format doit employer la
# virgule décimale. Le point ferait afficher 63 641,51 sous la forme 636,42.
FORMAT_NOMBRE = "0,00"
COLONNES_COMPARAISON_Z1_EJ = (
    "AJ_Année_Z",
    "AJ_Mois_Z",
    "AJ_ECART_CA_TTC",
    "AJ_ECART_HORS_TAXE_1",
    "AJ_ECART_TVA1",
)
COLONNES_MONTANTS_Z1 = ("CA NET", "HORS TAXES 1", "TVA 1")
COLONNES_MONTANTS_EJ = (
    "Somme - E_TTC",
    "Somme - AJ_TOTAL_HT",
    "Somme - AJ_TOTAL_TVA_20",
)
MODE_Z1_PAR_BOUTIQUE = {"MASSENA": "ZZ1", "MATURIN": "Z"}


@dataclass(frozen=True)
class ResultatComparaisonZ1Ej:
    """Valeurs à écrire et absences de périodes constatées dans les sources."""

    lignes: tuple[tuple[object, ...], ...]
    periodes_absentes_z1: tuple[tuple[str, str], ...]
    periodes_absentes_ej: tuple[tuple[str, str], ...]


def ajouter_TotalHtTvaTtc(document: Any, boutique: str) -> None:
    """Crée le DataPilot HT, TVA et TTC par année et mois."""
    import uno

    nom_source = FeuilleEjEntetes.CPLTE_ANNEE_MOIS.pour(boutique)
    nom_destination = FeuilleEjEntetes.TD_TOTAL_HT_TVA_TTC.pour(boutique)
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
    champs_requis = set(
        CHAMPS_LIGNES_TOTAL_HT_TVA_TTC + CHAMPS_DONNEES_TOTAL_HT_TVA_TTC
    )
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
    for nom_champ in CHAMPS_LIGNES_TOTAL_HT_TVA_TTC:
        champ = champs.getByIndex(index_colonnes[nom_champ])
        champ.setPropertyValue("Orientation", uno.Enum(orientation, "ROW"))
        if nom_champ == "AJ_ANNEE":
            champ.setPropertyValue("RepeatItemLabels", True)
    for nom_champ in CHAMPS_DONNEES_TOTAL_HT_TVA_TTC:
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
    definir_largeur_colonnes(feuille_destination, len(COLONNES_RECETTES_MENSUELLES))


def _donnees_utilisees(feuille: Any) -> tuple[tuple[object, ...], ...]:
    """Lit la zone utilisée d'une feuille sous forme de valeurs UNO."""
    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    return feuille.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()


def extraire_recettes_du_datapilot(
    feuille: Any,
) -> tuple[tuple[object, ...], ...]:
    """Aplatit les valeurs mensuelles du DataPilot dans l'ordre contractuel."""
    donnees = _donnees_utilisees(feuille)
    index_entete = next(
        (
            index
            for index, ligne in enumerate(donnees)
            if all(colonne in ligne for colonne in COLONNES_RECETTES_MENSUELLES)
        ),
        None,
    )
    if index_entete is None:
        raise ValueError("En-têtes du DataPilot HT/TVA/TTC introuvables")

    index_colonnes = {
        colonne: donnees[index_entete].index(colonne)
        for colonne in COLONNES_RECETTES_MENSUELLES
    }
    annee_courante: object = ""
    lignes: list[tuple[object, ...]] = []
    periodes: set[tuple[str, str]] = set()
    for ligne in donnees[index_entete + 1 :]:
        annee = ligne[index_colonnes["AJ_ANNEE"]]
        if annee not in (None, ""):
            annee_courante = annee
        mois = ligne[index_colonnes["AJ_MOIS"]]
        if mois in (None, ""):
            continue
        if annee_courante in (None, ""):
            raise ValueError(f"Année absente pour la période {mois!r} du DataPilot")

        montants = tuple(
            ligne[index_colonnes[colonne]]
            for colonne in COLONNES_RECETTES_MENSUELLES[2:]
        )
        if any(
            isinstance(montant, bool)
            or not isinstance(montant, (int, float))
            or not math.isfinite(float(montant))
            for montant in montants
        ):
            raise ValueError(f"Montant non numérique dans le DataPilot pour {mois!r}")

        cle = (str(annee_courante), str(mois))
        if cle in periodes:
            raise ValueError(f"Période dupliquée dans le DataPilot : {cle}")
        periodes.add(cle)
        lignes.append((annee_courante, mois, *montants))

    return tuple(sorted(lignes, key=lambda ligne: (str(ligne[0]), str(ligne[1]))))


def ajouter_recettes_mensuelles(document: Any, boutique: str) -> None:
    """Copie les résultats du DataPilot dans une table classique en valeurs."""
    feuilles = document.getSheets()
    nom_source = FeuilleEjEntetes.TD_TOTAL_HT_TVA_TTC.pour(boutique)
    nom_destination = FeuilleEjEntetes.RECETTES_MENSUELLES.pour(boutique)
    lignes = extraire_recettes_du_datapilot(feuilles.getByName(nom_source))

    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)
    feuille_destination.getCellRangeByPosition(
        0, 0, len(COLONNES_RECETTES_MENSUELLES) - 1, 0
    ).setDataArray((COLONNES_RECETTES_MENSUELLES,))
    feuille_destination.getCellRangeByPosition(
        0, 0, len(COLONNES_RECETTES_MENSUELLES) - 1, 0
    ).CharWeight = 150

    if lignes:
        derniere_ligne = len(lignes)
        feuille_destination.getCellRangeByPosition(
            0, 1, len(COLONNES_RECETTES_MENSUELLES) - 1, derniere_ligne
        ).setDataArray(lignes)
        feuille_destination.getCellRangeByPosition(
            2, 1, len(COLONNES_RECETTES_MENSUELLES) - 1, derniere_ligne
        ).NumberFormat = obtenir_format(document.getNumberFormats(), FORMAT_NOMBRE)

    valeurs_ecrites = _donnees_utilisees(feuille_destination)
    attendu = (COLONNES_RECETTES_MENSUELLES, *lignes)
    if valeurs_ecrites != attendu:
        raise RuntimeError(
            f"La feuille {nom_destination} ne concorde pas avec le DataPilot {nom_source}"
        )
    definir_largeur_colonnes(feuille_destination, len(COLONNES_RECETTES_MENSUELLES))


def ajouter_feuilles_recettes(document: Any, boutique: str) -> None:
    """Exécute les deux étapes contractuelles HT/TVA/TTC pour une boutique."""
    ajouter_TotalHtTvaTtc(document, boutique)
    ajouter_recettes_mensuelles(document, boutique)


def _texte_entier(valeur: object, nom_colonne: str) -> str:
    """Normalise une année Calc entière sans toucher aux identifiants textuels."""
    if valeur in (None, "") or isinstance(valeur, bool):
        raise ValueError(f"{nom_colonne} absent ou invalide : {valeur!r}")
    texte = str(valeur).strip()
    try:
        decimal = Decimal(texte)
    except InvalidOperation:
        return texte
    if decimal != decimal.to_integral_value():
        raise ValueError(f"{nom_colonne} non entier : {valeur!r}")
    return str(int(decimal))


def _decimal_montant(
    valeur: object,
    colonne: str,
    periode: tuple[str, str],
) -> Decimal:
    if valeur in (None, "") or isinstance(valeur, bool):
        raise ValueError(f"Montant {colonne} absent pour la période {periode}")
    try:
        montant = Decimal(str(valeur).strip())
    except InvalidOperation as erreur:
        raise ValueError(
            f"Montant {colonne} invalide pour la période {periode} : {valeur!r}"
        ) from erreur
    if not montant.is_finite():
        raise ValueError(f"Montant {colonne} non fini pour la période {periode}")
    return montant


def _trouver_entetes(
    donnees: Sequence[Sequence[object]],
    colonnes_requises: Iterable[str],
) -> tuple[int, dict[str, int]]:
    requises = tuple(colonnes_requises)
    for index_ligne, ligne in enumerate(donnees):
        entetes = tuple(str(valeur).strip() for valeur in ligne)
        if all(colonne in entetes for colonne in requises):
            return index_ligne, {
                colonne: entetes.index(colonne) for colonne in requises
            }
    raise ValueError("En-têtes contractuels introuvables : " + ", ".join(requises))


def indexer_montants_par_periode(
    donnees: Sequence[Sequence[object]],
    *,
    colonne_annee: str,
    colonne_mois: str,
    colonnes_montants: Sequence[str],
    annee_attendue: int,
) -> dict[tuple[str, str], tuple[Decimal, ...]]:
    """Indexe une feuille contractuelle et refuse toute période dupliquée."""
    requises = (colonne_annee, colonne_mois, *colonnes_montants)
    index_entete, index = _trouver_entetes(donnees, requises)
    annee_texte = str(annee_attendue)
    resultats: dict[tuple[str, str], tuple[Decimal, ...]] = {}
    for ligne in donnees[index_entete + 1 :]:
        if len(ligne) <= max(index.values()):
            continue
        valeur_annee = ligne[index[colonne_annee]]
        valeur_mois = ligne[index[colonne_mois]]
        if valeur_annee in (None, "") and valeur_mois in (None, ""):
            continue
        annee = _texte_entier(valeur_annee, colonne_annee)
        mois = str(valeur_mois).strip()
        if not mois:
            raise ValueError(f"{colonne_mois} absent pour l'année {annee}")
        if annee != annee_texte:
            continue
        periode = (annee, mois)
        if periode in resultats:
            raise ValueError(f"Période dupliquée : {periode}")
        resultats[periode] = tuple(
            _decimal_montant(ligne[index[colonne]], colonne, periode)
            for colonne in colonnes_montants
        )
    return resultats


def comparer_montants_mensuels_z1_ej(
    donnees_z1: Sequence[Sequence[object]],
    donnees_ej: Sequence[Sequence[object]],
    annee: int,
) -> ResultatComparaisonZ1Ej:
    """Joint Z1 et EJ par année/mois et calcule exactement Z1 moins EJ."""
    z1 = indexer_montants_par_periode(
        donnees_z1,
        colonne_annee="AJ_Année_Z",
        colonne_mois="AJ_Mois_Z",
        colonnes_montants=COLONNES_MONTANTS_Z1,
        annee_attendue=annee,
    )
    ej = indexer_montants_par_periode(
        donnees_ej,
        colonne_annee="AJ_ANNEE",
        colonne_mois="AJ_MOIS",
        colonnes_montants=COLONNES_MONTANTS_EJ,
        annee_attendue=annee,
    )
    periodes = tuple(sorted(z1.keys() | ej.keys()))
    lignes: list[tuple[object, ...]] = []
    for periode in periodes:
        if periode not in z1 or periode not in ej:
            lignes.append((*periode, "", "", ""))
            continue
        ecarts = tuple(
            montant_z1 - montant_ej
            for montant_z1, montant_ej in zip(
                z1[periode], ej[periode], strict=True
            )
        )
        lignes.append((*periode, *ecarts))
    return ResultatComparaisonZ1Ej(
        lignes=tuple(lignes),
        periodes_absentes_z1=tuple(sorted(ej.keys() - z1.keys())),
        periodes_absentes_ej=tuple(sorted(z1.keys() - ej.keys())),
    )


def _nom_feuille_z1(boutique: str, annee: int) -> str:
    constante = (
        FeuilleZ1SyntheseMois.Z1_TOTAL_MOIS_ANNEE_NATURE_MODE_ZZ1
        if MODE_Z1_PAR_BOUTIQUE[boutique] == "ZZ1"
        else FeuilleZ1SyntheseMois.Z1_TOTAL_MOIS_ANNEE_NATURE_MODE_Z
    )
    return constante.pour(boutique, annee)


def _nom_feuille_comparaison_z1_ej(boutique: str, annee: int) -> str:
    constante = (
        FeuilleZ1SyntheseMois.COMPARE_MONTANT_Z1_MODE_ZZ1_VS_EJ
        if MODE_Z1_PAR_BOUTIQUE[boutique] == "ZZ1"
        else FeuilleZ1SyntheseMois.COMPARE_MONTANT_Z1_MODE_Z_VS_EJ
    )
    return constante.pour(boutique, annee)


def ajouter_feuille_comparaison_z1_ej(
    document_destination: Any,
    document_ej: Any,
    document_z1: Any,
    boutique: str,
    annee: int,
) -> ResultatComparaisonZ1Ej:
    """Écrit dans un classeur autonome la comparaison Z1/EJ en valeurs."""
    feuilles_ej = document_ej.getSheets()
    feuille_ej = feuilles_ej.getByName(
        FeuilleEjEntetes.RECETTES_MENSUELLES.pour(boutique)
    )
    feuille_z1 = document_z1.getSheets().getByName(
        _nom_feuille_z1(boutique, annee)
    )
    resultat = comparer_montants_mensuels_z1_ej(
        _donnees_utilisees(feuille_z1),
        _donnees_utilisees(feuille_ej),
        annee,
    )

    nom_destination = _nom_feuille_comparaison_z1_ej(boutique, annee)
    destination = document_destination.getSheets().getByIndex(0)
    destination.setName(nom_destination)
    destination.getCellRangeByPosition(0, 0, 4, 0).setDataArray(
        (COLONNES_COMPARAISON_Z1_EJ,)
    )
    destination.getCellRangeByPosition(0, 0, 4, 0).CharWeight = 150
    if resultat.lignes:
        valeurs_uno = tuple(
            tuple(
                float(valeur) if isinstance(valeur, Decimal) else valeur
                for valeur in ligne
            )
            for ligne in resultat.lignes
        )
        destination.getCellRangeByPosition(
            0, 1, 4, len(valeurs_uno)
        ).setDataArray(valeurs_uno)
        destination.getCellRangeByPosition(
            2, 1, 4, len(valeurs_uno)
        ).NumberFormat = obtenir_format(
            document_destination.getNumberFormats(), FORMAT_NOMBRE
        )
    definir_largeur_colonnes(destination, len(COLONNES_COMPARAISON_Z1_EJ))
    return resultat


def _afficher_absences(
    boutique: str,
    annee: int,
    resultat: ResultatComparaisonZ1Ej,
) -> None:
    for libelle, periodes in (
        ("Z1", resultat.periodes_absentes_z1),
        ("EJ", resultat.periodes_absentes_ej),
    ):
        if periodes:
            print(
                f"CONTRÔLE {boutique} {annee} : périodes absentes de {libelle} : "
                + ", ".join(mois for _, mois in periodes)
            )


def supprimer_comparaisons_z1_ej_integrees(document_ej: Any, boutique: str) -> None:
    """Retire les anciennes comparaisons inter-classeurs du classeur EJ."""
    feuilles = document_ej.getSheets()
    prefixe = f"Compare_Montant_{boutique}_Z1Mode"
    for nom in tuple(feuilles.getElementNames()):
        if str(nom).startswith(prefixe) and str(nom).lower().endswith(
            tuple(f"vsej_{annee}" for annee in ANNEES)
        ):
            feuilles.removeByName(nom)


def enregistrer_comparaison_z1_ej(
    uno: Any,
    bureau: Any,
    document_ej: Any,
    document_z1: Any,
    repertoire_temporaire: Path,
    repertoire_sortie: Path,
    boutique: str,
    annee: int,
) -> tuple[Path, ResultatComparaisonZ1Ej]:
    """Crée atomiquement un ODS autonome contenant une unique comparaison."""
    nom_feuille = _nom_feuille_comparaison_z1_ej(boutique, annee)
    destination = repertoire_sortie / f"{nom_feuille}.ods"
    temporaire_ods = repertoire_temporaire / destination.name
    document_destination = bureau.loadComponentFromURL(
        "private:factory/scalc", "_blank", 0, ()
    )
    try:
        resultat = ajouter_feuille_comparaison_z1_ej(
            document_destination,
            document_ej,
            document_z1,
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
    return destination, resultat


def enrichir_et_enregistrer_classeur(
    uno: Any,
    soffice: str,
    destination: Path,
    *,
    boutique: str,
) -> None:
    """Ajoute les recettes à l'ODS EJ et génère les comparaisons Z1 séparées."""
    if not destination.is_file():
        raise FileNotFoundError(f"Classeur ODS introuvable : {destination}")
    sources_z1 = {
        annee: destination.parent
        / FeuilleZ1SyntheseMois.FICHIER_ODS.pour(boutique, annee)
        for annee in ANNEES
    }
    for source in sources_z1.values():
        if not source.is_file():
            raise FileNotFoundError(f"Classeur ODS Z1 introuvable : {source}")

    with tempfile.TemporaryDirectory(
        prefix=".ods-ej-entetes-3-", dir=destination.parent
    ) as repertoire_temporaire:
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
            ajouter_feuilles_recettes(document, boutique)
            supprimer_comparaisons_z1_ej_integrees(document, boutique)
            for annee, source_z1 in sources_z1.items():
                document_z1 = bureau.loadComponentFromURL(
                    uno.systemPathToFileUrl(str(source_z1)),
                    "_blank",
                    0,
                    proprietes(uno, Hidden=True, ReadOnly=True),
                )
                try:
                    chemin_comparaison, resultat = enregistrer_comparaison_z1_ej(
                        uno,
                        bureau,
                        document,
                        document_z1,
                        temporaire,
                        destination.parent,
                        boutique,
                        annee,
                    )
                    print(f"Comparaison Z1/EJ : {chemin_comparaison}")
                finally:
                    document_z1.close(True)
                _afficher_absences(boutique, annee, resultat)
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
    """Ajoute les recettes aux EJ et produit les comparaisons Z1 autonomes."""
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
