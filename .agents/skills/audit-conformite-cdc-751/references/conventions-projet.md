# Conventions et repères du projet 751

Ces décisions métier sont postérieures ou plus précises que la checklist initiale. Elles prévalent en cas d'ambiguïté.

## Décisions métier obligatoires

- Un lot multi-mois est affecté au **dernier mois indiqué**, mois de clôture : `042025_052025_062025 → 2025-06` et `062025_072025 → 2025-07`.
- Il faut détecter toutes les périodes adjacentes du nom. Une expression régulière qui consomme le séparateur `_` peut manquer la période suivante.
- Dans une comparaison Z2/EJ, si l'une des deux sources mensuelles n'existe pas, les cellules Z/quantité/écart dépendantes restent vides. Une absence ne devient jamais zéro.
- `D_QUANTITE_ARTICLE` reste **numérique**. Ce choix explicite n'est pas une non-conformité de type.
- MATURIN 2025-07 reçoit la clôture du lot `062025_072025`. Juin est couvert par ce lot clôturé en juillet et ne constitue pas une cinquième absence réelle.
- Les quatre véritables périodes sans mode Z MATURIN sont uniquement `2023-11`, `2023-12`, `2025-04` et `2025-05`.

## Repères du jeu de données actuel

Utiliser ces valeurs comme invariants à vérifier, jamais comme résultats à recopier sans calcul :

- 512 fichiers sources : 449 CSV et 63 TXT ;
- 6 tables SQLite : `tickets`, `lignes_ticket`, `z1_entetes`, `z1_lignes`, `z2_entetes`, `z2_lignes` ;
- volumes respectifs : 2 511, 4 131, 96, 3 936, 96 et 4 800 lignes ;
- 30 classeurs ODS et 131 feuilles ;
- 30 clôtures MASSENA et 27 clôtures MATURIN, soit 57 clôtures réelles ;
- 16 CSV préparatoires ;
- référence de tests après corrections : 158 tests réussis ;
- référence ODS après corrections : 17 033 cellules de formule, sans erreur de formule connue.

Un écart à ces repères doit être expliqué par un changement de périmètre ou signalé. Il ne faut pas forcer le rapport à reproduire les nombres historiques.

## Pièces non fournies

Les FEC 2023–2025, CA3 de janvier 2023 à août 2025 et règles/justificatifs de correction-annulation ne sont pas fournis. Vérifier que rien n'est inventé et que les cellules dépendantes restent vides. Utiliser `NON VÉRIFIABLE — PIÈCE CLIENT NON FOURNIE`, pas `NON CONFORME`, lorsque cette absence est la seule limite.

## Régénération et comparaison

- La base, les CSV et les ODS régénérés doivent être produits par le pipeline officiel.
- Comparer les ODS par structure et contenu métier (`content.xml`), pas seulement par hash du fichier ZIP : LibreOffice peut modifier les métadonnées d'empaquetage sans changer les cellules.
- Distinguer les fichiers réellement modifiés des fichiers seulement republiés.
- Le rapport d'exécution opérationnel et le rapport de conformité peuvent être complémentaires ; le rapport de conformité doit rester autonome pour les preuves d'audit.

