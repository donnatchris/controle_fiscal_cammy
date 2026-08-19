# Reprise fiscale 751

Le traitement reconstruit la base SQLite à partir des journaux électroniques EJ et des rapports Z, puis produit les CSV de travail.

Pour exécuter le pipeline :

```bash
uv run traitement
```

Les sorties courantes sont :

- `database/db.sqlite` : base SQLite reconstruite ;
- `output/travaux_preliminaires/` : CSV dérivés, séparés par `|` ;

Le traitement génère également, par LibreOffice et PyUNO, les deux classeurs `EJ_ENTETES_TICKETS_MASSENA.ods` et `EJ_ENTETES_TICKETS_MATURIN.ods` dans `output/libreoffice/`. Chacun contient uniquement sa feuille d'entrée `ENTETES_TICKETS_<BOUTIQUE>_0`. Le registre contractuel des futurs classeurs est conservé dans `src/shared/constantes.py`.
