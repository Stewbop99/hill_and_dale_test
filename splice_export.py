#!/usr/bin/env python3
"""
splice_export.py

Reads pre-rendered widget HTML files (5 types x N runners) from
hill_and_dale_app/charts/pre_rendered/<type>/*.html, splices each
runner's 5 widgets into a single self-contained page at
hill_and_dale_test/runners/<runner-slug>.html, and appends a
matching <li> entry to hill_and_dale_test/index.html.

Designed to run repeatedly / idempotently: re-running for a runner
already in index.html will NOT create a duplicate <li>, and will
overwrite that runner's page with fresh content.

USAGE:
    python splice_export.py                  # process every runner found
    python splice_export.py brendan-ward      # process just one runner
    python splice_export.py --dry-run         # report what would happen, write nothing

Folder layout assumed (relative to this script's location):
    hill_and_dale_app/charts/pre_rendered/<widget_type>/*.html   (input, read-only)
    hill_and_dale_test/runners/<slug>.html                       (output, one per runner)
    hill_and_dale_test/index.html                                (landing page, <li> appended)
"""

import re
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

# Order locked in by the user: best_day -> best_year -> career -> best_route -> most_reliable
WIDGET_ORDER = ["best_day", "best_year", "career", "best_route", "most_reliable"]

WIDGET_TITLES = {
    "best_day": "Best Ever Run",
    "best_year": "Best Year",
    "career": "Career",
    "best_route": "Best Route",
    "most_reliable": "Most Reliable",
}

THIS_FILE = Path(__file__).resolve()
CHARTS_DIR = THIS_FILE.parent                      # hill_and_dale_app/charts
APP_DIR = CHARTS_DIR.parent                         # hill_and_dale_app
PRE_RENDERED_DIR = CHARTS_DIR / "pre_rendered"
SITE_DIR = APP_DIR.parent / "hill_and_dale_test"    # sibling folder
RUNNERS_OUT_DIR = SITE_DIR / "runners"
INDEX_HTML = SITE_DIR / "index.html"

LI_MARKER = "<!-- export script appends one <li> per runner here -->"


# ----------------------------------------------------------------------
# Filename / slug matching (separator-agnostic: handles '-' and '_')
# ----------------------------------------------------------------------

def normalize_slug(raw: str) -> str:
    """Turn any mix of hyphens/underscores into a canonical hyphenated slug."""
    return re.sub(r"[_\s]+", "-", raw.strip().lower()).strip("-")


def slug_to_display_name(slug: str) -> str:
    """brendan-ward -> Brendan Ward"""
    return " ".join(part.capitalize() for part in slug.split("-"))


def find_widget_files(widget_type: str) -> dict:
    """
    Scan pre_rendered/<widget_type>/ and return {runner_slug: filepath}.

    Standard pattern (all 5 widget types as of the latest naming convention):
        <type>_<runner-slug>.html   e.g. best_route_brendan-ward.html

    Also tolerates, as a defensive fallback for any stray old-style files:
        <type>-<name>.html                (hyphen after type)
        <name>_<type>.html / <name>-<type>.html   (name-first, the old
                                                    route_suitability style)

    Agnostic to '-' vs '_' as the separator in all cases.
    """
    folder = PRE_RENDERED_DIR / widget_type
    results = {}

    if not folder.is_dir():
        return results

    for f in folder.glob("*.html"):
        stem = f.stem  # filename without .html

        slug = None

        # Try type-first pattern: <type>[-_]<name>
        # Build a regex that accepts either separator right after the type name.
        type_first_pattern = re.compile(
            r"^" + re.escape(widget_type) + r"[-_](?P<name>.+)$", re.IGNORECASE
        )
        m = type_first_pattern.match(stem)
        if m:
            slug = normalize_slug(m.group("name"))
        else:
            # Try name-first pattern: <name>[-_]<type>  (route_suitability's reversed style)
            name_first_pattern = re.compile(
                r"^(?P<name>.+?)[-_]" + re.escape(widget_type) + r"$", re.IGNORECASE
            )
            m = name_first_pattern.match(stem)
            if m:
                slug = normalize_slug(m.group("name"))

        if slug is None:
            print(f"  [warn] could not parse runner slug from '{f.name}' in "
                  f"'{widget_type}/' \u2014 skipping this file")
            continue

        if slug in results:
            print(f"  [warn] duplicate match for runner '{slug}' in '{widget_type}/' "
                  f"({results[slug].name} vs {f.name}) \u2014 keeping the first, skipping {f.name}")
            continue

        results[slug] = f

    return results


# ----------------------------------------------------------------------
# Extraction + namespacing
# ----------------------------------------------------------------------

STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.DOTALL | re.IGNORECASE)
SCRIPT_RE = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.DOTALL | re.IGNORECASE)
BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.DOTALL | re.IGNORECASE)
SRC_ATTR_RE = re.compile(r"src\s*=", re.IGNORECASE)

# Matches id="foo" / id='foo' for rewriting, and getElementById('foo') / ("foo") in scripts
ID_ATTR_RE = re.compile(r"""\bid\s*=\s*(["'])([A-Za-z0-9_-]+)\1""")
GET_ELEMENT_BY_ID_RE = re.compile(r"""getElementById\(\s*(["'])([A-Za-z0-9_-]+)\1\s*\)""")
HASH_REF_RE = re.compile(r"""(["'])#([A-Za-z0-9_-]+)\1""")  # e.g. querySelector('#chart')


def extract_parts(html: str):
    """Pull out <body> inner HTML (with <script>/<style> tags removed), all
    <style> block contents, and all inline <script> bodies.

    NOTE: <script> tags normally live inside <body>...</body> in the source
    files, so they get captured by the body match. They are extracted
    separately here and MUST be stripped back out of body_html, or the same
    script content ends up emitted twice in the final page: once verbatim
    (inside body_html) and once correctly namespaced/IIFE-wrapped (via the
    separate script_block). Same applies to <style>, in case any source file
    puts it inside <body> rather than <head>.
    """
    body_match = BODY_RE.search(html)
    body_html = body_match.group(1) if body_match else html

    styles = STYLE_RE.findall(html)

    inline_scripts = []
    external_script_tags = []
    for m in SCRIPT_RE.finditer(html):
        attrs = m.group("attrs")
        body = m.group("body")
        if SRC_ATTR_RE.search(attrs):
            # External script (e.g. Chart.js CDN) -- keep the tag as-is, hoist later
            external_script_tags.append(f"<script{attrs}></script>")
        else:
            inline_scripts.append(body)

    # Strip <script>...</script> and <style>...</style> out of body_html now
    # that their contents have been captured above -- otherwise duplicated.
    body_html = SCRIPT_RE.sub("", body_html)
    body_html = STYLE_RE.sub("", body_html)

    return body_html, styles, inline_scripts, external_script_tags


def namespace_block(body_html: str, styles: list, scripts: list, prefix: str):
    """
    Rewrite every id="X" -> id="prefix-X" in the body+styles, and every
    getElementById('X') / querySelector('#X') -> the same prefixed id, inside
    the scripts. Wrap each script in an IIFE so top-level const/let/function
    declarations can't collide with another widget's globals on the same page.
    """

    ids_found = set()

    def collect_id(m):
        ids_found.add(m.group(2))
        return m.group(0)

    ID_ATTR_RE.sub(collect_id, body_html)
    for s in styles:
        ID_ATTR_RE.sub(collect_id, s)  # styles rarely have id attrs, harmless if none

    def rewrite_id_attr(m):
        quote, name = m.group(1), m.group(2)
        return f'id={quote}{prefix}-{name}{quote}'

    new_body = ID_ATTR_RE.sub(rewrite_id_attr, body_html)

    new_styles = []
    for s in styles:
        # Rewrite #id selectors in CSS so prefixed ids still get styled correctly.
        def rewrite_css_id_selector(m):
            name = m.group(1)
            if name in ids_found:
                return f"#{prefix}-{name}"
            return m.group(0)

        s2 = re.sub(r"#([A-Za-z0-9_-]+)", rewrite_css_id_selector, s)
        new_styles.append(s2)

    new_scripts = []
    for script_body in scripts:
        s = script_body

        def rewrite_get_by_id(m):
            quote, name = m.group(1), m.group(2)
            if name in ids_found:
                return f"getElementById({quote}{prefix}-{name}{quote})"
            return m.group(0)

        s = GET_ELEMENT_BY_ID_RE.sub(rewrite_get_by_id, s)

        def rewrite_hash_ref(m):
            quote, name = m.group(1), m.group(2)
            if name in ids_found:
                return f"{quote}#{prefix}-{name}{quote}"
            return m.group(0)

        s = HASH_REF_RE.sub(rewrite_hash_ref, s)

        # Wrap in an IIFE so const/let/function declarations are scoped to this
        # widget only and can't collide with another widget's same-named globals
        # (several source files reuse generic names like COLORS, LABELS, TOOLTIPS).
        wrapped = f"(function() {{\n{s}\n}})();"
        new_scripts.append(wrapped)

    return new_body, new_styles, new_scripts


def build_section(widget_type: str, slug: str, file_path: Path) -> tuple:
    """
    Returns (section_html, external_script_tags) for one widget.
    section_html includes its own <style> (scoped via a wrapper class)
    and IIFE-wrapped <script> blocks, namespaced by widget_type.
    """
    html = file_path.read_text(encoding="utf-8")
    body_html, styles, scripts, external_scripts = extract_parts(html)

    prefix = widget_type.replace("_", "-")  # e.g. route_suitability -> route-suitability
    new_body, new_styles, new_scripts = namespace_block(body_html, styles, scripts, prefix)

    title = WIDGET_TITLES.get(widget_type, widget_type.replace("_", " ").title())

    style_block = ""
    if new_styles:
        # Scope every rule under .widget-<prefix> by naive prefixing of each selector.
        # This is a pragmatic (not bulletproof) scoping approach: it catches the vast
        # majority of simple selectors used in these widgets (classes, element types,
        # ids already namespaced above). It will NOT correctly scope @media/@keyframes
        # internals perfectly, but those are passed through unscoped which is safe
        # (keyframe names rarely collide; if they ever do, rename the keyframe).
        combined_css = "\n".join(new_styles)
        style_block = f"<style>\n/* --- {widget_type} styles, scoped under .widget-{prefix} --- */\n{scope_css(combined_css, f'.widget-{prefix}')}\n</style>"

    script_block = "\n".join(f"<script>\n{s}\n</script>" for s in new_scripts)

    section_html = f"""
<section class="widget widget-{prefix}" id="section-{prefix}" data-runner="{slug}">
  <h2 class="widget-section-title">{title}</h2>
  {style_block}
  <div class="widget-inner">
    {new_body}
  </div>
  {script_block}
</section>
""".strip()

    return section_html, external_scripts


CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
AT_RULE_START_RE = re.compile(r"^\s*@")


def scope_css(css: str, scope_selector: str) -> str:
    """
    Naive selector-scoping: prefixes each top-level selector with scope_selector,
    unless it's a bare 'body'/'html' selector (rewritten to the scope itself,
    since these widgets style `body` directly but we can't restyle the real
    page body per-widget) or an @-rule (left untouched and passed through).
    """
    out_parts = []

    pos = 0
    for m in CSS_RULE_RE.finditer(css):
        selector_part, decl_part = m.group(1), m.group(2)
        selector_part_stripped = selector_part.strip()

        if not selector_part_stripped:
            continue

        if AT_RULE_START_RE.match(selector_part_stripped):
            # @media, @keyframes, @font-face etc. -- pass through as-is, not scoped.
            out_parts.append(f"{selector_part} {{{decl_part}}}")
            continue

        new_selectors = []
        for sel in selector_part_stripped.split(","):
            sel = sel.strip()
            if sel in ("body", "html", "*", "*, *::before, *::after", "*::before, *::after"):
                new_selectors.append(scope_selector)
            elif sel.startswith("*"):
                new_selectors.append(f"{scope_selector} {sel}")
            else:
                new_selectors.append(f"{scope_selector} {sel}")
        out_parts.append(f"{', '.join(new_selectors)} {{{decl_part}}}")

    return "\n".join(out_parts)


# ----------------------------------------------------------------------
# Page assembly
# ----------------------------------------------------------------------

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{display_name} \u2014 Hill and Dale</title>
<link rel="stylesheet" href="../assets/css/style.css">
{external_scripts}
<style>
  /* Page-level layout for stacked widget sections. Each widget's own
     styles are scoped under .widget-<type> above, so these rules only
     control spacing/structure between sections, not widget internals. */
  body {{ margin: 0; padding: 0; background: #f3f2ee; }}
  .page-header {{
    max-width: 1000px; margin: 0 auto; padding: 24px 16px 0;
    font-family: system-ui, -apple-system, sans-serif;
  }}
  .page-header a {{ font-size: 13px; color: #1D9E75; text-decoration: none; }}
  .page-header h1 {{ font-size: 28px; margin: 8px 0 4px; }}
  .widget {{
    max-width: 1000px; margin: 24px auto; padding: 0 16px;
  }}
  .widget-section-title {{
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 13px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #888; margin: 0 0 10px;
  }}
  .widget-inner {{
    background: transparent;
  }}
</style>
</head>
<body>
  <div class="page-header">
    <a href="../index.html">&larr; All runners</a>
    <h1>{display_name}</h1>
  </div>

{sections}

</body>
</html>
"""


EXT_SCRIPT_SRC_RE = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _script_lib_key(tag: str) -> str:
    """
    Best-effort key to recognize 'the same library' across different CDN
    hosts/paths, e.g. jsdelivr's chart.umd.min.js vs cdnjs's chart.umd.js
    are both Chart.js and should only be loaded once per page. Falls back
    to the full URL if no known library name is recognized, so unrelated
    scripts are never accidentally merged.
    """
    m = EXT_SCRIPT_SRC_RE.search(tag)
    if not m:
        return tag
    url = m.group(1).lower()
    # filename, stripped of query string
    filename = url.rstrip("/").split("/")[-1].split("?")[0]
    # normalize common minified/versioned suffixes so chart.umd.min.js and
    # chart.umd.js collapse to the same key
    base = re.sub(r"\.min(?=\.js$)", "", filename)
    return base


def build_runner_page(slug: str, widget_files: dict) -> tuple:
    """
    widget_files: {widget_type: Path}, may be missing some types (warn, skip).
    Returns (page_html, missing_types).
    """
    sections = []
    all_external_scripts = []
    seen_lib_keys = set()
    missing = []

    for widget_type in WIDGET_ORDER:
        path = widget_files.get(widget_type)
        if path is None:
            missing.append(widget_type)
            sections.append(
                f'<section class="widget widget-{widget_type.replace("_","-")} widget-missing">'
                f'<p style="font-family:system-ui,sans-serif;color:#b00;padding:16px;">'
                f'Missing {WIDGET_TITLES.get(widget_type, widget_type)} widget for {slug} '
                f'\u2014 placeholder, re-run export once the file exists.</p></section>'
            )
            continue
        section_html, ext_scripts = build_section(widget_type, slug, path)
        sections.append(section_html)
        for tag in ext_scripts:
            key = _script_lib_key(tag)
            if key in seen_lib_keys:
                continue
            seen_lib_keys.add(key)
            all_external_scripts.append(tag)

    display_name = slug_to_display_name(slug)
    page_html = PAGE_TEMPLATE.format(
        display_name=display_name,
        sections="\n\n".join(sections),
        external_scripts="\n".join(all_external_scripts),
    )
    return page_html, missing


# ----------------------------------------------------------------------
# Landing page <li> insertion (idempotent)
# ----------------------------------------------------------------------

def update_index_html(slugs_processed: list, dry_run: bool = False):
    if not INDEX_HTML.exists():
        print(f"  [warn] {INDEX_HTML} not found \u2014 skipping landing page update")
        return

    index_html = INDEX_HTML.read_text(encoding="utf-8")

    if LI_MARKER not in index_html:
        print(f"  [warn] marker comment not found in index.html \u2014 skipping landing page update. "
              f"Expected to find:\n    {LI_MARKER}")
        return

    new_lis = []
    for slug in slugs_processed:
        href = f"runners/{slug}.html"
        existing_href_pattern = re.compile(
            r'<li>\s*<a\s+href="' + re.escape(href) + r'"[^>]*>.*?</a>\s*</li>',
            re.IGNORECASE | re.DOTALL,
        )
        if existing_href_pattern.search(index_html):
            print(f"  [info] {slug}: <li> already present in index.html, leaving as-is")
            continue
        display_name = slug_to_display_name(slug)
        new_lis.append(f'    <li><a href="{href}">{display_name}</a></li>')

    if not new_lis:
        print("  [info] no new <li> entries needed")
        return

    insertion = "\n".join(new_lis) + "\n    " + LI_MARKER
    updated_html = index_html.replace(LI_MARKER, insertion)

    if dry_run:
        print(f"  [dry-run] would insert {len(new_lis)} new <li> entr"
              f"{'y' if len(new_lis)==1 else 'ies'} into index.html:")
        for li in new_lis:
            print(f"    {li.strip()}")
        return

    INDEX_HTML.write_text(updated_html, encoding="utf-8")
    print(f"  [ok] inserted {len(new_lis)} new <li> entr"
          f"{'y' if len(new_lis)==1 else 'ies'} into index.html")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    requested_slugs = [normalize_slug(a) for a in args if not a.startswith("--")]

    print(f"Reading from: {PRE_RENDERED_DIR}")
    print(f"Writing to:   {RUNNERS_OUT_DIR}")
    print()

    # Build {widget_type: {slug: path}}
    per_type_files = {}
    all_slugs = set()
    for widget_type in WIDGET_ORDER:
        found = find_widget_files(widget_type)
        per_type_files[widget_type] = found
        all_slugs.update(found.keys())
        print(f"[{widget_type}] found {len(found)} file(s): {sorted(found.keys())}")

    print()

    if requested_slugs:
        target_slugs = [s for s in requested_slugs if s in all_slugs]
        not_found = [s for s in requested_slugs if s not in all_slugs]
        for nf in not_found:
            print(f"[warn] runner '{nf}' not found in any widget folder \u2014 skipping")
    else:
        target_slugs = sorted(all_slugs)

    if not target_slugs:
        print("No runners to process. Exiting.")
        return

    if not dry_run:
        RUNNERS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    processed = []
    for slug in target_slugs:
        widget_files_for_runner = {
            widget_type: per_type_files[widget_type].get(slug)
            for widget_type in WIDGET_ORDER
            if per_type_files[widget_type].get(slug) is not None
        }
        page_html, missing = build_runner_page(slug, widget_files_for_runner)

        out_path = RUNNERS_OUT_DIR / f"{slug}.html"

        if dry_run:
            status = "OK" if not missing else f"INCOMPLETE (missing: {', '.join(missing)})"
            print(f"  [dry-run] would write {out_path}  [{status}]")
        else:
            out_path.write_text(page_html, encoding="utf-8")
            status = "ok" if not missing else f"WARNING missing widgets: {', '.join(missing)}"
            print(f"  [ok] wrote {out_path}  ({status})")

        processed.append(slug)

    print()
    update_index_html(processed, dry_run=dry_run)


if __name__ == "__main__":
    main()
