#!/bin/sh
cd "$(dirname "$0")"
python3 -m http.server 8765 &
sleep 1
open http://localhost:8765 2>/dev/null || xdg-open http://localhost:8765 2>/dev/null
wait
