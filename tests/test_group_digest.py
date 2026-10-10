"""Grupo da turma em ritmo de resumo (muita gente no grupo): resumo por disciplina em horários fixos;
só o urgente chega na hora. O chat pessoal continua recebendo tudo na hora."""

from datetime import datetime
from zoneinfo import ZoneInfo

from nead_avisos import cli
from nead_avisos.collect import Notice
from nead_avisos.config import Settings
from nead_avisos.group_digest import current_slot, is_urgent_for_group, render
from nead_avisos.state import State, state_key
from nead_avisos.telegram import Telegram

TZ = ZoneInfo("America/Sao_Paulo")
ME, GROUP = 111, -999


def run_at(tmp_path, monkeypatch, when, notices):
    sent = []
    monkeypatch.setattr(Telegram, "_api", lambda self, m, p: {"ok": True, "result": []} if m == "getUpdates"
                        else sent.append((p["chat_id"], p["text"])) or {"ok": True})
    monkeypatch.setattr("time.sleep", lambda x: None)
    monkeypatch.setattr(cli, "_moodle", lambda s: type("M", (), {"calls": 0})())
    import nead_avisos.config as cfg
    real = cfg.get_secret
    monkeypatch.setattr(cli, "get_secret", lambda n: "1:a" if n == "telegram_token" else real(n))

    class FakeCollector:
        def __init__(self, s, m, state):
            self.first_run, self.m, self.state = False, m, state

        def run(self):
            return list(notices)
    monkeypatch.setattr(cli, "Collector", FakeCollector)

    class Clock:
        @staticmethod
        def now(tz=None):
            return when.astimezone(tz) if tz else when
    monkeypatch.setattr(cli, "datetime", type("D", (), {"now": Clock.now, "fromisoformat": datetime.fromisoformat}))
    s = Settings()
    s.data_dir, s.telegram_chat_id, s.telegram_group_id, s.quiet_hours = tmp_path, ME, GROUP, None
    cli._run(s, dry_run=False)
    return sent


def news(i, course="Banco de Dados II", kind="mod", **extra):
    return Notice(f"{kind}:{i}", "group", "📝", f"Nova atividade: Tarefa {i}", course,
                  url=f"https://nead.ifb.edu.br/mod/assign/view.php?id={i}", extra=extra)


def test_group_gets_one_summary_per_slot_and_me_everything_now(tmp_path, monkeypatch):
    run_at(tmp_path, monkeypatch, datetime(2026, 10, 10, 8, 5, tzinfo=TZ), [])   # resumo das 8h já passou
    t1 = datetime(2026, 10, 10, 9, 30, tzinfo=TZ)
    sent = run_at(tmp_path, monkeypatch, t1, [news(1), news(2, "Sistemas Operacionais")])
    assert [c for c, _ in sent] == [ME, ME]                         # chat pessoal: na hora; grupo: espera
    sent = run_at(tmp_path, monkeypatch, datetime(2026, 10, 10, 11, 0, tzinfo=TZ), [news(3)])
    assert [c for c, _ in sent] == [ME]
    sent = run_at(tmp_path, monkeypatch, datetime(2026, 10, 10, 13, 5, tzinfo=TZ), [])   # 13h: resumo
    group = [t for c, t in sent if c == GROUP]
    assert len(group) == 1 and "Novidades da turma" in group[0]
    assert group[0].index("Banco de Dados II") < group[0].index("Sistemas Operacionais")
    assert group[0].count("Nova atividade") == 3 and 'href="https://nead.ifb.edu.br/mod/assign/view.php?id=1"' in group[0]
    assert not run_at(tmp_path, monkeypatch, datetime(2026, 10, 10, 13, 20, tzinfo=TZ), [])   # não repete
    st = State(tmp_path / "state.json", key=state_key())
    assert st.data["group_queue"] == [] and st.data["group_last_slot"] == "2026-10-10 13"


def test_urgent_goes_to_group_right_away(tmp_path, monkeypatch):
    urgent = [Notice("due:5:0", "group", "⏰", "Prazo HOJE: Tarefa 5", "BD II", extra={"urgent": True, "event": 5}),
              Notice("duechange:6:abc", "group", "📅", "Prazo alterado: Tarefa 6", "BD II")]
    sent = run_at(tmp_path, monkeypatch, datetime(2026, 10, 10, 10, 0, tzinfo=TZ), urgent)
    assert [c for c, _ in sent].count(GROUP) == 2


def test_helpers():
    assert current_slot(datetime(2026, 10, 10, 7, 59, tzinfo=TZ), [8, 13, 19]) is None
    assert current_slot(datetime(2026, 10, 10, 13, 0, tzinfo=TZ), [8, 13, 19]) == "2026-10-10 13"
    assert current_slot(datetime(2026, 10, 10, 23, 0, tzinfo=TZ), [8, 13, 19]) == "2026-10-10 19"
    assert is_urgent_for_group(Notice("eventday:1", "group", "⏰", "Hoje às 19:00: Aula"))
    assert not is_urgent_for_group(Notice("post:1", "group", "📢", "Aviso"))
    many = [{"key": f"mod:{i}", "kind": "mod", "icon": "📝", "title": "x" * 200, "course": f"Sala {i % 3}",
             "url": None, "body": ""} for i in range(60)]
    parts = render(many, datetime(2026, 10, 10, 13, 0, tzinfo=TZ))
    assert len(parts) > 1 and all(len(p) <= 4000 for p in parts)
