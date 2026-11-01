"""Configuration du manuel utilisateur HTML, sans dépendance à Odoo."""

from pathlib import Path

project = "Training Management"
author = "Contributeurs Training Management"
copyright = "2026, Contributeurs Training Management — LGPL-3.0-only"
version = "20.0"
release = "20.0 — édition du 1 novembre 2026"
language = "fr"
extensions = ["sphinx_rtd_theme"]
html_theme = "sphinx_rtd_theme"
html_title = "Documentation utilisateur Training Management"
html_short_title = "Training Management"
html_static_path = ["_static"]
html_css_files = ["manual.css"]
html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
    "style_nav_header_background": "#714b67",
}
html_show_sourcelink = False
html_show_sphinx = False
html_last_updated_fmt = None
html_copy_source = False
exclude_patterns = []
today = "1 novembre 2026"
smartquotes = True

rst_epilog = """
.. |menu| replace:: **Formations**
"""


def normalize_html_assets(app, exception):
    """Éviter le bruit d'espacement des gabarits dans le HTML versionné."""
    if exception:
        return
    for path in Path(app.outdir).rglob("*"):
        if path.is_file() and path.suffix in {".html", ".css", ".js", ".svg"}:
            content = path.read_text(encoding="utf-8")
            path.write_text(
                "\n".join(line.rstrip() for line in content.splitlines()) + "\n",
                encoding="utf-8",
            )


def setup(app):
    app.connect("build-finished", normalize_html_assets)
