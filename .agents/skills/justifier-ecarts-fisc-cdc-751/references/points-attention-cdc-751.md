# Points d'attention et justifications - CDC 751

## Source et portée

Source primaire : `fichiers_sources/751 - CAMMY FRANCE DEVELOPPEMENT LTD.pdf`, lettre de 25 pages suivie d'une annexe de 10 pages, datée du 16 juillet 2026. La période contrôlée va du 1er janvier 2023 au 31 août 2025. La remise des résultats est annoncée au 28 août 2026.

Cette référence recense les sujets que la société doit expliquer ou justifier lorsqu'un écart apparaît. Elle ne présume pas qu'un écart existe et ne remplace pas la preuve issue des sources, de SQLite, des traitements et des ODS.

## Matrice des points d'attention

| Priorité | Exigence ou résultat à expliquer | Référence CDC | Preuves minimales attendues |
|---|---|---|---|
| Critique | Difficulté ou impossibilité de réaliser un travail demandé : prévenir rapidement par écrit, identifier les travaux touchés et les motifs | p. 1 | courrier daté, chronologie, périmètre, cause, mesure proposée |
| Critique | Conservation des enregistrements utilisés pendant le contrôle et possibilité de traitements complémentaires | p. 2 | inventaire, empreintes, sauvegarde, chaîne de garde |
| Majeure | Remise dématérialisée sécurisée, ZIP possible, double exemplaire du programme, du rapport d'exécution et des résultats | p. 2 | bordereau de remise, accusé de réception, inventaire des exemplaires |
| Majeure | Rapport des enregistrements lus, sélectionnés et écrits, total global des montants numériques | p. 2 | rapport d'exécution par fichier et feuille, totaux rapprochés |
| Majeure | Euros, virgule comme seul séparateur décimal, homogénéisation, champ absent laissé vide, montants d'annulation/correction négatifs | p. 2 | rendu Calc/ODS, types, échantillons, absence de zéros substitutifs |
| Critique | Respect de la période et des deux boutiques MASSENA/MATURIN | p. 3 et 5 | bornes de dates, inventaire des sources, couverture par boutique |
| Critique | Régularité des factures/tickets, CA et TVA, règlements, corrections et annulations | p. 3 | rapprochements détaillés et agrégés, pièces de paramétrage |
| Critique | FEC 2023, 2024 et période 2025 mentionnés comme fichiers communiqués | p. 4 | preuve de remise au fisc, preuve de mise à disposition ou de non-remise à DEVFRA, demande de pièces et réponse |
| Majeure | Schémas, noms, types et valeurs vides des fichiers EJ et Z | p. 5 à 8 | dictionnaire de données, contrôles de colonnes/types, filiation source-sortie |
| Majeure | `D_QUANTITE_ARTICLE` est demandé en type texte | p. 6 | si numérique : accord écrit du donneur d'ordre, justification fonctionnelle et absence d'altération |
| Critique | Cohérence TVA : TVA calculée à 20 %, écart TVA, TTC calculé, écart TTC et solde de règlement | p. 9 à 10 | valeurs ticket/source/SQLite/ODS, formule, impact HT-TVA-TTC-règlement |
| Critique | Toute rupture de séquentialité ou de chronologie des tickets | p. 10 | tickets avant/après, horodatages, magasin/caisse, motif opérationnel, journal applicatif |
| Critique | Résultats des recherches de doublons sur numéro interne et numéro de ticket | p. 11 | clés complètes, occurrences, distinction doublon réel/réutilisation de numéro, impact monétaire |
| Critique | Cohérence entre entêtes et lignes de tickets, net des corrections | p. 12 à 13 | recomposition par ticket, détail des lignes, corrections, écart au centime |
| Critique | Champ d'application et taux de TVA par libellé d'article | p. 13 à 14 | catalogue article, taux source, justification fiscale du taux, occurrences et montants |
| Majeure | Année/mois de clôture Z tirés du nom du fichier et agrégations par mode | p. 14 à 16 et 20 à 22 | nom source, périodes détectées, mode Z/ZZ1/ZZ2, compteur, date/heure, règle d'affectation |
| Critique | Intégralité des résultats de la comparaison Z2 mode ZZ1 contre ZZ2 pour MASSENA ; comparaison non demandée pour MATURIN 2024 | p. 17 | tableau d'écarts quantité/montant par nature, cause et impact |
| Critique | Comparaisons mensuelles des règlements Z2 contre EJ pour MASSENA et MATURIN | p. 19 | cartes/chèques/espèces, quantité et montant, rapprochement par clôture |
| Critique | Comparaisons mensuelles CA/HT/TVA de Z1 contre EJ pour MASSENA et MATURIN | p. 23 | CA TTC, HT, TVA, frontière de clôture, preuve par clôture |
| Critique | Comparaison du CA et de la TVA reconstitués avec les déclarations CA3 mensuelles | p. 24 | CA3 authentiques, valeurs reconstituées, écarts HT/TVA, explication et incidence déclarative |
| Critique | Procédures de correction/annulation non contrôlables faute de traçabilité et de paramétrages dans les données communiquées | p. 25 | citation du constat du CDC, liste des pièces absentes, demandes, traces disponibles, limites précises |

## Alertes propres au dossier actuel

Vérifier ces points à chaque utilisation ; ce sont des constats historiques, pas des valeurs à recopier sans contrôle.

### Contradiction FEC

La page 4 du CDC présente trois FEC comme communiqués, tandis que le rapport de conformité du 23 août 2026 indique qu'aucun FEC n'a été fourni au projet. Ne pas écrire simplement « FEC non fournis ». Déterminer si les fichiers ont été remis directement à l'administration mais pas à DEVFRA, omis du lot technique ou perdus. Exiger le bordereau du 15 avril 2026, l'accusé du 4 mai 2026, les échanges client-prestataire et les empreintes ou noms exacts.

### CA3 absentes

Le CDC exige la comparaison mensuelle avec les CA3, mais le dossier courant ne contient pas les déclarations de janvier 2023 à août 2025. Laisser les valeurs et écarts dépendants vides. Qualifier `NON VÉRIFIABLE - PIÈCE CLIENT NON FOURNIE` seulement si la non-remise à DEVFRA est documentée. Préciser que l'absence empêche la comparaison ; elle ne démontre ni concordance ni écart.

### Corrections et annulations

Le CDC constate lui-même page 25 l'absence de traçabilité intégrée et de paramétrages, rendant le traitement prévu impossible. Le jeu actuel contient néanmoins des valeurs `D_CORRECTION`. Expliquer séparément : ce que la valeur source permet de constater, ce que les règles absentes empêchent de vérifier et pourquoi aucune règle n'a été inventée.

### Modes Z absents

Les périodes historiques identifiées pour MATURIN sont 2023-11, 2023-12, 2025-04 et 2025-05. Des modes alternatifs peuvent exister, mais ils ne remplacent pas silencieusement le mode Z demandé. Justifier par l'inventaire des fichiers, laisser vides les cellules dépendantes et rapprocher les clôtures réelles disponibles.

### Lots multi-mois et frontières de clôture

Les lots `042025_052025_062025` et `062025_072025` ont historiquement été affectés au dernier mois indiqué, mois de clôture. Cette interprétation doit être appuyée par le nom source, la date/heure et le compteur de clôture, ainsi que par le rapprochement indépendant EJ/Z. Pour tout écart mensuel, distinguer `DÉCALAGE DE FRONTIÈRE DE CLÔTURE`, `LOT MULTI-MOIS`, `MODE/CLÔTURE ABSENT` et `ÉCART SOURCE À INVESTIGUER`.

### Type de quantité

Le CDC demande `D_QUANTITE_ARTICLE` en texte, alors que la décision métier historique l'a conservé en numérique. Il s'agit d'une dérogation littérale à documenter, même si elle préserve mieux la sémantique de quantité. Exiger une validation écrite, datée et attribuable ; à défaut, présenter le point comme écart de type et non comme conformité acquise.

### Situation auditée au 23 août 2026

Le rapport PDF courant conclut historiquement à `CONFORME AVEC RÉSERVE`, avec 130 feuilles conformes, aucune feuille non conforme et une feuille non vérifiable faute de CA3. Il indique aussi 57 clôtures réelles concordantes. Si ces preuves sont encore valides, il n'existe pas de non-conformité actuelle à justifier ; il existe des limites et contradictions documentaires à lever. Rejouer les contrôles avant toute réponse définitive.

## Hiérarchie des causes recevables

Une justification solide relie le constat à une cause et à une preuve :

1. donnée source absente ou incohérente, prouvée par l'inventaire et les fichiers bruts ;
2. convention de clôture ou paramétrage métier, prouvé par une validation et les données Z ;
3. exigence ambiguë ou contradictoire, citée précisément et soumise à validation ;
4. défaut de traitement DEVFRA, reproduit, circonscrit, corrigé et couvert par tests ;
5. cause indéterminée : déclarer l'investigation ouverte, sans attribuer la responsabilité.

Un écart n'est « sans incidence fiscale » que si un recalcul indépendant démontre l'absence d'effet sur HT, TVA, TTC, règlements et déclarations pour tout le périmètre touché.

## Format de fiche à remettre pour validation

```markdown
### Écart [identifiant] - [titre factuel]

- Exigence CDC : [page, section, exigence]
- Livrable/période : [fichier, feuille, boutique, dates]
- Constat : [valeur attendue / valeur constatée]
- Qualification : [statut]
- Cause démontrée : [cause + preuve] ou À ÉTABLIR
- Impact fiscal et comptable : [HT, TVA, TTC, règlements, CA3]
- Mesure conservatoire/correction : [action, date, périmètre]
- Vérification après action : [requête, test, rapprochement]
- Annexes : [sources, empreintes, échanges, validation]
- Formulation proposée au fisc : [texte concis et vérifiable]
- Validation requise : [direction, expert-comptable, conseil]
```

## Ordre de sortie recommandé

1. synthèse des écarts établis et des points non vérifiables ;
2. matrice exigence-constat-impact-preuve-action ;
3. fiches de justification ;
4. liste des preuves manquantes et questions à trancher ;
5. annexes techniques reproductibles.
