# Dictionnaire de données

Conventions : les identifiants sont en français, en minuscules, sans accent, avec des tirets bas. Les dates et heures sont en UTC. Une valeur manquante est enregistrée vide (`NULL`) et n'est jamais remplacée.

## Indicateurs

| Code | Libellé | Unité | Valeurs manquantes (sur 540) |
| --- | --- | --- | --- |
| `NY.GDP.MKTP.CD` | PIB (dollars courants) | dollars US | 0 |
| `NY.GDP.MKTP.KD.ZG` | Croissance annuelle du PIB (%) | % | 0 |
| `NY.GDP.PCAP.CD` | PIB par habitant (dollars courants) | dollars US | 0 |
| `FP.CPI.TOTL.ZG` | Inflation, prix à la consommation (%) | % | 48 |
| `SL.UEM.TOTL.ZS` | Chômage (% de la population active, estimation OIT) | % | 15 (la série commence en 1991) |
| `NE.EXP.GNFS.ZS` | Exportations de biens et services (% du PIB) | % du PIB | 75 |
| `NE.IMP.GNFS.ZS` | Importations de biens et services (% du PIB) | % du PIB | 75 |
| `BN.CAB.XOKA.GD.ZS` | Solde du compte courant (% du PIB) | % du PIB | 69 |
| `BX.KLT.DINV.WD.GD.ZS` | Investissements directs étrangers entrants nets (% du PIB) | % du PIB | 1 |
| `DT.DOD.DECT.GN.ZS` | Dette extérieure (% du RNB) | % du RNB | 18 |
| `FS.AST.PRVT.GD.ZS` | Crédit intérieur au secteur privé (% du PIB) | % du PIB | 9 |
| `SP.POP.TOTL` | Population totale | personnes | 0 |
| `SP.DYN.LE00.IN` | Espérance de vie à la naissance (années) | années | 15 |
| `EG.ELC.ACCS.ZS` | Accès à l'électricité (% de la population) | % de la population | 111 |
| `IT.NET.USER.ZS` | Utilisateurs d'Internet (% de la population) | % de la population | 79 |

Chaque indicateur couvre 15 pays x 36 années (1990-2025) = 540 observations. Les effectifs viennent de la collecte du 13 novembre 2026 (données de la Banque mondiale mises à jour le 11 novembre 2026). Les libellés français sont définis dans `config/pipeline.yml`.

Pays (codes ISO3) : CIV, GHA, NGA, SEN, MLI, BFA, NER, BEN, TGO, GIN, SLE, LBR, GMB, GNB, CPV.

## Bronze

Un fichier par indicateur et par collecte : `donnees/bronze/banque_mondiale/<code_indicateur>/<horodatage UTC>.json`.

| Clé | Description |
| --- | --- |
| `source` | Nom de la source et version de l'API (`banque_mondiale_indicateurs_v2`). |
| `code_indicateur` | Code de l'indicateur de la Banque mondiale. |
| `libelle_indicateur` | Libellé français issu de la configuration. |
| `date_collecte` | Date et heure de collecte (ISO 8601, UTC). |
| `requete` | La requête envoyée : `url` et `parametres`. |
| `pages` | Les pages brutes de l'API, exactement comme reçues. Chaque page est une liste de deux éléments : les métadonnées de la page, puis les observations. Les noms de champs à l'intérieur gardent les noms anglais de l'API. |

## Silver

`donnees/silver/indicateurs_banque_mondiale` (Parquet). Granularité : une ligne par pays, indicateur et année. Clé : (`code_pays`, `code_indicateur`, `annee`).

| Colonne | Type | Description |
| --- | --- | --- |
| `code_pays` | texte | Code pays ISO3. |
| `nom_pays` | texte | Nom du pays, tel que donné par l'API. |
| `code_indicateur` | texte | Code de l'indicateur de la Banque mondiale. |
| `libelle_indicateur` | texte | Libellé français de l'indicateur. |
| `annee` | entier | Année. |
| `valeur` | décimal (double) | Valeur observée. Vide si manquante. |
| `source` | texte | Code de la source (`banque_mondiale`). |
| `source_mise_a_jour` | texte | Date de dernière mise à jour des données par la source (`AAAA-MM-JJ`). |
| `date_collecte` | horodatage | Date et heure de collecte (UTC). |

## Gold

**`donnees/gold/moyennes_recentes`** : une ligne par pays et indicateur, sur la fenêtre définie dans `config/pipeline.yml` (section `gold`).

| Colonne | Type | Description |
| --- | --- | --- |
| `code_pays`, `nom_pays`, `code_indicateur`, `libelle_indicateur` | texte | Comme dans le silver. |
| `moyenne` | décimal | Moyenne des valeurs disponibles dans la fenêtre. |
| `nb_annees_renseignees` | entier long | Nombre d'années avec une valeur dans la fenêtre. |
| `couverture` | décimal | `nb_annees_renseignees` divisé par la longueur de la fenêtre. |
| `fiable` | booléen | Vrai si `couverture` atteint le seuil de fiabilité (0,70 par défaut). |
| `annee_debut`, `annee_fin` | entier | Bornes de la fenêtre (2015 et 2024 par défaut). |

**`donnees/gold/profil_pays`** : une ligne par pays. Colonnes : `code_pays`, `nom_pays`, puis une colonne par indicateur, nommée d'après le code en minuscules avec les points remplacés par des tirets bas (par exemple `sp_pop_totl`). La valeur est la moyenne de la fenêtre si `fiable`, sinon vide.

## Résultats de l'analyse

| Fichier | Description |
| --- | --- |
| `donnees/analyse/groupes_pays.csv` | Colonnes `code_pays` et `groupe`. Numéro de groupe issu de la classification de Ward. Les numéros sont des étiquettes arbitraires. |
| `donnees/analyse/dendrogramme.png` | Dendrogramme de la classification. |
| `donnees/qualite/rapport_qualite_<horodatage>.csv` | Rapport de qualité : `date_execution`, `controle`, `bloquant`, `statut` (`OK`, `ECHEC`, `AVERTISSEMENT`), `detail`. |

## Entrepôt (PostgreSQL)

| Table | Colonne | Type | Contrainte | Description |
| --- | --- | --- | --- | --- |
| `dim_pays` | `id_pays` | entier | clé primaire, générée | Clé de substitution. |
| | `code_pays` | char(3) | unique, non nul | Code ISO3. |
| | `nom_pays` | texte | non nul | Nom du pays. |
| `dim_indicateur` | `id_indicateur` | entier | clé primaire, générée | Clé de substitution. |
| | `code_indicateur` | texte | unique, non nul | Code de la Banque mondiale. |
| | `libelle_indicateur` | texte | non nul | Libellé français. |
| `dim_source` | `id_source` | entier | clé primaire, générée | Clé de substitution. |
| | `code_source` | texte | unique, non nul | Code de la source. |
| | `nom_source`, `url_source`, `licence` | texte | | Description de la source et note de licence. |
| `dim_annee` | `annee` | entier | clé primaire, entre 1900 et 2100 | Année. |
| | `decennie` | entier | non nul | Décennie (par exemple 2020). |
| `fait_observation` | `id_pays`, `id_indicateur`, `id_source`, `annee` | entier | clé primaire composée, chacun clé étrangère | Identifie l'observation. |
| | `valeur` | double precision | peut être vide | Valeur. `NULL` signifie manquante. |
| | `est_projection` | booléen | non nul, faux par défaut | Vrai pour une projection (aucune pour l'instant). |
| | `source_mise_a_jour` | date | | Date de mise à jour de la source. |
| | `date_collecte` | timestamptz | non nul | Date et heure de collecte (UTC). |

**Vue `vue_observations`** : la table de faits jointe à ses dimensions. Colonnes : `code_pays`, `nom_pays`, `code_indicateur`, `libelle_indicateur`, `code_source`, `annee`, `valeur`, `est_projection`, `source_mise_a_jour`, `date_collecte`. Le dashboard lit uniquement cette vue. En ligne, il en lit une copie : `tableau_de_bord/instantane/observations.parquet`, accompagnée de `meta.json` (date d'export, nombre de lignes, nombre de valeurs manquantes) et de `groupes_pays.csv` (colonnes `code_pays` et `groupe`).

## Règles

- Les données brutes (bronze) ne sont jamais modifiées ni supprimées par le pipeline.
- Les valeurs manquantes ne sont jamais inventées. Une moyenne est signalée non fiable quand moins de 70 % des années sont renseignées.
- Les valeurs gardent l'unité et la base de leur source. Aucune conversion d'unité n'est faite.
- La dernière collecte de chaque indicateur est celle utilisée dans le silver. Les collectes précédentes restent dans le bronze.

## Source et licence

Banque mondiale, API Indicators v2. Les jeux de données de la Banque mondiale sont publiés par défaut sous licence CC BY 4.0, sauf mention contraire. Cite la source en cas de réutilisation et indique que les données ont été agrégées et transformées. Ce projet n'est pas approuvé par la Banque mondiale.
