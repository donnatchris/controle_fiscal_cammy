import argparse
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from scripts import (
    compare_ca_gesco_ca3,
    db_vers_csv_751,
    ods_ej_entetes,
    compare_1,
    compare_2,
    ods_ej_tickets,
    ods_z1,
    ods_z2,
    recettes_mensuelles,
    reconstruire_base_751,
)
from shared.constantes import CHEMIN_DB, REPERTOIRE_SOURCE
from shared.rapport_execution import JournalExecution

RACINE_PROJET = Path(__file__).resolve().parents[1]
REPERTOIRE_SORTIE_PAR_DEFAUT = RACINE_PROJET / "output"
REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT = (
    REPERTOIRE_SORTIE_PAR_DEFAUT / "travaux_preliminaires"
)
REPERTOIRE_LIBREOFFICE_PAR_DEFAUT = REPERTOIRE_SORTIE_PAR_DEFAUT / "libreoffice"


def sauvegarder_repertoire_sortie(repertoire_sortie: Path) -> Path | None:
    """Copie une sortie existante non vide dans un sous-répertoire horodaté."""
    if not repertoire_sortie.exists():
        return None
    if not repertoire_sortie.is_dir():
        raise NotADirectoryError(
            f"Le chemin de sortie existe mais n'est pas un répertoire : {repertoire_sortie}"
        )
    if not any(repertoire_sortie.iterdir()):
        return None

    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    sauvegarde = repertoire_sortie / f"_sauvegarde_{horodatage}"
    sauvegarde.mkdir()
    for element in repertoire_sortie.iterdir():
        if element == sauvegarde:
            continue
        destination = sauvegarde / element.name
        if element.is_dir():
            shutil.copytree(element, destination, symlinks=True)
        else:
            shutil.copy2(element, destination, follow_symlinks=False)

    print(f"Répertoire de sortie sauvegardé : {sauvegarde}")
    return sauvegarde


def executer_traitements(
    chemin_repertoire: Path,
    chemin_base: Path,
    repertoire_staging: Path = REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT,
    repertoire_libreoffice: Path = REPERTOIRE_LIBREOFFICE_PAR_DEFAUT,
    repertoire_sortie: Path | None = None,
) -> bool:
    """Reconstruit la base, exporte les CSV et les classeurs ODS."""
    if repertoire_sortie is not None:
        sauvegarder_repertoire_sortie(repertoire_sortie)
    repertoire_staging.mkdir(parents=True, exist_ok=True)
    repertoire_libreoffice.mkdir(parents=True, exist_ok=True)
    journal_execution = JournalExecution(repertoire_staging)
    with tempfile.NamedTemporaryFile(
        prefix="rapport-execution-",
        suffix=".jsonl",
        delete=False,
    ) as fichier_mesures:
        chemin_mesures_execution = Path(fichier_mesures.name)

    def executer_etape(traitement: Callable[[], int]) -> bool:
        """Exécute une étape puis fige ses mesures dans le journal d'exécution."""
        etat_avant = journal_execution.capturer_etat(repertoire_libreoffice)
        if traitement() != 0:
            return False
        journal_execution.charger_compteurs_traitement(chemin_mesures_execution)
        journal_execution.collecter_etape(repertoire_libreoffice, etat_avant)
        return True

    print("\n=== 1/10 Reconstruction et validation de la base ===")
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

    print("\n=== 2/10 Génération des CSV ===")
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

    print("\n=== 3/10 Génération des feuilles ODS EJ ===")
    if not executer_etape(
        lambda: ods_ej_entetes.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
            ]
        ),
    ):
        return False
    if not executer_etape(
        lambda: ods_ej_tickets.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
            ]
        ),
    ):
        return False

    print("\n=== 4/10 Génération des feuilles ODS Z2 ===")
    if not executer_etape(
        lambda: ods_z2.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
                "--mesures-execution",
                str(chemin_mesures_execution),
            ]
        ),
    ):
        return False

    print("\n=== 5/10 Génération des comparaisons Z2 ===")
    if not executer_etape(
        lambda: compare_1.main(["--sortie", str(repertoire_libreoffice)]),
    ):
        return False

    print("\n=== 6/10 Génération des feuilles ODS Z1 ===")
    if not executer_etape(
        lambda: ods_z1.main(
            [
                "--staging",
                str(repertoire_staging),
                "--sortie",
                str(repertoire_libreoffice),
                "--mesures-execution",
                str(chemin_mesures_execution),
            ]
        ),
    ):
        return False

    print("\n=== 7/10 Génération des comparaisons Z1 ===")
    if not executer_etape(
        lambda: compare_2.main(["--sortie", str(repertoire_libreoffice)]),
    ):
        return False

    print("\n=== 8/10 Consolidation des recettes mensuelles toutes boutiques ===")
    if not executer_etape(
        lambda: recettes_mensuelles.main(["--sortie", str(repertoire_libreoffice)]),
    ):
        return False

    print("\n=== 9/10 Comparaison des recettes reconstituées avec les CA3 ===")
    if not executer_etape(
        lambda: compare_ca_gesco_ca3.main(["--sortie", str(repertoire_libreoffice)]),
    ):
        return False

    print("\n=== 10/10 Génération du rapport d'exécution ===")
    destination_rapport = journal_execution.ecrire_rapport(
        repertoire_sortie or repertoire_libreoffice.parent,
        repertoire_libreoffice,
    )
    chemin_mesures_execution.unlink(missing_ok=True)

    print("\nTraitement terminé avec succès.")
    print(f"Base SQLite : {chemin_base}")
    print(f"CSV : {repertoire_staging}")
    print(f"Classeurs LibreOffice : {repertoire_libreoffice}")
    print(f"Rapport d'exécution : {destination_rapport}")
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
        repertoire_sortie=REPERTOIRE_SORTIE_PAR_DEFAUT,
    )
    return 0 if succes else 1


if __name__ == "__main__":
    raise SystemExit(main())
