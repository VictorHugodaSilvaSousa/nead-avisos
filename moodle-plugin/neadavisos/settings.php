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
 * Configurações do administrador.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

if ($ADMIN->fulltree) {
    $settings->add(new admin_setting_heading('message_neadavisos/intro', '',
        get_string('settingsintro', 'message_neadavisos')));
    // Token: campo de senha (não aparece na página nem no HTML depois de salvo).
    $settings->add(new admin_setting_configpasswordunmask('message_neadavisos/bottoken',
        get_string('bottoken', 'message_neadavisos'), get_string('bottoken_desc', 'message_neadavisos'), ''));
    $settings->add(new admin_setting_configtext('message_neadavisos/botusername',
        get_string('botusername', 'message_neadavisos'), get_string('botusername_desc', 'message_neadavisos'),
        '', '/^@?[A-Za-z0-9_]{5,64}$/'));
    // Privacidade por padrão: conteúdo de mensagens privadas NÃO vai para o Telegram.
    $settings->add(new admin_setting_configcheckbox('message_neadavisos/showmessagecontent',
        get_string('showmessagecontent', 'message_neadavisos'),
        get_string('showmessagecontent_desc', 'message_neadavisos'), 0));
}
