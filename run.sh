#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"
termux-wake-lock 2>/dev/null

pkill -9 -f "python main.py" 2>/dev/null
pkill -9 -f ngrok 2>/dev/null
pkill -9 -f cloudflared 2>/dev/null
pkill -9 -f "ssh.*lhr.life" 2>/dev/null
sleep 2

while true; do
    echo "═══════════════════════════════════════════"
    echo "  RehanCodex Fixed — START $(date)"
    echo "═══════════════════════════════════════════"

    python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('rehancodex.db')
    c = conn.cursor()
    c.execute(\"DELETE FROM settings WHERE key LIKE 'tunnel_%'\")
    conn.commit()
    conn.close()
except: pass
" 2>/dev/null

    python main.py
    RC=$?

    echo ""
    echo "  Bot exited (rc=$RC) at $(date) — restart in 10s"
    pkill -9 -f ngrok 2>/dev/null
    pkill -9 -f cloudflared 2>/dev/null
    pkill -9 -f "ssh.*lhr.life" 2>/dev/null
    sleep 10
done
