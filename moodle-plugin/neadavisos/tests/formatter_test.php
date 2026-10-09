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
 * Testes do texto enviado ao Telegram (escape, privacidade, links).
 *
 * @package    message_neadavisos
 * @category   test
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @covers     \message_neadavisos\formatter
 * @covers     \message_neadavisos\telegram
 */
final class formatter_test extends \advanced_testcase {

    public function test_notification_is_escaped_and_without_footer(): void {
        $this->resetAfterTest();
        [$html, $url] = formatter::format((object) [
            'notification' => 1, 'subject' => 'Nota <script>x</script> 4 < 5 & "média"',
            'smallmessage' => "Sua nota: 9,0\n---------\nAltere suas preferências de notificação",
            'contexturl' => 'https://www.example.com/mod/assign/view.php?id=3',
        ]);
        $this->assertStringNotContainsString('<script>', $html);
        $this->assertStringContainsString('4 &lt; 5 &amp; &quot;média&quot;', $html);
        $this->assertStringNotContainsString('preferências', $html);
        $this->assertSame('https://www.example.com/mod/assign/view.php?id=3', $url);
    }

    public function test_private_message_content_stays_in_moodle_by_default(): void {
        $this->resetAfterTest();
        $from = $this->getDataGenerator()->create_user(['firstname' => 'Ana', 'lastname' => 'Souza']);
        $data = (object) ['notification' => 0, 'component' => 'moodle', 'name' => 'instantmessage',
            'userfrom' => $from, 'subject' => 'Mensagem', 'smallmessage' => 'Meu CPF é 123'];
        [$html] = formatter::format($data);
        $this->assertStringNotContainsString('CPF', $html);
        $this->assertStringContainsString('Ana Souza', $html);
        set_config('showmessagecontent', 1, 'message_neadavisos');
        [$html] = formatter::format($data);
        $this->assertStringContainsString('CPF', $html);
    }

    public function test_buttons_only_point_to_this_moodle_over_https(): void {
        global $CFG;
        $this->resetAfterTest();
        $CFG->wwwroot = 'https://nead.ifb.edu.br';
        $this->assertTrue(telegram::safe_link('https://nead.ifb.edu.br/course/view.php?id=1'));
        $this->assertFalse(telegram::safe_link('https://nead.ifb.edu.br.golpe.com/login'));
        $this->assertFalse(telegram::safe_link('http://nead.ifb.edu.br/course/view.php?id=1'));
        $this->assertFalse(telegram::safe_link('javascript:alert(1)'));
    }

    public function test_long_text_is_cut_without_open_tags(): void {
        $long = str_repeat("• <b>Item</b> <i>" . str_repeat('x', 90) . "</i>\n", 80);
        $cut = telegram::cut($long);
        $this->assertLessThanOrEqual(telegram::LIMIT, \core_text::strlen($cut));
        $this->assertSame(substr_count($cut, '<b>'), substr_count($cut, '</b>'));
    }
}
