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

/**
 * Canal de notificação "Telegram (NEAD Avisos)".
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

require_once($CFG->dirroot . '/message/output/lib.php');

use message_neadavisos\formatter;
use message_neadavisos\linker;
use message_neadavisos\telegram;

/**
 * Envia ao Telegram as notificações que o próprio aluno escolheu receber por este canal
 * (Preferências > Preferências de notificação).
 */
class message_output_neadavisos extends message_output {

    /**
     * Envia uma notificação/mensagem ao Telegram do destinatário.
     *
     * @param stdClass $eventdata dados do message_send()
     * @return bool true também quando não há o que enviar (conta não ligada), para não travar a fila
     */
    public function send_message($eventdata) {
        if (empty($eventdata->userto->id) || !empty($eventdata->userto->deleted) ||
                !empty($eventdata->userto->suspended) || !$this->is_system_configured()) {
            return true;
        }
        $chatid = linker::chat_of((int) $eventdata->userto->id);
        if ($chatid === null) {
            return true;
        }
        [$html, $url, $button] = formatter::format($eventdata);
        $ok = (new telegram())->send($chatid, $html, $url, $button);
        if (!$ok) {
            // Sem detalhes da mensagem (pode ter dado pessoal): só o fato de ter falhado.
            debugging('message_neadavisos: o Telegram não aceitou um aviso para o usuário ' .
                (int) $eventdata->userto->id, DEBUG_DEVELOPER);
        }
        return true;
    }

    /**
     * Formulário na página de preferências de notificação: ligar/desligar o Telegram.
     *
     * @param array $preferences
     * @return string HTML
     */
    public function config_form($preferences) {
        global $USER;
        if (!$this->is_system_configured()) {
            return get_string('notconfigured', 'message_neadavisos');
        }
        if (!empty($preferences->neadavisos_chatid)) {
            return html_writer::div(get_string('linked', 'message_neadavisos')) .
                html_writer::div(html_writer::checkbox('neadavisos_unlink', 1, false,
                    get_string('unlink', 'message_neadavisos')));
        }
        $url = linker::link_url((int) $USER->id);
        return html_writer::div(get_string('linkinstructions', 'message_neadavisos')) .
            html_writer::link($url, get_string('linkbutton', 'message_neadavisos'),
                ['class' => 'btn btn-primary', 'target' => '_blank', 'rel' => 'noopener noreferrer']) .
            html_writer::div(get_string('linkexpires', 'message_neadavisos'), 'form-text text-muted');
    }

    /**
     * Trata o formulário (só o desligamento; a ligação acontece pelo robô, com o código).
     *
     * @param stdClass $form
     * @param array $preferences
     */
    public function process_form($form, &$preferences) {
        global $USER;
        if (!empty($form->neadavisos_unlink)) {
            linker::unlink((int) $USER->id);
        }
    }

    /**
     * Carrega as preferências do usuário para o formulário.
     *
     * @param array $preferences
     * @param int $userid
     */
    public function load_data(&$preferences, $userid) {
        $preferences->neadavisos_chatid = linker::chat_of((int) $userid);
    }

    /**
     * O administrador configurou o robô?
     *
     * @return bool
     */
    public function is_system_configured() {
        return telegram::valid_token((string) get_config('message_neadavisos', 'bottoken'))
            && trim((string) get_config('message_neadavisos', 'botusername')) !== '';
    }

    /**
     * O usuário ligou a conta ao Telegram?
     *
     * @param stdClass|null $user
     * @return bool
     */
    public function is_user_configured($user = null) {
        global $USER;
        $userid = (int) ($user->id ?? $USER->id);
        return linker::chat_of($userid) !== null;
    }

    /**
     * Desligado por padrão: cada pessoa escolhe o que quer receber no Telegram.
     *
     * @return int
     */
    public function get_default_messaging_settings() {
        return MESSAGE_PERMITTED;
    }
}
