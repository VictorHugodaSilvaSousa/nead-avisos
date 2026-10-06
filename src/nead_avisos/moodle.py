"""Cliente do Moodle pelo serviço do app oficial (moodle_mobile_app), SOMENTE LEITURA.

- Login uma única vez (login/token.php) -> chave de acesso (token). A senha não é guardada.
- Só chama funções da lista branca abaixo, todas de consulta. Qualquer outra é recusada.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

READ_ONLY_FUNCTIONS = frozenset({
    "core_webservice_get_site_info",
    "core_enrol_get_users_courses",
    "core_user_get_course_user_profiles",
    "core_course_get_contents",
    "core_calendar_get_action_events_by_timesort",
    "core_calendar_get_calendar_events",
    "mod_forum_get_forums_by_courses",
    "mod_forum_get_forum_discussions",
    "message_popup_get_popup_notifications",
    "core_message_get_conversations",
    "mod_forum_get_discussion_posts",      # respostas nos fóruns
    "core_course_get_updates_since",       # o que o professor alterou em cada atividade
    "gradereport_user_get_grade_items",    # suas notas e comentários
})


class MoodleError(Exception):
    pass


class AuthError(MoodleError):
    """Token inválido/expirado ou login recusado."""


def _ssl():
    import truststore
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def _post(url: str, data: dict, timeout: int = 60) -> object:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(),
                                 headers={"User-Agent": "NEAD-Avisos/1.0 (somente leitura)"})
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ssl()) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise MoodleError(f"Moodle indisponível: {type(last).__name__}: {last}")


def get_token(base_url: str, username: str, password: str) -> str:
    """Troca usuário/senha pela chave do app oficial. A senha não sai daqui."""
    data = _post(f"{base_url}/login/token.php", {"username": username, "password": password,
                                                  "service": "moodle_mobile_app"})
    if not isinstance(data, dict) or not data.get("token"):
        raise AuthError(f"Login recusado pelo Moodle: {(data or {}).get('error', 'sem detalhe')}")
    return data["token"]


def _flatten(prefix: str, value, out: dict) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}[{k}]", v, out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _flatten(f"{prefix}[{i}]", v, out)
    elif isinstance(value, bool):
        out[prefix] = int(value)
    elif value is not None:
        out[prefix] = value


class Moodle:
    def __init__(self, base_url: str, token: str) -> None:
        self.base = base_url.rstrip("/")
        self.token = token
        self.calls = 0

    def call(self, function: str, **params):
        if function not in READ_ONLY_FUNCTIONS:
            raise PermissionError(f"Função fora da lista de leitura: {function}")
        data = {"wstoken": self.token, "wsfunction": function, "moodlewsrestformat": "json"}
        for k, v in params.items():
            _flatten(k, v, data)
        self.calls += 1
        result = _post(f"{self.base}/webservice/rest/server.php", data)
        if isinstance(result, dict) and result.get("exception"):
            code = result.get("errorcode", "")
            if code in ("invalidtoken", "accessexception"):
                raise AuthError(f"Chave de acesso do Moodle inválida ou expirada ({code}). Rode: nead-avisos setup")
            raise MoodleError(f"{function}: {code} {result.get('message', '')}".strip())
        return result

    def url(self, path: str) -> str:
        return f"{self.base}/{path.lstrip('/')}"
