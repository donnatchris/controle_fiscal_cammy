#!/usr/bin/env python3
"""Auditer en lecture seule la structure et les preuves du dossier fiscal 751."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SOURCE_ROOTS = (
    "2023_MASSENA",
    "2023_MATURIN",
    "2024_MASSENA",
    "2024_MATURIN",
    "2025_MASSENA",
    "2025_MATURIN",
)
EXPECTED_SOURCE_COUNTS = {".txt": 63, ".csv": 449, ".pdf": 1}
EXPECTED_DB_COUNTS = {"tickets": 1875, "lignes_ticket": 4131}
SUMMARY_FILES = (
    "RESUME_REPRISE_EJ.json",
    "RESUME_REPRISE_Z.json",
    "RESUME_RAPPROCHEMENT_EJ_Z.json",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def git_source_status(root: Path, source_dir: Path) -> list[str]:
    relative = source_dir.relative_to(root)
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", str(relative)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return [f"git status indisponible: {result.stderr.strip()}"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def source_inventory(source_dir: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    by_root: dict[str, int] = {}
    missing_roots: list[str] = []
    for name in SOURCE_ROOTS:
        root = source_dir / name
        if not root.is_dir():
            missing_roots.append(name)
            continue
        files = [path for path in root.rglob("*") if path.is_file()]
        by_root[name] = len(files)
        counts.update(path.suffix.lower() or "<sans-extension>" for path in files)
    return {
        "total": sum(counts.values()),
        "by_extension": dict(sorted(counts.items())),
        "by_root": by_root,
        "missing_roots": missing_roots,
    }


def database_counts(database: Path) -> dict[str, Any] | None:
    if not database.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in EXPECTED_DB_COUNTS
            }
    except sqlite3.Error as exc:
        return {"error": str(exc)}


def newest_control_directory(root: Path) -> Path | None:
    outputs = root / "traitement_marco" / "outputs"
    candidates = [path for path in outputs.glob("*/controle") if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def historical_summaries(control_dir: Path | None) -> dict[str, Any]:
    if control_dir is None:
        return {"control_dir": None, "summaries": {}, "red_gates": []}
    summaries: dict[str, Any] = {}
    red_gates: list[dict[str, Any]] = []
    for filename in SUMMARY_FILES:
        path = control_dir / filename
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            summaries[filename] = {"error": str(exc)}
            continue
        summaries[filename] = data
        for gate in data.get("gates", []):
            if gate.get("STATUT") != "VERT":
                red_gates.append({"summary": filename, **gate})
    return {
        "control_dir": str(control_dir),
        "summaries": summaries,
        "red_gates": red_gates,
    }


def audit(root: Path) -> dict[str, Any]:
    source_dir = root / "traitement_chris" / "fichiers_sources"
    specification = source_dir / "751 - CAMMY FRANCE DEVELOPPEMENT LTD.pdf"
    inventory = source_inventory(source_dir)
    source_status = git_source_status(root, source_dir) if source_dir.is_dir() else []
    db_counts = database_counts(root / "traitement_chris" / "database" / "db.sqlite")
    historical = historical_summaries(newest_control_directory(root))

    errors: list[str] = []
    warnings: list[str] = []
    if not specification.is_file():
        errors.append("Cahier des charges PDF absent.")
    if inventory["missing_roots"]:
        errors.append(f"Racines source absentes: {', '.join(inventory['missing_roots'])}")
    for extension, expected in EXPECTED_SOURCE_COUNTS.items():
        observed = inventory["by_extension"].get(extension, 0)
        if observed != expected:
            warnings.append(
                f"Inventaire {extension}: {observed} observé(s), baseline active {expected}."
            )
    if source_status:
        errors.append("Des sources brutes sont modifiées ou non suivies par Git.")
    if db_counts and "error" not in db_counts:
        for table, expected in EXPECTED_DB_COUNTS.items():
            observed = db_counts.get(table)
            if observed != expected:
                warnings.append(
                    f"Base active {table}: {observed}, baseline de vente {expected}."
                )
    elif db_counts and "error" in db_counts:
        warnings.append(f"Base SQLite illisible: {db_counts['error']}")
    if historical["red_gates"]:
        errors.append(f"{len(historical['red_gates'])} porte(s) historique(s) non verte(s).")
    if historical["control_dir"] is None:
        warnings.append("Aucun répertoire historique de contrôles détecté.")

    return {
        "root": str(root),
        "specification": str(specification),
        "source_inventory": inventory,
        "source_git_status": source_status,
        "database_counts": db_counts,
        "historical_controls": historical,
        "errors": errors,
        "warnings": warnings,
        "status": "ERREUR" if errors else "AVERTISSEMENT" if warnings else "OK",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repository_root())
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Retourner un code non nul aussi en présence d'avertissements.",
    )
    args = parser.parse_args()
    report = audit(args.repo_root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] or (args.strict and report["warnings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
