import sqlite3

from pathlib import Path


def ouvrir_base_existante(chemin_base: Path) -> sqlite3.Connection:
    """Ouvre une base creee au prealable par le script principal."""
    if not chemin_base.is_file():
        raise FileNotFoundError(
            f"Base SQLite introuvable : {chemin_base}. "
            "Lancez le traitement principal pour la creer."
        )
    return sqlite3.connect(chemin_base)
