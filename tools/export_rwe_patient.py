"""Export one patient with the settings in .env.rwe.local."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from multi_agent.ingestion.rwe_export import main

if __name__ == "__main__":
    raise SystemExit(main())
