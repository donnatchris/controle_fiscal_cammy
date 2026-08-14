import argparse
from pathlib import Path

from scripts import db_ej_vers_xlsx, generer_rapport_fiscal_751, reconstruire_base_751
from shared.constantes import CHEMIN_DB, REPERTOIRE_SOURCE


RACINE_PROJET = Path(__file__).resolve().parents[1]
REPERTOIRE_SORTIE_PAR_DEFAUT = RACINE_PROJET / "output"
REPERTOIRE_STAGING_PAR_DEFAUT = RACINE_PROJET / "staging"
REPERTOIRE_CONTROLE_PAR_DEFAUT = RACINE_PROJET / "controle"
REGLES_Z_PAR_DEFAUT = RACINE_PROJET / "config/regles_modes_z.json"


def executer_traitements(
    chemin_repertoire: Path,
    chemin_base: Path,
    repertoire_sortie: Path = REPERTOIRE_SORTIE_PAR_DEFAUT,
    repertoire_staging: Path = REPERTOIRE_STAGING_PAR_DEFAUT,
    repertoire_controle: Path = REPERTOIRE_CONTROLE_PAR_DEFAUT,
    chemin_regles: Path = REGLES_Z_PAR_DEFAUT,
    qa: bool = False,
) -> bool:
    """Reconstruit la base et génère les 18 classeurs et le rapport PDF."""
    repertoire_sortie.mkdir(parents=True, exist_ok=True)
    repertoire_staging.mkdir(parents=True, exist_ok=True)
    repertoire_controle.mkdir(parents=True, exist_ok=True)
    rapport = repertoire_controle / "rapport_reconstruction_751.json"

    print("\n=== 1/3 Reconstruction et validation de la base ===")
    code_reconstruction = reconstruire_base_751.main([
        "--sources", str(chemin_repertoire),
        "--base", str(chemin_base),
        "--rapport", str(rapport),
        "--publier",
    ])
    if code_reconstruction != 0:
        return False

    print("\n=== 2/3 Génération des contrôles et des 18 classeurs Excel ===")
    arguments_excel = [
        "--base", str(chemin_base),
        "--sortie", str(repertoire_sortie),
        "--staging", str(repertoire_staging),
        "--controle", str(repertoire_controle),
        "--regles", str(chemin_regles),
    ]
    if qa:
        arguments_excel.append("--qa")

    if db_ej_vers_xlsx.main(arguments_excel) != 0:
        return False

    print("\n=== 3/3 Génération du rapport d'analyse fiscale PDF ===")
    if generer_rapport_fiscal_751.main([
        "--base", str(chemin_base),
        "--controle", str(repertoire_controle),
        "--sortie", str(repertoire_sortie),
    ]) != 0:
        return False

    print("\nTraitement terminé avec succès.")
    print(f"Livrables contractuels : {repertoire_sortie}")
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
        "--sortie",
        type=Path,
        default=REPERTOIRE_SORTIE_PAR_DEFAUT,
        help="Dossier contenant les 18 classeurs et le rapport PDF (défaut : output).",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=REPERTOIRE_STAGING_PAR_DEFAUT,
        help="Dossier des CSV intermédiaires (défaut : staging).",
    )
    parser.add_argument(
        "--controle",
        type=Path,
        default=REPERTOIRE_CONTROLE_PAR_DEFAUT,
        help="Dossier des contrôles techniques (défaut : controle).",
    )
    parser.add_argument("--regles", type=Path, default=REGLES_Z_PAR_DEFAUT)
    parser.add_argument(
        "--qa",
        action="store_true",
        help="Rend également les 135 feuilles en PNG avec LibreOffice.",
    )
    args = parser.parse_args(argv)

    succes = executer_traitements(
        chemin_repertoire=Path(args.chemin_repertoire),
        chemin_base=Path(args.chemin_base),
        repertoire_sortie=args.sortie,
        repertoire_staging=args.staging,
        repertoire_controle=args.controle,
        chemin_regles=args.regles,
        qa=args.qa,
    )
    return 0 if succes else 1


if __name__ == "__main__":
    raise SystemExit(main())
