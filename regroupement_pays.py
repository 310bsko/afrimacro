from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # pas de fenêtre : l'image est enregistrée dans un fichier
import matplotlib.pyplot as plt
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from sklearn.metrics import silhouette_score

from analyse_pays import lire_profil, preparer

NB_GROUPES = 3
DOSSIER_SORTIE = Path("donnees/analyse")


def calculer_liaisons(standardise):
    """Classification ascendante hiérarchique avec le critère de Ward."""
    return linkage(standardise, method="ward")


def tracer_dendrogramme(liaisons, codes_pays, chemin):
    """Enregistre l'arbre des fusions successives dans une image."""
    figure, axe = plt.subplots(figsize=(10, 5))
    dendrogram(liaisons, labels=list(codes_pays), ax=axe)
    axe.set_title("Classification ascendante hiérarchique (Ward) des pays")
    axe.set_ylabel("Distance de fusion")
    figure.tight_layout()
    figure.savefig(chemin, dpi=150)
    plt.close(figure)


def tester_nombres_de_groupes(standardise, liaisons, valeurs_k=range(2, 7)):
    """Score de silhouette pour chaque nombre de groupes (proche de 1 : groupes bien séparés)."""
    scores = {}
    for k in valeurs_k:
        etiquettes = fcluster(liaisons, t=k, criterion="maxclust")
        scores[k] = silhouette_score(standardise, etiquettes)
    return scores


def principal():
    profil = lire_profil()
    complets, standardise = preparer(profil)
    liaisons = calculer_liaisons(standardise)

    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    tracer_dendrogramme(liaisons, standardise.index, DOSSIER_SORTIE / "dendrogramme.png")

    print("Score de silhouette selon le nombre de groupes :")
    for k, score in tester_nombres_de_groupes(standardise, liaisons).items():
        print(f"  {k} groupes : {score:.2f}")

    groupes = pd.Series(
        fcluster(liaisons, t=NB_GROUPES, criterion="maxclust"),
        index=standardise.index,
        name="groupe",
    )
    print(f"\nRegroupement en {NB_GROUPES} groupes :")
    for numero, pays in groupes.groupby(groupes):
        print(f"  groupe {numero} : {', '.join(pays.index)}")

    pd.options.display.float_format = "{:,.1f}".format
    print("\nMoyenne de chaque indicateur par groupe (valeurs d'origine) :")
    print(profil[complets.columns].groupby(groupes).mean().T)

    groupes.to_csv(DOSSIER_SORTIE / "groupes_pays.csv")
    print(f"\nFichiers écrits dans {DOSSIER_SORTIE}/")


if __name__ == "__main__":
    principal()
