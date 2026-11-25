<?php
// Standalone CLI renderer for the plugin's built-in content. No WordPress database is needed.
if (PHP_SAPI !== 'cli' || $argc !== 3) {
    exit(1);
}
$root = $argv[1];
$request = $argv[2];
define('ABSPATH', rtrim($root, '/').'/');
const ARRAY_A = 'ARRAY_A';
$_SERVER['REQUEST_METHOD'] = 'GET';
$_SERVER['REQUEST_URI'] = $request;
$path = parse_url($request, PHP_URL_PATH);
parse_str((string)parse_url($request, PHP_URL_QUERY), $_GET);

function plugin_dir_url($file) { return '/'; }
function plugins_url($path, $file) { return '/'.basename(dirname($file)).'/'.$path; }
function home_url($path = '/') { return 'https://preview.invalid'.($path ?: '/'); }
function admin_url($path) { return '/admin/'.$path; }
function rest_url($path) { return '/api/'.$path; }
function wp_parse_url($url, $component = -1) { return parse_url($url, $component); }
function add_query_arg($key, $value = null, $url = null) {
    $params = is_array($key) ? $key : [$key => $value];
    $url = is_array($key) ? $value : $url;
    return $url.(strpos($url, '?') === false ? '?' : '&').http_build_query($params);
}
function trailingslashit($value) { return rtrim($value, '/').'/'; }
function esc_html($value) { return htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8'); }
function esc_attr($value) { return esc_html($value); }
function esc_url($value) { return esc_html($value); }
function register_activation_hook() {}
function register_deactivation_hook() {}
function add_shortcode() {}
function add_filter($name, $callback, $priority = 10, $argc = 1) {
    $GLOBALS['filters'][$name][$priority][] = $callback;
}
function apply_filters($name, $value, ...$args) {
    $groups = $GLOBALS['filters'][$name] ?? [];
    ksort($groups);
    foreach ($groups as $group) {
        foreach ($group as $callback) $value = $callback($value, ...$args);
    }
    return $value;
}
function add_action($name, $callback, $priority = 10) {
    $GLOBALS['hooks'][$name][$priority][] = $callback;
}
function do_action($name, ...$args) {
    $groups = $GLOBALS['hooks'][$name] ?? [];
    ksort($groups);
    foreach ($groups as $group) {
        foreach ($group as $callback) if (is_callable($callback)) $callback(...$args);
    }
}
function remove_all_actions($name) { unset($GLOBALS['hooks'][$name]); }
function is_front_page() { return $GLOBALS['path'] === '/'; }
function is_admin() { return false; }
function is_feed() { return false; }
function is_embed() { return false; }
function is_preview() { return false; }
function is_trackback() { return false; }
function get_option($name, $default = '') {
    if ($name === 'permalink_structure') return '/%postname%/';
    if ($name === 'mhb_schema') return '1';
    if ($name === 'mhg_sections') {
        $ids = [];
        $next = 1;
        foreach (mhg_sections() as $section => $languages) {
            foreach ($languages as $code => $content) $ids[$section][$code] = $next++;
        }
        return $ids;
    }
    return $default;
}
function get_post($id) {
    $next = 1;
    foreach (mhg_sections() as $languages) {
        foreach ($languages as $content) {
            if ($next++ === $id) {
                return (object)['post_type' => 'mhg_material', 'post_status' => 'publish', 'post_content' => $content[1]];
            }
        }
    }
    return null;
}
function status_header($code) { http_response_code($code); }
function wp_head() { do_action('wp_head'); }
function wp_footer() { do_action('wp_footer'); }
function get_comments() { return []; }
function wp_nonce_field($name) {}
function do_blocks($value) { return $value; }
function wpautop($value) { return $value; }
function wp_enqueue_script($name, $url, $deps = [], $version = false, $footer = false) {
    $GLOBALS['scripts'][$name] = $url.'?v='.$version;
}
function wp_script_is($name, $list) { return isset($GLOBALS['scripts'][$name]); }
function wp_print_scripts($list) {
    foreach ($list as $name) echo '<script src="'.esc_attr($GLOBALS['scripts'][$name]).'"></script>';
}
function do_shortcode($value) {
    if (preg_match('~^\[mh_booking lang="(pl|en)" page="booking"\]$~', $value, $matches)) {
        return mhb_booking_form(['lang' => $matches[1], 'page' => 'booking']);
    }
    return $value;
}
function shortcode_atts($defaults, $attributes) { return array_merge($defaults, $attributes); }
function is_email($value) { return filter_var($value, FILTER_VALIDATE_EMAIL); }
function wp_json_encode($value, $flags = 0) { return json_encode($value, $flags); }
function wp_unique_id($prefix) { static $id = 0; return $prefix.(++$id); }

require $root.'/mazury-holiday.php';
if ($request === '--routes') {
    echo json_encode(array_values(array_column(mhg_routes(), 0)));
    exit;
}
do_action('template_redirect');
fwrite(STDERR, "Unrecognised route: $request\n");
exit(1);
