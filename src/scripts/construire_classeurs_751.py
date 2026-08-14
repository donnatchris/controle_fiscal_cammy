"""Construit en Python les 18 classeurs contractuels du dossier fiscal 751."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile

from collections import Counter
from copy import copy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter


BOUTIQUES = ("MASSENA", "MATURIN")
ANNEES = (2023, 2024, 2025)
MOIS_PAR_ANNEE = {
    2023: [f"2023-{mois:02d}" for mois in range(1, 13)],
    2024: [f"2024-{mois:02d}" for mois in range(1, 13)],
    2025: [f"2025-{mois:02d}" for mois in range(1, 9)],
}

COLONNES_EJ = [
    "nomfichier", "E_NUM_INTERNE", "E_NUM_TICKET", "E_DATE_TICKET",
    "E_HEURE_TICKET", "E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_TVA1",
    "E_TVA2", "E_TVA3", "E_TVA4", "E_HT_NON_TAXABLE", "E_TTC",
    "E_MDP_CB", "E_MDP_ESPECES", "E_MDP_CHEQUES",
]
COLONNES_LIGNES_EJ = [
    *COLONNES_EJ, "D_QUANTITE_ARTICLE", "D_LIBELLE_ARTICLE",
    "D_TAUX_TVA_ARTICLE", "D_MONTANT_ARTICLE", "D_CORRECTION", "D_AUTRE_INFO",
]
COLONNES_Z = [
    "nomfichier", "E_MODELE", "E_MACHINE", "E_RAPPORT", "E_FICHIER",
    "E_MODE", "E_COMPTEUR_Z", "E_DATE", "E_HEURE", "D_ENREGISTREMENT",
    "D_DESIGNATION", "D_QUANTITE", "D_MONTANT",
]
CHAMPS_NUMERIQUES = {
    "E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_TVA1", "E_TVA2", "E_TVA3",
    "E_TVA4", "E_HT_NON_TAXABLE", "E_TTC", "E_MDP_CB", "E_MDP_ESPECES",
    "E_MDP_CHEQUES", "D_QUANTITE_ARTICLE", "D_MONTANT_ARTICLE",
    "D_CORRECTION", "D_QUANTITE", "D_MONTANT",
}
CIBLES_Z2 = ("CARTES", "CHEQUES", "CORRECTION", "ESPECES", "REF./TIROIR")
CIBLES_Z1 = (
    "CA BRUT", "CA NET", "CB.TIROIR", "CHQ.TIROIR", "ESP.TIROIR",
    "HORS TAXE 1", "TVA 1",
)

REMPLISSAGE_ENTETE = PatternFill("solid", fgColor="1F4E78")
REMPLISSAGE_SAISIE = PatternFill("solid", fgColor="FFF2CC")
REMPLISSAGE_ALERTE = PatternFill("solid", fgColor="FEF3C7")
REMPLISSAGE_ECART = PatternFill("solid", fgColor="FECACA")
POLICE_ALERTE = Font(name="Aptos", size=9, bold=True, color="92400E")
POLICE_ECART = Font(name="Aptos", size=9, bold=True, color="991B1B")
BORD_FIN = Side(style="thin", color="E2E8F0")
BORD_ENTETE = Side(style="medium", color="1F4E78")
FORMAT_MONTANT = "#,##0.00;[Red]-#,##0.00"


def valeur_decimal(valeur: Any) -> Decimal | None:
    if valeur in (None, ""):
        return None
    texte = str(valeur).replace(" ", "").replace(",", ".")
    try:
        return Decimal(texte)
    except Exception:
        return None


def nombre(valeur: Decimal | None) -> Decimal:
    return valeur if valeur is not None else Decimal("0")


def lire_csv(chemin: Path) -> list[dict[str, Any]]:
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        lignes = []
        for ligne in csv.DictReader(fichier, delimiter=";"):
            lignes.append({
                champ: valeur_decimal(valeur) if champ in CHAMPS_NUMERIQUES else (valeur or "")
                for champ, valeur in ligne.items()
            })
    return lignes


def convertir_date(valeur: Any) -> Any:
    if not valeur or isinstance(valeur, datetime):
        return valeur or None
    texte = str(valeur).strip()
    for format_date in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(texte[:10], format_date)
        except ValueError:
            continue
    return valeur


def normaliser_cellule(entete: str, valeur: Any) -> Any:
    if entete in {"E_DATE_TICKET", "E_DATE"}:
        return convertir_date(valeur)
    return None if valeur is None else valeur


def nettoyer_nom(valeur: str) -> str:
    resultat = re.sub(r"[^A-Za-z0-9_]", "_", str(valeur))
    return f"_{resultat}" if resultat and not re.match(r"[A-Za-z_]", resultat[0]) else resultat


def periodes_reference(nom_fichier: str) -> list[str]:
    motifs = re.findall(r"(?:^|_)(0[1-9]|1[0-2])(20\d{2})(?=_|\.|$)", str(nom_fichier))
    return list(dict.fromkeys(f"{annee}-{mois}" for mois, annee in motifs))


def etiquette_periodes(nom_fichier: str) -> str:
    return "|".join(periodes_reference(nom_fichier))


def trier_tickets(lignes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    def cle(ligne: dict[str, Any]) -> tuple[int, int, str]:
        return (
            int(ligne.get("E_NUM_INTERNE") or 0),
            int(ligne.get("E_NUM_TICKET") or 0),
            str(ligne.get("E_DATE_TICKET") or ""),
        )
    return sorted(lignes, key=cle)


def lignes_mensuelles(annee: int | None = None) -> list[dict[str, Any]]:
    mois = MOIS_PAR_ANNEE[annee] if annee else [m for a in ANNEES for m in MOIS_PAR_ANNEE[a]]
    return [{"AJ_ANNEE": int(m[:4]), "AJ_MOIS": m} for m in mois]


def largeur_colonne(nom: str) -> float:
    if nom == "nomfichier" or "FICHIER" in nom:
        return 25
    if any(terme in nom for terme in ("LIBELLE", "DESIGNATION", "COMMENTAIRE")):
        return 24
    if nom == "AJ_MOIS_Z":
        return 30
    if any(terme in nom for terme in ("DATE", "MOIS", "ANNEE")):
        return 14
    if any(terme in nom for terme in ("STATUT", "OBSERVATION")):
        return 18
    return 14


def format_colonne(nom: str) -> str | None:
    if nom in {"E_DATE_TICKET", "E_DATE"}:
        return "yyyymmdd"
    if "ANNEE" in nom:
        return "0"
    if nom in {"E_NUM_INTERNE", "E_NUM_TICKET", "E_COMPTEUR_Z", "D_ENREGISTREMENT"}:
        return "@"
    if any(terme in nom for terme in ("QUANTITE", "OCCURRENCE", "COMPTE")):
        return FORMAT_MONTANT
    if (
        re.match(r"^(E_HT|E_TVA|E_TTC|E_MDP|D_MONTANT|D_CORRECTION|AJ_|SOMME_|MASSENA_|MATURIN_|MTT_)", nom)
        or "MONTANT" in nom
        or any(terme in nom for terme in ("TOTAL_HT", "TOTAL_TVA", "TOTAL_TTC"))
    ):
        return FORMAT_MONTANT
    return None


def ajouter_feuille(
    classeur: Workbook,
    nom: str,
    entetes: list[str],
    lignes: list[dict[str, Any]],
    nom_tableau: str,
) -> Any:
    feuille = classeur.create_sheet(nom[:31])
    feuille.sheet_view.showGridLines = False
    feuille.freeze_panes = "A2"
    feuille.append(entetes)
    for ligne in lignes:
        feuille.append([normaliser_cellule(entete, ligne.get(entete)) for entete in entetes])

    for cellule in feuille[1]:
        cellule.fill = copy(REMPLISSAGE_ENTETE)
        cellule.font = Font(name="Aptos Display", size=10, bold=True, color="FFFFFF")
        cellule.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cellule.border = Border(top=BORD_ENTETE, bottom=BORD_ENTETE, left=BORD_ENTETE, right=BORD_ENTETE)
    feuille.row_dimensions[1].height = 34

    derniere_ligne = max(len(lignes) + 1, 2)
    for index, entete in enumerate(entetes, start=1):
        lettre = get_column_letter(index)
        feuille.column_dimensions[lettre].width = largeur_colonne(entete)
        format_nombre = format_colonne(entete)
        for ligne in range(2, derniere_ligne + 1):
            cellule = feuille.cell(ligne, index)
            cellule.font = Font(name="Aptos", size=9)
            cellule.alignment = Alignment(vertical="center")
            cellule.border = Border(bottom=BORD_FIN)
            if format_nombre:
                cellule.number_format = format_nombre

    if lignes:
        reference = f"A1:{get_column_letter(len(entetes))}{len(lignes) + 1}"
        tableau = Table(displayName=nettoyer_nom(nom_tableau), ref=reference)
        tableau.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )
        feuille.add_table(tableau)
        feuille.auto_filter.ref = reference
    return feuille


def colonne_formules(
    feuille: Any,
    colonne: int,
    nombre_lignes: int,
    formule: Callable[[int, int], str],
) -> None:
    for index in range(nombre_lignes):
        feuille.cell(index + 2, colonne + 1, formule(index + 2, index))


def mise_en_forme_ecart(feuille: Any, colonne: int, nombre_lignes: int, tolerance: Decimal = Decimal("0.02")) -> None:
    if not nombre_lignes:
        return
    lettre = get_column_letter(colonne + 1)
    plage = f"{lettre}2:{lettre}{nombre_lignes + 1}"
    feuille.conditional_formatting.add(
        plage,
        CellIsRule(operator="greaterThan", formula=[str(tolerance)], fill=REMPLISSAGE_ECART, font=POLICE_ECART),
    )
    feuille.conditional_formatting.add(
        plage,
        CellIsRule(operator="lessThan", formula=[str(-tolerance)], fill=REMPLISSAGE_ECART, font=POLICE_ECART),
    )


def feuille_copie_formules(
    classeur: Workbook,
    nom: str,
    source: str,
    entetes: list[str],
    lignes: list[dict[str, Any]],
    tableau: str,
) -> Any:
    feuille = ajouter_feuille(classeur, nom, entetes, lignes, tableau)
    for colonne in range(len(entetes)):
        lettre = get_column_letter(colonne + 1)
        colonne_formules(feuille, colonne, len(lignes), lambda ligne, _index, l=lettre: f"='{source}'!{l}{ligne}")
    return feuille


def nouveau_classeur() -> Workbook:
    classeur = Workbook()
    classeur.remove(classeur.active)
    classeur.calculation.fullCalcOnLoad = True
    classeur.calculation.forceFullCalc = True
    classeur.calculation.calcMode = "auto"
    return classeur


def totaux_ej_mensuels(lignes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resultat = {
        mois: {
            "AJ_ANNEE": int(mois[:4]), "AJ_MOIS": mois, "E_TTC": Decimal("0"),
            "E_MDP_CB": Decimal("0"), "E_MDP_CHEQUES": Decimal("0"),
            "E_MDP_ESPECES": Decimal("0"), "AJ_TOTAL_HT": Decimal("0"),
            "AJ_TOTAL_TVA_20": Decimal("0"),
        }
        for annee in ANNEES for mois in MOIS_PAR_ANNEE[annee]
    }
    for ligne in lignes:
        date = str(ligne.get("E_DATE_TICKET") or "")
        mois = f"{date[:4]}-{date[4:6]}" if re.fullmatch(r"\d{8}", date) else date[:7]
        if mois not in resultat:
            continue
        courant = resultat[mois]
        for champ in ("E_TTC", "E_MDP_CB", "E_MDP_CHEQUES", "E_MDP_ESPECES"):
            courant[champ] += nombre(ligne.get(champ))
        courant["AJ_TOTAL_HT"] += sum(
            (nombre(ligne.get(champ)) for champ in ("E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_HT_NON_TAXABLE")),
            Decimal("0"),
        )
        courant["AJ_TOTAL_TVA_20"] += nombre(ligne.get("E_TVA1"))
    return list(resultat.values())


class Constructeur751:
    def __init__(
        self,
        staging: Path,
        controle: Path,
        sortie: Path,
        qa_dir: Path,
        qa: bool = False,
    ) -> None:
        self.csv = staging
        self.controle = controle
        self.xlsx = sortie
        self.qa = qa
        self.qa_dir = qa_dir
        self.xlsx.mkdir(parents=True, exist_ok=True)
        self.donnees: dict[str, dict[str, Any]] = {"entetes": {}, "lignes": {}, "z1": {}, "z2": {}}
        for boutique in BOUTIQUES:
            self.donnees["entetes"][boutique] = lire_csv(self.csv / f"EJ_ENTETES_TICKETS_{boutique}.csv")
            self.donnees["lignes"][boutique] = lire_csv(self.csv / f"EJ_LIGNES_TICKETS_{boutique}.csv")
            self.donnees["z1"][boutique] = {}
            self.donnees["z2"][boutique] = {}
            for annee in ANNEES:
                self.donnees["z1"][boutique][annee] = lire_csv(self.csv / f"Z1_SyntheseMois_TOUS_{annee}_{boutique}.csv")
                self.donnees["z2"][boutique][annee] = lire_csv(self.csv / f"Z2_TransactionsMois_TOUS_{annee}_{boutique}.csv")

        self.ej_mensuels = {
            boutique: totaux_ej_mensuels(self.donnees["entetes"][boutique])
            for boutique in BOUTIQUES
        }
        self.rapprochements = lire_csv(self.controle / "RAPPROCHEMENT_PAR_CLOTURE_EJ_Z.csv")
        self.ej_clotures = {
            boutique: {
                ligne["PERIODES_FICHIER"]: {
                    "E_TTC": nombre(valeur_decimal(ligne["CA_TTC_EJ"])),
                    "AJ_TOTAL_HT": nombre(valeur_decimal(ligne["HT_EJ"])),
                    "AJ_TOTAL_TVA_20": nombre(valeur_decimal(ligne["TVA_EJ"])),
                    "E_MDP_CB": nombre(valeur_decimal(ligne["CARTES_EJ"])),
                    "E_MDP_CHEQUES": nombre(valeur_decimal(ligne["CHEQUES_EJ"])),
                    "E_MDP_ESPECES": nombre(valeur_decimal(ligne["ESPECES_EJ"])),
                }
                for ligne in self.rapprochements if ligne["BOUTIQUE"] == boutique
            }
            for boutique in BOUTIQUES
        }
        self.manifeste: dict[str, Any] = {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "generator": "Python/openpyxl",
            "workbooks": [],
            "csvFiles": [
                nom
                for boutique in BOUTIQUES
                for nom in (
                    f"EJ_ENTETES_TICKETS_{boutique}.csv",
                    f"EJ_LIGNES_TICKETS_{boutique}.csv",
                    *(f"Z{niveau}_{'SyntheseMois' if niveau == 1 else 'TransactionsMois'}_TOUS_{annee}_{boutique}.csv"
                      for annee in ANNEES for niveau in (1, 2)),
                )
            ],
            "checks": [],
        }

    def periodes_cloture(self, annee: int, boutique: str) -> list[dict[str, Any]]:
        composites = list(dict.fromkeys(
            ligne["PERIODES_FICHIER"]
            for ligne in self.rapprochements
            if ligne["BOUTIQUE"] == boutique
            and int(ligne["EXERCICE"]) == annee
            and "|" in ligne["PERIODES_FICHIER"]
        ))
        composantes = {mois for etiquette in composites for mois in etiquette.split("|")}
        etiquettes = [mois for mois in MOIS_PAR_ANNEE[annee] if mois not in composantes] + composites
        etiquettes.sort(key=lambda valeur: valeur.split("|")[-1])
        return [{"AJ_ANNEE_Z": annee, "AJ_MOIS_Z": etiquette} for etiquette in etiquettes]

    def exporter(self, classeur: Workbook, nom_fichier: str, feuilles_demandees: list[str]) -> None:
        noms = classeur.sheetnames
        if len(noms) != len(feuilles_demandees):
            raise RuntimeError(f"{nom_fichier}: {len(noms)} feuilles au lieu de {len(feuilles_demandees)}")
        erreurs = [
            f"{feuille.title}!{cellule.coordinate}={cellule.value}"
            for feuille in classeur.worksheets
            for ligne in feuille.iter_rows()
            for cellule in ligne
            if isinstance(cellule.value, str)
            and cellule.value.startswith("=")
            and any(erreur in cellule.value.upper() for erreur in ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A"))
        ]
        if erreurs:
            raise RuntimeError(f"{nom_fichier}: formules invalides: {erreurs[:5]}")
        destination = self.xlsx / nom_fichier
        classeur.save(destination)
        verification = load_workbook(destination, read_only=True, data_only=False)
        try:
            if verification.sheetnames != noms:
                raise RuntimeError(f"{nom_fichier}: feuilles altérées après sauvegarde")
        finally:
            verification.close()
        self.manifeste["workbooks"].append({
            "fileName": nom_fichier,
            "sheetCount": len(noms),
            "sheets": noms,
            "requestedSheets": feuilles_demandees,
        })
        self.manifeste["checks"].append({"fileName": nom_fichier, "formulaErrors": 0})

    def construire_entetes(self, boutique: str) -> None:
        classeur = nouveau_classeur()
        lignes = self.donnees["entetes"][boutique]
        triees = trier_tickets(lignes)
        demandees = [
            f"ENTETES_TICKETS_{boutique}_0", f"ENTETES_TICKETS_{boutique}_TriCrstNumInterne",
            f"ENTETES_TICKETS_{boutique}_CtrlCoherenceEntete", f"ENTETES_TICKETS_{boutique}_sequentialite",
            "TD_OccurenceNumInterne", "DoublonNumInterne", "TD_OccurenceNumTicket", "DoublonNumTicket",
            f"ENTETES_TICKETS_{boutique}_CplteAnneeMoisTotalHT", "TD_TotalEnctTtc_ParAnneeMois",
            f"enct_mensuels_{boutique}_232425", "TD_TotalHtTvaTtc_ParAnneeMois",
            f"recettes_mensuelles_{boutique}_232425",
        ]
        noms = [
            f"ENTETES_{boutique}_0", "Entetes_TriNumInterne", "Entetes_CtrlCoherence", "Entetes_sequentialite",
            "TD_OccurenceNumInterne", "DoublonNumInterne", "TD_OccurenceNumTicket", "DoublonNumTicket",
            "Entetes_CplteAnneeMois", "TD_TotalEnctTTC", f"enct_mensuels_{boutique}",
            "TD_TotalHtTvaTtc", f"recettes_mensuelles_{boutique}",
        ]
        ajouter_feuille(classeur, noms[0], COLONNES_EJ, lignes, "Entetes0")
        ajouter_feuille(classeur, noms[1], COLONNES_EJ, triees, "EntetesTri")

        entetes_ctrl = [*COLONNES_EJ, "AJ_TVA1_CALCULE", "AJ_ECART_TVA1", "AJ_TTC_CALCULE", "AJ_ECART_TTC", "AJ_SOLDE_DU", "AJ_SOLDE_TOUS_MDP"]
        ctrl = ajouter_feuille(classeur, noms[2], entetes_ctrl, triees, "EntetesCtrl")
        colonnes = {nom: get_column_letter(index + 1) for index, nom in enumerate(entetes_ctrl)}
        formules = {
            "AJ_TVA1_CALCULE": lambda r: f"={colonnes['E_HT1']}{r}*20%",
            "AJ_ECART_TVA1": lambda r: f"={colonnes['E_TVA1']}{r}-{colonnes['AJ_TVA1_CALCULE']}{r}",
            "AJ_TTC_CALCULE": lambda r: f"={colonnes['E_HT1']}{r}+{colonnes['E_TVA1']}{r}",
            "AJ_ECART_TTC": lambda r: f"={colonnes['E_TTC']}{r}-{colonnes['AJ_TTC_CALCULE']}{r}",
            "AJ_SOLDE_DU": lambda r: f"={colonnes['E_TTC']}{r}-({colonnes['E_MDP_CB']}{r}+{colonnes['E_MDP_CHEQUES']}{r})",
            "AJ_SOLDE_TOUS_MDP": lambda r: f"={colonnes['E_TTC']}{r}-({colonnes['E_MDP_CB']}{r}+{colonnes['E_MDP_ESPECES']}{r}+{colonnes['E_MDP_CHEQUES']}{r})",
        }
        for nom, formule in formules.items():
            colonne_formules(ctrl, entetes_ctrl.index(nom), len(triees), lambda r, _i, f=formule: f(r))
        for nom in ("AJ_ECART_TVA1", "AJ_ECART_TTC", "AJ_SOLDE_TOUS_MDP"):
            mise_en_forme_ecart(ctrl, entetes_ctrl.index(nom), len(triees))

        entetes_seq = ["nomfichier", "E_NUM_INTERNE", "E_NUM_TICKET", "E_DATE_TICKET", "E_HEURE_TICKET", "AJ_TROU_NUM_TICKET", "AJ_TROU_NUM_INTERNE", "OBSERVATION"]
        seq = ajouter_feuille(classeur, noms[3], entetes_seq, triees, "EntetesSeq")
        colonne_formules(seq, 5, len(triees), lambda r, i: '=""' if i == 0 else f"=C{r}-C{r-1}")
        colonne_formules(seq, 6, len(triees), lambda r, i: '=""' if i == 0 else f"=B{r}-B{r-1}")
        colonne_formules(seq, 7, len(triees), lambda r, i: '="Premier enregistrement"' if i == 0 else f'=IF(AND(F{r}=1,G{r}=1),"OK","À JUSTIFIER")')
        seq.conditional_formatting.add(
            f"H2:H{len(triees)+1}",
            FormulaRule(formula=['ISNUMBER(SEARCH("JUSTIFIER",H2))'], fill=REMPLISSAGE_ALERTE, font=POLICE_ALERTE),
        )

        comptes_internes = Counter(ligne["E_NUM_INTERNE"] for ligne in triees if ligne.get("E_NUM_INTERNE") not in (None, ""))
        valeurs_internes = [{"E_NUM_INTERNE": valeur} for valeur in sorted(comptes_internes, key=int)]
        entetes_occ_int = ["E_NUM_INTERNE", "COMPTER_E_NUM_INTERNE"]
        occ_int = ajouter_feuille(classeur, noms[4], entetes_occ_int, valeurs_internes, "OccInt")
        colonne_formules(occ_int, 1, len(valeurs_internes), lambda r, _i: f"=COUNTIF('{noms[1]}'!$B$2:$B${len(triees)+1},A{r})")
        doublons_int = [{"E_NUM_INTERNE": valeur, "COMPTER_E_NUM_INTERNE": compte} for valeur, compte in comptes_internes.items() if compte > 1]
        ajouter_feuille(classeur, noms[5], entetes_occ_int, doublons_int or [{"E_NUM_INTERNE": "AUCUN", "COMPTER_E_NUM_INTERNE": 0}], "DupInt")

        comptes_tickets = Counter(ligne["E_NUM_TICKET"] for ligne in triees if ligne.get("E_NUM_TICKET") not in (None, ""))
        valeurs_tickets = [{"E_NUM_TICKET": valeur} for valeur in sorted(comptes_tickets, key=int)]
        entetes_occ_ticket = ["E_NUM_TICKET", "COMPTER_E_NUM_TICKET"]
        occ_ticket = ajouter_feuille(classeur, noms[6], entetes_occ_ticket, valeurs_tickets, "OccTicket")
        colonne_formules(occ_ticket, 1, len(valeurs_tickets), lambda r, _i: f"=COUNTIF('{noms[1]}'!$C$2:$C${len(triees)+1},A{r})")
        doublons_ticket = [{"E_NUM_TICKET": valeur, "COMPTER_E_NUM_TICKET": compte} for valeur, compte in comptes_tickets.items() if compte > 1]
        ajouter_feuille(classeur, noms[7], entetes_occ_ticket, doublons_ticket or [{"E_NUM_TICKET": "AUCUN", "COMPTER_E_NUM_TICKET": 0}], "DupTicket")

        entetes_completes = [*COLONNES_EJ, "AJ_TOTAL_HT", "AJ_TOTAL_TVA_20", "AJ_ANNEE", "AJ_MOIS"]
        complete = ajouter_feuille(classeur, noms[8], entetes_completes, triees, "EntetesCplte")
        c = {nom: get_column_letter(index + 1) for index, nom in enumerate(entetes_completes)}
        colonne_formules(complete, entetes_completes.index("AJ_TOTAL_HT"), len(triees), lambda r, _i: f"=SUM({c['E_HT1']}{r}:{c['E_HT4']}{r})+{c['E_HT_NON_TAXABLE']}{r}")
        colonne_formules(complete, entetes_completes.index("AJ_TOTAL_TVA_20"), len(triees), lambda r, _i: f"={c['E_TVA1']}{r}")
        colonne_formules(complete, entetes_completes.index("AJ_ANNEE"), len(triees), lambda r, _i: f"=YEAR({c['E_DATE_TICKET']}{r})")
        colonne_formules(complete, entetes_completes.index("AJ_MOIS"), len(triees), lambda r, _i: f'=TEXT({c["E_DATE_TICKET"]}{r},"yyyy-mm")')

        mois = lignes_mensuelles()
        entetes_enc = ["AJ_ANNEE", "AJ_MOIS", "SOMME_E_TTC", "SOMME_E_MDP_CB", "SOMME_E_MDP_CHEQUES", "SOMME_E_MDP_ESPECES"]
        enc = ajouter_feuille(classeur, noms[9], entetes_enc, mois, "EncMensuelTD")
        plage_mois = f"'{noms[8]}'!${c['AJ_MOIS']}$2:${c['AJ_MOIS']}${len(triees)+1}"
        for cible, champ in ((2, "E_TTC"), (3, "E_MDP_CB"), (4, "E_MDP_CHEQUES"), (5, "E_MDP_ESPECES")):
            colonne_formules(enc, cible, len(mois), lambda r, _i, f=champ: f"=SUMIFS('{noms[8]}'!${c[f]}$2:${c[f]}${len(triees)+1},{plage_mois},B{r})")
        feuille_copie_formules(classeur, noms[10], noms[9], entetes_enc, mois, "EncMensuelCopie")

        entetes_rec = ["AJ_ANNEE", "AJ_MOIS", "SOMME_AJ_TOTAL_HT", "SOMME_AJ_TOTAL_TVA_20", "SOMME_E_TTC"]
        rec = ajouter_feuille(classeur, noms[11], entetes_rec, mois, "RecMensuelTD")
        for cible, champ in ((2, "AJ_TOTAL_HT"), (3, "AJ_TOTAL_TVA_20"), (4, "E_TTC")):
            colonne_formules(rec, cible, len(mois), lambda r, _i, f=champ: f"=SUMIFS('{noms[8]}'!${c[f]}$2:${c[f]}${len(triees)+1},{plage_mois},B{r})")
        feuille_copie_formules(classeur, noms[12], noms[11], entetes_rec, mois, "RecMensuelCopie")
        self.exporter(classeur, f"TTS_EJ_ENTETES_TICKETS_{boutique}.xlsx", demandees)

    def construire_lignes(self, boutique: str) -> None:
        classeur = nouveau_classeur()
        lignes = self.donnees["lignes"][boutique]
        triees = trier_tickets(lignes)
        demandees = [
            f"LIGNES_TICKETS_{boutique}_0", f"LIGNES_TICKETS_{boutique}_TriCrstNumInterne",
            f"LIGNES_TICKETS_{boutique}_CtrlCoherenceLigne", "TD_TotalLignesParNumTicket",
            "CtrlCoherence_EnteteLigne", "TD_OccurenceLibelleArticle", "TD_OccurenceTxTvaArticle",
        ]
        noms = [f"LIGNES_{boutique}_0", "Lignes_TriNumInterne", "Lignes_CtrlCoherence", "TD_TotalLignesParTicket", "CtrlCoherence_EnteteLigne", "TD_OccurenceLibelle", "TD_OccurenceTxTVA"]
        ajouter_feuille(classeur, noms[0], COLONNES_LIGNES_EJ, lignes, "Lignes0")
        ajouter_feuille(classeur, noms[1], COLONNES_LIGNES_EJ, triees, "LignesTri")
        ajouter_feuille(classeur, noms[2], COLONNES_LIGNES_EJ, triees, "LignesCtrl")

        premiere_ligne = {}
        for ligne in triees:
            premiere_ligne.setdefault(ligne["E_NUM_TICKET"], ligne)
        totaux = [{"E_NUM_TICKET": ligne["E_NUM_TICKET"], "E_TTC": ligne["E_TTC"]} for ligne in premiere_ligne.values()]
        entetes_totaux = ["E_NUM_TICKET", "E_TTC", "COMPTER_D_LIBELLE_ARTICLE", "SOMME_D_MONTANT_ARTICLE", "SOMME_D_CORRECTION"]
        feuille_totaux = ajouter_feuille(classeur, noms[3], entetes_totaux, totaux, "TotalLignes")
        colonne_formules(feuille_totaux, 2, len(totaux), lambda r, _i: f"=COUNTIF('{noms[2]}'!$C$2:$C${len(triees)+1},A{r})")
        colonne_formules(feuille_totaux, 3, len(totaux), lambda r, _i: f"=SUMIFS('{noms[2]}'!$V$2:$V${len(triees)+1},'{noms[2]}'!$C$2:$C${len(triees)+1},A{r})")
        colonne_formules(feuille_totaux, 4, len(totaux), lambda r, _i: f"=SUMIFS('{noms[2]}'!$W$2:$W${len(triees)+1},'{noms[2]}'!$C$2:$C${len(triees)+1},A{r})")

        entetes_coherence = [*entetes_totaux, "AJ_ECART_TTC"]
        coherence = ajouter_feuille(classeur, noms[4], entetes_coherence, totaux, "CoherenceEnteteLigne")
        for colonne in range(len(entetes_totaux)):
            lettre = get_column_letter(colonne + 1)
            colonne_formules(coherence, colonne, len(totaux), lambda r, _i, l=lettre: f"='{noms[3]}'!{l}{r}")
        colonne_formules(coherence, 5, len(totaux), lambda r, _i: f"=B{r}-D{r}-E{r}")
        mise_en_forme_ecart(coherence, 5, len(totaux))

        libelles = sorted({ligne["D_LIBELLE_ARTICLE"] for ligne in triees if ligne.get("D_LIBELLE_ARTICLE")})
        lignes_libelles = [{"D_LIBELLE_ARTICLE": valeur} for valeur in libelles]
        entetes_libelles = ["D_LIBELLE_ARTICLE", "COMPTER_D_LIBELLE_ARTICLE"]
        occ_libelles = ajouter_feuille(classeur, noms[5], entetes_libelles, lignes_libelles, "OccLibelle")
        colonne_formules(occ_libelles, 1, len(lignes_libelles), lambda r, _i: f"=COUNTIF('{noms[2]}'!$T$2:$T${len(triees)+1},A{r})")
        taux = sorted({ligne["D_TAUX_TVA_ARTICLE"] for ligne in triees if ligne.get("D_TAUX_TVA_ARTICLE")})
        lignes_taux = [{"D_TAUX_TVA_ARTICLE": valeur} for valeur in taux]
        entetes_taux = ["D_TAUX_TVA_ARTICLE", "COMPTER_D_TAUX_TVA_ARTICLE"]
        occ_taux = ajouter_feuille(classeur, noms[6], entetes_taux, lignes_taux, "OccTxTva")
        colonne_formules(occ_taux, 1, len(lignes_taux), lambda r, _i: f"=COUNTIF('{noms[2]}'!$U$2:$U${len(triees)+1},A{r})")
        self.exporter(classeur, f"TTS_EJ_LIGNES_TICKETS_{boutique}.xlsx", demandees)

    @staticmethod
    def entetes_larges(cibles: Iterable[str], quantite: bool) -> list[str]:
        resultat = ["AJ_ANNEE_Z", "AJ_MOIS_Z"]
        for cible in cibles:
            cle = nettoyer_nom(cible).upper()
            if quantite:
                resultat.append(f"{cle}_D_QUANTITE")
            resultat.append(f"{cle}_D_MONTANT")
        return resultat

    def ajouter_mode_large(self, classeur: Workbook, nom: str, mois: list[dict[str, Any]], mode: str, cibles: tuple[str, ...], feuille_td: str, entetes_td: list[str], quantite: bool, tableau: str) -> list[str]:
        entetes = self.entetes_larges(cibles, quantite)
        feuille = ajouter_feuille(classeur, nom, entetes, mois, tableau)
        colonnes = {entete: get_column_letter(index + 1) for index, entete in enumerate(entetes_td)}
        derniere = 1 + len(mois) * 3 * len(cibles)
        colonne = 2
        for cible in cibles:
            for champ in (("D_QUANTITE", "D_MONTANT") if quantite else ("D_MONTANT",)):
                colonne_formules(
                    feuille, colonne, len(mois),
                    lambda r, _i, f=champ, c=cible: (
                        f"=SUMIFS('{feuille_td}'!${colonnes[f]}$2:${colonnes[f]}${derniere},"
                        f"'{feuille_td}'!${colonnes['AJ_MOIS_Z']}$2:${colonnes['AJ_MOIS_Z']}${derniere},B{r},"
                        f"'{feuille_td}'!${colonnes['E_MODE']}$2:${colonnes['E_MODE']}${derniere},\"{mode}\","
                        f"'{feuille_td}'!${colonnes['D_DESIGNATION']}$2:${colonnes['D_DESIGNATION']}${derniere},\"{c}\")"
                    ),
                )
                colonne += 1
        return entetes

    def construire_z2(self, boutique: str, annee: int) -> None:
        classeur = nouveau_classeur()
        lignes = self.donnees["z2"][boutique][annee]
        demandees = [
            f"Z2_TransactionsMois_TOUS_{annee}_{boutique}_0",
            f"Z2_TransactionsMois_TOUS_{annee}_{boutique}_CplteAnneeMoisZ",
            "TD_TotalMontant_parMoisAnnee_parNatureTransaction",
            f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZZ1",
            f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZZ2",
            f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZ",
        ]
        if boutique == "MASSENA":
            demandees.append(f"Compare_Montant_Massena_Z2_ModeZZ1vsModeZZ2_{annee}")
        demandees.append(f"Compare_Montant_{boutique}_Z2Mode{'ZZ1' if boutique == 'MASSENA' else 'Z'}vsEJ_{annee}")
        noms = [f"Z2_{annee}_{boutique}_0", "Z2_CplteAnneeMois", "TD_TotalNatureTransac", "Z2_Total_ModeZZ1", "Z2_Total_ModeZZ2", "Z2_Total_ModeZ"]
        if boutique == "MASSENA":
            noms.append("Compare_ZZ1_vs_ZZ2")
        noms.append("Compare_ZZ1_vs_EJ" if boutique == "MASSENA" else "Compare_Z_vs_EJ")
        ajouter_feuille(classeur, noms[0], COLONNES_Z, lignes, "Z2Raw")
        entetes_completes = [*COLONNES_Z, "AJ_ANNEE_Z", "AJ_MOIS_Z"]
        completes = [{**ligne, "AJ_ANNEE_Z": int(periodes_reference(ligne["nomfichier"])[0][:4]), "AJ_MOIS_Z": etiquette_periodes(ligne["nomfichier"])} for ligne in lignes]
        ajouter_feuille(classeur, noms[1], entetes_completes, completes, "Z2Cplte")
        mois = self.periodes_cloture(annee, boutique)
        td_lignes = [{**m, "E_MODE": mode, "D_DESIGNATION": designation} for m in mois for mode in ("Z", "ZZ1", "ZZ2") for designation in CIBLES_Z2]
        td_entetes = ["AJ_ANNEE_Z", "AJ_MOIS_Z", "E_MODE", "D_DESIGNATION", "D_QUANTITE", "D_MONTANT"]
        td = ajouter_feuille(classeur, noms[2], td_entetes, td_lignes, "Z2TotalNature")
        derniere = len(completes) + 1
        colonne_formules(td, 4, len(td_lignes), lambda r, _i: f"=SUMIFS('{noms[1]}'!$L$2:$L${derniere},'{noms[1]}'!$O$2:$O${derniere},B{r},'{noms[1]}'!$F$2:$F${derniere},C{r},'{noms[1]}'!$K$2:$K${derniere},D{r})")
        colonne_formules(td, 5, len(td_lignes), lambda r, _i: f"=SUMIFS('{noms[1]}'!$M$2:$M${derniere},'{noms[1]}'!$O$2:$O${derniere},B{r},'{noms[1]}'!$F$2:$F${derniere},C{r},'{noms[1]}'!$K$2:$K${derniere},D{r})")
        entetes_modes = {}
        for index, mode in enumerate(("ZZ1", "ZZ2", "Z")):
            entetes_modes[mode] = self.ajouter_mode_large(classeur, noms[3 + index], mois, mode, CIBLES_Z2, noms[2], td_entetes, True, f"Z2Mode{mode}")
        if boutique == "MASSENA":
            entetes_comp = ["AJ_ANNEE_Z", "AJ_MOIS_Z", *[element for cible in CIBLES_Z2 for element in (f"{nettoyer_nom(cible).upper()}_AJ_ECART_QTE", f"{nettoyer_nom(cible).upper()}_AJ_ECART_MONTANT")]]
            comp = ajouter_feuille(classeur, noms[6], entetes_comp, mois, "CompareZ2Modes")
            colonne = 2
            for index in range(len(CIBLES_Z2)):
                lettre_qte = get_column_letter(3 + index * 2)
                lettre_montant = get_column_letter(4 + index * 2)
                colonne_formules(comp, colonne, len(mois), lambda r, _i, l=lettre_qte: f"='{noms[3]}'!{l}{r}-'{noms[4]}'!{l}{r}")
                colonne += 1
                colonne_formules(comp, colonne, len(mois), lambda r, _i, l=lettre_montant: f"='{noms[3]}'!{l}{r}-'{noms[4]}'!{l}{r}")
                mise_en_forme_ecart(comp, colonne, len(mois))
                colonne += 1
        compare_nom = noms[-1]
        mode_retenu = "ZZ1" if boutique == "MASSENA" else "Z"
        feuille_mode = noms[3] if mode_retenu == "ZZ1" else noms[5]
        entetes_compare = ["AJ_ANNEE_Z", "AJ_MOIS_Z", "CARTES_Z2", "CARTES_EJ", "AJ_ECART_CARTES", "CHEQUES_Z2", "CHEQUES_EJ", "AJ_ECART_CHEQUES", "ESPECES_Z2", "ESPECES_EJ", "AJ_ECART_ESPECES"]
        ej = self.ej_clotures[boutique]
        lignes_compare = [{**m, "CARTES_EJ": ej.get(m["AJ_MOIS_Z"], {}).get("E_MDP_CB", Decimal("0")), "CHEQUES_EJ": ej.get(m["AJ_MOIS_Z"], {}).get("E_MDP_CHEQUES", Decimal("0")), "ESPECES_EJ": ej.get(m["AJ_MOIS_Z"], {}).get("E_MDP_ESPECES", Decimal("0"))} for m in mois]
        compare = ajouter_feuille(classeur, compare_nom, entetes_compare, lignes_compare, "CompareZ2EJ")
        colonnes_sources = {cible: get_column_letter(entetes_modes[mode_retenu].index(f"{cible}_D_MONTANT") + 1) for cible in ("CARTES", "CHEQUES", "ESPECES")}
        for z, source, ecart, cible in ((2, 3, 4, "CARTES"), (5, 6, 7, "CHEQUES"), (8, 9, 10, "ESPECES")):
            colonne_formules(compare, z, len(mois), lambda r, _i, c=cible: f"='{feuille_mode}'!{colonnes_sources[c]}{r}")
            colonne_formules(compare, ecart, len(mois), lambda r, _i, zc=z, sc=source: f"={get_column_letter(zc+1)}{r}-{get_column_letter(sc+1)}{r}")
            mise_en_forme_ecart(compare, ecart, len(mois))
        self.exporter(classeur, f"TTS_Z2_TransactionsMois_TOUS_{annee}_{boutique}.xlsx", demandees)

    def construire_z1(self, boutique: str, annee: int) -> None:
        classeur = nouveau_classeur()
        lignes = self.donnees["z1"][boutique][annee]
        mode_retenu = "ZZ1" if boutique == "MASSENA" else "Z"
        demandees = [
            f"Z1_SyntheseMois_TOUS_{annee}_{boutique}_0", f"Z1_SyntheseMois_TOUS_{annee}_{boutique}_CplteAnneeMoisZ",
            f"TD_OccurenceEfichierEmodeParMoisAnnee_{annee}", f"TD_Z1_TotalMontantParMoisAnnee_{annee}",
            f"Z1_TotalMontantParMoisAnnee_{annee}_ModeZZ1", f"Z1_TotalMontantParMoisAnnee_{annee}_ModeZZ2",
            f"Z1_TotalMontantParMoisAnnee_{annee}_ModeZ", f"Compare_Montant_{boutique}_Z1Mode{mode_retenu}vsEJ_{annee}",
        ]
        noms = [f"Z1_{annee}_{boutique}_0", "Z1_CplteAnneeMois", "TD_OccurenceFichMode", "TD_Z1_TotalMontant", "Z1_Total_ModeZZ1", "Z1_Total_ModeZZ2", "Z1_Total_ModeZ", "Compare_ZZ1_vs_EJ" if boutique == "MASSENA" else "Compare_Z_vs_EJ"]
        ajouter_feuille(classeur, noms[0], COLONNES_Z, lignes, "Z1Raw")
        entetes_completes = [*COLONNES_Z, "AJ_ANNEE_Z", "AJ_MOIS_Z"]
        completes = [{**ligne, "AJ_ANNEE_Z": int(periodes_reference(ligne["nomfichier"])[0][:4]), "AJ_MOIS_Z": etiquette_periodes(ligne["nomfichier"])} for ligne in lignes]
        ajouter_feuille(classeur, noms[1], entetes_completes, completes, "Z1Cplte")
        derniere = len(completes) + 1
        uniques = {}
        for ligne in completes:
            cle = (ligne["AJ_MOIS_Z"], ligne["E_DATE"], ligne["E_FICHIER"], ligne["E_MODE"])
            uniques.setdefault(cle, {"AJ_ANNEE_Z": ligne["AJ_ANNEE_Z"], "AJ_MOIS_Z": ligne["AJ_MOIS_Z"], "E_DATE": ligne["E_DATE"], "E_FICHIER": ligne["E_FICHIER"], "E_MODE": ligne["E_MODE"]})
        occurrences = sorted(uniques.values(), key=lambda ligne: (ligne["AJ_MOIS_Z"], ligne["E_MODE"], ligne["E_FICHIER"]))
        entetes_occ = ["AJ_ANNEE_Z", "AJ_MOIS_Z", "E_DATE", "E_FICHIER", "E_MODE", "OCCURRENCES"]
        occ = ajouter_feuille(classeur, noms[2], entetes_occ, occurrences, "OccZ1FichMode")
        colonne_formules(occ, 5, len(occurrences), lambda r, _i: f"=COUNTIFS('{noms[1]}'!$O$2:$O${derniere},B{r},'{noms[1]}'!$H$2:$H${derniere},C{r},'{noms[1]}'!$E$2:$E${derniere},D{r},'{noms[1]}'!$F$2:$F${derniere},E{r})")
        mois = self.periodes_cloture(annee, boutique)
        td_lignes = [{**m, "E_MODE": mode, "D_DESIGNATION": designation} for m in mois for mode in ("Z", "ZZ1", "ZZ2") for designation in CIBLES_Z1]
        td_entetes = ["AJ_ANNEE_Z", "AJ_MOIS_Z", "E_MODE", "D_DESIGNATION", "D_MONTANT"]
        td = ajouter_feuille(classeur, noms[3], td_entetes, td_lignes, "Z1TotalMontant")
        colonne_formules(td, 4, len(td_lignes), lambda r, _i: f"=SUMIFS('{noms[1]}'!$M$2:$M${derniere},'{noms[1]}'!$O$2:$O${derniere},B{r},'{noms[1]}'!$F$2:$F${derniere},C{r},'{noms[1]}'!$K$2:$K${derniere},D{r})")
        entetes_modes = {}
        for index, mode in enumerate(("ZZ1", "ZZ2", "Z")):
            entetes_modes[mode] = self.ajouter_mode_large(classeur, noms[4 + index], mois, mode, CIBLES_Z1, noms[3], td_entetes, False, f"Z1Mode{mode}")
        feuille_mode = noms[4] if mode_retenu == "ZZ1" else noms[6]
        entetes_compare = ["AJ_ANNEE_Z", "AJ_MOIS_Z", "CA_TTC_Z1", "CA_TTC_EJ", "AJ_ECART_CA_TTC", "HORS_TAXE_1_Z1", "HORS_TAXE_1_EJ", "AJ_ECART_HORS_TAXE_1", "TVA1_Z1", "TVA1_EJ", "AJ_ECART_TVA1"]
        ej = self.ej_clotures[boutique]
        lignes_compare = [{**m, "CA_TTC_EJ": ej.get(m["AJ_MOIS_Z"], {}).get("E_TTC", Decimal("0")), "HORS_TAXE_1_EJ": ej.get(m["AJ_MOIS_Z"], {}).get("AJ_TOTAL_HT", Decimal("0")), "TVA1_EJ": ej.get(m["AJ_MOIS_Z"], {}).get("AJ_TOTAL_TVA_20", Decimal("0"))} for m in mois]
        compare = ajouter_feuille(classeur, noms[7], entetes_compare, lignes_compare, "CompareZ1EJ")
        sources = {
            "CA BRUT": get_column_letter(entetes_modes[mode_retenu].index("CA_BRUT_D_MONTANT") + 1),
            "HORS TAXE 1": get_column_letter(entetes_modes[mode_retenu].index("HORS_TAXE_1_D_MONTANT") + 1),
            "TVA 1": get_column_letter(entetes_modes[mode_retenu].index("TVA_1_D_MONTANT") + 1),
        }
        for z, source, ecart, cible in ((2, 3, 4, "CA BRUT"), (5, 6, 7, "HORS TAXE 1"), (8, 9, 10, "TVA 1")):
            colonne_formules(compare, z, len(mois), lambda r, _i, c=cible: f"='{feuille_mode}'!{sources[c]}{r}")
            colonne_formules(compare, ecart, len(mois), lambda r, _i, zc=z, sc=source: f"={get_column_letter(zc+1)}{r}-{get_column_letter(sc+1)}{r}")
            mise_en_forme_ecart(compare, ecart, len(mois))
        self.exporter(classeur, f"TTS_Z1_SyntheseMois_TOUS_{annee}_{boutique}.xlsx", demandees)

    def construire_recettes(self) -> None:
        classeur = nouveau_classeur()
        cartes = {boutique: {ligne["AJ_MOIS"]: ligne for ligne in self.ej_mensuels[boutique]} for boutique in BOUTIQUES}
        lignes = [{
            **mois,
            "MASSENA_SOMME_AJ_TOTAL_HT": cartes["MASSENA"][mois["AJ_MOIS"]]["AJ_TOTAL_HT"],
            "MASSENA_SOMME_AJ_TOTAL_TVA_20": cartes["MASSENA"][mois["AJ_MOIS"]]["AJ_TOTAL_TVA_20"],
            "MASSENA_SOMME_E_TTC": cartes["MASSENA"][mois["AJ_MOIS"]]["E_TTC"],
            "MATURIN_SOMME_AJ_TOTAL_HT": cartes["MATURIN"][mois["AJ_MOIS"]]["AJ_TOTAL_HT"],
            "MATURIN_SOMME_AJ_TOTAL_TVA_20": cartes["MATURIN"][mois["AJ_MOIS"]]["AJ_TOTAL_TVA_20"],
            "MATURIN_SOMME_E_TTC": cartes["MATURIN"][mois["AJ_MOIS"]]["E_TTC"],
        } for mois in lignes_mensuelles()]
        entetes = ["AJ_ANNEE", "AJ_MOIS", "MASSENA_SOMME_AJ_TOTAL_HT", "MASSENA_SOMME_AJ_TOTAL_TVA_20", "MASSENA_SOMME_E_TTC", "MATURIN_SOMME_AJ_TOTAL_HT", "MATURIN_SOMME_AJ_TOTAL_TVA_20", "MATURIN_SOMME_E_TTC", "AJ_TOTAL_TOUS_BOUTIQUE_HT", "AJ_TOTAL_TOUS_BOUTIQUE_TVA", "AJ_TOTAL_TOUS_BOUTIQUE_TTC"]
        feuille = ajouter_feuille(classeur, "recettes_mensuelles_tous", entetes, lignes, "RecettesTous")
        colonne_formules(feuille, 8, len(lignes), lambda r, _i: f"=C{r}+F{r}")
        colonne_formules(feuille, 9, len(lignes), lambda r, _i: f"=D{r}+G{r}")
        colonne_formules(feuille, 10, len(lignes), lambda r, _i: f"=E{r}+H{r}")
        self.exporter(classeur, "recettes_mensuelles_tous_boutique_232425.xlsx", ["recettes_mensuelles_tous_boutique_232425"])

    def construire_ca3(self) -> None:
        classeur = nouveau_classeur()
        cartes = {boutique: {ligne["AJ_MOIS"]: ligne for ligne in self.ej_mensuels[boutique]} for boutique in BOUTIQUES}
        lignes = []
        for mois in lignes_mensuelles():
            libelle = mois["AJ_MOIS"]
            lignes.append({
                **mois,
                "AJ_TOTAL_TOUS_BOUTIQUE_HT": cartes["MASSENA"][libelle]["AJ_TOTAL_HT"] + cartes["MATURIN"][libelle]["AJ_TOTAL_HT"],
                "AJ_TOTAL_TOUS_BOUTIQUE_TVA": cartes["MASSENA"][libelle]["AJ_TOTAL_TVA_20"] + cartes["MATURIN"][libelle]["AJ_TOTAL_TVA_20"],
                "AJ_TOTAL_TOUS_BOUTIQUE_TTC": cartes["MASSENA"][libelle]["E_TTC"] + cartes["MATURIN"][libelle]["E_TTC"],
            })
        entetes = ["AJ_ANNEE", "AJ_MOIS", "AJ_TOTAL_TOUS_BOUTIQUE_HT", "AJ_TOTAL_TOUS_BOUTIQUE_TVA", "AJ_TOTAL_TOUS_BOUTIQUE_TTC", "MTT_HT1_CA3", "MTT_HT1_20_CA3", "MTT_TVA_20_CA3", "AJ_ECART_HT20", "AJ_ECART_TVA20", "STATUT", "COMMENTAIRE"]
        feuille = ajouter_feuille(classeur, "CompareCA_Gesco_CA3", entetes, lignes, "CompareCA3")
        colonne_formules(feuille, 8, len(lignes), lambda r, _i: f'=IF(G{r}="","",C{r}-G{r})')
        colonne_formules(feuille, 9, len(lignes), lambda r, _i: f'=IF(H{r}="","",D{r}-H{r})')
        colonne_formules(feuille, 10, len(lignes), lambda r, _i: f'=IF(COUNTA(F{r}:H{r})=0,"À SAISIR","RENSEIGNÉ")')
        for ligne in range(2, len(lignes) + 2):
            for colonne in range(6, 9):
                feuille.cell(ligne, colonne).fill = copy(REMPLISSAGE_SAISIE)
            feuille.cell(ligne, 12).fill = copy(REMPLISSAGE_SAISIE)
        feuille.conditional_formatting.add(f"K2:K{len(lignes)+1}", FormulaRule(formula=['ISNUMBER(SEARCH("À SAISIR",K2))'], fill=REMPLISSAGE_ALERTE, font=POLICE_ALERTE))
        mise_en_forme_ecart(feuille, 8, len(lignes))
        mise_en_forme_ecart(feuille, 9, len(lignes))

        entetes_fec = ["EXERCICE", "PERIODE", "GESCo_HT", "GESCo_TVA", "GESCo_TTC", "CA_HT_FEC", "TVA_COLLECTEE_FEC", "CA_TTC_FEC", "AJ_ECART_HT", "AJ_ECART_TVA", "AJ_ECART_TTC", "SOURCE_FEC", "STATUT"]
        lignes_fec = []
        for annee in ANNEES:
            selection = [ligne for ligne in lignes if ligne["AJ_ANNEE"] == annee]
            lignes_fec.append([
                annee, "2025-01-01 au 2025-08-31" if annee == 2025 else f"{annee}-01-01 au {annee}-12-31",
                sum((ligne["AJ_TOTAL_TOUS_BOUTIQUE_HT"] for ligne in selection), Decimal("0")),
                sum((ligne["AJ_TOTAL_TOUS_BOUTIQUE_TVA"] for ligne in selection), Decimal("0")),
                sum((ligne["AJ_TOTAL_TOUS_BOUTIQUE_TTC"] for ligne in selection), Decimal("0")),
                None, None, None, None, None, None, None, None,
            ])
        for colonne, valeur in enumerate(entetes_fec, start=14):
            cellule = feuille.cell(1, colonne, valeur)
            cellule.fill = copy(REMPLISSAGE_ENTETE)
            cellule.font = Font(name="Aptos Display", size=10, bold=True, color="FFFFFF")
            cellule.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cellule.border = Border(top=BORD_ENTETE, bottom=BORD_ENTETE, left=BORD_ENTETE, right=BORD_ENTETE)
        for index_ligne, valeurs in enumerate(lignes_fec, start=2):
            for index_colonne, valeur in enumerate(valeurs, start=14):
                cellule = feuille.cell(index_ligne, index_colonne, valeur)
                cellule.font = Font(name="Aptos", size=9)
                cellule.border = Border(bottom=BORD_FIN)
                if 16 <= index_colonne <= 24:
                    cellule.number_format = FORMAT_MONTANT
            for colonne in range(19, 22):
                feuille.cell(index_ligne, colonne).fill = copy(REMPLISSAGE_SAISIE)
            feuille.cell(index_ligne, 25).fill = copy(REMPLISSAGE_SAISIE)
            feuille.cell(index_ligne, 22, f'=IF(S{index_ligne}="","",P{index_ligne}-S{index_ligne})')
            feuille.cell(index_ligne, 23, f'=IF(T{index_ligne}="","",Q{index_ligne}-T{index_ligne})')
            feuille.cell(index_ligne, 24, f'=IF(U{index_ligne}="","",R{index_ligne}-U{index_ligne})')
            feuille.cell(index_ligne, 26, f'=IF(COUNTA(S{index_ligne}:U{index_ligne})=0,"À SAISIR","RENSEIGNÉ")')
        feuille.column_dimensions["O"].width = 26
        for lettre in ("P", "Q", "R", "S", "T", "U", "V", "W", "X"):
            feuille.column_dimensions[lettre].width = 17
        feuille.column_dimensions["Y"].width = 24
        feuille.column_dimensions["Z"].width = 16
        feuille.conditional_formatting.add("Z2:Z4", FormulaRule(formula=['ISNUMBER(SEARCH("À SAISIR",Z2))'], fill=REMPLISSAGE_ALERTE, font=POLICE_ALERTE))
        for colonne in (21, 22, 23):
            mise_en_forme_ecart(feuille, colonne, 3)
        self.exporter(classeur, "CompareCA_Gesco_CA3.xlsx", ["CompareCA_Gesco_CA3"])

    def rendre_qa(self) -> int:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        pdftoppm = shutil.which("pdftoppm")
        if not soffice or not pdftoppm:
            raise FileNotFoundError("Le mode --qa nécessite LibreOffice (soffice) et pdftoppm.")
        if self.qa_dir.exists():
            shutil.rmtree(self.qa_dir)
        self.qa_dir.mkdir(parents=True)
        pages = 0
        for entree in self.manifeste["workbooks"]:
            nom = entree["fileName"]
            destination = self.qa_dir / Path(nom).stem
            destination.mkdir()
            with tempfile.TemporaryDirectory(prefix="qa_751_") as temporaire:
                temporaire_path = Path(temporaire)
                source = self.xlsx / nom
                classeur = load_workbook(source)
                for feuille in classeur.worksheets:
                    derniere_colonne = min(max(feuille.max_column, 1), 26)
                    derniere_ligne = min(max(feuille.max_row, 1), 16)
                    feuille.print_area = f"A1:{get_column_letter(derniere_colonne)}{derniere_ligne}"
                    feuille.page_setup.orientation = "landscape"
                    feuille.page_setup.fitToWidth = 1
                    feuille.page_setup.fitToHeight = 1
                    feuille.sheet_properties.pageSetUpPr.fitToPage = True
                    feuille.sheet_properties.pageSetUpPr.autoPageBreaks = False
                temporaire_xlsx = temporaire_path / nom
                classeur.save(temporaire_xlsx)
                classeur.close()
                profil_libreoffice = temporaire_path / "profil_libreoffice"
                conversion = subprocess.run(
                    [
                        soffice,
                        f"-env:UserInstallation={profil_libreoffice.as_uri()}",
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        str(temporaire_path),
                        str(temporaire_xlsx),
                    ],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                if conversion.returncode:
                    raise RuntimeError(
                        f"Échec du rendu LibreOffice pour {nom} "
                        f"(code {conversion.returncode}) : {conversion.stdout.strip()}"
                    )
                pdf = temporaire_path / f"{Path(nom).stem}.pdf"
                if not pdf.is_file():
                    raise RuntimeError(f"Aperçu PDF non produit pour {nom}")
                prefixe = destination / "feuille"
                subprocess.run([pdftoppm, "-png", "-r", "90", str(pdf), str(prefixe)], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                images = sorted(destination.glob("feuille-*.png"))
                if len(images) != entree["sheetCount"]:
                    raise RuntimeError(f"{nom}: {len(images)} aperçus pour {entree['sheetCount']} feuilles")
                pages += len(images)
        return pages

    def construire(self) -> dict[str, Any]:
        for boutique in BOUTIQUES:
            self.construire_entetes(boutique)
            self.construire_lignes(boutique)
        for boutique in BOUTIQUES:
            for annee in ANNEES:
                self.construire_z1(boutique, annee)
                self.construire_z2(boutique, annee)
        self.construire_recettes()
        self.construire_ca3()
        self.manifeste["summary"] = {
            "excelFiles": len(self.manifeste["workbooks"]),
            "excelSheets": sum(entree["sheetCount"] for entree in self.manifeste["workbooks"]),
            "csvFiles": len(self.manifeste["csvFiles"]),
        }
        self.manifeste["controle"] = json.loads((self.controle / "RESUME_EXPORT_751.json").read_text(encoding="utf-8"))
        if self.qa:
            self.manifeste["summary"]["qaPreviews"] = self.rendre_qa()
        for entree in self.manifeste["workbooks"]:
            chemin = self.xlsx / entree["fileName"]
            entree["sha256"] = hashlib.sha256(chemin.read_bytes()).hexdigest()
        self.controle.mkdir(parents=True, exist_ok=True)
        (self.controle / "MANIFESTE_CONTROLE_751.json").write_text(
            json.dumps(self.manifeste, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.manifeste["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--controle", type=Path, required=True)
    parser.add_argument("--sortie", type=Path, required=True)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--qa", action="store_true")
    args = parser.parse_args(argv)
    resume = Constructeur751(
        args.staging.resolve(),
        args.controle.resolve(),
        args.sortie.resolve(),
        args.qa_dir.resolve(),
        args.qa,
    ).construire()
    print(json.dumps(resume, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
