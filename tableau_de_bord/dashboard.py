import pandas as pd
import plotly.express as px
import streamlit as st

from acces_donnees import charger_groupes, charger_observations

st.set_page_config(page_title="AfriMacro", layout="wide")


@st.cache_data(ttl=600)
def lire_observations():
    """Lit la vue de l'entrepôt (une ligne par pays, indicateur et année) et indique d'où elle vient.

    Base PostgreSQL si elle répond (poste local), sinon instantané versionné (mise en ligne).
    """
    observations, origine = charger_observations()
    observations["valeur"] = pd.to_numeric(observations["valeur"])
    return observations, origine


@st.cache_data
def lire_groupes():
    """Lit les groupes de pays produits par l'analyse (absents : le graphique 3 n'est pas coloré)."""
    return charger_groupes()


def resumer_pays(donnees):
    """Pour chaque pays : dernière valeur renseignée et variation sur 5 ans (même unité que l'indicateur)."""
    lignes = []
    for nom_pays, groupe in donnees.groupby("nom_pays"):
        renseignees = groupe.dropna(subset=["valeur"]).sort_values("annee")
        if renseignees.empty:
            lignes.append({"Pays": nom_pays, "Dernière année": None, "Dernière valeur": None,
                           "Variation sur 5 ans": None})
            continue
        derniere = renseignees.iloc[-1]
        reference = renseignees[renseignees["annee"] <= derniere["annee"] - 5]
        variation = derniere["valeur"] - reference.iloc[-1]["valeur"] if not reference.empty else None
        lignes.append({"Pays": nom_pays, "Dernière année": int(derniere["annee"]),
                       "Dernière valeur": derniere["valeur"], "Variation sur 5 ans": variation})
    return pd.DataFrame(lignes)


try:
    observations, origine = lire_observations()
except FileNotFoundError as erreur:
    st.error(str(erreur))
    st.stop()
groupes = lire_groupes()

st.title("AfriMacro : indicateurs économiques de l'Afrique de l'Ouest")
st.caption(
    "Source : Banque mondiale, Indicators API v2 (licence CC BY 4.0 sauf mention contraire). "
    f"Données annuelles. Origine des données affichées : {origine}."
)

# --- Sélecteurs
indicateurs = sorted(observations["libelle_indicateur"].unique())
noms_pays = sorted(observations["nom_pays"].unique())
pays_par_defaut = [nom for nom in ("Cote d'Ivoire", "Ghana", "Senegal") if nom in noms_pays] or noms_pays[:3]

indicateur = st.sidebar.selectbox("Indicateur", indicateurs)
pays_choisis = st.sidebar.multiselect("Pays", noms_pays, default=pays_par_defaut)
annee_min, annee_max = int(observations["annee"].min()), int(observations["annee"].max())
periode = st.sidebar.slider("Période", annee_min, annee_max, (annee_min, annee_max))

if not pays_choisis:
    st.warning("Choisis au moins un pays dans la barre latérale.")
    st.stop()

indicateur_complet = observations[observations["libelle_indicateur"] == indicateur]
donnees = indicateur_complet[
    indicateur_complet["nom_pays"].isin(pays_choisis) & indicateur_complet["annee"].between(*periode)
]

# --- Indicateurs clés
colonne_1, colonne_2, colonne_3 = st.columns(3)
colonne_1.metric("Pays sélectionnés", len(pays_choisis))
colonne_2.metric("Dernière collecte des données", f"{observations['date_collecte'].max():%d/%m/%Y}")
colonne_3.metric("Dernière mise à jour de la source", f"{observations['source_mise_a_jour'].max():%d/%m/%Y}")

# --- Graphique 1 : évolution
st.subheader(f"Évolution : {indicateur}")
figure = px.line(donnees, x="annee", y="valeur", color="nom_pays", markers=True,
                 labels={"annee": "Année", "valeur": "Valeur", "nom_pays": "Pays"})
st.plotly_chart(figure, width="stretch")
st.caption("Les valeurs manquantes sont laissées vides : elles ne sont jamais comblées ni inventées.")
st.dataframe(resumer_pays(donnees), hide_index=True, width="stretch")

# --- Graphique 2 : classement de tous les pays pour une année
st.subheader("Classement des pays pour une année")
annees_avec_valeurs = sorted(indicateur_complet.dropna(subset=["valeur"])["annee"].unique(), reverse=True)
annee_classement = st.selectbox("Année", annees_avec_valeurs)
classement = indicateur_complet[indicateur_complet["annee"] == annee_classement].dropna(subset=["valeur"])
if groupes is not None:
    classement = classement.merge(groupes, on="code_pays", how="left")
    classement["groupe"] = classement["groupe"].astype("Int64").astype(str)
figure_classement = px.bar(
    classement.sort_values("valeur"), x="valeur", y="nom_pays", orientation="h",
    color="groupe" if groupes is not None else None,
    labels={"valeur": "Valeur", "nom_pays": "Pays", "groupe": "Groupe"},
)
st.plotly_chart(figure_classement, width="stretch")
nb_sans_valeur = indicateur_complet["code_pays"].nunique() - len(classement)
if nb_sans_valeur:
    st.caption(f"{nb_sans_valeur} pays sans valeur pour {annee_classement}.")

# --- Graphique 3 : profils de pays (moyenne sur la période choisie)
st.subheader("Profils de pays : deux indicateurs face à face")
colonne_x, colonne_y = st.columns(2)
indicateur_x = colonne_x.selectbox("Axe horizontal", indicateurs, index=0, key="axe_x")
indicateur_y = colonne_y.selectbox("Axe vertical", indicateurs, index=min(1, len(indicateurs) - 1), key="axe_y")
echelle_log = st.checkbox("Échelle logarithmique", value=False)

sur_la_periode = observations[observations["annee"].between(*periode)]
moyennes = (sur_la_periode.pivot_table(index=["code_pays", "nom_pays"], columns="libelle_indicateur",
                                       values="valeur", aggfunc="mean").reset_index())
if indicateur_x in moyennes.columns and indicateur_y in moyennes.columns:
    profil = moyennes[["code_pays", "nom_pays", indicateur_x, indicateur_y]].dropna()
    if groupes is not None:
        profil = profil.merge(groupes, on="code_pays", how="left")
        profil["groupe"] = profil["groupe"].astype("Int64").astype(str)
    figure_profil = px.scatter(
        profil, x=indicateur_x, y=indicateur_y, text="code_pays",
        color="groupe" if groupes is not None else None,
        log_x=echelle_log, log_y=echelle_log, labels={"groupe": "Groupe"},
    )
    figure_profil.update_traces(textposition="top center")
    st.plotly_chart(figure_profil, width="stretch")
    st.caption(f"Moyennes de {periode[0]} à {periode[1]}. Pays sans valeur pour l'un des deux indicateurs : non affichés.")

# --- Méthodologie et limites
with st.expander("Méthodologie et limites", expanded=True):
    st.markdown(
        f"""
- **Source** : Banque mondiale, Indicators API v2, publiée sous licence CC BY 4.0 sauf mention contraire. Données agrégées et transformées dans le cadre de ce projet. Ce projet n'est pas approuvé par la Banque mondiale.
- **Origine des données affichées** : {origine}. En ligne, le tableau de bord lit un instantané figé de l'entrepôt ; sur le poste local, il lit la base PostgreSQL.
- **Données** : annuelles, collectées le {observations['date_collecte'].max():%d/%m/%Y}. Les années les plus récentes sont souvent incomplètes.
- **Valeurs manquantes** : jamais inventées ni interpolées. Elles apparaissent comme des trous.
- **Groupes de pays** : classification ascendante hiérarchique (critère de Ward) sur 12 indicateurs standardisés, moyennes 2015-2024. Les indicateurs incomplets (exportations, importations, compte courant) sont exclus. Avec 15 pays seulement, l'analyse est exploratoire.
- **Interprétation** : les graphiques décrivent des ressemblances et des évolutions. Ils n'établissent aucun lien de cause à effet.
"""
    )
