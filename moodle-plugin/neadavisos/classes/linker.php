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
 * Liga (e desliga) a conta do Moodle ao chat do Telegram com um CÓDIGO DE USO ÚNICO.
 *
 * Segurança:
 *  - o código é aleatório (random_bytes), vale 15 minutos e é apagado ao ser usado;
 *  - só chats PRIVADOS são aceitos (nunca grupos);
 *  - um chat fica ligado a uma única conta (ligar de novo desliga a anterior);
 *  - só o número do chat é guardado (preferência do usuário); nada de nome ou telefone do Telegram.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class linker {
    /** Preferência com o número do chat. */
    const PREF_CHAT = 'message_processor_neadavisos_chatid';
    /** Preferência com "código|expira_em". */
    const PREF_CODE = 'message_processor_neadavisos_code';
    /** Validade do código, em segundos. */
    const CODE_TTL = 900;

    /**
     * Código de uso único para o usuário (reaproveita o atual se ainda valer mais de 5 minutos).
     *
     * @param int $userid
     * @return string
     */
    public static function code_for(int $userid): string {
        $current = (string) get_user_preferences(self::PREF_CODE, '', $userid);
        if (preg_match('/^([a-f0-9]{16})\|(\d+)$/', $current, $m) && (int) $m[2] - time() > 300) {
            return $m[1];
        }
        $code = bin2hex(random_bytes(8));
        set_user_preference(self::PREF_CODE, $code . '|' . (time() + self::CODE_TTL), $userid);
        return $code;
    }

    /**
     * Link que abre o robô já com o código (o Telegram envia "/start CÓDIGO" ao apertar INICIAR).
     *
     * @param int $userid
     * @return string|null null se o robô não estiver configurado
     */
    public static function link_url(int $userid): ?string {
        $bot = trim((string) get_config('message_neadavisos', 'botusername'), "@ \t");
        if (!preg_match('/^[A-Za-z0-9_]{5,64}$/', $bot)) {
            return null;
        }
        return 'https://t.me/' . $bot . '?start=' . self::code_for($userid);
    }

    /**
     * Conta dona de um código válido.
     *
     * @param string $code
     * @return int|null
     */
    public static function user_for_code(string $code): ?int {
        global $DB;
        if (!preg_match('/^[a-f0-9]{16}$/', $code)) {
            return null;
        }
        $like = $DB->sql_like('value', ':value', false);
        $records = $DB->get_records_select('user_preferences', "name = :name AND $like",
            ['name' => self::PREF_CODE, 'value' => $code . '|%']);
        foreach ($records as $record) {
            [$stored, $expires] = array_pad(explode('|', $record->value, 2), 2, 0);
            if (hash_equals($stored, $code) && (int) $expires >= time()) {
                return (int) $record->userid;
            }
        }
        return null;
    }

    /**
     * Liga o chat à conta (e solta o mesmo chat de qualquer outra conta).
     *
     * @param int $userid
     * @param string $chatid
     */
    public static function link(int $userid, string $chatid): void {
        global $DB;
        $DB->delete_records_select('user_preferences', 'name = :name AND value = :value AND userid <> :userid',
            ['name' => self::PREF_CHAT, 'value' => $chatid, 'userid' => $userid]);
        set_user_preference(self::PREF_CHAT, $chatid, $userid);
        unset_user_preference(self::PREF_CODE, $userid);
    }

    /**
     * Desliga a conta do Telegram.
     *
     * @param int $userid
     */
    public static function unlink(int $userid): void {
        unset_user_preference(self::PREF_CHAT, $userid);
        unset_user_preference(self::PREF_CODE, $userid);
    }

    /**
     * Chat ligado à conta (ou null).
     *
     * @param int $userid
     * @return string|null
     */
    public static function chat_of(int $userid): ?string {
        $chat = (string) get_user_preferences(self::PREF_CHAT, '', $userid);
        return preg_match('/^-?\d{1,20}$/', $chat) ? $chat : null;
    }

    /**
     * Lê as mensagens enviadas ao robô e trata "/start CÓDIGO" (ligar) e "/parar" (desligar).
     * Chamado pela tarefa agendada a cada minuto.
     *
     * @param telegram|null $tg
     * @return int quantas contas foram ligadas ou desligadas
     */
    public static function process_updates(?telegram $tg = null): int {
        global $DB;
        $tg = $tg ?? new telegram();
        $offset = (int) get_config('message_neadavisos', 'updateoffset');
        $result = $tg->call('getUpdates', ['offset' => $offset, 'timeout' => 0, 'allowed_updates' => ['message']]);
        if (empty($result['ok']) || empty($result['result'])) {
            return 0;
        }
        $changed = 0;
        foreach ($result['result'] as $update) {
            $offset = max($offset, (int) $update['update_id'] + 1);
            $msg = $update['message'] ?? [];
            $chat = $msg['chat'] ?? [];
            if (($chat['type'] ?? '') !== 'private' || empty($chat['id'])) {
                continue;                                          // Grupos e canais são ignorados.
            }
            $chatid = (string) $chat['id'];
            $text = trim((string) ($msg['text'] ?? ''));
            if (preg_match('#^/(parar|stop)\b#i', $text)) {
                $userids = $DB->get_fieldset_select('user_preferences', 'userid', 'name = :name AND value = :value',
                    ['name' => self::PREF_CHAT, 'value' => $chatid]);
                foreach ($userids as $userid) {
                    self::unlink((int) $userid);
                    $changed++;
                }
                $tg->send($chatid, get_string('telegramunlinked', 'message_neadavisos'));
                continue;
            }
            $code = preg_match('#^(?:/start\s+)?([a-f0-9]{16})$#', $text, $m) ? $m[1] : '';
            $userid = $code ? self::user_for_code($code) : null;
            if ($userid) {
                self::link($userid, $chatid);
                $changed++;
                $tg->send($chatid, get_string('telegramlinked', 'message_neadavisos', s(format_string(
                    get_site()->fullname))));
            } else if (preg_match('#^/start#', $text)) {
                $tg->send($chatid, get_string('telegramhowto', 'message_neadavisos'));
            }
        }
        set_config('updateoffset', $offset, 'message_neadavisos');
        return $changed;
    }
}
