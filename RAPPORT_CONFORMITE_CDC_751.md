# Rapport de conformité au cahier des charges 751

- **Projet audité :** contrôle fiscal CAMMY France Développement LTD
- **Date de l’audit :** 23 août 2026
- **Période couverte par les livrables :** 1er janvier 2023 au 31 août 2025

**Références :** `fichiers_sources/751 - CAMMY FRANCE DEVELOPPEMENT LTD.pdf` (36 pages, dont CDC pages 1 à 25), checklist d’audit fournie, `output/database/db.sqlite`, 30 classeurs ODS et `output/rapport-d-execution.txt`.

> **Conclusion globale : CONFORME AVEC RÉSERVE.** Les données sources, la base SQLite, les 57 clôtures réelles et les 130 feuilles vérifiables sont cohérentes après correction et régénération. La seule feuille non vérifiable est la comparaison CA3, faute de déclarations fournies. `D_QUANTITE_ARTICLE` est volontairement conservée en numérique conformément à la décision métier du 23 août 2026.

## 1. Résumé exécutif

| Conclusion par feuille | Nombre |
|---|---:|
| CONFORME | 130 |
| CONFORME AVEC RÉSERVE | 0 |
| NON CONFORME | 0 |
| NON VÉRIFIABLE | 1 |
| **Total** | **131** |

Points favorables :

- les 512 sources de caisse (449 CSV et 63 TXT) ont été relues sans modification ;
- la reconstruction complète produit les volumes SQLite attendus et 16 CSV préparatoires cohérents ;
- `PRAGMA integrity_check` retourne `ok` et `PRAGMA foreign_key_check` ne retourne aucune ligne ;
- les 30 clôtures MASSENA et les 27 clôtures MATURIN concordent au centime avec les EJ sur HT, TVA, TTC, cartes, chèques et espèces ;
- les 131 feuilles attendues sont présentes et le balayage de 17 033 cellules de formule ne détecte aucune erreur `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?` ou `#N/A` ;
- les données CA3, FEC et règles/justificatifs de correction-annulation absentes ne sont pas inventées dans les livrables contrôlés.

Corrections et décisions vérifiées :

1. **Lots multi-mois affectés au dernier mois.** Les fonctions Z1 et Z2 relèvent désormais toutes les périodes présentes dans le nom et retiennent la dernière : `042025_052025_062025 → 2025-06` et `062025_072025 → 2025-07`.
2. **Absence du mode Z laissée vide dans les comparaisons Z2/EJ.** Lorsqu’une période n’existe que d’un côté, les six cellules de quantité/écart sont vides ; aucun zéro ni faux écart n’est inventé, comme dans le comparateur Z1.
3. **`D_QUANTITE_ARTICLE` reste numérique.** Ce type est conservé explicitement à la demande du donneur d’ordre ; aucune modification de cette colonne n’a été effectuée.
4. **Rapport d’exécution complété par le présent audit.** Le rapport opérationnel couvre les 131 feuilles et les compteurs ; le présent fichier apporte les preuves SQL, le tableau des 57 clôtures et la qualification des écarts et pièces absentes.

## 2. Méthode et périmètre

L’audit suit la chaîne `sources → SQLite → CSV intermédiaires → traitements → ODS`. Les contrôles ODS ont été faits directement dans `content.xml` des archives ODS afin de lire les valeurs typées, formules, feuilles, zones utilisées et valeurs mises en cache, puis confrontés aux requêtes SQLite de l’annexe A.

La reconstruction complète de SQLite a été exécutée sous `/tmp/controle_fiscal_cammy_audit751` :

- 512 sources inchangées ; empreinte agrégée SHA-256 : `8c2d56c83e65b7533932e90b45e4b77dd1ff524de678f1bdb42615834a8fe6cc` ;
- empreinte SHA-256 des dumps SQL livré/temporaire : `9bf3e1cd401a86a58ab90bbf5bca3729bf4024be3853f2be5a6922358cb557b8` des deux côtés ;
- comparaison récursive des 16 CSV préparatoires : aucune différence ;
- la régénération complète a abouti dans l’environnement Docker/LibreOffice du projet : base, 16 CSV, 30 ODS et rapport d’exécution recréés avec succès ;
- tests unitaires : **158 réussis**.

Les feuilles détaillées ont été contrôlées sur un ticket identifiable ; les feuilles agrégées avec `COUNT`, `SUM` et `GROUP BY` ; les comparaisons avec recalcul indépendant des deux côtés disponibles et de l’écart. Les montants sont comparés au centime avec `Decimal`; les résidus binaires inférieurs à 0,005 € sont normalisés à 0,00 €.

## 3. Inventaire SQLite et contrôles transversaux

| Table | Lignes livrées | Lignes reconstruites | Résultat |
|---|---:|---:|---|
| `tickets` | 2511 | 2511 | IDENTIQUE |
| `lignes_ticket` | 4131 | 4131 | IDENTIQUE |
| `z1_entetes` | 96 | 96 | IDENTIQUE |
| `z1_lignes` | 3936 | 3936 | IDENTIQUE |
| `z2_entetes` | 96 | 96 | IDENTIQUE |
| `z2_lignes` | 4800 | 4800 | IDENTIQUE |

| Boutique | Tickets de vente | Lignes article | HT total | TVA totale | TTC total | CB | Chèques | Espèces |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MASSENA | 1 153 | 2 521 | 625 407,76 | 125 081,94 | 750 489,70 | 260 816,50 | 7 029,00 | 482 644,20 |
| MATURIN | 722 | 1 610 | 471 917,39 | 94 383,51 | 566 300,90 | 451 238,76 | 369,00 | 114 693,14 |

Échantillons cellule par cellule :

- MASSENA, `E_NUM_INTERNE=004517`, `E_NUM_TICKET=003562`, 2023-01-02 11:25 : HT 249,17 ; TVA 49,83 ; TTC 299,00 ; CB 299,00. Valeurs SQLite et ODS identiques.
- MATURIN, `E_NUM_INTERNE=000977`, `E_NUM_TICKET=000609`, 2023-01-04 12:01 : HT 747,50 ; TVA 149,50 ; TTC 897,00 ; espèces 897,00. Valeurs SQLite et ODS identiques.
- Ligne MASSENA du ticket 003562 : quantité source `1`, libellé `DEPT001`, taux `T1`, montant 299,00. Valeurs identiques ; la quantité reste volontairement numérique conformément à la décision métier.

## 4. Pièces externes et données absentes

| Élément | Constat | Statut |
|---|---|---|
| FEC 2023, 2024, 2025 | Aucun FEC fourni ; aucune donnée FEC inventée | NON VÉRIFIABLE — PIÈCE CLIENT NON FOURNIE |
| CA3 janvier 2023 à août 2025 | Colonnes CA3 et écarts laissés vides dans les 32 lignes | NON VÉRIFIABLE — PIÈCE CLIENT NON FOURNIE |
| Règles/justificatifs de correction-annulation | Non fournis ; les 12 valeurs `D_CORRECTION` issues des EJ sont conservées, sans règle inventée | NON VÉRIFIABLE — PIÈCE CLIENT NON FOURNIE |
| MATURIN 2023-11, 2023-12, 2025-04, 2025-05 | Mode Z contractuel absent | NON VÉRIFIABLE — CLÔTURE/MODE Z ABSENT |

## 5. Lots multi-mois et comparaisons mensuelles

| Lot / période | Attendu | ODS constaté | Effet | Qualification |
|---|---|---|---|---|
| MASSENA `042025_052025_062025` | `AJ_Mois_Z=2025-06` | `2025-06` en Z1 et Z2, modes ZZ1/ZZ2 | agrégats et comparaisons portés au mois de clôture | LOT MULTI-MOIS — CONFORME |
| MATURIN `062025_072025` | `AJ_Mois_Z=2025-07` | `2025-07` en Z1 et Z2, mode Z | juillet récupère la clôture ; juin est couvert par ce lot | LOT MULTI-MOIS — CONFORME |
| MATURIN 2023-11/12 | Z et écarts Z1/Z2 vides | Z1 et Z2 vides | aucune valeur inventée | MODE/CLÔTURE ABSENT — CONFORME |
| MATURIN 2025-04/05 | Z et écarts Z1/Z2 vides | Z1 et Z2 vides | aucune valeur inventée | MODE/CLÔTURE ABSENT — CONFORME |

Les autres écarts mensuels significatifs sont expliqués par les frontières de clôture :

- MASSENA 2023 : paires février/mars, juin/juillet, août/septembre et octobre/novembre ;
- MASSENA 2024 : chaîne janvier-mars, paires juillet/août et octobre/novembre ;
- MASSENA 2025 : janvier/février ; avril et mai sont sans clôture mensuelle distincte et le lot avril-mai-juin est correctement affecté à juin ;
- MATURIN 2023 : septembre/octobre ; novembre/décembre relève de l’absence du mode Z ;
- MATURIN 2024 : janvier porte le reliquat depuis la dernière clôture 2023, puis paires mai/juin et octobre/novembre ;
- MATURIN 2025 : janvier/février et août ; avril et mai sont les deux périodes réellement sans mode Z. Juin est couvert par le lot multi-mois dont la clôture conventionnelle est portée en juillet ; juillet n’est donc pas une période absente.

Le rapprochement indépendant des clôtures ci-dessous démontre qu’aucun de ces écarts mensuels ne constitue un écart source : toutes les clôtures réelles concordent.

## 6. Contrôle indépendant des 57 clôtures EJ/Z

Convention : intervalle `date/heure clôture précédente < ticket ≤ date/heure clôture courante`; pour la première clôture, début au 2023-01-01 00:00. Les cellules présentent `EJ/Z`.

| Boutique | Z | Clôture | Début exclusif | Tickets | HT EJ/Z1 | TVA EJ/Z1 | TTC EJ/Z1 | CB EJ/Z2 | Chèques EJ/Z2 | Espèces EJ/Z2 | Résultat |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| MASSENA | 0061 | 2023-01-31 18:44 | 2023-01-01 00:00 | 121 | 63641.51/63641.51 | 12728.29/12728.29 | 76369.80/76369.80 | 15385.00/15385.00 | 6042.00/6042.00 | 54942.80/54942.80 | IDENTIQUE |
| MASSENA | 0062 | 2023-03-03 19:13 | 2023-01-31 18:44 | 72 | 43970.84/43970.84 | 8794.16/8794.16 | 52765.00/52765.00 | 22705.00/22705.00 | 0.00/0.00 | 30060.00/30060.00 | IDENTIQUE |
| MASSENA | 0063 | 2023-04-01 10:35 | 2023-03-03 19:13 | 53 | 28010.82/28010.82 | 5602.18/5602.18 | 33613.00/33613.00 | 4414.00/4414.00 | 987.00/987.00 | 28212.00/28212.00 | IDENTIQUE |
| MASSENA | 0064 | 2023-05-02 08:33 | 2023-04-01 10:35 | 72 | 46746.64/46746.64 | 9349.36/9349.36 | 56096.00/56096.00 | 20500.00/20500.00 | 0.00/0.00 | 35596.00/35596.00 | IDENTIQUE |
| MASSENA | 0065 | 2023-06-01 10:11 | 2023-05-02 08:33 | 47 | 33634.99/33634.99 | 6727.01/6727.01 | 40362.00/40362.00 | 23452.00/23452.00 | 0.00/0.00 | 16910.00/16910.00 | IDENTIQUE |
| MASSENA | 0066 | 2023-07-01 14:49 | 2023-06-01 10:11 | 47 | 22242.47/22242.47 | 4448.53/4448.53 | 26691.00/26691.00 | 6499.00/6499.00 | 0.00/0.00 | 20192.00/20192.00 | IDENTIQUE |
| MASSENA | 0067 | 2023-08-01 13:05 | 2023-07-01 14:49 | 38 | 26193.34/26193.34 | 5238.66/5238.66 | 31432.00/31432.00 | 12773.00/12773.00 | 0.00/0.00 | 18659.00/18659.00 | IDENTIQUE |
| MASSENA | 0068 | 2023-09-01 18:14 | 2023-08-01 13:05 | 39 | 21853.32/21853.32 | 4370.68/4370.68 | 26224.00/26224.00 | 5315.00/5315.00 | 0.00/0.00 | 20909.00/20909.00 | IDENTIQUE |
| MASSENA | 0069 | 2023-10-01 17:53 | 2023-09-01 18:14 | 60 | 28277.94/28277.94 | 5655.56/5655.56 | 33933.50/33933.50 | 13209.00/13209.00 | 0.00/0.00 | 20724.50/20724.50 | IDENTIQUE |
| MASSENA | 0070 | 2023-11-10 16:03 | 2023-10-01 17:53 | 37 | 26769.83/26769.83 | 5353.97/5353.97 | 32123.80/32123.80 | 20776.00/20776.00 | 0.00/0.00 | 11347.80/11347.80 | IDENTIQUE |
| MASSENA | 0071 | 2023-12-01 14:21 | 2023-11-10 16:03 | 6 | 5325.01/5325.01 | 1064.99/1064.99 | 6390.00/6390.00 | 5204.00/5204.00 | 0.00/0.00 | 1186.00/1186.00 | IDENTIQUE |
| MASSENA | 0072 | 2024-01-01 17:14 | 2023-12-01 14:21 | 36 | 23448.36/23448.36 | 4689.64/4689.64 | 28138.00/28138.00 | 9809.00/9809.00 | 0.00/0.00 | 18329.00/18329.00 | IDENTIQUE |
| MASSENA | 0073 | 2024-02-02 10:45 | 2024-01-01 17:14 | 21 | 9623.34/9623.34 | 1924.66/1924.66 | 11548.00/11548.00 | 2324.00/2324.00 | 0.00/0.00 | 9224.00/9224.00 | IDENTIQUE |
| MASSENA | 0074 | 2024-03-02 14:50 | 2024-02-02 10:45 | 24 | 9994.99/9994.99 | 1999.01/1999.01 | 11994.00/11994.00 | 4954.00/4954.00 | 0.00/0.00 | 7040.00/7040.00 | IDENTIQUE |
| MASSENA | 0075 | 2024-04-02 10:00 | 2024-03-02 14:50 | 37 | 12759.21/12759.21 | 2551.89/2551.89 | 15311.10/15311.10 | 1044.50/1044.50 | 0.00/0.00 | 14266.60/14266.60 | IDENTIQUE |
| MASSENA | 0076 | 2024-04-30 17:45 | 2024-04-02 10:00 | 25 | 9576.41/9576.41 | 1915.29/1915.29 | 11491.70/11491.70 | 8669.80/8669.80 | 0.00/0.00 | 2821.90/2821.90 | IDENTIQUE |
| MASSENA | 0077 | 2024-06-01 16:16 | 2024-04-30 17:45 | 28 | 16000.12/16000.12 | 3200.08/3200.08 | 19200.20/19200.20 | 10232.30/10232.30 | 0.00/0.00 | 8967.90/8967.90 | IDENTIQUE |
| MASSENA | 0078 | 2024-07-01 11:33 | 2024-06-01 16:16 | 47 | 28064.87/28064.87 | 5613.03/5613.03 | 33677.90/33677.90 | 15382.00/15382.00 | 0.00/0.00 | 18295.90/18295.90 | IDENTIQUE |
| MASSENA | 0079 | 2024-08-03 16:47 | 2024-07-01 11:33 | 36 | 22790.84/22790.84 | 4558.16/4558.16 | 27349.00/27349.00 | 9139.00/9139.00 | 0.00/0.00 | 18210.00/18210.00 | IDENTIQUE |
| MASSENA | 0080 | 2024-09-02 00:39 | 2024-08-03 16:47 | 49 | 30415.96/30415.96 | 6083.24/6083.24 | 36499.20/36499.20 | 11797.40/11797.40 | 0.00/0.00 | 24701.80/24701.80 | IDENTIQUE |
| MASSENA | 0081 | 2024-10-01 15:45 | 2024-09-02 00:39 | 25 | 11208.22/11208.22 | 2241.68/2241.68 | 13449.90/13449.90 | 1214.00/1214.00 | 0.00/0.00 | 12235.90/12235.90 | IDENTIQUE |
| MASSENA | 0082 | 2024-11-05 18:08 | 2024-10-01 15:45 | 43 | 19657.21/19657.21 | 3931.49/3931.49 | 23588.70/23588.70 | 687.00/687.00 | 0.00/0.00 | 22901.70/22901.70 | IDENTIQUE |
| MASSENA | 0083 | 2024-11-30 18:36 | 2024-11-05 18:08 | 12 | 3943.83/3943.83 | 788.77/788.77 | 4732.60/4732.60 | 2986.60/2986.60 | 0.00/0.00 | 1746.00/1746.00 | IDENTIQUE |
| MASSENA | 0084 | 2025-01-02 18:07 | 2024-11-30 18:36 | 26 | 10827.95/10827.95 | 2165.65/2165.65 | 12993.60/12993.60 | 1882.00/1882.00 | 0.00/0.00 | 11111.60/11111.60 | IDENTIQUE |
| MASSENA | 0085 | 2025-02-03 12:18 | 2025-01-02 18:07 | 29 | 7853.49/7853.49 | 1570.71/1570.71 | 9424.20/9424.20 | 3089.50/3089.50 | 0.00/0.00 | 6334.70/6334.70 | IDENTIQUE |
| MASSENA | 0086 | 2025-03-01 15:41 | 2025-02-03 12:18 | 23 | 14858.14/14858.14 | 2971.66/2971.66 | 17829.80/17829.80 | 7497.00/7497.00 | 0.00/0.00 | 10332.80/10332.80 | IDENTIQUE |
| MASSENA | 0087 | 2025-03-29 23:24 | 2025-03-01 15:41 | 30 | 17193.94/17193.94 | 3438.76/3438.76 | 20632.70/20632.70 | 9581.00/9581.00 | 0.00/0.00 | 11051.70/11051.70 | IDENTIQUE |
| MASSENA | 0088 | 2025-07-01 09:58 | 2025-03-29 23:24 | 34 | 10381.75/10381.75 | 2076.35/2076.35 | 12458.10/12458.10 | 5642.40/5642.40 | 0.00/0.00 | 6815.70/6815.70 | IDENTIQUE |
| MASSENA | 0089 | 2025-07-31 18:38 | 2025-07-01 09:58 | 27 | 16820.76/16820.76 | 3364.14/3364.14 | 20184.90/20184.90 | 2581.00/2581.00 | 0.00/0.00 | 17603.90/17603.90 | IDENTIQUE |
| MASSENA | 0090 | 2025-09-02 17:20 | 2025-07-31 18:38 | 9 | 3321.66/3321.66 | 664.34/664.34 | 3986.00/3986.00 | 2072.00/2072.00 | 0.00/0.00 | 1914.00/1914.00 | IDENTIQUE |
| MATURIN | 0019 | 2023-02-01 10:06 | 2023-01-01 00:00 | 32 | 19343.80/19343.80 | 3868.80/3868.80 | 23212.60/23212.60 | 17964.60/17964.60 | 0.00/0.00 | 5248.00/5248.00 | IDENTIQUE |
| MATURIN | 0020 | 2023-03-01 10:42 | 2023-02-01 10:06 | 25 | 16980.66/16980.66 | 3396.14/3396.14 | 20376.80/20376.80 | 11477.00/11477.00 | 329.00/329.00 | 8570.80/8570.80 | IDENTIQUE |
| MATURIN | 0021 | 2023-04-01 13:48 | 2023-03-01 10:42 | 25 | 21143.33/21143.33 | 4228.67/4228.67 | 25372.00/25372.00 | 15536.00/15536.00 | 0.00/0.00 | 9836.00/9836.00 | IDENTIQUE |
| MATURIN | 0022 | 2023-05-02 09:28 | 2023-04-01 13:48 | 15 | 11197.49/11197.49 | 2239.51/2239.51 | 13437.00/13437.00 | 9995.00/9995.00 | 0.00/0.00 | 3442.00/3442.00 | IDENTIQUE |
| MATURIN | 0023 | 2023-06-01 08:54 | 2023-05-02 09:28 | 24 | 12954.99/12954.99 | 2591.01/2591.01 | 15546.00/15546.00 | 12585.00/12585.00 | 0.00/0.00 | 2961.00/2961.00 | IDENTIQUE |
| MATURIN | 0024 | 2023-07-01 13:35 | 2023-06-01 08:54 | 25 | 24096.90/24096.90 | 4819.37/4819.37 | 28916.27/28916.27 | 27185.98/27185.98 | 0.00/0.00 | 1730.29/1730.29 | IDENTIQUE |
| MATURIN | 0025 | 2023-08-01 09:14 | 2023-07-01 13:35 | 41 | 25931.66/25931.66 | 5186.34/5186.34 | 31118.00/31118.00 | 29413.00/29413.00 | 0.00/0.00 | 1705.00/1705.00 | IDENTIQUE |
| MATURIN | 0026 | 2023-09-01 09:09 | 2023-08-01 09:14 | 17 | 11412.18/11412.18 | 2282.42/2282.42 | 13694.60/13694.60 | 9776.00/9776.00 | 0.00/0.00 | 3918.60/3918.60 | IDENTIQUE |
| MATURIN | 0027 | 2023-10-02 09:14 | 2023-09-01 09:09 | 31 | 16803.01/16803.01 | 3360.59/3360.59 | 20163.60/20163.60 | 19377.80/19377.80 | 0.00/0.00 | 785.80/785.80 | IDENTIQUE |
| MATURIN | 0028 | 2023-11-02 11:03 | 2023-10-02 09:14 | 28 | 18600.84/18600.84 | 3720.16/3720.16 | 22321.00/22321.00 | 19379.00/19379.00 | 0.00/0.00 | 2942.00/2942.00 | IDENTIQUE |
| MATURIN | 0029 | 2024-02-01 10:29 | 2023-11-02 11:03 | 94 | 21902.19/21902.19 | 4380.46/4380.46 | 26282.65/26282.65 | 24254.70/24254.70 | 0.00/0.00 | 2027.95/2027.95 | IDENTIQUE |
| MATURIN | 0030 | 2024-03-01 09:35 | 2024-02-01 10:29 | 40 | 25412.08/25412.08 | 5082.42/5082.42 | 30494.50/30494.50 | 26707.70/26707.70 | 0.00/0.00 | 3786.80/3786.80 | IDENTIQUE |
| MATURIN | 0031 | 2024-04-02 14:09 | 2024-03-01 09:35 | 30 | 15207.84/15207.84 | 3041.56/3041.56 | 18249.40/18249.40 | 9708.50/9708.50 | 0.00/0.00 | 8540.90/8540.90 | IDENTIQUE |
| MATURIN | 0032 | 2024-05-02 10:02 | 2024-04-02 14:09 | 29 | 18912.44/18912.44 | 3782.54/3782.54 | 22694.98/22694.98 | 19292.28/19292.28 | 0.00/0.00 | 3402.70/3402.70 | IDENTIQUE |
| MATURIN | 0033 | 2024-06-01 13:45 | 2024-05-02 10:02 | 25 | 14081.67/14081.67 | 2816.33/2816.33 | 16898.00/16898.00 | 12950.00/12950.00 | 0.00/0.00 | 3948.00/3948.00 | IDENTIQUE |
| MATURIN | 0034 | 2024-07-01 11:10 | 2024-06-01 13:45 | 23 | 27606.34/27606.34 | 5521.26/5521.26 | 33127.60/33127.60 | 30116.80/30116.80 | 0.00/0.00 | 3010.80/3010.80 | IDENTIQUE |
| MATURIN | 0035 | 2024-08-01 09:51 | 2024-07-01 11:10 | 29 | 35895.02/35895.02 | 7178.98/7178.98 | 43074.00/43074.00 | 31799.00/31799.00 | 0.00/0.00 | 11275.00/11275.00 | IDENTIQUE |
| MATURIN | 0036 | 2024-08-30 14:07 | 2024-08-01 09:51 | 24 | 32256.27/32256.27 | 6451.23/6451.23 | 38707.50/38707.50 | 36110.50/36110.50 | 0.00/0.00 | 2597.00/2597.00 | IDENTIQUE |
| MATURIN | 0037 | 2024-09-30 16:55 | 2024-08-30 14:07 | 22 | 16653.23/16653.23 | 3330.67/3330.67 | 19983.90/19983.90 | 14956.70/14956.70 | 0.00/0.00 | 5027.20/5027.20 | IDENTIQUE |
| MATURIN | 0038 | 2024-11-02 14:14 | 2024-09-30 16:55 | 14 | 31114.67/31114.67 | 6222.93/6222.93 | 37337.60/37337.60 | 34703.80/34703.80 | 0.00/0.00 | 2633.80/2633.80 | IDENTIQUE |
| MATURIN | 0039 | 2024-12-02 10:55 | 2024-11-02 14:14 | 7 | 4168.26/4168.26 | 833.64/833.64 | 5001.90/5001.90 | 5001.90/5001.90 | 0.00/0.00 | 0.00/0.00 | IDENTIQUE |
| MATURIN | 0040 | 2024-12-31 17:08 | 2024-12-02 10:55 | 17 | 9106.33/9106.33 | 1821.27/1821.27 | 10927.60/10927.60 | 7865.60/7865.60 | 0.00/0.00 | 3062.00/3062.00 | IDENTIQUE |
| MATURIN | 0041 | 2025-02-01 15:53 | 2024-12-31 17:08 | 19 | 9733.59/9733.59 | 1946.71/1946.71 | 11680.30/11680.30 | 8948.80/8948.80 | 0.00/0.00 | 2731.50/2731.50 | IDENTIQUE |
| MATURIN | 0042 | 2025-03-01 13:36 | 2025-02-01 15:53 | 13 | 3815.68/3815.68 | 763.12/763.12 | 4578.80/4578.80 | 2048.80/2048.80 | 0.00/0.00 | 2530.00/2530.00 | IDENTIQUE |
| MATURIN | 0043 | 2025-04-01 09:43 | 2025-03-01 13:36 | 12 | 3211.42/3211.42 | 642.28/642.28 | 3853.70/3853.70 | 3348.70/3348.70 | 0.00/0.00 | 505.00/505.00 | IDENTIQUE |
| MATURIN | 0044 | 2025-08-01 09:38 | 2025-04-01 09:43 | 55 | 22562.17/22562.17 | 4512.43/4512.43 | 27074.60/27074.60 | 9991.60/9991.60 | 40.00/40.00 | 17043.00/17043.00 | IDENTIQUE |
| MATURIN | 0045 | 2025-09-01 09:02 | 2025-08-01 09:38 | 6 | 1813.33/1813.33 | 362.67/362.67 | 2176.00/2176.00 | 744.00/744.00 | 0.00/0.00 | 1432.00/1432.00 | IDENTIQUE |

**Résultat : 57/57 IDENTIQUE — 30 clôtures MASSENA et 27 clôtures MATURIN.**

## 7. Matrice exhaustive des 131 feuilles

Les identifiants de requête renvoient à l’annexe A. Pour les feuilles copiées ou dérivées, la preuve SQL est rejouée contre la valeur source et la valeur effectivement écrite dans la feuille.

| # | Classeur | Feuille | Source immédiate | Lus/sél./écrits | SQL | Résultat | Conclusion |
|---:|---|---|---|---:|---|---|---|
| 1 | `CompareCA_Gesco_CA3.ods` | `CompareCA_Gesco_CA3` | recettes_mensuelles_tous_boutique_232425.ods / recettes_mensuelles_tous_boutique_232425 | 32/32/32 | Q-CA3 | Gesco IDENTIQUE ; CA3 absente | **NON VÉRIFIABLE** |
| 2 | `Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2023.ods` | `Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2023` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / Z1_TotalMontantParMoisAnnee_2023_ModeZZ1; TTS_EJ_ENTETES_TICKETS_MASSENA.ods / recettes_mensuelles_MASSENA_232425 | 44/24/12 | Q-CMP-Z1 | IDENTIQUE | **CONFORME** |
| 3 | `Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2024.ods` | `Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2024` | TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods / Z1_TotalMontantParMoisAnnee_2024_ModeZZ1; TTS_EJ_ENTETES_TICKETS_MASSENA.ods / recettes_mensuelles_MASSENA_232425 | 44/24/12 | Q-CMP-Z1 | IDENTIQUE | **CONFORME** |
| 4 | `Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2025.ods` | `Compare_Montant_MASSENA_Z1ModeZZ1vsEJ_2025` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / Z1_TotalMontantParMoisAnnee_2025_ModeZZ1; TTS_EJ_ENTETES_TICKETS_MASSENA.ods / recettes_mensuelles_MASSENA_232425 | 38/14/8 | Q-CMP-Z1 | IDENTIQUE | **CONFORME** |
| 5 | `Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2023.ods` | `Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2023` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ1; TTS_EJ_ENTETES_TICKETS_MASSENA.ods / enct_mensuels_MASSENA_232425 | 44/24/12 | Q-CMP-Z2 | IDENTIQUE | **CONFORME** |
| 6 | `Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2024.ods` | `Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2024` | TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ1; TTS_EJ_ENTETES_TICKETS_MASSENA.ods / enct_mensuels_MASSENA_232425 | 44/24/12 | Q-CMP-Z2 | IDENTIQUE | **CONFORME** |
| 7 | `Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2025.ods` | `Compare_Montant_MASSENA_Z2ModeZZ1vsEJ_2025` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ1; TTS_EJ_ENTETES_TICKETS_MASSENA.ods / enct_mensuels_MASSENA_232425 | 38/14/8 | Q-CMP-Z2 | IDENTIQUE | **CONFORME** |
| 8 | `Compare_Montant_MATURIN_Z1ModeZvsEJ_2023.ods` | `Compare_Montant_MATURIN_Z1ModeZvsEJ_2023` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / Z1_TotalMontantParMoisAnnee_2023_ModeZ; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / recettes_mensuelles_MATURIN_232425 | 42/22/12 | Q-CMP-Z1 | IDENTIQUE | **CONFORME** |
| 9 | `Compare_Montant_MATURIN_Z1ModeZvsEJ_2024.ods` | `Compare_Montant_MATURIN_Z1ModeZvsEJ_2024` | TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods / Z1_TotalMontantParMoisAnnee_2024_ModeZ; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / recettes_mensuelles_MATURIN_232425 | 44/24/12 | Q-CMP-Z1 | IDENTIQUE | **CONFORME** |
| 10 | `Compare_Montant_MATURIN_Z1ModeZvsEJ_2025.ods` | `Compare_Montant_MATURIN_Z1ModeZvsEJ_2025` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / Z1_TotalMontantParMoisAnnee_2025_ModeZ; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / recettes_mensuelles_MATURIN_232425 | 37/13/8 | Q-CMP-Z1 | IDENTIQUE | **CONFORME** |
| 11 | `Compare_Montant_MATURIN_Z2ModeZVsEJ_2023.ods` | `Compare_Montant_MATURIN_Z2ModeZVsEJ_2023` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZ; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / enct_mensuels_MATURIN_232425 | 42/22/12 | Q-CMP-Z2 | IDENTIQUE | **CONFORME** |
| 12 | `Compare_Montant_MATURIN_Z2ModeZVsEJ_2024.ods` | `Compare_Montant_MATURIN_Z2ModeZVsEJ_2024` | TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZ; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / enct_mensuels_MATURIN_232425 | 44/24/12 | Q-CMP-Z2 | IDENTIQUE | **CONFORME** |
| 13 | `Compare_Montant_MATURIN_Z2ModeZVsEJ_2025.ods` | `Compare_Montant_MATURIN_Z2ModeZVsEJ_2025` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZ; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / enct_mensuels_MATURIN_232425 | 37/13/8 | Q-CMP-Z2 | IDENTIQUE | **CONFORME** |
| 14 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `ENTETES_TICKETS_MASSENA_0` | /app/output/travaux_preliminaires/EJ_ENTETES_TICKETS_MASSENA.csv | 1153/1153/1153 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 15 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `ENTETES_TICKETS_MASSENA_TriCrstNumInterne` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_0 | 1153/1153/1153 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 16 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `ENTETES_TICKETS_MASSENA_CtrlCoherenceEntete` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_TriCrstNumInterne | 1153/1153/1153 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 17 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `ENTETES_TICKETS_MASSENA_sequentialite` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_CtrlCoherenceEntete | 1153/1153/1153 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 18 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `TD_OccurenceNumInterne` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_sequentialite | 1153/1153/1153 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 19 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `DoublonNumInterne` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / TD_OccurenceNumInterne | 1153/1153/1153 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 20 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `TD_OccurenceNumTicket` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_sequentialite | 1153/1153/1153 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 21 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `DoublonNumTicket` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / TD_OccurenceNumTicket | 1153/1153/1153 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 22 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `ENTETES_TICKETS_MASSENA_CplteAnneeMoisTotalHT` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_TriCrstNumInterne | 1153/1153/1153 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 23 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `TD_TotalEnctTtc_ParAnneeMois` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_CplteAnneeMoisTotalHT | 1153/1153/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 24 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `enct_mensuels_MASSENA_232425` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / TD_TotalEnctTtc_ParAnneeMois | 32/32/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 25 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `TD_TotalHtTvaTtc_ParAnneeMois` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / ENTETES_TICKETS_MASSENA_CplteAnneeMoisTotalHT | 1153/1153/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 26 | `TTS_EJ_ENTETES_TICKETS_MASSENA.ods` | `recettes_mensuelles_MASSENA_232425` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / TD_TotalHtTvaTtc_ParAnneeMois | 32/32/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 27 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `ENTETES_TICKETS_MATURIN_0` | /app/output/travaux_preliminaires/EJ_ENTETES_TICKETS_MATURIN.csv | 722/722/722 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 28 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `ENTETES_TICKETS_MATURIN_TriCrstNumInterne` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_0 | 722/722/722 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 29 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `ENTETES_TICKETS_MATURIN_CtrlCoherenceEntete` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_TriCrstNumInterne | 722/722/722 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 30 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `ENTETES_TICKETS_MATURIN_sequentialite` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_CtrlCoherenceEntete | 722/722/722 | Q-EJ-ENTETE | IDENTIQUE | **CONFORME** |
| 31 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `TD_OccurenceNumInterne` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_sequentialite | 722/722/722 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 32 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `DoublonNumInterne` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / TD_OccurenceNumInterne | 722/722/722 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 33 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `TD_OccurenceNumTicket` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_sequentialite | 722/722/722 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 34 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `DoublonNumTicket` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / TD_OccurenceNumTicket | 722/722/722 | Q-EJ-DOUBLON | IDENTIQUE | **CONFORME** |
| 35 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `ENTETES_TICKETS_MATURIN_CplteAnneeMoisTotalHT` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_TriCrstNumInterne | 722/722/722 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 36 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `TD_TotalEnctTtc_ParAnneeMois` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_CplteAnneeMoisTotalHT | 722/722/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 37 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `enct_mensuels_MATURIN_232425` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / TD_TotalEnctTtc_ParAnneeMois | 32/32/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 38 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `TD_TotalHtTvaTtc_ParAnneeMois` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / ENTETES_TICKETS_MATURIN_CplteAnneeMoisTotalHT | 722/722/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 39 | `TTS_EJ_ENTETES_TICKETS_MATURIN.ods` | `recettes_mensuelles_MATURIN_232425` | TTS_EJ_ENTETES_TICKETS_MATURIN.ods / TD_TotalHtTvaTtc_ParAnneeMois | 32/32/32 | Q-EJ-MOIS | IDENTIQUE | **CONFORME** |
| 40 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `LIGNES_TICKETS_MASSENA_0` | /app/output/travaux_preliminaires/EJ_LIGNES_TICKETS_MASSENA.csv | 2521/2521/2521 | Q-EJ-LIGNE | valeur IDENTIQUE ; type numérique validé | **CONFORME** |
| 41 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `LIGNES_TICKETS_MASSENA_TriCrstNumInterne` | TTS_EJ_LIGNES_TICKETS_MASSENA.ods / LIGNES_TICKETS_MASSENA_0 | 2521/2521/2521 | Q-EJ-LIGNE | valeur IDENTIQUE ; type numérique validé | **CONFORME** |
| 42 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `LIGNES_TICKETS_MASSENA_CtrlCoherenceLigne` | TTS_EJ_LIGNES_TICKETS_MASSENA.ods / LIGNES_TICKETS_MASSENA_TriCrstNumInterne | 2521/2521/2521 | Q-EJ-LIGNE | valeur IDENTIQUE ; type numérique validé | **CONFORME** |
| 43 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `TD_OccurenceLibelleArticle` | TTS_EJ_LIGNES_TICKETS_MASSENA.ods / LIGNES_TICKETS_MASSENA_CtrlCoherenceLigne | 2521/2521/2 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 44 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `TD_OccurenceTxTvaArticle` | TTS_EJ_LIGNES_TICKETS_MASSENA.ods / LIGNES_TICKETS_MASSENA_CtrlCoherenceLigne | 2521/2521/2 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 45 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `TD_TotalLignesParNumTicket` | TTS_EJ_LIGNES_TICKETS_MASSENA.ods / LIGNES_TICKETS_MASSENA_CtrlCoherenceLigne | 2521/2521/1153 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 46 | `TTS_EJ_LIGNES_TICKETS_MASSENA.ods` | `CtrlCoherence_EnteteLigne` | TTS_EJ_LIGNES_TICKETS_MASSENA.ods / TD_TotalLignesParNumTicket | 1153/1153/1153 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 47 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `LIGNES_TICKETS_MATURIN_0` | /app/output/travaux_preliminaires/EJ_LIGNES_TICKETS_MATURIN.csv | 1610/1610/1610 | Q-EJ-LIGNE | valeur IDENTIQUE ; type numérique validé | **CONFORME** |
| 48 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `LIGNES_TICKETS_MATURIN_TriCrstNumInterne` | TTS_EJ_LIGNES_TICKETS_MATURIN.ods / LIGNES_TICKETS_MATURIN_0 | 1610/1610/1610 | Q-EJ-LIGNE | valeur IDENTIQUE ; type numérique validé | **CONFORME** |
| 49 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `LIGNES_TICKETS_MATURIN_CtrlCoherenceLigne` | TTS_EJ_LIGNES_TICKETS_MATURIN.ods / LIGNES_TICKETS_MATURIN_TriCrstNumInterne | 1610/1610/1610 | Q-EJ-LIGNE | valeur IDENTIQUE ; type numérique validé | **CONFORME** |
| 50 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `TD_OccurenceLibelleArticle` | TTS_EJ_LIGNES_TICKETS_MATURIN.ods / LIGNES_TICKETS_MATURIN_CtrlCoherenceLigne | 1610/1610/2 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 51 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `TD_OccurenceTxTvaArticle` | TTS_EJ_LIGNES_TICKETS_MATURIN.ods / LIGNES_TICKETS_MATURIN_CtrlCoherenceLigne | 1610/1610/2 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 52 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `TD_TotalLignesParNumTicket` | TTS_EJ_LIGNES_TICKETS_MATURIN.ods / LIGNES_TICKETS_MATURIN_CtrlCoherenceLigne | 1610/1610/722 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 53 | `TTS_EJ_LIGNES_TICKETS_MATURIN.ods` | `CtrlCoherence_EnteteLigne` | TTS_EJ_LIGNES_TICKETS_MATURIN.ods / TD_TotalLignesParNumTicket | 722/722/722 | Q-EJ-LIGNE-AGG | IDENTIQUE | **CONFORME** |
| 54 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `Z1_SyntheseMois_TOUS_2023_MASSENA_0` | /app/output/travaux_preliminaires/Z1_SyntheseMois_TOUS_2023_MASSENA.csv | 1025/1025/1025 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 55 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `Z1_SyntheseMois_TOUS_2023_MASSENA_CplteAnneeMoisZ` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / Z1_SyntheseMois_TOUS_2023_MASSENA_0 | 1025/1025/1025 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 56 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `TD_OccurenceEfichierEmodeParMoisAnnée_2023` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / Z1_SyntheseMois_TOUS_2023_MASSENA_CplteAnneeMoisZ | 1025/1025/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 57 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `TD_Z1_TotalMontantParMoisAnnee_2023` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / Z1_SyntheseMois_TOUS_2023_MASSENA_CplteAnneeMoisZ | 1025/41/1 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 58 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2023_ModeZZ1` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2023 | 1025/84/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 59 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2023_ModeZZ2` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2023 | 1025/84/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 60 | `TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2023_ModeZ` | TTS_Z1_SyntheseMois_TOUS_2023_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2023 | 1025/7/1 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 61 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `Z1_SyntheseMois_TOUS_2023_MATURIN_0` | /app/output/travaux_preliminaires/Z1_SyntheseMois_TOUS_2023_MATURIN.csv | 615/615/615 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 62 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `Z1_SyntheseMois_TOUS_2023_MATURIN_CplteAnneeMoisZ` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / Z1_SyntheseMois_TOUS_2023_MATURIN_0 | 615/615/615 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 63 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `TD_OccurenceEfichierEmodeParMoisAnnée_2023` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / Z1_SyntheseMois_TOUS_2023_MATURIN_CplteAnneeMoisZ | 615/615/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 64 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `TD_Z1_TotalMontantParMoisAnnee_2023` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / Z1_SyntheseMois_TOUS_2023_MATURIN_CplteAnneeMoisZ | 615/410/10 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 65 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2023_ModeZZ1` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2023 | 615/14/2 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 66 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2023_ModeZZ2` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2023 | 615/21/2 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 67 | `TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2023_ModeZ` | TTS_Z1_SyntheseMois_TOUS_2023_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2023 | 615/70/10 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 68 | `TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods` | `Z1_SyntheseMois_TOUS_2024_MASSENA_0` | /app/output/travaux_preliminaires/Z1_SyntheseMois_TOUS_2024_MASSENA.csv | 984/984/984 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 69 | `TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods` | `Z1_SyntheseMois_TOUS_2024_MASSENA_CplteAnneeMoisZ` | TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods / Z1_SyntheseMois_TOUS_2024_MASSENA_0 | 984/984/984 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 70 | `TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods` | `TD_OccurenceEfichierEmodeParMoisAnnée_2024` | TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods / Z1_SyntheseMois_TOUS_2024_MASSENA_CplteAnneeMoisZ | 984/984/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 71 | `TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods` | `TD_Z1_TotalMontantParMoisAnnee_2024` | TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods / Z1_SyntheseMois_TOUS_2024_MASSENA_CplteAnneeMoisZ | 984/492/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 72 | `TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2024_ModeZZ1` | TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2024 | 984/84/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 73 | `TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2024_ModeZZ2` | TTS_Z1_SyntheseMois_TOUS_2024_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2024 | 984/84/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 74 | `TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods` | `Z1_SyntheseMois_TOUS_2024_MATURIN_0` | /app/output/travaux_preliminaires/Z1_SyntheseMois_TOUS_2024_MATURIN.csv | 492/492/492 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 75 | `TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods` | `Z1_SyntheseMois_TOUS_2024_MATURIN_CplteAnneeMoisZ` | TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods / Z1_SyntheseMois_TOUS_2024_MATURIN_0 | 492/492/492 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 76 | `TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods` | `TD_OccurenceEfichierEmodeParMoisAnnée_2024` | TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods / Z1_SyntheseMois_TOUS_2024_MATURIN_CplteAnneeMoisZ | 492/492/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 77 | `TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods` | `TD_Z1_TotalMontantParMoisAnnee_2024` | TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods / Z1_SyntheseMois_TOUS_2024_MATURIN_CplteAnneeMoisZ | 492/492/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 78 | `TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2024_ModeZ` | TTS_Z1_SyntheseMois_TOUS_2024_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2024 | 492/84/12 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 79 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `Z1_SyntheseMois_TOUS_2025_MASSENA_0` | /app/output/travaux_preliminaires/Z1_SyntheseMois_TOUS_2025_MASSENA.csv | 533/533/533 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 80 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `Z1_SyntheseMois_TOUS_2025_MASSENA_CplteAnneeMoisZ` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / Z1_SyntheseMois_TOUS_2025_MASSENA_0 | 533/533/533 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 81 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `TD_OccurenceEfichierEmodeParMoisAnnée_2025` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / Z1_SyntheseMois_TOUS_2025_MASSENA_CplteAnneeMoisZ | 533/533/6 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 82 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `TD_Z1_TotalMontantParMoisAnnee_2025` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / Z1_SyntheseMois_TOUS_2025_MASSENA_CplteAnneeMoisZ | 533/41/1 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 83 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2025_ModeZZ1` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2025 | 533/42/6 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 84 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2025_ModeZZ2` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2025 | 533/42/6 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 85 | `TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods` | `Z1_TotalMontantParMoisAnnee_2025_ModeZ` | TTS_Z1_SyntheseMois_TOUS_2025_MASSENA.ods / TD_Z1_TotalMontantParMoisAnnee_2025 | 533/7/1 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 86 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `Z1_SyntheseMois_TOUS_2025_MATURIN_0` | /app/output/travaux_preliminaires/Z1_SyntheseMois_TOUS_2025_MATURIN.csv | 287/287/287 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 87 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `Z1_SyntheseMois_TOUS_2025_MATURIN_CplteAnneeMoisZ` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / Z1_SyntheseMois_TOUS_2025_MATURIN_0 | 287/287/287 | Q-Z1-DETAIL | IDENTIQUE | **CONFORME** |
| 88 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `TD_OccurenceEfichierEmodeParMoisAnnée_2025` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / Z1_SyntheseMois_TOUS_2025_MATURIN_CplteAnneeMoisZ | 287/287/6 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 89 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `TD_Z1_TotalMontantParMoisAnnee_2025` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / Z1_SyntheseMois_TOUS_2025_MATURIN_CplteAnneeMoisZ | 287/205/5 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 90 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2025_ModeZZ1` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2025 | 287/7/1 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 91 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2025_ModeZZ2` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2025 | 287/7/1 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 92 | `TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods` | `Z1_TotalMontantParMoisAnnee_2025_ModeZ` | TTS_Z1_SyntheseMois_TOUS_2025_MATURIN.ods / TD_Z1_TotalMontantParMoisAnnee_2025 | 287/35/5 | Q-Z1-AGG | IDENTIQUE | **CONFORME** |
| 93 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `Z2_TransactionsMois_TOUS_2023_MASSENA_0` | /app/output/travaux_preliminaires/Z2_TransactionsMois_TOUS_2023_MASSENA.csv | 1250/1250/1250 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 94 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `Z2_TransactionsMois_TOUS_2023_MASSENA_CplteAnneeMoisZ` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / Z2_TransactionsMois_TOUS_2023_MASSENA_0 | 1250/1250/1250 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 95 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `TD_TotalMontant_parMoisAnnee_parNatureTransaction` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / Z2_TransactionsMois_TOUS_2023_MASSENA_CplteAnneeMoisZ | 1250/50/2 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 96 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ1` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 1250/60/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 97 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ2` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 1250/60/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 98 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZ` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 1250/5/1 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 99 | `TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods` | `Compare_Montant_MASSENA_Z2_ModeZZ1vsModeZZ2_2023` | TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ1; TTS_Z2_TransactionsMois_TOUS_2023_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ2 | 24/24/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 100 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `Z2_TransactionsMois_TOUS_2023_MATURIN_0` | /app/output/travaux_preliminaires/Z2_TransactionsMois_TOUS_2023_MATURIN.csv | 750/750/750 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 101 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `Z2_TransactionsMois_TOUS_2023_MATURIN_CplteAnneeMoisZ` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / Z2_TransactionsMois_TOUS_2023_MATURIN_0 | 750/750/750 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 102 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `TD_TotalMontant_parMoisAnnee_parNatureTransaction` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / Z2_TransactionsMois_TOUS_2023_MATURIN_CplteAnneeMoisZ | 750/500/20 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 103 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ1` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 750/10/2 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 104 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ2` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 750/15/2 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 105 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZ` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 750/50/10 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 106 | `TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods` | `Compare_Montant_MATURIN_Z2_ModeZZ1vsModeZZ2_2023` | TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ1; TTS_Z2_TransactionsMois_TOUS_2023_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2023_ModeZZ2 | 4/4/2 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 107 | `TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods` | `Z2_TransactionsMois_TOUS_2024_MASSENA_0` | /app/output/travaux_preliminaires/Z2_TransactionsMois_TOUS_2024_MASSENA.csv | 1200/1200/1200 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 108 | `TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods` | `Z2_TransactionsMois_TOUS_2024_MASSENA_CplteAnneeMoisZ` | TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / Z2_TransactionsMois_TOUS_2024_MASSENA_0 | 1200/1200/1200 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 109 | `TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods` | `TD_TotalMontant_parMoisAnnee_parNatureTransaction` | TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / Z2_TransactionsMois_TOUS_2024_MASSENA_CplteAnneeMoisZ | 1200/600/24 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 110 | `TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ1` | TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 1200/60/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 111 | `TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ2` | TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 1200/60/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 112 | `TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods` | `Compare_Montant_MASSENA_Z2_ModeZZ1vsModeZZ2_2024` | TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ1; TTS_Z2_TransactionsMois_TOUS_2024_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZZ2 | 24/24/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 113 | `TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods` | `Z2_TransactionsMois_TOUS_2024_MATURIN_0` | /app/output/travaux_preliminaires/Z2_TransactionsMois_TOUS_2024_MATURIN.csv | 600/600/600 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 114 | `TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods` | `Z2_TransactionsMois_TOUS_2024_MATURIN_CplteAnneeMoisZ` | TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods / Z2_TransactionsMois_TOUS_2024_MATURIN_0 | 600/600/600 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 115 | `TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods` | `TD_TotalMontant_parMoisAnnee_parNatureTransaction` | TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods / Z2_TransactionsMois_TOUS_2024_MATURIN_CplteAnneeMoisZ | 600/600/24 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 116 | `TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2024_ModeZ` | TTS_Z2_TransactionsMois_TOUS_2024_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 600/60/12 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 117 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `Z2_TransactionsMois_TOUS_2025_MASSENA_0` | /app/output/travaux_preliminaires/Z2_TransactionsMois_TOUS_2025_MASSENA.csv | 650/650/650 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 118 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `Z2_TransactionsMois_TOUS_2025_MASSENA_CplteAnneeMoisZ` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / Z2_TransactionsMois_TOUS_2025_MASSENA_0 | 650/650/650 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 119 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `TD_TotalMontant_parMoisAnnee_parNatureTransaction` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / Z2_TransactionsMois_TOUS_2025_MASSENA_CplteAnneeMoisZ | 650/50/2 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 120 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ1` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 650/30/6 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 121 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ2` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 650/30/6 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 122 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZ` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 650/5/1 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 123 | `TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods` | `Compare_Montant_MASSENA_Z2_ModeZZ1vsModeZZ2_2025` | TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ1; TTS_Z2_TransactionsMois_TOUS_2025_MASSENA.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ2 | 12/12/6 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 124 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `Z2_TransactionsMois_TOUS_2025_MATURIN_0` | /app/output/travaux_preliminaires/Z2_TransactionsMois_TOUS_2025_MATURIN.csv | 350/350/350 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 125 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `Z2_TransactionsMois_TOUS_2025_MATURIN_CplteAnneeMoisZ` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / Z2_TransactionsMois_TOUS_2025_MATURIN_0 | 350/350/350 | Q-Z2-DETAIL | IDENTIQUE | **CONFORME** |
| 126 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `TD_TotalMontant_parMoisAnnee_parNatureTransaction` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / Z2_TransactionsMois_TOUS_2025_MATURIN_CplteAnneeMoisZ | 350/250/10 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 127 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ1` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 350/5/1 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 128 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ2` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 350/5/1 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 129 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZ` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / TD_TotalMontant_parMoisAnnee_parNatureTransaction | 350/25/5 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 130 | `TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods` | `Compare_Montant_MATURIN_Z2_ModeZZ1vsModeZZ2_2025` | TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ1; TTS_Z2_TransactionsMois_TOUS_2025_MATURIN.ods / Z2_TotalMontant_parMoisAnnee_parNatureTransaction_2025_ModeZZ2 | 2/2/1 | Q-Z2-AGG | IDENTIQUE | **CONFORME** |
| 131 | `recettes_mensuelles_tous_boutique_232425.ods` | `recettes_mensuelles_tous_boutique_232425` | TTS_EJ_ENTETES_TICKETS_MASSENA.ods / recettes_mensuelles_MASSENA_232425; TTS_EJ_ENTETES_TICKETS_MATURIN.ods / recettes_mensuelles_MATURIN_232425 | 64/64/32 | Q-CONSOL | IDENTIQUE | **CONFORME** |

## 8. Rapport d’exécution existant

Le fichier `output/rapport-d-execution.txt` régénéré contient exactement 131 entrées, soit une par feuille, avec les compteurs lus/sélectionnés/écrits et les totaux demandés. Les preuves SQL, les contrôles indépendants des clôtures et les pièces externes absentes sont documentés dans le présent rapport de conformité. **Conclusion : CONFORME AVEC RÉSERVE**, le rapport opérationnel et le rapport d’audit devant être lus ensemble.

## 9. Annexe A — catalogue des contrôles SQL

### Q-EJ-ENTETE — ticket détaillé

```sql
SELECT boutique, E_NUM_INTERNE, E_NUM_TICKET, E_DATE_TICKET, E_HEURE_TICKET,
       E_HT1, E_TVA1, E_TTC, E_MDP_CB, E_MDP_ESPECES, E_MDP_CHEQUES
FROM tickets
WHERE boutique = :boutique
  AND type IN ('REG','_R_F')
  AND NULLIF(TRIM(E_NUM_TICKET),'') IS NOT NULL
ORDER BY E_NUM_INTERNE
LIMIT 1;
```

Résultats échantillonnés : MASSENA 004517/003562 = 249,17 HT, 49,83 TVA, 299,00 TTC, 299,00 CB ; MATURIN 000977/000609 = 747,50 HT, 149,50 TVA, 897,00 TTC, 897,00 espèces. ODS : identique.

### Q-EJ-LIGNE — ligne d’article identifiable

```sql
SELECT t.boutique, t.E_NUM_INTERNE, t.E_NUM_TICKET,
       l.D_QUANTITE_ARTICLE, l.D_LIBELLE_ARTICLE,
       l.D_TAUX_TVA_ARTICLE, l.D_MONTANT_ARTICLE, l.D_CORRECTION
FROM lignes_ticket l JOIN tickets t ON t.id = l.ticket_id
WHERE t.boutique = :boutique
  AND t.E_NUM_INTERNE = :num_interne
ORDER BY l.id;
```

Échantillon MASSENA 004517 : 1 / DEPT001 / T1 / 299,00 / vide, valeurs identiques. Type ODS de la quantité : numérique, maintenu explicitement conformément à la décision métier du 23 août 2026.

### Q-EJ-DOUBLON — occurrences et doublons

```sql
SELECT E_NUM_INTERNE, COUNT(*) AS n
FROM tickets
WHERE boutique=:boutique AND type IN ('REG','_R_F')
  AND NULLIF(TRIM(E_NUM_TICKET),'') IS NOT NULL
GROUP BY E_NUM_INTERNE
ORDER BY E_NUM_INTERNE;
```

Le même contrôle est exécuté sur `E_NUM_TICKET`. Résultat : 1 153 clés MASSENA et 722 MATURIN, toutes d’occurrence 1 ; aucun doublon. ODS : identique.

### Q-EJ-MOIS — agrégats mensuels EJ

```sql
SELECT boutique, substr(E_DATE_TICKET,1,7) AS periode, COUNT(*) AS tickets,
       SUM(CAST(E_HT1 AS NUMERIC)) AS ht,
       SUM(CAST(E_TVA1 AS NUMERIC)) AS tva,
       SUM(CAST(E_TTC AS NUMERIC)) AS ttc,
       SUM(CAST(E_MDP_CB AS NUMERIC)) AS cb,
       SUM(CAST(E_MDP_CHEQUES AS NUMERIC)) AS cheques,
       SUM(CAST(E_MDP_ESPECES AS NUMERIC)) AS especes
FROM tickets
WHERE type IN ('REG','_R_F')
  AND NULLIF(TRIM(E_NUM_TICKET),'') IS NOT NULL
GROUP BY boutique, periode;
```

Exemple 2023-01 : MASSENA 121 tickets, HT 63 641,51, TVA 12 728,29, TTC 76 369,80, CB 15 385,00, chèques 6 042,00, espèces 54 942,80 ; MATURIN 32 tickets, HT 19 343,80, TVA 3 868,80, TTC 23 212,60, CB 17 964,60, espèces 5 248,00. ODS : identique.

### Q-EJ-LIGNE-AGG — agrégats articles et cohérence entête/ligne

```sql
SELECT t.E_NUM_TICKET, t.E_TTC, COUNT(l.id) AS lignes,
       SUM(CAST(l.D_MONTANT_ARTICLE AS NUMERIC)) AS montant_articles,
       SUM(CAST(COALESCE(l.D_CORRECTION,'0') AS NUMERIC)) AS corrections
FROM tickets t JOIN lignes_ticket l ON l.ticket_id=t.id
WHERE t.boutique=:boutique AND t.type IN ('REG','_R_F')
  AND NULLIF(TRIM(t.E_NUM_TICKET),'') IS NOT NULL
GROUP BY t.id, t.E_NUM_TICKET, t.E_TTC;
```

Les occurrences par libellé et taux sont également rejouées avec `GROUP BY`. Résultats : 2 521 lignes MASSENA et 1 610 MATURIN ; libellé DEPT001 2 516/1 601 ; taux T1 2 516/1 603. ODS : identique.

### Q-Z1-DETAIL — détail Z1

```sql
SELECT e.nom_fichier, e.boutique, e.E_MODE, e.E_COMPTEUR_Z,
       e.E_DATE, e.E_HEURE, l.D_ENREGISTREMENT,
       l.D_DESIGNATION, l.D_QUANTITE, l.D_MONTANT
FROM z1_entetes e JOIN z1_lignes l ON l.z1_entete_id=e.id
WHERE e.nom_fichier=:nom_fichier
ORDER BY l.id;
```

Les 96 entêtes et 3 936 lignes sont retrouvés. Les champs d’identification, dates, quantités et montants contrôlés sont identiques aux feuilles `_0` et `Cplte`. Les lots multi-mois sont affectés au dernier mois détecté.

### Q-Z1-AGG — agrégat Z1 par mode/période/désignation

```sql
SELECT e.boutique, e.E_MODE, e.nom_fichier, l.D_DESIGNATION,
       SUM(CAST(l.D_MONTANT AS NUMERIC)) AS montant
FROM z1_entetes e JOIN z1_lignes l ON l.z1_entete_id=e.id
WHERE e.boutique=:boutique AND e.E_MODE=:mode
GROUP BY e.boutique, e.E_MODE, e.nom_fichier, l.D_DESIGNATION;
```

Les montants au centime et les clés de période sont identiques. Les fichiers multi-mois sont portés sur le dernier mois : juin 2025 pour MASSENA et juillet 2025 pour MATURIN.

### Q-Z2-DETAIL — détail Z2

```sql
SELECT e.nom_fichier, e.boutique, e.E_MODE, e.E_COMPTEUR_Z,
       e.E_DATE, e.E_HEURE, l.D_ENREGISTREMENT,
       l.D_DESIGNATION, l.D_QUANTITE, l.D_MONTANT
FROM z2_entetes e JOIN z2_lignes l ON l.z2_entete_id=e.id
WHERE e.nom_fichier=:nom_fichier
ORDER BY l.id;
```

Les 96 entêtes et 4 800 lignes sont retrouvés. Valeurs et périodes identiques, y compris pour les deux lots multi-mois.

### Q-Z2-AGG — agrégat Z2 par mode/période/nature

```sql
SELECT e.boutique, e.E_MODE, e.nom_fichier, l.D_DESIGNATION,
       SUM(CAST(l.D_QUANTITE AS NUMERIC)) AS quantite,
       SUM(CAST(l.D_MONTANT AS NUMERIC)) AS montant
FROM z2_entetes e JOIN z2_lignes l ON l.z2_entete_id=e.id
WHERE e.boutique=:boutique AND e.E_MODE=:mode
  AND l.D_DESIGNATION IN ('CARTES','CHEQUES','CORRECTION','ESPECES','REF./TIROIR')
GROUP BY e.boutique, e.E_MODE, e.nom_fichier, l.D_DESIGNATION;
```

Montants et périodes identiques, y compris sur les lots multi-mois.

### Q-CMP-Z1 — comparaison indépendante Z1/EJ

Le côté Z1 est recalculé avec Q-Z1-AGG (`CA NET`, `HORS TAXE 1`, `TVA 1`) et le côté EJ avec Q-EJ-MOIS ; l’écart est recalculé en `Decimal`. Exemple clôture MASSENA 0061 : TTC 76 369,80/76 369,80, HT 63 641,51/63 641,51, TVA 12 728,29/12 728,29 — IDENTIQUE.

### Q-CMP-Z2 — comparaison indépendante Z2/EJ

Le côté Z2 est recalculé avec Q-Z2-AGG (`CARTES`, `CHEQUES`, `ESPECES`) et le côté EJ avec Q-EJ-MOIS. Une période absente de Z produit six cellules quantité/écart vides. Contrôles conformes pour MATURIN 2023-11, 2023-12, 2025-04 et 2025-05. Juin 2025 est couvert par le lot `062025_072025` clôturé en juillet ; juillet porte bien les valeurs Z.

### Q-CONSOL — consolidation des deux boutiques

```sql
SELECT substr(E_DATE_TICKET,1,7) AS periode, boutique,
       SUM(CAST(E_HT1 AS NUMERIC)) AS ht,
       SUM(CAST(E_TVA1 AS NUMERIC)) AS tva,
       SUM(CAST(E_TTC AS NUMERIC)) AS ttc
FROM tickets
WHERE type IN ('REG','_R_F')
  AND NULLIF(TRIM(E_NUM_TICKET),'') IS NOT NULL
GROUP BY periode, boutique;
```

Les deux lignes boutique sont additionnées par période. Total des 32 périodes : HT 1 097 325,15 ; TVA 219 465,45 ; TTC 1 316 790,60. ODS : identique.

### Q-CA3 — côté Gesco de la comparaison CA3

Même requête que Q-CONSOL, puis comparaison aux colonnes CA3. Le côté Gesco est identique ; les colonnes `MTT_HT_CA3`, `MTT_HT_20_CA3`, `MTT_TVA_20_CA3` et les deux écarts sont vides sur 32 lignes. Résultat : NON VÉRIFIABLE — PIÈCE CLIENT NON FOURNIE.

### Q-CLOTURE — rapprochement indépendant entre deux clôtures

```sql
SELECT E_HT1,E_TVA1,E_TTC,E_MDP_CB,E_MDP_CHEQUES,E_MDP_ESPECES
FROM tickets
WHERE boutique=:boutique
  AND type IN ('REG','_R_F')
  AND NULLIF(TRIM(E_NUM_TICKET),'') IS NOT NULL
  AND datetime(E_DATE_TICKET||' '||E_HEURE_TICKET)>:cloture_precedente
  AND datetime(E_DATE_TICKET||' '||E_HEURE_TICKET)<=:cloture_courante;
```

Les lignes sont additionnées en `Decimal` puis comparées à Z1 et Z2. Résultat : 57/57 IDENTIQUE.

## 10. Critères finaux

- Structure, colonnes, lignes, filiation et formules : conformes hors anomalies listées.
- Types : `D_QUANTITE_ARTICLE` est numérique dans les six feuilles concernées, conformément à la décision métier explicite ; les autres types contrôlés sont conformes.
- Contrôles SQL : au moins une preuve référencée pour chacune des 131 feuilles ; CA3 contrôlable seulement côté Gesco.
- Données absentes : correctement vides pour CA3 et pour les comparaisons Z1/Z2 ; aucun zéro ni écart n’est inventé quand une source mensuelle est absente.
- Lots multi-mois : conformes, dernier mois retenu comme mois de clôture.
- Données externes : aucune FEC, CA3 ou règle justificative inventée.
- Anomalies sources : aucune détectée par le rapprochement indépendant des 57 clôtures.

**Verdict final : CONFORME AVEC RÉSERVE. Les 130 feuilles vérifiables, les lots multi-mois et les comparaisons Z1/Z2 sont conformes ; la feuille CA3 reste non vérifiable faute de déclarations, et le rapport d’exécution opérationnel est complété par le présent rapport d’audit.**
