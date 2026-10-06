"""Avisos v3: tudo o que o professor faz (alterações em atividades, fóruns, notas, eventos)."""

from datetime import timedelta

from nead_avisos.collect import Collector
from nead_avisos.config import Settings
from nead_avisos.state import State
from nead_avisos.telegram import render
from test_collect import NOW, FakeMoodle

TEACHER, CLASSMATE = 900, 901


class V3Moodle(FakeMoodle):
    def __init__(self):
        super().__init__()
        self.forums = [{"id": 50, "course": 1, "type": "news", "name": "Avisos"},
                       {"id": 51, "course": 1, "type": "general", "name": "Fórum de Dúvidas"}]
        self.discussions = {50: list(self.posts), 51: []}

    def call(self, function, **params):
        if function == "core_user_get_course_user_profiles":
            uid = params["userlist"][0]["userid"]
            if uid == TEACHER:
                return [{"roles": [{"shortname": "editingteacher"}]}]
        if function == "mod_forum_get_forums_by_courses":
            return self.forums
        if function == "mod_forum_get_forum_discussions":
            return {"discussions": self.discussions[params["forumid"]]}
        return super().call(function, **params)


def run(m, st, now):
    return Collector(Settings(), m, st, now).run()


def started(tmp_path):
    m, st = V3Moodle(), State(tmp_path / "s.json")
    run(m, st, NOW)                                   # 1ª execução: só registra o estado atual
    return m, st


def disc(i, author, n=0, tm=None, name="Dúvida", message="texto"):
    t = (tm or NOW).timestamp()
    return {"discussion": i, "name": name, "message": message, "userid": author, "userfullname": f"Pessoa {author}",
            "created": t, "timemodified": t, "numreplies": n}


def test_teacher_edits_activity_text_files_and_name(tmp_path):
    m, st = started(tmp_path)
    mod = m.modules[1][0]
    mod.update(name="Aula 1 (revisada)", description="<p>Leia o capítulo 3</p>",
               contents=[{"type": "file", "filename": "slides.pdf", "timemodified": 1}])
    out = run(m, st, NOW + timedelta(minutes=15))
    edit = next(n for n in out if n.key.startswith("edit:11:"))
    assert edit.audience == "group" and edit.title == "Atividade alterada pelo professor: Aula 1 (revisada)"
    text = render(edit)
    assert "Nome: <s>Aula 1</s> → <b>Aula 1 (revisada)</b>" in text
    assert "Enunciado/descrição atualizado" in text and "Leia o capítulo 3" in text
    assert "📎 Arquivo novo: slides.pdf" in text
    mod["contents"][0]["timemodified"] = 2                                     # professor troca o arquivo
    again = [n for n in run(m, st, NOW + timedelta(minutes=30)) if n.key.startswith("edit:11:")]
    assert len(again) == 1 and "Arquivo atualizado: slides.pdf" in again[0].body
    assert not [n for n in run(m, st, NOW + timedelta(minutes=45)) if n.key.startswith("edit:")]   # sem repetir


def test_existing_installation_gets_new_notice_types_without_flood(tmp_path):
    m, st = V3Moodle(), State(tmp_path / "s.json")
    st.data = {"initialized": NOW.isoformat(), "seen": {}}                     # instalação antiga (antes da v3)
    m.grades[1] = [{"id": 5, "itemtype": "mod", "itemname": "Tarefa 1", "gradeformatted": "8,00", "cmid": 11}]
    m.discussions[51] = [disc(70, CLASSMATE)]
    first = run(m, st, NOW)
    assert not [n for n in first if n.key.startswith(("grade:", "topic:", "edit:", "event:"))]
    m.grades[1][0]["gradeformatted"] = "9,00"
    later = run(m, st, NOW + timedelta(minutes=15))
    assert [n.title for n in later if n.key.startswith("grade:")] == ["Nota alterada: Tarefa 1"]


def test_forum_topics_and_replies_teacher_to_group_classmate_to_me(tmp_path):
    m, st = started(tmp_path)
    m.discussions[51] = [disc(71, TEACHER, name="Plantão de dúvidas"), disc(72, CLASSMATE, name="Ajuda SQL")]
    out = {n.key: n for n in run(m, st, NOW + timedelta(minutes=15))}
    assert out["topic:71"].audience == "group" and "(professor/mediação)" in out["topic:71"].body
    assert out["topic:72"].audience == "me"
    # professor responde no tópico do colega
    later = NOW + timedelta(minutes=20)
    m.discussions[51][1] = disc(72, CLASSMATE, n=1, tm=later, name="Ajuda SQL")
    m.discussions[51][1]["created"] = NOW.timestamp()
    m.replies[72] = [{"id": 801, "parentid": 800, "timecreated": later.timestamp(), "message": "<p>Use JOIN</p>",
                      "author": {"id": TEACHER, "fullname": "Prof. Ana"}}]
    reply = next(n for n in run(m, st, NOW + timedelta(minutes=30)) if n.key.startswith("reply:72:"))
    assert reply.audience == "group" and reply.title == "Professor respondeu em: Ajuda SQL"
    assert "Prof. Ana" in reply.body and "Use JOIN" in reply.body


def test_announcement_edited_by_teacher(tmp_path):
    m, st = started(tmp_path)
    post = dict(m.discussions[50][0], userid=TEACHER, timemodified=(NOW + timedelta(minutes=5)).timestamp(),
                numreplies=0, message="<p>Aula remarcada para 20h</p>", usermodifiedfullname="Prof. Ana")
    m.discussions[50] = [post]
    edited = [n for n in run(m, st, NOW + timedelta(minutes=15)) if n.key.startswith("postedit:")]
    assert len(edited) == 1 and edited[0].title == "Aviso editado: Bem-vindos" and "remarcada" in edited[0].body


def test_grade_and_teacher_feedback_only_to_me(tmp_path):
    m, st = started(tmp_path)
    m.grades[1] = [{"id": 5, "itemtype": "mod", "itemname": "Tarefa 1", "gradeformatted": "-", "cmid": 11},
                   {"id": 6, "itemtype": "course", "itemname": None, "gradeformatted": "10,00"}]
    run(m, st, NOW + timedelta(minutes=10))
    m.grades[1][0].update(gradeformatted='<i class="icon"></i>10,00', rangeformatted="0&ndash;10",
                          feedback="<p>Ótimo trabalho!</p>")
    out = [n for n in run(m, st, NOW + timedelta(minutes=20)) if n.key.startswith(("grade:", "feedback:"))]
    assert len(out) == 1 and out[0].audience == "me" and out[0].title == "Nota lançada: Tarefa 1"
    assert "<b>10,00</b>" in out[0].body and "0–10" in out[0].body and "Ótimo trabalho!" in out[0].body
    assert out[0].url == "https://m/mod/page/view.php?id=11"


def test_configuration_change_reported_by_moodle(tmp_path):
    m, st = started(tmp_path)
    m.updates[1] = [{"contextlevel": "module", "id": 11,
                     "updates": [{"name": "configuration", "timeupdated": int(NOW.timestamp()) + 60}]}]
    cfg = [n for n in run(m, st, NOW + timedelta(minutes=15)) if n.key.startswith("cfg:")]
    assert len(cfg) == 1 and cfg[0].title == "Configuração alterada: Aula 1" and cfg[0].audience == "group"


def test_new_class_event_and_same_day_reminder(tmp_path):
    m, st = started(tmp_path)
    start = NOW + timedelta(hours=10)
    m.events = [{"id": 31, "name": "Aula síncrona", "eventtype": "course", "courseid": 1,
                 "timestart": start.timestamp(), "timeduration": 3600, "description": "<p>Link no Meet</p>"}]
    out = {n.key: n for n in run(m, st, NOW + timedelta(minutes=15))}
    assert out["event:31"].title == "Novo evento: Aula síncrona" and out["event:31"].audience == "group"
    assert out["eventday:31"].title.startswith("Hoje às")
    m.events[0]["timestart"] = (start + timedelta(days=1)).timestamp()
    changed = [n for n in run(m, st, NOW + timedelta(minutes=30)) if n.key.startswith("eventchange:31")]
    assert len(changed) == 1 and changed[0].title == "Evento alterado: Aula síncrona"
