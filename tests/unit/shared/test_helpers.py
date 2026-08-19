from shared.ods_helpers import convertir_valeur_tableau


def test_convertir_valeur_tableau_utilise_la_configuration_des_colonnes() -> None:
    assert convertir_valeur_tableau(
        "000012",
        "numero",
        colonnes_texte={"numero"},
    ) == "000012"
    assert convertir_valeur_tableau(
        "2023-01-02",
        "date",
        colonne_date="date",
    ) == 44_928.0
    assert convertir_valeur_tableau("12.50", "montant") == 12.5
