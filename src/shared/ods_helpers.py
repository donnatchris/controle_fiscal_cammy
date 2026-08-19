"""Primitives PyUNO réutilisables pour créer et modifier des feuilles Calc."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

from shared.constantes import LARGEUR_COLONNE_DEFAUT


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


def definir_largeur_colonnes(
    feuille: Any,
    nombre_colonnes: int,
    largeur: int = LARGEUR_COLONNE_DEFAUT,
) -> None:
    """Applique une largeur fixe aux colonnes utilisées."""
    colonnes = feuille.getColumns()
    for index in range(nombre_colonnes):
        colonnes.getByIndex(index).Width = largeur


def copier_feuille(document: Any, nom_source: str, nom_destination: str) -> Any:
    """Copie une feuille et retourne la nouvelle feuille."""
    feuilles = document.getSheets()
    feuilles.copyByName(nom_source, nom_destination, feuilles.getCount())
    return feuilles.getByName(nom_destination)


def copier_valeurs_feuille(document: Any, nom_source: str, nom_destination: str) -> Any:
    """Copie les seules valeurs utilisées d'une feuille vers une nouvelle feuille."""
    feuilles = document.getSheets()
    feuille_source = feuilles.getByName(nom_source)
    curseur = feuille_source.createCursor()
    curseur.gotoEndOfUsedArea(True)
    adresse = curseur.getRangeAddress()
    valeurs = feuille_source.getCellRangeByPosition(
        adresse.StartColumn,
        adresse.StartRow,
        adresse.EndColumn,
        adresse.EndRow,
    ).getDataArray()

    if feuilles.hasByName(nom_destination):
        feuilles.removeByName(nom_destination)
    feuilles.insertNewByName(nom_destination, feuilles.getCount())
    feuille_destination = feuilles.getByName(nom_destination)
    feuille_destination.getCellRangeByPosition(
        0,
        0,
        adresse.EndColumn - adresse.StartColumn,
        adresse.EndRow - adresse.StartRow,
    ).setDataArray(valeurs)
    return feuille_destination


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


def proprietes(uno: Any, **valeurs: object) -> tuple[Any, ...]:
    """Crée un tuple de PropertyValue UNO à partir d'un dictionnaire de valeurs."""
    resultat = []
    for nom, valeur in valeurs.items():
        propriete = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        propriete.Name = nom
        propriete.Value = valeur
        resultat.append(propriete)
    return tuple(resultat)


def demarrer_libreoffice(
    soffice: str,
    profil: Path,
    *,
    port_uno: int = 2002,
) -> subprocess.Popen[str]:
    """Démarre une instance Calc isolée, pilotée exclusivement par PyUNO."""
    executable = shutil.which(soffice) if Path(soffice).name == soffice else soffice
    if not executable:
        raise FileNotFoundError(
            "LibreOffice introuvable : installez ou indiquez soffice."
        )
    return subprocess.Popen(
        [
            executable,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            f"--accept=socket,host=127.0.0.1,port={port_uno};urp;StarOffice.ComponentContext",
            f"-env:UserInstallation={profil.as_uri()}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def connecter_uno(uno: Any, delai_secondes: float = 15, *, port_uno: int = 2002) -> Any:
    """Se connecte à l'instance LibreOffice via PyUNO."""
    contexte_local = uno.getComponentContext()
    resolveur = contexte_local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", contexte_local
    )
    url = f"uno:socket,host=127.0.0.1,port={port_uno};urp;StarOffice.ComponentContext"
    fin = time.monotonic() + delai_secondes
    while time.monotonic() < fin:
        try:
            return resolveur.resolve(url)
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Impossible de se connecter à LibreOffice via PyUNO.")


def pyuno_disponible() -> Any | None:
    """Retourne le module PyUNO lorsqu'il est disponible."""
    try:
        import uno
    except ModuleNotFoundError:
        return None
    return uno


def python_pyuno_defaut() -> Path:
    """Retourne l'interpréteur Python fourni avec LibreOffice."""
    chemin = os.environ.get("LIBREOFFICE_PYTHON")
    if chemin:
        return Path(chemin)
    candidat_macos = Path("/Applications/LibreOffice.app/Contents/Resources/python")
    if candidat_macos.is_file():
        return candidat_macos
    raise FileNotFoundError(
        "Interpréteur Python PyUNO introuvable : indiquez --python-uno ou LIBREOFFICE_PYTHON."
    )
