"""Tests de l'accès aux données du tableau de bord (base ou instantané)."""

import json

import pandas as pd
import pytest

from tableau_de_bord import acces_donnees


@pytest.fixture
def instantane(tmp_path, monkeypatch):
    """Un faux instantané dans un dossier temporaire."""
    pd.DataFrame(
        {"code_pays": ["CIV", "GHA"], "annee": [2024, 2024], "valeur": [1.5, None]}
    ).to_parquet(tmp_path / acces_donnees.NOM_FICHIER_OBSERVATIONS, index=False)
    (tmp_path / acces_donnees.NOM_FICHIER_META).write_text(
        json.dumps({"date_export": "2026-11-13 09:00 UTC"}), encoding="utf-8"
    )
    monkeypatch.setattr(acces_donnees, "DOSSIER_INSTANTANE", tmp_path)
    return tmp_path


def test_sans_base_on_lit_l_instantane(instantane, monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    donnees, origine = acces_donnees.charger_observations()
    assert len(donnees) == 2
    assert origine == "instantané du 2026-11-13 09:00 UTC"


def test_base_injoignable_retombe_sur_l_instantane(instantane, monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "x")
    monkeypatch.setenv("POSTGRES_DB", "x")
    monkeypatch.setenv("POSTGRES_USER", "x")
    monkeypatch.setenv("POSTGRES_PORT", "1")  # port fermé : connexion refusée
    donnees, origine = acces_donnees.charger_observations()
    assert len(donnees) == 2
    assert origine.startswith("instantané")


def test_ni_base_ni_instantane_echoue_clairement(tmp_path, monkeypatch):
    monkeypatch.setattr(acces_donnees, "DOSSIER_INSTANTANE", tmp_path)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    with pytest.raises(FileNotFoundError, match="exporter_instantane"):
        acces_donnees.charger_observations()


def test_groupes_lus_dans_l_instantane_sans_fichier_local(instantane, monkeypatch, tmp_path):
    monkeypatch.setattr(acces_donnees, "CHEMIN_GROUPES_LOCAL", tmp_path / "absent.csv")
    (instantane / acces_donnees.NOM_FICHIER_GROUPES).write_text(
        "code_pays,groupe\nCIV,1\nCPV,2\n", encoding="utf-8"
    )
    groupes = acces_donnees.charger_groupes()
    assert list(groupes["code_pays"]) == ["CIV", "CPV"]


def test_groupes_absents_retourne_none(instantane, monkeypatch, tmp_path):
    monkeypatch.setattr(acces_donnees, "CHEMIN_GROUPES_LOCAL", tmp_path / "absent.csv")
    assert acces_donnees.charger_groupes() is None
