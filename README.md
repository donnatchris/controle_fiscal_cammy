# Traitement fiscal des données de caisse - dossier 751

Ce projet Python reconstruit une base SQLite exhaustive à partir des journaux électroniques EJ et des rapports Z, exécute les contrôles demandés par le cahier des charges, puis génère les 18 classeurs Excel contractuels et un rapport PDF d'analyse destiné à l'administration fiscale.

Le programme actif se trouve intégralement dans `src/`. Le dossier `output/` est réservé aux 19 livrables à remettre : 18 classeurs et le rapport PDF. Il ne contient ni code, ni données intermédiaires, ni fichiers de contrôle technique.

## Périmètre

- Société : CAMMY FRANCE DEVELOPPEMENT LTD.
- Boutiques : MASSENA et MATURIN.
- Exercices : 2023, 2024 et janvier à août 2025.
- Sources actives : 63 fichiers EJ, 449 fichiers CSV Z, une notice explicative et le cahier des charges PDF, soit 514 fichiers au total (hors `.DS_Store`).
- Données attendues après reconstruction : 2 511 blocs EJ, 4 131 lignes de détail, 96 fichiers Z1 et 96 fichiers Z2.

Le traitement couvre actuellement le périmètre caisse EJ/Z. Les FEC, les déclarations CA3 et les justificatifs externes de correction ou d'annulation ne sont pas présents. Le statut maximal est donc `CONFORME SUR LE PÉRIMÈTRE CAISSE - À COMPLÉTER`.

## Stratégie complète du traitement

Le point d'entrée `traitement` exécute le workflow suivant dans l'ordre.

### 1. Inventaire et protection des sources

Le programme parcourt récursivement `fichiers_sources/` et calcule une empreinte SHA-256 de chaque fichier EJ et Z avant le parsing. Les empreintes sont recalculées après la reconstruction afin de vérifier qu'aucune source n'a été modifiée pendant le traitement.

Les sources sont immuables : le programme ne les renomme, ne les corrige et ne les réécrit jamais.

### 2. Reconstruction isolée de SQLite

Une base temporaire neuve est créée à côté de `database/db.sqlite`. Le traitement y crée six tables :

- `tickets` et `lignes_ticket` pour les EJ ;
- `z1_entetes` et `z1_lignes` pour les rapports de synthèse Z1 ;
- `z2_entetes` et `z2_lignes` pour les transactions Z2.

Les montants sont parsés avec `Decimal` et stockés en texte décimal dans SQLite afin d'éviter les arrondis binaires des nombres flottants.

### 3. Parsing exhaustif des EJ

Les fichiers `EJ*.TXT` sont lus en Windows-1252 (`cp1252`), découpés en blocs, puis convertis en entêtes et lignes de ticket.

La base conserve tous les types rencontrés, notamment `REG`, `_R_F`, `X`, `XZ` et `Z`, avec leur type, événement, signature, numéro interne, date, heure, boutique et fichier d'origine. L'absence de numéro de facture ne provoque pas la suppression d'un bloc.

Les lignes article conservent l'indicateur source de TVA (`T1`, `T2`, etc.). Le taux de 20 % n'est employé que dans la formule de contrôle demandée pour `E_HT1`.

Les montants économiques des tickets `_R_F` de vente sont enregistrés négativement, y compris HT, TVA, TTC, règlements, montants d'article et corrections. Les 35 retours de vente restent présents et totalisent -19 821,00 EUR TTC.

### 4. Parsing des rapports Z1 et Z2

Les CSV Z sont également lus en Windows-1252. Les huit lignes d'entête et les lignes de données sont normalisées puis enregistrées dans les tables Z1 et Z2.

Les modes `Z`, `ZZ1` et `ZZ2` restent disponibles dans la base. Le mode utilisé pour un rapprochement n'est pas deviné : il est défini par boutique et exercice dans `config/regles_modes_z.json`. Les noms de fichiers pouvant contenir plusieurs mois sont analysés sans réduire silencieusement leur période.

### 5. Validation et publication atomique

La base temporaire doit satisfaire les invariants suivants avant de remplacer la base active :

- 2 511 blocs EJ et 4 131 lignes de détail ;
- 1 875 tickets de vente, dont 1 153 MASSENA et 722 MATURIN ;
- 35 retours `_R_F` de vente pour -19 821,00 EUR TTC ;
- 96 entêtes Z1 et 3 936 lignes Z1 ;
- 96 entêtes Z2 et 4 800 lignes Z2 ;
- aucune erreur de clé étrangère ;
- aucune modification des sources.

Si un contrôle échoue, la base temporaire est supprimée et la base active reste inchangée. Si tous les contrôles passent, l'ancienne base est sauvegardée sous la forme `database/db.sqlite.bak_AAAAMMJJ_HHMMSS`, puis la nouvelle base est publiée atomiquement comme `database/db.sqlite`.

### 6. Préparation des données intermédiaires

Le programme interroge SQLite et écrit 16 CSV dans `staging/` :

- quatre jeux EJ, entêtes et lignes pour chaque boutique ;
- six jeux Z1, un par boutique et exercice ;
- six jeux Z2, un par boutique et exercice.

Ces CSV servent uniquement d'interface déterministe entre SQLite et le générateur Excel. Ils ne font pas partie de la livraison.

Pour les exports de ventes EJ, la sélection est strictement limitée aux blocs `REG` et `_R_F` dont `E_NUM_TICKET` est renseigné. Les 636 autres blocs restent dans SQLite et sont inventoriés comme non sélectionnés, sans être qualifiés d'erreurs.

### 7. Contrôles et rapprochements

Les contrôles techniques sont écrits dans `controle/`. Ils couvrent notamment :

- l'inventaire des types de blocs EJ ;
- la justification des blocs non sélectionnés dans les ventes ;
- les volumes lus, sélectionnés et écrits ;
- la couverture des périodes Z et les fichiers multi-mois ;
- les rapprochements EJ/Z entre clôtures successives ;
- les totaux TTC, HT, TVA, carte, chèques et espèces ;
- les empreintes SHA-256 des classeurs générés.

La baseline actuelle comporte 57 rapprochements de clôture conformes sur 57, 60 périodes avec clôture, quatre périodes sans clôture et aucune période ambiguë. Une période sans clôture est documentée comme un fait d'exploitation ; le programme n'invente jamais un fichier Z absent.

### 8. Construction des classeurs Excel

Les 18 classeurs sont générés en Python avec `openpyxl`. Ils comprennent :

- quatre classeurs EJ : entêtes et lignes pour MASSENA et MATURIN ;
- six classeurs Z1 : un par boutique et exercice ;
- six classeurs Z2 : un par boutique et exercice ;
- un classeur de recettes mensuelles consolidées ;
- un classeur de comparaison avec les CA3, dont les zones externes restent vides tant que les déclarations ne sont pas fournies.

Les feuilles de contrôle du cahier des charges sont intégrées aux classeurs : cohérence, tri, séquentialité, doublons, occurrences, agrégations mensuelles et rapprochements. Les champs absents restent vides et les dates EJ sont exportées au format `yyyymmdd`.

Le générateur relit chaque classeur après sauvegarde et vérifie les noms et l'ordre des feuilles. Il exige les 18 fichiers `.xlsx` attendus et refuse tout fichier étranger à la livraison.

### 9. Rapport d'analyse fiscale

Le programme recalcule directement depuis SQLite la séquentialité de `E_NUM_INTERNE` et `E_NUM_TICKET`, les doublons, la chronologie, les égalités monétaires et les totaux annuels. Il relit également les rapprochements EJ/Z et la structure des 18 classeurs.

Il produit `output/RAPPORT_ANALYSE_FISCALE_751.pdf`. Le rapport distingue :

- les contrôles sans anomalie inexpliquée ;
- les écarts apparents expliqués, notamment les numéros internes des blocs administratifs absents des seuls exports de ventes ;
- les points à documenter, dont les quatre périodes MATURIN sans clôture Z étiquetée ;
- les contrôles impossibles tant que les FEC, CA3 et justificatifs externes ne sont pas fournis.

Le statut reste volontairement limité à `CONFORME SUR LE PÉRIMÈTRE CAISSE - À COMPLÉTER`.

### 10. Contrôle visuel optionnel

Avec l'option `--qa`, chaque feuille est rendue en PNG par LibreOffice et Poppler. Les 135 images sont placées dans `controle/qa_previews/` et servent uniquement à vérifier la lisibilité et la mise en page. Elles ne sont jamais copiées dans `output/` et ne font pas partie de la livraison contractuelle.

## Architecture du projet

```text
├── src/                         Programme Python actif
│   ├── traitement.py            Point d'entrée du workflow complet
│   ├── classes/                  Modèles et parseurs EJ/Z
│   ├── scripts/                  Reconstruction, exports, contrôles et Excel
│   └── shared/                   Constantes et fonctions partagées
├── tests/                        Tests automatisés, hors du programme
│   └── unit/                     Tests unitaires des parseurs et traitements
├── fichiers_sources/             Sources EJ/Z et cahier des charges, immuables
├── config/                       Règles explicites de sélection des modes Z
├── database/                     Base SQLite active et sauvegardes horodatées
├── staging/                      16 CSV intermédiaires régénérables
├── controle/                     Preuves et diagnostics techniques
│   └── qa_previews/              135 PNG optionnels produits avec --qa
├── output/                       18 classeurs contractuels et rapport PDF
├── pyproject.toml                Dépendances et commande `traitement`
├── uv.lock                       Versions Python verrouillées
└── README.md                     Documentation d'exploitation
```

### Contenu de `src/`

- `src/traitement.py` orchestre toutes les étapes.
- `src/classes/ticket.py` parse les blocs EJ et applique le signe négatif aux retours `_R_F`.
- `src/classes/z.py` représente les rapports Z et leurs lignes.
- `src/scripts/reconstruire_base_751.py` construit, contrôle et publie SQLite.
- `src/scripts/ej_vers_db.py` charge tous les blocs EJ dans SQLite.
- `src/scripts/z1_vers_db.py` et `src/scripts/z2_vers_db.py` chargent les rapports Z.
- `src/scripts/db_vers_csv_751.py` produit le staging et les rapprochements.
- `src/scripts/construire_classeurs_751.py` construit les 18 classeurs.
- `src/scripts/db_ej_vers_xlsx.py` orchestre les exports et vérifie `output/`.
- `src/scripts/generer_rapport_fiscal_751.py` recalcule les constats et produit le PDF fiscal.

### Contenu de `controle/`

Ce dossier est interne au traitement et n'est pas remis comme résultat Excel. Il contient notamment :

- `rapport_reconstruction_751.json` : validation de la base avant publication ;
- `RESUME_EXPORT_751.json` : volumes et statut du périmètre caisse ;
- `RAPPORT_CONTROLES_751.md` : synthèse lisible des contrôles ;
- `INVENTAIRE_TYPES_BLOCS_EJ.csv` : inventaire exhaustif des types ;
- `BLOCS_EXCLUS_EXPORTS_VENTES.csv` : blocs non sélectionnés et motifs ;
- `CONTROLE_COUVERTURE_PERIODES_Z.csv` : présence des clôtures par période ;
- `RAPPROCHEMENT_PAR_CLOTURE_EJ_Z.csv` : comparaison détaillée EJ/Z ;
- `MANIFESTE_CONTROLE_751.json` : structure et SHA-256 des 18 classeurs ;
- `qa_previews/` : rendus visuels optionnels.

### Contenu de `output/`

`output/` contient exactement :

- 4 classeurs `TTS_EJ_*.xlsx` ;
- 6 classeurs `TTS_Z1_*.xlsx` ;
- 6 classeurs `TTS_Z2_*.xlsx` ;
- `recettes_mensuelles_tous_boutique_232425.xlsx` ;
- `CompareCA_Gesco_CA3.xlsx`.
- `RAPPORT_ANALYSE_FISCALE_751.pdf` : analyse, anomalies expliquées, limites et conclusion.

Aucun programme, manifeste, JSON, CSV, aperçu PNG ou sous-dossier n'est admis dans `output/`.

## Prérequis

Le traitement standard nécessite :

- Python 3.12 ou supérieur ;
- `uv` pour créer l'environnement et installer les dépendances verrouillées.

Vérification :

```bash
python3 --version
uv --version
```

Installation :

```bash
uv sync
```

Node.js n'est pas nécessaire. Le mode optionnel `--qa` nécessite en plus LibreOffice (`soffice`) et Poppler (`pdftoppm`).

## Exécution

Toutes les commandes suivantes sont à lancer depuis la racine du projet, c'est-à-dire le dossier contenant `pyproject.toml`.

### Traitement complet

```bash
uv run traitement
```

Cette commande reconstruit la base, publie `database/db.sqlite`, régénère le staging et les contrôles, remplace les 18 classeurs attendus puis recrée le rapport PDF dans `output/`.

### Traitement complet avec contrôle visuel

```bash
uv run traitement --qa
```

### Chemins personnalisés

```bash
uv run traitement \
  fichiers_sources \
  database/db.sqlite \
  --sortie output \
  --staging staging \
  --controle controle \
  --regles config/regles_modes_z.json
```

### Reconstruction SQLite uniquement

```bash
uv run python src/scripts/reconstruire_base_751.py \
  --sources fichiers_sources \
  --base database/db.sqlite \
  --rapport controle/rapport_reconstruction_751.json \
  --publier
```

Sans `--publier`, la base temporaire est validée mais ne remplace pas `database/db.sqlite`.

### Exports et classeurs uniquement

```bash
uv run python src/scripts/db_ej_vers_xlsx.py \
  --base database/db.sqlite \
  --sortie output \
  --staging staging \
  --controle controle \
  --regles config/regles_modes_z.json
```

### Rapport PDF uniquement

Les classeurs et contrôles doivent déjà avoir été générés :

```bash
uv run python src/scripts/generer_rapport_fiscal_751.py \
  --base database/db.sqlite \
  --controle controle \
  --sortie output
```

## Tests et validation

Exécuter toute la suite de tests :

```bash
uv run python -m pytest -v
```

Auditer le projet depuis la racine du dépôt :

```bash
python3 .agents/skills/piloter-reprise-fiscale-751/scripts/audit_project.py
```

Les principaux seuils de non-régression sont les volumes SQLite, les 1 875 tickets de vente, les 4 131 lignes de détail, les 35 retours négatifs et les 57 rapprochements EJ/Z conformes.

## Limites connues

- Les FEC 2023, 2024 et 2025 ne sont pas présents dans les sources actives.
- Les déclarations CA3 ne sont pas présentes ; les cellules correspondantes du classeur de comparaison restent volontairement vides.
- Les règles de gestion et justificatifs externes nécessaires à une conclusion complète sur les corrections et annulations ne sont pas fournis.
- Le traitement ne constitue pas, à lui seul, une attestation de conformité fiscale ou juridique au-delà du périmètre de caisse effectivement contrôlé.

## Accès direct à la base SQLite

La base générée se trouve dans `database/db.sqlite`. Elle peut être interrogée directement avec le client en ligne de commande `sqlite3`. Pour éviter toute modification accidentelle, toujours l'ouvrir avec l'option `-readonly`. Une modification manuelle serait non tracée et pourrait être écrasée lors du prochain `uv run traitement`.

### Installer le client SQLite

Vérifier d'abord si le client est déjà disponible :

```bash
sqlite3 --version
```

Sur macOS avec Homebrew :

```bash
brew install sqlite
```

Sur Debian ou Ubuntu :

```bash
sudo apt update
sudo apt install sqlite3
```

La documentation du client est disponible sur [sqlite.org](https://www.sqlite.org/cli.html).

### Ouvrir la base en lecture seule

Depuis la racine du projet :

```bash
sqlite3 -readonly database/db.sqlite
```

Quelques commandes utiles dans le terminal SQLite :

```text
.headers on
.mode column
.nullvalue NULL
.tables
.schema tickets
.schema lignes_ticket
.quit
```

Une requête peut aussi être exécutée directement depuis le terminal, sans ouvrir de session interactive :

```bash
sqlite3 -readonly -header -column database/db.sqlite \
  "SELECT boutique, type, COUNT(*) AS nombre FROM tickets GROUP BY boutique, type ORDER BY boutique, type;"
```

### Requêtes de contrôle courantes

Compter les lignes de chaque table principale :

```sql
SELECT 'tickets' AS table_sqlite, COUNT(*) AS lignes FROM tickets
UNION ALL
SELECT 'lignes_ticket', COUNT(*) FROM lignes_ticket
UNION ALL
SELECT 'z1_entetes', COUNT(*) FROM z1_entetes
UNION ALL
SELECT 'z1_lignes', COUNT(*) FROM z1_lignes
UNION ALL
SELECT 'z2_entetes', COUNT(*) FROM z2_entetes
UNION ALL
SELECT 'z2_lignes', COUNT(*) FROM z2_lignes;
```

Inventorier les blocs EJ par boutique et par type :

```sql
SELECT boutique, type, COUNT(*) AS nombre
FROM tickets
GROUP BY boutique, type
ORDER BY boutique, type;
```

Rechercher les ruptures chronologiques de `E_NUM_INTERNE` :

```sql
WITH nums AS (
    SELECT
        id,
        boutique,
        nomFichier,
        E_DATE_TICKET,
        E_HEURE_TICKET,
        CAST(E_NUM_INTERNE AS INTEGER) AS num,
        LAG(CAST(E_NUM_INTERNE AS INTEGER)) OVER (
            PARTITION BY boutique
            ORDER BY E_DATE_TICKET, E_HEURE_TICKET, id
        ) AS precedent
    FROM tickets
    WHERE E_NUM_INTERNE IS NOT NULL
      AND E_NUM_INTERNE != ''
)
SELECT
    boutique,
    nomFichier,
    E_DATE_TICKET,
    E_HEURE_TICKET,
    precedent,
    num,
    num - precedent AS ecart
FROM nums
WHERE precedent IS NOT NULL
  AND num != precedent + 1
ORDER BY boutique, E_DATE_TICKET, E_HEURE_TICKET, num;
```

Cette requête contrôle la séquence interne de tous les blocs du journal électronique. Une absence de résultat signifie qu'aucune rupture n'a été détectée. `E_NUM_INTERNE` ne doit pas être confondu avec `E_NUM_TICKET`, qui est le numéro du ticket de vente.

Rechercher les ruptures de `E_NUM_TICKET` pour les ventes et retours de vente :

```sql
WITH ventes AS (
    SELECT
        id,
        boutique,
        nomFichier,
        E_DATE_TICKET,
        E_HEURE_TICKET,
        CAST(E_NUM_TICKET AS INTEGER) AS num,
        LAG(CAST(E_NUM_TICKET AS INTEGER)) OVER (
            PARTITION BY boutique
            ORDER BY E_DATE_TICKET, E_HEURE_TICKET, id
        ) AS precedent
    FROM tickets
    WHERE type IN ('REG', '_R_F')
      AND COALESCE(E_NUM_TICKET, '') != ''
)
SELECT
    boutique,
    nomFichier,
    E_DATE_TICKET,
    E_HEURE_TICKET,
    precedent,
    num,
    num - precedent AS ecart
FROM ventes
WHERE precedent IS NOT NULL
  AND num != precedent + 1
ORDER BY boutique, E_DATE_TICKET, E_HEURE_TICKET, num;
```

Rechercher les doublons de numéro de ticket de vente :

```sql
SELECT boutique, E_NUM_TICKET, COUNT(*) AS occurrences
FROM tickets
WHERE type IN ('REG', '_R_F')
  AND COALESCE(E_NUM_TICKET, '') != ''
GROUP BY boutique, E_NUM_TICKET
HAVING COUNT(*) > 1
ORDER BY boutique, CAST(E_NUM_TICKET AS INTEGER);
```

Compter les retours `_R_F` et distinguer ceux qui portent un numéro de ticket de vente :

```sql
SELECT
    boutique,
    COUNT(*) AS blocs_retour,
    SUM(
        CASE
            WHEN COALESCE(E_NUM_TICKET, '') != '' THEN 1
            ELSE 0
        END
    ) AS retours_vente
FROM tickets
WHERE type = '_R_F'
GROUP BY boutique
ORDER BY boutique;
```

Vérifier l'intégrité SQLite et rechercher d'éventuelles lignes de détail orphelines :

```sql
PRAGMA integrity_check;
PRAGMA foreign_key_check;

SELECT COUNT(*) AS lignes_orphelines
FROM lignes_ticket AS l
LEFT JOIN tickets AS t ON t.id = l.ticket_id
WHERE t.id IS NULL;
```

`PRAGMA integrity_check` doit retourner `ok`, `PRAGMA foreign_key_check` ne doit retourner aucune ligne et le nombre de lignes orphelines doit être nul.

Les montants sont stockés en texte décimal afin de préserver leur valeur exacte. Ne pas utiliser `CAST(... AS REAL)` pour conclure sur un écart monétaire : les contrôles fiscaux au centime doivent rester effectués par le programme Python avec `Decimal` ou à partir des fichiers de contrôle générés dans `controle/`.
