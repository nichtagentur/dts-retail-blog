#!/usr/bin/env python3
"""Autonomous article generator for the DTS / Retail Media blog.

Usage: python3 autopublish.py <index 0..5>

Per iteration:
  1. Generate ~900-word article via OpenRouter (cheap text model, JSON mode)
  2. Generate hero image via Gemini 3 Flash Image
  3. Optionally generate short video (Veo 3.1 Lite)
  4. Write HTML article + update index.html card list
  5. git commit + push
  6. Headless-Chrome screenshot of the LOCAL article
  7. git push screenshot, post to SimpleMessage with article URL + screenshot URL
"""
import os, sys, json, base64, subprocess, time, urllib.request, pathlib, html, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOPICS = json.loads((ROOT / "auto/topics.json").read_text())
OR_KEY = os.environ["OPENROUTER_API_KEY"]
SM_KEY = os.environ.get("SIMPLEMESSAGE_API_KEY")
SITE_BASE = "https://nichtagentur.github.io/dts-retail-blog"
RAW_BASE = "https://raw.githubusercontent.com/nichtagentur/dts-retail-blog/main"

TEXT_MODEL = "google/gemini-3-flash-preview"
IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
VIDEO_MODEL = "google/veo-3.1-lite"

def log(*a):
    print("[autopub]", *a, flush=True)

def or_chat(messages, model=TEXT_MODEL, json_mode=False, modalities=None, max_tokens=None):
    body = {"model": model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if modalities:
        body["modalities"] = modalities
    if max_tokens:
        body["max_tokens"] = max_tokens
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://nichtagentur.github.io/", "X-Title": "dts-retail-blog-auto"},
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)

def gen_article_content(topic):
    sys_prompt = """Du bist Fachautor*in fuer digitales Drive-to-Store-Marketing und Retail Media im DACH-Raum.
Schreibe seriose, faktenorientierte Fachartikel mit konkreten Zahlen, Quellen-Hinweisen und realistischen Einschaetzungen.
Nutze deutsche Rechtschreibung mit ASCII-Ersatz fuer Umlaute (ae, oe, ue, ss). Keine Emoji.

WICHTIG: Verwende im body_html KEINE doppelten Anfuehrungszeichen (") - weder fuer HTML-Attribute noch innerhalb des Texts. Verwende stattdessen einfache Anfuehrungszeichen ' oder das Zeichen >. Nutze KEINE HTML-Attribute auf den Tags (also <p> nicht <p class='x'>). Das ist absolut kritisch, weil dein Output durch JSON-Parser laeuft.

Antworte AUSSCHLIESSLICH als JSON-Objekt mit den Feldern:
- title: max 70 Zeichen, suchmaschinen-optimiert
- description: max 155 Zeichen Meta-Description
- lede: 1-2 Saetze Einleitungs-Lede
- body_html: Artikel-Body als HTML, ca. 800-1100 Woerter, nutze h2, h3, p, ul, ol, li, strong, blockquote, optional table/thead/tbody/tr/th/td. KEIN html/body/h1/article-Tag, KEIN img-Tag. Mind. 3 h2-Sektionen, mind. 1 Liste, mind. 1 blockquote oder Tabelle. KEINE doppelten Anfuehrungszeichen im Text. Saubere fachliche Argumentation.
- references: Array von 3-4 plausiblen Quellen-Hinweisen als kurze Strings"""
    msg = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Thema: {topic}\n\nVeroeffentlichungsdatum: 2026-05-06. Geographischer Fokus: DACH (Deutschland, Oesterreich, Schweiz). "
         "Schreibe einen Fachartikel zu diesem Thema im Schema oben."},
    ]
    log("calling text model...")
    resp = or_chat(msg, json_mode=True, max_tokens=4096)
    content = resp["choices"][0]["message"]["content"]
    # strip code fences if present
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.M)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        log(f"  JSON parse failed ({e}), attempting repair")
        # Repair: in body_html string, replace unescaped " (not preceded by \) with '
        # Find body_html: "..."  span and clean it
        m = re.search(r'"body_html"\s*:\s*"', content)
        if m:
            start = m.end()
            # Walk until we find the matching closing quote that's followed by , or }
            depth = 0
            i = start
            while i < len(content):
                ch = content[i]
                if ch == "\\":
                    i += 2; continue
                if ch == '"':
                    # peek ahead skipping whitespace for , or }
                    j = i + 1
                    while j < len(content) and content[j] in " \t\r\n":
                        j += 1
                    if j < len(content) and content[j] in ",}":
                        end = i
                        inner = content[start:end]
                        cleaned = inner.replace('"', "'")
                        content = content[:start] + cleaned + content[end:]
                        break
                i += 1
        return json.loads(content)

def gen_image(prompt, out_path):
    log("calling image model...")
    resp = or_chat([{"role": "user", "content": prompt}],
                   model=IMAGE_MODEL, modalities=["image", "text"])
    msg = resp["choices"][0]["message"]
    images = msg.get("images") or []
    if not images:
        raise RuntimeError(f"No image returned: {json.dumps(msg)[:300]}")
    url = images[0]["image_url"]["url"]
    if url.startswith("data:"):
        data = base64.b64decode(url.split(",", 1)[1])
    else:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
    out_path.write_bytes(data)
    log(f"saved {out_path.name} ({len(data)//1024} KB)")

def gen_video(prompt, out_path):
    log("calling video model (Veo 3.1 Lite)...")
    body = json.dumps({
        "model": VIDEO_MODEL, "prompt": prompt,
        "aspect_ratio": "16:9", "duration": 4, "resolution": "720p", "generate_audio": True,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/videos", data=body,
        headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        job = json.load(r)
    vid_id = job.get("id") or job.get("video", {}).get("id")
    if not vid_id:
        raise RuntimeError(f"No video id: {json.dumps(job)[:400]}")
    log(f"video job {vid_id}, polling...")
    deadline = time.time() + 240
    while time.time() < deadline:
        time.sleep(8)
        req = urllib.request.Request(
            f"https://openrouter.ai/api/v1/videos/{vid_id}",
            headers={"Authorization": f"Bearer {OR_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            status_resp = json.load(r)
        status = status_resp.get("status") or status_resp.get("video", {}).get("status")
        log(f"  video status: {status}")
        if status == "completed":
            urls = (status_resp.get("unsigned_urls")
                    or status_resp.get("video", {}).get("unsigned_urls")
                    or [])
            if not urls:
                raise RuntimeError(f"No urls: {json.dumps(status_resp)[:400]}")
            with urllib.request.urlopen(urls[0], timeout=120) as r:
                out_path.write_bytes(r.read())
            log(f"saved video {out_path.name}")
            return True
        if status in ("failed", "cancelled", "error"):
            raise RuntimeError(f"video failed: {json.dumps(status_resp)[:400]}")
    raise RuntimeError("video polling timed out")

def render_html(meta, t, slug, has_video):
    title = html.escape(meta["title"])
    desc = html.escape(meta["description"])
    lede = html.escape(meta["lede"])
    tag_text = html.escape(t["tag"])
    tag_color_var = {"purple": "var(--c-purple)", "cyan": "var(--c-cyan)",
                     "yellow": "var(--c-yellow)", "coral": "var(--c-coral)"}[t["tag_color"]]
    tag_text_color = "var(--c-cream)" if t["tag_color"] in ("purple", "coral") else "var(--c-navy)"
    refs_html = "".join(f"<li>{html.escape(r)}</li>" for r in meta.get("references", []))
    image_url_full = f"{SITE_BASE}/assets/img/{slug}-hero.png"
    canonical = f"{SITE_BASE}/artikel/{slug}.html"
    today = "2026-05-06"
    video_block = ""
    if has_video:
        video_block = f"""
  <figure class=\"article__hero\">
    <video controls preload=\"metadata\" poster=\"../assets/img/{slug}-hero.png\" style=\"width:100%;border-radius:var(--radius-lg);border:1.5px solid var(--c-navy);aspect-ratio:16/9;object-fit:cover;\">
      <source src=\"../assets/video/{slug}.mp4\" type=\"video/mp4\">
    </video>
    <figcaption>4-Sekunden-Video, generiert mit Veo 3.1 Lite zur Illustration.</figcaption>
  </figure>"""
    else:
        video_block = f"""
  <figure class=\"article__hero\">
    <img src=\"../assets/img/{slug}-hero.png\" alt=\"{tag_text} - Symbolbild\" width=\"1600\" height=\"900\">
  </figure>"""
    return f"""<!doctype html>
<html lang=\"de\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{title}</title>
<meta name=\"description\" content=\"{desc}\">
<link rel=\"canonical\" href=\"{canonical}\">
<meta property=\"og:type\" content=\"article\">
<meta property=\"og:title\" content=\"{title}\">
<meta property=\"og:description\" content=\"{desc}\">
<meta property=\"og:url\" content=\"{canonical}\">
<meta property=\"og:image\" content=\"{image_url_full}\">
<meta property=\"article:published_time\" content=\"{today}\">
<meta property=\"article:author\" content=\"Alexandra Aichholzer\">
<meta name=\"twitter:card\" content=\"summary_large_image\">
<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700;12..96,800&family=DM+Sans:wght@400;500;600;700&display=swap\">
<link rel=\"icon\" href=\"../favicon.ico\" type=\"image/png\">
<link rel=\"stylesheet\" href=\"../assets/style.css\">
<script type=\"application/ld+json\">
{{\"@context\":\"https://schema.org\",\"@type\":\"Article\",\"headline\":{json.dumps(meta["title"])},\"description\":{json.dumps(meta["description"])},\"image\":[\"{image_url_full}\"],\"datePublished\":\"{today}\",\"dateModified\":\"{today}\",\"inLanguage\":\"de-AT\",\"author\":{{\"@type\":\"Person\",\"name\":\"Alexandra Aichholzer\",\"url\":\"{SITE_BASE}/about.html\"}},\"publisher\":{{\"@type\":\"Organization\",\"name\":\"StoreSignal Editorial\",\"url\":\"{SITE_BASE}/\"}},\"mainEntityOfPage\":\"{canonical}\"}}
</script>
<script type=\"application/ld+json\">
{{\"@context\":\"https://schema.org\",\"@type\":\"BreadcrumbList\",\"itemListElement\":[{{\"@type\":\"ListItem\",\"position\":1,\"name\":\"Startseite\",\"item\":\"{SITE_BASE}/\"}},{{\"@type\":\"ListItem\",\"position\":2,\"name\":\"{tag_text}\",\"item\":\"{SITE_BASE}/\"}},{{\"@type\":\"ListItem\",\"position\":3,\"name\":{json.dumps(meta["title"])}}}]}}
</script>
</head>
<body>
<a class=\"skip-link\" href=\"#main\">Zum Inhalt springen</a>
<header class=\"site-header\">
  <div class=\"site-header__inner\">
    <a class=\"brand\" href=\"../\">Store<span>Signal</span></a>
    <nav class=\"site-nav\" aria-label=\"Hauptnavigation\">
      <a href=\"../\">Artikel</a>
      <a href=\"../about.html\">Ueber uns</a>
    </nav>
  </div>
</header>

<main id=\"main\">
<article class=\"article\">
  <nav class=\"article__breadcrumbs\" aria-label=\"Breadcrumb\">
    <a href=\"../\">Start</a> &rsaquo; <span>{tag_text}</span>
  </nav>

  <header class=\"article__header\">
    <span class=\"article__tag\" style=\"background:{tag_color_var};color:{tag_text_color};\">{tag_text}</span>
    <h1 class=\"article__title\">{title}</h1>
    <p class=\"article__lede\">{lede}</p>
    <div class=\"article__meta\">
      <span><strong>Autorin:</strong> <a href=\"../about.html\">Alexandra Aichholzer</a></span>
      <span><strong>Veroeffentlicht:</strong> 6. Mai 2026</span>
      <span><strong>Auto-generiert:</strong> Auto-Publisher v1</span>
    </div>
  </header>
{video_block}

  <div class=\"article__body\">
{meta["body_html"]}
  </div>

  <aside class=\"author-box\">
    <div class=\"author-box__inner\">
      <div class=\"author-box__avatar\" aria-hidden=\"true\">AA</div>
      <div class=\"author-box__text\">
        <strong>Alexandra Aichholzer</strong>
        <p>Chefredakteurin StoreSignal. Begleitet seit 2018 Drive-to-Store- und Retail-Media-Programme im DACH-Raum.</p>
        <p><a href=\"../about.html\">Mehr ueber die Redaktion</a></p>
      </div>
    </div>
  </aside>

  <section class=\"refs\" aria-label=\"Quellen\">
    <h2>Quellen & weiterfuehrende Links</h2>
    <ol>{refs_html}</ol>
  </section>
</article>
</main>

<footer class=\"site-footer\">
  <div class=\"site-footer__inner\">
    <div>
      <h3>StoreSignal</h3>
      <p>Unabhaengige Fachredaktion fuer Drive-to-Store und Retail Media im deutschsprachigen Raum.</p>
    </div>
    <div>
      <h3>Themen</h3>
      <ul>
        <li><a href=\"../\">Alle Artikel</a></li>
      </ul>
    </div>
    <div>
      <h3>Redaktion</h3>
      <ul>
        <li><a href=\"../about.html\">Ueber uns</a></li>
      </ul>
    </div>
  </div>
  <div class=\"site-footer__legal\">
    <span>(c) 2026 StoreSignal Editorial</span>
    <span><a href=\"../about.html#impressum\">Impressum</a> - <a href=\"../about.html#datenschutz\">Datenschutz</a></span>
  </div>
</footer>
</body>
</html>
"""

def update_index_card(slug, meta, t):
    idx_path = ROOT / "index.html"
    idx = idx_path.read_text()
    tag_class = {"purple": "tag--purple", "cyan": "tag--cyan",
                 "yellow": "", "coral": "tag--coral"}[t["tag_color"]]
    title = html.escape(meta["title"])
    desc = html.escape(meta["description"])
    tag_text = html.escape(t["tag"])
    card = f"""    <article class=\"card\">
      <a href=\"artikel/{slug}.html\" class=\"card__media\" aria-hidden=\"true\" tabindex=\"-1\">
        <img src=\"assets/img/{slug}-hero.png\" alt=\"\" width=\"640\" height=\"360\" loading=\"lazy\">
      </a>
      <div class=\"card__body\">
        <span class=\"card__tag {tag_class}\">{tag_text}</span>
        <h2 class=\"card__title\"><a href=\"artikel/{slug}.html\">{title}</a></h2>
        <p class=\"card__excerpt\">{desc}</p>
        <p class=\"card__meta\">6. Mai 2026 - Auto-generiert</p>
      </div>
    </article>
"""
    new_idx = idx.replace("<!-- AUTO-CARDS-START -->",
                          "<!-- AUTO-CARDS-START -->\n" + card.rstrip())
    idx_path.write_text(new_idx)

def screenshot_local(slug, out_path):
    file_url = f"file://{ROOT}/artikel/{slug}.html"
    cmd = ["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
           "--hide-scrollbars", "--window-size=1280,1800",
           f"--screenshot={out_path}", file_url]
    log("taking screenshot...")
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)

def git_push(msg):
    subprocess.run(["git", "-C", str(ROOT), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m", msg], check=True)
    subprocess.run(["git", "-C", str(ROOT), "push", "-q"], check=True)

def post_simplemessage(text):
    if not SM_KEY:
        log("WARN: no SIMPLEMESSAGE_API_KEY"); return
    body = json.dumps({"text": text}).encode()
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                "https://simplemessage.franzai.com/api/messages", data=body,
                headers={"Authorization": f"Bearer {SM_KEY}", "Content-Type": "application/json",
                         "User-Agent": "dts-retail-blog-auto/1"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last_err = e
            log(f"  simplemessage attempt {attempt+1} failed: {e}")
            time.sleep(5 * (attempt + 1))
    log(f"  simplemessage post FAILED after retries: {last_err}")
    return None

def main():
    idx = int(sys.argv[1])
    t = TOPICS[idx]
    slug = t["slug"]
    log(f"=== iteration {idx+1}/{len(TOPICS)}: {slug} ===")

    # 1. text
    meta = gen_article_content(t["topic"])
    log(f"got article: title='{meta['title'][:60]}' body={len(meta['body_html'])}b")

    # 2. image
    img_path = ROOT / f"assets/img/{slug}-hero.png"
    gen_image(t["image_prompt"], img_path)

    # 3. optional video
    has_video = bool(t.get("video"))
    if has_video:
        (ROOT / "assets/video").mkdir(exist_ok=True)
        try:
            gen_video(t["video_prompt"], ROOT / f"assets/video/{slug}.mp4")
        except Exception as e:
            log(f"video failed, falling back to image-only: {e}")
            has_video = False

    # 4. write HTML
    article_path = ROOT / f"artikel/{slug}.html"
    article_path.write_text(render_html(meta, t, slug, has_video))
    update_index_card(slug, meta, t)

    # 5. push article
    git_push(f"auto: publish {slug}")

    # 6. screenshot
    shot_path = ROOT / f"assets/img/screenshots/{slug}.png"
    screenshot_local(slug, shot_path)

    # 7. push screenshot
    git_push(f"auto: screenshot for {slug}")

    # 8. post to simplemessage
    article_url = f"{SITE_BASE}/artikel/{slug}.html"
    shot_url = f"{RAW_BASE}/assets/img/screenshots/{slug}.png"
    note_video = " (mit 4-Sek-Video von Veo 3.1 Lite)" if has_video else ""
    text = (f"Auto-Publish #{idx+1}/6: \"{meta['title']}\"{note_video}\n\n"
            f"Live: {article_url}\n\n![screenshot]({shot_url})")
    if len(text) > 1000:
        text = text[:990] + "..."
    log("posting to simplemessage...")
    post_simplemessage(text)
    log(f"DONE iteration {idx+1}")

if __name__ == "__main__":
    main()
