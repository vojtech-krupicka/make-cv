# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The project has not had a tagged release yet; everything below is the
history so far.

### Added
- `make_cv.py`: render a LaTeX `.tex` file from a Jinja2 template and a
  YAML/JSON data file, with optional `--pdf` compilation.
  - LaTeX-friendly Jinja2 delimiters (`(( ))`, `((* *))`, `((# #))`,
    `%%` line statements) so templates don't clash with LaTeX braces.
  - YAML or JSON input, auto-detected from the file suffix.
  - Pydantic v2 validation of the input data before rendering, with clear
    errors instead of cryptic Jinja2/LaTeX failures.
  - Clean PDF builds: `latexmk` runs in a temporary directory, only the
    final `.pdf` is copied back out, the build log is printed, and all
    `.aux`/`.fls`/`.fdb_latexmk`/etc. clutter is discarded.
  - CLI: `-t/--template`, `-d/--data`, `-o/--output`, `--pdf`,
    `--overwrite`; output base name derived from the data file when `-o`
    is omitted; overwrite protection on existing `.tex`/`.md`/`.pdf`.
- Markdown output: every run also writes a `<base>.md` file next to the
  `.tex` file (no flag), rendered from a Jinja template embedded in
  `make_cv.py` (`MARKDOWN_TEMPLATE`). A `latex_to_markdown()` filter
  converts the common LaTeX markup in the data (`\textbf{}`/`\emph{}`,
  backslash escapes, `\ `, `--`/`---`, inline `$…$`) back to plain
  Markdown.
- `Dockerfile` (Debian Bookworm + Python 3 + `latexmk`/TeX Live) and a
  `.devcontainer/devcontainer.json` for a ready-to-use VS Code Dev
  Container, with Python, Ruff, LaTeX Workshop, and YAML extensions.
  - Extra CLI tools in the image: `git`, `sudo`, `nano`.
  - Non-root `vscode` user (UID/GID 1000, passwordless sudo) so files
    written to mounted folders stay owned by the host user.
  - Dev Container mounts the repo at `/app` and a sibling `../my-cv`
    folder at `/app/data` for personal CV inputs (Jinja/YAML) and outputs
    (`.tex`/`.pdf`), kept out of this repo; runs as `remoteUser: vscode`.
- `.vscode/launch.example.json`: checked-in `debugpy` launch-config
  template for running `make_cv.py` under the debugger.
- `.vscode/settings.json`: editor and unittest test-runner configuration.
- Ruff for linting/formatting; the codebase was formatted accordingly.
- Pydantic models for CV data: `CVData`, `Education`, `Experience`,
  `JobProject`, `Skills`, `Language`, with per-field documentation.
- `print_log_file` helper to surface the LaTeX `.log` on compilation
  failure.
- Example LaTeX templates and CV data files.
- `unittest` test suite in `tests/test_make_cv.py` covering data loading,
  validation, rendering, LaTeX→Markdown conversion, output-path
  resolution, overwrite protection, PDF compilation (mocked), and CLI
  parsing.
- Expanded `README.md`: usage, template syntax, model schema, Docker /
  Dev Container instructions, and test instructions.

### Changed
- Tightened data-loading errors (`TypeError` for non-mapping top-level
  content) and passed `check=False` explicitly to `subprocess.run`.
- Reworked the data model and example data for real-world CV input,
  adding project breakdowns (`Experience.projects` / `JobProject`).
- Renamed the example CV data/output to `vojtech-krupicka-cv.*` (beta CV).
- Dev Container now builds from the repo-root `Dockerfile` and mounts via
  `mounts` rather than `workspaceMount`.

### Removed
- `data/xkrupi06.tex.jinja` template.
- Personal CV data, `.tex`, and `.pdf` files from version control; the
  `data/` directory and `.vscode/launch.json` are now gitignored.
