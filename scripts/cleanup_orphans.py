import os
import shutil
from pathlib import Path

root = Path(r"c:\Users\Matías Riquelme\Desktop\Proyectos documentados\Slingshot_Trading")
target_tests = root / "scripts" / "tests"
target_tmp = root / "tmp"

target_tests.mkdir(parents=True, exist_ok=True)
target_tmp.mkdir(parents=True, exist_ok=True)

migrated_tests = []
migrated_tmps = []

for filepath in root.rglob("*.py"):
    # Ignorar carpetas .venv y node_modules y las de destino
    if ".venv" in filepath.parts or "node_modules" in filepath.parts:
        continue
        
    if filepath.name.startswith("test_") and filepath.parent != target_tests:
        dest = target_tests / filepath.name
        shutil.move(str(filepath), str(dest))
        migrated_tests.append(filepath.name)
        
    elif filepath.name.startswith("tmp_") and filepath.parent != target_tmp:
        dest = target_tmp / filepath.name
        shutil.move(str(filepath), str(dest))
        migrated_tmps.append(filepath.name)

# Cleanup
engine_tests = root / "engine" / "tests"
if engine_tests.exists() and not any(engine_tests.iterdir()):
    engine_tests.rmdir()

# Clean other tmp residues in root
for ext in ["*.txt", "*.json", "*.yaml"]:
    for f in root.glob(ext):
        if f.name in ["package.json", "tsconfig.json", "package-lock.json", ".eslintrc.json"]:
            continue # Preserve node files
        dest = target_tmp / f.name
        shutil.move(str(f), str(dest))
        migrated_tmps.append(f.name)

print(f"Migrated Tests: {len(migrated_tests)}")
for t in migrated_tests: print(" -", t)
print(f"Migrated Tmp/Residues: {len(migrated_tmps)}")
for t in migrated_tmps: print(" -", t)
