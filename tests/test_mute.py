"""/silenciar, /ativar e /silenciados: só o SEU chat; o grupo da turma não muda."""

from datetime import timedelta

from nead_avisos import cli, mute
from nead_avisos.collect import Collector, Notice
from nead_avisos.config import Settings
from nead_avisos.state import State, state_key
from nead_avisos.telegram import Telegram
from test_collect import NOW, FakeMoodle

ME, GROUP = 111, -999


def test_categories_and_names():
    assert mute.normalize("Notificações") == "notificacoes" and mute.normalize("nota") == "notas"
    assert mute.normalize("xyz") is None
    assert mute.category(Notice("notif:1", "me", "✅", "Envio confirmado: X")) == "confirmacoes"
    assert mute.category(Notice("notif:2", "me", "📢", "Aviso")) == "notificacoes"
    assert mute.category(Notice("grade:1:9:0", "me", "📊", "Nota")) == "notas"
    assert mute.category(Notice("cmd:5", "me", "🤖", "NEAD Avisos")) is None        # respostas nunca silenciam


def test_commands_change_the_muted_list(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    Collector(Settings(), m, st, NOW).run()
    col = Collector(Settings(), m, st, NOW + timedelta(minutes=15))
    col.commands = [(1, "/silenciar", "confirmações"), (2, "/silenciar", "notas"), (3, "/ativar", "notas"),
                    (4, "/silenciar", "banana"), (5, "/silenciados", "")]
    out = {n.key: n for n in col.run()}
    assert st.data["muted"] == ["confirmacoes"]
    assert "🔕 <b>confirmacoes</b> silenciado" in out["cmd:1"].body
    assert "ativado de novo" in out["cmd:3"].body
    assert "Não conheço o tipo 'banana'" in out["cmd:4"].body
    assert "Silenciados no seu chat: confirmacoes" in out["cmd:5"].body


def test_muted_types_skip_only_my_chat(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: {"ok": True, "result": []} if m == "getUpdates"
                        else sent.append(p["chat_id"]) or {"ok": True})
    monkeypatch.setattr("time.sleep", lambda x: None)
    monkeypatch.setattr(cli, "_moodle", lambda s: type("M", (), {"calls": 0})())
    import nead_avisos.config as cfg
    real = cfg.get_secret
    monkeypatch.setattr(cli, "get_secret", lambda n: "1:a" if n == "telegram_token" else real(n))
    st = State(tmp_path / "state.json", key=state_key())
    st.data = {"muted": ["confirmacoes", "atividades"]}
    st.save()
    notices = [Notice("notif:1", "me", "✅", "Envio confirmado: X"),                 # silenciado
               Notice("grade:1:9:0", "me", "📊", "Nota lançada: X"),                 # chega
               Notice("duechange:7:a", "group", "📅", "Prazo alterado: Y"),          # prazos: não silenciado
               Notice("edit:8:b", "group", "✏️", "Atividade alterada: Z", extra={})]  # atividades: grupo ainda recebe

    class FakeCollector:
        def __init__(self, s, m, state):
            self.first_run, self.m, self.state = False, m, state

        def run(self):
            return list(notices)
    monkeypatch.setattr(cli, "Collector", FakeCollector)
    s = Settings()
    s.data_dir, s.telegram_chat_id, s.telegram_group_id, s.group_slots, s.quiet_hours = tmp_path, ME, GROUP, None, None
    cli._run(s, dry_run=False)
    assert sent.count(ME) == 2 and sent.count(GROUP) == 2      # nota + prazo alterado no meu; o grupo recebe os dele
