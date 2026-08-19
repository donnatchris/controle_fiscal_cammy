import argparse
from pathlib import Path

from scripts import db_vers_csv_751, reconstruire_base_751
from shared.constantes import CHEMIN_DB, REPERTOIRE_SOURCE


RACINE_PROJET = Path(__file__).resolve().parents[1]
REPERTOIRE_SORTIE_PAR_DEFAUT = RACINE_PROJET / "output"
REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT = (
    REPERTOIRE_SORTIE_PAR_DEFAUT / "travaux_preliminaires"
)
REPERTOIRE_CONTROLE_PAR_DEFAUT = RACINE_PROJET / "controle"
REGLES_Z_PAR_DEFAUT = RACINE_PROJET / "config/regles_modes_z.json"


def executer_traitements(
    chemin_repertoire: Path,
    chemin_base: Path,
    repertoire_staging: Path = REPERTOIRE_TRAVAUX_PRELIMINAIRES_PAR_DEFAUT,
    repertoire_controle: Path = REPERTOIRE_CONTROLE_PAR_DEFAUT,
    chemin_regles: Path = REGLES_Z_PAR_DEFAUT,
) -> bool:
    """Reconstruit la base SQLite puis exporte les CSV et contrôles associés."""
    repertoire_staging.mkdir(parents=True, exist_ok=True)
    repertoire_controle.mkdir(parents=True, exist_ok=True)
    rapport = repertoire_controle / "rapport_reconstruction_751.json"

    print("\n=== 1/2 Reconstruction et validation de la base ===")
    code_reconstruction = reconstruire_base_751.main([
        "--sources", str(chemin_repertoire),
        "--base", str(chemin_base),
        "--rapport", str(rapport),
        "--publier",
    ])
    if code_reconstruction != 0:
        return False

    print("\n=== 2/2 Génération des CSV et contrôles ===")
    if db_vers_csv_751.main([
        "--base", str(chemin_base),
        "--staging", str(repertoire_staging),
        "--controle", str(repertoire_controle),
        "--regles", str(chemin_regles),
    ]) != 0:
        return False

    print("\nTraitement terminé avec succès.")
    print(f"Base SQLite : {chemin_base}")
    print(f"CSV : {repertoire_staging}")
    print(f"Contrôles techniques : {repertoire_controle}")
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
    parser.add_argument(
        "--controle",
        type=Path,
        default=REPERTOIRE_CONTROLE_PAR_DEFAUT,
        help="Dossier des contrôles techniques (défaut : controle).",
    )
    parser.add_argument("--regles", type=Path, default=REGLES_Z_PAR_DEFAUT)
    args = parser.parse_args(argv)

    succes = executer_traitements(
        chemin_repertoire=Path(args.chemin_repertoire),
        chemin_base=Path(args.chemin_base),
        repertoire_staging=args.staging,
        repertoire_controle=args.controle,
        chemin_regles=args.regles,
    )
    return 0 if succes else 1


if __name__ == "__main__":
    raise SystemExit(main())
