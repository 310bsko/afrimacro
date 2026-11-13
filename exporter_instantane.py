"""Exporte un instantané de l'entrepôt pour la mise en ligne du tableau de bord.

Rôle dans le pipeline : le tableau de bord hébergé en ligne n'a pas accès à la
base PostgreSQL locale. On publie donc une copie figée de la vue
`vue_observations` (Parquet) dans un dossier versionné par Git. En ligne, le
tableau de bord lit cet instantané ; en local, il lit la base.

Lancement : uv run --env-file .env exporter_instantane.py
Le script réécrit l'instantané à chaque lancement (il ne s'accumule pas).
"""

import json
import shutil
import sys
from datetime import datetime, timezone

from tableau_de_bord.acces_donnees import (
    CHEMIN_GROUPES_LOCAL,
    DOSSIER_INSTANTANE,
    ERREURS_BASE,
    NOM_FICHIER_GROUPES,
    NOM_FICHIER_META,
    NOM_FICHIER_OBSERVATIONS,
    lire_vue_postgres,
)


def principal() -> None:
    try:
        observations = lire_vue_postgres()
    except ERREURS_BASE as erreur:
        print(f"ÉCHEC : lecture de la base impossible ({erreur}).")
        print("Démarrer PostgreSQL (docker compose up -d) et lancer avec : uv run --env-file .env ...")
        sys.exit(1)

    if observations.empty:
        print("ÉCHEC : la vue vue_observations est vide. Lancer d'abord chargement_entrepot.py.")
        sys.exit(1)

    DOSSIER_INSTANTANE.mkdir(parents=True, exist_ok=True)
    chemin_parquet = DOSSIER_INSTANTANE / NOM_FICHIER_OBSERVATIONS
    observations.to_parquet(chemin_parquet, index=False)

    nb_sans_valeur = int(observations["valeur"].isna().sum()) if "valeur" in observations else None
    meta = {
        "date_export": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "nb_lignes": int(len(observations)),
        "nb_sans_valeur": nb_sans_valeur,
    }
    (DOSSIER_INSTANTANE / NOM_FICHIER_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Le regroupement de pays (regroupement_pays.py) est publié avec l'instantané.
    if CHEMIN_GROUPES_LOCAL.exists():
        shutil.copyfile(CHEMIN_GROUPES_LOCAL, DOSSIER_INSTANTANE / NOM_FICHIER_GROUPES)
    else:
        print(f"AVERTISSEMENT : {CHEMIN_GROUPES_LOCAL} introuvable (lancer regroupement_pays.py).")

    taille_ko = chemin_parquet.stat().st_size / 1024
    print(f"instantané : {meta['nb_lignes']} lignes, dont {nb_sans_valeur} sans valeur")
    print(f"écrit dans {DOSSIER_INSTANTANE}/ ({taille_ko:.0f} Ko pour le Parquet)")


if __name__ == "__main__":
    principal()
