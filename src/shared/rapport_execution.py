"""Collecte les mesures d'exécution et produit le rapport final des ODS.

Les compteurs ``lus`` et ``sélectionnés`` sont mémorisés à la fin de chaque
étape du pipeline. Le rapport final relit ensuite les ODS publiés uniquement
pour contrôler les lignes effectivement écrites et les totaux numériques.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import ZipFile

from shared.constantes import SEPARATEUR_CSV


NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
ATTR_NOM = f"{{{NS['table']}}}name"
ATTR_REPETITION_COLONNES = f"{{{NS['table']}}}number-columns-repeated"
ATTR_REPETITION_LIGNES = f"{{{NS['table']}}}number-rows-repeated"
ATTR_TYPE = f"{{{NS['office']}}}value-type"
ATTR_VALEUR = f"{{{NS['office']}}}value"


@dataclass(frozen=True)
class Cellule:
    texte: str
    nombre: Decimal | None = None


@dataclass(frozen=True)
class MesureFeuille:
    fichier: Path
    feuille: str
    sources: tuple[str, ...]
    lus: int
    selectionnes: int
    ecrits: int
    portee_compteurs: str = "source immédiate"
    source_metier: str | None = None


@dataclass(frozen=True)
class CompteurTraitement:
    lus: int
    selectionnes: int
    source_metier: str


@dataclass(frozen=True)
class AnalyseFeuille:
    lignes_ecrites: int
    totaux_numeriques: dict[str, Decimal]


CHAMPS_MONTANTS = (
    "MONTANT",
    "MDP",
    "SOLDE",
    "ECART",
    "CORRECTION",
)
CHAMPS_QUANTITES = ("QUANTITE", "QTE", "COMPTER")
DESIGNATIONS_Z1_MONTANTS = (
    "CA BRUT",
    "CA NET",
    "CB.TIROIR",
    "CHQ.TIROIR",
    "ESP.TIROIR",
    "HORS TAXE",
)


def _attribut_entier(element: ElementTree.Element, nom: str) -> int:
    valeur = element.get(nom, "1")
    try:
        return max(1, int(valeur))
    except ValueError as erreur:
        raise ValueError(f"Répétition ODS invalide : {valeur!r}") from erreur


def _lire_cellule(element: ElementTree.Element) -> Cellule:
    """Lit la valeur persistée ODS sans interpréter son rendu formaté.

    ``office:value`` est la valeur numérique réelle de Calc, y compris pour
    les pourcentages (par exemple 20 % est persisté sous la forme ``0.2``).
    Le contenu de ``text:p`` est conservé uniquement comme libellé affiché.
    """
    texte = "".join(element.itertext()).strip()
    if element.get(ATTR_TYPE) not in {"float", "currency", "percentage"}:
        return Cellule(texte)
    valeur = element.get(ATTR_VALEUR)
    if valeur is None:
        return Cellule(texte)
    try:
        return Cellule(texte, Decimal(valeur))
    except InvalidOperation as erreur:
        raise ValueError(f"Valeur numérique ODS invalide : {valeur!r}") from erreur


def lire_feuilles_ods(chemin: Path) -> dict[str, tuple[tuple[Cellule, ...], ...]]:
    """Lit les valeurs persistées des feuilles d'un ODS sans lancer Calc."""
    with ZipFile(chemin) as archive:
        contenu = archive.read("content.xml")
    racine = ElementTree.fromstring(contenu)
    resultat: dict[str, tuple[tuple[Cellule, ...], ...]] = {}
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
                    continue
                if cellule.tag != f"{{{NS['table']}}}table-cell":
                    continue
                cellules.extend(
                    [_lire_cellule(cellule)]
                    * _attribut_entier(cellule, ATTR_REPETITION_COLONNES)
                )
            if not any(cellule.texte or cellule.nombre is not None for cellule in cellules):
                continue
            valeur_ligne = tuple(cellules)
            lignes.extend(
                [valeur_ligne] * _attribut_entier(ligne, ATTR_REPETITION_LIGNES)
            )
        resultat[nom] = tuple(lignes)
    return resultat


def analyser_feuille(lignes: tuple[tuple[Cellule, ...], ...]) -> AnalyseFeuille:
    """Compte les données et totalise uniquement montants et quantités."""
    if not lignes:
        return AnalyseFeuille(0, {})
    if any(cellule.texte == "AJ_TROU_NUM_TICKET" for cellule in lignes[0]):
        # La première ligne métier de sequentialité ne porte volontairement
        # aucun trou. Elle est donc entièrement textuelle et ne doit pas être
        # confondue avec une seconde ligne d'en-tête.
        index_donnees = 1
    else:
        premiere_ligne_numerique = next(
            (
                index
                for index, ligne in enumerate(lignes)
                if any(cellule.nombre is not None for cellule in ligne)
            ),
            None,
        )
        index_donnees = (
            1 if premiere_ligne_numerique is None else premiere_ligne_numerique
        )
    entetes = lignes[:index_donnees]
    est_tableau_croise = any(
        cellule.texte == "Data"
        or cellule.texte.startswith(("Somme - ", "Compter - "))
        for ligne in entetes
        for cellule in ligne
    )
    donnees = tuple(
        ligne
        for ligne in lignes[index_donnees:]
        if not est_tableau_croise or not _est_ligne_total_general(ligne)
    )
    analyse_tcd_z2 = _analyser_tcd_z2(entetes, donnees)
    if analyse_tcd_z2 is not None:
        return AnalyseFeuille(len(donnees), analyse_tcd_z2)
    largeur = max((len(ligne) for ligne in lignes), default=0)
    totaux: dict[str, Decimal] = {}
    noms_colonnes = _noms_colonnes(entetes, largeur)
    for colonne in range(largeur):
        valeurs = [
            ligne[colonne].nombre
            for ligne in donnees
            if colonne < len(ligne) and ligne[colonne].nombre is not None
        ]
        if not valeurs:
            continue
        nom = noms_colonnes[colonne]
        if not _champ_totalisable(nom, entetes):
            continue
        totaux[nom] = sum(valeurs, Decimal())
    return AnalyseFeuille(len(donnees), totaux)


def _est_ligne_total_general(ligne: tuple[Cellule, ...]) -> bool:
    """Écarte les lignes de synthèse ajoutées par les tableaux croisés."""
    libelles = {
        cellule.texte.strip().upper().replace("É", "E")
        for cellule in ligne
        if cellule.texte
    }
    return bool(libelles & {"TOTAL GENERAL", "GRAND TOTAL"})


def _noms_colonnes(
    entetes: tuple[tuple[Cellule, ...], ...], largeur: int
) -> tuple[str, ...]:
    """Reconstruit les en-têtes, y compris les cellules fusionnées de Calc."""
    par_colonne: list[list[str]] = [[] for _ in range(largeur)]
    for ligne in entetes:
        precedent = ""
        for colonne in range(largeur):
            texte = ligne[colonne].texte if colonne < len(ligne) else ""
            if texte:
                precedent = texte
            if precedent:
                par_colonne[colonne].append(precedent)
    return tuple(
        " / ".join(dict.fromkeys(morceaux)) or f"colonne_{index + 1}"
        for index, morceaux in enumerate(par_colonne)
    )


def _champ_totalisable(
    nom: str,
    entetes: tuple[tuple[Cellule, ...], ...] = (),
) -> bool:
    return _est_quantite(nom) or _est_montant(nom, entetes)


def _est_quantite(nom: str) -> bool:
    nom_normalise = nom.upper().replace("É", "E")
    feuille = nom_normalise.rsplit(" / ", 1)[-1]
    return any(motif in feuille for motif in CHAMPS_QUANTITES)


def _est_montant(
    nom: str,
    entetes: tuple[tuple[Cellule, ...], ...] = (),
) -> bool:
    nom_normalise = nom.upper().replace("É", "E")
    feuille = nom_normalise.rsplit(" / ", 1)[-1]
    if _est_quantite(nom) or "TAUX" in feuille:
        return False
    if any(motif in feuille for motif in CHAMPS_MONTANTS):
        return True
    if re.search(r"(?:^|[^A-Z0-9])(HT\d*|TTC|TVA\d*)(?:$|[^A-Z0-9])", feuille):
        return True
    if any(designation in feuille for designation in DESIGNATIONS_Z1_MONTANTS):
        return True
    if "D_DESIGNATION /" in nom_normalise:
        return True
    if feuille in {"AJ_ANNEE_Z", "AJ_MOIS_Z", "DATA", "(EMPTY)"}:
        return False
    return any(
        cellule.texte == "Somme - D_MONTANT"
        for ligne in entetes
        for cellule in ligne
    ) and feuille not in {"AJ_ANNEE_Z", "AJ_MOIS_Z"}


def _analyser_tcd_z2(
    entetes: tuple[tuple[Cellule, ...], ...],
    donnees: tuple[tuple[Cellule, ...], ...],
) -> dict[str, Decimal] | None:
    """Extrait les mesures disposées en lignes du TCD Z2 principal."""
    ligne_entete = next(
        (
            ligne
            for ligne in reversed(entetes)
            if any(cellule.texte == "Data" for cellule in ligne)
        ),
        None,
    )
    if ligne_entete is None:
        return None
    index_data = next(
        index for index, cellule in enumerate(ligne_entete) if cellule.texte == "Data"
    )
    totaux: dict[str, Decimal] = {}
    for ligne in donnees:
        if index_data >= len(ligne):
            continue
        mesure = ligne[index_data].texte.removeprefix("Somme - ")
        if mesure not in {"D_QUANTITE", "D_MONTANT"}:
            continue
        for colonne in range(index_data + 1, min(len(ligne_entete), len(ligne))):
            nature = ligne_entete[colonne].texte
            valeur = ligne[colonne].nombre
            if not nature or nature == "(empty)" or valeur is None:
                continue
            cle = f"{nature} / {mesure}"
            totaux[cle] = totaux.get(cle, Decimal()) + valeur
    # Une ligne d'en-tête ``Data`` existe aussi dans les TCD dont les mesures
    # sont disposées en colonnes. Dans ce cas, laisser l'analyse générique
    # totaliser les colonnes au lieu de conclure à tort qu'il n'y a aucun total.
    return totaux or None


def _compter_csv(chemin: Path) -> int:
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        return sum(1 for _ in csv.DictReader(fichier, delimiter=SEPARATEUR_CSV))


def _annee_comparaison(nom_feuille: str) -> int | None:
    if not nom_feuille.startswith("Compare_Montant_"):
        return None
    correspondance = re.search(r"_(2023|2024|2025)$", nom_feuille)
    return int(correspondance.group(1)) if correspondance else None


def _compter_lignes_annee(
    lignes: tuple[tuple[Cellule, ...], ...], annee: int
) -> int:
    """Compte les lignes source dont la première colonne porte l'exercice."""
    valeur_annee = Decimal(annee)
    texte_annee = str(annee)
    return sum(
        1
        for ligne in lignes
        if ligne
        and (
            ligne[0].nombre == valeur_annee
            or ligne[0].texte.strip() == texte_annee
        )
    )


def _reference_ods(fichier: str, feuille: str) -> str:
    return f"ods:{fichier}#{feuille}"


def _reference_csv(chemin: Path) -> str:
    return f"csv:{chemin}"


def _sources_declarees(
    fichier: Path,
    feuille: str,
    repertoire_staging: Path,
) -> tuple[str, ...]:
    """Retourne la filiation immédiate déclarée par les générateurs actifs."""
    nom_fichier = fichier.name
    if feuille.endswith("_0"):
        if feuille.startswith("ENTETES_TICKETS_"):
            boutique = feuille.removeprefix("ENTETES_TICKETS_").removesuffix("_0")
            return (_reference_csv(repertoire_staging / f"EJ_ENTETES_TICKETS_{boutique}.csv"),)
        if feuille.startswith("LIGNES_TICKETS_"):
            boutique = feuille.removeprefix("LIGNES_TICKETS_").removesuffix("_0")
            return (_reference_csv(repertoire_staging / f"EJ_LIGNES_TICKETS_{boutique}.csv"),)
        if feuille.startswith("Z1_SyntheseMois_TOUS_"):
            return (_reference_csv(repertoire_staging / f"{feuille.removesuffix('_0')}.csv"),)
        if feuille.startswith("Z2_TransactionsMois_TOUS_"):
            return (_reference_csv(repertoire_staging / f"{feuille.removesuffix('_0')}.csv"),)

    def meme_fichier(nom_feuille: str) -> tuple[str, ...]:
        return (_reference_ods(nom_fichier, nom_feuille),)

    if nom_fichier.startswith("TTS_EJ_ENTETES_TICKETS_"):
        boutique = nom_fichier.removeprefix("TTS_EJ_ENTETES_TICKETS_").removesuffix(".ods")
        base = f"ENTETES_TICKETS_{boutique}_0"
        tri = f"ENTETES_TICKETS_{boutique}_TriCrstNumInterne"
        coherence = f"ENTETES_TICKETS_{boutique}_CtrlCoherenceEntete"
        sequentialite = f"ENTETES_TICKETS_{boutique}_sequentialite"
        if feuille == tri:
            return meme_fichier(base)
        if feuille == coherence:
            return meme_fichier(tri)
        if feuille == sequentialite:
            return meme_fichier(coherence)
        if feuille in {"TD_OccurenceNumInterne", "TD_OccurenceNumTicket"}:
            return meme_fichier(sequentialite)
        if feuille == "DoublonNumInterne":
            return meme_fichier("TD_OccurenceNumInterne")
        if feuille == "DoublonNumTicket":
            return meme_fichier("TD_OccurenceNumTicket")
        if feuille.endswith("CplteAnneeMoisTotalHT"):
            return meme_fichier(tri)
        if feuille == "TD_TotalEnctTtc_ParAnneeMois":
            return meme_fichier(f"ENTETES_TICKETS_{boutique}_CplteAnneeMoisTotalHT")
        if feuille.startswith("enct_mensuels_"):
            return meme_fichier("TD_TotalEnctTtc_ParAnneeMois")
        if feuille == "TD_TotalHtTvaTtc_ParAnneeMois":
            return meme_fichier(f"ENTETES_TICKETS_{boutique}_CplteAnneeMoisTotalHT")
        if feuille.startswith("recettes_mensuelles_"):
            return meme_fichier("TD_TotalHtTvaTtc_ParAnneeMois")

    if nom_fichier.startswith("TTS_EJ_LIGNES_TICKETS_"):
        boutique = nom_fichier.removeprefix("TTS_EJ_LIGNES_TICKETS_").removesuffix(".ods")
        base = f"LIGNES_TICKETS_{boutique}_0"
        tri = f"LIGNES_TICKETS_{boutique}_TriCrstNumInterne"
        coherence = f"LIGNES_TICKETS_{boutique}_CtrlCoherenceLigne"
        if feuille == tri:
            return meme_fichier(base)
        if feuille == coherence:
            return meme_fichier(tri)
        if feuille in {"TD_TotalLignesParNumTicket", "TD_OccurenceLibelleArticle", "TD_OccurenceTxTvaArticle"}:
            return meme_fichier(coherence)
        if feuille == "CtrlCoherence_EnteteLigne":
            return meme_fichier("TD_TotalLignesParNumTicket")

    if "CplteAnneeMoisZ" in feuille:
        return meme_fichier(f"{feuille.removesuffix('_CplteAnneeMoisZ')}_0")
    if feuille.startswith("TD_OccurenceEfichierEmode") or feuille.startswith("TD_Z1_TotalMontant") or feuille.startswith("TD_TotalMontant_parMoisAnnee"):
        prefixe = "Z1_SyntheseMois_TOUS" if feuille.startswith("TD_Z1") or feuille.startswith("TD_Occurence") else "Z2_TransactionsMois_TOUS"
        parties = nom_fichier.removesuffix(".ods").split("_")
        annee, boutique = parties[-2:]
        return meme_fichier(f"{prefixe}_{annee}_{boutique}_CplteAnneeMoisZ")
    if feuille.startswith(("Z1_TotalMontantParMoisAnnee_", "Z2_TotalMontant_parMoisAnnee_")):
        parties = nom_fichier.removesuffix(".ods").split("_")
        annee, boutique = parties[-2:]
        source = (
            f"TD_Z1_TotalMontantParMoisAnnee_{annee}"
            if feuille.startswith("Z1_")
            else "TD_TotalMontant_parMoisAnnee_parNatureTransaction"
        )
        return meme_fichier(source)
    if feuille.startswith("Compare_Montant_"):
        # Les comparaisons inter-classeurs sont complétées ci-dessous.
        if "Z2_ModeZZ1vsModeZZ2" in feuille:
            parties = nom_fichier.removesuffix(".ods").split("_")
            annee, boutique = parties[-2:]
            return (
                _reference_ods(nom_fichier, f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZZ1"),
                _reference_ods(nom_fichier, f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZZ2"),
            )
        if "Z2Mode" in feuille:
            boutique, annee = feuille.split("_")[2], feuille.rsplit("_", 1)[1]
            mode = "ZZ1" if "Z2ModeZZ1" in feuille else "Z"
            return (
                _reference_ods(f"TTS_Z2_TransactionsMois_TOUS_{annee}_{boutique}.ods", f"Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_Mode{mode}"),
                _reference_ods(f"TTS_EJ_ENTETES_TICKETS_{boutique}.ods", f"enct_mensuels_{boutique}_232425"),
            )
        if "Z1Mode" in feuille:
            boutique, annee = feuille.split("_")[2], feuille.rsplit("_", 1)[1]
            mode = "ZZ1" if "Z1ModeZZ1" in feuille else "Z"
            return (
                _reference_ods(f"TTS_Z1_SyntheseMois_TOUS_{annee}_{boutique}.ods", f"Z1_TotalMontantParMoisAnnee_{annee}_Mode{mode}"),
                _reference_ods(f"TTS_EJ_ENTETES_TICKETS_{boutique}.ods", f"recettes_mensuelles_{boutique}_232425"),
            )
    if feuille == "recettes_mensuelles_tous_boutique_232425":
        return tuple(
            _reference_ods(f"TTS_EJ_ENTETES_TICKETS_{boutique}.ods", f"recettes_mensuelles_{boutique}_232425")
            for boutique in ("MASSENA", "MATURIN")
        )
    if feuille == "CompareCA_Gesco_CA3":
        return (_reference_ods("recettes_mensuelles_tous_boutique_232425.ods", "recettes_mensuelles_tous_boutique_232425"),)
    return ()


def _libelle_source(reference: str) -> str:
    if reference.startswith("csv:"):
        return reference.removeprefix("csv:")
    if reference.startswith("ods:"):
        fichier, feuille = reference.removeprefix("ods:").split("#", 1)
        return f"{fichier} / {feuille}"
    return reference


class JournalExecution:
    """Journal en mémoire des compteurs relevés à chaque étape du pipeline."""

    def __init__(self, repertoire_staging: Path) -> None:
        self.repertoire_staging = repertoire_staging
        self.mesures: dict[tuple[str, str], MesureFeuille] = {}
        self.compteurs_traitement: dict[tuple[str, str], CompteurTraitement] = {}

    def charger_compteurs_traitement(self, chemin: Path) -> None:
        """Charge les compteurs explicitement relevés par les générateurs."""
        if not chemin.is_file():
            return
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if not ligne:
                continue
            mesure = json.loads(ligne)
            cle = (str(mesure["fichier"]), str(mesure["feuille"]))
            self.compteurs_traitement[cle] = CompteurTraitement(
                lus=int(mesure["lus"]),
                selectionnes=int(mesure["selectionnes"]),
                source_metier=str(mesure["source_metier"]),
            )

    def capturer_etat(self, repertoire_classeurs: Path) -> dict[Path, str]:
        return {
            chemin: sha256(chemin.read_bytes()).hexdigest()
            for chemin in repertoire_classeurs.glob("*.ods")
        } if repertoire_classeurs.exists() else {}

    def collecter_etape(
        self,
        repertoire_classeurs: Path,
        etat_avant: dict[Path, str],
    ) -> None:
        """Mémorise les compteurs des classeurs créés ou modifiés par une étape."""
        etat_apres = self.capturer_etat(repertoire_classeurs)
        feuilles_a_mesurer: list[
            tuple[Path, str, tuple[tuple[Cellule, ...], ...], tuple[str, ...]]
        ] = []
        for fichier, empreinte in sorted(etat_apres.items()):
            if etat_avant.get(fichier) == empreinte:
                continue
            for nom_feuille, lignes in lire_feuilles_ods(fichier).items():
                sources = _sources_declarees(fichier, nom_feuille, self.repertoire_staging)
                feuilles_a_mesurer.append((fichier, nom_feuille, lignes, sources))

        # Certains traitements créent une source et sa feuille dérivée dans la
        # même étape. Les dépendances sont donc mémorisées dans leur ordre de
        # filiation, même si le nom du classeur de comparaison se trie avant sa
        # source.
        cles_en_attente = {
            (fichier.name, nom_feuille)
            for fichier, nom_feuille, _, _ in feuilles_a_mesurer
        }
        while feuilles_a_mesurer:
            index = next(
                (
                    position
                    for position, (_, _, _, sources) in enumerate(feuilles_a_mesurer)
                    if all(
                        not source.startswith("ods:")
                        or tuple(source.removeprefix("ods:").split("#", 1))
                        not in cles_en_attente
                        for source in sources
                    )
                ),
                0,
            )
            fichier, nom_feuille, lignes, sources = feuilles_a_mesurer.pop(index)
            cles_en_attente.remove((fichier.name, nom_feuille))
            analyse = analyser_feuille(lignes)
            lus_source = sum(self._compter_source(source) for source in sources)
            annee_comparaison = _annee_comparaison(nom_feuille)
            if annee_comparaison is not None:
                selectionnes_source = sum(
                    self._compter_source_pour_annee(
                        source,
                        annee_comparaison,
                        repertoire_classeurs,
                    )
                    for source in sources
                )
            else:
                selectionnes_source = (
                    analyse.lignes_ecrites
                    if nom_feuille.endswith("_0")
                    else lus_source
                )
            compteur_metier = self.compteurs_traitement.get(
                (fichier.name, nom_feuille)
            )
            lus = compteur_metier.lus if compteur_metier else lus_source
            selectionnes = (
                compteur_metier.selectionnes
                if compteur_metier
                else selectionnes_source
            )
            self.mesures[(fichier.name, nom_feuille)] = MesureFeuille(
                fichier=fichier,
                feuille=nom_feuille,
                sources=sources,
                lus=lus,
                selectionnes=selectionnes,
                ecrits=analyse.lignes_ecrites,
                portee_compteurs=(
                    "source métier/originelle"
                    if compteur_metier
                    else "source immédiate"
                ),
                source_metier=(
                    compteur_metier.source_metier if compteur_metier else None
                ),
            )

    def _compter_source(self, reference: str) -> int:
        if reference.startswith("csv:"):
            chemin = Path(reference.removeprefix("csv:"))
            return _compter_csv(chemin) if chemin.is_file() else 0
        if reference.startswith("ods:"):
            fichier, feuille = reference.removeprefix("ods:").split("#", 1)
            mesure = self.mesures.get((fichier, feuille))
            return mesure.ecrits if mesure is not None else 0
        return 0

    def _compter_source_pour_annee(
        self,
        reference: str,
        annee: int,
        repertoire_classeurs: Path,
    ) -> int:
        if not reference.startswith("ods:"):
            return 0
        fichier, feuille = reference.removeprefix("ods:").split("#", 1)
        chemin = repertoire_classeurs / fichier
        if not chemin.is_file():
            return 0
        lignes = lire_feuilles_ods(chemin).get(feuille, ())
        return _compter_lignes_annee(lignes, annee)

    def verifier_coherence_compteurs(self) -> None:
        """Vérifie la borne des lectures rattachées aux sources immédiates."""
        for mesure in self.mesures.values():
            if mesure.portee_compteurs != "source immédiate":
                continue
            maximum = sum(self._compter_source(source) for source in mesure.sources)
            if mesure.lus > maximum:
                raise RuntimeError(
                    "Compteur de lecture incohérent avec la source immédiate : "
                    f"{mesure.fichier.name} / {mesure.feuille} lit {mesure.lus} "
                    f"enregistrements pour {maximum} écrits par sa ou ses sources."
                )

    def ecrire_rapport(self, repertoire_sortie: Path, repertoire_classeurs: Path) -> Path:
        """Relit les livrables ODS, puis écrit le rapport texte demandé."""
        self.verifier_coherence_compteurs()
        lignes_rapport = ["RAPPORT D'EXÉCUTION", ""]
        for fichier in sorted(repertoire_classeurs.glob("*.ods")):
            for nom_feuille, lignes in lire_feuilles_ods(fichier).items():
                analyse = analyser_feuille(lignes)
                mesure = self.mesures.get((fichier.name, nom_feuille))
                sources = mesure.sources if mesure is not None else _sources_declarees(
                    fichier, nom_feuille, self.repertoire_staging
                )
                lus = mesure.lus if mesure is not None else 0
                selectionnes = mesure.selectionnes if mesure is not None else 0
                portee = (
                    mesure.portee_compteurs
                    if mesure is not None
                    else "source immédiate"
                )
                lignes_rapport.extend(
                    (
                        f"Fichier de sortie : {fichier.name}",
                        f"Onglet de sortie : {nom_feuille}",
                        "Source(s) immédiate(s) — fichier / onglet : " + (
                            "; ".join(_libelle_source(source) for source in sources)
                            if sources else "non documenté"
                        ),
                        f"Portée des compteurs lus/sélectionnés : {portee}",
                        *(
                            (
                                "Source métier/originelle des compteurs : "
                                + mesure.source_metier,
                            )
                            if mesure is not None and mesure.source_metier
                            else ()
                        ),
                        f"Enregistrements lus : {lus}",
                        f"Enregistrements sélectionnés : {selectionnes}",
                        f"Enregistrements écrits : {analyse.lignes_ecrites}",
                        "Totaux des champs numériques :",
                    )
                )
                if analyse.totaux_numeriques:
                    lignes_rapport.extend(
                        f"- {nom}: {_formater_nombre(total, monetaire=_est_montant(nom))}"
                        for nom, total in analyse.totaux_numeriques.items()
                    )
                else:
                    lignes_rapport.append("- aucun")
                lignes_rapport.append("")
        repertoire_sortie.mkdir(parents=True, exist_ok=True)
        destination = repertoire_sortie / "rapport-d-execution.txt"
        temporaire = destination.with_suffix(".tmp")
        temporaire.write_text("\n".join(lignes_rapport) + "\n", encoding="utf-8")
        temporaire.replace(destination)
        return destination


def enregistrer_compteur_traitement(
    chemin: Path | None,
    *,
    fichier: str,
    feuille: str,
    lus: int,
    selectionnes: int,
    source_metier: str,
) -> None:
    """Persiste un compteur relevé par un générateur PyUNO en cours d'étape."""
    if chemin is None:
        return
    evenement = {
        "fichier": fichier,
        "feuille": feuille,
        "lus": lus,
        "selectionnes": selectionnes,
        "source_metier": source_metier,
    }
    with chemin.open("a", encoding="utf-8") as fichier_mesures:
        fichier_mesures.write(json.dumps(evenement) + "\n")


def _formater_nombre(valeur: Decimal, *, monetaire: bool) -> str:
    if monetaire:
        arrondi = valeur.quantize(Decimal("0.01"))
        if arrondi == 0:
            arrondi = Decimal("0.00")
        return f"{arrondi:f}".replace(".", ",")
    if valeur == 0:
        return "0"
    texte = format(valeur.normalize(), "f")
    return texte.replace(".", ",")
