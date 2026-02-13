# sec-fetcher

Download SEC EDGAR filings with:
- simple file download mode
- tar source download + extract mode
- filtering by `ticker` or `cik`
- latest single filing mode

[![PyPI version](https://img.shields.io/pypi/v/sec-fetcher.svg)](https://pypi.org/project/sec-fetcher/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 📖 Documentation

| Link | Description |
|------|-------------|
| **[View documentation (GitHub Pages)](https://your-org.github.io/sec-fetcher/)** | Full docs: install, quickstart, CLI, form types, API reference. |
| **[docs/index.html](docs/index.html)** | Open in browser for local viewing. |

**Host the docs yourself:** Repo **Settings → Pages →** Deploy from branch **main**, folder **/docs**. See [docs/README.md](docs/README.md).

---

## Install

**Requires Python 3.10+.**

```bash
pip install sec-fetcher
```

With a virtual environment (recommended on PEP 668–managed systems):

```bash
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install sec-fetcher
```

**Package:** `sec-fetcher` (PyPI) · **Module / CLI:** `secfetch` or `secfetcher`

---

## Quick start

### Python API

```python
from secfetch import download_quarter, download_year
from secfetcher import download_quarter_tar

# Simple: one quarter
download_quarter(
    year=2024, quarter=1, forms=["10-Q"],
    ticker="AAPL",
    data_dir="data",
)

# Tar: one quarter (downloads tar source, extracts, removes tar files)
download_quarter_tar(
    year=2024, quarter=1,
    forms=["10-Q"],
    ticker="AAPL",
    data_dir="data",
)

# Simple: full year
download_year(
    year=2024, forms=["8-K"], cik="320193", data_dir="data"
)
```

### Latest single filing mode

Supported in both `download_quarter` and `download_quarter_tar`.

Rule:
- omit `year`, `quarter`, and `forms`
- provide `ticker` or `cik`

```python
from secfetch import download_quarter
from secfetcher import download_quarter_tar

# Simple latest
download_quarter(ticker="AAPL")
download_quarter(cik="320193")

# Tar latest
download_quarter_tar(ticker="AAPL")
download_quarter_tar(cik="320193")
```

### CLI

```bash
secfetch quarter --year 2024 --quarter 1 --forms 10-Q --ticker AAPL --data-dir data
secfetch year --year 2024 --forms 8-K --cik 320193 --data-dir data
python -m secfetch --help
```

---

## SEC User-Agent (required)

The SEC expects a descriptive User-Agent with contact info. Set it via environment variable or pass `user_agent` in code/CLI.

```bash
export SEC_USER_AGENT="Your Name or Company contact@example.com"
```

---

## Form type allowlist

Only SEC form types from the allowlist are accepted (e.g. `10-Q`, `10-K`, `8-K`). If `data/config/form_types.json` exists, it is used; otherwise packaged defaults are used.

---

## Output layout

```
data/
  index/master/<year>/QTR<n>/    master index cache
  filings/<form>/<group>/<accession>/  downloaded files
  _state/manifest.json
```

`<group>` is usually CIK.  
If a single `ticker` or single `cik` filter is provided, that identifier may be used as group folder.

---

## Important defaults

- progress display: enabled by default
- tar mode concurrency: `20`
- tar mode extraction: `True` (tar files removed after extraction)
- form types:
  - uses `data/config/form_types.json` only if it already exists
  - otherwise uses packaged defaults

---

## Development

```bash
git clone https://github.com/your-org/sec-fetcher.git && cd sec-fetcher
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

---

## Publishing (PyPI)

Releases are published via GitHub Actions. Push a version tag (e.g. `v0.1.3`) or run the workflow from the Actions tab.

---

## License

[MIT](LICENSE)
