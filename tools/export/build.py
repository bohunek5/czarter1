#!/usr/bin/env python3
"""Render the public views of the Stillo 31 WordPress plugin without a database."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


SHIM = Path(__file__).with_name('render.php')
STATIC_TYPES = {'.txt', '.woff2', '.webp', '.png', '.css', '.js'}
SOURCE_DIRS = ['front/assets', 'front', 'site', 'booking', 'tour']
LOCAL_ORIGIN = 'https://preview.invalid/'
CLOCK = "new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Warsaw',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())"


def preview_url(value, base):
    parts = urlsplit(value)
    if value.startswith(LOCAL_ORIGIN):
        query = dict(parse_qsl(parts.query))
        language = 'en/' if query.pop('lang', 'pl') == 'en' else ''
        return urlunsplit(('', '', base + language + parts.path.lstrip('/'), urlencode(query), parts.fragment))
    if not parts.netloc and parts.path.startswith('/'):
        return base + parts.path.lstrip('/')
    return value


def rewrite_links(doc, base):
    for tag in doc.find_all(True):
        for key, value in list(tag.attrs.items()):
            if not isinstance(value, str):
                continue
            if key == 'srcset':
                sources = []
                for candidate in value.split(','):
                    url, *descriptor = candidate.split()
                    sources.append(' '.join([preview_url(url, base), *descriptor]))
                tag[key] = ', '.join(sources)
            elif key in ('action', 'src', 'href') or (key.startswith('data-') and value.startswith((LOCAL_ORIGIN, '/front/', '/site/', '/tour/', '/booking/'))):
                tag[key] = preview_url(value, base)


def disable_controls(controls):
    for control in controls:
        control['disabled'] = ''
        control.attrs.pop('required', None)


def prepare_forms(doc, base, english):
    if dock := doc.select_one('.mhg-dock-form'):
        dock['action'] = base + ('en/' if english else '') + 'rezerwacje/'
        if lang := dock.select_one('[name=lang]'):
            lang.decompose()

    if booking := doc.select_one('[data-mhb]'):
        config = json.loads(booking['data-mhb'])
        if config['open'] or config['inventory']:
            raise ValueError('The preview must render the offline calendar.')
        public_config = {k: config[k] for k in ['lang', 'min', 'today', 'open', 'inventory']}
        booking['data-mhb'] = json.dumps(public_config, separators=(',', ':'))
        note = doc.new_tag('p', attrs={'class': 'preview-note'})
        note.string = ('Preview calendar. You can try dates and equipment without making a booking.' if english
                       else 'Kalendarz pokazowy. Możesz wybrać termin i sprzęt. Rezerwacje i płatności są wyłączone.')
        booking.select_one('.mhb-heading').insert_after(note)
        booking.select_one('.mhb-note').string = ('Equipment quantities are for this preview only.' if english
                                                  else 'Liczby sztuk służą do przetestowania formularza.')
        disable_controls(booking.select('.mhb-person input, .mhb-submit'))
        submit = booking.select_one('.mhb-submit')
        submit['type'] = 'button'
        submit.string = 'Sending disabled in preview' if english else 'Wysyłka wyłączona w podglądzie'
        booking.select_one('[data-form]')['method'] = 'dialog'

    if reviews := doc.select_one('.mhg-review-form'):
        reviews['method'] = 'dialog'
        reviews.attrs.pop('action', None)
        for hidden in reviews.select('input[type=hidden], .mhg-hp'):
            hidden.decompose()
        disable_controls(reviews.select('input, textarea, button'))
        submit = reviews.select_one('button')
        submit['type'] = 'button'
        submit.string = 'Publishing disabled in preview' if english else 'Publikacja wyłączona w podglądzie'


def php_run(php, source, route):
    return subprocess.run([php, str(SHIM), str(source), route], check=True, capture_output=False,
                          stdout=subprocess.PIPE, encoding='utf-8').stdout


def render_page(php, source, build_dir, base, lang, slug):
    english = lang == 'en'
    uri = '/' + (slug + '/' if slug else '') + ('?lang=en' if english else '')
    doc = BeautifulSoup(php_run(php, source, uri), 'html5lib')
    if not doc.h1 or doc.html.get('lang') != lang:
        raise ValueError(f'The plugin did not render {uri}')
    rewrite_links(doc, base)
    for name, value in [('robots', 'noindex, nofollow, noarchive'), ('referrer', 'no-referrer')]:
        doc.head.append(doc.new_tag('meta', attrs={'name': name, 'content': value}))
    prepare_forms(doc, base, english)
    target = build_dir / ('en' if english else '') / slug / 'index.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(doc), encoding='utf-8')


def remove_js_block(script, start, end, replacement=''):
    # Keep unrelated upstream behavior intact and fail if template boundaries change.
    begin = script.index(start)
    finish = script.index(end, begin + len(start))
    return script[:begin] + replacement + script[finish:]


def offline_assets(build_dir):
    booking_file = build_dir / 'booking/booking.js'
    script = booking_file.read_text(encoding='utf-8')
    blocks = [
        ('  async function call(', '  function init(', ''),
        ('    async function inventory(', '    function summary()', ''),
        ('      try{\n        const values=await inventory', '    function goMonth(', '    }\n'),
        ('      if (cfg.inventory) {\n        if (!known(from))', '      start.value = from;', ''),
        ('      if(!cfg.inventory)return null;', '    function changeQty()', '      return null;\n    }\n'),
        ("    form.addEventListener('submit',async", '    displayMonth();',
         "    form.addEventListener('submit', event => event.preventDefault());\n")
    ]
    for start, end, replacement in blocks:
        script = remove_js_block(script, start, end, replacement)
    clock = f'    const currentDate = {CLOCK};\n    cfg.today = currentDate;\n    cfg.min = currentDate;\n'
    script = script.replace('    const en = cfg.lang', clock + '    const en = cfg.lang', 1)
    booking_file.write_text(script, encoding='utf-8')
    dock = build_dir / 'front/booking-dock.js'
    dock.write_text(dock.read_text(encoding='utf-8').replace('  const english =', f'  start.min = {CLOCK};\n  const english =', 1), encoding='utf-8')
    with (build_dir / 'booking/booking.css').open('a', encoding='utf-8') as css:
        css.write('\n.preview-note{font:inherit;color:#294c50;background:#ecf3f0;border-inline-start:3px solid #377677;margin:.3rem 0 1rem;padding:.65rem 1rem}.mhb-submit:disabled{opacity:.68;cursor:default}\n')


def build(php, source, destination, base):
    routes = json.loads(php_run(php, source, '--routes'))
    if not routes or any(not re.fullmatch('[a-z0-9-]+', route) for route in routes):
        raise ValueError('Route list is empty or contains an invalid slug.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent) as temporary:
        work = Path(temporary)
        for rel in SOURCE_DIRS:
            for asset in (source / rel).iterdir():
                if asset.is_file() and asset.suffix.lower() in STATIC_TYPES and 'admin' not in asset.name:
                    output = work / rel / asset.name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(asset, output)
        for language in ['pl', 'en']:
            for route in ['', *routes]:
                render_page(php, source, work, base, language, route)
        offline_assets(work)
        # Never package leftovers from a different project into a public preview.
        for path in destination.rglob('*'):
            if path.is_symlink() or (path.is_file() and not (work / path.relative_to(destination)).is_file()):
                raise ValueError(f'Use a clean export directory. Unexpected entry: {path}')
        shutil.copytree(work, destination, dirs_exist_ok=True)
    print(f'Exported {2 * (len(routes) + 1)} pages to {destination}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='plugin directory containing mazury-holiday.php')
    parser.add_argument('--output', required=True, type=Path, help='static export directory')
    parser.add_argument('--php', default='php', help='PHP CLI executable (default: php on PATH)')
    parser.add_argument('--base', default='/czarter1/', help='URL prefix of the GitHub Pages site')
    args = parser.parse_args()
    source, destination = args.source.resolve(), args.output.resolve()
    if not (source / 'mazury-holiday.php').is_file():
        parser.error('--source must contain mazury-holiday.php')
    if source == destination or source in destination.parents or destination in source.parents:
        parser.error('Use separate source and output directories.')
    if not re.fullmatch(r'/(?:[A-Za-z0-9_-]+/)*', args.base):
        parser.error('--base must be a URL path that starts and ends with a slash.')
    if not shutil.which(args.php):
        parser.error('PHP CLI not found. Install PHP or specify --php.')
    build(args.php, source, destination, args.base)


if __name__ == '__main__':
    main()
