import csv

import pytest

from cwt_quant.sentiment_eval import evaluate


def write_split(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["text", "label"])
        writer.writerows(rows)
    return path


def test_train_majority_and_lexical_use_same_validation_rows(tmp_path):
    train = write_split(tmp_path / "train.csv", [
        ("Risk builds", 0), ("Report published", 2), ("Meeting scheduled", 2),
    ])
    val = write_split(tmp_path / "valid.csv", [
        ("bearish", 0), ("bullish", 1), ("report grew", 1), ("report dated", 2),
    ])
    result = evaluate(train, val)
    assert result["majority_label"] == "neutral"
    assert result["validation"]["evaluated_rows"] == 4
    assert result["lexical"]["accuracy"] == pytest.approx(.75)
    assert result["lexical"]["macro_f1"] == pytest.approx(7 / 9)
    assert result["lexical"]["confusion_matrix"] == [[1, 0, 0], [0, 1, 1], [0, 0, 1]]
    assert result["majority"]["accuracy"] == pytest.approx(.25)
    assert result["majority"]["macro_f1"] == pytest.approx(2 / 15)


def test_overlap_is_excluded_and_repeated_labels_are_counted_once(tmp_path):
    train = write_split(tmp_path / "train.csv", [("X bullish", 1), ("x  BULLISH ", 1)])
    val = write_split(tmp_path / "valid.csv", [
        (" X  bullish ", 1), ("weak", 0), ("WEAK", 0),
    ])
    result = evaluate(train, val)
    assert result["train"]["deduplicated_rows"] == 1
    assert result["validation"] == {
        **result["validation"], "raw_rows": 3, "deduplicated_rows": 2,
        "excluded_train_overlap": 1, "evaluated_rows": 1,
    }
    assert result["lexical"]["accuracy"] == 1


@pytest.mark.parametrize("rows", [
    [("   ", 1)], [("label outside schema", 3)], [("conflict", 0), ("CONFLICT", 1)],
])
def test_malformed_or_conflicting_labels_fail_closed(tmp_path, rows):
    train = write_split(tmp_path / "train.csv", [("strong", 1)])
    val = write_split(tmp_path / "valid.csv", rows)
    with pytest.raises(ValueError):
        evaluate(train, val)


def test_checksum_mismatch_fails_closed(tmp_path):
    train = write_split(tmp_path / "train.csv", [("strong", 1)])
    val = write_split(tmp_path / "valid.csv", [("weak", 0)])
    with pytest.raises(ValueError, match="SHA-256"):
        evaluate(train, val, expected_sha256=("0" * 64, None))


def test_no_disjoint_validation_rows_fails_closed(tmp_path):
    train = write_split(tmp_path / "train.csv", [("strong", 1)])
    val = write_split(tmp_path / "valid.csv", [("STRONG", 1)])
    with pytest.raises(ValueError, match="No disjoint validation"):
        evaluate(train, val)
