import logging
from pathlib import Path

from nem12_to_sql.cli import main

GOOD_FIXTURE = Path(__file__).parent / "fixtures" / "sample_nem12.csv"
BAD_FIXTURE = Path(__file__).parent / "fixtures" / "malformed_nem12.csv"

# ---------- Tests Functions ---------- #

def test_successful_run_against_sample_fixture(tmp_path, caplog):
    # Arrange
    out_path = tmp_path / "out.sql"
    # Action
    with caplog.at_level(logging.INFO):
        exit_code = main([str(GOOD_FIXTURE), "-o", str(out_path)])
    # Assert
    assert exit_code == 0
    assert "wrote 384 rows" in caplog.text
    assert out_path.read_text().count("INSERT INTO meter_readings") == 1


def test_strict_mode_exits_with_error_and_reports_line(tmp_path, caplog):
    # Arrange
    out_path = tmp_path / "out.sql"
    # Action
    with caplog.at_level(logging.INFO):
        exit_code = main([str(BAD_FIXTURE), "-o", str(out_path)])
    # Assert
    assert exit_code == 1
    assert "line 3" in caplog.text
    assert "expected 48 interval values, found 3" in caplog.text


def test_lenient_mode_skips_bad_record_and_keeps_good_one(tmp_path, caplog):
    # Arrange
    out_path = tmp_path / "out.sql"
    # Action
    with caplog.at_level(logging.INFO):
        exit_code = main([str(BAD_FIXTURE), "-o", str(out_path), "--lenient"])
    # Assert
    assert exit_code == 0
    assert "skipping malformed 300 record at line 3" in caplog.text
    assert "wrote 48 rows" in caplog.text  # only the second, well-formed 300 record survives

    sql = out_path.read_text()
    row_lines = [line for line in sql.splitlines() if line.strip().startswith("(")]
    assert len(row_lines) == 48
    assert "NEM1201009" in sql


def test_non_csv_input_file_exits_nonzero_and_reports_error(tmp_path, caplog):
    # Arrange
    input_path = tmp_path / "sample.nem12"
    input_path.write_text("100,NEM12\n", encoding="utf-8")
    out_path = tmp_path / "out.sql"
    # Action
    with caplog.at_level(logging.INFO):
        exit_code = main([str(input_path), "-o", str(out_path)])
    # Assert
    assert exit_code == 1
    assert f"input file must be a .csv file: {input_path}" in caplog.text
    assert not out_path.exists()


def test_missing_input_file_exits_nonzero_and_reports_error(tmp_path, caplog):
    # Arrange
    missing_input = tmp_path / "does_not_exist.csv"
    out_path = tmp_path / "out.sql"
    # Action
    with caplog.at_level(logging.INFO):
        exit_code = main([str(missing_input), "-o", str(out_path)])
    # Assert
    assert exit_code == 1
    assert f"input file not found: {missing_input}" in caplog.text
    assert not out_path.exists()
