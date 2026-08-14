# Carte du projet et autorité des artefacts

## Source de vérité active

- `traitement_chris/fichiers_sources/` : PDF contractuel et six dossiers de données brutes. Considérer ce répertoire comme immuable.
- `traitement_chris/src/` : implémentation Python active en cours de développement.
- `traitement_chris/tests/` : tests Python actifs.
- `traitement_chris/database/` et `traitement_chris/output/` : données dérivées régénérables ; ne pas les confondre avec les sources.
- `traitement_chris/pyproject.toml` : Python >= 3.12, pandas, openpyxl et pytest via uv.

## Référence historique non canonique

`traitement_marco/` est ignoré par Git et contient une reprise JavaScript, des contrôles et des packages historiques. L'utiliser pour comprendre les règles, retrouver une méthode et comparer les baselines. Ne pas le présenter comme preuve du code Python courant et ne pas le modifier comme substitut à l'implémentation active.

La reprise historique contient notamment :

- `reprise_751/src/ej_pipeline.mjs` : classification exhaustive des blocs EJ et provenance.
- `reprise_751/src/z_pipeline.mjs` : parsing Z1/Z2 et règles de modes.
- `reprise_751/src/reconciliation.mjs` : rapprochement entre clôtures successives.
- `reprise_751/config/regles_modes_z.json` : choix explicites de modes par boutique/exercice.
- `outputs/.../controle/` : résumés et portes qualité d'une exécution antérieure.

## État observé lors de la création du skill

- Sources actives : 63 TXT EJ, 449 CSV Z et 1 PDF explicatif dans les six dossiers, soit 513 fichiers ; le cahier des charges principal est à la racine de `fichiers_sources/`.
- Base SQLite active : 2 511 lignes `tickets` et 4 130 lignes `lignes_ticket`.
- Baseline historique : 1 875 tickets de vente, 4 131 lignes, 35 retours `_R_F` pour -19 821,00 EUR, 57 rapprochements de clôtures concordants et quatre périodes sans clôture Z.
- Le résumé historique annonce 519 fichiers, dont 7 `AUTRE`, alors que l'arborescence active observée en contient 513, dont un PDF explicatif. Vérifier les empreintes et expliquer cet écart avant de réutiliser cette baseline.
- Les FEC 2023-2025, les CA3 et les justificatifs de correction/annulation sont signalés comme absents de la livraison historique.

Ces chiffres servent à détecter une régression, pas à la masquer. Recalculer depuis les sources actives et documenter toute différence.

## Règles de développement

- Préserver le worktree sale : examiner `git status` avant toute modification et ne pas écraser les changements existants.
- Préférer des fonctions pures de parsing et d'agrégation, avec tests sur des extraits minimaux.
- Conserver les montants en `Decimal` dans Python ou en centimes entiers dans JavaScript/SQLite de calcul.
- Rendre les scripts non interactifs pour les exécutions automatisées ; utiliser des répertoires de sortie isolés.
- Écrire les sorties atomiquement lorsque leur remplacement peut interrompre une livraison.
- Inclure une colonne de provenance ou un lien déterministe vers la source pour chaque enregistrement normalisé.
- Ne jamais faire dépendre la conformité d'un classeur Excel non testé comme seule implémentation d'une formule métier.

## Commandes usuelles

Depuis `traitement_chris/` :

```bash
uv run pytest -v
uv run python src/scripts/ej_vers_db.py fichiers_sources database/db.sqlite
uv run python src/scripts/db_ej_vers_xlsx.py
```

Lancer la reconstruction destructive de la base uniquement après avoir confirmé la cible exacte et protégé tout résultat utilisateur utile.

Depuis la racine du dépôt, auditer sans mutation :

```bash
python3 .agents/skills/piloter-reprise-fiscale-751/scripts/audit_project.py
```
