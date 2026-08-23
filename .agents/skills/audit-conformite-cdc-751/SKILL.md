---
name: audit-conformite-cdc-751
description: Auditer ou réauditer les livrables du projet CAMMY selon le cahier des charges 751, vérifier la chaîne sources–SQLite–traitements–ODS et écrire le rapport Markdown de conformité. À utiliser pour ce dossier 751, pas comme checklist générique pour des classeurs sans SQLite ni CDC 751.
---

# Audit de conformité CDC 751

Produire un audit prouvé, feuille par feuille, puis écrire ou actualiser `RAPPORT_CONFORMITE_CDC_751.pdf` à la racine du projet.

## Références obligatoires

Lire entièrement avant l'audit :

- [references/checklist-751.md](references/checklist-751.md) pour les contrôles contractuels ;
- [references/conventions-projet.md](references/conventions-projet.md) pour les décisions métier postérieures à la checklist et les repères du jeu de données.

Lire aussi [references/rapport-conformite.md](references/rapport-conformite.md) avant de rédiger ou modifier le rapport.

## Autorisation et état initial

- Un audit ou une demande de rapport est en lecture seule : ne modifier ni code, ni sources, ni base, ni ODS. Le seul fichier créé ou mis à jour est le rapport Markdown demandé.
- Une demande explicite de correction autorise uniquement les changements visés, leurs tests et la régénération aval nécessaire.
- Relever l'état Git avant toute action. Préserver les changements préexistants et comparer l'état final à cet inventaire.
- Faire les reconstructions de contrôle sous `/tmp`. Ne publier dans `output/` que si l'utilisateur demande explicitement une régénération.

## Exécution de l'audit

1. Inventorier le CDC, les sources, SQLite, les CSV intermédiaires, les ODS et le rapport d'exécution. Calculer des empreintes lorsque cela permet de prouver l'absence de modification.
2. Vérifier SQLite : six tables métier, volumes, `integrity_check`, clés étrangères et filiation entre entêtes et lignes.
3. Contrôler chaque feuille ODS, pas seulement chaque classeur : colonnes, types, lignes, formules, agrégations, filiation, totaux, valeurs absentes et erreurs de formule.
4. Pour chaque feuille raccordable à SQLite, documenter au moins une preuve SQL avec clé ou période, requête, valeur SQLite, valeur ODS et résultat `IDENTIQUE` ou `DIFFÉRENT`. Adapter la preuve à la nature de la feuille : ticket identifiable, agrégat `COUNT/SUM/GROUP BY`, ou recalcul des deux côtés et de l'écart.
5. Reconstituer indépendamment chaque clôture réelle entre la clôture précédente et la clôture courante. Comparer HT, TVA, TTC à Z1 et cartes, chèques, espèces à Z2, clôture par clôture et sans compensation mensuelle.
6. Tester explicitement les lots multi-mois, les périodes sans mode Z, les cellules dépendant des FEC/CA3 absents et `D_QUANTITE_ARTICLE`.
7. Qualifier les écarts mensuels uniquement avec les catégories de la checklist. Ne jamais confondre un décalage de frontière ou un lot multi-mois avec un écart source.
8. Conclure chaque feuille avec un seul statut autorisé. Ne déduire le verdict global qu'après établissement de la matrice exhaustive.

Lorsque la régénération est demandée, exécuter la suite de tests puis le pipeline officiel du projet. Si PyUNO local échoue, utiliser l'environnement Docker/LibreOffice prévu par le dépôt ; ne contourner ni ne réécrire les ODS avec une bibliothèque différente.

## Vérification finale

Après rédaction, exécuter :

```bash
python3 <chemin-du-skill>/scripts/validate_audit_751.py \
  --project <racine-du-projet> \
  --report <racine-du-projet>/RAPPORT_CONFORMITE_CDC_751.md
```

Le validateur contrôle les invariants substantiels du jeu 751, la couverture des classeurs/feuilles, les preuves SQL, SQLite et les cas métier critiques. Corriger le rapport ou investiguer les livrables si le script échoue ; ne modifier aucune valeur pour satisfaire artificiellement le validateur.
