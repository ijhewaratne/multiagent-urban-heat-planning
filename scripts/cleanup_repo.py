#!/usr/bin/env python3
"""
Repository cleanup for Fraunhofer handoff and PhD alignment.
Moves research artifacts to archive/, deletes obsolete files.
"""

import shutil
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[0]

# Files to DELETE (obsolete)
TO_DELETE = [
    "src/branitz_heat_decision/ui/app.py",           # Old tab-based UI
    "src/branitz_heat_decision/ui/app_old.py",       # Older version
    "src/branitz_heat_decision/agents/test_import",
    "src/branitz_heat_decision/agents/test_import.py"
]

# Files/Directories to ARCHIVE
TO_ARCHIVE = [
    "docs",
    "Legacy",
    "notebooks",
    "tests",
    "scripts/00_prepare_data.py"
]

# Patterns to GITIGNORE
TO_GITIGNORE = [
    "data/raw/",
    "data/processed/*.parquet",
    "results/",
    "cache/",
    "*.pickle",
    ".env",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    "*.egg-info/",
    "archive/"
]

def archive_files():
    """Move research artifacts to archive/ directory."""
    archive_dir = REPO_ROOT / "archive"
    archive_dir.mkdir(exist_ok=True)
    
    for pattern in TO_ARCHIVE:
        for path in REPO_ROOT.glob(pattern):
            if path.exists():
                # Preserve directory structure
                relative = path.relative_to(REPO_ROOT)
                dest = archive_dir / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                if path.is_dir():
                    shutil.copytree(path, dest, dirs_exist_ok=True)
                    shutil.rmtree(path)
                else:
                    shutil.move(path, dest)
                print(f"✓ Archived: {relative}")

def delete_obsolete():
    """Remove obsolete files."""
    for pattern in TO_DELETE:
        for path in REPO_ROOT.glob(pattern):
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                print(f"✓ Deleted: {path.relative_to(REPO_ROOT)}")

def update_gitignore():
    """Add cleanup patterns to .gitignore."""
    gitignore = REPO_ROOT / ".gitignore"
    
    existing = set()
    if gitignore.exists():
        existing = set(gitignore.read_text().splitlines())
    
    new_entries = [p for p in TO_GITIGNORE if p not in existing]
    
    if new_entries:
        with open(gitignore, "a") as f:
            f.write("\n# Cleanup additions\n")
            for pattern in new_entries:
                f.write(f"{pattern}\n")
        print(f"✓ Updated .gitignore with {len(new_entries)} patterns")

def verify_imports():
    """Quick check that core imports still work."""
    print("\nVerifying imports...")
    try:
        import sys
        sys.path.insert(0, str(REPO_ROOT / "src"))
        
        from branitz_heat_decision.agents import BranitzOrchestrator
        from branitz_heat_decision.nlu import classify_intent
        from branitz_heat_decision.adk.tools import run_cha_tool
        
        print("✓ All core imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def main():
    print("🔍 Starting repository cleanup...\n")
    
    archive_files()
    print()
    delete_obsolete()
    print()
    update_gitignore()
    print()
    
    if verify_imports():
        print("\n✅ Cleanup complete!")
        print(f"📁 Archive location: {REPO_ROOT / 'archive'}")
        print("\nNext steps:")
        print("  1. Review archive/ contents")
        print("  2. Run: git rm -r --cached archive/ data/results/ cache/ || true")
        print("  3. Commit: git add . && git commit -m 'Cleanup: archive research artifacts'")
    else:
        print("\n⚠️ Cleanup may have broken imports - review changes")

if __name__ == "__main__":
    main()
