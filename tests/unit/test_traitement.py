from pathlib import Path

import pytest

import traitement


def test_executer_traitements_enchaine_reconstruction_csv_et_ods(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appels: list[tuple[str, list[str]]] = []
    sources = tmp_path / "sources"
    base = tmp_path / "database/db.sqlite"
    staging = tmp_path / "staging"
    libreoffice = tmp_path / "libreoffice"
    monkeypatch.setattr(
        traitement.reconstruire_base_751,
        "main",
        lambda arguments: appels.append(("reconstruction", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.db_vers_csv_751,
        "main",
        lambda arguments: appels.append(("csv", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.ods_ej_entetes,
        "main",
        lambda arguments: appels.append(("ods_entetes", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.ods_ej_tickets,
        "main",
        lambda arguments: appels.append(("ods_tickets", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.compare_1,
        "main",
        lambda arguments: appels.append(("ods_entetes_enrichi", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.compare_2,
        "main",
        lambda arguments: appels.append(("ods_entetes_recettes", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.ods_z1,
        "main",
        lambda arguments: appels.append(("ods_z1", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.ods_z2,
        "main",
        lambda arguments: appels.append(("ods_z2", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.recettes_mensuelles,
        "main",
        lambda arguments: appels.append(("recettes_mensuelles", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.compare_ca_gesco_ca3,
        "main",
        lambda arguments: appels.append(("compare_ca3", arguments)) or 0,
    )

    assert traitement.executer_traitements(
        chemin_repertoire=sources,
        chemin_base=base,
        repertoire_staging=staging,
        repertoire_libreoffice=libreoffice,
    ) is True
    assert appels == [
        ("reconstruction", [
            "--sources", str(sources), "--base", str(base),
            "--publier",
        ]),
        ("csv", [
            "--base", str(base), "--staging", str(staging),
        ]),
        ("ods_entetes", ["--staging", str(staging), "--sortie", str(libreoffice)]),
        ("ods_tickets", ["--staging", str(staging), "--sortie", str(libreoffice)]),
        ("ods_z2", ["--staging", str(staging), "--sortie", str(libreoffice)]),
        ("ods_entetes_enrichi", ["--sortie", str(libreoffice)]),
        ("ods_z1", ["--staging", str(staging), "--sortie", str(libreoffice)]),
        ("ods_entetes_recettes", ["--sortie", str(libreoffice)]),
        ("recettes_mensuelles", ["--sortie", str(libreoffice)]),
        ("compare_ca3", ["--sortie", str(libreoffice)]),
    ]
    assert staging.is_dir()
    assert libreoffice.is_dir()


def test_executer_traitements_sauvegarde_la_sortie_existante(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repertoire_sortie = tmp_path / "output"
    repertoire_sortie.mkdir()
    (repertoire_sortie / "ancien_livrable.txt").write_text("à conserver")

    for module in (
        traitement.reconstruire_base_751,
        traitement.db_vers_csv_751,
        traitement.ods_ej_entetes,
        traitement.ods_ej_tickets,
        traitement.ods_z1,
        traitement.ods_z2,
        traitement.compare_1,
        traitement.compare_2,
        traitement.recettes_mensuelles,
        traitement.compare_ca_gesco_ca3,
    ):
        monkeypatch.setattr(module, "main", lambda _: 0)

    assert traitement.executer_traitements(
        chemin_repertoire=tmp_path / "sources",
        chemin_base=repertoire_sortie / "database/db.sqlite",
        repertoire_staging=repertoire_sortie / "travaux_preliminaires",
        repertoire_libreoffice=repertoire_sortie / "libreoffice",
        repertoire_sortie=repertoire_sortie,
    ) is True

    assert repertoire_sortie.is_dir()
    assert (repertoire_sortie / "ancien_livrable.txt").read_text() == "à conserver"
    sauvegardes = list(repertoire_sortie.glob("sauvegarde_*"))
    assert len(sauvegardes) == 1
    assert (sauvegardes[0] / "ancien_livrable.txt").read_text() == "à conserver"


def test_executer_traitements_sarrete_si_reconstruction_echoue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(traitement.reconstruire_base_751, "main", lambda _: 1)
    monkeypatch.setattr(
        traitement.db_vers_csv_751,
        "main",
        lambda _: pytest.fail("Les CSV ne doivent pas être générés"),
    )
    monkeypatch.setattr(
        traitement.ods_ej_entetes,
        "main",
        lambda _: pytest.fail("Les ODS ne doivent pas être générés"),
    )
    monkeypatch.setattr(
        traitement.ods_ej_tickets,
        "main",
        lambda _: pytest.fail("Les ODS ne doivent pas être générés"),
    )
    monkeypatch.setattr(
        traitement.ods_z2,
        "main",
        lambda _: pytest.fail("Les ODS ne doivent pas être générés"),
    )
    monkeypatch.setattr(
        traitement.compare_1,
        "main",
        lambda _: pytest.fail("Les entêtes enrichies ne doivent pas être générées"),
    )

    assert traitement.executer_traitements(
        chemin_repertoire=tmp_path / "sources",
        chemin_base=tmp_path / "db.sqlite",
        repertoire_staging=tmp_path / "staging",
    ) is False


def test_main_utilise_les_repertoires_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    arguments: dict[str, object] = {}
    monkeypatch.setattr(
        traitement,
        "executer_traitements",
        lambda **kwargs: arguments.update(kwargs) or True,
    )

    assert traitement.main([]) == 0
    assert arguments["repertoire_staging"] == traitement.RACINE_PROJET / "output/travaux_preliminaires"
    assert arguments["repertoire_libreoffice"] == traitement.RACINE_PROJET / "output/libreoffice"
    assert arguments["repertoire_sortie"] == traitement.RACINE_PROJET / "output"
