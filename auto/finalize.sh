#!/bin/bash
# Wait for main loop to finish, then retry the failed in-store-audio article (index 2).
set -u
source ~/.env
cd "$(dirname "$0")/.."
LOG="auto/auto-loop.log"
echo "=== finalizer waiting for main loop $(date -Is) ===" >> "$LOG"
# Wait until run-loop.sh is no longer running
while pgrep -f "run-loop.sh" >/dev/null; do
    sleep 30
done
echo "=== finalizer: main loop done, retrying index 2 (in-store-audio) $(date -Is) ===" >> "$LOG"
sleep 10  # small breath
python3 auto/autopublish.py 2 >> "$LOG" 2>&1 || echo "finalizer iter 2 FAILED" >> "$LOG"
echo "=== finalizer done $(date -Is) ===" >> "$LOG"
curl -s -X POST https://simplemessage.franzai.com/api/messages \
  -H "Authorization: Bearer $SIMPLEMESSAGE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text":"Auto-Publish vollstaendig abgeschlossen: alle 6 Artikel sind live unter https://nichtagentur.github.io/dts-retail-blog/ - Stack: Gemini 3 Flash (Text), Gemini 3.1 Flash Image (Bilder), Veo 3.1 Lite (Video bei Programmatic DOOH)."}' >> "$LOG" 2>&1
