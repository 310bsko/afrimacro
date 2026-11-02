-- Vues de l'entrepôt : des requêtes enregistrées qui se comportent comme des tables.
-- Elles ne copient aucune donnée. Ce script peut être relancé sans danger.

CREATE OR REPLACE VIEW vue_observations AS
SELECT p.code_pays,
       p.nom_pays,
       i.code_indicateur,
       i.libelle_indicateur,
       s.code_source,
       f.annee,
       f.valeur,
       f.est_projection,
       f.source_mise_a_jour,
       f.date_collecte
FROM fait_observation f
JOIN dim_pays p USING (id_pays)
JOIN dim_indicateur i USING (id_indicateur)
JOIN dim_source s USING (id_source);

COMMENT ON VIEW vue_observations IS 'Observations avec les libellés des dimensions : la vue lue par le dashboard.';
