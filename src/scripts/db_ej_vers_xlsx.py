"""Orchestre la livraison contractuelle SQLite -> CSV de contrôle -> 18 XLSX."""

from __future__ import annotations

import argparse
import shutil

from pathlib import Path

from scripts import db_vers_csv_751, construire_classeurs_751
from shared.constantes import CHEMIN_DB, iterer_classeurs_751


NOMS_CLASSEURS_ATTENDUS = {
    classeur.nom_fichier for classeur in iterer_classeurs_751()
}
NOMBRE_CLASSEURS_ATTENDU = len(NOMS_CLASSEURS_ATTENDUS)
ANCIENS_FICHIERS_SORTIE = {
    "EJ_ENTETE_TICKETS_MASSENA.xlsx",
    "EJ_ENTETE_TICKETS_MATURIN.xlsx",
    "EJ_LIGNES_TICKETS_MASSENA.xlsx",
    "EJ_LIGNES_TICKETS_MATURIN.xlsx",
    "rapport_reconstruction_751.json",
    ".DS_Store",
}
ANCIENS_DOSSIERS_SORTIE = {
    "controle",
    "livraison_reprise",
    "resultats_csv",
}


def nettoyer_ancienne_sortie(sortie: Path) -> None:
    """Retire uniquement les artefacts connus de l'ancienne arborescence."""
    if not sortie.exists():
        sortie.mkdir(parents=True)
        return
    for nom in ANCIENS_FICHIERS_SORTIE:
        chemin = sortie / nom
        if chemin.is_file():
            chemin.unlink()
    for nom in ANCIENS_DOSSIERS_SORTIE:
        chemin = sortie / nom
        if chemin.is_dir():
            shutil.rmtree(chemin)


def verifier_dossier_classeurs(sortie: Path) -> list[Path]:
    """Exige exclusivement les 18 classeurs dans le dossier Excel."""
    repertoire_classeurs = sortie
    if not repertoire_classeurs.is_dir():
        raise FileNotFoundError(
            f"Dossier des classeurs introuvable : {repertoire_classeurs}"
        )

    elements = sorted(repertoire_classeurs.iterdir())
    classeurs = [
        element
        for element in elements
        if element.is_file() and element.suffix.lower() == ".xlsx"
    ]
    noms_observes = {classeur.name for classeur in classeurs}
    manquants = sorted(NOMS_CLASSEURS_ATTENDUS - noms_observes)
    inattendus = sorted(
        element.name
        for element in elements
        if (
            element.name not in NOMS_CLASSEURS_ATTENDUS
        )
    )
    if manquants or inattendus:
        raise RuntimeError(
            "Dossier de livraison Excel non conforme : "
            f"manquants={manquants}, inattendus={inattendus}"
        )
    return classeurs


def construire_classeurs(
    *,
    sortie: Path,
    staging: Path,
    controle: Path,
    qa: bool,
) -> None:
    """Exécute le constructeur Python puis vérifie les 18 classeurs."""
    nettoyer_ancienne_sortie(sortie)
    constructeur = construire_classeurs_751.Constructeur751(
        staging=staging.resolve(),
        controle=controle.resolve(),
        sortie=sortie.resolve(),
        qa_dir=(controle / "qa_previews").resolve(),
        qa=qa,
    )
    constructeur.construire()
    classeurs = verifier_dossier_classeurs(sortie)
    if len(classeurs) != NOMBRE_CLASSEURS_ATTENDU:  # garde explicite pour le rapport d'exécution
        raise RuntimeError(f"Nombre de classeurs inattendu : {len(classeurs)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(CHEMIN_DB))
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--controle", type=Path, required=True)
    parser.add_argument("--regles", type=Path, default=Path("config/regles_modes_z.json"))
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Rend chaque feuille en PNG avec LibreOffice pour contrôle visuel.",
    )
    args = parser.parse_args(argv)

    db_vers_csv_751.main([
        "--base", str(args.base),
        "--staging", str(args.staging),
        "--controle", str(args.controle),
        "--regles", str(args.regles),
    ])
    construire_classeurs(
        sortie=args.sortie,
        staging=args.staging,
        controle=args.controle,
        qa=args.qa,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
