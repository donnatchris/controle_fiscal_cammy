from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from shared.rapport_execution import (
    Cellule,
    JournalExecution,
    _formater_nombre,
    analyser_feuille,
    enregistrer_compteur_traitement,
    lire_feuilles_ods,
)


def _ecrire_ods(chemin: Path) -> None:
    contenu = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body><office:spreadsheet>
    <table:table table:name="ENTETES_TICKETS_MASSENA_0">
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>E_NUM_TICKET</text:p></table:table-cell>
        <table:table-cell office:value-type="string"><text:p>E_TTC</text:p></table:table-cell>
      </table:table-row>
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>0001</text:p></table:table-cell>
        <table:table-cell office:value-type="float" office:value="10.5"><text:p>10,50</text:p></table:table-cell>
      </table:table-row>
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>0002</text:p></table:table-cell>
        <table:table-cell office:value-type="float" office:value="2"><text:p>2,00</text:p></table:table-cell>
      </table:table-row>
    </table:table>
    <table:table table:name="ENTETES_TICKETS_MASSENA_TriCrstNumInterne">
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>E_NUM_TICKET</text:p></table:table-cell>
        <table:table-cell office:value-type="string"><text:p>E_TTC</text:p></table:table-cell>
      </table:table-row>
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>0001</text:p></table:table-cell>
        <table:table-cell office:value-type="float" office:value="10.5"><text:p>10,50</text:p></table:table-cell>
      </table:table-row>
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>0002</text:p></table:table-cell>
        <table:table-cell office:value-type="float" office:value="2"><text:p>2,00</text:p></table:table-cell>
      </table:table-row>
    </table:table>
  </office:spreadsheet></office:body>
</office:document-content>"""
    with ZipFile(chemin, "w", ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", contenu)


def _ecrire_ods_valeurs_reelles(chemin: Path) -> None:
    contenu = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body><office:spreadsheet>
    <table:table table:name="SOURCE_EJ">
      <table:table-row>
        <table:table-cell office:value-type="string"><text:p>E_HT1</text:p></table:table-cell>
        <table:table-cell office:value-type="string"><text:p>AJ_TVA1_CALCULE</text:p></table:table-cell>
        <table:table-cell office:value-type="string"><text:p>D_TAUX_TVA</text:p></table:table-cell>
      </table:table-row>
      <table:table-row>
        <table:table-cell office:value-type="float" office:value="625407.76"><text:p>6254,08</text:p></table:table-cell>
        <table:table-cell office:value-type="float" office:value="125081.552"><text:p>1252,94</text:p></table:table-cell>
        <table:table-cell office:value-type="percentage" office:value="0.2"><text:p>20 %</text:p></table:table-cell>
      </table:table-row>
    </table:table>
    <table:table table:name="SOURCE_Z1">
      <table:table-row><table:table-cell office:value-type="string"><text:p>D_MONTANT</text:p></table:table-cell></table:table-row>
      <table:table-row><table:table-cell office:value-type="float" office:value="6419219"><text:p>64192,19</text:p></table:table-cell></table:table-row>
    </table:table>
    <table:table table:name="SOURCE_Z2">
      <table:table-row><table:table-cell office:value-type="string"><text:p>D_MONTANT</text:p></table:table-cell></table:table-row>
      <table:table-row><table:table-cell office:value-type="float" office:value="1605888"><text:p>16058,88</text:p></table:table-cell></table:table-row>
    </table:table>
  </office:spreadsheet></office:body>
</office:document-content>"""
    with ZipFile(chemin, "w", ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", contenu)


def _ecrire_ods_feuilles_texte(
    chemin: Path,
    feuilles: dict[str, tuple[tuple[str, ...], ...]],
) -> None:
    tables = []
    for nom, lignes in feuilles.items():
        lignes_xml = []
        for ligne in lignes:
            cellules = "".join(
                '<table:table-cell office:value-type="string">'
                f"<text:p>{valeur}</text:p></table:table-cell>"
                for valeur in ligne
            )
            lignes_xml.append(f"<table:table-row>{cellules}</table:table-row>")
        tables.append(
            f'<table:table table:name="{nom}">{"".join(lignes_xml)}</table:table>'
        )
    contenu = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
  <office:body><office:spreadsheet>""" + "".join(tables) + """
  </office:spreadsheet></office:body>
</office:document-content>"""
    with ZipFile(chemin, "w", ZIP_DEFLATED) as archive:
        archive.writestr("content.xml", contenu)


def test_rapport_conserve_les_mesures_collectees_pendant_etape_et_relit_ods(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "EJ_ENTETES_TICKETS_MASSENA.csv").write_text(
        "E_NUM_TICKET|E_TTC\n0001|10.50\n0002|2.00\n0003|99.00\n",
        encoding="utf-8",
    )
    classeurs = tmp_path / "libreoffice"
    classeurs.mkdir()
    _ecrire_ods(classeurs / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods")

    journal = JournalExecution(staging)
    journal.collecter_etape(classeurs, {})
    rapport = journal.ecrire_rapport(tmp_path / "output", classeurs)

    contenu = rapport.read_text(encoding="utf-8")
    assert "Fichier de sortie : TTS_EJ_ENTETES_TICKETS_MASSENA.ods" in contenu
    assert "Onglet de sortie : ENTETES_TICKETS_MASSENA_0" in contenu
    assert "Enregistrements lus : 3" in contenu
    assert "Enregistrements sélectionnés : 2" in contenu
    assert "Enregistrements écrits : 2" in contenu
    assert "- E_TTC: 12,50" in contenu
    assert "Onglet de sortie : ENTETES_TICKETS_MASSENA_TriCrstNumInterne" in contenu
    assert "Enregistrements lus : 2" in contenu


def test_rapport_totalise_les_valeurs_reelles_ods_sans_relire_le_texte_affiche(
    tmp_path: Path,
) -> None:
    classeurs = tmp_path / "libreoffice"
    classeurs.mkdir()
    ods = classeurs / "controle.ods"
    _ecrire_ods_valeurs_reelles(ods)

    feuilles = lire_feuilles_ods(ods)
    assert feuilles["SOURCE_EJ"][1][2].nombre == Decimal("0.2")
    assert analyser_feuille(feuilles["SOURCE_EJ"]).totaux_numeriques == {
        "E_HT1": Decimal("625407.76"),
        "AJ_TVA1_CALCULE": Decimal("125081.552"),
    }
    assert analyser_feuille(feuilles["SOURCE_Z1"]).totaux_numeriques[
        "D_MONTANT"
    ] == Decimal("6419219")
    assert analyser_feuille(feuilles["SOURCE_Z2"]).totaux_numeriques[
        "D_MONTANT"
    ] == Decimal("1605888")

    journal = JournalExecution(tmp_path / "staging")
    journal.collecter_etape(classeurs, {})
    rapport = journal.ecrire_rapport(tmp_path / "output", classeurs).read_text(
        encoding="utf-8"
    )
    assert "- E_HT1: 625407,76" in rapport
    assert "- AJ_TVA1_CALCULE: 125081,55" in rapport
    assert "- D_MONTANT: 6419219,00" in rapport
    assert "- D_MONTANT: 1605888,00" in rapport


def test_analyser_feuille_ignore_identifiants_et_reconstruit_entetes_z2_groupes() -> None:
    analyse = analyser_feuille(
        (
            (
                Cellule(""),
                Cellule(""),
                Cellule("CARTES"),
                Cellule(""),
                Cellule("CHEQUES"),
                Cellule(""),
            ),
            (
                Cellule("AJ_Année_Z"),
                Cellule("AJ_Mois_Z"),
                Cellule("D_QUANTITE"),
                Cellule("D_MONTANT"),
                Cellule("D_QUANTITE"),
                Cellule("D_MONTANT"),
            ),
            (
                Cellule("2024", Decimal("2024")),
                Cellule("2024-01"),
                Cellule("2", Decimal("2")),
                Cellule("10,5", Decimal("10.5")),
                Cellule("3", Decimal("3")),
                Cellule("4,25", Decimal("4.25")),
            ),
        )
    )

    assert analyse.lignes_ecrites == 1
    assert analyse.totaux_numeriques == {
        "CARTES / D_QUANTITE": Decimal("2"),
        "CARTES / D_MONTANT": Decimal("10.5"),
        "CHEQUES / D_QUANTITE": Decimal("3"),
        "CHEQUES / D_MONTANT": Decimal("4.25"),
    }


def test_sequentialite_conserve_la_premiere_ligne_sans_trou_precedent() -> None:
    analyse = analyser_feuille(
        (
            (
                Cellule("nomfichier"),
                Cellule("E_NUM_INTERNE"),
                Cellule("E_NUM_TICKET"),
                Cellule("E_DATE_TICKET"),
                Cellule("E_HEURE_TICKET"),
                Cellule("AJ_TROU_NUM_TICKET"),
            ),
            (
                Cellule("EJ310123.TXT"),
                Cellule("004517"),
                Cellule("003562"),
                Cellule("2023-01-02"),
                Cellule("11:25"),
                Cellule(""),
            ),
            (
                Cellule("EJ310123.TXT"),
                Cellule("004518"),
                Cellule("003563"),
                Cellule("2023-01-02"),
                Cellule("12:34"),
                Cellule("1", Decimal("1")),
            ),
        )
    )
    assert analyse.lignes_ecrites == 2


@pytest.mark.parametrize("famille", ("Z1", "Z2"))
@pytest.mark.parametrize(("annee", "mois_retenus"), ((2023, 12), (2024, 12), (2025, 8)))
def test_comparaison_annuelle_lit_toutes_les_sources_et_selectionne_exercice(
    tmp_path: Path,
    famille: str,
    annee: int,
    mois_retenus: int,
) -> None:
    classeurs = tmp_path / "libreoffice"
    classeurs.mkdir()
    if famille == "Z1":
        nom_source = f"TTS_Z1_SyntheseMois_TOUS_{annee}_MASSENA.ods"
        feuille_source = f"Z1_TotalMontantParMoisAnnee_{annee}_ModeZZ1"
        feuille_ej = "recettes_mensuelles_MASSENA_232425"
    else:
        nom_source = f"TTS_Z2_TransactionsMois_TOUS_{annee}_MASSENA.ods"
        feuille_source = (
            "Z2_TotalMontant_parMoisAnnee_parNatureTransaction_"
            f"{annee}_ModeZZ1"
        )
        feuille_ej = "enct_mensuels_MASSENA_232425"
    lignes_source = (
        (("AJ_Année_Z", "AJ_Mois_Z"),)
        + tuple(
            (str(annee), f"{annee}-{mois:02d}")
            for mois in range(1, mois_retenus + 1)
        )
    )
    _ecrire_ods_feuilles_texte(
        classeurs / nom_source,
        {feuille_source: lignes_source},
    )

    lignes_ej = (("AJ_ANNEE", "AJ_MOIS"),) + tuple(
        (str(exercice), f"{exercice}-{mois:02d}")
        for exercice, nombre_mois in ((2023, 12), (2024, 12), (2025, 8))
        for mois in range(1, nombre_mois + 1)
    )
    _ecrire_ods_feuilles_texte(
        classeurs / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        {feuille_ej: lignes_ej},
    )

    feuille_comparaison = (
        f"Compare_Montant_MASSENA_{famille}ModeZZ1vsEJ_{annee}"
    )
    lignes_comparaison = (("AJ_Année_Z", "AJ_Mois_Z"),) + tuple(
        (str(annee), f"{annee}-{mois:02d}")
        for mois in range(1, mois_retenus + 1)
    )
    _ecrire_ods_feuilles_texte(
        classeurs / f"{feuille_comparaison}.ods",
        {feuille_comparaison: lignes_comparaison},
    )

    journal = JournalExecution(tmp_path / "staging")
    journal.collecter_etape(classeurs, {})
    mesure = journal.mesures[(f"{feuille_comparaison}.ods", feuille_comparaison)]
    assert mesure.lus == mois_retenus + 32
    assert mesure.selectionnes == mois_retenus * 2


def test_compteur_releve_pendant_traitement_prime_le_nombre_de_groupes_ecrits(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "EJ_ENTETES_TICKETS_MASSENA.csv").write_text(
        "E_NUM_TICKET|E_TTC\n0001|10.50\n",
        encoding="utf-8",
    )
    classeurs = tmp_path / "libreoffice"
    classeurs.mkdir()
    _ecrire_ods(classeurs / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods")
    journal = JournalExecution(staging)
    mesures = tmp_path / "mesures.jsonl"
    enregistrer_compteur_traitement(
        mesures,
        fichier="TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        feuille="ENTETES_TICKETS_MASSENA_0",
        lus=12,
        selectionnes=7,
        source_metier="source.csv",
    )

    journal.charger_compteurs_traitement(mesures)
    journal.collecter_etape(classeurs, {})

    mesure = journal.mesures[(
        "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        "ENTETES_TICKETS_MASSENA_0",
    )]
    assert (mesure.lus, mesure.selectionnes) == (12, 7)
    assert mesure.portee_compteurs == "source métier/originelle"
    assert mesure.source_metier == "source.csv"
    contenu = journal.ecrire_rapport(tmp_path / "output", classeurs).read_text(
        encoding="utf-8"
    )
    assert (
        "Portée des compteurs lus/sélectionnés : source métier/originelle"
        in contenu
    )
    assert "Source métier/originelle des compteurs : source.csv" in contenu


def test_analyser_feuille_reintegre_d_correction_comme_montant() -> None:
    analyse = analyser_feuille(
        (
            (Cellule("D_CORRECTION"), Cellule("D_TAUX_TVA_ARTICLE")),
            (
                Cellule("-12,5", Decimal("-12.5")),
                Cellule("20", Decimal("20")),
            ),
        )
    )
    assert analyse.totaux_numeriques == {"D_CORRECTION": Decimal("-12.5")}


def test_analyser_tcd_z1_totalise_toutes_les_designations_monetaires() -> None:
    analyse = analyser_feuille(
        (
            (Cellule("Somme - D_MONTANT"), Cellule(""), Cellule("D_DESIGNATION")),
            (
                Cellule("AJ_Année_Z"),
                Cellule("AJ_Mois_Z"),
                Cellule("CA BRUT"),
                Cellule("CA NET"),
                Cellule("CB.TIROIR"),
                Cellule("HORS TAXE 1"),
                Cellule("TVA 1"),
            ),
            (
                Cellule("2023", Decimal("2023")),
                Cellule("2023-01"),
                Cellule("100", Decimal("100")),
                Cellule("90", Decimal("90")),
                Cellule("70", Decimal("70")),
                Cellule("75", Decimal("75")),
                Cellule("15", Decimal("15")),
            ),
        )
    )
    assert set(analyse.totaux_numeriques) == {
        "D_DESIGNATION / CA BRUT",
        "D_DESIGNATION / CA NET",
        "D_DESIGNATION / CB.TIROIR",
        "D_DESIGNATION / HORS TAXE 1",
        "D_DESIGNATION / TVA 1",
    }


def test_analyser_tcd_z2_principal_totalise_quantites_et_montants_par_nature() -> None:
    analyse = analyser_feuille(
        (
            (
                Cellule("AJ_Année_Z"),
                Cellule("AJ_Mois_Z"),
                Cellule("Data"),
                Cellule("CARTES"),
                Cellule("CORRECTION"),
            ),
            (
                Cellule("2023", Decimal("2023")),
                Cellule("2023-01"),
                Cellule("Somme - D_QUANTITE"),
                Cellule("2", Decimal("2")),
                Cellule("1", Decimal("1")),
            ),
            (
                Cellule(""),
                Cellule(""),
                Cellule("Somme - D_MONTANT"),
                Cellule("20", Decimal("20")),
                Cellule("-5", Decimal("-5")),
            ),
        )
    )
    assert analyse.totaux_numeriques == {
        "CARTES / D_QUANTITE": Decimal("2"),
        "CORRECTION / D_QUANTITE": Decimal("1"),
        "CARTES / D_MONTANT": Decimal("20"),
        "CORRECTION / D_MONTANT": Decimal("-5"),
    }


@pytest.mark.parametrize(
    ("entetes", "valeurs", "attendus"),
    (
        (
            ("AJ_ANNEE", "AJ_MOIS", "Somme - E_TTC", "Somme - E_MDP_CB"),
            ("2023", "2023-01", "76369.8", "15385"),
            {"Data / Somme - E_TTC": Decimal("76369.8"),
             "Data / Somme - E_MDP_CB": Decimal("15385")},
        ),
        (
            ("AJ_ANNEE", "AJ_MOIS", "Somme - AJ_TOTAL_HT", "Somme - AJ_TOTAL_TVA_20"),
            ("2023", "2023-01", "63641.51", "12728.29"),
            {"Data / Somme - AJ_TOTAL_HT": Decimal("63641.51"),
             "Data / Somme - AJ_TOTAL_TVA_20": Decimal("12728.29")},
        ),
        (
            ("E_NUM_TICKET", "E_TTC", "Compter - D_LIBELLE_ARTICLE", "Somme - D_MONTANT_ARTICLE", "Somme - D_CORRECTION"),
            ("003562", "299", "1", "299", "-5"),
            {"E_TTC": Decimal("299"),
             "Data / Compter - D_LIBELLE_ARTICLE": Decimal("1"),
             "Data / Somme - D_MONTANT_ARTICLE": Decimal("299"),
             "Data / Somme - D_CORRECTION": Decimal("-5")},
        ),
    ),
)
def test_tcd_data_en_colonnes_remontent_leurs_totaux_numeriques(
    entetes: tuple[str, ...],
    valeurs: tuple[str, ...],
    attendus: dict[str, Decimal],
) -> None:
    analyse = analyser_feuille(
        (
            tuple(Cellule("Data") if index == 2 else Cellule("") for index in range(len(entetes))),
            tuple(Cellule(entete) for entete in entetes),
            tuple(
                Cellule(valeur, Decimal(valeur)) if index >= 2 or entete == "E_TTC" else Cellule(valeur)
                for index, (entete, valeur) in enumerate(zip(entetes, valeurs, strict=True))
            ),
        )
    )
    assert analyse.totaux_numeriques == attendus


def test_tcd_occurrences_ne_compte_pas_total_general_comme_enregistrement() -> None:
    analyse = analyser_feuille(
        (
            (Cellule("E_NUM_INTERNE"), Cellule("Compter - E_NUM_INTERNE")),
            (Cellule("004517"), Cellule("1", Decimal("1"))),
            (Cellule("004518"), Cellule("1", Decimal("1"))),
            (Cellule("Total général"), Cellule("2", Decimal("2"))),
        )
    )
    assert analyse.lignes_ecrites == 2
    assert analyse.totaux_numeriques == {
        "Compter - E_NUM_INTERNE": Decimal("2")
    }


def test_formater_nombre_normalise_zero_negatif() -> None:
    assert _formater_nombre(Decimal("-0.004"), monetaire=True) == "0,00"
    assert _formater_nombre(Decimal("-0"), monetaire=False) == "0"


def test_coherence_refuse_plus_de_lus_que_decrits_source_immediate(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "EJ_ENTETES_TICKETS_MASSENA.csv").write_text(
        "E_NUM_TICKET|E_TTC\n0001|10.50\n0002|2.00\n",
        encoding="utf-8",
    )
    classeurs = tmp_path / "libreoffice"
    classeurs.mkdir()
    _ecrire_ods(classeurs / "TTS_EJ_ENTETES_TICKETS_MASSENA.ods")
    journal = JournalExecution(staging)
    journal.collecter_etape(classeurs, {})
    cle = (
        "TTS_EJ_ENTETES_TICKETS_MASSENA.ods",
        "ENTETES_TICKETS_MASSENA_TriCrstNumInterne",
    )
    journal.mesures[cle] = replace(journal.mesures[cle], lus=3)

    with pytest.raises(RuntimeError, match="source immédiate"):
        journal.verifier_coherence_compteurs()
