# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Victor Hugo da Silva Sousa
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nead_avisos.collect import Collector, plain, short_course, term_of
from nead_avisos.config import Settings
from nead_avisos.moodle import READ_ONLY_FUNCTIONS, Moodle
from nead_avisos.state import State

TZ = ZoneInfo("America/Sao_Paulo")
NOW = datetime(2026, 10, 3, 9, 0, tzinfo=TZ)


class FakeMoodle(Moodle):
    def __init__(self):
        super().__init__("https://nead.ifb.edu.br", "t")
        self.modules = {1: [{"id": 11, "name": "Aula 1", "modname": "page", "url": "https://m/mod/page/view.php?id=11",
                             "instance": 501}]}
        self.posts = [{"discussion": 900, "name": "Bem-vindos", "message": "<p>Olá <b>turma</b></p>",
                       "userfullname": "Prof. Ana", "created": NOW.timestamp() - 3600}]
        self.events = []
        self.notifs = []
        self.convs = []
        self.updates, self.replies, self.grades = {}, {}, {}

    def call(self, function, **params):
        assert function in READ_ONLY_FUNCTIONS
        if function == "core_webservice_get_site_info":
            return {"userid": 7}
        if function == "core_enrol_get_users_courses":
            return [{"id": 1, "fullname": "[TDS_M3] Banco de Dados II 2026/2", "enddate": 0},
                    {"id": 2, "fullname": "[TDS_M2] Redes 2026/1", "enddate": 0},            # semestre encerrado
                    {"id": 3, "fullname": "[TDS_M3] Sistemas Operacionais 2026/2", "enddate": 0},  # sou mediador
                    {"id": 4, "fullname": "Bolsa Futuro Digital", "enddate": 0}]             # outro programa
        if function == "core_user_get_course_user_profiles":
            cid = params["userlist"][0]["courseid"]
            return [{"roles": [{"shortname": "med_virtual" if cid == 3 else "student"}]}]
        if function == "core_course_get_contents":
            return [{"name": "Semana 1", "modules": self.modules.get(params["courseid"], [])}]
        if function == "mod_forum_get_forums_by_courses":
            return [{"id": 50, "course": 1, "type": "news", "name": "Avisos"}]
        if function == "mod_forum_get_forum_discussions":
            return {"discussions": self.posts}
        if function == "core_calendar_get_calendar_events":
            return {"events": self.events}
        if function == "core_calendar_get_action_events_by_timesort":
            return {"events": []}
        if function == "message_popup_get_popup_notifications":
            return {"notifications": self.notifs}
        if function == "core_message_get_conversations":
            return {"conversations": self.convs}
        if function == "core_course_get_updates_since":
            return {"instances": self.updates.get(params["courseid"], [])}
        if function == "core_message_get_conversation_messages":
            conv = next(c for c in self.convs if c["id"] == params["convid"])
            return {"messages": conv["messages"], "members": conv["members"]}
        if function == "mod_forum_get_discussion_posts":
            return {"posts": self.replies.get(params["discussionid"], [])}
        if function == "gradereport_user_get_grade_items":
            return {"usergrades": [{"gradeitems": self.grades.get(params["courseid"], [])}]}
        raise AssertionError(function)


def run(m, state, now=NOW):
    return Collector(Settings(), m, state, now).run()


def test_courses_only_student_current_and_group_only_class(tmp_path):
    m = FakeMoodle()
    col = Collector(Settings(), m, State(tmp_path / "s.json"), NOW)
    courses = col.courses()
    assert [c["id"] for c in courses] == [1, 4]               # sem mediação (3) e sem semestre encerrado (2)
    assert col.group_course_ids(courses) == {1}               # outro programa não vai para o grupo da turma


def test_first_run_is_silent_then_only_news(tmp_path):
    m, state = FakeMoodle(), State(tmp_path / "s.json")
    first = run(m, state)
    assert [n.key for n in first] == ["digest:2026-10-03"]    # só o resumo do dia, sem enxurrada
    assert run(m, state, NOW + timedelta(minutes=15)) == []    # nada novo, nada enviado

    m.modules[1].append({"id": 12, "name": "Tarefa 2", "modname": "assign", "url": "https://m/mod/assign/view.php?id=12",
                         "instance": 502, "dates": [{"dataid": "duedate", "timestamp": (NOW + timedelta(days=5)).timestamp()}]})
    m.posts.insert(0, {"discussion": 901, "name": "Prova adiada", "message": "A prova foi para sexta.",
                       "userfullname": "Prof. Ana", "created": NOW.timestamp()})
    m.notifs.append({"id": 77, "subject": "Sua tarefa foi avaliada", "smallmessage": "Nota 9", "timecreated": NOW.timestamp()})
    news = run(m, state, NOW + timedelta(minutes=30))
    by_key = {n.key: n for n in news}
    assert by_key["mod:12"].audience == "group" and "Prazo: 08/10" in by_key["mod:12"].body
    assert by_key["post:901"].audience == "group" and "sexta" in by_key["post:901"].body
    assert by_key["notif:77"].audience == "me"                 # notificação pessoal nunca vai ao grupo
    assert run(m, state, NOW + timedelta(minutes=45)) == []    # não repete


def test_deadline_reminders_at_3_1_0_days(tmp_path):
    m, state = FakeMoodle(), State(tmp_path / "s.json")
    m.modules[1].append({"id": 12, "name": "Tarefa 2", "modname": "assign", "url": "https://m/mod/assign/view.php?id=12",
                         "instance": 502})
    run(m, state)
    due = NOW + timedelta(days=3, hours=2)
    m.events = [{"id": 5, "name": "Tarefa 2 está marcado(a) para esse prazo", "eventtype": "due", "modulename": "assign",
                 "instance": 502, "courseid": 1, "timestart": due.timestamp()}]
    keys = [n.key for n in run(m, state, NOW + timedelta(hours=1))]
    assert "due:5:3" in keys
    assert [n.key for n in run(m, state, NOW + timedelta(hours=2))] == []                       # não repete
    assert [n.key for n in run(m, state, due - timedelta(days=1)) if n.key.startswith("due:")] == ["due:5:1"]
    reminders = [n for n in run(m, state, due - timedelta(hours=3)) if n.key.startswith("due:")]
    assert reminders[0].key == "due:5:0" and "HOJE" in reminders[0].title
    assert reminders[0].url == "https://m/mod/assign/view.php?id=12"                           # link pela instância
    assert "está marcado" not in reminders[0].title


def test_unread_message_only_to_me(tmp_path):
    m, state = FakeMoodle(), State(tmp_path / "s.json")
    run(m, state)
    m.convs = [{"id": 40, "type": 1, "members": [{"id": 9, "fullname": "Colega"}],
                "messages": [{"id": 300, "useridfrom": 9, "text": "<p>Oi!</p>", "timecreated": NOW.timestamp()}]}]
    msgs = run(m, state, NOW + timedelta(minutes=5))
    assert [(n.key, n.audience, n.title) for n in msgs if not n.key.startswith("check:")] ==         [("msg:300", "me", "Mensagem de Colega")]


def test_helpers():
    assert short_course("[TDS_M3] Banco de Dados II 2026/2") == "Banco de Dados II"
    assert term_of("[TDS_M2] Redes 2026/1") == "2026/1" and term_of("Mediadores Virtuais") is None
    assert plain("<p>Olá&nbsp;<b>turma</b></p><p>linha 2</p>") == "Olá turma\nlinha 2"


def test_client_refuses_non_read_functions():
    with pytest.raises(PermissionError):
        Moodle("https://x", "t").call("core_message_send_instant_messages")
    writes = {"send", "update", "create", "delete", "set", "submit", "save", "mark", "add"}
    assert not [f for f in READ_ONLY_FUNCTIONS if writes & set(f.split("_"))]


def test_silent_first_run_sends_nothing(tmp_path):
    s = Settings()
    s.silent_first_run = True
    m, state = FakeMoodle(), State(tmp_path / "s.json")
    assert Collector(s, m, state, NOW).run() == []
    assert "digest:2026-10-03" in state.data["seen"]          # o resumo de hoje não sai depois
