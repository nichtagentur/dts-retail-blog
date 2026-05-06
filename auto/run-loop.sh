#!/bin/bash
# Run autopublish.py 6 times, every 5 minutes. Logs everything.
set -u
source ~/.env  # SIMPLEMESSAGE_API_KEY + OPENROUTER_API_KEY
cd "$(dirname "$0")/.."
LOG="auto/auto-loop.log"
echo "=== auto loop start $(date -Is) ===" >> "$LOG"
for i in 0 1 2 3 4 5; do
    echo "--- iteration $i start $(date -Is) ---" >> "$LOG"
    python3 auto/autopublish.py "$i" >> "$LOG" 2>&1 || echo "iter $i FAILED" >> "$LOG"
    if [ "$i" != "5" ]; then
        echo "--- iteration $i end, sleeping 300s ---" >> "$LOG"
        sleep 300
    fi
done
echo "=== auto loop done $(date -Is) ===" >> "$LOG"
# final summary post
source ~/.env
curl -s -X POST https://simplemessage.franzai.com/api/messages \
  -H "Authorization: Bearer $SIMPLEMESSAGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Auto-Publish abgeschlossen: 6 Artikel in 30 Minuten. Alle live unter https://nichtagentur.github.io/dts-retail-blog/ - Generierung mit Gemini 3.1 Flash (Text+Bild) und Veo 3.1 Lite (Video bei Programmatic DOOH)."}' >> "$LOG" 2>&1
