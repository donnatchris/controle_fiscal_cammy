import csv
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import StringIO

from shared.parse_money import parse_money


@dataclass
class ZHeader:
    nom_fichier: str
    E_MODELE: str
    E_MACHINE: str
    E_RAPPORT: str
    E_FICHIER: str
    E_MODE: str
    E_COMPTEUR_Z: str
    E_DATE: date
    E_HEURE: str
    _CLES = {
        "MODELE": "E_MODELE",
        "MACHINE": "E_MACHINE",
        "RAPPORT": "E_RAPPORT",
        "FICHIER": "E_FICHIER",
        "MODE": "E_MODE",
        "COMPTEUR Z": "E_COMPTEUR_Z",
        "DATE": "E_DATE",
        "HEURE": "E_HEURE",
    }

    @staticmethod
    def from_raw(*, nom_fichier: str, raw: str) -> "ZHeader":
        lines = raw.splitlines()
        if len(lines) < 8:
            raise ValueError("Le header doit contenir au moins 8 lignes.")

        values = {}

        for i, (key, attr) in enumerate(ZHeader._CLES.items()):
            tokens = lines[i].split(",")
            if len(tokens) != 2:
                raise ValueError(
                    f"La ligne {i + 1} du header ne contient pas exactement 2 tokens séparés par une virgule."
                )
            if tokens[0].strip(' "') != key:
                raise ValueError(
                    f"La ligne {i + 1} du header ne commence pas par la clé attendue '{key}'."
                )
            value = tokens[1].strip(' "')
            values[attr] = value

        # Convertir la date
        values["E_DATE"] = datetime.strptime(
            values["E_DATE"],
            "%d-%m-%Y",
        ).date()

        return ZHeader(nom_fichier=nom_fichier, **values)


@dataclass
class ZLine:
    D_ENREGISTREMENT: str
    D_DESIGNATION: str
    D_QUANTITE: int
    D_MONTANT: Decimal
    _COLONNES = ["ENREGISTREMENT", "DESIGNATION", "QUANTITE/No", "MONTANT"]

    @staticmethod
    def from_row(row: list[str]) -> "ZLine":
        if len(row) != 4:
            raise ValueError("La ligne ne contient pas exactement 4 colonnes.")

        return ZLine(
            D_ENREGISTREMENT=row[0].strip(),
            D_DESIGNATION=row[1].strip(),
            D_QUANTITE=int(row[2].strip()),
            D_MONTANT=parse_money(row[3].strip()),
        )


@dataclass
class Z:
    boutique: str
    header: ZHeader
    lines: list[ZLine]
    _SEPARATOR = r"\r?\n\s*\r?\n"

    @staticmethod
    def from_raw(*, boutique: str, nom_fichier: str, raw: str) -> "Z":
        header_raw, data = re.split(Z._SEPARATOR, raw, maxsplit=1)

        header = ZHeader.from_raw(
            nom_fichier=nom_fichier,
            raw=header_raw,
        )

        reader = csv.reader(StringIO(data), delimiter=",", quotechar='"')

        colonnes = [colonne.strip() for colonne in next(reader)]
        if colonnes != ZLine._COLONNES:
            raise ValueError(
                f"Les colonnes ne correspondent pas à celles attendues. "
                f"Attendu: {ZLine._COLONNES}, trouvé: {colonnes}"
            )

        lines = []

        for row in reader:
            lines.append(ZLine.from_row(row))

        return Z(
            boutique=boutique,
            header=header,
            lines=lines,
        )
