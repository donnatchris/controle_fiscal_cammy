# Portes qualité du dossier 751

## Principe

Bloquer la livraison définitive dès qu'une porte applicable est rouge. Associer chaque porte à une preuve reproductible : commande, fichier de contrôle, total et empreinte de sources.

## Baselines de non-régression du périmètre caisse

N'utiliser ces valeurs que si la baseline de sources est identique ou explicitement rapprochée :

| Porte | Objet | Attendu historique |
|---|---|---|
| G0 | Inventaire et manifeste | Tous les fichiers inventoriés, SHA-256 valide, aucune source modifiée |
| G1 | Classification EJ | 2 511 blocs signés classés, 0 quarantaine |
| G2 | Tickets de vente | 1 875 total : 1 153 MASSENA, 722 MATURIN |
| G3 | Lignes de ticket | 4 131 lignes, 0 orpheline |
| G4A | Inventaire CSV Z | 449 CSV classés |
| G4B | Parsing Z1/Z2 | 192 fichiers : 96 Z1 et 96 Z2, 0 quarantaine |
| G4C | Modes Z | 0 règle boutique/exercice en anomalie |
| G4D | Multi-mois | 6 fichiers explicitement étiquetés début/fin |
| G4E | Couverture | 60 périodes avec clôture, 4 sans clôture, 0 ambiguïté |
| G5 | Rapprochement EJ/Z | 57 clôtures sur 57 concordantes au seuil de 0,02 EUR |
| G6A | Séquences | 0 rupture de numéro de ticket non expliquée |
| G6B | Unicité | 0 doublon de numéro interne ou ticket |
| G6C | Retours clé | 35 `_R_F`, conservés et signés pour -19 821,00 EUR TTC |

Les quatre périodes historiquement sans clôture sont MATURIN 2023-11, 2023-12, 2025-04 et 2025-05. Les traiter comme absences de clôture constatées, pas comme fichiers à inventer.

## Portes externes

- **FEC** : exiger les trois fichiers et leur validation de structure avant tout rapprochement comptable.
- **CA3** : exiger les déclarations de janvier 2023 à août 2025 avant de conclure la comparaison du CA/TVA déclaré.
- **Corrections/annulations** : exiger la règle de gestion, les paramétrages et justificatifs avant de conclure sur la procédure.
- **Transmission** : produire programme, résultats et rapport d'exécution, un descriptif des zones, les totaux de contrôle et deux copies de remise.

Si une porte externe manque, utiliser le statut `CONFORME SUR LE PÉRIMÈTRE CAISSE - À COMPLÉTER`, jamais `CONFORME`.

## Contrôles de format

- CSV : séparateur explicite et constant, encodage documenté, colonnes dans l'ordre contractuel, valeurs absentes vides.
- Dates : format contractuel sans conversion locale implicite.
- Montants : euros, deux décimales, virgule dans les livrables français ; calcul exact avant formatage.
- Excel : noms d'onglets <= 31 caractères, correspondance documentée avec le cahier des charges, formules ou valeurs vérifiées et rendu visuel contrôlé.
- Rapport : méthode, sources, versions, totaux lus/sélectionnés/écrits, contrôles, écarts, limites et dépendances externes.
- Package : aucun fichier temporaire, manifeste SHA-256 complet, programme exécutable, résultats et contrôles cohérents avec le rapport.

## Preuve minimale après modification

1. État Git et inventaire des sources inchangés.
2. Tests unitaires ciblés verts.
3. Suite complète verte.
4. Audit du skill sans erreur.
5. Portes qualité régénérées depuis le code courant.
6. Inspection visuelle des artefacts bureautiques concernés.
7. Compte rendu des écarts, y compris ceux expliqués et ceux bloquants.
