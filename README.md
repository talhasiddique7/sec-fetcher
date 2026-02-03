# secfetcher

**Download SEC EDGAR filings by quarter or year** using the official SEC master index. Fetch only the form types and file types you need.

[![PyPI version](https://img.shields.io/pypi/v/secfetcher.svg)](https://pypi.org/project/secfetcher/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/secfetcher.svg)](https://pypi.org/project/secfetcher/)
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

```bash
pip install secfetcher
```

With a virtual environment (recommended on PEP 668–managed systems):

```bash
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install secfetcher
```

**Package:** `secfetcher` (PyPI) · **Module / CLI:** `secfetch` or `secfetcher`

---

## Quick start

### Python API

```python
from secfetcher import download_quarter, download_year

# One quarter
download_quarter(
    year=2024,
    quarter=3,
    forms=["10-Q", "10-K"],
    data_dir="data",
    file_types=[".xml", ".htm", ".html", ".pdf"],
)

# Full year (all quarters)
download_year(year=2024, forms=["8-K"], data_dir="data", file_types=[".htm", ".html"])
```

### CLI

```bash
secfetch quarter --year 2024 --quarter 3 --forms 10-Q 10-K --data-dir data --file-types .xml .htm .html .pdf
secfetch year --year 2024 --forms 8-K --data-dir data --file-types .htm .html
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

Only SEC form types from the allowlist are accepted (e.g. `10-Q`, `10-K`, `8-K`). The list lives in `data/config/form_types.json` (created on first run); edit it to add or remove types. The full list is in the [documentation](docs/index.html#form-types).

---

## Output layout

```
data/
  index/master/<year>/QTR<n>/   master index cache
  filings/<form>/<cik>/<accession>/   downloaded files
  _state/manifest.json
```

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

Releases are published via GitHub Actions. Push a version tag (e.g. `v0.1.1`) or run the workflow from the Actions tab.

---

## License

[MIT](LICENSE)
