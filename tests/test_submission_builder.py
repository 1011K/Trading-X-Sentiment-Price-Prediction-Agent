import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from cwt_quant.calendar import XNYSCalendar
from test_submission import END, snapshot

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "AAPL-evaluation.pdf", "latest-n0-n5.csv", "open-nowcast.csv",
    "post-close-forecasts.csv", "model_comparison.csv", "trade_ledger.csv",
    "research-figure.png", "outlook.md", "evaluation.md", "manifest.json",
    "x-coverage.json", "SHA256SUMS.txt",
}


def run_builder(*args):
    return subprocess.run(
        [sys.executable, "scripts/build_submission.py", *map(str, args)],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True,
    )


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize("with_x", [False, True], ids=["no-news-price-only", "eligible-x-test-only"])
def test_offline_submission_bundle(tmp_path, with_x):
    prices = tmp_path / "prices"
    prices.mkdir()
    bars = snapshot(prices / "AAPL.json")
    args = ["test-only", "--prices-dir", prices, "--news-snapshot", tmp_path / "missing.json"]
    if with_x:
        posts = [{
            "id": str(i + 1), "author": {"id": str(i + 1)}, "text": "$AAPL bullish",
            "created_at": f"{bar['date']}T15:00:00Z", "observed_at": f"{bar['date']}T15:01:00Z",
        } for i, bar in enumerate(bars[75:120])]
        export = tmp_path / "x.json"
        export.write_text(json.dumps(posts))
        attestation = tmp_path / "x-manifest.json"
        attestation.write_text(json.dumps({
            "platform": "X", "source_name": "Apify", "acquisition_method": "authorized_local_export",
            "intended_asset": "AAPL", "intended_purpose": "research", "access_authorized": True,
            "rights_basis": "Permission to use authored TEST ONLY records",
            "dataset_id": "testDataset1", "retrieved_at_utc": "2026-11-15T12:00:00+00:00",
            "row_count": len(posts), "export_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            "historical_text_point_in_time_verified": True,
        }))
        args += ["--x-export", export, "--x-manifest", attestation]
    out = tmp_path / "bundle"
    result = run_builder(*args, "--out", out)
    assert result.returncode == 0, result.stderr
    assert {p.name for p in out.iterdir()} == EXPECTED
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["build_mode"] == "test-only"
    assert manifest["historical_x_status"] == ("AVAILABLE" if with_x else "WITHHELD")
    assert manifest["x_eligible_rows"] == (45 if with_x else 0)
    assert manifest["news_snapshot_sha256"] is None
    assert manifest["prices"]["sha256"] == hashlib.sha256((prices / "AAPL.json").read_bytes()).hexdigest()
    assert manifest["observed_close"] == bars[-1]["close"]
    assert set(manifest["risk"]) == {r["model"] for r in rows(out / "model_comparison.csv")}
    assert ("price_sentiment" in manifest["risk"]) == with_x
    assert "TEST ONLY" in (out / "outlook.md").read_text()
    assert "capture was unavailable" in (out / "outlook.md").read_text()
    assert (out / "AAPL-evaluation.pdf").read_bytes().startswith(b"%PDF-")
    assert (out / "research-figure.png").read_bytes().startswith(b"\x89PNG")
    latest = rows(out / "latest-n0-n5.csv")
    opening = [r for r in rows(out / "open-nowcast.csv") if r["target_session"] == str(END)]
    forward = rows(out / "post-close-forecasts.csv")
    assert latest == [{k: r.get(k, "") for k in latest[0]} for r in opening + forward]
    targets = [END]
    for _ in range(5):
        targets.append(XNYSCalendar().next_trading_day(targets[-1]))
    assert all(r["target_session"] == str(targets[int(r["horizon"])]) for r in latest)
    sums = dict(line.split("  ", 1)[::-1] for line in (out / "SHA256SUMS.txt").read_text().splitlines())
    assert set(sums) == EXPECTED - {"SHA256SUMS.txt"}
    assert all(hashlib.sha256((out / name).read_bytes()).hexdigest() == digest for name, digest in sums.items())


def test_frozen_builder_refuses_replacement_prices(tmp_path):
    snapshot(tmp_path / "AAPL.json")
    out = tmp_path / "bundle"
    result = run_builder("frozen", "--prices-dir", tmp_path, "--out", out)
    assert result.returncode == 1
    assert "Frozen AAPL snapshot SHA-256 mismatch" in result.stderr
    assert not out.exists()


def test_assessment_issuer_context_stays_outside_models(tmp_path):
    snapshot(tmp_path / "AAPL.json")
    plain, issuer = tmp_path / "plain", tmp_path / "issuer"
    args = ["test-only", "--prices-dir", tmp_path]
    assert run_builder(*args, "--out", plain).returncode == 0
    result = run_builder(*args, "--issuer-context", "--out", issuer)
    assert result.returncode == 0, result.stderr
    meta = json.loads((issuer / "manifest.json").read_text())
    context = meta["current_news"]
    assert context["source"] == "Apple Newsroom"
    assert context["historical_features_eligible"] is False
    assert {a["published_date"] for a in context["articles"]} == {"2026-11-02", "2026-11-13"}
    assert context["collected_at_utc"].startswith("2026-11-16")
    issuer_file = ROOT / "docs" / "AAPL_ISSUER_CONTEXT.json"
    assert meta["news_snapshot_sha256"] == hashlib.sha256(issuer_file.read_bytes()).hexdigest()
    outlook = (issuer / "outlook.md").read_text()
    assert "Apple Newsroom" in outlook and "2026-11-16" in outlook and "2026-11-13" in outlook
    for name in ("latest-n0-n5.csv", "model_comparison.csv", "trade_ledger.csv", "research-figure.png"):
        assert (issuer / name).read_bytes() == (plain / name).read_bytes()
