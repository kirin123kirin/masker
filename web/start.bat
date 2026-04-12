@echo off
cd /d %~dp0
python -c "from pathlib import Path;import shutil;s=Path('models/tsmatz/xlm-roberta-ner-japanese/model_quantized.onnx');d=Path('models/tsmatz/xlm-roberta-ner-japanese/onnx/model_quantized.onnx');d.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(s),str(d)) if s.exists() and not d.exists() else None" 2>nul
start http://localhost:8765
python -m http.server 8765
pause
