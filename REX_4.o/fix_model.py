#!/usr/bin/env python3
# ==============================================================================
# fix_model.py  -  REX 4.0   Model Path Finder & Fixer
# ==============================================================================
# Run this from your REX folder:
#   python fix_model.py
#
# It will:
#   1. Search your REX folder for the Vosk model
#   2. Tell you exactly what to fix
#   3. Optionally fix config.json automatically
# ==============================================================================

import sys
import json
from pathlib import Path

rex_root = Path(__file__).parent.resolve()

print("\n" + "=" * 70)
print("  REX 4.0 - Vosk Model Finder")
print("=" * 70)
print(f"\n  Searching in: {rex_root}\n")

# ── What a valid Vosk model folder looks like ─────────────────────────────────
VOSK_MARKERS = ["am", "conf", "graph"]   # sub-folders every model has

def is_vosk_model(path: Path) -> bool:
    """Return True if path looks like an unpacked Vosk model."""
    return path.is_dir() and all((path / m).exists() for m in VOSK_MARKERS)

# ── Search ────────────────────────────────────────────────────────────────────
candidates = []

# Check common names first
for name in ["model", "vosk-model", "vosk_model"]:
    p = rex_root / name
    if is_vosk_model(p):
        candidates.append(p)

# Then scan one level deep for any folder that looks like a model
for child in rex_root.iterdir():
    if child in candidates:
        continue
    if is_vosk_model(child):
        candidates.append(child)
    # Also check one level deeper (e.g. models/vosk-model-en-us-0.22)
    if child.is_dir():
        for grandchild in child.iterdir():
            if is_vosk_model(grandchild):
                candidates.append(grandchild)

# ── Report ────────────────────────────────────────────────────────────────────
if not candidates:
    print("  ✗  No Vosk model found!\n")
    print("  You need to download one:")
    print("  1. Go to:  https://alphacephei.com/vosk/models")
    print("  2. Download: vosk-model-small-en-us-0.15.zip  (50 MB, fastest)")
    print("     or:      vosk-model-en-us-0.22-lgraph.zip  (130 MB, better)")
    print("  3. Extract the zip into your REX folder")
    print(f"     So you get: {rex_root}\\model\\am\\")
    print("                                    \\conf\\")
    print("                                    \\graph\\")
    print("\n  Then run  python fix_model.py  again.\n")
    sys.exit(0)

print(f"  Found {len(candidates)} Vosk model(s):\n")
for i, c in enumerate(candidates, 1):
    # Work out the relative path from rex_root
    try:
        rel = c.relative_to(rex_root)
    except ValueError:
        rel = c
    print(f"  [{i}] {rel}  ({c})")

# ── Read current config ────────────────────────────────────────────────────────
config_path = rex_root / "config.json"
current_model = "model"   # default

if config_path.exists():
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        current_model = cfg.get("recognition", {}).get("model_path", "model")
        print(f"\n  config.json currently points to: \"{current_model}\"")
    except Exception as e:
        print(f"\n  Warning: could not read config.json: {e}")
else:
    print("\n  config.json not found – will be created by REX on first run.")

# ── Check if current config is already correct ────────────────────────────────
current_full = rex_root / current_model
if is_vosk_model(current_full):
    print(f"\n  ✓  config.json is already correct!")
    print(f"     Model path '{current_model}' is valid.")
    print("\n  Your Vosk model is set up correctly. Try running REX again:")
    print("     python REX_4.o.py\n")
    sys.exit(0)

# ── Pick the best candidate ───────────────────────────────────────────────────
best = candidates[0]
try:
    best_rel = str(best.relative_to(rex_root))
except ValueError:
    best_rel = str(best)

print(f"\n  ✗  Current path \"{current_model}\" is WRONG.")
print(f"  ✓  Should be:   \"{best_rel}\"")

# ── Offer to fix ──────────────────────────────────────────────────────────────
print(f"\n  Fix config.json automatically? (y/n): ", end="")
answer = input().strip().lower()

if answer == "y":
    # Read or create config
    if config_path.exists():
        with open(config_path) as f:
            cfg = json.load(f)
    else:
        cfg = {}

    if "recognition" not in cfg:
        cfg["recognition"] = {}
    cfg["recognition"]["model_path"] = best_rel

    # Backup old config
    if config_path.exists():
        backup = config_path.with_suffix(".json.bak")
        import shutil
        shutil.copy(config_path, backup)
        print(f"\n  Backed up old config to: {backup.name}")

    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"  ✓  config.json updated!  model_path = \"{best_rel}\"")
    print("\n  Now run REX:")
    print("     python REX_4.o.py\n")

else:
    print(f"\n  Manual fix: open config.json and set:")
    print(f'     "recognition": {{')
    print(f'       "model_path": "{best_rel}"')
    print(f'     }}')
    print()