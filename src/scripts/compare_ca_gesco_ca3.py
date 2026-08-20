"""Génère la comparaison des recettes reconstituées avec les CA3."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from scripts.recettes_mensuelles import (
    NOM_FICHIER as NOM_FICHIER_RECETTES,
    NOM_FEUILLE as NOM_FEUILLE_RECETTES,
    _donnees_utilisees,
    _entier,
    _mois,
    _montant,
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


NOM_FICHIER = "CompareCA_Gesco_CA3.ods"
NOM_FEUILLE = "CompareCA_Gesco_CA3"
COLONNES_SOURCE = (
    "AJ_ANNEE",
    "AJ_MOIS",
    "AJ_TOTAL_TOUS_BOUTIQUE_HT",
    "AJ_TOTAL_TOUS_BOUTIQUE_TVA",
    "AJ_TOTAL_TOUS_BOUTIQUE_TTC",
)
COLONNES_DESTINATION = (
    *COLONNES_SOURCE,
    "MTT_HT_CA3",
    "MTT_HT_20_CA3",
    "MTT_TVA_20_CA3",
    "AJ_ECART_HT20",
    "AJ_ECART_TVA20",
)
FORMAT_NOMBRE = "0,00"


def extraire_recettes_reconstituees(
    donnees: Sequence[Sequence[object]],
) -> tuple[tuple[object, ...], ...]:
    """Extrait et trie les montants contractuels de la feuille consolidée."""
    if not donnees:
        raise ValueError("Feuille de recettes mensuelles toutes boutiques vide")
    entetes = tuple(str(valeur).strip() for valeur in donnees[0])
    manquantes = set(COLONNES_SOURCE) - set(entetes)
    if manquantes:
        raise ValueError(
            "Colonnes absentes des recettes mensuelles toutes boutiques : "
            + ", ".join(sorted(manquantes))
        )
    index = {colonne: entetes.index(colonne) for colonne in COLONNES_SOURCE}
    resultat: dict[
        tuple[int, int], tuple[Decimal, Decimal, Decimal]
    ] = {}
    for ligne in donnees[1:]:
        if all(valeur in (None, "") for valeur in ligne):
            continue
        annee = _entier(ligne[index["AJ_ANNEE"]], "AJ_ANNEE")
        periode = (annee, _mois(ligne[index["AJ_MOIS"]], annee))
        if periode in resultat:
            raise ValueError(
                "Période dupliquée dans les recettes mensuelles toutes boutiques : "
                f"{annee}-{periode[1]:02d}"
            )
        resultat[periode] = tuple(
            _montant(ligne[index[colonne]], colonne, periode)
            for colonne in COLONNES_SOURCE[2:]
        )
    return tuple(
        (annee, mois, *resultat[(annee, mois)])
        for annee, mois in sorted(resultat)
    )


def ajouter_feuille(document: Any, lignes: Sequence[Sequence[object]]) -> None:
    """Écrit les recettes, laisse les CA3 vides et prépare les écarts."""
    feuille = document.getSheets().getByIndex(0)
    feuille.setName(NOM_FEUILLE)
    plage_entetes = feuille.getCellRangeByPosition(
        0, 0, len(COLONNES_DESTINATION) - 1, 0
    )
    plage_entetes.setDataArray((COLONNES_DESTINATION,))
    plage_entetes.CharWeight = 150
    plage_entetes.IsTextWrapped = True

    if lignes:
        valeurs = tuple(
            tuple(
                float(valeur) if isinstance(valeur, Decimal) else valeur
                for valeur in ligne
            )
            for ligne in lignes
        )
        derniere_ligne = len(valeurs)
        feuille.getCellRangeByPosition(0, 1, 4, derniere_ligne).setDataArray(
            valeurs
        )
        formules = tuple(
            (
                f'=IF(G{ligne}="";"";C{ligne}-G{ligne})',
                f'=IF(H{ligne}="";"";D{ligne}-H{ligne})',
            )
            for ligne in range(2, derniere_ligne + 2)
        )
        feuille.getCellRangeByPosition(8, 1, 9, derniere_ligne).setFormulaArray(
            formules
        )
        feuille.getCellRangeByPosition(2, 1, 9, derniere_ligne).NumberFormat = (
            obtenir_format(document.getNumberFormats(), FORMAT_NOMBRE)
        )
    definir_largeur_colonnes(feuille, len(COLONNES_DESTINATION))


def generer_classeur(
    repertoire_sortie: Path,
    uno: Any,
    soffice: str = "soffice",
    *,
    port_uno: int = 2002,
) -> Path:
    """Crée atomiquement le classeur depuis la consolidation contractuelle."""
    source = repertoire_sortie / NOM_FICHIER_RECETTES
    if not source.is_file():
        raise FileNotFoundError(f"Classeur ODS source introuvable : {source}")
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    destination = repertoire_sortie / NOM_FICHIER

    with tempfile.TemporaryDirectory(
        prefix=".compare-ca-gesco-ca3-", dir=repertoire_sortie
    ) as nom_temporaire:
        temporaire = Path(nom_temporaire)
        chemin_temporaire = temporaire / NOM_FICHIER
        processus = demarrer_libreoffice(
            soffice, temporaire / "profil", port_uno=port_uno
        )
        document_source = None
        document_destination = None
        try:
            contexte = connecter_uno(uno, port_uno=port_uno)
            bureau = contexte.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", contexte
            )
            document_source = bureau.loadComponentFromURL(
                uno.systemPathToFileUrl(str(source.resolve())),
                "_blank",
                0,
                proprietes(uno, Hidden=True, ReadOnly=True),
            )
            feuilles_source = document_source.getSheets()
            if not feuilles_source.hasByName(NOM_FEUILLE_RECETTES):
                raise ValueError(
                    f"Feuille source {NOM_FEUILLE_RECETTES!r} absente de {source}"
                )
            lignes = extraire_recettes_reconstituees(
                _donnees_utilisees(
                    feuilles_source.getByName(NOM_FEUILLE_RECETTES)
                )
            )

            document_destination = bureau.loadComponentFromURL(
                "private:factory/scalc",
                "_blank",
                0,
                proprietes(uno, Hidden=True),
            )
            ajouter_feuille(document_destination, lignes)
            document_destination.storeAsURL(
                uno.systemPathToFileUrl(str(chemin_temporaire.resolve())),
                proprietes(uno, FilterName="calc8"),
            )
        finally:
            if document_destination is not None:
                document_destination.close(True)
            if document_source is not None:
                document_source.close(True)
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()
                processus.wait(timeout=5)

        if not chemin_temporaire.is_file():
            raise RuntimeError(
                f"PyUNO n'a pas produit le fichier attendu : {chemin_temporaire}"
            )
        os.replace(chemin_temporaire, destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--soffice", default="soffice")
    parser.add_argument("--python-uno", type=Path, default=None)
    parser.add_argument("--port-uno", type=int, default=2002)
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

    destination = generer_classeur(
        args.sortie, uno, args.soffice, port_uno=args.port_uno
    )
    print(f"Comparaison CA Gesco / CA3 : {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
