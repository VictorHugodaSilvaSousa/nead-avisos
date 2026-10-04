"""Descobre o que há de novo no Moodle para o aluno e transforma em avisos.

Tipos de aviso (audience: 'me' = só o seu chat; 'group' = também o grupo da turma):
  nova atividade/material (group) · aviso no fórum de Avisos (group) · lembrete de prazo (group, pelo
  calendário da sala) · seu prazo ainda não entregue (me) · notificação do Moodle (me) · mensagem (me) ·
  resumo diário de prazos (me + group)

Primeira execução: só registra o estado atual (não envia uma enxurrada de "novidades" antigas).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .config import Settings
from .moodle import Moodle
from .state import State

ACTIVITY_LABEL = {"assign": "Tarefa", "quiz": "Questionário", "forum": "Fórum", "resource": "Arquivo",
                  "page": "Página", "url": "Link", "folder": "Pasta", "lesson": "Lição", "h5pactivity": "H5P",
                  "questionnaire": "Enquete", "choice": "Escolha", "feedback": "Pesquisa", "book": "Livro",
                  "label": "Rótulo", "glossary": "Glossário", "wiki": "Wiki", "workshop": "Laboratório"}
SKIP_MODULES = {"label"}
MATERIAL_LABELS = {"Arquivo", "Página", "Link", "Pasta", "Livro", "url", "resource", "page", "folder", "book"}            # rótulos são texto solto na página do curso, não "atividade"
_PREFIX_RE = re.compile(r"^\s*\[[^\]]+\]\s*")


@dataclass
class Notice:
    key: str                         # identificador único (evita repetir)
    audience: str                    # 'me' | 'group'
    icon: str
    title: str
    course: str = ""
    body: str = ""
    url: str | None = None
    when: datetime | None = None
    extra: dict = field(default_factory=dict)


_TERM_RE = re.compile(r"(?<!\d)(20\d{2})\s*[/.-]\s*([12])(?!\d)")


def term_of(name: str) -> str | None:
    m = _TERM_RE.search(name or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


WEEKDAYS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
DATE_LABEL = {"allowsubmissionsfromdate": "Abre", "timeopen": "Abre", "timeavailablefrom": "Abre",
              "duedate": "Prazo", "deadline": "Prazo", "timeclose": "Fecha", "cutoffdate": "Aceita atraso até",
              "timeavailableto": "Fecha", "gradingduedate": None}
DUE_KEYS = ("duedate", "timeclose", "deadline", "timeavailableto")
# Prazos de entrega de verdade. 'expectcompletionon' (data ESPERADA de conclusão, ex.: "Slides ... deve estar
# concluído") é só sugestão do professor e não entra em lembretes nem em "prazo perdido".
REAL_DEADLINES = ("due", "close")


def h(text) -> str:
    """Escapa texto que entra numa mensagem com formatação (<b>, <i>, <a>)."""
    return html.escape("" if text is None else str(text), quote=True)


def fmt(dt: datetime) -> str:
    """'08/10 (qua) 23:59' — dia da semana em português em qualquer sistema (a nuvem roda em inglês)."""
    return f"{dt:%d/%m} ({WEEKDAYS[dt.weekday()]}) {dt:%H:%M}"


def clean_event_name(name: str) -> str:
    return re.sub(r" (está marcado|vence|é devido|deve ser|should be|is due).*$", "", name or "")


def short_course(name: str) -> str:
    """'[TDS_M3] Banco de Dados II 2026/2' -> 'Banco de Dados II'."""
    name = _PREFIX_RE.sub("", name)
    return re.sub(r"\s*\(?\b20\d{2}\s*[/.-]\s*[12]\)?\s*$", "", name).strip() or name


def plain(text: str | None, limit: int = 600) -> str:
    """HTML do Moodle -> texto simples, curto."""
    text = re.sub(r"<(br|/p|/div|/li)\s*/?>", "\n", text or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\xa0]+", " ", text)).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


class Collector:
    def __init__(self, s: Settings, m: Moodle, state: State, now: datetime | None = None) -> None:
        self.s, self.m, self.state = s, m, state
        self.now = now or datetime.now(s.tz)
        self.notices: list[Notice] = []
        self.first_run = not state.data.get("initialized")
        self.instance_url: dict[tuple[str, int], str] = {}   # (tipo, instância) -> link, para o calendário

    # ------------------------------------------------------------------ salas acompanhadas
    def courses(self) -> list[dict]:
        info = self.m.call("core_webservice_get_site_info")
        self.userid = info["userid"]
        enrolled = self.m.call("core_enrol_get_users_courses", userid=self.userid)
        now_ts = self.now.timestamp()
        out = []
        student = [c for c in enrolled if c["id"] in self.s.include_courses or "student" in self._roles(c["id"])]
        terms = [term_of(c["fullname"]) for c in student if term_of(c["fullname"])]
        latest = max(terms) if terms else None
        for c in student:
            if c["id"] in self.s.exclude_courses:
                continue
            forced = c["id"] in self.s.include_courses
            ended = bool(c.get("enddate")) and c["enddate"] < now_ts - 7 * 86400
            old_term = term_of(c["fullname"]) is not None and term_of(c["fullname"]) < latest
            if forced or not (ended or old_term):   # só salas onde você é ALUNO e que estão em andamento
                out.append(c)
        self.latest_term = latest
        return out

    def _roles(self, course_id: int) -> set[str]:
        cache = self.state.data.setdefault("roles", {})
        key = str(course_id)
        if key not in cache:
            prof = self.m.call("core_user_get_course_user_profiles",
                               userlist=[{"userid": self.userid, "courseid": course_id}])
            cache[key] = sorted(r["shortname"] for r in (prof[0].get("roles", []) if prof else []))
        return set(cache[key])

    def group_course_ids(self, courses: list[dict]) -> set[int]:
        """Grupo da turma: só a SUA turma atual (salas do semestre mais recente) e a Sala da Coordenação.
        Outros cursos em que você está inscrito (ex.: outros programas) vão só para o seu chat."""
        if self.s.group_courses:
            return set(self.s.group_courses)
        latest = getattr(self, "latest_term", None)
        return {c["id"] for c in courses
                if (latest and term_of(c["fullname"]) == latest) or "coordena" in c["fullname"].lower()}

    # ------------------------------------------------------------------ coleta
    def run(self) -> list[Notice]:
        courses = self.courses()
        self.state.data["courses"] = {str(c["id"]): c["fullname"] for c in courses}
        group_ids = self.group_course_ids(courses)
        for c in courses:
            aud = "group" if c["id"] in group_ids else "me"
            self._new_modules(c, aud)
        self._forum_news(courses, group_ids)
        self._course_deadlines(courses, group_ids)
        self._my_deadlines()
        self._notifications()
        self._messages()
        self._daily_digest(courses, group_ids)
        self._my_digest()
        self._group_bursts()
        if self.first_run:
            self.state.data["initialized"] = self.now.isoformat()
            baseline = len(self.notices)
            # Na nuvem (ou quando já existe outra instalação), a 1ª execução fica TOTALMENTE silenciosa:
            # o resumo do dia já pode ter sido enviado pela instalação do PC.
            self.notices = [] if self.s.silent_first_run else [n for n in self.notices if n.key.startswith("digest:")]
            self.state.data["baseline_items"] = baseline
        return self.notices

    def _seen(self, key: str) -> bool:
        seen = self.state.data.setdefault("seen", {})
        if key in seen:
            return True
        seen[key] = self.now.isoformat(timespec="seconds")
        return False

    def _new_modules(self, c: dict, aud: str) -> None:
        sections = self.m.call("core_course_get_contents", courseid=c["id"])
        dues = self.state.data.setdefault("dues", {})
        for sec in sections:
            for mod in sec.get("modules", []):
                if mod.get("instance") and mod.get("url"):
                    self.instance_url[(mod.get("modname"), mod["instance"])] = mod["url"]
                if mod.get("modname") in SKIP_MODULES or not mod.get("uservisible", True) or not mod.get("visible", 1):
                    continue
                dates = {d.get("dataid"): d.get("timestamp") for d in mod.get("dates", []) if d.get("timestamp")}
                due = next((dates[k] for k in DUE_KEYS if dates.get(k)), None)
                key = f"mod:{mod['id']}"
                label = ACTIVITY_LABEL.get(mod.get("modname"), mod.get("modname", "Item"))
                course = short_course(c["fullname"])
                # Prazo alterado pelo professor (só para itens já conhecidos)
                old_due = dues.get(str(mod["id"]))
                if due:
                    dues[str(mod["id"])] = due
                if old_due and due and old_due != due and not self.first_run:
                    before = datetime.fromtimestamp(old_due, self.s.tz)
                    after = datetime.fromtimestamp(due, self.s.tz)
                    self.notices.append(Notice(
                        f"duechange:{mod['id']}:{due}", aud, "📅", f"Prazo alterado: {mod['name']}", course,
                        f"<s>{h(fmt(before))}</s> → <b>{h(fmt(after))}</b>", mod.get("url"), after))
                if self._seen(key):
                    continue
                lines = [f"{h(label)} · seção <b>{h(sec.get('name') or 'curso')}</b>"]
                for dataid, ts in dates.items():
                    name = DATE_LABEL.get(dataid)
                    if name:
                        lines.append(f"{name}: {h(fmt(datetime.fromtimestamp(ts, self.s.tz)))}")
                desc = plain(mod.get("description"), 300)
                if desc:
                    lines.append(f"<i>{h(desc)}</i>")
                self.notices.append(Notice(key, aud, "📝", f"Nova {'atividade' if label not in MATERIAL_LABELS else 'publicação'}: {mod['name']}",
                                           course, "\n".join(lines), mod.get("url"),
                                           extra={"kind": "mod", "course": course, "name": mod["name"],
                                                  "label": label, "due": due}))

    def _forum_news(self, courses: list[dict], group_ids: set[int]) -> None:
        forums = self.m.call("mod_forum_get_forums_by_courses", courseids=[c["id"] for c in courses])
        names = {c["id"]: c["fullname"] for c in courses}
        for f in forums:
            if f.get("type") != "news" and "aviso" not in (f.get("name") or "").lower():
                continue
            data = self.m.call("mod_forum_get_forum_discussions", forumid=f["id"], sortorder=1, page=0, perpage=10)
            for d in data.get("discussions", []):
                if self._seen(f"post:{d['discussion']}"):
                    continue
                aud = "group" if f["course"] in group_ids else "me"
                created = datetime.fromtimestamp(d.get("created") or d.get("timemodified", 0), self.s.tz)
                self.notices.append(Notice(
                    f"post:{d['discussion']}", aud, "📢", d.get("name") or d.get("subject") or "Aviso",
                    short_course(names.get(f["course"], "")),
                    f"<i>{h(d.get('userfullname', ''))}</i> · {h(fmt(created))}\n{h(plain(d.get('message')))}",
                    self.m.url(f"mod/forum/discuss.php?d={d['discussion']}"), created))

    def _course_deadlines(self, courses: list[dict], group_ids: set[int]) -> None:
        """Lembretes de prazo iguais para toda a turma (calendário da sala)."""
        horizon = max(self.s.reminder_days + [0])
        events = self.m.call("core_calendar_get_calendar_events",
                             events={"courseids": [c["id"] for c in courses]},
                             options={"timestart": int(self.now.timestamp()),
                                      "timeend": int((self.now + timedelta(days=horizon + 1)).timestamp())})
        names = {c["id"]: c["fullname"] for c in courses}
        for ev in events.get("events", []):
            if ev.get("eventtype") not in REAL_DEADLINES or not ev.get("modulename"):
                continue
            due = datetime.fromtimestamp(ev["timestart"], self.s.tz)
            days = (due.date() - self.now.date()).days
            stage = next((d for d in sorted(self.s.reminder_days) if days <= d), None)
            if stage is None or self._seen(f"due:{ev['id']}:{stage}"):
                continue
            aud = "group" if ev.get("courseid") in group_ids else "me"
            when = "HOJE" if days == 0 else ("amanhã" if days == 1 else f"em {days} dias")
            self.notices.append(Notice(
                f"due:{ev['id']}:{stage}", aud, "⏰", f"Prazo {when}: {clean_event_name(ev['name'])}",
                short_course(names.get(ev.get("courseid"), "")), f"Entrega até {fmt(due)}",
                self.instance_url.get((ev["modulename"], ev.get("instance"))), due))

    def _my_events(self, days_back: int = 30, days_ahead: int = 7) -> list[dict]:
        """Seus itens AINDA NÃO CONCLUÍDOS (o Moodle tira da lista o que você já entregou)."""
        if not hasattr(self, "_my_cache"):
            data = self.m.call("core_calendar_get_action_events_by_timesort",
                               timesortfrom=int((self.now - timedelta(days=days_back)).timestamp()),
                               timesortto=int((self.now + timedelta(days=days_ahead)).timestamp()), limitnum=50)
            # A lista do Moodle mistura TODAS as salas da conta (inclusive onde você é mediador) e inclui a
            # "data esperada de conclusão" de materiais. Aqui ficam só prazos REAIS das salas em que você é aluno.
            tracked = {int(k) for k in self.state.data.get("courses", {})}
            self._my_cache = [e for e in data.get("events", [])
                              if (e.get("course") or {}).get("id") in tracked
                              and e.get("eventtype") in REAL_DEADLINES]
        return self._my_cache

    def _my_deadlines(self) -> None:
        """Só no seu chat: lembretes do que VOCÊ ainda não entregou (3 dias, 1 dia, no dia, 6 horas antes)
        e aviso único de prazo PERDIDO, dizendo se o Moodle ainda aceita envio atrasado."""
        for ev in self._my_events():
            due = datetime.fromtimestamp(ev["timesort"], self.s.tz)
            course = short_course((ev.get("course") or {}).get("fullname", ""))
            name = clean_event_name(ev.get("name"))
            actionable = (ev.get("action") or {}).get("actionable", True)
            if due < self.now:
                if self._seen(f"late:{ev['id']}"):
                    continue
                body = (f"Venceu {fmt(due)}.\n" + ("O Moodle ainda aceita envio atrasado: envie o quanto antes."
                                                    if actionable else
                                                    "O envio está encerrado: fale com o professor ou o mediador."))
                self.notices.append(Notice(f"late:{ev['id']}", "me", "⚠️", f"Prazo perdido: {name}", course, body,
                                           ev.get("url"), due))
                continue
            if not actionable:
                continue
            hours = (due - self.now).total_seconds() / 3600
            days = (due.date() - self.now.date()).days
            stage = "6h" if hours <= 6 else next((f"{d}d" for d in sorted(self.s.reminder_days) if days <= d), None)
            if stage is None or self._seen(f"mine:{ev['id']}:{stage}"):
                continue
            when = (f"em {max(int(hours), 1)} hora(s)" if stage == "6h" else
                    "HOJE" if days == 0 else "amanhã" if days == 1 else f"em {days} dias")
            self.notices.append(Notice(f"mine:{ev['id']}:{stage}", "me", "🔴", f"Você ainda não entregou ({when}): {name}",
                                       course, f"Vence {fmt(due)}", ev.get("url"), due))

    def _my_digest(self) -> None:
        """Uma vez por dia, só no seu chat: tudo o que está atrasado e o que vence nos próximos 7 dias."""
        key = f"mydigest:{self.now:%Y-%m-%d}"
        if self.now.hour < self.s.digest_hour or key in self.state.data.setdefault("seen", {}):
            return
        self._seen(key)
        late, soon = [], []
        for ev in sorted(self._my_events(), key=lambda e: e["timesort"]):
            due = datetime.fromtimestamp(ev["timesort"], self.s.tz)
            course = short_course((ev.get("course") or {}).get("fullname", ""))
            line = f"• {fmt(due)} — {course}: {clean_event_name(ev.get('name'))}"
            if due < self.now:
                if (ev.get("action") or {}).get("actionable", True):
                    late.append(line + " (ainda aceita envio)")
            else:
                soon.append(line)
        if not late and not soon:
            body = "Nada pendente para os próximos 7 dias. 🎉"
        else:
            body = ""
            if late:
                body += "⚠️ Atrasadas (ainda dá para enviar):\n" + "\n".join(late) + "\n\n"
            if soon:
                body += "⏳ Vencem nos próximos 7 dias:\n" + "\n".join(soon)
        self.notices.append(Notice(key, "me", "📋", f"Suas pendências ({self.now:%d/%m})", "", body.strip()))

    def _notifications(self) -> None:
        data = self.m.call("message_popup_get_popup_notifications", useridto=self.userid, newestfirst=1, limit=20,
                           offset=0)
        for n in data.get("notifications", []):
            if self._seen(f"notif:{n['id']}"):
                continue
            self.notices.append(Notice(f"notif:{n['id']}", "me", "🔔", plain(n.get("subject"), 150), "",
                                       plain(n.get("smallmessage") or n.get("fullmessage"), 400),
                                       n.get("contexturl"),
                                       datetime.fromtimestamp(n.get("timecreated", 0), self.s.tz)))

    def _messages(self) -> None:
        data = self.m.call("core_message_get_conversations", userid=self.userid, limitfrom=0, limitnum=20)
        for conv in data.get("conversations", []):
            msgs = conv.get("messages") or []
            if not conv.get("unreadcount") or not msgs:
                continue
            last = msgs[0]
            if last.get("useridfrom") == self.userid or self._seen(f"msg:{last['id']}"):
                continue
            who = next((m.get("fullname") for m in conv.get("members", []) if m.get("id") == last.get("useridfrom")),
                       conv.get("name") or "")
            self.notices.append(Notice(f"msg:{last['id']}", "me", "✉️", f"Mensagem de {who}", "",
                                       plain(last.get("text"), 400), self.m.url(f"message/index.php?id={last.get('useridfrom')}"),
                                       datetime.fromtimestamp(last.get("timecreated", 0), self.s.tz)))

    def _daily_digest(self, courses: list[dict], group_ids: set[int]) -> None:
        """Uma vez por dia (a partir de RESUMO_HORA): prazos dos próximos 7 dias."""
        key = f"digest:{self.now:%Y-%m-%d}"
        if self.now.hour < self.s.digest_hour or key in self.state.data.setdefault("seen", {}):
            return
        events = self.m.call("core_calendar_get_calendar_events",
                             events={"courseids": [c["id"] for c in courses]},
                             options={"timestart": int(self.now.timestamp()),
                                      "timeend": int((self.now + timedelta(days=7)).timestamp())})
        names = {c["id"]: c["fullname"] for c in courses}
        items = []
        for ev in sorted(events.get("events", []), key=lambda e: e["timestart"]):
            if ev.get("eventtype") in ("due", "close") and ev.get("modulename") and ev.get("courseid") in group_ids:
                due = datetime.fromtimestamp(ev["timestart"], self.s.tz)
                items.append(f"• {fmt(due)} — {short_course(names.get(ev['courseid'], ''))}: "
                             f"{clean_event_name(ev['name'])}")
        self._seen(key)
        body = "\n".join(items) if items else "Nenhum prazo nos próximos 7 dias. 🎉"
        self.notices.append(Notice(key, "group", "🗓", f"Prazos da semana ({self.now:%d/%m})", "", body))

    def _group_bursts(self, limit: int = 3) -> None:
        """Mais de `limit` itens novos na mesma sala de uma vez -> uma mensagem só, com a lista e os links."""
        by_course: dict[tuple[str, str], list[Notice]] = {}
        for n in self.notices:
            if n.extra.get("kind") == "mod":
                by_course.setdefault((n.course, n.audience), []).append(n)
        for (course, aud), items in by_course.items():
            if len(items) <= limit:
                continue
            lines = []
            for n in items[:25]:
                link = f'<a href="{h(n.url)}">{h(n.extra["name"])}</a>' if n.url else h(n.extra["name"])
                due = (f" — prazo {h(fmt(datetime.fromtimestamp(n.extra['due'], self.s.tz)))}"
                       if n.extra.get("due") else "")
                lines.append(f"• {h(n.extra['label'])}: {link}{due}")
            if len(items) > 25:
                lines.append(f"… e mais {len(items) - 25}")
            merged = Notice("bulk:" + ",".join(n.key for n in items), aud, "📝",
                            f"{len(items)} novos itens publicados", course, "\n".join(lines))
            merged.extra = {"keys": [n.key for n in items]}
            self.notices = [n for n in self.notices if n not in items] + [merged]
