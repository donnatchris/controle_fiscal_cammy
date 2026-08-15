# Cahier des charges fiscal 751 - synthèse opératoire

Source : `fichiers_sources/751 - CAMMY FRANCE DEVELOPPEMENT LTD.pdf`, scan de 36 pages daté du 16 juillet 2026. Les pages 1 à 25 portent les exigences ; les pages 26 à 36 forment l'annexe d'inventaire. Le PDF ne contient pas de couche texte : relire visuellement la page source avant toute interprétation litigieuse.

## Cadre et échéance

- Contrôle fondé sur l'article L.47 A-II b du LPF.
- Périmètre : CAMMY FRANCE DEVELOPPEMENT LTD, boutiques MASSENA et MATURIN.
- Périodes : 01/01/2023-31/12/2023, 01/01/2024-31/12/2024 et 01/01/2025-31/08/2025.
- Date limite indiquée : 28/08/2026.
- Objectifs : règles de facturation, CA réalisé, TVA collectée, règlements, comparaison aux déclarations et procédures de correction/annulation.

## Modalités de preuve et de livraison

- Sauvegarder les enregistrements utilisés pendant le contrôle.
- Remettre les résultats sous forme dématérialisée conforme à l'article A.47 A-2 du LPF, sur USB ou plateforme sécurisée ; autoriser un ZIP.
- Fournir en double exemplaire le rapport d'exécution, le programme et les résultats, dont un exemplaire au vérificateur.
- Fournir un descriptif des zones et règles de gestion.
- Afficher, par état et fichier, les nombres d'enregistrements lus, sélectionnés et écrits, ainsi qu'un total global des montants numériques.
- Exprimer les résultats en euros avec virgule comme séparateur décimal.
- Uniformiser les sorties et laisser vide tout champ non géré ou absent.
- Présenter négativement les montants qui annulent ou corrigent, notamment retours et avoirs.

## Sources attendues

- Journaux électroniques : `EJJMMAA.txt`.
- Rapports Z de synthèse : CSV dont le nom commence par `Z`, avec huit lignes d'entête, une ligne de titre puis des données.
- Écritures comptables : FEC 2023, 2024 et 2025 mentionnés par le cahier des charges, à fournir séparément s'ils ne figurent pas dans les sources.
- Annexe 1 : arborescence des exports par boutique, exercice et période, avec contenu fonctionnel des fichiers.

## Sorties EJ

Produire un fichier par boutique pour les entêtes et un pour les lignes :

- `EJ_ENTETES_TICKETS_MASSENA`
- `EJ_ENTETES_TICKETS_MATURIN`
- `EJ_LIGNES_TICKETS_MASSENA`
- `EJ_LIGNES_TICKETS_MATURIN`

Un ticket de vente correspond à un enregistrement d'entête. Répéter les données d'entête devant chaque ligne de détail.

Champs d'entête :

`nomfichier`, `E_NUM_INTERNE`, `E_NUM_TICKET`, `E_DATE_TICKET`, `E_HEURE_TICKET`, `E_HT1`, `E_HT2`, `E_HT3`, `E_HT4`, `E_TVA1`, `E_TVA2`, `E_TVA3`, `E_TVA4`, `E_HT_NON_TAXABLE`, `E_TTC`, `E_MDP_CB`, `E_MDP_ESPECES`, `E_MDP_CHEQUES`.

Champs de détail ajoutés :

`D_QUANTITE_ARTICLE`, `D_LIBELLE_ARTICLE`, `D_TAUX_TVA_ARTICLE`, `D_MONTANT_ARTICLE`, `D_CORRECTION`, `D_AUTRE_INFO`.

## Sorties Z

Assembler les CSV par nature, boutique et exercice :

- `Z1_SyntheseMois_TOUS_AAAA_BOUTIQUE`
- `Z2_TransactionsMois_TOUS_AAAA_BOUTIQUE`

Champs :

`nomfichier`, `E_MODELE`, `E_MACHINE`, `E_RAPPORT`, `E_FICHIER`, `E_MODE`, `E_COMPTEUR_Z`, `E_DATE`, `E_HEURE`, `D_ENREGISTREMENT`, `D_DESIGNATION`, `D_QUANTITE`, `D_MONTANT`.

Conserver les modes `Z`, `ZZ1` et `ZZ2`. Appliquer les règles par boutique et exercice depuis une configuration explicite ; ne pas les déduire silencieusement. Identifier les fichiers couvrant plusieurs mois.

## Contrôles et formules imposés

### Entêtes EJ

- Calculer `AI_TVA1_CALCULE = E_HT1 * 20 %`.
- Calculer `AI_ECART_TVA1 = E_TVA1 - AI_TVA1_CALCULE`.
- Calculer `AI_TTC_CALCULE = E_HT1 + E_TVA1`.
- Calculer `AI_ECART_TTC = E_TTC - AI_TTC_CALCULE`.
- Calculer `AI_SOLDE_DU = E_TTC - (E_MDP_CB + E_MDP_CHEQUES)` selon la formule du cahier des charges.
- Trier par `E_NUM_INTERNE`, analyser les ruptures de `E_NUM_TICKET` et de chronologie, puis justifier toute rupture.
- Rechercher les doublons de `E_NUM_INTERNE` et de `E_NUM_TICKET`.

### Cohérence entête-lignes

- Grouper par ticket les quantités, montants d'article et corrections.
- Calculer `AI_ECART_TTC = E_TTC - (somme D_MONTANT_ARTICLE + somme D_CORRECTION)`.
- Compter les occurrences de `D_LIBELLE_ARTICLE` et de `D_TAUX_TVA_ARTICLE`.

### CA, TVA et règlements

- Agréger Z2 par année, mois et nature de transaction, puis comparer les modes requis.
- Agréger Z1 par année, mois et `D_DESIGNATION`, notamment `CA BRUT`, `CA NET`, `CB.TIROIR`, `CHQ.TIROIR`, `ESP.TIROIR`, `HORS TAXES 1` et `TVA 1` selon les libellés réels.
- Calculer depuis les EJ les montants mensuels HT, TVA, TTC et règlements par boutique.
- Comparer les agrégats EJ aux rapports Z retenus, puis réunir MASSENA et MATURIN dans les recettes mensuelles toutes boutiques.
- Comparer ensuite les recettes reconstituées aux déclarations CA3 uniquement si celles-ci sont fournies.

## Corrections et annulations

Le cahier des charges constate que les données communiquées ne contiennent pas les éléments de traçabilité et de paramétrage nécessaires à l'analyse complète des procédures de correction/annulation. Signaler cette limite et demander les justificatifs ; ne jamais combler ce manque par une hypothèse non sourcée.
