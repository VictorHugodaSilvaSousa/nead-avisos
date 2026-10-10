"""Prazo que existe na atividade mas não no calendário (caso real: BD II, 'Entregar trabalho - parte 2 - SQL'),
e prazo escrito só no nome da atividade: também viram lembrete e entram nos prazos da semana."""

from datetime import timedelta

from nead_avisos.collect import Collector
from nead_avisos.config import Settings
from nead_avisos.state import State
from nead_avisos.telegram import render
from test_collect import NOW, FakeMoodle


def run(m, st, now):
    return Collector(Settings(), m, st, now).run()


def started(tmp_path):
    m, st = FakeMoodle(), State(tmp_path / "s.json")
    run(m, st, NOW)
    return m, st


def test_activity_deadline_missing_from_calendar_still_reminds(tmp_path):
    m, st = started(tmp_path)
    due = (NOW + timedelta(days=1)).replace(hour=22, minute=0)
    m.modules[1].append({"id": 40, "name": "Trabalho & SQL", "modname": "assign", "instance": 140,
                         "url": "https://nead.ifb.edu.br/mod/assign/view.php?id=40",
                         "dates": [{"dataid": "duedate", "timestamp": due.timestamp()}]})
    out = {n.key: n for n in run(m, st, NOW + timedelta(minutes=15))}
    rem = out["due:m40:1"]
    assert rem.title == "Prazo amanhã: Trabalho & SQL" and rem.audience == "group"
    assert "não está no calendário" in rem.body
    assert "Trabalho &amp; SQL" in render(rem) and "&amp;amp;" not in render(rem)


def test_no_duplicate_when_calendar_has_it(tmp_path):
    m, st = started(tmp_path)
    due = NOW + timedelta(days=1)
    m.modules[1].append({"id": 41, "name": "Tarefa no calendário", "modname": "assign", "instance": 141,
                         "url": "https://nead.ifb.edu.br/mod/assign/view.php?id=41",
                         "dates": [{"dataid": "duedate", "timestamp": due.timestamp()}]})
    m.events = [{"id": 9, "name": "Tarefa no calendário está marcado(a) para esse prazo", "eventtype": "due",
                 "modulename": "assign", "instance": 141, "courseid": 1, "timestart": due.timestamp()}]
    keys = [n.key for n in run(m, st, NOW + timedelta(minutes=15)) if n.key.startswith("due:")]
    assert keys == ["due:9:1"]


def test_deadline_only_in_the_name_says_end_of_day(tmp_path):
    m, st = started(tmp_path)
    when = NOW + timedelta(days=3)
    m.modules[1].append({"id": 42, "name": f"ENTREGA: Ideias (NOVO PRAZO: ATÉ {when.day} DE OUTUBRO)",
                         "modname": "assign", "instance": 142, "url": "https://nead.ifb.edu.br/mod/assign/view.php?id=42"})
    rem = next(n for n in run(m, st, NOW + timedelta(minutes=15)) if n.key.startswith("due:m42:"))
    assert "até o fim do dia" in rem.body and "nome da atividade" in rem.body
