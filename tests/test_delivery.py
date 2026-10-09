"""Entrega no Telegram: grupo que vira supergrupo e falha só no grupo (caso real de 06/10/2026)."""

from datetime import datetime, timedelta

from nead_avisos import cli
from nead_avisos.collect import Notice
from nead_avisos.config import Settings
from nead_avisos.state import State
from nead_avisos.telegram import Telegram

ME, OLD_GROUP, NEW_GROUP = 111, -5442611616, -1003700245505


class FakeApi:
    """Simula a API do Telegram: o grupo antigo responde 'virou supergrupo'."""
    def __init__(self, group_works=True):
        self.sent, self.group_works = [], group_works

    def __call__(self, tg, method, payload):
        chat = payload.get("chat_id")
        if chat == OLD_GROUP:
            return {"ok": False, "description": "Bad Request: group chat was upgraded to a supergroup chat",
                    "parameters": {"migrate_to_chat_id": NEW_GROUP}}
        if chat == NEW_GROUP and not self.group_works:
            return {"ok": False, "description": "Forbidden"}
        self.sent.append((chat, payload.get("text", "")))
        return {"ok": True}


def setup(tmp_path, monkeypatch, api, notices):
    s = Settings()
    s.data_dir, s.telegram_chat_id, s.telegram_group_id = tmp_path, ME, OLD_GROUP
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: api(self, m, p))
    import nead_avisos.config as cfg
    real = cfg.get_secret
    monkeypatch.setattr(cli, "get_secret", lambda name: "123:abc" if name == "telegram_token" else real(name))
    monkeypatch.setattr(cli, "_moodle", lambda s: type("M", (), {"calls": 0})())
    monkeypatch.setattr("time.sleep", lambda x: None)

    class FakeCollector:
        def __init__(self, s, m, state):
            self.first_run, self.m = False, m
            self.state = state

        def run(self):
            seen = self.state.data.setdefault("seen", {})
            out = [n for n in notices() if n.key not in seen]
            for n in out:
                seen[n.key] = "x"
            return out
    monkeypatch.setattr(cli, "Collector", FakeCollector)
    return s


def digest():
    return [Notice("digest:2026-10-06", "group", "🗓", "Prazos da semana", body="• nada")]


def test_supergroup_migration_is_followed_and_remembered(tmp_path, monkeypatch):
    api = FakeApi()
    s = setup(tmp_path, monkeypatch, api, digest)
    assert cli._run(s, dry_run=False) == 0
    assert [c for c, _ in api.sent][:2] == [ME, NEW_GROUP]            # chegou no grupo novo
    assert any("virou supergrupo" in t and str(NEW_GROUP) in t for c, t in api.sent if c == ME)
    from nead_avisos.state import state_key
    state = State(tmp_path / "state.json", key=state_key())
    assert state.data["group_migrated"][str(OLD_GROUP)] == NEW_GROUP


def test_failure_only_in_group_never_repeats_in_private_chat(tmp_path, monkeypatch):
    api = FakeApi(group_works=False)
    s = setup(tmp_path, monkeypatch, api, digest)
    for _ in range(4):                                                  # 4 execuções seguidas (1 hora)
        cli._run(s, dry_run=False)
    private = [t for c, t in api.sent if c == ME and t.startswith("🗓")]
    assert len(private) == 1                                            # no seu chat: uma vez só
    from nead_avisos.state import state_key
    state = State(tmp_path / "state.json", key=state_key())
    assert "digest:2026-10-06" in state.data["partial"]                 # grupo continua pendente
    # depois de 1 dia de falhas, desiste (não fica tentando para sempre)
    state.data["partial"]["digest:2026-10-06"]["since"] = (datetime.now(s.tz) - timedelta(days=2)).isoformat()
    state.save()
    cli._run(s, dry_run=False)
    assert "digest:2026-10-06" not in State(tmp_path / "state.json", key=state_key()).data["partial"]
