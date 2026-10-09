<?php
// This file is part of Moodle - https://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <https://www.gnu.org/licenses/>.

namespace message_neadavisos;

/**
 * Transforma uma notificação/mensagem do Moodle no texto do Telegram.
 *
 * Privacidade por padrão: o CONTEÚDO de mensagens privadas entre pessoas só vai para o Telegram se o
 * administrador permitir (configuração "showmessagecontent"); sem isso, chega só "você recebeu uma mensagem
 * de Fulano" com o botão para ler no Moodle.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class formatter {
    /** Tamanho máximo do texto do aviso (o resto fica no Moodle). */
    const BODY_LIMIT = 900;

    /**
     * É uma mensagem privada entre pessoas (e não uma notificação do sistema)?
     *
     * @param \stdClass $eventdata
     * @return bool
     */
    public static function is_private_message(\stdClass $eventdata): bool {
        return empty($eventdata->notification) ||
            (($eventdata->component ?? '') === 'moodle' && ($eventdata->name ?? '') === 'instantmessage');
    }

    /**
     * Texto do aviso (HTML do Telegram, tudo escapado) e o link do botão.
     *
     * @param \stdClass $eventdata dados do message_send()
     * @return array [string $html, string|null $url, string $buttontext]
     */
    public static function format(\stdClass $eventdata): array {
        global $CFG;
        if (self::is_private_message($eventdata)) {
            $from = !empty($eventdata->userfrom->id) ? fullname($eventdata->userfrom) : get_string('someone',
                'message_neadavisos');
            $html = '✉️ <b>' . s(get_string('newmessagefrom', 'message_neadavisos', $from)) . '</b>';
            if (get_config('message_neadavisos', 'showmessagecontent')) {
                $html .= "\n\n" . s(self::plain($eventdata->smallmessage ?? $eventdata->fullmessage ?? ''));
            } else {
                $html .= "\n\n<i>" . s(get_string('readinmoodle', 'message_neadavisos')) . '</i>';
            }
            $url = !empty($eventdata->userfrom->id)
                ? $CFG->wwwroot . '/message/index.php?id=' . (int) $eventdata->userfrom->id
                : $CFG->wwwroot . '/message/index.php';
            return [$html, $url, get_string('buttonreply', 'message_neadavisos')];
        }
        $subject = self::plain($eventdata->subject ?? '');
        $body = self::plain($eventdata->smallmessage ?? '');
        if ($body === '' || $body === $subject) {
            $body = self::plain($eventdata->fullmessage ?? '');
        }
        $body = $body === $subject ? '' : self::shorten($body);
        $html = '🔔 <b>' . s($subject) . '</b>' . ($body !== '' ? "\n\n" . s($body) : '');
        $url = !empty($eventdata->contexturl) ? (string) (is_object($eventdata->contexturl)
            ? $eventdata->contexturl->out(false) : $eventdata->contexturl) : null;
        return [$html, $url, get_string('buttonopen', 'message_neadavisos')];
    }

    /**
     * HTML/texto do Moodle -> texto simples, sem rodapés de preferências de notificação.
     *
     * @param string $text
     * @return string
     */
    public static function plain(string $text): string {
        $text = preg_replace('#<(br|/p|/div|/li)\s*/?>#i', "\n", $text);
        $text = html_entity_decode(strip_tags($text), ENT_QUOTES, 'UTF-8');
        $text = preg_replace('/\s*(-{3,}|_{3,})[\s\S]*$/u', '', $text);           // Rodapé "---------".
        $text = preg_replace('/\s*(Altere suas preferências de notificação|Change your notification preferences)' .
            '[\s\S]*$/iu', '', $text);
        $text = preg_replace("/[ \t\x{00A0}]+/u", ' ', $text);
        return trim(preg_replace("/\n\s*\n+/", "\n", $text));
    }

    /**
     * @param string $text
     * @return string
     */
    public static function shorten(string $text): string {
        if (\core_text::strlen($text) <= self::BODY_LIMIT) {
            return $text;
        }
        $cut = \core_text::substr($text, 0, self::BODY_LIMIT);
        $pos = \core_text::strrpos($cut, ' ');
        return ($pos !== false ? \core_text::substr($cut, 0, $pos) : $cut) . '…';
    }
}
