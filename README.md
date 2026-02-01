# secfetcher

Download SEC EDGAR filings by **quarter** or **year** using the official SEC **master index** as the
source of truth. `secfetcher` downloads each filing’s EDGAR folder and saves only the file types you
request.

- **PyPI package name**: `secfetcher`
- **Python module / CLI name**: `secfetch`

## Install

```bash
python -m pip install secfetcher
```

If your system Python is “externally managed” (PEP 668), install into a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install secfetcher
```

## Required: SEC User-Agent

The SEC requires a descriptive User-Agent string with contact information.

Set it via environment variable:

```bash
export SEC_USER_AGENT="Your Name or Company contact@example.com"
```

You can also pass a user-agent explicitly in code (if the API you call supports it).

## Quickstart (Python API)

### Download one quarter

```python
from secfetch import download_quarter

download_quarter(
    year=2024,
    quarter=3,
    forms=["10-Q", "10-K"],
    data_dir="data",
    file_types=[".xml", ".htm", ".html", ".pdf"],
)
```

### Download a full year (all quarters)

```python
from secfetch import download_year

download_year(
    year=2024,
    forms=["8-K"],
    data_dir="data",
    file_types=[".htm", ".html"],
)
```

## CLI

```bash
secfetch quarter --year 2024 --quarter 3 --forms 10-Q 10-K --data-dir data --file-types .xml .htm .html .pdf
secfetch year --year 2024 --forms 8-K --data-dir data --file-types .htm .html
```

Module form also works:

```bash
python -m secfetch --help
```

## Form type allowlist (strict)

`secfetch` only accepts SEC form types listed in:

- `data/config/form_types.json` (auto-created on first run), sourced from
- `src/secfetch/resources/form_types.json` (packaged default)

Edit `data/config/form_types.json` to add or remove accepted form types.

## Output layout

```
data/
  index/
    master/
      2024/
        QTR3/
          master.idx
  filings/
    10-Q/
      0000320193/
        0000320193-24-000069/
          <downloaded files...>
  _state/
    manifest.json
```

## Index cache cleanup (per-quarter)

After a quarter finishes with **no errors**, `secfetch` deletes the cached master index for that
quarter under `data/index/master/<year>/QTR<q>/`.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"
pytest
```

## Release to PyPI

This repo is set up to publish to PyPI via GitHub Actions. A publish typically happens when you push
a `v*` tag (for example `v0.1.1`), and can also be run manually from the Actions UI.

