import json

import pytest
import requests

import ingestion_bronze


class FausseReponse:
    """Fausse réponse HTTP : aucun accès à internet n'est nécessaire."""

    def __init__(self, contenu):
        self._contenu = contenu

    def raise_for_status(self):
        pass

    def json(self):
        return self._contenu


def fausse_page(numero, nb_pages, lignes):
    return [{"page": numero, "pages": nb_pages}, lignes]


def test_lire_toutes_les_pages_lit_chaque_page(monkeypatch):
    reponses = iter([FausseReponse(fausse_page(1, 2, ["a"])), FausseReponse(fausse_page(2, 2, ["b"]))])
    monkeypatch.setattr(ingestion_bronze.requests, "get", lambda *args, **kwargs: next(reponses))

    pages = ingestion_bronze.lire_toutes_les_pages("http://fake", {})

    assert len(pages) == 2
    assert pages[1][1] == ["b"]


def test_obtenir_json_reessaie_apres_un_timeout(monkeypatch):
    appels = []

    def faux_get(*args, **kwargs):
        appels.append(1)
        if len(appels) == 1:
            raise requests.ReadTimeout("trop lent")
        return FausseReponse({"ok": True})

    monkeypatch.setattr(ingestion_bronze.requests, "get", faux_get)
    monkeypatch.setattr(ingestion_bronze.time, "sleep", lambda secondes: None)

    assert ingestion_bronze.obtenir_json("http://fake", {}) == {"ok": True}
    assert len(appels) == 2


def test_indicateur_inconnu_leve_une_erreur_ingestion(monkeypatch):
    contenu_erreur = [{"message": [{"id": "120"}]}]
    monkeypatch.setattr(ingestion_bronze.requests, "get", lambda *args, **kwargs: FausseReponse(contenu_erreur))

    with pytest.raises(ingestion_bronze.ErreurIngestion):
        ingestion_bronze.lire_toutes_les_pages("http://fake", {})


def test_configuration_refuse_un_debut_apres_la_fin(tmp_path):
    chemin = tmp_path / "mauvaise.yml"
    chemin.write_text("periode: {debut: 2030, fin: 2020}\npays: [CIV]\n", encoding="utf-8")

    with pytest.raises(ValueError):
        ingestion_bronze.charger_configuration(chemin)


def test_collecter_indicateur_ecrit_une_enveloppe_en_francais(monkeypatch, tmp_path):
    configuration = {
        "url_base": "http://fake",
        "par_page": 1000,
        "dossier_donnees": str(tmp_path),
        "periode": {"debut": 2020, "fin": 2021},
        "pays": ["CIV", "GHA"],
        "indicateurs": {"SP.POP.TOTL": "Population totale"},
    }
    page_brute = fausse_page(1, 1, [{"value": 1.0}, {"value": None}])
    monkeypatch.setattr(ingestion_bronze.requests, "get", lambda *args, **kwargs: FausseReponse(page_brute))

    lignes, sans_valeur, nb_pages = ingestion_bronze.collecter_indicateur("SP.POP.TOTL", configuration)

    fichiers = list((tmp_path / "bronze" / "banque_mondiale" / "SP.POP.TOTL").glob("*.json"))
    assert (lignes, sans_valeur, nb_pages) == (2, 1, 1)
    assert len(fichiers) == 1
    enveloppe = json.loads(fichiers[0].read_text(encoding="utf-8"))
    assert enveloppe["code_indicateur"] == "SP.POP.TOTL"
    assert enveloppe["pages"] == [page_brute]  # le brut n'est pas modifié
    assert "date_collecte" in enveloppe
