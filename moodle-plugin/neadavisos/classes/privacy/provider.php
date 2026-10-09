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

namespace message_neadavisos\privacy;

use core_privacy\local\metadata\collection;
use core_privacy\local\request\transform;
use core_privacy\local\request\writer;
use message_neadavisos\linker;

/**
 * Privacidade (LGPD/GDPR): o que o plugin guarda e para onde envia.
 *
 * Guarda: o número do chat do Telegram e o código de ligação (preferências do usuário).
 * Envia: o texto das notificações que a própria pessoa escolheu receber no Telegram.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class provider implements
        \core_privacy\local\metadata\provider,
        \core_privacy\local\request\user_preference_provider {

    /**
     * @param collection $collection
     * @return collection
     */
    public static function get_metadata(collection $collection): collection {
        $collection->add_user_preference(linker::PREF_CHAT, 'privacy:metadata:preference:chatid');
        $collection->add_user_preference(linker::PREF_CODE, 'privacy:metadata:preference:code');
        $collection->add_external_location_link('telegram', [
            'chatid' => 'privacy:metadata:telegram:chatid',
            'message' => 'privacy:metadata:telegram:message',
        ], 'privacy:metadata:telegram');
        return $collection;
    }

    /**
     * Exporta as preferências do usuário.
     *
     * @param int $userid
     */
    public static function export_user_preferences(int $userid) {
        $chat = get_user_preferences(linker::PREF_CHAT, null, $userid);
        if ($chat !== null) {
            writer::export_user_preference('message_neadavisos', linker::PREF_CHAT, $chat,
                get_string('privacy:metadata:preference:chatid', 'message_neadavisos'));
        }
        $code = get_user_preferences(linker::PREF_CODE, null, $userid);
        if ($code !== null) {
            [, $expires] = array_pad(explode('|', $code, 2), 2, 0);
            writer::export_user_preference('message_neadavisos', linker::PREF_CODE,
                transform::datetime((int) $expires),
                get_string('privacy:metadata:preference:code', 'message_neadavisos'));
        }
    }
}
