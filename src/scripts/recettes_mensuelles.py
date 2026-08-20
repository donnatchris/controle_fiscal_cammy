"""Consolide les recettes mensuelles MASSENA et MATURIN dans un ODS."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from shared.constantes import BOUTIQUES, FeuilleEjEntetes
from shared.ods_helpers import (
    connecter_uno,
    definir_largeur_colonnes,
    demarrer_libreoffice,
    obtenir_format,
    proprietes,
    python_pyuno_defaut,
    pyuno_disponible,
)


NOM_FICHIER = "recettes_mensuelles_tous_boutique_232425.ods"
NOM_FEUILLE = "recettes_mensuelles_tous_boutique_232425"
FICHIER_EJ_PAR_BOUTIQUE = {
    boutique: f"TTS_EJ_ENTETES_TICKETS_{boutique}.ods" for boutique in BOUTIQUES
}
COLONNES_SOURCE = (
    "AJ_ANNEE",
    "AJ_MOIS",
    "Somme - AJ_TOTAL_HT",
    "Somme - AJ_TOTAL_TVA_20",
    "Somme - E_TTC",
)
COLONNES_DESTINATION = (
    "AJ_ANNEE",
    "AJ_MOIS",
    "MASSENA_SOMME_AJ_TOTAL_HT",
    "MASSENA_SOMME_AJ_TOTAL_TVA_20",
    "MASSENA_SOMME_E_TTC",
    "MATURIN_SOMME_AJ_TOTAL_HT",
    "MATURIN_SOMME_AJ_TOTAL_TVA_20",
    "MATURIN_SOMME_E_TTC",
    "AJ_TOTAL_TOUS_BOUTIQUE_HT",
    "AJ_TOTAL_TOUS_BOUTIQUE_TVA",
    "AJ_TOTAL_TOUS_BOUTIQUE_TTC",
)
FORMAT_NOMBRE = "0,00"


def _donnees_utilisees(feuille: Any) -> tuple[tuple[object, ...], ...]:
    """Retourne la zone utilisée d'une feuille Calc."""
    curseur = feuille.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    return feuille.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()


def _entier(valeur: object, colonne: str) -> int:
    if valeur in (None, "") or isinstance(valeur, bool):
        raise ValueError(f"{colonne} absent ou invalide : {valeur!r}")
    try:
        nombre = Decimal(str(valeur).strip())
    except InvalidOperation as erreur:
        raise ValueError(f"{colonne} invalide : {valeur!r}") from erreur
    if not nombre.is_finite() or nombre != nombre.to_integral_value():
        raise ValueError(f"{colonne} n'est pas un entier : {valeur!r}")
    return int(nombre)


def _mois(valeur: object, annee: int) -> int:
    """Accepte un mois numérique ou la période historique ``AAAA-MM``."""
    texte = str(valeur).strip()
    if "-" in texte:
        annee_mois = texte.split("-", 1)
        if len(annee_mois) != 2 or _entier(annee_mois[0], "AJ_ANNEE") != annee:
            raise ValueError(f"AJ_MOIS incohérent avec AJ_ANNEE : {valeur!r}")
        texte = annee_mois[1]
    mois = _entier(texte, "AJ_MOIS")
    if not 1 <= mois <= 12:
        raise ValueError(f"AJ_MOIS hors limites : {valeur!r}")
    return mois


def _montant(valeur: object, colonne: str, periode: tuple[int, int]) -> Decimal:
    if valeur in (None, "") or isinstance(valeur, bool):
        raise ValueError(f"{colonne} absent pour {periode[0]}-{periode[1]:02d}")
    try:
        montant = Decimal(str(valeur).strip())
    except InvalidOperation as erreur:
        raise ValueError(
            f"{colonne} invalide pour {periode[0]}-{periode[1]:02d} : {valeur!r}"
        ) from erreur
    if not montant.is_finite():
        raise ValueError(f"{colonne} non fini pour {periode[0]}-{periode[1]:02d}")
    return montant


def indexer_recettes(
    donnees: Sequence[Sequence[object]], boutique: str
) -> dict[tuple[int, int], tuple[Decimal, Decimal, Decimal]]:
    """Indexe une feuille source et refuse les périodes dupliquées."""
    if not donnees:
        raise ValueError(f"Feuille de recettes {boutique} vide")
    entetes = tuple(str(valeur).strip() for valeur in donnees[0])
    manquantes = set(COLONNES_SOURCE) - set(entetes)
    if manquantes:
        raise ValueError(
            f"Colonnes absentes des recettes {boutique} : "
            + ", ".join(sorted(manquantes))
        )
    index = {colonne: entetes.index(colonne) for colonne in COLONNES_SOURCE}
    resultat: dict[tuple[int, int], tuple[Decimal, Decimal, Decimal]] = {}
    for ligne in donnees[1:]:
        if all(valeur in (None, "") for valeur in ligne):
            continue
        annee = _entier(ligne[index["AJ_ANNEE"]], "AJ_ANNEE")
        periode = (annee, _mois(ligne[index["AJ_MOIS"]], annee))
        if periode in resultat:
            raise ValueError(
                f"Période dupliquée dans les recettes {boutique} : "
                f"{annee}-{periode[1]:02d}"
            )
        resultat[periode] = tuple(
            _montant(ligne[index[colonne]], colonne, periode)
            for colonne in COLONNES_SOURCE[2:]
        )
    return resultat


def consolider_recettes(
    recettes_par_boutique: Mapping[
        str, Mapping[tuple[int, int], tuple[Decimal, Decimal, Decimal]]
    ],
) -> tuple[tuple[object, ...], ...]:
    """Joint les deux boutiques par période sans inventer de mois ou montant."""
    manquantes = set(BOUTIQUES) - recettes_par_boutique.keys()
    if manquantes:
        raise ValueError("Boutiques absentes : " + ", ".join(sorted(manquantes)))
    periodes_massena = set(recettes_par_boutique["MASSENA"])
    periodes_maturin = set(recettes_par_boutique["MATURIN"])
    if periodes_massena != periodes_maturin:
        absentes_massena = sorted(periodes_maturin - periodes_massena)
        absentes_maturin = sorted(periodes_massena - periodes_maturin)
        raise ValueError(
            "Périodes non concordantes entre boutiques ; "
            f"absentes MASSENA={absentes_massena}, absentes MATURIN={absentes_maturin}"
        )
    return tuple(
        (
            annee,
            mois,
            *recettes_par_boutique["MASSENA"][(annee, mois)],
            *recettes_par_boutique["MATURIN"][(annee, mois)],
        )
        for annee, mois in sorted(periodes_massena)
    )


def ajouter_feuille(document: Any, lignes: Sequence[Sequence[object]]) -> None:
    """Écrit la consolidation et les trois totaux en formules Calc."""
    feuilles = document.getSheets()
    feuille = feuilles.getByIndex(0)
    feuille.setName(NOM_FEUILLE)
    plage_entetes = feuille.getCellRangeByPosition(
        0, 0, len(COLONNES_DESTINATION) - 1, 0
    )
    plage_entetes.setDataArray((COLONNES_DESTINATION,))
    plage_entetes.CharWeight = 150
    plage_entetes.IsTextWrapped = True

    if lignes:
        valeurs = tuple(
            tuple(float(valeur) if isinstance(valeur, Decimal) else valeur for valeur in ligne)
            for ligne in lignes
        )
        derniere_ligne = len(valeurs)
        feuille.getCellRangeByPosition(0, 1, 7, derniere_ligne).setDataArray(valeurs)
        formules = tuple(
            (f"=C{ligne}+F{ligne}", f"=D{ligne}+G{ligne}", f"=E{ligne}+H{ligne}")
            for ligne in range(2, derniere_ligne + 2)
        )
        feuille.getCellRangeByPosition(8, 1, 10, derniere_ligne).setFormulaArray(
            formules
        )
        feuille.getCellRangeByPosition(2, 1, 10, derniere_ligne).NumberFormat = (
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
    """Lit les deux feuilles contractuelles et publie l'ODS atomiquement."""
    sources = {
        boutique: repertoire_sortie / FICHIER_EJ_PAR_BOUTIQUE[boutique]
        for boutique in BOUTIQUES
    }
    for source in sources.values():
        if not source.is_file():
            raise FileNotFoundError(f"Classeur ODS source introuvable : {source}")
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    destination = repertoire_sortie / NOM_FICHIER

    with tempfile.TemporaryDirectory(
        prefix=".recettes-mensuelles-", dir=repertoire_sortie
    ) as nom_temporaire:
        temporaire = Path(nom_temporaire)
        chemin_temporaire = temporaire / NOM_FICHIER
        processus = demarrer_libreoffice(
            soffice, temporaire / "profil", port_uno=port_uno
        )
        documents_sources: list[Any] = []
        document_destination = None
        try:
            contexte = connecter_uno(uno, port_uno=port_uno)
            bureau = contexte.ServiceManager.createInstanceWithContext(
                "com.sun.star.frame.Desktop", contexte
            )
            recettes = {}
            for boutique in BOUTIQUES:
                document_source = bureau.loadComponentFromURL(
                    uno.systemPathToFileUrl(str(sources[boutique].resolve())),
                    "_blank",
                    0,
                    proprietes(uno, Hidden=True, ReadOnly=True),
                )
                documents_sources.append(document_source)
                nom_feuille = FeuilleEjEntetes.RECETTES_MENSUELLES.pour(boutique)
                if not document_source.getSheets().hasByName(nom_feuille):
                    raise ValueError(
                        f"Feuille source {nom_feuille!r} absente de {sources[boutique]}"
                    )
                recettes[boutique] = indexer_recettes(
                    _donnees_utilisees(document_source.getSheets().getByName(nom_feuille)),
                    boutique,
                )

            document_destination = bureau.loadComponentFromURL(
                "private:factory/scalc", "_blank", 0, proprietes(uno, Hidden=True)
            )
            ajouter_feuille(document_destination, consolider_recettes(recettes))
            document_destination.storeAsURL(
                uno.systemPathToFileUrl(str(chemin_temporaire.resolve())),
                proprietes(uno, FilterName="calc8"),
            )
        finally:
            if document_destination is not None:
                document_destination.close(True)
            for document_source in reversed(documents_sources):
                document_source.close(True)
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()
                processus.wait(timeout=5)

        if not chemin_temporaire.is_file():
            raise RuntimeError(f"PyUNO n'a pas produit le fichier attendu : {chemin_temporaire}")
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
        environnement["PYTHONPATH"] = racine_src + os.pathsep + environnement.get(
            "PYTHONPATH", ""
        )
        resultat = subprocess.run(
            [str(python_uno), str(Path(__file__).resolve()), *arguments_relais],
            env=environnement,
        )
        return resultat.returncode

    destination = generer_classeur(
        args.sortie, uno, args.soffice, port_uno=args.port_uno
    )
    print(f"Recettes mensuelles toutes boutiques : {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
