import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

CHEMIN_PROFIL = "donnees/gold/profil_pays"
COLONNES_A_LOGARITHME = ["sp_pop_totl", "ny_gdp_mktp_cd"]   # variables très asymétriques


def lire_profil():
    """Lit le profil des pays (gold) : une ligne par pays, une colonne par indicateur."""
    profil = pd.read_parquet(CHEMIN_PROFIL)
    return profil.set_index("code_pays").drop(columns="nom_pays")


def colonnes_incompletes(profil):
    """Indicateurs avec au moins une valeur manquante, et le nombre de pays concernés."""
    manquantes = profil.isna().sum()
    return manquantes[manquantes > 0]


def preparer(profil):
    """Garde les indicateurs complets, applique le logarithme aux variables asymétriques, puis standardise."""
    complets = profil.loc[:, profil.notna().all()].copy()
    for colonne in COLONNES_A_LOGARITHME:
        if colonne in complets.columns:
            complets[colonne] = np.log10(complets[colonne])
    standardise = pd.DataFrame(
        StandardScaler().fit_transform(complets),
        index=complets.index,
        columns=complets.columns,
    )
    return complets, standardise


def principal():
    pd.options.display.float_format = "{:,.2f}".format
    profil = lire_profil()
    print(f"profil : {profil.shape[0]} pays x {profil.shape[1]} indicateurs\n")

    print("Échelle de chaque indicateur (minimum et maximum) :")
    print(profil.agg(["min", "max"]).T, "\n")

    incomplets = colonnes_incompletes(profil)
    print("Indicateurs avec des valeurs manquantes (nombre de pays concernés) :")
    print(incomplets.to_string() if len(incomplets) else "aucun", "\n")

    complets, standardise = preparer(profil)
    print(f"Indicateurs retenus : {complets.shape[1]} sur {profil.shape[1]}\n")

    print("Après standardisation :")
    print(pd.DataFrame({"moyenne": standardise.mean(), "ecart_type": standardise.std(ddof=0)}))
    print("\nPopulation standardisée :")
    print(standardise["sp_pop_totl"].sort_values().round(2))

if __name__ == "__main__":
    principal()
