"""
Generate the poster images used by database/seeds/005_demo_catalogue.py.

Each poster is an original title card (gradient, shapes, title and details) saved as
<out>/<slug>.svg, so no third-party poster art is copied. Upload the files to the top level of
the public Supabase Storage bucket demo-posters, which is where the seed points poster_url.

    python scripts/generate_demo_posters.py              # writes ./demo-posters/
    python scripts/generate_demo_posters.py some/folder
"""
import hashlib
import importlib.util
import os
import sys
import textwrap
from xml.sax.saxutils import escape

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "demo-posters")

spec = importlib.util.spec_from_file_location("catalogue", os.path.join(ROOT, "database", "seeds", "005_demo_catalogue.py"))
catalogue = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalogue)

PALETTES = {
    "Action": ("#16051f", "#e94560", "#ffb347"),
    "Sci-Fi": ("#050b1f", "#3a86ff", "#8ecae6"),
    "Biography": ("#141414", "#c9a227", "#f1e3b0"),
    "Comedy": ("#2b1055", "#ff9f1c", "#ffd166"),
    "Sports": ("#04151f", "#2ec4b6", "#cbf3f0"),
    "concert": ("#12002b", "#ff2e88", "#7b2ff7"),
    "theatre": ("#1a0505", "#b5172a", "#e9c46a"),
    "Stand-up Comedy": ("#111111", "#ffd60a", "#ffffff"),
    "other": ("#062925", "#2a9d8f", "#e9f5db"),
}
LABELS = {"movie": "MOVIE", "concert": "CONCERT", "theatre": "PLAY", "Stand-up Comedy": "STAND-UP"}


def palette(event_type, genre):
    if event_type == "movie":
        return PALETTES.get(genre.split(",")[0].strip(), PALETTES["Action"])
    if genre in PALETTES:
        return PALETTES[genre]
    return PALETTES.get(event_type, PALETTES["other"])


def poster(slug, title, event_type, genre, details):
    bg, accent, light = palette(event_type, genre)
    h = int(hashlib.sha1(slug.encode()).hexdigest(), 16)
    cx, cy, r = 150 + h % 300, 140 + (h >> 8) % 160, 140 + (h >> 16) % 100
    angle = (h >> 24) % 40 - 20
    label = LABELS.get(genre, LABELS.get(event_type, "EVENT"))
    lines = textwrap.wrap(title, width=13 if len(title) > 22 else 12)[:4]
    size = 74 if len(lines) <= 2 else 60
    # Browse cards crop posters to their upper part, so the title sits in the middle third.
    top = 300 + size
    title_svg = "".join(
        f'<text x="48" y="{top + i * (size + 6)}" font-size="{size}" font-weight="800" fill="#ffffff" '
        f'font-family="Inter, Helvetica, Arial, sans-serif" letter-spacing="-1">{escape(line)}</text>'
        for i, line in enumerate(lines))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900" role="img" aria-label="{escape(title)}">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg}"/><stop offset="1" stop-color="{accent}" stop-opacity="0.85"/></linearGradient>
<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{light}" stop-opacity="0.55"/><stop offset="1" stop-color="{light}" stop-opacity="0"/></radialGradient>
<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0.2" stop-color="#000" stop-opacity="0"/><stop offset="0.55" stop-color="#000" stop-opacity="0.45"/><stop offset="1" stop-color="#000" stop-opacity="0.7"/></linearGradient>
</defs>
<rect width="600" height="900" fill="url(#g)"/>
<circle cx="{cx}" cy="{cy}" r="{r * 1.6:.0f}" fill="url(#glow)"/>
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{light}" stroke-opacity="0.35" stroke-width="2"/>
<circle cx="{cx}" cy="{cy}" r="{r * 0.62:.0f}" fill="none" stroke="{light}" stroke-opacity="0.2" stroke-width="10"/>
<g transform="rotate({angle} 300 450)" opacity="0.18"><rect x="-200" y="520" width="1000" height="26" fill="{light}"/><rect x="-200" y="566" width="1000" height="8" fill="{light}"/></g>
<rect width="600" height="900" fill="url(#fade)"/>
<rect x="48" y="52" rx="6" width="{len(label) * 13 + 28}" height="34" fill="{accent}"/>
<text x="62" y="76" font-size="18" font-weight="700" fill="#ffffff" font-family="Inter, Helvetica, Arial, sans-serif" letter-spacing="2">{label}</text>
{title_svg}
<text x="48" y="{top + len(lines) * (size + 6) + 10}" font-size="24" fill="{light}" font-family="Inter, Helvetica, Arial, sans-serif">{escape(genre)}</text>
<text x="48" y="{top + len(lines) * (size + 6) + 48}" font-size="22" fill="#ffffff" fill-opacity="0.8" font-family="Inter, Helvetica, Arial, sans-serif">{escape(details)}</text>
<text x="552" y="{900 - 48}" text-anchor="end" font-size="20" font-weight="700" fill="#ffffff" fill-opacity="0.7" font-family="Inter, Helvetica, Arial, sans-serif">TicketFlow</text>
</svg>
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    count = 0
    for m in catalogue.MOVIES:
        details = f"{m['language']} · {m['certificate']} · {m['runtime'] // 60}h {m['runtime'] % 60}m"
        with open(os.path.join(OUT, f"{m['slug']}.svg"), "w") as f:
            f.write(poster(m["slug"], m["title"], "movie", m["genre"], details))
        count += 1
    for (etype, slug, title, genre, language, minutes, age, *_rest) in catalogue.LIVE:
        details = f"{language} · {age} · {minutes} min"
        with open(os.path.join(OUT, f"{slug}.svg"), "w") as f:
            f.write(poster(slug, title, etype, genre, details))
        count += 1
    print(f"Wrote {count} posters to {OUT}; upload them to the demo-posters bucket")


if __name__ == "__main__":
    main()
