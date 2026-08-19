# Reprise fiscale 751

Le traitement reconstruit la base SQLite à partir des journaux électroniques EJ et des rapports Z, puis produit les CSV de travail et les contrôles associés.

Pour exécuter le pipeline :

```bash
uv run traitement
```

Les sorties courantes sont :

- `database/db.sqlite` : base SQLite reconstruite ;
- `output/travaux_preliminaires/` : CSV dérivés, séparés par `|` ;
- `controle/` : rapport de reconstruction et contrôles techniques.

La production des classeurs `.ods` avec LibreOffice sera ajoutée dans une étape dédiée. Le registre contractuel des 18 futurs classeurs est conservé dans `src/shared/constantes.py` et porte désormais l’extension `.ods`.
