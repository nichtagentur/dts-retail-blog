#!/usr/bin/env python3
"""Generate images via OpenRouter + Gemini for the DTS / Retail Media blog."""
import os, json, base64, sys, urllib.request, pathlib

API_KEY = os.environ["OPENROUTER_API_KEY"]
MODEL = "google/gemini-3-pro-image-preview"
OUT_DIR = pathlib.Path("assets/img")
OUT_DIR.mkdir(parents=True, exist_ok=True)

STYLE = (
    "Editorial business photography, magazine quality, shot on Hasselblad medium-format, "
    "soft directional light, muted palette of deep navy, warm beige and brushed steel, "
    "subtle film grain, shallow depth of field, cinematic mood, "
    "wide 16:9 composition, no text, no signage, no logos, no watermark"
)

PROMPTS = {
    "site-hero": (
        "Aerial wide shot of a modern European shopping street at blue hour, "
        "warm shop windows glowing, faint translucent digital map overlay floating above the street "
        "with subtle pin markers — looks like an augmented-reality layer, not a graphic. "
        "Pedestrians blurred in motion. " + STYLE + ", no people in focus."
    ),
    "article1-hero": (
        "Close composition: a person's hand holding a smartphone showing a clean minimal map UI "
        "with a glowing route ending at a storefront across the street, "
        "real storefront softly out of focus in background, dusk light, "
        "warm reflections in the glass. " + STYLE
    ),
    "article1-inline": (
        "Overhead flatlay on a marble desk: open laptop showing a clean dashboard with line charts, "
        "a paper retail map with red pins, a coffee cup, an open notebook with handwriting blurred. "
        "Editorial, clean, " + STYLE
    ),
    "article2-hero": (
        "Wide interior shot of a modern European supermarket aisle at golden hour, "
        "large blank digital screens mounted above the shelves emitting soft warm glow "
        "(screens completely empty, no graphics, no text). "
        "Shopper silhouette far in the distance, soft focus. " + STYLE
    ),
    "article2-inline": (
        "Studio still life: a tablet device leaning against a stack of corrugated cardboard "
        "shipping boxes, the tablet screen showing only a soft abstract gradient (no UI, no text). "
        "Single warm spotlight, deep navy backdrop. " + STYLE
    ),
    "article3-hero": (
        "Top-down view of an urban district at night with a soft glowing translucent circular geofence "
        "ring overlay around a single retail building, neighbouring streets dim. "
        "Looks like a subtle data-visualisation layer over real cityscape. " + STYLE
    ),
    "article3-inline": (
        "Macro shot of a modern analytics dashboard on a high-resolution monitor, "
        "abstract clean line and bar charts in navy and amber on dark background, "
        "no readable text or numbers, slightly out of focus on the edges, "
        "in a quiet office at dusk. " + STYLE
    ),
}

def call_openrouter(prompt: str) -> bytes:
    body = json.dumps({
        "model": MODEL,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://nichtagentur.github.io/",
            "X-Title": "dts-retail-blog",
        },
    )
    with urllib.request.urlopen(req, timeout=240) as r:
        data = json.load(r)
    msg = data["choices"][0]["message"]
    images = msg.get("images") or []
    if not images:
        raise RuntimeError(f"No image returned. Raw: {json.dumps(msg)[:400]}")
    url = images[0]["image_url"]["url"]
    if url.startswith("data:"):
        return base64.b64decode(url.split(",", 1)[1])
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    keys = [target] if target else list(PROMPTS.keys())
    for k in keys:
        out = OUT_DIR / f"{k}.png"
        print(f"  -> {k} ...", flush=True)
        try:
            data = call_openrouter(PROMPTS[k])
            out.write_bytes(data)
            print(f"     saved {out} ({len(data)//1024} KB)")
        except Exception as e:
            print(f"     FAILED: {e}")
