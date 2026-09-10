"""Start the local patient workspace: python run_dashboard.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from multi_agent.application.web import main

if __name__ == "__main__":
    main()
