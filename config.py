import os

import os
from pathlib import Path


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:30b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))

DIAMOND_PREDICT_SCRIPT = os.getenv(
    "DIAMOND_PREDICT_SCRIPT",
    r"D:\Python Project\DiaMond\DiaMond\tools\predict_diamond.py",
)
DIAMOND_CHECKPOINT = os.getenv("DIAMOND_CHECKPOINT", "")
DIAMOND_OUTPUT_DIR = Path(
    os.getenv("DIAMOND_OUTPUT_DIR", str(Path("data") / "diamond_outputs"))
)
