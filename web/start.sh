#!/bin/sh
cd "$(dirname "$0")"
python3 -c "from pathlib import Path;import shutil;s=Path('models/tsmatz/xlm-roberta-ner-japanese/model_quantized.onnx');d=Path('models/tsmatz/xlm-roberta-ner-japanese/onnx/model_quantized.onnx');d.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(s),str(d)) if s.exists() and not d.exists() else None" 2>/dev/null
python3 -m http.server 8765 &
sleep 1
open http://localhost:8765 2>/dev/null || xdg-open http://localhost:8765 2>/dev/null
wait
