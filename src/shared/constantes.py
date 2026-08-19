from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


BOUTIQUES = ["MASSENA", "MATURIN"]
ANNEES = [2023, 2024, 2025]
PREFIXES_FICHIERS_Z1 = ("Z001_", "Z101_", "Z201")
PREFIXES_FICHIERS_Z2 = ("Z002_", "Z102_", "Z202")

SEPARATEUR_TICKET = "1-----------------------"
SEPARATEUR_SIGNATURE = "2-----------------------"
SEPARATEUR_CSV = "|"

CHEMIN_DB = "database/db.sqlite"
REPERTOIRE_SORTIE = "output/"
REPERTOIRE_SOURCE = "fichiers_sources/"


ModeNomFeuille751 = Literal["nom_complet", "alias_court"]
NOM_COMPLET: ModeNomFeuille751 = "nom_complet"
ALIAS_COURT: ModeNomFeuille751 = "alias_court"


@dataclass(frozen=True)
class NomFeuille751:
    """Associe le nom contractuel d'une feuille à son alias physique court."""

    nom_complet: str
    alias_court: str
    boutiques: tuple[str, ...] = ()


@dataclass(frozen=True)
class DefinitionClasseur751:
    """Décrit une famille de classeurs et l'ordre contractuel de ses feuilles."""

    identifiant: str
    nom_fichier: str
    feuilles: tuple[NomFeuille751, ...]
    par_boutique: bool = False
    par_annee: bool = False


@dataclass(frozen=True)
class NomFeuilleResolue751:
    nom_complet: str
    alias_court: str

    def selon(self, mode: ModeNomFeuille751) -> str:
        if mode == NOM_COMPLET:
            return self.nom_complet
        if mode == ALIAS_COURT:
            return self.alias_court
        raise ValueError(f"Mode de nommage inconnu : {mode}")


@dataclass(frozen=True)
class ClasseurResolu751:
    identifiant: str
    nom_fichier: str
    feuilles: tuple[NomFeuilleResolue751, ...]

    def noms_feuilles(self, mode: ModeNomFeuille751) -> tuple[str, ...]:
        return tuple(feuille.selon(mode) for feuille in self.feuilles)


NOMS_CLASSEURS_751: Mapping[str, DefinitionClasseur751] = MappingProxyType({
    "ej_entetes": DefinitionClasseur751(
        identifiant="ej_entetes",
        nom_fichier="TTS_EJ_ENTETES_TICKETS_{boutique}.ods",
        par_boutique=True,
        feuilles=(
            NomFeuille751("ENTETES_TICKETS_{boutique}_0", "ENTETES_{boutique}_0"),
            NomFeuille751("ENTETES_TICKETS_{boutique}_TriCrstNumInterne", "Entetes_TriNumInterne"),
            NomFeuille751("ENTETES_TICKETS_{boutique}_CtrlCoherenceEntete", "Entetes_CtrlCoherence"),
            NomFeuille751("ENTETES_TICKETS_{boutique}_sequentialite", "Entetes_sequentialite"),
            NomFeuille751("TD_OccurenceNumInterne", "TD_OccurenceNumInterne"),
            NomFeuille751("DoublonNumInterne", "DoublonNumInterne"),
            NomFeuille751("TD_OccurenceNumTicket", "TD_OccurenceNumTicket"),
            NomFeuille751("DoublonNumTicket", "DoublonNumTicket"),
            NomFeuille751("ENTETES_TICKETS_{boutique}_CplteAnneeMoisTotalHT", "Entetes_CplteAnneeMois"),
            NomFeuille751("TD_TotalEnctTtc_ParAnneeMois", "TD_TotalEnctTTC"),
            NomFeuille751("enct_mensuels_{boutique}_232425", "enct_mensuels_{boutique}"),
            NomFeuille751("TD_TotalHtTvaTtc_ParAnneeMois", "TD_TotalHtTvaTtc"),
            NomFeuille751("recettes_mensuelles_{boutique}_232425", "recettes_mensuelles_{boutique}"),
        ),
    ),
    "ej_lignes": DefinitionClasseur751(
        identifiant="ej_lignes",
        nom_fichier="TTS_EJ_LIGNES_TICKETS_{boutique}.ods",
        par_boutique=True,
        feuilles=(
            NomFeuille751("LIGNES_TICKETS_{boutique}_0", "LIGNES_{boutique}_0"),
            NomFeuille751("LIGNES_TICKETS_{boutique}_TriCrstNumInterne", "Lignes_TriNumInterne"),
            NomFeuille751("LIGNES_TICKETS_{boutique}_CtrlCoherenceLigne", "Lignes_CtrlCoherence"),
            NomFeuille751("TD_TotalLignesParNumTicket", "TD_TotalLignesParTicket"),
            NomFeuille751("CtrlCoherence_EnteteLigne", "CtrlCoherence_EnteteLigne"),
            NomFeuille751("TD_OccurenceLibelleArticle", "TD_OccurenceLibelle"),
            NomFeuille751("TD_OccurenceTxTvaArticle", "TD_OccurenceTxTVA"),
        ),
    ),
    "z2": DefinitionClasseur751(
        identifiant="z2",
        nom_fichier="TTS_Z2_TransactionsMois_TOUS_{annee}_{boutique}.ods",
        par_boutique=True,
        par_annee=True,
        feuilles=(
            NomFeuille751("Z2_TransactionsMois_TOUS_{annee}_{boutique}_0", "Z2_{annee}_{boutique}_0"),
            NomFeuille751("Z2_TransactionsMois_TOUS_{annee}_{boutique}_CplteAnneeMoisZ", "Z2_CplteAnneeMois"),
            NomFeuille751("TD_TotalMontant_parMoisAnnee_parNatureTransaction", "TD_TotalNatureTransac"),
            NomFeuille751("Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZZ1", "Z2_Total_ModeZZ1"),
            NomFeuille751("Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZZ2", "Z2_Total_ModeZZ2"),
            NomFeuille751("Z2_TotalMontant_parMoisAnnee_parNatureTransaction_{annee}_ModeZ", "Z2_Total_ModeZ"),
            NomFeuille751("Compare_Montant_Massena_Z2_ModeZZ1vsModeZZ2_{annee}", "Compare_ZZ1_vs_ZZ2", ("MASSENA",)),
            NomFeuille751("Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_{annee}", "Compare_ZZ1_vs_EJ", ("MASSENA",)),
            NomFeuille751("Compare_Montant_MATURIN_Z2ModeZvsEJ_{annee}", "Compare_Z_vs_EJ", ("MATURIN",)),
        ),
    ),
    "z1": DefinitionClasseur751(
        identifiant="z1",
        nom_fichier="TTS_Z1_SyntheseMois_TOUS_{annee}_{boutique}.ods",
        par_boutique=True,
        par_annee=True,
        feuilles=(
            NomFeuille751("Z1_SyntheseMois_TOUS_{annee}_{boutique}_0", "Z1_{annee}_{boutique}_0"),
            NomFeuille751("Z1_SyntheseMois_TOUS_{annee}_{boutique}_CplteAnneeMoisZ", "Z1_CplteAnneeMois"),
            NomFeuille751("TD_OccurenceEfichierEmodeParMoisAnnee_{annee}", "TD_OccurenceFichMode"),
            NomFeuille751("TD_Z1_TotalMontantParMoisAnnee_{annee}", "TD_Z1_TotalMontant"),
            NomFeuille751("Z1_TotalMontantParMoisAnnee_{annee}_ModeZZ1", "Z1_Total_ModeZZ1"),
            NomFeuille751("Z1_TotalMontantParMoisAnnee_{annee}_ModeZZ2", "Z1_Total_ModeZZ2"),
            NomFeuille751("Z1_TotalMontantParMoisAnnee_{annee}_ModeZ", "Z1_Total_ModeZ"),
            NomFeuille751("Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_{annee}", "Compare_ZZ1_vs_EJ", ("MASSENA",)),
            NomFeuille751("Compare_Montant_MATURIN_Z1ModeZvsEJ_{annee}", "Compare_Z_vs_EJ", ("MATURIN",)),
        ),
    ),
    "recettes_toutes": DefinitionClasseur751(
        identifiant="recettes_toutes",
        nom_fichier="recettes_mensuelles_tous_boutique_232425.ods",
        feuilles=(NomFeuille751("recettes_mensuelles_tous_boutique_232425", "recettes_mensuelles_tous"),),
    ),
    "comparaison_ca3": DefinitionClasseur751(
        identifiant="comparaison_ca3",
        nom_fichier="CompareCA_Gesco_CA3.ods",
        feuilles=(NomFeuille751("CompareCA_Gesco_CA3", "CompareCA_Gesco_CA3"),),
    ),
})


def resoudre_classeur_751(
    identifiant: str,
    *,
    boutique: str | None = None,
    annee: int | None = None,
) -> ClasseurResolu751:
    """Résout les modèles d'une famille sans choisir le format de nom des feuilles."""

    try:
        definition = NOMS_CLASSEURS_751[identifiant]
    except KeyError as exc:
        raise ValueError(f"Famille de classeur inconnue : {identifiant}") from exc
    if definition.par_boutique:
        if boutique not in BOUTIQUES:
            raise ValueError(f"Boutique invalide pour {identifiant} : {boutique}")
    elif boutique is not None:
        raise ValueError(f"La famille {identifiant} n'accepte pas de boutique")
    if definition.par_annee:
        if annee not in ANNEES:
            raise ValueError(f"Année invalide pour {identifiant} : {annee}")
    elif annee is not None:
        raise ValueError(f"La famille {identifiant} n'accepte pas d'année")

    contexte = {"boutique": boutique or "", "annee": annee or ""}
    feuilles = tuple(
        NomFeuilleResolue751(
            nom_complet=feuille.nom_complet.format(**contexte),
            alias_court=feuille.alias_court.format(**contexte),
        )
        for feuille in definition.feuilles
        if not feuille.boutiques or boutique in feuille.boutiques
    )
    return ClasseurResolu751(
        identifiant=definition.identifiant,
        nom_fichier=definition.nom_fichier.format(**contexte),
        feuilles=feuilles,
    )


def iterer_classeurs_751() -> tuple[ClasseurResolu751, ...]:
    """Développe les six familles en 18 classeurs contractuels."""

    classeurs: list[ClasseurResolu751] = []
    for identifiant, definition in NOMS_CLASSEURS_751.items():
        boutiques = BOUTIQUES if definition.par_boutique else [None]
        annees = ANNEES if definition.par_annee else [None]
        for boutique in boutiques:
            for annee in annees:
                classeurs.append(
                    resoudre_classeur_751(
                        identifiant,
                        boutique=boutique,
                        annee=annee,
                    )
                )
    return tuple(classeurs)
