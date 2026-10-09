"""Descobre o que há de novo no Moodle para o aluno e transforma em avisos.

Tipos de aviso (audience: 'me' = só o seu chat; 'group' = também o grupo da turma):
  nova atividade/material (group) · atividade ALTERADA pelo professor: nome, prazo, enunciado, arquivos,
  disponibilidade ou configuração (group) · aviso no fórum de Avisos, aviso editado (group) · tópico novo e
  resposta de professor em qualquer fórum (group; de colegas: me) · novo evento/aula e evento alterado (group) ·
  lembrete de prazo (group) · nota lançada/alterada e comentário do professor (me) · seu prazo ainda não
  entregue e prazo perdido (me) · notificação do Moodle sem repetir assunto (me) · TODA mensagem recebida
  (me) · verificação diária do que chegou (me) · resumos diários (me + group)

Primeira execução: só registra o estado atual (não envia uma enxurrada de "novidades" antigas).
"""

from __future__ import annotations

import html
import json
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


def left(due: datetime, now: datetime) -> str:
    """'faltam 2 dias', 'faltam 5 h', 'faltam 40 min' (ou 'venceu há 3 dias')."""
    secs = (due - now).total_seconds()
    past, secs = secs < 0, abs(secs)
    if secs >= 2 * 86400:
        txt = f"{int(secs // 86400)} dias"
    elif secs >= 86400:
        txt = f"1 dia e {int(secs % 86400 // 3600)} h"
    elif secs >= 3600:
        txt = f"{int(secs // 3600)} h"
    else:
        txt = f"{max(int(secs // 60), 1)} min"
    return f"venceu há {txt}" if past else f"faltam {txt}"


def sent_label(dt: datetime, now: datetime) -> str:
    """Quando algo foi ENVIADO, sem ambiguidade: 'hoje às 08:15', 'ontem (07/10, qua) às 21:10',
    'em 05/10 (seg) às 21:10'. (Uma data solta parecia ser a data de hoje.)"""
    days = (now.date() - dt.date()).days
    if days == 0:
        return f"hoje às {dt:%H:%M}"
    if days == 1:
        return f"ontem ({dt:%d/%m}, {WEEKDAYS[dt.weekday()]}) às {dt:%H:%M}"
    return f"em {dt:%d/%m} ({WEEKDAYS[dt.weekday()]}) às {dt:%H:%M}"


def clean_event_name(name: str) -> str:
    return re.sub(r" (está marcado|vence|é devido|deve ser|should be|is due).*$", "", name or "")


def short_course(name: str) -> str:
    """'[TDS_M3] Banco de Dados II 2026/2' -> 'Banco de Dados II'."""
    name = _PREFIX_RE.sub("", name)
    return re.sub(r"\s*\(?\b20\d{2}\s*[/.-]\s*[12]\)?\s*$", "", name).strip() or name


def digest(text: str | None) -> str:
    """Impressão digital de um texto: permite saber se MUDOU sem guardar o texto no estado."""
    import hashlib
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16] if text else ""


def as_digest(value) -> str:
    """Valor guardado no estado como hash. Estado antigo guardava o texto: converte na hora (sem falso 'alterado')."""
    if not value:
        return ""
    value = str(value)
    return value if re.fullmatch(r"[0-9a-f]{16}", value) else digest(value)


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
        self.mods: dict[int, dict] = {}        # cmid -> {name, url, new} (para avisos de configuração)
        self.mod_url: dict[int, str] = {}      # cmid -> link (para notas)
        self.edited: set[int] = set()          # cmids com aviso de alteração nesta execução
        self.covered: dict[str, str] = {}      # notificação do Moodle não reenviada -> por quê (verificação)
        self._notif_twins: set[tuple] = set()
        self.commands: list[tuple[int, str]] = []    # (id da atualização, comando) pedidos por você ao robô

    # ------------------------------------------------------------------ salas acompanhadas
    def courses(self) -> list[dict]:
        info = self.m.call("core_webservice_get_site_info")
        self.userid = info["userid"]
        enrolled = self.m.call("core_enrol_get_users_courses", userid=self.userid)
        self.short_names = {c.get("shortname", ""): short_course(c["fullname"]) for c in enrolled if c.get("shortname")}
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
        self.silent_edits = self._feature_silent("edits")
        for c in courses:
            aud = "group" if c["id"] in group_ids else "me"
            self._new_modules(c, aud)
        self._config_updates(courses, group_ids)
        self._forums(courses, group_ids)
        self._grades(courses)
        self._events(courses, group_ids)
        self._course_deadlines(courses, group_ids)
        self._my_deadlines()
        self._notifications()
        self._messages()
        self._daily_digest(courses, group_ids)
        self._my_digest()
        self._daily_check()
        self._commands(courses, group_ids)
        self._no_double_reminders()
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
                self.mod_url[mod["id"]] = mod.get("url")
                self.mods[mod["id"]] = {"name": mod.get("name"), "url": mod.get("url"),
                                        "new": key not in self.state.data.setdefault("seen", {})}
                self._activity_edits(mod, c, aud, self.silent_edits)
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
                short_course(names.get(ev.get("courseid"), "")), f"Entrega até {fmt(due)} — {left(due, self.now)}",
                self.instance_url.get((ev["modulename"], ev.get("instance"))), due,
                extra={"event": ev["id"], "urgent": days == 0}))

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
                                           ev.get("url"), due, extra={"urgent": actionable}))
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
                                       course, f"Vence {fmt(due)} — <b>{h(left(due, self.now))}</b>", ev.get("url"),
                                       due, extra={"event": ev["id"], "urgent": stage in ("6h", "0d")}))

    def _my_digest(self, force_key: str | None = None) -> None:
        """Uma vez por dia, só no seu chat: tudo o que está atrasado e o que vence nos próximos 7 dias.
        Com force_key: agora, a pedido (comando /pendencias)."""
        key = force_key or f"mydigest:{self.now:%Y-%m-%d}"
        if not force_key and (self.now.hour < self.s.digest_hour or key in self.state.data.setdefault("seen", {})):
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

    # ------------------------------------------------------------------ caixa de entrada (notificações e mensagens)
    REMINDER_TYPES = {"assign_due_soon", "assign_due_digest", "assign_overdue", "quiz_open_soon", "quiz_due_soon"}

    @staticmethod
    def _ref(url: str | None) -> str | None:
        """Assunto de um link do Moodle: discussão do fórum ('d:123') ou atividade ('cm:456')."""
        if not url:
            return None
        m = re.search(r"discuss\.php\?d=(\d+)", url)
        if m:
            return f"d:{m.group(1)}"
        m = re.search(r"/mod/\w+/view\.php\?id=(\d+)", url)
        return f"cm:{m.group(1)}" if m else None

    def _remember_refs(self) -> None:
        refs = self.state.data.setdefault("refs", {})
        for n in self.notices:
            if (ref := self._ref(n.url)) is not None:
                refs[ref] = self.now.isoformat(timespec="seconds")
        limit = (self.now - timedelta(days=30)).isoformat()
        self.state.data["refs"] = {k: v for k, v in refs.items() if v >= limit}

    def _notifications(self) -> None:
        """Tudo o que o Moodle notifica para você. Lembretes de prazo do Moodle e notificações de um assunto que
        já foi avisado (mesma discussão/atividade) não se repetem; o resto chega aqui."""
        self._remember_refs()
        refs = self.state.data.get("refs", {})
        data = self.m.call("message_popup_get_popup_notifications", useridto=self.userid, newestfirst=1, limit=50,
                           offset=0)
        self.inbox_notifs = data.get("notifications", [])
        for n in self.inbox_notifs:
            key = f"notif:{n['id']}"
            if self._seen(key):
                continue
            if n.get("eventtype") in self.REMINDER_TYPES:
                self.covered[key] = "lembrete de prazo do NEAD Avisos"
                continue
            if (ref := self._ref(n.get("contexturl"))) and ref in refs:
                self.covered[key] = "mesmo assunto já avisado"
                continue
            icon, title, course, body = self._humanize(n)
            twin = (title, n.get("contexturl"))
            if twin in self._notif_twins:            # o Moodle às vezes manda a mesma notificação 2 vezes
                self.covered[key] = "notificação repetida do Moodle"
                continue
            self._notif_twins.add(twin)
            self.notices.append(Notice(key, "me", icon, title, course, body, n.get("contexturl"),
                                       datetime.fromtimestamp(n.get("timecreated", 0), self.s.tz),
                                       extra={"kind": "notif", "quiet": icon == "✅"}))   # confirmação: sem som

    def _course_label(self, text: str) -> str:
        """'[TDS_M3] Sistemas Operacionais 2026/2' ou 'BDII_2026/2' -> nome curto da disciplina."""
        for short, name in sorted(getattr(self, "short_names", {}).items(), key=lambda kv: -len(kv[0])):
            if short and short in (text or ""):              # sigla oficial da sala (ex.: BDII_2026/2)
                return name
        m = re.search(r"\[[^\]]+\][^:.]*?20\d{2}\s*/\s*[12]", text or "")
        return short_course(m.group(0)) if m else ""

    def _humanize(self, n: dict) -> tuple[str, str, str, str]:
        """Notificação do Moodle -> (ícone, título, disciplina, texto) em linguagem direta, sem rodapés."""
        subj = plain(n.get("subject"), 200)
        small = plain(n.get("smallmessage") or n.get("fullmessage"), 700)
        small = re.sub(r"\s*(Altere suas preferências de notificação|Change your notification preferences).*$",
                       "", small, flags=re.S | re.I).strip()
        et, comp = n.get("eventtype") or "", n.get("component") or ""
        course = self._course_label(subj + " " + small)
        if et == "coursecontentupdated":
            m = re.match(r"(.+?) (foi alterad[oa]|é nov[oa]|was updated|is new) (?:no curso|in the course)", small)
            if m:
                item, new = m.group(1).strip(), m.group(2).startswith(("é nov", "is new"))
                body = ("⚠️ O nome menciona <b>prazo</b>: confira a data." if "prazo" in item.lower() else "")
                return ("🆕", f"Novo na sala: {item}", course, body) if new else \
                       ("✏️", f"Alterado pelo professor: {item}", course, body)
        if comp == "mod_assign":
            m = re.match(r"Você enviou sua tarefa para (.+)", subj) or re.match(r"You have submitted.* for (.+)", subj)
            if m:
                return "✅", f"Envio confirmado: {m.group(1).strip()}", course, ""
            m = re.match(r"(.+?) retornou feedback para a tarefa (.+)", subj)
            if m:
                return ("📝", f"Feedback do professor: {m.group(2).strip()}", course,
                        f"<i>{h(m.group(1).strip())}</i> comentou a sua entrega. Abra para ler.")
        if comp == "mod_quiz" and et == "confirmation":
            return "✅", f"Questionário enviado: {subj.split(':', 1)[-1].strip()}", course, ""
        if comp == "mod_forum":
            title = re.sub(r"^\[[^\]]+\]\s*\S+:\s*", "", subj) or subj
            m = re.match(r"(.+?) (?:enviou mensagem|posted) (?:em|in) (?:[^:]+): ([^:]+):", small)
            body = f"<i>{h(m.group(1))}</i> publicou em {h(m.group(2))}." if m else h(small)
            return "📢", title, course, body
        body = "" if small.strip() == subj.strip() else h(small)
        return "🔔", subj, course, body

    COMMANDS_HELP = ("Comandos (a resposta chega em até 15 minutos):\n"
                     "/pendencias — o que você ainda não entregou (atrasadas e próximos 7 dias)\n"
                     "/prazos — prazos da turma nos próximos 7 dias\n"
                     "/ajuda — esta lista")

    def _commands(self, courses: list[dict], group_ids: set[int]) -> None:
        """Responde aos comandos que VOCÊ mandou ao robô (o envio só vai para o seu chat)."""
        for update_id, cmd in self.commands:
            key = f"cmd:{update_id}"
            if key in self.state.data.setdefault("seen", {}):
                continue
            if cmd in ("/pendencias", "/pendências"):
                self._my_digest(force_key=key)
            elif cmd == "/prazos":
                self._daily_digest(courses, group_ids, force_key=key)
            else:
                self._seen(key)
                self.notices.append(Notice(key, "me", "🤖", "NEAD Avisos", "", self.COMMANDS_HELP,
                                           extra={"urgent": True}))

    def _no_double_reminders(self) -> None:
        """Quem tem o lembrete pessoal ('você ainda não entregou') não recebe também, no chat pessoal, o lembrete
        da turma do mesmo prazo: esse vai só para o grupo."""
        mine = {n.extra.get("event") for n in self.notices if n.key.startswith("mine:")}
        for n in self.notices:
            if n.key.startswith("due:") and n.extra.get("event") in mine:
                n.extra["skip_me"] = True

    def _messages(self) -> None:
        """Toda mensagem recebida, de qualquer conversa (individual ou em grupo), uma por uma.
        (O Moodle do NEAD não informa 'não lidas', então a referência é a data da última mensagem já vista.)"""
        silent = self._feature_silent("messages")
        marks = self.state.data.setdefault("conv", {})
        data = self.m.call("core_message_get_conversations", userid=self.userid, limitfrom=0, limitnum=50)
        backlog: list[tuple[float, str, str]] = []
        self.inbox_msgs = []
        for conv in data.get("conversations", []):
            last = (conv.get("messages") or [{}])[0]
            cid = str(conv["id"])
            last_ts = last.get("timecreated") or 0
            seen_ts = marks.get(cid)
            if seen_ts is not None and last_ts <= seen_ts:
                continue
            marks[cid] = last_ts
            window = (self.now - timedelta(days=7)).timestamp() if (silent or seen_ts is None) else seen_ts
            if last_ts <= window:
                continue
            full = self.m.call("core_message_get_conversation_messages", currentuserid=self.userid, convid=conv["id"],
                               newest=True, limitfrom=0, limitnum=30)
            names = {m.get("id"): m.get("fullname") for m in full.get("members", []) + conv.get("members", [])}
            group = conv.get("name") if conv.get("type") == 2 else None
            for msg in sorted(full.get("messages", []), key=lambda x: x["timecreated"]):
                if msg["useridfrom"] == self.userid or msg["timecreated"] <= window:
                    continue
                who = names.get(msg["useridfrom"]) or "alguém"
                key = f"msg:{msg['id']}"
                when = datetime.fromtimestamp(msg["timecreated"], self.s.tz)
                self.inbox_msgs.append((key, msg["timecreated"]))
                if self._seen(key):
                    continue
                text = plain(msg.get("text"), 600)
                if silent:
                    backlog.append((msg["timecreated"], who + (f" ({group})" if group else ""), text))
                    continue
                self.notices.append(Notice(key, "me", "✉️", f"Mensagem de {who}" + (f" em {group}" if group else ""),
                                           "", f"<i>Enviada {h(sent_label(when, self.now))}</i>\n\n{h(text)}",
                                           self.m.url(f"message/index.php?convid={conv['id']}"), when,
                                           extra={"urgent": True}))
        if backlog and not self.first_run:
            backlog.sort()
            # Cabe com folga no limite do Telegram (4.000 caracteres): 12 itens de até 150 caracteres.
            def short(x: str) -> str:
                return x if len(x) <= 150 else x[:150].rsplit(" ", 1)[0] + "…"
            lines = [f"• <b>{h(who)}</b> — enviada {h(sent_label(datetime.fromtimestamp(t, self.s.tz), self.now))}"
                     f"\n  {h(short(text))}"
                     for t, who, text in backlog[-12:]]
            if len(backlog) > 12:
                lines.insert(0, f"(as {len(backlog) - 12} mais antigas estão no Moodle)")
            self.notices.append(Notice(f"msgbacklog:{self.now:%Y-%m-%d}", "me", "✉️",
                                       f"{len(backlog)} mensagem(ns) recebida(s) nos últimos 7 dias",
                                       "", "\n".join(lines), self.m.url("message/index.php")))

    def _daily_check(self) -> None:
        """Uma vez por dia, só no seu chat: confere tudo o que o Moodle registrou para você nas últimas 24 h
        (notificações e mensagens) contra o que foi enviado aqui. O que faltar sai agora mesmo."""
        key = f"check:{self.now:%Y-%m-%d}"
        if self.first_run or self.now.hour < self.s.digest_hour or key in self.state.data.setdefault("seen", {}):
            return
        self._seen(key)
        since = (self.now - timedelta(days=1)).timestamp()
        pending = {n.key for n in self.notices}
        seen = self.state.data["seen"]
        kinds = {"forum": "fórum", "assign": "tarefas", "quiz": "questionários", "moodle": "conteúdo da sala"}
        count: dict[str, int] = {}
        sent = covered = 0
        for n in getattr(self, "inbox_notifs", []):
            if (n.get("timecreated") or 0) < since:
                continue
            comp = (n.get("component") or "").split("_")[-1]
            label = kinds.get(comp, "outras")
            count[label] = count.get(label, 0) + 1
            k = f"notif:{n['id']}"
            if k in self.covered:
                covered += 1
            elif k in seen or k in pending:
                sent += 1
        msgs = [k for k, t in getattr(self, "inbox_msgs", []) if t >= since]
        total = sum(count.values()) + len(msgs)
        if not total:
            return                     # dia sem nada no Moodle: sem mensagem
        else:
            parts = [f"{v} de {k}" for k, v in sorted(count.items())] + ([f"{len(msgs)} mensagem(ns)"] if msgs else [])
            body = (f"Nas últimas 24 h o Moodle registrou {total} item(ns) para você: {', '.join(parts)}.\n"
                    f"✅ {sent + len(msgs)} enviado(s) aqui"
                    + (f" e {covered} já coberto(s) por lembrete ou aviso do mesmo assunto." if covered else "."))
        self.notices.append(Notice(key, "me", "🔎", f"Verificação do dia ({self.now:%d/%m})", "", body))

    def _daily_digest(self, courses: list[dict], group_ids: set[int], force_key: str | None = None) -> None:
        """Uma vez por dia (a partir de RESUMO_HORA): prazos dos próximos 7 dias. Com force_key: agora, a pedido
        (comando /prazos), só no seu chat."""
        key = force_key or f"digest:{self.now:%Y-%m-%d}"
        if not force_key and (self.now.hour < self.s.digest_hour or key in self.state.data.setdefault("seen", {})):
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
        self.notices.append(Notice(key, "me" if force_key else "group", "🗓",
                                   f"Prazos da semana ({self.now:%d/%m})", "", body,
                                   extra={"urgent": True} if force_key else {}))

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

    # ------------------------------------------------------------------ v3: tudo o que o professor faz
    def _feature_silent(self, feature: str) -> bool:
        """Tipo de aviso novo numa instalação que já existia: a 1ª vez só registra o estado atual (sem
        enxurrada de "novidades" antigas). Na 1ª execução da instalação tudo já é silencioso."""
        feats = self.state.data.setdefault("features", [])
        if feature in feats:
            return self.first_run
        feats.append(feature)
        return True

    def _is_staff(self, course_id: int, user_id: int | None) -> bool:
        """Professor/mediação = qualquer papel na sala que não seja só 'student' (cache no estado)."""
        if not user_id:
            return False
        cache = self.state.data.setdefault("people", {})
        key = f"{course_id}:{user_id}"
        if key not in cache:
            try:
                prof = self.m.call("core_user_get_course_user_profiles",
                                   userlist=[{"userid": user_id, "courseid": course_id}])
                cache[key] = sorted(r["shortname"] for r in (prof[0].get("roles", []) if prof else []))
            except Exception:  # noqa: BLE001 — sem papel conhecido: trata como colega
                cache[key] = []
        roles = set(cache[key])
        return bool(roles) and roles != {"student"}

    @staticmethod
    def _fingerprint(mod: dict) -> dict:
        return {"name": mod.get("name") or "",
                "desc": digest(plain(mod.get("description"), 2000)),
                "dates": {d.get("dataid"): d.get("timestamp") for d in mod.get("dates", []) if d.get("timestamp")},
                "files": {f.get("filename"): f.get("timemodified") for f in mod.get("contents") or []
                          if f.get("type") == "file" and f.get("filename")},
                "avail": digest(plain(mod.get("availabilityinfo"), 400))}

    def _changes(self, old: dict, new: dict, mod: dict | None = None) -> tuple[list[str], bool]:
        """Linhas legíveis do que mudou; e se a mudança foi SÓ de datas."""
        lines: list[str] = []
        if old.get("name") != new["name"]:
            lines.append(f"Nome: <s>{h(old.get('name'))}</s> → <b>{h(new['name'])}</b>")
        for dataid in sorted(set(old.get("dates", {})) | set(new["dates"])):
            label = DATE_LABEL.get(dataid, None if dataid in DATE_LABEL else dataid)
            a, b = old.get("dates", {}).get(dataid), new["dates"].get(dataid)
            if label is None or a == b:
                continue
            fa = h(fmt(datetime.fromtimestamp(a, self.s.tz))) if a else "sem data"
            fb = h(fmt(datetime.fromtimestamp(b, self.s.tz))) if b else "removido"
            lines.append(f"{label}: <s>{fa}</s> → <b>{fb}</b>")
        only_dates = bool(lines) and all(not x.startswith("Nome:") for x in lines)
        if as_digest(old.get("desc")) != new["desc"]:
            text = plain((mod or {}).get("description"), 2000)            # o texto vem do Moodle, não do estado
            snippet = text if len(text) <= 350 else text[:350].rsplit(" ", 1)[0] + "…"
            lines.append("Enunciado/descrição atualizado" + (f":\n<i>{h(snippet)}</i>" if snippet else " (removido)"))
            only_dates = False
        old_files = old.get("files", {})
        for name, tm in new["files"].items():
            if name not in old_files:
                lines.append(f"📎 Arquivo novo: {h(name)}")
            elif old_files[name] != tm:
                lines.append(f"📎 Arquivo atualizado: {h(name)}")
        for name in old_files:
            if name not in new["files"]:
                lines.append(f"📎 Arquivo removido: {h(name)}")
        if as_digest(old.get("avail")) != new["avail"] and new["avail"]:
            lines.append(f"Disponibilidade: {h(plain((mod or {}).get('availabilityinfo'), 400))}")
        if any(x.startswith(("📎", "Disponibilidade")) for x in lines):
            only_dates = False
        return lines, only_dates

    def _activity_edits(self, mod: dict, c: dict, aud: str, silent: bool) -> None:
        """Professor alterou a atividade: nome, datas, enunciado, arquivos ou disponibilidade."""
        prints = self.state.data.setdefault("fp", {})
        key = str(mod["id"])
        new, old = self._fingerprint(mod), prints.get(key)
        prints[key] = new
        if old is None or silent:
            return
        lines, only_dates = self._changes(old, new, mod)
        if not lines:
            return
        import hashlib
        fp_id = hashlib.sha1(json.dumps(new, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
        prefix, icon, title = (("duechange", "📅", "Prazo alterado") if only_dates
                               else ("edit", "✏️", "Atividade alterada pelo professor"))
        if self._seen(f"{prefix}:{mod['id']}:{fp_id}"):
            return
        self.edited.add(mod["id"])
        due = next((new["dates"][k] for k in DUE_KEYS if new["dates"].get(k)), None)
        self.notices.append(Notice(f"{prefix}:{mod['id']}:{fp_id}", aud, icon, f"{title}: {new['name']}",
                                   short_course(c["fullname"]), "\n".join(lines), mod.get("url"),
                                   datetime.fromtimestamp(due, self.s.tz) if only_dates and due else None))

    def _config_updates(self, courses: list[dict], group_ids: set[int]) -> None:
        """Mudanças de configuração que não aparecem no conteúdo (ex.: regras de envio, nota, tentativas),
        informadas pelo próprio Moodle (core_course_get_updates_since)."""
        silent = self._feature_silent("config")
        marks = self.state.data.setdefault("updates_since", {})
        start = int(self.now.timestamp())
        for c in courses:
            since = marks.get(str(c["id"]))
            marks[str(c["id"])] = start
            if silent or not since:
                continue
            try:
                data = self.m.call("core_course_get_updates_since", courseid=c["id"], since=since)
            except Exception:  # noqa: BLE001 — recurso opcional: o resto dos avisos continua
                continue
            aud = "group" if c["id"] in group_ids else "me"
            for inst in data.get("instances", []):
                if inst.get("contextlevel") != "module" or inst.get("id") in self.edited:
                    continue
                cfg = [u for u in inst.get("updates", []) if u.get("name") == "configuration"]
                info = self.mods.get(inst.get("id"))
                if not cfg or not info or info["new"]:
                    continue
                stamp = max(u.get("timeupdated") or since for u in cfg)
                if self._seen(f"cfg:{inst['id']}:{stamp}"):
                    continue
                self.notices.append(Notice(
                    f"cfg:{inst['id']}:{stamp}", aud, "⚙️", f"Configuração alterada: {info['name']}",
                    short_course(c["fullname"]),
                    "O professor mudou as configurações desta atividade (ex.: forma de envio, nota, tentativas "
                    "ou critérios). Vale abrir e conferir.", info["url"]))

    def _forums(self, courses: list[dict], group_ids: set[int]) -> None:
        """Todos os fóruns: tópicos novos, respostas e avisos editados. Professor/mediação vai para o grupo
        da turma; postagens de colegas só para o seu chat."""
        silent = self._feature_silent("forums")
        forums = self.m.call("mod_forum_get_forums_by_courses", courseids=[c["id"] for c in courses])
        names = {c["id"]: c["fullname"] for c in courses}
        known = self.state.data.setdefault("disc", {})
        for f in forums:
            news = f.get("type") == "news" or "aviso" in (f.get("name") or "").lower()
            data = self.m.call("mod_forum_get_forum_discussions", forumid=f["id"], sortorder=1, page=0, perpage=10)
            course = short_course(names.get(f["course"], ""))
            for d in data.get("discussions", []):
                did = str(d["discussion"])
                old = known.get(did)
                known[did] = {"n": d.get("numreplies", 0), "tm": d.get("timemodified", 0)}
                url = self.m.url(f"mod/forum/discuss.php?d={d['discussion']}")
                staff = self._is_staff(f["course"], d.get("userid"))
                in_group = f["course"] in group_ids
                mine = d.get("userid") == self.userid
                if old is None:
                    if mine:                       # tópico que VOCÊ criou: não é novidade para você
                        self._seen(f"post:{did}" if news else f"topic:{did}")
                        continue
                    # tópico novo (os do fórum de Avisos continuam com a chave antiga 'post:')
                    key = f"post:{did}" if news else f"topic:{did}"
                    if self._seen(key) or silent:
                        continue
                    created = datetime.fromtimestamp(d.get("created") or d.get("timemodified", 0), self.s.tz)
                    aud = "group" if in_group and (news or staff) else "me"
                    title = (d.get("name") or d.get("subject") or "Aviso") if news else \
                        f"Novo tópico em {f.get('name')}: {d.get('name') or d.get('subject')}"
                    who = h(d.get("userfullname", "")) + (" (professor/mediação)" if staff and not news else "")
                    self.notices.append(Notice(key, aud, "📢" if news else "💬", title, course,
                                               f"<i>{who}</i> · publicado {h(sent_label(created, self.now))}\n\n{h(plain(d.get('message')))}",
                                               url, created))
                    continue
                if silent or d.get("timemodified", 0) <= old.get("tm", 0):
                    continue
                if d.get("numreplies", 0) > old.get("n", 0):
                    self._new_replies(d, f, course, in_group, news, old, url)
                elif (news or staff) and d.get("usermodified", d.get("userid")) != self.userid:
                    key = f"postedit:{did}:{d.get('timemodified')}"
                    if self._seen(key):
                        continue
                    self.notices.append(Notice(
                        key, "group" if in_group else "me", "✏️", f"Aviso editado: {d.get('name')}", course,
                        f"<i>{h(d.get('usermodifiedfullname') or d.get('userfullname', ''))}</i> atualizou o texto:\n"
                        f"{h(plain(d.get('message')))}", url))

    def _new_replies(self, d: dict, f: dict, course: str, in_group: bool, news: bool, old: dict, url: str) -> None:
        try:
            data = self.m.call("mod_forum_get_discussion_posts", discussionid=d["discussion"], sortby="created",
                               sortdirection="DESC")
        except Exception:  # noqa: BLE001
            return
        fresh = [p for p in data.get("posts", []) if (p.get("timecreated") or 0) > old.get("tm", 0)
                 and p.get("parentid") and (p.get("author") or {}).get("id") != self.userid]   # sem as suas
        if not fresh:
            return
        key = f"reply:{d['discussion']}:{max(p['id'] for p in fresh)}"
        if self._seen(key):
            return
        by_staff = [p for p in fresh if self._is_staff(f["course"], (p.get("author") or {}).get("id"))]
        last = (by_staff or fresh)[0]
        author = (last.get("author") or {}).get("fullname", "")
        when = datetime.fromtimestamp(last.get("timecreated", 0), self.s.tz)
        body = (f"<i>{h(author)}{' (professor/mediação)' if by_staff else ''}</i> · respondeu {h(sent_label(when, self.now))}\n\n"
                f"{h(plain(last.get('message'), 500))}")
        if len(fresh) > 1:
            body += f"\n\n+{len(fresh) - 1} outra(s) resposta(s) nesta discussão."
        aud = "group" if in_group and by_staff else "me"
        title = (f"Professor respondeu em: {d.get('name')}" if by_staff else f"Nova resposta em: {d.get('name')}")
        self.notices.append(Notice(key, aud, "💬", title, course, body, url, when))

    def _grades(self, courses: list[dict]) -> None:
        """Só no seu chat: nota lançada ou alterada e comentário (feedback) do professor."""
        silent = self._feature_silent("grades")
        known = self.state.data.setdefault("grades", {})
        for c in courses:
            try:
                data = self.m.call("gradereport_user_get_grade_items", courseid=c["id"], userid=self.userid)
            except Exception:  # noqa: BLE001
                continue
            for item in (data.get("usergrades") or [{}])[0].get("gradeitems", []):
                if item.get("itemtype") != "mod":
                    continue
                key = f"{c['id']}:{item['id']}"
                grade = plain(item.get("gradeformatted"), 40).strip()
                grade = "" if grade in ("-", "") else grade
                feedback = plain(item.get("feedback"), 600)
                old = known.get(key)
                known[key] = {"g": grade, "f": digest(feedback)}       # o comentário fica só no Telegram
                if silent or old is None and not grade and not feedback:
                    continue
                old = old or {"g": "", "f": ""}
                name = plain(item.get("itemname"), 150) or "Atividade"
                rng = plain(item.get("rangeformatted"), 20)
                url = self.mod_url.get(item.get("cmid"))
                course = short_course(c["fullname"])
                changed_fb = feedback and digest(feedback) != old["f"] and feedback != old["f"]
                fb = f"\n💬 Comentário do professor:\n<i>{h(feedback)}</i>" if changed_fb else ""
                if grade and grade != old["g"]:
                    title = f"Nota lançada: {name}" if not old["g"] else f"Nota alterada: {name}"
                    text = (f"<b>{h(grade)}</b>" + (f" (escala {h(rng)})" if rng else "")
                            if not old["g"] else f"<s>{h(old['g'])}</s> → <b>{h(grade)}</b>")
                    self.notices.append(Notice(f"grade:{key}:{grade}:{len(feedback)}", "me", "📊", title, course,
                                               text + fb, url))
                elif fb:
                    self.notices.append(Notice(f"feedback:{key}:{len(feedback)}", "me", "💬",
                                               f"Comentário do professor: {name}", course, fb.strip(), url))

    def _events(self, courses: list[dict], group_ids: set[int]) -> None:
        """Eventos da sala que não são prazo de atividade (aula síncrona, encontro, prova presencial...):
        novo evento, evento alterado e lembrete no dia."""
        silent = self._feature_silent("events")
        data = self.m.call("core_calendar_get_calendar_events", events={"courseids": [c["id"] for c in courses]},
                           options={"timestart": int((self.now - timedelta(hours=12)).timestamp()),
                                    "timeend": int((self.now + timedelta(days=60)).timestamp())})
        names = {c["id"]: c["fullname"] for c in courses}
        known = self.state.data.setdefault("events", {})
        for ev in data.get("events", []):
            if ev.get("modulename") or ev.get("eventtype") not in ("course", "group", "site", "category"):
                continue
            eid = str(ev["id"])
            stamp = [ev.get("timestart"), ev.get("timeduration"), digest(ev.get("name")),
                     digest(plain(ev.get("description"), 300))]
            old = known.get(eid)
            if old is not None and len(old) == 4:          # estado antigo guardava nome/descrição em texto
                old = [old[0], old[1], as_digest(old[2]), as_digest(old[3])]
            known[eid] = stamp
            start = datetime.fromtimestamp(ev["timestart"], self.s.tz)
            aud = "group" if ev.get("courseid") in group_ids else "me"
            course = short_course(names.get(ev.get("courseid"), ""))
            desc = plain(ev.get("description"), 300)
            body = f"<b>{h(fmt(start))}</b>" + (f"\n<i>{h(desc)}</i>" if desc else "")
            url = self.m.url(f"calendar/view.php?view=day&time={ev['timestart']}")
            if silent:
                continue
            if old is None and start >= self.now:
                if not self._seen(f"event:{eid}"):
                    self.notices.append(Notice(f"event:{eid}", aud, "📆", f"Novo evento: {ev['name']}", course, body,
                                               url, start))
            elif old is not None and old != stamp and start >= self.now:
                import hashlib
                key = f"eventchange:{eid}:" + hashlib.sha1(json.dumps(stamp, ensure_ascii=False).encode()).hexdigest()[:8]
                if not self._seen(key):
                    self.notices.append(Notice(key, aud, "📆", f"Evento alterado: {ev['name']}", course, body,
                                               url, start))
            if f"event:{eid}" in {n.key for n in self.notices}:
                self._seen(f"eventday:{eid}")      # o "Novo evento" de hoje já diz o horário
            if start.date() == self.now.date() and start >= self.now and not self._seen(f"eventday:{eid}"):
                self.notices.append(Notice(f"eventday:{eid}", aud, "⏰", f"Hoje às {start:%H:%M}: {ev['name']}",
                                           course, body, url, start))
