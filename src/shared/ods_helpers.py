"""Primitives PyUNO réutilisables pour créer et modifier des feuilles Calc."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any


def obtenir_format(formats: Any, format_chaine: str) -> int:
    """Retourne la clé de format UNO correspondant à la chaîne donnée."""
    from com.sun.star.lang import Locale

    locale = Locale()
    locale.Language = "fr"
    locale.Country = "FR"
    cle = formats.queryKey(format_chaine, locale, False)
    if cle == -1:
        cle = formats.addNew(format_chaine, locale)
    return cle


def optimiser_largeur_colonnes(feuille: Any) -> None:
    """Optimise la largeur de toutes les colonnes d'une feuille Calc."""
    colonnes = feuille.getColumns()
    for index in range(colonnes.getCount()):
        colonnes.getByIndex(index).OptimalWidth = True


def copier_feuille(document: Any, nom_source: str, nom_destination: str) -> Any:
    """Copie une feuille et retourne la nouvelle feuille."""
    feuilles = document.getSheets()
    feuilles.copyByName(nom_source, nom_destination, feuilles.getCount())
    return feuilles.getByName(nom_destination)


def convertir_valeur_tableau(
    valeur: object | None,
    colonne: str,
    *,
    colonnes_texte: Collection[str] = (),
    colonne_date: str | None = None,
) -> object:
    """Convertit une valeur Python vers le type attendu par Calc."""
    if valeur in (None, ""):
        return ""

    texte = str(valeur)
    if colonne in colonnes_texte:
        return texte
    if colonne == colonne_date:
        valeur_date = date.fromisoformat(texte)
        return float((valeur_date - date(1899, 12, 30)).days)
    return float(Decimal(texte))


def ecrire_valeur(
    cellule: Any,
    valeur: object | None,
    colonne: str,
    *,
    colonnes_texte: Collection[str] = (),
    colonne_date: str | None = None,
    formats: Any | None = None,
    format_date: str = "YYYY-MM-DD",
) -> None:
    """Écrit une valeur dans une cellule Calc en préservant texte et date."""
    if valeur in (None, ""):
        return
    if colonne in colonnes_texte:
        cellule.String = str(valeur)
        return

    cellule.Value = convertir_valeur_tableau(
        valeur,
        colonne,
        colonnes_texte=colonnes_texte,
        colonne_date=colonne_date,
    )
    if colonne == colonne_date and formats is not None:
        cellule.NumberFormat = obtenir_format(formats, format_date)


def ecrire_tableau(
    feuille: Any,
    rows: Sequence[Mapping[str, object]],
    colonnes: Sequence[str],
    formats: Any,
    *,
    colonnes_texte: Collection[str] = (),
    colonne_date: str | None = None,
    format_date: str = "YYYY-MM-DD",
    ligne_depart: int = 1,
    colonne_depart: int = 0,
) -> None:
    """Écrit un tableau typé dans Calc en un seul appel UNO."""
    if not rows:
        return

    donnees = tuple(
        tuple(
            convertir_valeur_tableau(
                row.get(colonne),
                colonne,
                colonnes_texte=colonnes_texte,
                colonne_date=colonne_date,
            )
            for colonne in colonnes
        )
        for row in rows
    )
    derniere_ligne = ligne_depart + len(rows) - 1
    feuille.getCellRangeByPosition(
        colonne_depart,
        ligne_depart,
        colonne_depart + len(colonnes) - 1,
        derniere_ligne,
    ).setDataArray(donnees)

    if colonne_date is not None and colonne_date in colonnes:
        index_date = colonnes.index(colonne_date)
        feuille.getCellRangeByPosition(
            colonne_depart + index_date,
            ligne_depart,
            colonne_depart + index_date,
            derniere_ligne,
        ).NumberFormat = obtenir_format(formats, format_date)
