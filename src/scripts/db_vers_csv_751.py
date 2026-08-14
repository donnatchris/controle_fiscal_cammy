"""Prépare, depuis SQLite, les CSV contractuels et les contrôles du dossier 751."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from shared.constantes import CHEMIN_DB


BOUTIQUES = ("MASSENA", "MATURIN")
ANNEES = (2023, 2024, 2025)
MOIS_PAR_ANNEE = {2023: 12, 2024: 12, 2025: 8}
TOLERANCE = Decimal("0.02")
COLONNES_EJ = [
    "nomfichier", "E_NUM_INTERNE", "E_NUM_TICKET", "E_DATE_TICKET", "E_HEURE_TICKET",
    "E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_TVA1", "E_TVA2", "E_TVA3", "E_TVA4",
    "E_HT_NON_TAXABLE", "E_TTC", "E_MDP_CB", "E_MDP_ESPECES", "E_MDP_CHEQUES",
]
COLONNES_LIGNES = COLONNES_EJ + [
    "D_QUANTITE_ARTICLE", "D_LIBELLE_ARTICLE", "D_TAUX_TVA_ARTICLE",
    "D_MONTANT_ARTICLE", "D_CORRECTION", "D_AUTRE_INFO",
]
COLONNES_Z = [
    "nomfichier", "E_MODELE", "E_MACHINE", "E_RAPPORT", "E_FICHIER", "E_MODE",
    "E_COMPTEUR_Z", "E_DATE", "E_HEURE", "D_ENREGISTREMENT", "D_DESIGNATION",
    "D_QUANTITE", "D_MONTANT",
]
CHAMPS_MONETAIRES_EJ = {
    "E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_TVA1", "E_TVA2", "E_TVA3", "E_TVA4",
    "E_HT_NON_TAXABLE", "E_TTC", "E_MDP_CB", "E_MDP_ESPECES", "E_MDP_CHEQUES",
    "D_MONTANT_ARTICLE", "D_CORRECTION",
}
PATTERN_PERIODE = re.compile(r"(?:^|_)(0[1-9]|1[0-2])(20\d{2})(?=_|\.|$)")


def decimal(value: object | None) -> Decimal:
    return Decimal(str(value)) if value not in (None, "") else Decimal("0")


def format_decimal(value: object | None) -> str:
    return "" if value in (None, "") else format(decimal(value), ".2f")


def periodes_fichier(nom_fichier: str) -> list[str]:
    return list(dict.fromkeys(f"{annee}-{mois}" for mois, annee in PATTERN_PERIODE.findall(nom_fichier)))


def ecrire_csv(chemin: Path, colonnes: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as fichier:
        writer = csv.DictWriter(fichier, fieldnames=colonnes, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({colonne: "" if row.get(colonne) is None else row.get(colonne) for colonne in colonnes})


def rows_dict(connection: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict[str, object]]:
    return [dict(row) for row in connection.execute(query, params)]


def normaliser_ej(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        row["E_DATE_TICKET"] = str(row["E_DATE_TICKET"]).replace("-", "")
        for champ in CHAMPS_MONETAIRES_EJ:
            if champ in row:
                row[champ] = format_decimal(row[champ])
    return rows


def charger_tickets(connection: sqlite3.Connection) -> list[dict[str, object]]:
    return rows_dict(
        connection,
        """
        SELECT t.*, t.type AS MARQUEUR_SOURCE
        FROM tickets t
        WHERE t.type IN ('REG', '_R_F')
          AND NULLIF(TRIM(t.E_NUM_TICKET), '') IS NOT NULL
        ORDER BY t.boutique, t.E_DATE_TICKET, t.E_HEURE_TICKET, t.E_NUM_INTERNE
        """,
    )


def exporter_ej(connection: sqlite3.Connection, staging: Path) -> dict[str, int]:
    compteurs: dict[str, int] = {}
    for boutique in BOUTIQUES:
        entetes = rows_dict(
            connection,
            """
            SELECT nomFichier AS nomfichier, E_NUM_INTERNE, E_NUM_TICKET, E_DATE_TICKET,
                   E_HEURE_TICKET, E_HT1, E_HT2, E_HT3, E_HT4, E_TVA1, E_TVA2,
                   E_TVA3, E_TVA4, E_HT_NON_TAXABLE, E_TTC, E_MDP_CB,
                   E_MDP_ESPECES, E_MDP_CHEQUES
            FROM tickets
            WHERE boutique = ? AND type IN ('REG', '_R_F')
              AND NULLIF(TRIM(E_NUM_TICKET), '') IS NOT NULL
            ORDER BY E_DATE_TICKET, E_HEURE_TICKET, E_NUM_INTERNE
            """,
            (boutique,),
        )
        lignes = rows_dict(
            connection,
            """
            SELECT t.nomFichier AS nomfichier, t.E_NUM_INTERNE, t.E_NUM_TICKET,
                   t.E_DATE_TICKET, t.E_HEURE_TICKET, t.E_HT1, t.E_HT2, t.E_HT3,
                   t.E_HT4, t.E_TVA1, t.E_TVA2, t.E_TVA3, t.E_TVA4,
                   t.E_HT_NON_TAXABLE, t.E_TTC, t.E_MDP_CB, t.E_MDP_ESPECES,
                   t.E_MDP_CHEQUES, l.D_QUANTITE_ARTICLE, l.D_LIBELLE_ARTICLE,
                   l.D_TAUX_TVA_ARTICLE, l.D_MONTANT_ARTICLE, l.D_CORRECTION,
                   l.D_AUTRE_INFO
            FROM lignes_ticket l JOIN tickets t ON t.id = l.ticket_id
            WHERE t.boutique = ? AND t.type IN ('REG', '_R_F')
              AND NULLIF(TRIM(t.E_NUM_TICKET), '') IS NOT NULL
            ORDER BY t.E_DATE_TICKET, t.E_HEURE_TICKET, t.E_NUM_INTERNE, l.id
            """,
            (boutique,),
        )
        normaliser_ej(entetes)
        normaliser_ej(lignes)
        ecrire_csv(staging / f"EJ_ENTETES_TICKETS_{boutique}.csv", COLONNES_EJ, entetes)
        ecrire_csv(staging / f"EJ_LIGNES_TICKETS_{boutique}.csv", COLONNES_LIGNES, lignes)
        compteurs[f"entetes_{boutique}"] = len(entetes)
        compteurs[f"lignes_{boutique}"] = len(lignes)
    return compteurs


def charger_z(connection: sqlite3.Connection, niveau: int) -> list[dict[str, object]]:
    return rows_dict(
        connection,
        f"""
        SELECT e.nom_fichier AS nomfichier, e.boutique, e.E_MODELE, e.E_MACHINE,
               e.E_RAPPORT, e.E_FICHIER, e.E_MODE, e.E_COMPTEUR_Z, e.E_DATE,
               e.E_HEURE, l.D_ENREGISTREMENT, l.D_DESIGNATION, l.D_QUANTITE,
               l.D_MONTANT
        FROM z{niveau}_lignes l
        JOIN z{niveau}_entetes e ON e.id = l.z{niveau}_entete_id
        ORDER BY e.boutique, e.nom_fichier, l.id
        """,
    )


def exporter_z(connection: sqlite3.Connection, staging: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    jeux = {1: charger_z(connection, 1), 2: charger_z(connection, 2)}
    for niveau, rows in jeux.items():
        for row in rows:
            row["D_QUANTITE"] = format_decimal(row["D_QUANTITE"])
            row["D_MONTANT"] = format_decimal(row["D_MONTANT"])
        for boutique in BOUTIQUES:
            for annee in ANNEES:
                selection = [
                    row for row in rows
                    if row["boutique"] == boutique
                    and periodes_fichier(str(row["nomfichier"]))
                    and periodes_fichier(str(row["nomfichier"]))[0].startswith(str(annee))
                ]
                prefixe = "Z1_SyntheseMois_TOUS" if niveau == 1 else "Z2_TransactionsMois_TOUS"
                ecrire_csv(staging / f"{prefixe}_{annee}_{boutique}.csv", COLONNES_Z, selection)
    return jeux[1], jeux[2]


def groupe_clotures(rows: list[dict[str, object]], regles: dict) -> dict[tuple[str, str, str, str], list[dict[str, object]]]:
    groupes: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        periodes = periodes_fichier(str(row["nomfichier"]))
        if not periodes:
            continue
        annee = periodes[0][:4]
        if row["E_MODE"] != regles[row["boutique"]][annee]["mode_retenu"]:
            continue
        cle = (str(row["boutique"]), str(row["E_MODE"]), str(row["E_COMPTEUR_Z"]), "|".join(periodes))
        groupes[cle].append(row)
    return groupes


def somme(rows: Iterable[Mapping[str, object]], champ: str) -> Decimal:
    return sum((decimal(row.get(champ)) for row in rows), start=Decimal("0"))


def somme_z(rows: list[dict[str, object]], designation: str) -> Decimal:
    return somme((row for row in rows if row["D_DESIGNATION"] == designation), "D_MONTANT")


def montant_ticket(ticket: Mapping[str, object], champs: Sequence[str]) -> Decimal:
    return sum((decimal(ticket.get(champ)) for champ in champs), start=Decimal("0"))


def rapprocher(
    tickets: list[dict[str, object]],
    z1: list[dict[str, object]],
    z2: list[dict[str, object]],
    regles: dict,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    z1_groupes = groupe_clotures(z1, regles)
    z2_groupes = groupe_clotures(z2, regles)
    rapprochements: list[dict[str, object]] = []
    couverture: list[dict[str, object]] = []

    for boutique in BOUTIQUES:
        clotures = []
        for cle, lignes_z1 in z1_groupes.items():
            if cle[0] != boutique:
                continue
            premiere = lignes_z1[0]
            clotures.append((
                datetime.fromisoformat(f"{premiere['E_DATE']}T{str(premiere['E_HEURE'])[:5]}"),
                cle,
                lignes_z1,
                z2_groupes.get(cle, []),
            ))
        clotures.sort(key=lambda item: (item[1][3].split("|")[-1], item[0]))

        for annee in ANNEES:
            for mois in range(1, MOIS_PAR_ANNEE[annee] + 1):
                periode = f"{annee}-{mois:02d}"
                candidates = [item for item in clotures if periode in item[1][3].split("|")]
                couverture.append({
                    "BOUTIQUE": boutique,
                    "PERIODE": periode,
                    "NB_CLOTURES_ETIQUETEES": len(candidates),
                    "CLOTURES": " ; ".join(f"{item[1][3]}:{item[1][2]}:{item[0].isoformat(' ')}" for item in candidates),
                    "STATUT": "CLOTURE_PRESENTE" if len(candidates) == 1 else "PAS_DE_CLOTURE" if not candidates else "AMBIGUITE",
                    "NOTE": "Période issue du nom du fichier ; aucune clôture n'est inventée.",
                })

        precedente: datetime | None = None
        for fermeture, cle, lignes_z1, lignes_z2 in clotures:
            periodes = cle[3].split("|")
            debut = precedente or datetime.fromisoformat(f"{periodes[0]}-01T00:00:00")
            selection = []
            for ticket in tickets:
                if ticket["boutique"] != boutique:
                    continue
                horodatage = datetime.fromisoformat(f"{ticket['E_DATE_TICKET']}T{str(ticket['E_HEURE_TICKET'])[:5]}")
                if (horodatage > debut if precedente else horodatage >= debut) and horodatage <= fermeture:
                    selection.append(ticket)

            valeurs = {
                "CA_TTC_Z1": somme_z(lignes_z1, "CA BRUT"),
                "CA_TTC_EJ": somme(selection, "E_TTC"),
                "HT_Z1": somme_z(lignes_z1, "HORS TAXE 1"),
                "HT_EJ": sum((montant_ticket(t, ["E_HT1", "E_HT2", "E_HT3", "E_HT4", "E_HT_NON_TAXABLE"]) for t in selection), start=Decimal("0")),
                "TVA_Z1": somme_z(lignes_z1, "TVA 1"),
                "TVA_EJ": sum((montant_ticket(t, ["E_TVA1", "E_TVA2", "E_TVA3", "E_TVA4"]) for t in selection), start=Decimal("0")),
                "CARTES_Z2": somme_z(lignes_z2, "CARTES"),
                "CARTES_EJ": somme(selection, "E_MDP_CB"),
                "CHEQUES_Z2": somme_z(lignes_z2, "CHEQUES"),
                "CHEQUES_EJ": somme(selection, "E_MDP_CHEQUES"),
                "ESPECES_Z2": somme_z(lignes_z2, "ESPECES"),
                "ESPECES_EJ": somme(selection, "E_MDP_ESPECES"),
            }
            ecarts = {
                "ECART_CA_TTC": valeurs["CA_TTC_Z1"] - valeurs["CA_TTC_EJ"],
                "ECART_HT": valeurs["HT_Z1"] - valeurs["HT_EJ"],
                "ECART_TVA": valeurs["TVA_Z1"] - valeurs["TVA_EJ"],
                "ECART_CARTES": valeurs["CARTES_Z2"] - valeurs["CARTES_EJ"],
                "ECART_CHEQUES": valeurs["CHEQUES_Z2"] - valeurs["CHEQUES_EJ"],
                "ECART_ESPECES": valeurs["ESPECES_Z2"] - valeurs["ESPECES_EJ"],
            }
            retours = [ticket for ticket in selection if ticket["type"] == "_R_F"]
            conforme = bool(lignes_z2) and all(abs(ecart) <= TOLERANCE for ecart in ecarts.values())
            rapprochements.append({
                "BOUTIQUE": boutique, "EXERCICE": periodes[0][:4],
                "PERIODE_DEBUT": periodes[0], "PERIODE_FIN": periodes[-1],
                "PERIODES_FICHIER": cle[3], "TYPE_PERIODE": "MULTI_MOIS" if len(periodes) > 1 else "MOIS_SIMPLE",
                "MODE_RETENU": cle[1], "COMPTEUR_Z": cle[2],
                "DATE_CLOTURE_PRECEDENTE": precedente.date().isoformat() if precedente else "DEBUT_PERIODE",
                "HEURE_CLOTURE_PRECEDENTE": precedente.strftime("%H:%M") if precedente else "",
                "DATE_CLOTURE_Z": fermeture.date().isoformat(), "HEURE_CLOTURE_Z": fermeture.strftime("%H:%M"),
                "REGLE_RATTACHEMENT": "DOSSIER_NOM_FICHIER_PUIS_INTERVALLE_ENTRE_CLOTURES",
                "NB_TICKETS_EJ": len(selection), "NB_RETOURS_CLE_EJ": len(retours),
                "MONTANT_RETOURS_CLE_EJ": somme(retours, "E_TTC"), "RETOUR_CLE_Z1": somme_z(lignes_z1, "RETOUR CLE"),
                **valeurs, **ecarts, "NB_FICHIERS_Z1": 1, "NB_FICHIERS_Z2": 1 if lignes_z2 else 0,
                "STATUT": "OK" if conforme else "BLOQUANT",
                "ANALYSE": "CONCORDE_ENTRE_CLOTURES" if conforme else "ECART_NON_EXPLIQUE",
                "NOTE": "Retours _R_F signés négativement ; période multi-mois conservée." if len(periodes) > 1 else "Retours _R_F signés négativement.",
                "SOURCES_Z1": str(lignes_z1[0]["nomfichier"]),
                "SOURCES_Z2": str(lignes_z2[0]["nomfichier"]) if lignes_z2 else "",
            })
            precedente = fermeture
    return rapprochements, couverture


def exporter_controles(
    connection: sqlite3.Connection,
    controle: Path,
    tickets: list[dict[str, object]],
    z1: list[dict[str, object]],
    z2: list[dict[str, object]],
    regles: dict,
) -> dict[str, object]:
    inventaire = rows_dict(connection, "SELECT type, COUNT(*) AS nombre FROM tickets GROUP BY type ORDER BY type")
    exclus = rows_dict(
        connection,
        """
        SELECT type, COUNT(*) AS nombre
        FROM tickets
        WHERE NOT (type IN ('REG', '_R_F') AND NULLIF(TRIM(E_NUM_TICKET), '') IS NOT NULL)
        GROUP BY type ORDER BY type
        """,
    )
    for row in exclus:
        row["motif"] = (
            "Bloc administratif" if row["type"] in {"X", "XZ", "Z"}
            else "Événement sans E_NUM_TICKET" if row["type"] in {"REG", "_R_F"}
            else "Type non autorisé pour les ventes ; conservé en base"
        )
    ecrire_csv(controle / "INVENTAIRE_TYPES_BLOCS_EJ.csv", ["type", "nombre"], inventaire)
    ecrire_csv(controle / "BLOCS_EXCLUS_EXPORTS_VENTES.csv", ["type", "nombre", "motif"], exclus)

    rapprochements, couverture = rapprocher(tickets, z1, z2, regles)
    money_fields = [key for key in rapprochements[0] if key.startswith(("CA_", "HT_", "TVA_", "CARTES_", "CHEQUES_", "ESPECES_", "ECART_", "MONTANT_", "RETOUR_"))]
    for row in rapprochements:
        for champ in money_fields:
            row[champ] = format_decimal(row[champ])
    colonnes_rapprochement = list(rapprochements[0])
    ecrire_csv(controle / "RAPPROCHEMENT_PAR_CLOTURE_EJ_Z.csv", colonnes_rapprochement, rapprochements)
    ecrire_csv(controle / "CONTROLE_COUVERTURE_PERIODES_Z.csv", list(couverture[0]), couverture)

    non_conformes = [row for row in rapprochements if row["STATUT"] != "OK"]
    presents = sum(row["STATUT"] == "CLOTURE_PRESENTE" for row in couverture)
    absents = sum(row["STATUT"] == "PAS_DE_CLOTURE" for row in couverture)
    ambigus = sum(row["STATUT"] == "AMBIGUITE" for row in couverture)
    multi_mois = sum(len(periodes_fichier(str(row["nomfichier"]))) > 1 for row in {
        (row["boutique"], row["nomfichier"]): row for row in z1 + z2
    }.values())
    resume = {
        "blocs_lus": sum(int(row["nombre"]) for row in inventaire),
        "tickets_selectionnes_et_ecrits": len(tickets),
        "blocs_non_selectionnes": sum(int(row["nombre"]) for row in exclus),
        "inventaire_types": {str(row["type"]): int(row["nombre"]) for row in inventaire},
        "types_inconnus": sorted({str(row["type"]) for row in inventaire} - {"REG", "_R_F", "X", "XZ", "Z"}),
        "rapprochements_ok": len(rapprochements) - len(non_conformes),
        "rapprochements_total": len(rapprochements),
        "periodes_avec_cloture": presents,
        "periodes_sans_cloture": absents,
        "periodes_ambigues": ambigus,
        "fichiers_multi_mois_z1_z2": multi_mois,
        "statut": "CONFORME SUR LE PÉRIMÈTRE CAISSE - À COMPLÉTER" if not non_conformes and not ambigus else "ANOMALIES À ANALYSER",
        "elements_absents": ["FEC", "CA3", "justificatifs externes"],
    }
    if (len(rapprochements), presents, absents, ambigus, multi_mois) != (57, 60, 4, 0, 6):
        raise RuntimeError(f"Contrôles de périodes inattendus : {resume}")
    if non_conformes:
        raise RuntimeError(f"{len(non_conformes)} rapprochements EJ/Z non conformes")
    controle.mkdir(parents=True, exist_ok=True)
    (controle / "RESUME_EXPORT_751.json").write_text(
        json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lignes_rapport = [
        "# Rapport de contrôle des exports 751",
        "",
        f"Statut : **{resume['statut']}**",
        "",
        f"- Blocs EJ lus et conservés en base : {resume['blocs_lus']}",
        f"- Tickets de vente sélectionnés et écrits : {resume['tickets_selectionnes_et_ecrits']}",
        f"- Blocs non sélectionnés pour les ventes : {resume['blocs_non_selectionnes']}",
        f"- Rapprochements EJ/Z conformes : {resume['rapprochements_ok']}/{resume['rapprochements_total']}",
        f"- Périodes avec clôture / sans clôture / ambiguës : {presents} / {absents} / {ambigus}",
        f"- Fichiers Z1/Z2 multi-mois : {multi_mois}",
        "",
        "## Blocs exclus des classeurs de ventes",
        "",
        "| Type | Nombre | Motif |",
        "|---|---:|---|",
        *[f"| {row['type']} | {row['nombre']} | {row['motif']} |" for row in exclus],
        "",
        "Les types exclus ne sont pas qualifiés d’erreurs : ils restent intégralement conservés en base.",
        "`D_TAUX_TVA_ARTICLE` conserve les indicateurs source (`T1`, `T2`, etc.) ; le taux de 20 % n’est utilisé que dans la formule de contrôle de `E_HT1`.",
        "Les champs CA3 et FEC restent volontairement vides tant que les sources externes ne sont pas fournies.",
    ]
    (controle / "RAPPORT_CONTROLES_751.md").write_text(
        "\n".join(lignes_rapport) + "\n", encoding="utf-8"
    )
    return resume


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(CHEMIN_DB))
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--controle", type=Path, required=True)
    parser.add_argument("--regles", type=Path, default=Path("config/regles_modes_z.json"))
    args = parser.parse_args(argv)
    regles = json.loads(args.regles.read_text(encoding="utf-8"))

    with sqlite3.connect(args.base) as connection:
        connection.row_factory = sqlite3.Row
        compteurs = exporter_ej(connection, args.staging)
        tickets = charger_tickets(connection)
        z1, z2 = exporter_z(connection, args.staging)
        resume = exporter_controles(connection, args.controle, tickets, z1, z2, regles)

    attendu = {"entetes_MASSENA": 1_153, "entetes_MATURIN": 722, "lignes_MASSENA": 2_521, "lignes_MATURIN": 1_610}
    if compteurs != attendu:
        raise RuntimeError(f"Volumes EJ inattendus : attendu={attendu}, obtenu={compteurs}")
    print(json.dumps({"exports_ej": compteurs, "controle": resume}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
