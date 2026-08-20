import argparse
from pathlib import Path

from scripts import (
    db_vers_csv_751,
    ods_ej_entetes,
    ods_ej_entetes_enrichi,
    ods_ej_tickets,
    ods_z2,
    reconstruire_base_751,
)
from shared.constantes import CHEMIN_DB, REPERTOIRE_SOURCE

RACINE_PROJET = Path(__file__).resolve().parents[1]
REPERTOIRE_SORTIE_PAR_DEFAUT = RACINE_PROJET / "output"
REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT = (
    REPERTOIRE_SORTIE_PAR_DEFAUT / "travaux_preliminaires"
)
REPERTOIRE_LIBREOFFICE_PAR_DEFAUT = REPERTOIRE_SORTIE_PAR_DEFAUT / "libreoffice"


def executer_traitements(
    chemin_repertoire: Path,
    chemin_base: Path,
    repertoire_staging: Path = REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT,
    repertoire_libreoffice: Path = REPERTOIRE_LIBREOFFICE_PAR_DEFAUT,
) -> bool:
    """Reconstruit la base, exporte les CSV et les classeurs ODS."""
    repertoire_staging.mkdir(parents=True, exist_ok=True)
    repertoire_libreoffice.mkdir(parents=True, exist_ok=True)

    print("\n=== 1/5 Reconstruction et validation de la base ===")
    code_reconstruction = reconstruire_base_751.main(
        [
            "--sources",
            str(chemin_repertoire),
            "--base",
            str(chemin_base),
            "--publier",
        ]
    )
    if code_reconstruction != 0:
        return False

    print("\n=== 2/5 Génération des CSV ===")
    if (
        db_vers_csv_751.main(
            [
                "--base",
                str(chemin_base),
                "--staging",
                str(repertoire_staging),
            ]
        )
        != 0
    ):
        return False

    print("\n=== 3/5 Génération des feuilles ODS EJ ===")
    if (
        ods_ej_entetes.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
            ]
        )
        != 0
    ):
        return False
    if (
        ods_ej_tickets.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
            ]
        )
        != 0
    ):
        return False

    print("\n=== 4/5 Génération des feuilles ODS Z2 ===")
    if (
        ods_z2.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
            ]
        )
        != 0
    ):
        return False

    print("\n=== 5/5 Enrichissement des feuilles ODS d'entêtes EJ ===")
    if ods_ej_entetes_enrichi.main(["--sortie", str(repertoire_libreoffice)]) != 0:
        return False

    print("\nTraitement terminé avec succès.")
    print(f"Base SQLite : {chemin_base}")
    print(f"CSV : {repertoire_staging}")
    print(f"Classeurs LibreOffice : {repertoire_libreoffice}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "chemin_repertoire",
        help="Chemin du repertoire contenant les fichiers sources",
        nargs="?",
        default=str(RACINE_PROJET / REPERTOIRE_SOURCE),
    )
    parser.add_argument(
        "--libreoffice",
        type=Path,
        default=REPERTOIRE_LIBREOFFICE_PAR_DEFAUT,
        help="Dossier des classeurs ODS (défaut : output/libreoffice).",
    )
    parser.add_argument(
        "chemin_base",
        help="Chemin vers la base de donnees SQLite",
        nargs="?",
        default=str(RACINE_PROJET / CHEMIN_DB),
    )
    parser.add_argument(
        "--staging",
        "--travaux-preliminaires",
        dest="staging",
        type=Path,
        default=REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT,
        help="Dossier des CSV intermédiaires (défaut : output/travaux_preliminaires).",
    )
    args = parser.parse_args(argv)

    succes = executer_traitements(
        chemin_repertoire=Path(args.chemin_repertoire),
        chemin_base=Path(args.chemin_base),
        repertoire_staging=args.staging,
        repertoire_libreoffice=args.libreoffice,
    )
    return 0 if succes else 1


if __name__ == "__main__":
    raise SystemExit(main())
