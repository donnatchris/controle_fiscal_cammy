# Checklist de conformité au cahier des charges 751

## Règles d'audit obligatoires

Pour chaque feuille produite, ne pas se contenter de vérifier la structure du classeur.

La vérification doit suivre la chaîne :

`fichiers source → base SQLite → traitements → feuille ODS`

Pour chaque feuille :

* [ ] vérifier les colonnes attendues ;
* [ ] vérifier les types ;
* [ ] vérifier le nombre de lignes ;
* [ ] vérifier les formules et agrégations ;
* [ ] vérifier la filiation avec la feuille ou la donnée source ;
* [ ] **effectuer au minimum un contrôle indépendant à partir de la base SQLite** ;
* [ ] comparer le résultat obtenu par SQL avec la donnée effectivement présente dans la feuille.

---

# Contrôle obligatoire contre la base SQLite

La base SQLite constitue une source intermédiaire permettant de vérifier que les données utilisées dans les feuilles correspondent bien aux données réellement parsées.

## Principe

Pour **chaque feuille**, effectuer au minimum **un test échantillonné de comparaison avec la base de données**, lorsqu'une correspondance avec les données de la base existe.

Le contrôle doit être effectué avec une ou plusieurs requêtes `SELECT`.

Exemples :

```sql
SELECT ...
FROM tickets
WHERE ...;
```

```sql
SELECT ...
FROM lignes_ticket
WHERE ...;
```

ou pour les données Z :

```sql
SELECT ...
FROM ...
WHERE ...;
```

Le contrôle doit permettre de vérifier réellement les valeurs et pas seulement l'existence des enregistrements.

## Pour une feuille contenant des données détaillées

* [ ] sélectionner au moins un enregistrement identifiable dans la feuille ;
* [ ] retrouver cet enregistrement avec un `SELECT` dans SQLite ;
* [ ] comparer les champs pertinents cellule par cellule ;
* [ ] vérifier notamment les identifiants, dates, montants et modes de paiement ;
* [ ] signaler toute différence.

Exemple de contrôle attendu :

`feuille → E_NUM_TICKET = X → SELECT correspondant → comparaison de E_TTC, E_HT1, E_TVA1, paiements, date, etc.`

## Pour une feuille issue d'une agrégation

Ne pas uniquement comparer une ligne individuelle.

* [ ] reproduire au moins une agrégation de la feuille avec un `SELECT`, `SUM`, `COUNT` et `GROUP BY` approprié ;
* [ ] comparer le résultat SQL avec la cellule ou la ligne correspondante dans la feuille.

Exemples :

```sql
SELECT
    strftime('%Y-%m', E_DATE_TICKET) AS mois,
    SUM(E_TTC)
FROM tickets
WHERE ...
GROUP BY mois;
```

ou l'équivalent adapté au schéma réel.

## Pour une feuille de comparaison

* [ ] vérifier indépendamment au moins un des deux montants comparés depuis la base ;
* [ ] lorsque les deux sources existent en base, vérifier les deux ;
* [ ] recalculer ensuite l'écart indépendamment ;
* [ ] comparer avec la valeur écrite dans la feuille.

## Échantillonnage

Minimum obligatoire :

* [ ] **au moins un contrôle SQL par feuille** lorsqu'une vérification SQLite est techniquement possible.

Pour les feuilles critiques, augmenter l'échantillon :

* [ ] première période ;
* [ ] dernière période ;
* [ ] une période intermédiaire ;
* [ ] une valeur négative lorsqu'il en existe ;
* [ ] une période présentant un écart ;
* [ ] une période multi-mois lorsqu'elle existe ;
* [ ] une période sans clôture lorsqu'elle existe.

Le compte rendu doit préciser :

* requête SQL utilisée ;
* valeur obtenue dans SQLite ;
* valeur trouvée dans la feuille ;
* résultat : `IDENTIQUE` ou `DIFFÉRENT`.

---

# Règle générale : donnée absente

Le CDC indique que lorsqu'une donnée n'est pas disponible, le champ concerné doit être laissé vide.

Donc :

* [ ] absence de donnée ≠ zéro ;
* [ ] ne jamais inventer une valeur ;
* [ ] ne jamais transformer automatiquement une absence en `0` ;
* [ ] si une comparaison ne peut pas être réalisée faute d'une source, laisser l'écart vide ;
* [ ] conserver un véritable `0` lorsque la source contient réellement la valeur numérique zéro.

---

# Pièces externes absentes

Les pièces suivantes ne sont pas présentes dans les données fournies par le client :

* FEC 2023 ;
* FEC 2024 ;
* FEC 2025 ;
* déclarations CA3 de janvier 2023 à août 2025 ;
* règles, paramétrages et justificatifs relatifs aux corrections et annulations.

**Cette absence est normale dans le cadre du projet actuel : ces documents n'ont pas été fournis par le client.**

Elle ne constitue donc **pas une erreur du programme ni une non-conformité du traitement réalisé sur les données disponibles**.

Codex doit vérifier uniquement que :

* [ ] aucune donnée FEC n'est inventée ;
* [ ] aucune donnée CA3 n'est inventée ;
* [ ] aucune règle de correction/annulation non fournie n'est inventée ;
* [ ] les cellules dépendant de ces informations restent vides lorsque le CDC exige une donnée indisponible ;
* [ ] le rapport d'exécution mentionne explicitement que ces pièces n'ont pas été fournies ;
* [ ] aucun zéro n'est utilisé pour masquer l'absence de ces pièces.

Le statut approprié est :

`NON VÉRIFIABLE — PIÈCE CLIENT NON FOURNIE`

et non :

`NON CONFORME`.

---

# Z1 / Z2 — détermination de AJ_Année_Z et AJ_Mois_Z

Le CDC définit :

* `AJ_Année_Z` comme l'année de la clôture de la caisse, au format `AAAA`, telle que mentionnée dans le nom du fichier ;
* `AJ_Mois_Z` comme le mois de la clôture de la caisse, au format `AAAA-MM`, tel que mentionné dans le nom du fichier.

## Cas mono-mois

Pour un fichier indiquant un seul mois :

* [ ] utiliser ce mois comme `AJ_Mois_Z`.

Exemple :

`012025` → `AJ_Mois_Z = 2025-01`.

## Cas multi-mois

Lorsqu'un fichier correspond à plusieurs mois parce qu'aucune clôture intermédiaire n'a été effectuée, **le dernier mois indiqué est retenu pour ****`AJ_Mois_Z`**.

Ce dernier mois correspond au **mois de la clôture de la caisse**.

Exemple :

`042025_052025_062025`

correspond à une clôture portant les mois d'avril, mai et juin et réalisée comme clôture de juin.

Donc :

`AJ_Mois_Z = 2025-06`

De même :

`062025_072025`

donne :

`AJ_Mois_Z = 2025-07`.

Contrôles :

* [ ] détecter tous les mois présents dans le nom du fichier ;
* [ ] si un seul mois est présent, l'utiliser ;
* [ ] si plusieurs mois sont présents, utiliser **le dernier mois** ;
* [ ] conserver en interne la liste complète des mois détectés afin de pouvoir identifier les lots multi-mois ;
* [ ] vérifier par `SELECT` et par comparaison avec les EJ que le fichier représente bien la clôture correspondant à cette période ;
* [ ] signaler dans le rapport qu'il s'agit d'un lot multi-mois.

Cette convention doit être documentée dans le rapport comme interprétation retenue de la notion de **« mois de la clôture de la caisse »** du CDC.

---

# Périodes sans clôture

Certaines périodes ne disposent pas du mode Z contractuellement demandé.

Cas actuellement identifiés pour MATURIN :

* [ ] 2023-11 ;
* [ ] 2023-12 ;
* [ ] 2025-04 ;
* [ ] 2025-05.

Des modes alternatifs `ZZ1` ou `ZZ2` peuvent exister.

Ils ne doivent pas remplacer silencieusement le mode `Z` demandé.

Pour ces périodes :

* [ ] ne pas créer artificiellement une clôture Z ;
* [ ] ne pas utiliser `0` comme montant Z ;
* [ ] laisser vides les données de comparaison nécessitant le mode absent ;
* [ ] laisser vide l'écart impossible à calculer ;
* [ ] signaler explicitement l'absence de clôture/mode demandé.

Statut :

`NON VÉRIFIABLE — CLÔTURE/MODE Z ABSENT`

---

# Contrôle indépendant des clôtures EJ/Z

En complément des tableaux mensuels demandés par le CDC, effectuer un contrôle indépendant des clôtures réellement présentes.

Pour chaque clôture retenue :

* [ ] identifier la clôture précédente ;
* [ ] déterminer les tickets EJ appartenant à la période comprise entre les deux clôtures ;
* [ ] recalculer les montants à partir de la base SQLite ;
* [ ] comparer avec Z1 :

  * [ ] HT ;
  * [ ] TVA ;
  * [ ] TTC ;
* [ ] comparer avec Z2 :

  * [ ] carte ;
  * [ ] chèques ;
  * [ ] espèces.

Les calculs doivent être effectués indépendamment des feuilles ODS.

Le contrôle actuellement établi doit pouvoir être reproduit :

* [ ] 30 clôtures MASSENA ;
* [ ] 27 clôtures MATURIN ;
* [ ] 57 clôtures réelles au total ;
* [ ] concordance Z1/EJ ;
* [ ] concordance Z2/EJ.

Tout futur écart réel doit être signalé sans être masqué par une compensation entre plusieurs mois.

---

# Comparaisons mensuelles EJ/Z

Les comparaisons mensuelles demandées par le CDC doivent rester présentes.

Ne pas forcer artificiellement les écarts à zéro.

Un écart mensuel peut résulter :

* d'une clôture effectuée après la frontière du mois civil ;
* d'une clôture couvrant plusieurs mois ;
* de l'absence d'une clôture intermédiaire ;
* d'un véritable écart dans les données sources.

Pour chaque écart significatif :

* [ ] identifier son origine ;
* [ ] vérifier les données correspondantes dans SQLite ;
* [ ] vérifier les fichiers EJ et Z sources ;
* [ ] qualifier l'écart.

Qualifications possibles :

* `DÉCALAGE DE FRONTIÈRE DE CLÔTURE`
* `LOT MULTI-MOIS`
* `MODE/CLÔTURE ABSENT`
* `ÉCART SOURCE À INVESTIGUER`

Ne jamais qualifier d'anomalie source un simple effet de calendrier démontré par le rapprochement indépendant des clôtures.

---

# Rapport d'exécution

Le rapport doit permettre de distinguer les différents types de résultats.

Pour chaque feuille :

* [ ] classeur ;
* [ ] feuille ;
* [ ] source immédiate ;
* [ ] nombre d'enregistrements lus ;
* [ ] nombre d'enregistrements sélectionnés ;
* [ ] nombre d'enregistrements écrits ;
* [ ] totaux numériques demandés ;
* [ ] contrôles de cohérence ;
* [ ] résultat du contrôle SQL échantillonné ;
* [ ] anomalie éventuelle.

Pour chaque contrôle SQL échantillonné, mentionner au minimum :

* [ ] feuille concernée ;
* [ ] clé ou période contrôlée ;
* [ ] requête ou description de la requête SQL ;
* [ ] valeur SQLite ;
* [ ] valeur ODS ;
* [ ] résultat de la comparaison.

Le rapport doit également mentionner :

* [ ] les 57 clôtures contrôlées indépendamment ;
* [ ] leur concordance avec les EJ ;
* [ ] les écarts mensuels détectés ;
* [ ] leur qualification ;
* [ ] les périodes multi-mois ;
* [ ] les périodes sans clôture ;
* [ ] les FEC absents ;
* [ ] les CA3 absentes ;
* [ ] les justificatifs/règles de correction-annulation absents.

Les pièces externes absentes doivent être présentées comme **non fournies par le client**, et non comme des erreurs du traitement.

---

# Critères finaux d'acceptation

Avant de conclure à la conformité d'une feuille :

* [ ] structure conforme au CDC ;
* [ ] colonnes correctes ;
* [ ] types corrects ;
* [ ] copie/filiation correcte ;
* [ ] calculs recalculés indépendamment ;
* [ ] agrégations recalculées indépendamment ;
* [ ] **au moins un contrôle SQL contre SQLite effectué pour cette feuille lorsqu'il est applicable** ;
* [ ] absence de donnée correctement représentée par une cellule vide ;
* [ ] lots multi-mois affectés au **dernier mois**, correspondant au mois de clôture ;
* [ ] aucune donnée externe inventée ;
* [ ] aucune anomalie source masquée ;
* [ ] aucun effet de calendrier présenté à tort comme une anomalie de données.

La conclusion par feuille doit utiliser uniquement :

* `CONFORME`
* `CONFORME AVEC RÉSERVE`
* `NON CONFORME`
* `NON VÉRIFIABLE`

Une pièce client absente ne doit pas, à elle seule, entraîner `NON CONFORME`.
