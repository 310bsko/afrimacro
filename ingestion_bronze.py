import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml


class ErreurIngestion(Exception):
    """Erreur de collecte : l'API est injoignable ou répond de façon inattendue."""


def charger_configuration(chemin="config/pipeline.yml"):
    """Lit le fichier de configuration et vérifie qu'il est cohérent."""
    with open(chemin, encoding="utf-8") as fichier:
        configuration = yaml.safe_load(fichier)

    if configuration["periode"]["fin"] is None:
        configuration["periode"]["fin"] = date.today().year
    if configuration["periode"]["debut"] > configuration["periode"]["fin"]:
        raise ValueError("periode.debut doit être inférieur ou égal à periode.fin")
    if not configuration["pays"]:
        raise ValueError("La liste des pays est vide")
    return configuration


def obtenir_json(url, parametres, essais=3, facteur_attente=2):
    """Appelle l'API. Si elle ne répond pas, réessaie avec des pauses de plus en plus longues."""
    for tentative in range(1, essais + 1):
        try:
            reponse = requests.get(url, params=parametres, timeout=30)
            reponse.raise_for_status()
            return reponse.json()
        except (requests.RequestException, ValueError) as erreur:
            if tentative == essais:
                raise ErreurIngestion(f"échec après {essais} essais ({type(erreur).__name__})") from erreur
            attente = facteur_attente ** tentative
            print(f"  essai {tentative}/{essais} échoué ({type(erreur).__name__}), nouvel essai dans {attente}s")
            time.sleep(attente)


def lire_toutes_les_pages(url, parametres):
    """Lit toutes les pages de la réponse. Retourne la liste des réponses brutes."""
    pages = []
    numero_page = 1
    while True:
        contenu = obtenir_json(url, {**parametres, "page": numero_page})
        valide = (
            isinstance(contenu, list)
            and len(contenu) == 2
            and isinstance(contenu[0], dict)
            and "pages" in contenu[0]
        )
        if not valide:
            raise ErreurIngestion(f"réponse inattendue : {str(contenu)[:150]}")
        pages.append(contenu)
        if numero_page >= contenu[0]["pages"]:
            return pages
        numero_page += 1


def collecter_indicateur(code_indicateur, configuration):
    """Collecte un indicateur pour tous les pays et sauvegarde le brut dans bronze."""
    pays = ";".join(configuration["pays"])
    url = f"{configuration['url_base']}/country/{pays}/indicator/{code_indicateur}"
    parametres = {
        "format": "json",
        "per_page": configuration["par_page"],
        "date": f"{configuration['periode']['debut']}:{configuration['periode']['fin']}",
    }
    pages = lire_toutes_les_pages(url, parametres)

    date_collecte = datetime.now(timezone.utc)
    horodatage = date_collecte.strftime("%Y%m%dT%H%M%S%fZ")
    chemin = (Path(configuration["dossier_donnees"]) / "bronze" / "banque_mondiale"
              / code_indicateur / f"{horodatage}.json")
    chemin.parent.mkdir(parents=True, exist_ok=True)

    enveloppe = {
        "source": "banque_mondiale_indicateurs_v2",
        "code_indicateur": code_indicateur,
        "libelle_indicateur": configuration["indicateurs"][code_indicateur],
        "date_collecte": date_collecte.isoformat(),
        "requete": {"url": url, "parametres": parametres},
        "pages": pages,
    }
    with open(chemin, "x", encoding="utf-8") as fichier:
        json.dump(enveloppe, fichier, ensure_ascii=False)

    observations = [obs for page in pages for obs in (page[1] or [])]
    sans_valeur = sum(1 for obs in observations if obs["value"] is None)
    return len(observations), sans_valeur, len(pages)


def principal():
    configuration = charger_configuration()
    debut = time.perf_counter()
    echecs = []
    total_lignes = 0

    for code_indicateur in configuration["indicateurs"]:
        try:
            lignes, sans_valeur, nb_pages = collecter_indicateur(code_indicateur, configuration)
        except (ErreurIngestion, OSError) as erreur:
            print(f"{code_indicateur}: ÉCHEC - {erreur}")
            echecs.append(code_indicateur)
            continue
        total_lignes += lignes
        print(f"{code_indicateur}: {lignes} lignes ({nb_pages} page(s)), dont {sans_valeur} sans valeur")

    duree = time.perf_counter() - debut
    total = len(configuration["indicateurs"])
    print(f"\nTerminé : {total - len(echecs)}/{total} indicateurs, {total_lignes} lignes, {duree:.1f}s")
    if echecs:
        print("Indicateurs en échec :", echecs)
        sys.exit(1)


if __name__ == "__main__":
    principal()
