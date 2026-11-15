"""Offline aggregate audit of the lexical scorer against published sentiment labels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from .features import lexical_sentiment

DATASET = "zeroshot/twitter-financial-news-sentiment"
REVISION = "ccbe24de388e287beb92dd393a335c376b350ac3"
TRAIN_SHA256 = "71aa99d0d37feced03c999ec23b5b25302c92f39d69b6acb0a37aa076c5420e8"
VALIDATION_SHA256 = "31ea8274c98b52212daa68f2fb962811bf1913c1efe51b99765c8e2311806de6"
LABELS = ("bearish", "bullish", "neutral")


def _load(path: Path, split: str, expected_hash: str | None) -> tuple[dict, dict]:
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if expected_hash is not None and digest != expected_hash:
        raise ValueError(f"{split} SHA-256 does not match the pinned source")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True)
        if next(reader, None) != ["text", "label"]:
            raise ValueError(f"{split} requires CSV fields text,label in that order")
        rows = {}
        raw_rows = 0
        for raw_rows, row in enumerate(reader, start=1):
            if len(row) != 2 or not row[0].strip() or row[1] not in {"0", "1", "2"}:
                raise ValueError(f"{split} data record {raw_rows} has invalid text or label")
            text, raw_label = row
            key = " ".join(text.casefold().split())
            label = int(raw_label)
            if key in rows and rows[key][1] != label:
                raise ValueError(f"{split} data record {raw_rows} has a conflicting duplicate label")
            rows.setdefault(key, (text, label))
    except (UnicodeDecodeError, csv.Error):
        raise ValueError(f"{split} is not a valid UTF-8 CSV") from None
    if not rows:
        raise ValueError(f"{split} contains no labelled observations")
    return rows, {"sha256": digest, "raw_rows": raw_rows, "deduplicated_rows": len(rows)}


def _metrics(actual: list[int], predictions: list[int]) -> dict:
    matrix = [[0 for _ in LABELS] for _ in LABELS]
    for label, prediction in zip(actual, predictions):
        matrix[label][prediction] += 1
    scores = {}
    for index, label in enumerate(LABELS):
        true_positive = matrix[index][index]
        support = sum(matrix[index])
        predicted = sum(row[index] for row in matrix)
        scores[label] = {
            "support": support,
            "predicted": predicted,
            "precision": true_positive / predicted if predicted else 0.0,
            "recall": true_positive / support if support else 0.0,
            "f1": 2 * true_positive / (support + predicted) if support + predicted else 0.0,
        }
    return {
        "accuracy": sum(matrix[i][i] for i in range(len(LABELS))) / len(actual),
        "macro_f1": sum(metrics["f1"] for metrics in scores.values()) / len(LABELS),
        "confusion_matrix": matrix,
        "classes": scores,
    }


def evaluate(
    train_path: Path,
    validation_path: Path,
    *,
    expected_sha256: tuple[str | None, str | None] = (None, None),
) -> dict:
    train, train_stats = _load(train_path, "Training split", expected_sha256[0])
    validation, valid_stats = _load(validation_path, "Validation split", expected_sha256[1])
    # Normalize text only for overlap handling. Score the originally published text.
    disjoint = [row for key, row in validation.items() if key not in train]
    if not disjoint:
        raise ValueError("No disjoint validation observations remain")
    train_count = Counter(label for _, label in train.values())
    majority = max(range(len(LABELS)), key=lambda i: (train_count[i], -i))
    actual, predictions = [], []
    for text, label in disjoint:
        score = lexical_sentiment(text)
        actual.append(label)
        predictions.append(0 if score < 0 else 1 if score > 0 else 2)
    return {
        "labels_confusion_order": list(LABELS),
        "duplicate_policy": "Casefold and collapse whitespace; drop within-split repeats and cross-split validation overlap.",
        "train": {
            **train_stats,
            "labels": {name: train_count[index] for index, name in enumerate(LABELS)},
        },
        "validation": {
            **valid_stats,
            "excluded_train_overlap": len(validation) - len(disjoint),
            "evaluated_rows": len(disjoint),
        },
        "majority_label": LABELS[majority],
        "lexical": _metrics(actual, predictions),
        "majority": _metrics(actual, [majority] * len(actual)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--validation", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = evaluate(
            args.train, args.validation, expected_sha256=(TRAIN_SHA256, VALIDATION_SHA256),
        )
    except OSError:
        parser.exit(2, "Could not read the local dataset split files.\n")
    except ValueError as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps({
        "dataset": DATASET,
        "revision": REVISION,
        "publisher_license": "MIT",
        "dataset_card": f"https://huggingface.co/datasets/{DATASET}/blob/{REVISION}/README.md",
        "scope": "Aggregate labelled-text classification only; no AAPL historical coverage or predictive performance evidence.",
        **result,
    }, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
