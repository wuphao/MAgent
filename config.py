import os
from pathlib import Path


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "300"))

DIAMOND_PREDICT_SCRIPT = os.getenv(
    "DIAMOND_PREDICT_SCRIPT",
    str(Path(__file__).resolve().parent / "tools" / "predict_diamond_integrated.py"),
)
DIAMOND_ROOT = Path(os.getenv("DIAMOND_ROOT", r"D:\Python Project\DiaMond\DiaMond"))
DIAMOND_PYTHON = os.getenv(
    "DIAMOND_PYTHON",
    str(DIAMOND_ROOT / ".venv" / "Scripts" / "python.exe"),
)
DIAMOND_CHECKPOINT = os.getenv(
    "DIAMOND_CHECKPOINT",
    str(DIAMOND_ROOT / "models" / "DiaMond" / "mri+pet" / "DiaMond_multi_split4_bestval.pt"),
)
DIAMOND_DEVICE = os.getenv("DIAMOND_DEVICE", "cuda")
DIAMOND_OUTPUT_DIR = Path(
    os.getenv("DIAMOND_OUTPUT_DIR", str(Path("data") / "diamond_outputs"))
)
