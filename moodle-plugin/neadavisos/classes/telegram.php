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
 * Cliente mínimo da API de robôs do Telegram.
 *
 * O token do robô nunca é registrado em log nem exibido: só vai na URL da chamada HTTPS.
 *
 * @package    message_neadavisos
 * @copyright  2026 Victor Hugo da Silva Sousa
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class telegram {
    /** Limite de caracteres de uma mensagem do Telegram (com folga). */
    const LIMIT = 4000;

    /** @var string token do robô (configuração do administrador). */
    protected $token;

    /**
     * @param string|null $token token do robô; padrão: configuração do plugin.
     */
    public function __construct(?string $token = null) {
        $this->token = $token ?? (string) get_config('message_neadavisos', 'bottoken');
    }

    /**
     * O token tem o formato que o @BotFather entrega (número:código)?
     *
     * @param string $token
     * @return bool
     */
    public static function valid_token(string $token): bool {
        return (bool) preg_match('/^\d{5,15}:[A-Za-z0-9_-]{30,64}$/', $token);
    }

    /**
     * Chama um método da API do Telegram.
     *
     * @param string $method
     * @param array $params
     * @return array resposta decodificada; ['ok' => false, 'description' => ...] em caso de falha
     */
    public function call(string $method, array $params = []): array {
        global $CFG;
        require_once($CFG->libdir . '/filelib.php');
        if (!self::valid_token($this->token)) {
            return ['ok' => false, 'description' => 'token do robô não configurado'];
        }
        $curl = new \curl();        // Respeita as regras de rede do administrador (hosts/portas bloqueados).
        $curl->setHeader(['Content-Type: application/json']);
        $raw = $curl->post('https://api.telegram.org/bot' . $this->token . '/' . $method, json_encode($params),
            ['CURLOPT_TIMEOUT' => 20, 'CURLOPT_CONNECTTIMEOUT' => 10]);
        $data = json_decode((string) $raw, true);
        if (!is_array($data)) {
            // Nunca inclui a URL (que contém o token) na mensagem de erro.
            return ['ok' => false, 'description' => 'sem resposta do Telegram (' . $curl->get_errno() . ')'];
        }
        return $data;
    }

    /**
     * Envia uma mensagem (HTML do Telegram) com um botão opcional.
     *
     * @param string $chatid
     * @param string $html texto já escapado (ver format_notification)
     * @param string|null $url link do botão (só https do próprio Moodle)
     * @param string|null $buttontext
     * @return bool
     */
    public function send(string $chatid, string $html, ?string $url = null, ?string $buttontext = null): bool {
        $params = ['chat_id' => $chatid, 'text' => self::cut($html), 'parse_mode' => 'HTML',
            'disable_web_page_preview' => true];
        if ($url && self::safe_link($url)) {
            $params['reply_markup'] = ['inline_keyboard' => [[['text' => $buttontext ?: 'Abrir no Moodle',
                'url' => $url]]]];
        }
        $result = $this->call('sendMessage', $params);
        if (empty($result['ok']) && preg_match("/can't parse entities|too long/i", $result['description'] ?? '')) {
            // Formatação recusada: reenvia como texto simples (o aviso nunca se perde por isso).
            $params['text'] = \core_text::substr(html_entity_decode(strip_tags($params['text']), ENT_QUOTES,
                'UTF-8'), 0, self::LIMIT);
            unset($params['parse_mode']);
            $result = $this->call('sendMessage', $params);
        }
        return !empty($result['ok']);
    }

    /**
     * Botões só levam ao próprio Moodle, por https (link de terceiros numa notificação não vira botão).
     *
     * @param string $url
     * @return bool
     */
    public static function safe_link(string $url): bool {
        global $CFG;
        $u = parse_url($url);
        $site = parse_url($CFG->wwwroot);
        return ($u['scheme'] ?? '') === 'https' && !empty($u['host']) && $u['host'] === ($site['host'] ?? null);
    }

    /**
     * Corta textos longos sem deixar marcação HTML aberta.
     *
     * @param string $html
     * @return string
     */
    public static function cut(string $html): string {
        if (\core_text::strlen($html) <= self::LIMIT) {
            return $html;
        }
        $cut = \core_text::substr($html, 0, self::LIMIT - 20);
        $pos = \core_text::strrpos($cut, "\n");
        if ($pos !== false && $pos > self::LIMIT / 2) {
            $cut = \core_text::substr($cut, 0, $pos);
        }
        if (substr_count($cut, '<') !== substr_count($cut, '>') ||
                preg_match_all('/<(b|i)>/', $cut) !== preg_match_all('/<\/(b|i)>/', $cut)) {
            $cut = s(html_entity_decode(strip_tags($cut), ENT_QUOTES, 'UTF-8'));
        }
        return $cut . "\n…";
    }
}
