"""Utilitaires communs pour parcourir les fichiers sources."""

from pathlib import Path

from shared.constantes import BOUTIQUES


def trouver_boutiques_dans_sources(
    chemin_fichier: Path,
    chemin_repertoire: Path,
) -> list[str]:
    """Cherche les boutiques uniquement depuis la racine des sources."""
    chemin_relatif = chemin_fichier.relative_to(chemin_repertoire)
    chemin_dans_sources = Path(chemin_repertoire.name) / chemin_relatif
    texte = str(chemin_dans_sources).upper()
    return [boutique for boutique in BOUTIQUES if boutique in texte]
