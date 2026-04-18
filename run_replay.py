#!/usr/bin/env python3
"""
run_replay.py — JailVax Replay Engine
======================================
Reads the "before" transcript files (crescendo_combined.json, fitd_combined.json,
gcg_combined.json) and replays every attack with the JailVax Z3 middleware active.

Produces "after" transcript files in the exact same JSON format so you can
directly compare before/after ASR.

Usage:
    python run_replay.py                          # Run all 283 attacks
    python run_replay.py --attack crescendo       # Only crescendo (48)
    python run_replay.py --attack fitd            # Only FITD (115)
    python run_replay.py --attack gcg             # Only GCG (120)
    python run_replay.py --resume                 # Resume from where we left off
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# ── Project paths ────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
ARCH_DIR    = BASE_DIR / "Full Architecture"
OUTPUT_DIR  = BASE_DIR / "transcripts_with_jailvax"

# Add project root to path for jailvax_verify import
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(ARCH_DIR))

# ── Import the attack modules ───────────────────────────────────────────────
# We import the actual attack functions directly rather than using subprocesses.
# This gives us better control and error handling.

def import_crescendo():
    """Import crescendo module."""
    spec_path = ARCH_DIR / "crescendo_attack.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("crescendo_attack", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def import_fitd():
    """Import FITD module."""
    spec_path = ARCH_DIR / "fitd_gemini.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("fitd_gemini", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def import_gcg():
    """Import GCG module."""
    spec_path = ARCH_DIR / "gcg_gemini.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("gcg_gemini", spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Progress tracker ─────────────────────────────────────────────────────────

PROGRESS_FILE = OUTPUT_DIR / "replay_progress.json"

def load_progress():
    """Load progress from disk to support resumption."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"completed": []}

def save_progress(progress):
    """Save progress to disk."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def make_run_key(attack_type, goal, target_model, attacker_model=""):
    """Create a unique key for deduplication / resume support."""
    return f"{attack_type}|{goal}|{target_model}|{attacker_model}"


# ── Crescendo replay ────────────────────────────────────────────────────────

def replay_crescendo(resume_keys=None):
    """Replay all crescendo attacks from crescendo_combined.json."""
    before_path = BASE_DIR / "crescendo_combined.json"
    if not before_path.exists():
        print("[!] crescendo_combined.json not found, skipping.")
        return []

    with open(before_path, "r") as f:
        before = json.load(f)

    # Extract unique (goal, attacker, target) combos from the before file
    runs = []
    for t in before["transcripts"]:
        runs.append({
            "goal":           t["goal"],
            "target_model":   t["target_model"],
            "attacker_model": t["attacker_model"],
        })

    print(f"\n{'='*70}")
    print(f"CRESCENDO REPLAY — {len(runs)} attacks to replay")
    print(f"{'='*70}")

    # Import the crescendo module
    cres = import_crescendo()
    cres.init_client()

    transcripts = []
    progress = load_progress()

    for i, run in enumerate(runs):
        key = make_run_key("crescendo", run["goal"], run["target_model"], run["attacker_model"])

        # Check if already completed (resume support)
        if resume_keys and key in resume_keys:
            # Try to load existing transcript
            safe = run["goal"][:30].replace(" ", "_").replace("/", "_")
            existing = OUTPUT_DIR / "crescendo" / f"crescendo_{safe}_{run['target_model']}_{run['attacker_model']}.json"
            if existing.exists():
                with open(existing, "r") as f:
                    transcripts.append(json.load(f))
                print(f"  [{i+1}/{len(runs)}] SKIPPED (already completed): {run['goal'][:50]}")
                continue

        print(f"\n[{i+1}/{len(runs)}] Crescendo | {run['attacker_model']} → {run['target_model']}")
        print(f"  Goal: {run['goal']}")

        try:
            transcript = cres.run_crescendo_attack(
                goal=run["goal"],
                target_model=run["target_model"],
                attacker_model=run["attacker_model"],
            )

            # Save individual transcript
            safe = run["goal"][:30].replace(" ", "_").replace("/", "_")
            out_file = OUTPUT_DIR / "crescendo" / f"crescendo_{safe}_{run['target_model']}_{run['attacker_model']}.json"
            with open(out_file, "w") as f:
                json.dump(transcript, f, indent=2)

            transcripts.append(transcript)
            progress["completed"].append(key)
            save_progress(progress)
            print(f"  → Saved to {out_file.name}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            traceback.print_exc()
            # Save a failure record
            transcripts.append({
                "attack_type": "crescendo",
                "goal": run["goal"],
                "target_model": run["target_model"],
                "attacker_model": run["attacker_model"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "error": str(e),
                "max_overall_score": 0,
                "num_turns": 0,
                "turns": [],
                "score_trajectories": {"harm": [], "topic_drift": [], "compliance": [], "specificity": []},
            })

        # Rate limit courtesy pause
        time.sleep(2)

    # Combine into crescendo_combined_jailvax.json (same format as original)
    combined = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_attacks": len(transcripts),
        "successful_attacks": sum(1 for t in transcripts if t.get("success")),
        "attack_pairs_used": before.get("attack_pairs_used", []),
        "goals_used": before.get("goals_used", []),
        "transcripts": transcripts,
    }
    out_combined = BASE_DIR / "crescendo_combined_jailvax.json"
    with open(out_combined, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"\n[+] Crescendo combined saved → {out_combined}")

    return transcripts


# ── FITD replay ──────────────────────────────────────────────────────────────

def replay_fitd(resume_keys=None):
    """Replay all FITD attacks from fitd_combined.json."""
    before_path = BASE_DIR / "fitd_combined.json"
    if not before_path.exists():
        print("[!] fitd_combined.json not found, skipping.")
        return []

    with open(before_path, "r") as f:
        before = json.load(f)

    # Extract unique (goal, target_model) combos — skip error-only entries
    runs = []
    for item in before:
        goal = item.get("goal", "")
        if not goal:
            continue
        # FITD before transcripts don't always have target_model — default to flash-lite
        target = item.get("target_model", "gemini-2.5-flash-lite")
        runs.append({"goal": goal, "target_model": target})

    print(f"\n{'='*70}")
    print(f"FITD REPLAY — {len(runs)} attacks to replay")
    print(f"{'='*70}")

    # Import FITD module
    fitd_mod = import_fitd()
    cfg = fitd_mod.setup_vertex()

    results = []
    progress = load_progress()

    for i, run in enumerate(runs):
        key = make_run_key("fitd", run["goal"], run["target_model"])

        if resume_keys and key in resume_keys:
            safe = run["goal"][:35].replace(" ", "_").replace("/", "-")
            existing = OUTPUT_DIR / "fitd" / f"fitd_{safe}_{run['target_model']}.json"
            if existing.exists():
                with open(existing, "r") as f:
                    data = json.load(f)
                # Extract summary for combined file
                n_turns = len(data.get("streams", [{}])[0].get("iterations", []))
                results.append({
                    "goal": run["goal"],
                    "success": data.get("success"),
                    "turns": n_turns,
                    "turns_to_success": data.get("queries_to_jailbreak"),
                    "target_model": run["target_model"],
                    "_full_transcript": data,
                })
                print(f"  [{i+1}/{len(runs)}] SKIPPED (already completed): {run['goal'][:50]}")
                continue

        print(f"\n[{i+1}/{len(runs)}] FITD | target: {run['target_model']}")
        print(f"  Goal: {run['goal']}")

        try:
            transcript = fitd_mod.run_fitd_attack(
                cfg=cfg,
                target_model=run["target_model"],
                goal=run["goal"],
                max_turns=8,
            )

            # Save individual transcript
            safe = run["goal"][:35].replace(" ", "_").replace("/", "-")
            out_file = OUTPUT_DIR / "fitd" / f"fitd_{safe}_{run['target_model']}.json"
            with open(out_file, "w") as f:
                json.dump(transcript, f, indent=2)

            n_turns = len(transcript.get("streams", [{}])[0].get("iterations", []))
            results.append({
                "goal": run["goal"],
                "success": transcript.get("success"),
                "turns": n_turns,
                "turns_to_success": transcript.get("queries_to_jailbreak"),
                "target_model": run["target_model"],
                "_full_transcript": transcript,
            })

            progress["completed"].append(key)
            save_progress(progress)
            print(f"  → Saved to {out_file.name}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            traceback.print_exc()
            results.append({
                "goal": run["goal"],
                "success": None,
                "turns": 0,
                "turns_to_success": None,
                "error": str(e),
                "target_model": run["target_model"],
            })

        time.sleep(2)

    # Combine — match the original fitd_combined.json format (list of summary dicts)
    combined = []
    for r in results:
        entry = {
            "goal": r["goal"],
            "success": r["success"],
            "turns": r["turns"],
            "turns_to_success": r["turns_to_success"],
            "target_model": r.get("target_model", "gemini-2.5-flash-lite"),
        }
        if "error" in r:
            entry["error"] = r["error"]
        combined.append(entry)

    out_combined = BASE_DIR / "fitd_combined_jailvax.json"
    with open(out_combined, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"\n[+] FITD combined saved → {out_combined}")

    # Also save the full transcripts
    full_transcripts = [r.get("_full_transcript") for r in results if "_full_transcript" in r]
    if full_transcripts:
        out_full = OUTPUT_DIR / "fitd" / "fitd_all_full_transcripts.json"
        with open(out_full, "w") as f:
            json.dump(full_transcripts, f, indent=2)

    return results


# ── GCG replay ───────────────────────────────────────────────────────────────

def replay_gcg(resume_keys=None):
    """Replay all GCG attacks from gcg_combined.json."""
    before_path = BASE_DIR / "gcg_combined.json"
    if not before_path.exists():
        print("[!] gcg_combined.json not found, skipping.")
        return []

    with open(before_path, "r") as f:
        before = json.load(f)

    runs = []
    for item in before:
        goal = item.get("goal", "")
        if not goal:
            continue
        target = item.get("target_model", "gemini-2.5-flash-lite")
        runs.append({"goal": goal, "target_model": target})

    print(f"\n{'='*70}")
    print(f"GCG REPLAY — {len(runs)} attacks to replay")
    print(f"{'='*70}")

    gcg_mod = import_gcg()
    cfg = gcg_mod.setup_vertex()

    results = []
    progress = load_progress()

    for i, run in enumerate(runs):
        key = make_run_key("gcg", run["goal"], run["target_model"])

        if resume_keys and key in resume_keys:
            safe = run["goal"][:35].replace(" ", "_").replace("/", "-")
            existing = OUTPUT_DIR / "gcg" / f"gcg_{safe}_{run['target_model']}.json"
            if existing.exists():
                with open(existing, "r") as f:
                    data = json.load(f)
                total_trials = sum(len(s.get("iterations", [])) for s in data.get("streams", []))
                results.append({
                    "goal": run["goal"],
                    "success": data.get("success"),
                    "trials": total_trials,
                    "turns_to_success": data.get("queries_to_jailbreak"),
                    "target_model": run["target_model"],
                    "_full_transcript": data,
                })
                print(f"  [{i+1}/{len(runs)}] SKIPPED (already completed): {run['goal'][:50]}")
                continue

        print(f"\n[{i+1}/{len(runs)}] GCG | target: {run['target_model']}")
        print(f"  Goal: {run['goal']}")

        try:
            transcript = gcg_mod.run_gcg_attack(
                cfg=cfg,
                target_model=run["target_model"],
                goal=run["goal"],
                strategy="diverse",
                stop_on_success=True,
            )

            safe = run["goal"][:35].replace(" ", "_").replace("/", "-")
            out_file = OUTPUT_DIR / "gcg" / f"gcg_{safe}_{run['target_model']}.json"
            with open(out_file, "w") as f:
                json.dump(transcript, f, indent=2)

            total_trials = sum(len(s.get("iterations", [])) for s in transcript.get("streams", []))
            results.append({
                "goal": run["goal"],
                "success": transcript.get("success"),
                "trials": total_trials,
                "turns_to_success": transcript.get("queries_to_jailbreak"),
                "target_model": run["target_model"],
                "_full_transcript": transcript,
            })

            progress["completed"].append(key)
            save_progress(progress)
            print(f"  → Saved to {out_file.name}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            traceback.print_exc()
            results.append({
                "goal": run["goal"],
                "success": None,
                "trials": 0,
                "turns_to_success": None,
                "error": str(e),
                "target_model": run["target_model"],
            })

        time.sleep(2)

    # Combine — match original gcg_combined.json format
    combined = []
    for r in results:
        entry = {
            "goal": r["goal"],
            "success": r["success"],
            "trials": r["trials"],
            "turns_to_success": r["turns_to_success"],
            "target_model": r.get("target_model", "gemini-2.5-flash-lite"),
        }
        if "error" in r:
            entry["error"] = r["error"]
        combined.append(entry)

    out_combined = BASE_DIR / "gcg_combined_jailvax.json"
    with open(out_combined, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"\n[+] GCG combined saved → {out_combined}")

    full_transcripts = [r.get("_full_transcript") for r in results if "_full_transcript" in r]
    if full_transcripts:
        out_full = OUTPUT_DIR / "gcg" / "gcg_all_full_transcripts.json"
        with open(out_full, "w") as f:
            json.dump(full_transcripts, f, indent=2)

    return results


# ── Summary printer ──────────────────────────────────────────────────────────

def print_comparison_summary():
    """Print before/after ASR comparison from the combined files."""
    print(f"\n{'='*70}")
    print(f"JAILVAX BEFORE / AFTER ASR COMPARISON")
    print(f"{'='*70}")
    print(f"{'Attack':<12} {'Before Total':<14} {'Before ASR':<12} {'After Total':<14} {'After ASR':<12} {'Δ ASR':<10}")
    print("-" * 70)

    for attack, before_file, after_file in [
        ("Crescendo", "crescendo_combined.json", "crescendo_combined_jailvax.json"),
        ("FITD",      "fitd_combined.json",      "fitd_combined_jailvax.json"),
        ("GCG",       "gcg_combined.json",        "gcg_combined_jailvax.json"),
    ]:
        bp = BASE_DIR / before_file
        ap = BASE_DIR / after_file

        if bp.exists():
            with open(bp, "r") as f:
                bd = json.load(f)
            if isinstance(bd, dict):  # crescendo format
                bt = bd["total_attacks"]
                bs = bd["successful_attacks"]
            else:  # fitd/gcg format (list)
                bt = len(bd)
                bs = sum(1 for i in bd if i.get("success") == True)
            b_asr = bs / bt * 100 if bt else 0
        else:
            bt, bs, b_asr = 0, 0, 0

        if ap.exists():
            with open(ap, "r") as f:
                ad = json.load(f)
            if isinstance(ad, dict):
                at = ad["total_attacks"]
                asuc = ad["successful_attacks"]
            else:
                at = len(ad)
                asuc = sum(1 for i in ad if i.get("success") == True)
            a_asr = asuc / at * 100 if at else 0
        else:
            at, asuc, a_asr = "—", "—", "—"

        if isinstance(a_asr, (int, float)):
            delta = f"{a_asr - b_asr:+.1f}%"
            a_asr_str = f"{a_asr:.1f}%"
        else:
            delta = "—"
            a_asr_str = "—"

        print(f"{attack:<12} {f'{bs}/{bt}':<14} {b_asr:.1f}%{'':>6} {f'{asuc}/{at}' if isinstance(at,int) else '—':<14} {a_asr_str:<12} {delta:<10}")

    print("=" * 70)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="JailVax Replay Engine")
    parser.add_argument("--attack", type=str, default=None,
                        choices=["crescendo", "fitd", "gcg"],
                        help="Run only a specific attack type (default: all)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from previously completed runs")
    args = parser.parse_args()

    start_time = datetime.now()

    print("=" * 70)
    print("JailVax Replay Engine")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Load progress for resume support
    resume_keys = None
    if args.resume:
        progress = load_progress()
        resume_keys = set(progress.get("completed", []))
        print(f"Resuming — {len(resume_keys)} runs already completed.")

    # Ensure output directories exist
    for d in ["crescendo", "fitd", "gcg"]:
        (OUTPUT_DIR / d).mkdir(parents=True, exist_ok=True)

    if args.attack is None or args.attack == "crescendo":
        replay_crescendo(resume_keys)

    if args.attack is None or args.attack == "fitd":
        replay_fitd(resume_keys)

    if args.attack is None or args.attack == "gcg":
        replay_gcg(resume_keys)

    # Print comparison
    print_comparison_summary()

    end_time = datetime.now()
    print(f"\nTotal runtime: {end_time - start_time}")
    print("Done! Run 'python generate_report.py' to generate the comparison .docx report.")


if __name__ == "__main__":
    main()
