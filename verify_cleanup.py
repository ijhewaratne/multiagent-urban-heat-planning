#!/usr/bin/env python3
"""Verify repository cleanup status."""

from pathlib import Path

REPO = Path(__file__).resolve().parent

checks = {
    "❌ Old UI removed": not (REPO / "src/branitz_heat_decision/ui/app.py").exists(),
    "❌ Checklists archived": not (REPO / "docs/checklist_feb.md").exists(),
}

print("Repository Cleanup Verification")
print("=" * 40)
for desc, result in checks.items():
    status = "PASS" if result else "FAIL"
    print(f"{desc}: {status}")

all_pass = all(checks.values())
print(f"\n{'✅ All checks passed!' if all_pass else '⚠️ Some checks failed'}")
