# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
from datetime import timedelta

from nead_avisos.collect import Collector, fmt
from nead_avisos.config import Settings
from nead_avisos.state import State
from nead_avisos.telegram import render
from test_collect import NOW, FakeMoodle


class MyEventsMoodle(FakeMoodle):
    def __init__(self):
        super().__init__()
        self.my = []

    def call(self, function, **params):
        if function == "core_calendar_get_action_events_by_timesort":
            lo, hi = params["timesortfrom"], params["timesortto"]
            return {"events": [e for e in self.my if lo <= e["timesort"] <= hi]}
        return super().call(function, **params)


def run(m, state, now):
    return Collector(Settings(), m, state, now).run()


def ev(i, due, actionable=True, name="Tarefa X está marcado(a) para esse prazo", course=1, eventtype="due"):
    return {"id": i, "name": name, "timesort": due.timestamp(), "url": f"https://m/mod/assign/view.php?id={i}",
            "eventtype": eventtype, "action": {"actionable": actionable},
            "course": {"id": course, "fullname": "[TDS_M3] Banco de Dados II 2026/2"}}


def test_missed_deadline_once_and_says_if_late_submission_allowed(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    m.my = [ev(1, NOW - timedelta(days=2), True), ev(2, NOW - timedelta(days=1), False)]
    late = {n.key: n for n in run(m, st, NOW + timedelta(minutes=20)) if n.key.startswith("late:")}
    assert "ainda aceita envio atrasado" in late["late:1"].body
    assert "envio está encerrado" in late["late:2"].body
    assert late["late:1"].audience == "me" and late["late:1"].title == "Prazo perdido: Tarefa X"
    assert not [n for n in run(m, st, NOW + timedelta(minutes=40)) if n.key.startswith("late:")]   # uma vez só


def test_personal_reminders_3d_1d_today_and_6h(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    due = NOW + timedelta(days=3, hours=4)
    run(m, st, NOW)
    m.my = [ev(5, due)]
    keys = lambda now: [n.key for n in run(m, st, now) if n.key.startswith("mine:")]  # noqa: E731
    assert keys(NOW + timedelta(minutes=10)) == ["mine:5:3d"]
    assert keys(due - timedelta(days=1)) == ["mine:5:1d"]
    assert keys(due - timedelta(hours=10)) == ["mine:5:0d"]
    assert keys(due - timedelta(hours=5)) == ["mine:5:6h"]
    assert keys(due - timedelta(hours=4)) == []


def test_my_digest_lists_late_and_upcoming(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    m.my = [ev(1, NOW + timedelta(days=1, hours=1) - timedelta(days=4), True, "Atrasada A"),
            ev(2, NOW + timedelta(days=3), True, "Próxima B")]
    nxt = (NOW + timedelta(days=1)).replace(hour=7, minute=5)
    digest = next(n for n in run(m, st, nxt) if n.key.startswith("mydigest:"))
    assert digest.audience == "me"
    assert "Atrasadas" in digest.body and "Atrasada A" in digest.body and "Próxima B" in digest.body


def test_deadline_change_detected(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    mod = {"id": 12, "name": "Tarefa 2", "modname": "assign", "url": "https://m/a?id=12", "instance": 502,
           "dates": [{"dataid": "duedate", "timestamp": (NOW + timedelta(days=5)).timestamp()}]}
    m.modules[1].append(mod)
    run(m, st, NOW)
    mod["dates"] = [{"dataid": "duedate", "timestamp": (NOW + timedelta(days=8)).timestamp()}]
    changed = [n for n in run(m, st, NOW + timedelta(minutes=20)) if n.key.startswith("duechange:")]
    assert len(changed) == 1 and changed[0].audience == "group" and "Prazo alterado" in changed[0].title
    assert "<s>" in changed[0].body and fmt(NOW + timedelta(days=8)) in changed[0].body


def test_burst_of_publications_becomes_one_message(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    m.modules[1] += [{"id": 100 + i, "name": f"Aula {i} & extras", "modname": "page",
                      "url": f"https://m/p?id={100 + i}", "instance": 600 + i} for i in range(6)]
    news = run(m, st, NOW + timedelta(minutes=20))
    bulk = [n for n in news if n.key.startswith("bulk:")]
    assert len(bulk) == 1 and not [n for n in news if n.key.startswith("mod:")]
    assert bulk[0].title == "6 novos itens publicados" and len(bulk[0].extra["keys"]) == 6
    text = render(bulk[0])
    assert "Aula 0 &amp; extras" in text and '<a href="https://m/p?id=100">' in text


def test_special_characters_are_escaped(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    m.modules[1].append({"id": 70, "name": "Q&A <revisão>", "modname": "assign", "url": "https://m/a?id=70",
                         "instance": 700, "description": "<p>Leia o <b>capítulo</b> & responda</p>"})
    n = next(n for n in run(m, st, NOW + timedelta(minutes=20)) if n.key == "mod:70")
    text = render(n)
    assert "Q&amp;A &lt;revisão&gt;" in text and "<i>Leia o capítulo &amp; responda</i>" in text


def test_weekday_in_portuguese():
    assert fmt(NOW) == "03/10 (sáb) 09:00"      # 03/10/2026 é sábado


def test_mediated_courses_and_expected_completion_are_ignored(tmp_path):
    m, st = MyEventsMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    m.my = [ev(1, NOW - timedelta(days=3), course=3),                                  # sala onde é mediador
            ev(2, NOW - timedelta(days=3), eventtype="expectcompletionon",
               name="Slides - Aula 2.3 deve estar concluído"),                          # só sugestão
            ev(3, NOW - timedelta(days=3))]                                             # prazo real, sala de aluno
    late = [n.key for n in run(m, st, NOW + timedelta(minutes=20)) if n.key.startswith("late:")]
    assert late == ["late:3"]
