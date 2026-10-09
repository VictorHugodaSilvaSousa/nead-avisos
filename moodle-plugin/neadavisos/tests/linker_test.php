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
 * Testes da ligação conta <-> Telegram (código de uso único).
 *
 * Rodar: vendor/bin/phpunit --filter message_neadavisos
 *
 * @package    message_neadavisos
 * @category   test
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \message_neadavisos\linker
 */
final class linker_test extends \advanced_testcase {

    /**
     * Telegram falso: devolve as mensagens dadas e registra os envios (sem rede).
     *
     * @param array $updates
     * @return telegram
     */
    private function fake_telegram(array $updates): telegram {
        return new class($updates) extends telegram {
            /** @var array */
            public $sent = [];
            /** @var array */
            private $updates;

            public function __construct(array $updates) {
                parent::__construct('1234567:' . str_repeat('A', 35));
                $this->updates = $updates;
            }

            public function call(string $method, array $params = []): array {
                if ($method === 'getUpdates') {
                    return ['ok' => true, 'result' => $this->updates];
                }
                $this->sent[] = $params;
                return ['ok' => true];
            }
        };
    }

    /**
     * @param int $id
     * @param string|int $chat
     * @param string $text
     * @param string $type
     * @return array
     */
    private function update(int $id, $chat, string $text, string $type = 'private'): array {
        return ['update_id' => $id, 'message' => ['chat' => ['id' => $chat, 'type' => $type], 'text' => $text]];
    }

    public function test_only_the_chat_with_the_code_is_linked(): void {
        $this->resetAfterTest();
        set_config('botusername', 'nead_avisos_bot', 'message_neadavisos');
        $user = $this->getDataGenerator()->create_user();
        $url = linker::link_url($user->id);
        $this->assertMatchesRegularExpression('#^https://t\.me/nead_avisos_bot\?start=[a-f0-9]{16}$#', $url);
        $code = substr($url, -16);

        $tg = $this->fake_telegram([
            $this->update(1, 666, '/start'),                         // Intruso sem código.
            $this->update(2, -100, '/start ' . $code, 'group'),      // Grupo com o código.
            $this->update(3, 111, '/start ' . $code),                // O dono.
        ]);
        $this->assertSame(1, linker::process_updates($tg));
        $this->assertSame('111', linker::chat_of($user->id));
        $this->assertNull(get_user_preferences(linker::PREF_CODE, null, $user->id));   // Código usado é apagado.
        $this->assertEquals(4, get_config('message_neadavisos', 'updateoffset'));
    }

    public function test_expired_and_malformed_codes_are_refused(): void {
        $this->resetAfterTest();
        $user = $this->getDataGenerator()->create_user();
        set_user_preference(linker::PREF_CODE, 'abcdefabcdefabcd|' . (time() - 1), $user->id);
        $this->assertNull(linker::user_for_code('abcdefabcdefabcd'));
        $this->assertNull(linker::user_for_code("x' OR 1=1 --"));
    }

    public function test_one_chat_belongs_to_one_account_and_parar_unlinks(): void {
        $this->resetAfterTest();
        $a = $this->getDataGenerator()->create_user();
        $b = $this->getDataGenerator()->create_user();
        linker::link($a->id, '111');
        linker::link($b->id, '111');
        $this->assertNull(linker::chat_of($a->id));
        $this->assertSame('111', linker::chat_of($b->id));
        linker::process_updates($this->fake_telegram([$this->update(9, 111, '/parar')]));
        $this->assertNull(linker::chat_of($b->id));
    }
}
