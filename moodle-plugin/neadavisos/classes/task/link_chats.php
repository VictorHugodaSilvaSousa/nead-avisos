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

namespace message_neadavisos\task;

use message_neadavisos\linker;
use message_neadavisos\telegram;

/**
 * Lê as mensagens enviadas ao robô e liga/desliga contas (código de uso único, /parar).
 *
 * Usa getUpdates (o servidor chama o Telegram), sem abrir nenhum endereço público no Moodle.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class link_chats extends \core\task\scheduled_task {
    /**
     * @return string
     */
    public function get_name() {
        return get_string('tasklinkchats', 'message_neadavisos');
    }

    /**
     * Executa a tarefa.
     */
    public function execute() {
        if (!telegram::valid_token((string) get_config('message_neadavisos', 'bottoken'))) {
            return;
        }
        $changed = linker::process_updates();
        if ($changed) {
            mtrace("message_neadavisos: {$changed} conta(s) ligada(s)/desligada(s) do Telegram.");
        }
    }
}
