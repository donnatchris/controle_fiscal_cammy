---
name: justifier-ecarts-fisc-cdc-751
description: Qualifier les écarts, limites et non-conformités du dossier fiscal CAMMY/DEVFRA au regard du CDC 751, puis préparer une justification factuelle et prouvée destinée à l'administration. À utiliser pour ce CDC précis, pas pour un mémoire fiscal générique ni pour déclarer conforme un livrable non audité.
---

# Justifier les écarts au CDC 751

Préparer un dossier de réponse qui explique les écarts sans les minimiser, les confondre avec une pièce absente ou attribuer une cause non démontrée.

## Référence métier obligatoire

Lire [references/points-attention-cdc-751.md](references/points-attention-cdc-751.md) avant toute qualification ou rédaction. Consulter aussi le PDF original du CDC et le dernier rapport de conformité disponible dans le projet. Le rapport existant est un indice : rejouer ou citer ses preuves, sans reprendre automatiquement son verdict.

## Périmètre et autorisation

- Une demande d'analyse ou de préparation de réponse reste en lecture seule : ne modifier ni sources, ni base, ni traitements, ni ODS et ne transmettre rien au fisc.
- Ne corriger un livrable que sur demande explicite, en conservant la valeur avant correction et la preuve de la régénération.
- Employer la raison sociale exacte figurant dans le CDC ; utiliser « DEVFRA » seulement comme nom opérationnel si le dossier permet de relier les deux.
- Signaler que la qualification fiscale ou juridique finale doit être validée par le conseil de l'entreprise lorsque la réponse dépasse les constats techniques.

## Qualification

Pour chaque constat, distinguer obligatoirement :

- `NON CONFORME` : une exigence applicable du CDC n'est pas respectée ;
- `NON VÉRIFIABLE` : la vérification est impossible faute de pièce ou de mode source, sans invention de valeur ;
- `CONFORME AVEC RÉSERVE` : le traitement vérifiable est conforme, mais une limite documentée subsiste ;
- `ANOMALIE SOURCE` : l'écart existe déjà dans les fichiers remis et le traitement le restitue fidèlement ;
- `INTERPRÉTATION VALIDÉE` : une ambiguïté du CDC a fait l'objet d'une décision écrite, datée et attribuable.

Ne jamais transformer une absence en zéro, un décalage de frontière de clôture en anomalie source, ni une décision orale en dérogation opposable. La mention d'un fichier comme « communiqué » dans le CDC prévaut comme alerte documentaire tant que son historique de transmission n'est pas établi.

## Dossier de preuve par écart

Avant de proposer une justification, établir :

1. l'exigence exacte, la page du CDC et le livrable concerné ;
2. le fait observé, son périmètre, sa période et les valeurs comparées ;
3. la qualification et l'imputabilité prouvée : source, paramétrage client, traitement DEVFRA ou impossibilité de conclure ;
4. l'impact chiffré sur HT, TVA, TTC et règlements, ou le calcul qui démontre l'absence d'impact ;
5. la cause racine accompagnée de pièces datées : source, requête SQL, journal, capture, échange, validation métier ou empreinte ;
6. la mesure conservatoire, la correction éventuelle, sa date et les tests de non-régression ;
7. les pièces annexées et l'identité du responsable qui valide la réponse.

Si un de ces éléments manque, écrire `À ÉTABLIR` et formuler la demande de preuve. Ne pas combler le vide par une hypothèse.

## Rédaction attendue

Produire d'abord un tableau des points d'attention, puis une fiche autonome par écart. Chaque fiche sépare clairement : `Exigence`, `Constat`, `Cause démontrée`, `Impact`, `Correction/mesure`, `Preuves`, `Formulation proposée` et `Validation requise`.

La formulation proposée doit reconnaître le fait, expliquer la cause sans spéculation, chiffrer l'effet, décrire la mesure prise et renvoyer aux annexes. Éviter les arguments nus tels que « erreur humaine », « problème logiciel », « sans incidence » ou « document non fourni ».

Conclure par :

- les non-conformités réellement établies ;
- les points seulement non vérifiables ;
- les contradictions documentaires à résoudre ;
- les décisions ou pièces que DEVFRA doit obtenir avant envoi ;
- un avertissement explicite si le rapport courant ne constate aucune non-conformité.
