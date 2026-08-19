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
        traitement.db_ej_entetes_vers_ods,
        "main",
        lambda arguments: appels.append(("ods_entetes", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.db_ej_tickets_vers_ods,
        "main",
        lambda arguments: appels.append(("ods_tickets", arguments)) or 0,
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
    ]
    assert staging.is_dir()
    assert libreoffice.is_dir()


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
        traitement.db_ej_entetes_vers_ods,
        "main",
        lambda _: pytest.fail("Les ODS ne doivent pas être générés"),
    )
    monkeypatch.setattr(
        traitement.db_ej_tickets_vers_ods,
        "main",
        lambda _: pytest.fail("Les ODS ne doivent pas être générés"),
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
