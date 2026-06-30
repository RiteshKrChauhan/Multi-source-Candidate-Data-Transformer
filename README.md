# Candidate Profile Aggregation Pipeline

A production-oriented Python 3.11+ pipeline that ingests heterogeneous candidate records, maps them to one canonical model, normalizes and deduplicates identities, merges conflicting data with explainable rules, scores confidence, preserves field-level provenance, projects configurable output, and validates the result against JSON Schema.

## Highlights

- Structured ingestion: CSV and flexible ATS JSON (single object, list, or `candidates`/`results` wrapper).
- Unstructured ingestion: resume TXT and text-based PDF with isolated regex/section extraction.
- Canonical Pydantic models with strict extra-field rejection.
- E.164 phones, lowercase validated emails, `YYYY-MM` dates, ISO-3166 alpha-2 countries, canonical skill aliases, and normalized URLs.
- Identity matching in priority order: email, phone, LinkedIn/GitHub, then RapidFuzz name similarity.
- Conflict resolution priority: Resume > LinkedIn > ATS > CSV > GitHub; the longest valid name wins, collections are stable unions, and experience/education entries are coalesced.
- Per-field and weighted overall confidence with source reliability, extraction quality, and cross-source corroboration.
- Field-level provenance containing source, source record ID, extraction method, original field, and original value.
- Runtime field selection, renaming, confidence/provenance switches, normalization, and `null`/`omit`/`error` missing-value policies.
- Canonical and projected output validation using JSON Schema Draft 2020-12.
- Deterministic UUIDv5 IDs, deterministic ordering, fault isolation, structured logging, and atomic output writes.

## Architecture

```text
CSV / ATS JSON / Resume TXT-PDF
              │
      independent parsers
              │ SourceRecord
              ▼
       canonical mapper ── normalization
              │ CandidateProfile
              ▼
       matcher → merger → confidence
              │
              ├── canonical schema validation
              ▼
       runtime projection
              │
              ├── projected schema validation
              ▼
          atomic JSON output
```

The layers are intentionally decoupled. Parsers produce `SourceRecord`, never canonical models. Mapping owns source-field aliases. Matching, merging, and confidence operate only on canonical profiles. Projection does not parse or merge. Validation accepts plain JSON-compatible data.

## Project layout

```text
parsers/       Source-specific readers and extraction
models/        Source and canonical Pydantic models
mapper/        Source-to-canonical field mapping
normalizer/    Email, phone, date, country, skill, URL rules
merge/         Identity matching and conflict resolution
confidence/    Field and overall confidence scoring
projection/    Runtime output shaping
validator/     JSON Schema and validation service
config/        Projection models and example configurations
cli/           CLI implementation
utils/         Atomic JSON output helper
input/         Runnable sample inputs
output/        Generated sample output
tests/         Unit and end-to-end tests
```

## Setup

Follow these steps exactly to get the project running from scratch:

**1. Clone the repository**
```bash
git clone <your-repo-url>
cd multi-source-candidate-transformer
```

**2. Create and activate a virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

**3. Install all dependencies**
```bash
pip install -r requirements-dev.txt
```

Python 3.11 and 3.12 are supported by the declared dependency ranges.

## Run

**Default output (all fields, full provenance + confidence):**
```bash
python main.py --csv input/candidates.csv --resume input/resume.pdf --ats input/ats.json --config config/default.json --output output/candidates.json
```

**Compact custom-config output (renamed fields, no metadata, omit-missing policy):**
```bash
python main.py --csv input/candidates.csv --resume input/resume.pdf --ats input/ats.json --config config/compact.json --output output/compact_output.json
```

Each input flag is repeatable — supply as many files as needed. National phone numbers are parsed against the US region by default:

```bash
python main.py --csv input/india.csv --phone-region IN --output output/india.json
```

Full CLI reference:

```text
--csv PATH            CSV input; repeatable
--resume PATH         TXT or PDF resume; repeatable
--ats PATH            ATS JSON input; repeatable
--config PATH         Projection configuration JSON; defaults to all fields
--output PATH         Required JSON destination
--phone-region CC     Region used to interpret national phone numbers (default: US)
--name-threshold N    RapidFuzz fuzzy-name threshold 0-100 (default: 90)
--log-level LEVEL     DEBUG, INFO, WARNING, or ERROR (default: INFO)
```

A malformed input file is logged and skipped; other files continue to be processed. The process exits non-zero if no record can be loaded, mapping/projection fails globally, schema validation fails, or the output file cannot be written.

## Sample Output

Running the default command above on the three bundled sample inputs (`input/candidates.csv`, `input/resume.txt`, `input/ats.json`) produces `output/candidates.json` with **2 merged canonical profiles**.

The three sources for Ada Lovelace (CSV row, ATS JSON record, and resume TXT) are automatically detected as the same person via shared email and phone, merged under one record, and scored:

```json
[
  {
    "candidate_id": "cand_3f1d6d02d39e5fed89d78dd7777af45f",
    "full_name": "Ada Byron Lovelace",
    "emails": ["ada@example.com"],
    "phones": ["+14155552671"],
    "location": { "city": "San Francisco", "region": null, "country": "US" },
    "links": {
      "linkedin": "https://linkedin.com/in/ada-lovelace",
      "github": "https://github.com/ada-lovelace",
      "portfolio": null
    },
    "headline": "Senior software engineer building dependable data and machine learning systems.",
    "years_experience": 8.0,
    "skills": ["Python", "C++", "React", "AWS", "Machine Learning", "JavaScript"],
    "experience": [
      { "company": "Analytical Engines Inc.", "title": "Senior Software Engineer",
        "start_date": "2018-01", "end_date": null, "description": "Built reliable data platforms." }
    ],
    "education": [
      { "institution": "University of London", "degree": "BSc",
        "field_of_study": "Mathematics", "start_date": null, "end_date": "2015-06" }
    ],
    "overall_confidence": 0.983,
    "confidence": { "full_name": 1.0, "emails": 1.0, "phones": 1.0, "skills": 1.0, "..." : "..." }
  },
  {
    "candidate_id": "cand_7cbe7f876dbb5bb59800e674d9866df9",
    "full_name": "Grace Hopper",
    "emails": ["grace@example.org"],
    "phones": ["+12025550187"],
    "location": { "city": "Arlington", "region": null, "country": "US" },
    "headline": "Computer Scientist",
    "years_experience": 12.0,
    "skills": ["Python", "PostgreSQL"],
    "overall_confidence": 0.813
  }
]
```

The full output including all provenance records is in [`output/candidates.json`](output/candidates.json). The compact renamed output (using `config/compact.json`) is in [`output/compact_output.json`](output/compact_output.json).

## Projection configuration

`config/default.json` emits the full representation. `config/compact.json` demonstrates a minimal renamed output.

```json
{
  "fields": ["candidate_id", "full_name", "emails", "skills", "overall_confidence"],
  "rename": {"candidate_id": "id", "full_name": "name", "overall_confidence": "score"},
  "include_confidence": false,
  "include_provenance": false,
  "apply_normalization": true,
  "missing_value_policy": "omit"
}
```

`fields` uses canonical top-level names. Renaming occurs after selection. When enabled, `confidence` and `provenance` are added even if absent from `fields`. Missing values include `null`, empty strings, empty lists, empty objects, and models whose members are all empty.

Canonical values are always normalized before identity matching, as required for safe deduplication. `apply_normalization` controls the projection layer's final idempotent normalization pass; disabling it does not restore unsafe raw identifiers. Original source values remain available in provenance.

## Canonical model and rules

The output schema is `validator/candidate_schema.json`. The canonical profile contains:

```text
candidate_id, full_name, emails, phones, location, links, headline,
years_experience, skills, experience, education, provenance,
confidence, overall_confidence
```

Matching first checks exact normalized identifiers. Fuzzy names are considered only when no strong identifiers conflict. This reduces false-positive merges for common names. Matching groups use union-find, so transitive duplicate relationships are resolved in one deterministic component.

Stable candidate IDs are UUIDv5 hashes of sorted normalized identity keys. Re-running unchanged inputs—or supplying those inputs in a different order—produces the same IDs and output ordering.

Confidence is a bounded `[0, 1]` score. It combines the strongest contributing source, extraction method quality, corroborating source count, and collection completeness. Overall confidence is a weighted mean over populated business fields only; missing fields do not artificially drag the score to zero. The weights and reliability tables are explicit in `confidence/scorer.py`.

## Extend

To add a source, implement `BaseParser.parse()` and return `SourceRecord` objects, then register the parser in `CandidatePipeline`. Add source aliases to `CanonicalMapper` only when its field vocabulary differs. Parsing remains independent of merge policy.

Skill aliases are centralized in `DataNormalizer.SKILL_ALIASES`. For a larger taxonomy, replace that dictionary with an injected repository while keeping the same `skill()` boundary.

## Tests

**Run the full test suite:**
```bash
python -m pytest
```

**Run with coverage report:**
```bash
python -m pytest --cov=. --cov-report=term-missing
```

The suite is split across 6 files:

| File | What it covers |
|---|---|
| `tests/test_normalizer.py` | Email, phone, date, country, skill normalization; deduplication after normalization |
| `tests/test_parsers_and_mapper.py` | CSV parser + canonical mapping; ATS nested JSON fields; resume TXT heuristic extraction (name, email, skills, experience, education) |
| `tests/test_match_and_merge.py` | Identifier match priority (email > phone > link); conflict guard preventing false-positive fuzzy merges; merger source-priority rules; deterministic UUIDv5 candidate IDs |
| `tests/test_projection_validation.py` | Field selection, rename, metadata toggle; `null` / `omit` / `error` missing-value policies; projected JSON Schema validation |
| `tests/test_pipeline.py` | End-to-end multi-source merge determinism; graceful skipping of malformed input files; clear error on zero valid inputs |
| `tests/test_cli.py` | CLI atomic JSON write to nested output directory; CLI exit code 2 when no input is provided |

## Operational notes

- PDF support extracts embedded text; scanned/image-only resumes need an OCR parser extension.
- Input files are processed independently, so one corrupt file does not poison a batch.
- Output is written to a temporary sibling file, flushed, and atomically replaced.
- Logs go to stderr; JSON output remains clean.
- The in-memory matcher is intentionally straightforward and deterministic. At very large scale, block candidates by normalized email/phone/link and fuzzy-match only the remaining name buckets while retaining the same matcher interface.
