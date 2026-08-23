#!/usr/bin/env python3
"""Valide les invariants substantiels d'un audit CDC 751 et de son rapport."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sqlite3
from xml.etree import ElementTree
from zipfile import ZipFile


NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}
ATTR_NOM = f"{{{NS['table']}}}name"
ATTR_REP_COL = f"{{{NS['table']}}}number-columns-repeated"
ATTR_REP_ROW = f"{{{NS['table']}}}number-rows-repeated"
ATTR_TYPE = f"{{{NS['office']}}}value-type"
ATTR_VALUE = f"{{{NS['office']}}}value"
ATTR_FORMULE = f"{{{NS['table']}}}formula"
ERREURS_FORMULE = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A")
TABLES_ATTENDUES = {
    "tickets": 2511,
    "lignes_ticket": 4131,
    "z1_entetes": 96,
    "z1_lignes": 3936,
    "z2_entetes": 96,
    "z2_lignes": 4800,
}
STATUTS = {
    "CONFORME",
    "CONFORME AVEC RÉSERVE",
    "NON CONFORME",
    "NON VÉRIFIABLE",
}


@dataclass(frozen=True)
class Cellule:
    texte: str
    nombre: Decimal | None = None


def repetition(element: ElementTree.Element, attribut: str) -> int:
    try:
        return max(1, int(element.get(attribut, "1")))
    except ValueError as erreur:
        raise AssertionError("Répétition ODS invalide") from erreur


def lire_cellule(element: ElementTree.Element) -> Cellule:
    texte = "".join(element.itertext()).strip()
    if element.get(ATTR_TYPE) not in {"float", "currency", "percentage"}:
        return Cellule(texte)
    valeur = element.get(ATTR_VALUE)
    if valeur is None:
        return Cellule(texte)
    try:
        return Cellule(texte, Decimal(valeur))
    except InvalidOperation as erreur:
        raise AssertionError(f"Valeur numérique ODS invalide : {valeur}") from erreur


def lire_ods(chemin: Path) -> tuple[dict[str, tuple[tuple[Cellule, ...], ...]], int, list[str]]:
    with ZipFile(chemin) as archive:
        racine = ElementTree.fromstring(archive.read("content.xml"))
    feuilles: dict[str, tuple[tuple[Cellule, ...], ...]] = {}
    formules = 0
    erreurs: list[str] = []
    for cellule in racine.iter():
        if ATTR_FORMULE in cellule.attrib:
            formules += 1
        texte = "".join(cellule.itertext())
        if any(erreur in texte for erreur in ERREURS_FORMULE):
            erreurs.append(texte)
    for table in racine.findall(".//table:table", NS):
        nom = table.get(ATTR_NOM)
        if not nom:
            continue
        lignes: list[tuple[Cellule, ...]] = []
        for ligne in table.findall("table:table-row", NS):
            cellules: list[Cellule] = []
            for cellule in ligne:
                if cellule.tag.endswith("covered-table-cell"):
                    cellules.append(Cellule(""))
                elif cellule.tag == f"{{{NS['table']}}}table-cell":
                    cellules.extend([lire_cellule(cellule)] * repetition(cellule, ATTR_REP_COL))
            if any(cellule.texte or cellule.nombre is not None for cellule in cellules):
                lignes.extend([tuple(cellules)] * repetition(ligne, ATTR_REP_ROW))
        feuilles[nom] = tuple(lignes)
    return feuilles, formules, erreurs


def assert_lot(
    feuilles: dict[str, dict[str, tuple[tuple[Cellule, ...], ...]]],
    fichier: str,
    feuille: str,
    motif: str,
    periode: str,
) -> None:
    lignes = feuilles[fichier][feuille]
    entetes = [cellule.texte for cellule in lignes[0]]
    index_nom = entetes.index("nomfichier")
    index_periode = entetes.index("AJ_Mois_Z")
    trouvees = {
        ligne[index_periode].texte
        for ligne in lignes[1:]
        if motif in ligne[index_nom].texte
    }
    assert trouvees == {periode}, f"{fichier}: période {trouvees}, attendu {periode}"


def verifier_absences_z2(
    feuilles: dict[str, dict[str, tuple[tuple[Cellule, ...], ...]]]
) -> None:
    attentes = {
        "Compare_Montant_MATURIN_Z2ModeZVsEJ_2023.ods": ("2023-11", "2023-12"),
        "Compare_Montant_MATURIN_Z2ModeZVsEJ_2025.ods": ("2025-04", "2025-05", "2025-06"),
    }
    for fichier, periodes in attentes.items():
        lignes = next(iter(feuilles[fichier].values()))
        par_periode = {ligne[1].texte: ligne for ligne in lignes[1:]}
        for periode in periodes:
            assert periode in par_periode, f"Période absente de la comparaison : {periode}"
            assert all(
                cellule.texte == "" and cellule.nombre is None
                for cellule in par_periode[periode][2:8]
            ), f"Faux écart Z2 pour {fichier} / {periode}"
    lignes_2025 = next(
        iter(feuilles["Compare_Montant_MATURIN_Z2ModeZVsEJ_2025.ods"].values())
    )
    juillet = next(ligne for ligne in lignes_2025 if ligne[1].texte == "2025-07")
    assert any(cellule.nombre is not None for cellule in juillet[2:8]), (
        "MATURIN 2025-07 doit porter la clôture du lot 062025_072025"
    )


def verifier_quantite_numerique(
    feuilles: dict[str, dict[str, tuple[tuple[Cellule, ...], ...]]]
) -> None:
    for boutique in ("MASSENA", "MATURIN"):
        fichier = f"TTS_EJ_LIGNES_TICKETS_{boutique}.ods"
        feuille = f"LIGNES_TICKETS_{boutique}_0"
        lignes = feuilles[fichier][feuille]
        entetes = [cellule.texte for cellule in lignes[0]]
        index = entetes.index("D_QUANTITE_ARTICLE")
        assert any(ligne[index].nombre is not None for ligne in lignes[1:]), (
            f"{fichier}: D_QUANTITE_ARTICLE n'est pas numérique"
        )


def verifier_sqlite(chemin: Path, strict: bool) -> dict[str, int]:
    assert chemin.is_file(), f"Base SQLite absente : {chemin}"
    connexion = sqlite3.connect(chemin)
    try:
        assert connexion.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not connexion.execute("PRAGMA foreign_key_check").fetchall()
        volumes = {
            table: connexion.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in TABLES_ATTENDUES
        }
    finally:
        connexion.close()
    if strict:
        assert volumes == TABLES_ATTENDUES, f"Volumes SQLite inattendus : {volumes}"
    return volumes


def nettoyer_markdown(valeur: str) -> str:
    return valeur.strip().strip("`")


def verifier_rapport(
    chemin: Path,
    feuilles: dict[str, dict[str, tuple[tuple[Cellule, ...], ...]]],
    strict: bool,
) -> Counter[str]:
    assert chemin.is_file(), f"Rapport absent : {chemin}"
    contenu = chemin.read_text(encoding="utf-8")
    lignes_matrice = [
        ligne for ligne in contenu.splitlines() if re.match(r"^\|\s*\d+\s*\|", ligne)
    ]
    if strict:
        assert len(lignes_matrice) == 131, f"Matrice : {len(lignes_matrice)} feuilles"
    numeros: list[int] = []
    statuts: Counter[str] = Counter()
    for ligne in lignes_matrice:
        champs = [champ.strip() for champ in ligne.split("|")[1:-1]]
        numero = int(champs[0])
        fichier = nettoyer_markdown(champs[1])
        feuille = nettoyer_markdown(champs[2])
        numeros.append(numero)
        assert fichier in feuilles, f"Classeur matriciel absent : {fichier}"
        assert feuille in feuilles[fichier], f"Feuille matricielle absente : {fichier} / {feuille}"
        assert re.search(r"\bQ-[A-Z0-9-]+\b", champs[5]), f"Preuve SQL absente : ligne {numero}"
        correspondance = re.search(
            r"\*\*(CONFORME AVEC RÉSERVE|CONFORME|NON CONFORME|NON VÉRIFIABLE)\*\*",
            champs[-1],
        )
        assert correspondance, f"Statut absent ou invalide : ligne {numero}"
        statut = correspondance.group(1)
        assert statut in STATUTS
        statuts[statut] += 1
    assert len(numeros) == len(set(numeros)), "Numéros de matrice dupliqués"
    clotures = [
        ligne
        for ligne in contenu.splitlines()
        if re.match(r"^\| (MASSENA|MATURIN) \|", ligne) and ligne.endswith("| IDENTIQUE |")
    ]
    if strict:
        assert len(clotures) == 57, f"Clôtures documentées : {len(clotures)}"
    for periode in ("2023-11", "2023-12", "2025-04", "2025-05"):
        assert periode in contenu, f"Période sans Z non documentée : {periode}"
    for terme in (
        "FEC",
        "CA3",
        "D_QUANTITE_ARTICLE",
        "042025_052025_062025",
        "062025_072025",
    ):
        assert terme in contenu, f"Élément obligatoire absent du rapport : {terme}"
    return statuts


def analyser_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--allow-baseline-drift",
        action="store_true",
        help="Tolère un changement expliqué des volumes, classeurs, feuilles et clôtures.",
    )
    return parser.parse_args()


def main() -> int:
    args = analyser_arguments()
    projet = args.project.resolve()
    repertoire_ods = projet / "output" / "libreoffice"
    fichiers_ods = sorted(repertoire_ods.glob("*.ods"))
    strict = not args.allow_baseline_drift
    if strict:
        assert len(fichiers_ods) == 30, f"Classeurs ODS : {len(fichiers_ods)}"
    feuilles: dict[str, dict[str, tuple[tuple[Cellule, ...], ...]]] = {}
    total_formules = 0
    erreurs: list[str] = []
    for fichier in fichiers_ods:
        contenu, formules, erreurs_fichier = lire_ods(fichier)
        feuilles[fichier.name] = contenu
        total_formules += formules
        erreurs.extend(f"{fichier.name}: {erreur}" for erreur in erreurs_fichier)
    total_feuilles = sum(len(contenu) for contenu in feuilles.values())
    if strict:
        assert total_feuilles == 131, f"Feuilles ODS : {total_feuilles}"
        assert total_formules == 17033, f"Formules ODS : {total_formules}"
    assert not erreurs, f"Erreurs de formule : {erreurs[:3]}"

    assert_lot(
        feuilles,
        "TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods",
        "Z1_SyntheseMois_TOUS_2025_MASSENA_CplteAnneeMoisZ",
        "042025_052025_062025",
        "2025-06",
    )
    assert_lot(
        feuilles,
        "TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods",
        "Z2_TransactionsMois_TOUS_2025_MASSENA_CplteAnneeMoisZ",
        "042025_052025_062025",
        "2025-06",
    )
    assert_lot(
        feuilles,
        "TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods",
        "Z1_SyntheseMois_TOUS_2025_MATURIN_CplteAnneeMoisZ",
        "062025_072025",
        "2025-07",
    )
    assert_lot(
        feuilles,
        "TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods",
        "Z2_TransactionsMois_TOUS_2025_MATURIN_CplteAnneeMoisZ",
        "062025_072025",
        "2025-07",
    )
    verifier_absences_z2(feuilles)
    verifier_quantite_numerique(feuilles)
    volumes = verifier_sqlite(projet / "output" / "database" / "db.sqlite", strict)
    statuts = verifier_rapport(args.report.resolve(), feuilles, strict)

    print(f"ODS : {len(fichiers_ods)} classeurs, {total_feuilles} feuilles")
    print(f"Formules : {total_formules}, erreurs : {len(erreurs)}")
    print(f"SQLite : {volumes}")
    print(f"Matrice : {dict(statuts)}")
    print("Lots multi-mois, absences Z2 et quantité numérique : conformes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
