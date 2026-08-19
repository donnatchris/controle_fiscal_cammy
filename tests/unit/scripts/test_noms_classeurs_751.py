from shared.constantes import FeuilleEjEntetes


def test_feuilles_ej_entetes_sont_resolues_par_boutique() -> None:
    assert FeuilleEjEntetes.ENTETES.pour("MASSENA") == "ENTETES_TICKETS_MASSENA_0"
    assert (
        FeuilleEjEntetes.SEQUENTIALITE.pour("MATURIN")
        == "ENTETES_TICKETS_MATURIN_sequentialite"
    )
    assert FeuilleEjEntetes.TD_OCCURRENCE_NUM_INTERNE.pour("MASSENA") == (
        "TD_OccurenceNumInterne"
    )
