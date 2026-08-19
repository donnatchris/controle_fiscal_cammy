"""Reconstruit et valide la base 751 avant publication atomique."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import uuid

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from scripts import ej_vers_db, z1_vers_db, z2_vers_db
from shared.constantes import CHEMIN_DB, REPERTOIRE_SOURCE


ATTENDUS = {
    "blocs_ej": 2_511,
    "tickets_vente": 1_875,
    "details": 4_131,
    "retours_vente": 35,
    "retours_ttc": Decimal("-19821.00"),
    "z1_fichiers": 96,
    "z1_lignes": 3_936,
    "z2_fichiers": 96,
    "z2_lignes": 4_800,
}


def empreintes_sources(repertoire: Path) -> dict[str, str]:
    """Calcule les empreintes des sources EJ/Z sans jamais les modifier."""
    empreintes: dict[str, str] = {}
    for chemin in sorted(repertoire.rglob("*")):
        if not chemin.is_file() or chemin.suffix.upper() not in {".TXT", ".CSV"}:
            continue
        empreintes[str(chemin.relative_to(repertoire))] = hashlib.sha256(
            chemin.read_bytes()
        ).hexdigest()
    return empreintes


def somme_decimal(rows: list[sqlite3.Row], colonne: str) -> Decimal:
    return sum(
        (Decimal(row[colonne]) for row in rows if row[colonne] is not None),
        start=Decimal("0"),
    )


def valider_base(chemin_base: Path) -> None:
    """Valide les invariants comptables avec Decimal, jamais avec des flottants."""
    with sqlite3.connect(chemin_base) as connection:
        connection.row_factory = sqlite3.Row
        compte = lambda table: connection.execute(
            f"SELECT COUNT(*) AS n FROM {table}"  # noqa: S608 - tables internes fixes
        ).fetchone()["n"]

        inventaire = {
            row["type"]: row["n"]
            for row in connection.execute(
                "SELECT type, COUNT(*) AS n FROM tickets GROUP BY type ORDER BY type"
            )
        }
        ventes_par_boutique = {
            row["boutique"]: row["n"]
            for row in connection.execute(
                """
                SELECT boutique, COUNT(*) AS n
                FROM tickets
                WHERE type IN ('REG', '_R_F')
                  AND NULLIF(TRIM(E_NUM_TICKET), '') IS NOT NULL
                GROUP BY boutique
                ORDER BY boutique
                """
            )
        }
        retours = connection.execute(
            """
            SELECT E_TTC
            FROM tickets
            WHERE type = '_R_F'
              AND NULLIF(TRIM(E_NUM_TICKET), '') IS NOT NULL
            """
        ).fetchall()
        ventes = sum(ventes_par_boutique.values())
        validation: dict[str, object] = {
            "blocs_ej": compte("tickets"),
            "details": compte("lignes_ticket"),
            "tickets_vente": ventes,
            "blocs_administratifs_exclus_exports": compte("tickets") - ventes,
            "ventes_par_boutique": ventes_par_boutique,
            "inventaire_types": inventaire,
            "types_inconnus": sorted(set(inventaire) - {"REG", "_R_F", "X", "XZ", "Z"}),
            "retours_vente": len(retours),
            "retours_ttc": format(somme_decimal(retours, "E_TTC"), ".2f"),
            "z1_fichiers": compte("z1_entetes"),
            "z1_lignes": compte("z1_lignes"),
            "z2_fichiers": compte("z2_entetes"),
            "z2_lignes": compte("z2_lignes"),
            "foreign_key_errors": len(connection.execute("PRAGMA foreign_key_check").fetchall()),
        }

    erreurs = []
    for cle, attendu in ATTENDUS.items():
        obtenu = Decimal(validation[cle]) if cle == "retours_ttc" else validation[cle]
        if obtenu != attendu:
            erreurs.append(f"{cle}: attendu={attendu}, obtenu={obtenu}")
    if validation["ventes_par_boutique"] != {"MASSENA": 1_153, "MATURIN": 722}:
        erreurs.append(f"ventes_par_boutique: {validation['ventes_par_boutique']}")
    if validation["foreign_key_errors"] != 0:
        erreurs.append(f"foreign_key_errors: {validation['foreign_key_errors']}")
    if erreurs:
        raise RuntimeError("Validation de reconstruction échouée : " + "; ".join(erreurs))


def reconstruire(repertoire_sources: Path, chemin_temporaire: Path) -> None:
    """Construit les six tables dans une base neuve et isolée."""
    with sqlite3.connect(chemin_temporaire) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        ej_vers_db.creer_base(connection)
        z1_vers_db.creer_tables(connection)
        z2_vers_db.creer_tables(connection)
        ej_vers_db.traiter_repertoire(connection, repertoire_sources)
        z1_vers_db.traiter_repertoire(connection, repertoire_sources)
        z2_vers_db.traiter_repertoire(connection, repertoire_sources)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path(REPERTOIRE_SOURCE))
    parser.add_argument("--base", type=Path, default=Path(CHEMIN_DB))
    parser.add_argument(
        "--publier",
        action="store_true",
        help="Remplace la base active seulement après validation intégrale.",
    )
    args = parser.parse_args(argv)

    args.base.parent.mkdir(parents=True, exist_ok=True)
    chemin_temporaire = args.base.with_name(f".{args.base.name}.{uuid.uuid4().hex}.tmp")
    avant = empreintes_sources(args.sources)

    try:
        reconstruire(args.sources, chemin_temporaire)
        valider_base(chemin_temporaire)
        apres = empreintes_sources(args.sources)
        if avant != apres:
            raise RuntimeError("Les sources ont changé pendant la reconstruction")

        publication: dict[str, str | None] = {"base_active": None, "sauvegarde": None}
        if args.publier:
            sauvegarde = None
            if args.base.exists():
                horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
                sauvegarde = args.base.with_suffix(f".sqlite.bak_{horodatage}")
                shutil.copy2(args.base, sauvegarde)
            os.replace(chemin_temporaire, args.base)
            publication = {
                "base_active": str(args.base.resolve()),
                "sauvegarde": str(sauvegarde.resolve()) if sauvegarde else None,
            }

        print(f"Base validée à partir de {len(avant)} sources inchangées.")
        if not args.publier:
            print(f"Base temporaire validée et conservée : {chemin_temporaire}")
        return 0
    except Exception:
        if chemin_temporaire.exists():
            chemin_temporaire.unlink()
        raise


if __name__ == "__main__":
    raise SystemExit(main())
