import argparse
import json
from pathlib import Path
from workloads import build_suite, fingerprint


def main():
    parser = argparse.ArgumentParser(description="Create frozen pilot workloads, without labels")
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument("--horizon", type=int, default=3000)
    parser.add_argument("--out", default="workloads")
    args = parser.parse_args()
    out = Path(args.out)
    # New output directories prevent stale manifests or mixed generations.
    if out.exists():
        parser.error("Output already exists. Use --out with a new folder name.")
    cases = build_suite(args.seed, args.horizon)
    out.mkdir(parents=True)
    entries = []
    for c in cases:
        relative = f"{c['split']}/{c['task_set_id']}.json"
        dest = out / relative
        dest.parent.mkdir(exist_ok=True)
        dest.write_text(json.dumps(c, indent=2), encoding="utf-8")
        entries.append({"task_set_id": c["task_set_id"], "split": c["split"],
                        "path": relative, "workload_sha256": c["workload_sha256"]})
    counts = {s: sum(c["split"] == s for c in cases) for s in ("train", "validation", "test")}
    manifest = {"schema_version": 1, "generator_version": "pilot-v3",
                "master_seed": args.seed, "horizon_ms": args.horizon,
                "counts": counts, "suite_sha256": fingerprint(entries), "cases": entries,
                "purpose": "Pilot workloads only, not a state-label training dataset"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Created {len(cases)} workloads: train={counts['train']}, "
          f"validation={counts['validation']}, test={counts['test']}")
    print(f"Saved to {out}. No labels generated. Test workloads reserved.")


if __name__ == "__main__":
    main()
