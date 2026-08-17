from pathlib import Path

import pytest

import traitement


def test_executer_traitements_enchaine_reconstruction_et_classeurs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appels: list[tuple[str, list[str]]] = []
    sources = tmp_path / "sources"
    base = tmp_path / "database/db.sqlite"
    sortie = tmp_path / "output"
    staging = tmp_path / "staging"
    controle = tmp_path / "controle"
    regles = tmp_path / "config/regles.json"
    monkeypatch.setattr(
        traitement.reconstruire_base_751,
        "main",
        lambda arguments: appels.append(("reconstruction", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.db_ej_vers_xlsx,
        "main",
        lambda arguments: appels.append(("excel", arguments)) or 0,
    )
    monkeypatch.setattr(
        traitement.generer_rapport_fiscal_751,
        "main",
        lambda arguments: appels.append(("pdf", arguments)) or 0,
    )

    succes = traitement.executer_traitements(
        chemin_repertoire=sources,
        chemin_base=base,
        repertoire_sortie=sortie,
        repertoire_staging=staging,
        repertoire_controle=controle,
        chemin_regles=regles,
        qa=True,
    )

    assert succes is True
    assert appels == [
        (
            "reconstruction",
            [
                "--sources", str(sources),
                "--base", str(base),
                "--rapport", str(controle / "rapport_reconstruction_751.json"),
                "--publier",
            ],
        ),
        (
            "excel",
            [
                "--base", str(base),
                "--sortie", str(sortie / "excel"),
                "--staging", str(staging),
                "--controle", str(controle),
                "--regles", str(regles),
                "--qa",
            ],
        ),
        (
            "pdf",
            [
                "--base", str(base),
                "--controle", str(controle),
                "--sortie", str(sortie),
            ],
        ),
    ]
    assert sortie.is_dir()
    assert (sortie / "excel").is_dir()
    assert staging.is_dir()
    assert controle.is_dir()


def test_executer_traitements_sarrete_si_reconstruction_echoue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    excel_appele = False

    monkeypatch.setattr(traitement.reconstruire_base_751, "main", lambda _: 1)

    def excel_main(_: list[str]) -> int:
        nonlocal excel_appele
        excel_appele = True
        return 0

    monkeypatch.setattr(traitement.db_ej_vers_xlsx, "main", excel_main)
    monkeypatch.setattr(
        traitement.generer_rapport_fiscal_751,
        "main",
        lambda _: pytest.fail("Le rapport ne doit pas être appelé"),
    )

    succes = traitement.executer_traitements(
        chemin_repertoire=tmp_path / "sources",
        chemin_base=tmp_path / "db.sqlite",
        repertoire_sortie=tmp_path / "output",
        repertoire_staging=tmp_path / "staging",
        repertoire_controle=tmp_path / "controle",
    )

    assert succes is False
    assert excel_appele is False


def test_main_utilise_output_par_defaut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments: dict[str, object] = {}

    def simuler(**kwargs: object) -> bool:
        arguments.update(kwargs)
        return True

    monkeypatch.setattr(traitement, "executer_traitements", simuler)

    assert traitement.main([]) == 0
    assert arguments["repertoire_sortie"] == traitement.RACINE_PROJET / "output"
    assert arguments["repertoire_staging"] == (
        traitement.RACINE_PROJET / "output/travaux_preliminaires"
    )
    assert arguments["repertoire_controle"] == traitement.RACINE_PROJET / "controle"
    assert arguments["chemin_repertoire"] == traitement.RACINE_PROJET / "fichiers_sources"
    assert arguments["chemin_base"] == traitement.RACINE_PROJET / "database/db.sqlite"


def test_main_accepte_option_travaux_preliminaires(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arguments: dict[str, object] = {}
    destination = tmp_path / "travaux_preliminaires"

    monkeypatch.setattr(
        traitement,
        "executer_traitements",
        lambda **kwargs: arguments.update(kwargs) or True,
    )

    assert traitement.main(["--travaux-preliminaires", str(destination)]) == 0
    assert arguments["repertoire_staging"] == destination


def test_ranger_anciens_classeurs_deplace_uniquement_les_xlsx_attendus(
    tmp_path: Path,
) -> None:
    sortie = tmp_path / "output"
    excel = sortie / "excel"
    sortie.mkdir()
    nom = next(iter(traitement.db_ej_vers_xlsx.NOMS_CLASSEURS_ATTENDUS))
    ancien = sortie / nom
    ancien.write_bytes(b"xlsx")
    inconnu = sortie / "a_preserver.xlsx"
    inconnu.write_bytes(b"utilisateur")

    traitement.ranger_anciens_classeurs(sortie, excel)

    assert not ancien.exists()
    assert (excel / nom).read_bytes() == b"xlsx"
    assert inconnu.read_bytes() == b"utilisateur"
