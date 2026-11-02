-- Entrepôt de données AfriMacro : modèle dimensionnel en étoile.
-- Ce script peut être relancé sans danger : il ne recrée pas ce qui existe déjà.

-- Dimensions : les axes d'analyse (qui, quoi, d'où, quand)

CREATE TABLE IF NOT EXISTS dim_pays (
    id_pays   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code_pays CHAR(3) NOT NULL UNIQUE,
    nom_pays  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_indicateur (
    id_indicateur      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code_indicateur    TEXT NOT NULL UNIQUE,
    libelle_indicateur TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_source (
    id_source   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code_source TEXT NOT NULL UNIQUE,
    nom_source  TEXT NOT NULL,
    url_source  TEXT,
    licence     TEXT
);

CREATE TABLE IF NOT EXISTS dim_annee (
    annee    INTEGER PRIMARY KEY CHECK (annee BETWEEN 1900 AND 2100),
    decennie INTEGER NOT NULL
);

-- Fait : les mesures. Une ligne par pays, indicateur, source et année.

CREATE TABLE IF NOT EXISTS fait_observation (
    id_pays            INTEGER NOT NULL REFERENCES dim_pays (id_pays),
    id_indicateur      INTEGER NOT NULL REFERENCES dim_indicateur (id_indicateur),
    id_source          INTEGER NOT NULL REFERENCES dim_source (id_source),
    annee              INTEGER NOT NULL REFERENCES dim_annee (annee),
    valeur             DOUBLE PRECISION,
    est_projection     BOOLEAN NOT NULL DEFAULT FALSE,
    source_mise_a_jour DATE,
    date_collecte      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id_pays, id_indicateur, id_source, annee)
);

COMMENT ON COLUMN fait_observation.valeur IS 'Valeur de l''indicateur. NULL = valeur manquante : elle n''est jamais inventée.';
COMMENT ON COLUMN fait_observation.est_projection IS 'Vrai si la valeur est une projection et non une observation.';
COMMENT ON COLUMN fait_observation.date_collecte IS 'Date de collecte de la donnée brute (UTC).';

-- Donnée de référence : la source utilisée par la version 1 du projet.

INSERT INTO dim_source (code_source, nom_source, url_source, licence)
VALUES ('banque_mondiale', 'Banque mondiale - Indicators API v2', 'https://api.worldbank.org/v2',
        'CC BY 4.0 en général (à vérifier indicateur par indicateur)')
ON CONFLICT (code_source) DO NOTHING;
