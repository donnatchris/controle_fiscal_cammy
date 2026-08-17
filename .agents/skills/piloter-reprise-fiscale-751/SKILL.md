---
name: piloter-reprise-fiscale-751
description: Encadrer l'analyse, le développement, les contrôles, les rapprochements et la livraison du dossier fiscal 751 CAMMY FRANCE DEVELOPPEMENT LTD à partir des journaux électroniques EJ, rapports Z et exigences du cahier des charges L.47 A-II b LPF. Utiliser ce skill pour toute modification, revue, correction, génération de CSV/SQLite/Excel/PDF, validation de données de caisse, comparaison CA/TVA/FEC/CA3 ou préparation de livraison dans le projet fiscal 751.
---

# Piloter la reprise fiscale 751

## Charger le contexte utile

1. Localiser la racine du projet contenant `pyproject.toml`, `src/` et `fichiers_sources/`.
2. Lire [references/cahier-des-charges.md](references/cahier-des-charges.md) avant de modifier une règle métier, un schéma, une formule ou un livrable.
3. Lire [references/project-map.md](references/project-map.md) avant de choisir le code canonique ou de réutiliser un résultat existant.
4. Lire [references/quality-gates.md](references/quality-gates.md) avant de valider, publier ou annoncer une conformité.
5. Exécuter `python3 .agents/skills/piloter-reprise-fiscale-751/scripts/audit_project.py` pour établir l'état initial en lecture seule.

## Appliquer les invariants

- Traiter le PDF et les six dossiers boutique/exercice de `fichiers_sources/` comme des preuves immuables. Ne jamais les corriger, renommer ou réécrire.
- Conserver une provenance jusqu'au fichier, au bloc ou à la ligne source et produire un manifeste SHA-256 pour toute livraison.
- Représenter les montants avec `Decimal` ou des centimes entiers pendant les calculs. Ne jamais utiliser de flottants binaires pour décider d'un écart.
- Conserver les zéros comme zéros et les données absentes comme champs vides. Ne jamais inventer une valeur, une clôture, un FEC, une CA3 ou une justification.
- Signer négativement toute annulation, correction ou retour affectant les montants. Conserver la transaction et sa traçabilité.
- Utiliser la période métier portée par le dossier et le nom du fichier. Utiliser la date et l'heure Z comme bornes entre deux clôtures réelles ; ne pas réduire silencieusement un lot multi-mois.
- Isoler en quarantaine tout bloc ambigu, incomplet ou non reconnu. Ne pas ignorer silencieusement une erreur de parsing.
- Séparer strictement sources, staging, résultats, contrôles, programme, documentation et package de livraison.
- Générer tous les CSV dérivés avec le séparateur `|`, de façon explicite et constante.
- Traiter `E_NUM_INTERNE`, `E_NUM_TICKET`, `E_COMPTEUR_Z` et `D_ENREGISTREMENT` comme du texte de bout en bout ; préserver exactement leurs zéros initiaux et ne jamais les convertir en nombres ni les normaliser par suppression de ces zéros.
- Exporter `D_QUANTITE` comme un entier sans séparateur décimal. Signaler ou rejeter toute valeur source qui ne peut pas être représentée sans perte comme un entier.
- Exporter toutes les dates au format ISO `YYYY-MM-DD`, sans conversion locale implicite.
- Préserver les changements utilisateur présents dans le worktree et limiter les modifications au périmètre demandé.

## Suivre le workflow

1. **Inventorier.** Compter les fichiers par extension, boutique et exercice ; calculer les empreintes ; signaler tout écart avec une baseline connue.
2. **Parser.** Décoder les EJ et CSV Z en Windows-1252, classifier chaque bloc signé, normaliser les champs contractuels et conserver la provenance.
3. **Contrôler les EJ.** Vérifier exhaustivité, relations entête/lignes, cohérence HT-TVA-TTC, règlements, séquences, chronologie, doublons et retours `_R_F`.
4. **Contrôler les Z.** Vérifier schéma, mode Z/ZZ1/ZZ2, compteur, période simple ou multi-mois et règles boutique/exercice.
5. **Rapprocher.** Comparer EJ, Z1 et Z2 par clôtures successives sur TTC, HT, TVA, carte, chèques et espèces ; documenter chaque écart au centime.
6. **Agréger.** Produire les recettes mensuelles par boutique puis toutes boutiques, sans confondre mois civil et intervalle de clôture.
7. **Comparer aux données externes.** N'exécuter les rapprochements FEC et CA3 que lorsque les pièces sont réellement fournies. Sinon produire un statut bloqué explicite.
8. **Générer.** Respecter exactement les noms de colonnes et les familles de livrables du cahier des charges. Produire programme, résultats et rapport d'exécution.
9. **Valider.** Exécuter les tests ciblés puis la suite complète, relancer l'audit, contrôler les portes qualité et inspecter visuellement chaque classeur, DOCX et PDF livré.
10. **Livrer.** Produire un package ZIP avec manifeste, versions du programme et résultats. Conserver une double copie de transmission et marquer toute dépendance externe restante.

## Décider du statut

- Annoncer `CONFORME` uniquement si toutes les portes applicables sont vertes, les artefacts ont été régénérés depuis la baseline vérifiée et les pièces externes requises sont présentes.
- Annoncer `CONFORME SUR LE PÉRIMÈTRE CAISSE - À COMPLÉTER` lorsque EJ/Z sont validés mais que FEC, CA3 ou justificatifs manquent.
- Annoncer `BLOQUÉ` lorsqu'une source, une période, une règle de mode ou un écart non expliqué empêche un résultat fiable.
- Distinguer un résultat historique d'une preuve produite par le code courant. Ne jamais présenter un ancien package vert comme validation automatique du worktree actuel.

## Vérifier proportionnellement au changement

- Pour un parseur ou une formule : ajouter un test unitaire avec montant négatif, champ vide, ligne coupée et format inattendu pertinent.
- Pour une agrégation ou un rapprochement : vérifier des totaux indépendants et les cas multi-mois, absence de clôture et retour `_R_F`.
- Pour un schéma de sortie : contrôler noms, ordre, types, séparateur `|`, encodage, dates `YYYY-MM-DD`, préservation des zéros initiaux des identifiants textuels, `D_QUANTITE` entier et virgule décimale réservée aux montants.
- Pour Excel, DOCX ou PDF : utiliser le skill spécialisé correspondant et effectuer un rendu visuel avant livraison.
- Pour un package : vérifier les empreintes, l'absence de fichiers temporaires et la présence du programme, des résultats, des contrôles et du rapport.

## Produire un compte rendu

Indiquer systématiquement : périmètre traité, sources utilisées, tests exécutés, portes vertes/rouges, écarts expliqués, dépendances externes et chemins des livrables. Ne pas attester une conformité fiscale ou juridique au-delà des contrôles effectivement réalisés.
