This is flo energy assignment.

## Setup
```
python3 -m venv .venv 

.venv/bin/pip install -e ".[dev]"

```

## Run

### Program
```
.venv/bin/python -m nem12_to_sql tests/samples/sample_nem12.csv -o out.sql

.venv/bin/python -m nem12_to_sql tests/samples/sample_nem12.csv -o out.sql --lenient

.venv/bin/python -m nem12_to_sql tests/samples/sample_nem12.csv -o out.sql --no-upsert

.venv/bin/python -m nem12_to_sql tests/samples/malformed_nem12.csv -o out.sql

.venv/bin/python -m nem12_to_sql tests/samples/malformed_nem12.csv -o out.sql --lenient

.venv/bin/python -m nem12_to_sql tests/samples/malformed_nem12.csv -o out.sql --lenient --no-upsert

```
### Unit tests
```
.venv/bin/pytest tests/test_parser.py -v 
.venv/bin/pytest tests/test_sql_writer.py -v

```
