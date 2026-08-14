# Rapport de contrôle des exports 751

Statut : **CONFORME SUR LE PÉRIMÈTRE CAISSE - À COMPLÉTER**

- Blocs EJ lus et conservés en base : 2511
- Tickets de vente sélectionnés et écrits : 1875
- Blocs non sélectionnés pour les ventes : 636
- Rapprochements EJ/Z conformes : 57/57
- Périodes avec clôture / sans clôture / ambiguës : 60 / 4 / 0
- Fichiers Z1/Z2 multi-mois : 6

## Blocs exclus des classeurs de ventes

| Type | Nombre | Motif |
|---|---:|---|
| REG | 311 | Événement sans E_NUM_TICKET |
| X | 32 | Bloc administratif |
| XZ | 133 | Bloc administratif |
| Z | 157 | Bloc administratif |
| _R_F | 3 | Événement sans E_NUM_TICKET |

Les types exclus ne sont pas qualifiés d’erreurs : ils restent intégralement conservés en base.
`D_TAUX_TVA_ARTICLE` conserve les indicateurs source (`T1`, `T2`, etc.) ; le taux de 20 % n’est utilisé que dans la formule de contrôle de `E_HT1`.
Les champs CA3 et FEC restent volontairement vides tant que les sources externes ne sont pas fournies.
