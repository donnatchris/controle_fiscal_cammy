# Contenu du rapport de conformité

Le rapport doit être autonome, factuel et reproductible. Écrire les résultats constatés ; ne reprendre aucun verdict historique sans rejouer les contrôles.

## Sections requises

1. Résumé exécutif : verdict global et décompte exact des quatre statuts.
2. Méthodologie et périmètre : chaîne contrôlée, reconstruction, empreintes, tests et limites d'environnement.
3. Inventaire SQLite : six tables, volumes, intégrité, clés étrangères et agrégats transversaux.
4. Données et pièces absentes : FEC, CA3, corrections/annulations et périodes sans mode Z avec le statut approprié.
5. Lots multi-mois et comparaisons mensuelles : mois attendu, mois ODS, effet et qualification.
6. Tableau exhaustif des clôtures : boutique, compteur Z, bornes, tickets, six montants EJ/Z et résultat.
7. Matrice exhaustive des 131 feuilles : classeur, feuille, source immédiate, lus/sélectionnés/écrits, identifiant de preuve SQL, résultat et conclusion.
8. Rapport d'exécution : couverture et éventuelles informations apportées par le rapport d'audit.
9. Catalogue des requêtes SQL : requêtes ou patrons complets, paramètres, échantillons et résultats.
10. Critères finaux et verdict.

## Règles de preuve

- Une ligne de matrice doit correspondre à une feuille réelle et à une preuve SQL applicable. Pour une feuille non raccordable, expliquer précisément pourquoi.
- Utiliser des identifiants stables comme `Q-EJ-ENTETE`, `Q-EJ-AGG`, `Q-Z1-DETAIL`, `Q-Z1-AGG`, `Q-Z2-DETAIL`, `Q-Z2-AGG`, `Q-CMP-Z1`, `Q-CMP-Z2`, `Q-CLOTURE`, `Q-CONSOL` et `Q-CA3`.
- Présenter les montants avec une précision au centime. Tolérer uniquement les résidus binaires strictement inférieurs à 0,005 € et documenter cette normalisation.
- Pour toute différence, indiquer le fichier, la feuille, la clé ou période, les deux valeurs et la cause technique si elle est démontrée.
- Ne pas qualifier une feuille `CONFORME` si une preuve applicable manque.

## Statuts

La conclusion par feuille est exactement l'une de ces valeurs :

- `CONFORME`
- `CONFORME AVEC RÉSERVE`
- `NON CONFORME`
- `NON VÉRIFIABLE`

Le verdict global peut être `CONFORME AVEC RÉSERVE` lorsque toutes les feuilles vérifiables sont conformes mais que des pièces client absentes empêchent certains contrôles. Une pièce externe absente, à elle seule, ne justifie jamais `NON CONFORME`.
