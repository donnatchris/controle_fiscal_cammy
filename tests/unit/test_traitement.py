from pathlib import Path

import pytest

import traitement


def test_executer_traitements_enchaine_reconstruction_et_csv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appels: list[tuple[str, list[str]]] = []
    sources = tmp_path / "sources"
    base = tmp_path / "database/db.sqlite"
    staging = tmp_path / "staging"
    controle = tmp_path / "controle"
    regles = tmp_path / "config/regles.json"
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

    assert traitement.executer_traitements(
        chemin_repertoire=sources,
        chemin_base=base,
        repertoire_staging=staging,
        repertoire_controle=controle,
        chemin_regles=regles,
    ) is True
    assert appels == [
        ("reconstruction", [
            "--sources", str(sources), "--base", str(base),
            "--rapport", str(controle / "rapport_reconstruction_751.json"), "--publier",
        ]),
        ("csv", [
            "--base", str(base), "--staging", str(staging),
            "--controle", str(controle), "--regles", str(regles),
        ]),
    ]
    assert staging.is_dir()
    assert controle.is_dir()


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

    assert traitement.executer_traitements(
        chemin_repertoire=tmp_path / "sources",
        chemin_base=tmp_path / "db.sqlite",
        repertoire_staging=tmp_path / "staging",
        repertoire_controle=tmp_path / "controle",
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
    assert arguments["repertoire_controle"] == traitement.RACINE_PROJET / "controle"
