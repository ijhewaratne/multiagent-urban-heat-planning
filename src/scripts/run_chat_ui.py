#!/usr/bin/env python3
"""
Launch the conversational UI (no street selection required).

Usage:
    PYTHONPATH=src python src/scripts/run_chat_ui.py

Or from project root:
    streamlit run src/branitz_heat_decision/ui/app_conversational.py
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

if __name__ == "__main__":
    import streamlit.web.cli as stcli

    app_path = project_root / "src" / "branitz_heat_decision" / "ui" / "app_conversational.py"
    sys.argv = ["streamlit", "run", str(app_path)]
    sys.exit(stcli.main())
