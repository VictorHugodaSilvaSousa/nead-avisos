"""Isola os testes: segredos num cofre em memória (nunca o Gerenciador de Credenciais real) e sem variáveis
NEAD_AVISOS_* do ambiente."""

import os

import pytest

from nead_avisos import cli, config


@pytest.fixture(autouse=True)
def isolated_secrets(monkeypatch):
    for var in [v for v in os.environ if v.startswith("NEAD_AVISOS_")] + ["GITHUB_ACTIONS"]:
        monkeypatch.delenv(var, raising=False)
    store: dict[str, str] = {}
    monkeypatch.setattr(config, "get_secret", lambda name: store.get(name))
    monkeypatch.setattr(config, "set_secret", lambda name, value: store.__setitem__(name, value))
    monkeypatch.setattr(cli, "get_secret", lambda name: store.get(name))
    monkeypatch.setattr(cli, "set_secret", lambda name, value: store.__setitem__(name, value))
    yield store
