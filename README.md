# Flo Energy Assignment (nem12-to-sql)

Streams a NEM12 meter data file and generates batched SQL `INSERT ... ON CONFLICT` statements for
the `meter_readings` table:

```sql
create table meter_readings (
  id uuid default gen_random_uuid() not null,
  "nmi" varchar(10) not null,
  "timestamp" timestamp not null,
  "consumption" numeric not null,
  constraint meter_readings_pk primary key (id),
  constraint meter_readings_unique_consumption unique ("nmi", "timestamp")
);
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Usage

```bash
# write SQL to a file
.venv/bin/python -m nem12_to_sql path/to/input.nem12 -o out.sql

# tolerate malformed 300 records (log + skip) instead of aborting the whole file
.venv/bin/python -m nem12_to_sql path/to/input.nem12 -o out.sql --lenient

# tune how many rows go into each multi-row INSERT statement (default 1000)
.venv/bin/python -m nem12_to_sql path/to/input.nem12 -o out.sql --batch-size 5000
```

**Run against the assessment's sample data:**

```bash
.venv/bin/python -m nem12_to_sql tests/fixtures/sample_nem12.csv -o out.sql

# print SQL to terminal instead of a file
.venv/bin/python -m nem12_to_sql tests/fixtures/sample_nem12.csv

# lenient mode
.venv/bin/python -m nem12_to_sql tests/fixtures/sample_nem12.csv -o out.sql --lenient

# plain INSERT (no upsert)
.venv/bin/python -m nem12_to_sql tests/fixtures/sample_nem12.csv -o out.sql --no-upsert
```

## Tests

```bash
.venv/bin/pytest -q
```

## Data Models

### 100 Record: The Envelope (Header)

This is the file cover sheet. It tells the system, _"Hey, I am a NEM12 file. Here is who sent me, who is supposed to get me, and the exact date and time I was created."_ It appears exctly once, at the very top of the file.

```
eg. 100,NEM12,200506081149,UNITEDDP,NEMMCO
```

### 200 Record: The Delivery Address & Meter Config (NMI Details)
This is important record, the parent container for a specific connection point or meter register. It specifies the property ID (NMI), which meter or register we are talking about, what unit of measurement is being used (kWh), and how long the intervals are (30-minutes). This appears evry time the file switches to a new meter, a new register.

```
eg. 200,NEM1201009,E1E2,1,E1,N1,01009,kWh,30,20050610
```

### 300 Record: The Daily Log (Interval Data)
This is the actual data payload. This is the child of the 200 record. It says, _"For this specific date, here is a long string of numbers showing exactly how much electricity was used during every single interval of that day."_ (e.g., 48 numbers for 30-minute intervals). It also includes a quick "Quality Flag" (like 'A' for Actual or 'E' for Estimated data). One 300 record appears for every single day of data being provided under that specific 200 record.

```
eg. 300,20050301,0,0,0,0,0,0,0,0,0,0,0,0,0.461,0.810,0.568,1.234,1.353,1.507,1.344,1.773,0.848,1.271,0.895,1.327,1.013,1.793,0.988,0.985,0.876,0.555,0760,0.938,0.566,0.512,0.970,0.760,0.731,0.615,0.886,0.531,0.774,0.712,0.598,0670,0.587,0.657,0.345,0.231,A,,,20050310121004,20050310182204
```

### 400 Record: The Footnote (Interval Event)
This record represents the explanation for data issues. This is an optional child of the 300 record. This appears only when there is an anomaly, gap, or variable quality in the day's data that needs explaining.

```
eg. 400,32,48,E52,,
```

### 500 Record: The Business Handshake (B2B Details)
This is transactional meta-data, represent B2B details. This is an optional business tracker. It links the data back to a specific commercial request. It says, "This data belongs to Market Transaction ID XXXXX, requested by Retailer Y."

```
eg. 500,O,S01009,20050310121004,
```

### 900 Record: The Stop Sign (End of Data)
This is file closer. It tells the parsing software, _"That's all! Do not look for any more data after this line."_ This appears exactly once, at the absolute bottom of the file.

```
eg. 900
```

## Outcome

The expected outcome is to parse the `200` and `300` records from NEM12 csv file and generate the insert statements for (nmi, timestamp, consumption). The solution must process large files.


## Design notes / assumptions

- Only `100`, `200`, `300`, `400`, `500`, `900` NEM12 record types are recognized. `400`/`500` are
  parsed enough to be skipped explicitly; any other leading record type raises rather than being
  silently ignored.
- Interval timestamps are the *end* of each interval (NEM12 convention): for a 30-minute interval
  the first value of a day is `00:30` and the 48th is `00:00` of the following day.
- `nmi` and `timestamp` are unique together in the schema, but a real NEM12 file can carry multiple
  `200` blocks for the same NMI (different registers/channels, e.g. E1/E2). The generated SQL
  therefore upserts (`ON CONFLICT (nmi, "timestamp") DO UPDATE SET consumption = EXCLUDED.consumption`)
  rather than plain-inserting or silently dropping — see `WRITEUP.md` (Q3) for the rationale.
- `consumption` is parsed as `Decimal`, never `float`, to match the `numeric` column exactly and
  avoid binary floating-point rounding drift.
- The parser is a generator over the input file handle — it never loads the whole file into memory,
  so throughput scales with disk I/O, not RAM, regardless of file size.


## Implementation Details

- I built this as a streaming pipeline so it can handle files of any size without loading everything into memory — the parser reads the file line by line and yields readings one at a time, instead of building a big list upfront.

- The CLI layer only handles argument parsing and wiring things together; it doesn't know anything about the NEM12 format or SQL — that logic lives in the parser and writer modules, which keeps things testable and easy to reason about.

- The parser works like a small state machine: it tracks which NMI and interval length it's currently in (from the 200 record), then uses that context to expand each 300 record into individual timestamped meter readings.

- I added a lenient mode so that if one row of consumption data is malformed, you can choose to skip just that row and keep processing the rest of the file, instead of the whole import failing. Structural problems, like a reading with no NMI block before it, always fail though, because there's no safe way to guess what they belong to.

- On the output side, I batch the readings into multi-row INSERT statements instead of one INSERT per row, which is much cheaper for the database to execute, and the batch size is configurable.

- By default I generate upsert statements (ON CONFLICT DO UPDATE) so re-running the same file is safe and won't create duplicates, but there's a flag to turn that off if someone just wants plain inserts.

- In the main function, I only catch the errors I actually expect, like a missing file or a bad NEM12 record, and turn those into a clean error message and exit code; anything unexpected just crashes loudly instead of being hidden.


### Validations
- THe validation 
    - Rejects input file format other .csv file
    - Rejects malformed `200` records, eg. missing fields, invalid interval length, invalid NMI format.
    - Eejects malformed `300` records, eg. bad date, wrong value count, invalid consumption values).
    - The above supports in strict mode (default), OR tolerant mode (`--lenient`) with warnings only for malformed `300` records.
- `300` appears before any valid `200` (always fails, even in lenient mode).
- Duplicate `(nmi, timestamp)` rows are handled with upsert by default.
- context is reset on `500` (end-of-block marker).
- Invalid consumption tokens.
- Unrecognised record types raises error.
- Empty lines are trimmed/skipped.
- Interval length that doesn't evenly divide a day.


## Q1. Rationale for the technologies used

- I chose Python because - this is an I/O-bound, single-pass text-processing job, not a compute-heavy one, so Go/Java's raw speed advantage barely matters at this point, Python's generator-based streaming maps naturally onto "read a line, maybe emit a record" with far less code than hand-rolled Go channels or Java iterators.

- I kept it to Python 3.11's standard library only, no runtime dependencies at all. I parse lines by hand with `str.split` instead of the `csv` module, and use `dataclasses`, `datetime`/`timedelta`, `decimal.Decimal`, `argparse`, and `logging`. The file is just flat lines that need to be read one at a time and turned into a stream of readings, so a simple state machine over lines fits much better than pulling in pandas or an ORM — both of those nudge you toward loading more into memory than a single-pass job actually needs, and would add a dependency for no real benefit. Staying dependency-free also means anyone can run this tool wherever Python 3.11 is available, with no install or build step beyond the package itself.

- I used `Decimal` instead of `float` for consumption values, because the target database column is `numeric`. Regular binary floats can't represent a value like `0.461` exactly, and doing arithmetic on them repeatedly makes that error drift over time. `Decimal`, built directly from the string in the file, round-trips exactly into a SQL numeric literal, so there's no precision loss anywhere in the pipeline.

- For testing and code quality I used pytest, plus ruff and black for linting and formatting, but I made sure these are dev-only dependencies declared as an optional extra, so the actual shipped tool stays completely dependency-free.

- For the CLI I just used `argparse` and ran it as `python -m nem12_to_sql` — this is a single-command batch tool, so there's no need for a bigger CLI framework. Argparse already gives you `--help`, type coercion, and both short and long flags for free.

- For a timed, correctness-focused assignment, Python's lack of a build step and low syntactic overhead (no type declarations, no checked exceptions) means more time goes into handling edge cases like malformed records and batching, rather than fighting a compiler — though Go or Java would likely win on throughput if this became a long-running, high-volume service.


## Q2. What I'd do differently with more time

- The biggest gap: I generate SQL text, not load it. For production, I'd swap in a COPY-based or driver-level path (execute_values, real COPY) — much faster than INSERTs at volume. Scoped out here since the brief only asked for SQL generation.

- I'd widen NEM12 coverage: extend the implementation for 400, 500 records. Also, I would have improved the test coverage for existing implementation.

- Parallelism for very large files - the current design is single-threaded and I/O-bound, which is the right default (simple, correct, and disk speed is usually the real botteneck) — but for multi-GB files, sharding by NMI block across worker processes and merging output streams would cut wall-clock time on a multi-core box.

- Checkpointing / resumability - for very large files, if the process crashes or is killed mid-way, there's currently no way to resume from where it left off. I'd track progress (e.g. last successfully processed line number or NMI block) so a restart doesn't have to reprocess the whole file from scratch, or worse, double-insert already-written rows.

- Idempotent, transactional writes - right now each batch is its own INSERT ... ON CONFLICT statement, but there's no transaction wrapping the whole run. If the process dies halfway through writing output, you can end up with a partial file that's neither a clean success nor a clean failure. I'd wrap the whole output in an explicit transaction (or at least document that partial output must be discarded and rerun) so it's always all-or-nothing from the database's point of view.

- Poison-pill / dead-letter handling for bad records - --lenient just logs and drops malformed 300 records. For resiliency I'd want those dropped records captured somewhere durable (a dead-letter file or table) rather than only a log line, so nothing is silently lost and someone can go back and reconcile or reprocess them later.

- Observability setup - If this became a recurring ingestion job instead of an ad hoc CLI run, I'd add structured logging — row counts, error counts, per-NMI throughput, as JSON log lines — so we can see failures and volume anomalies in a dashboard instead of someone grepping stderr after the fact.

- Introduce CI/CD. I left it out because the assessment explicitly said no infra/deployment code, but for a real repo that's the obvious next step.


## Q3. Rationale for the design choices made

- Streaming over parse-then-process. NEM12 files can be very large, so loading the whole file into memory before writing SQL would scale poorly. Instead, `NEM12Parser.parse()` yields one `MeterReading` at a time as it reads line by line, and `generate_insert_statements()` buffers only a single batch before flushing to disk. Peak memory stays `O(batch_size)` rather than `O(file size)`, which keeps the process viable on multi-GB inputs without needing a machine-sized RAM budget.

- Keep it simple with just three modules cli, parser, sql writer. This makes the design small, easy to understand, replacable. Make it easy for testing.

- Defaulting upsert (`ON CONFLICT ... DO UPDATE`) over plain insert or `DO NOTHING`. The schema's `UNIQUE(nmi, timestamp)` collides when the same NMI has multiple registers (`E1`/`E2`) landing on the same timestamps. Upsert also makes re-processing a corrected file idempotent, instead of requiring a delete-and-reload or a hard failure on duplicate keys.

- Strict by default to fail fast, `--lenient` opt-in for `300` interval-count mismatches only. Billing-adjacent data shouldn't silently swallow errors by default, but one bad line shouldn't block a whole batch either. Structural errors (unknown record type, orphan `300`, invalid NMI) always raise regardless — those mean the file isn't valid NEM12.

- Batched multi-row `INSERT`s (1000 rows/statement by default), not one per row. Keeps the brief's "generates insert statements" literally true while cutting statement count ~1000x. Batch size is configurable since the right value depends on the target system.

- Raw SQL text output, not a live DB connection, per the brief. The NMI is the only file content that reaches that text, so it's validated against `^[A-Z0-9]{1,10}$` and quote-escaped defensively — cheap insurance against a malformed upstream file injecting SQL.

- `id` omitted from generated `INSERT`s — the table already defaults it to `gen_random_uuid()`, so inventing primary keys would just be dead weight.
