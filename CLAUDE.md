# dts-retail-blog

SEO-optimierter Static-Site-Blog "StoreSignal" zu digitalem Drive-to-Store-Marketing und Retail Media Networks. Drei Fachartikel, handcoded HTML/CSS, kein Build-Step.

## Struktur
- `index.html` - Startseite mit Artikel-Cards
- `about.html` - Redaktion / E-E-A-T / Impressum / Datenschutz
- `artikel/*.html` - die drei Artikel
- `assets/style.css` - eine CSS-Datei
- `assets/img/*.png` - via `ai-images` Skill (Gemini 3 Pro Image) generiert
- `sitemap.xml`, `robots.txt`
- `gen.py` - reproduzierbares Skript fuer die Bildgenerierung

## Lokal preview
```
cd ~/Projects/dts-retail-blog && python3 -m http.server 8000
# http://localhost:8000
```

## Bilder neu erzeugen
```
python3 gen.py                # alle
python3 gen.py article1-hero  # nur eines
```

## Deploy
```
gh repo create nichtagentur/dts-retail-blog --public --source=. --push
# Settings -> Pages -> Branch: main, Folder: /
```

## SEO-Features
- Saubere `<title>` + Meta-Description je Seite
- Canonical, Open Graph, Twitter Card
- JSON-LD: WebSite, Blog, Article, BreadcrumbList, AboutPage, Person
- Semantisches HTML5, H1-H3-Hierarchie, alt-Texte
- Sitemap + robots.txt
- E-E-A-T: Autorenbox, About-Seite, Quellen, Impressum
