import pytest

from shared.constantes import ALIAS_COURT, NOM_COMPLET, iterer_classeurs_751, resoudre_classeur_751


def test_registre_developpe_18_classeurs_ods() -> None:
    classeurs = iterer_classeurs_751()
    assert len(classeurs) == 18
    assert sum(len(classeur.feuilles) for classeur in classeurs) == 135
    assert all(classeur.nom_fichier.endswith(".ods") for classeur in classeurs)


def test_alias_sont_ordonnes_uniques_et_resolus() -> None:
    for classeur in iterer_classeurs_751():
        noms_complets = classeur.noms_feuilles(NOM_COMPLET)
        alias = classeur.noms_feuilles(ALIAS_COURT)
        assert len(noms_complets) == len(alias) == len(set(alias))


def test_resolveur_refuse_un_contexte_invalide() -> None:
    with pytest.raises(ValueError, match="Boutique invalide"):
        resoudre_classeur_751("ej_entetes", boutique="INCONNUE")
