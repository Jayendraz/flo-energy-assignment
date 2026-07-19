This is flo energy assignment.

## Setup
```
python3 -m venv .venv 

.venv/bin/pip install -e ".[dev]"

```

## Run

```
.venv/bin/python src/nem12_to_sql/cli.py tests/samples/sample_nem12.csv 

.venv/bin/python src/nem12_to_sql/cli.py tests/samples/sample_nem12.csv --lenient

```
