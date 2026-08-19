from enum import Enum
from pathlib import Path


BOUTIQUES = ["MASSENA", "MATURIN"]
ANNEES = [2023, 2024, 2025]
PREFIXES_FICHIERS_Z1 = ("Z001_", "Z101_", "Z201")
PREFIXES_FICHIERS_Z2 = ("Z002_", "Z102_", "Z202")

SEPARATEUR_TICKET = "1-----------------------"
SEPARATEUR_SIGNATURE = "2-----------------------"
SEPARATEUR_CSV = "|"

REPERTOIRE_SORTIE = Path("output")
CHEMIN_DB = Path(REPERTOIRE_SORTIE / "database" / "db.sqlite")
REPERTOIRE_SOURCE = Path("fichiers_sources")
LARGEUR_COLONNE_DEFAUT = 5000


class FeuilleEjEntetes(Enum):
    ENTETES = "ENTETES_TICKETS_{boutique}_0"
    TRI_NUM_INTERNE = "ENTETES_TICKETS_{boutique}_TriCrstNumInterne"
    CTRL_COHERENCE = "ENTETES_TICKETS_{boutique}_CtrlCoherenceEntete"
    SEQUENTIALITE = "ENTETES_TICKETS_{boutique}_sequentialite"
    TD_OCCURRENCE_NUM_INTERNE = "TD_OccurenceNumInterne"
    DOUBLON_NUM_INTERNE = "DoublonNumInterne"
    TD_OCCURRENCE_NUM_TICKET = "TD_OccurenceNumTicket"
    DOUBLON_NUM_TICKET = "DoublonNumTicket"
    CPLTE_ANNEE_MOIS = "ENTETES_TICKETS_{boutique}_CplteAnneeMoisTotalHT"
    TD_TOTAL_ENCT = "TD_TotalEnctTtc_ParAnneeMois"
    ENCT_MENSUELS = "enct_mensuels_{boutique}_232425"
    TD_TOTAL_HT_TVA_TTC = "TD_TotalHtTvaTtc_ParAnneeMois"
    RECETTES_MENSUELLES = "recettes_mensuelles_{boutique}_232425"

    def pour(self, boutique: str) -> str:
        return self.value.format(boutique=boutique)


class FeuilleEjTickets(Enum):
    TICKETS = "LIGNES_TICKETS_{boutique}_0"
    TRI_NUM_INTERNE = "LIGNES_TICKETS_{boutique}_TriCrstNumInterne"
    CTRL_COHERENCE = "LIGNES_TICKETS_{boutique}_CtrlCoherenceLigne"
    TD_TOTAL_LIGNES = "TD_TotalLignesParNumTicket"
    CONTROLE_COHERENCE = "CtrlCoherence_EnteteLigne"
    TD_OCCURENCE_ARTICLE = "TD_OccurenceLibelleArticle"
    TD_OCCURRENCE_TVA = "TD_OccurenceTxTvaArticle"

    def pour(self, boutique: str) -> str:
        return self.value.format(boutique=boutique)
