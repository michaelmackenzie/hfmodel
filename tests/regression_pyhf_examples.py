#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


def _run(command, cwd):
    print("+", " ".join(command))
    proc = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"Command failed with code {proc.returncode}: {' '.join(command)}")
    return proc.stdout


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _assert_keys(payload, keys, label):
    missing = [key for key in keys if key not in payload]
    if missing:
        raise AssertionError(f"{label}: missing keys {missing}")


def main():
    repo = Path(__file__).resolve().parents[1]
    examples = repo / "examples"
    cli = [sys.executable, "bin/hfmodel"]

    _run([sys.executable, "simple_shapes.py"], cwd=examples)
    _run([sys.executable, "simple_shapes_two_channel.py"], cwd=examples)

    build_targets = [
        ("examples/simple_shapes_card.txt", "examples/simple_shapes_model_regtest.json"),
        ("examples/counting_categories.txt", "examples/counting_categories_model_regtest.json"),
        ("examples/simple_shapes_two_channel_card.txt", "examples/simple_shapes_two_channel_model_regtest.json"),
    ]

    for card, output_model in build_targets:
        _run(cli + ["build", card, output_model], cwd=repo)
        model_payload = _load_json(repo / output_model)
        _assert_keys(model_payload, ["format", "workspace", "fit_metadata", "card"], f"build output {output_model}")

    analyze_targets = [
        ("examples/simple_shapes_model_regtest.json", "examples/analysis_simple_regtest.json"),
        ("examples/counting_categories_model_regtest.json", "examples/analysis_counting_regtest.json"),
        ("examples/simple_shapes_two_channel_model_regtest.json", "examples/analysis_two_channel_regtest.json"),
    ]

    for model_file, output_snapshot in analyze_targets:
        _run(
            cli
            + [
                "analyze",
                "--model-file",
                model_file,
                "--toys",
                "1",
                "--cls",
                "0.05",
                "--cls-scan-points",
                "7",
                "--output",
                output_snapshot,
            ],
            cwd=repo,
        )

        snapshot = _load_json(repo / output_snapshot)
        _assert_keys(
            snapshot,
            ["format", "workspace", "model_metadata", "observed_counts_by_channel", "summaries", "config"],
            f"analysis snapshot {output_snapshot}",
        )

        summaries = snapshot.get("summaries", [])
        if len(summaries) != 1:
            raise AssertionError(f"{output_snapshot}: expected exactly one summary entry")
        summary = summaries[0]
        _assert_keys(
            summary,
            ["dataset_id", "valid", "poi_name", "poi_fit", "poi_unc_hesse", "fit_params", "dataset_plot"],
            f"summary in {output_snapshot}",
        )

        report_file = Path(str(output_snapshot).replace(".json", "_ensemble_report.json"))
        report = _load_json(repo / report_file)
        _assert_keys(report, ["n_datasets", "runtime", "fit_quality", "poi_name"], f"ensemble report {report_file}")

    # Seed reproducibility check: same seed should reproduce identical toy fit sequence.
    _run(
        cli
        + [
            "analyze",
            "--model-file",
            "examples/simple_shapes_model_regtest.json",
            "--toys",
            "5",
            "--seed",
            "777",
            "--output",
            "examples/analysis_seed_regtest_a.json",
        ],
        cwd=repo,
    )
    _run(
        cli
        + [
            "analyze",
            "--model-file",
            "examples/simple_shapes_model_regtest.json",
            "--toys",
            "5",
            "--seed",
            "777",
            "--output",
            "examples/analysis_seed_regtest_b.json",
        ],
        cwd=repo,
    )
    snap_a = _load_json(repo / "examples/analysis_seed_regtest_a.json")
    snap_b = _load_json(repo / "examples/analysis_seed_regtest_b.json")
    fits_a = [item.get("poi_fit") for item in snap_a.get("summaries", [])]
    fits_b = [item.get("poi_fit") for item in snap_b.get("summaries", [])]
    if fits_a != fits_b:
        raise AssertionError("Seed reproducibility check failed: poi_fit sequences differ")

    # Feldman-Cousins smoke test with small settings for runtime.
    _run(
        cli
        + [
            "analyze",
            "--model-file",
            "examples/simple_shapes_model_regtest.json",
            "--toys",
            "1",
            "--feldman-cousins",
            "0.1",
            "--fc-scan-points",
            "5",
            "--fc-toys",
            "5",
            "--output",
            "examples/analysis_fc_regtest.json",
        ],
        cwd=repo,
    )
    fc_snapshot = _load_json(repo / "examples/analysis_fc_regtest.json")
    fc_summaries = fc_snapshot.get("summaries", [])
    if not fc_summaries:
        raise AssertionError("Feldman-Cousins snapshot missing summaries")
    fc_payload = fc_summaries[0].get("feldman_cousins")
    if not isinstance(fc_payload, dict):
        raise AssertionError("Feldman-Cousins payload missing from summary")
    if fc_payload.get("fc_status") not in ("ok", "no-accepted-points", "failed"):
        raise AssertionError(f"Unexpected Feldman-Cousins status: {fc_payload.get('fc_status')}")

    print("All pyhf regression checks passed.")


if __name__ == "__main__":
    main()
