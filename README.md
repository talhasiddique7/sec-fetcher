# secfetcher

`secfetcher` is the pip-installable package name. The importable Python module and CLI are `secfetch`.
It’s a small Python package for downloading SEC EDGAR filings by **quarter** or **year**.
It uses the SEC **master index** as the source of truth, then downloads each filing’s folder from EDGAR
and saves only the file types you request.

## Install (local)

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

If your system Python is “externally managed” (PEP 668), you must install into a virtualenv (as above).

## Required: SEC User-Agent

SEC requires a descriptive user-agent with contact info.

Set an environment variable:

```bash
export SEC_USER_AGENT="Your Company Name contact@example.com"
```

Or pass it directly in code.

## Public API

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

### Form type allowlist (strict)

`secfetch` **only accepts** SEC form types listed in:

- `data/config/form_types.json` (auto-created on first run), sourced from
- `src/secfetch/resources/form_types.json` (packaged default)

Edit `data/config/form_types.json` if you want to add/remove accepted form types.

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

After a **quarter** finishes with **no errors**, `secfetch` deletes the cached master index for that
quarter under `data/index/master/<year>/QTR<q>/`.

## CLI (optional)

```bash
secfetch quarter --year 2024 --quarter 3 --forms 10-Q 10-K --data-dir data --file-types .xml .htm .html .pdf
secfetch year --year 2024 --forms 8-K --data-dir data --file-types .htm .html
```

You can also run it as a module:

```bash
python -m secfetch --help
```

## Notes

- The package API lives under `src/secfetch/`.

