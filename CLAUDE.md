# CLAUDE.md

Background notes for anyone (human or AI) picking up work on this repo.
For *what changed*, see [CHANGELOG.md](./CHANGELOG.md); for *how to use it*,
see [README.md](./README.md).

## What this is

`make_cv.py` is a single-file CV generator:

```
YAML/JSON data  ─┬─►  Jinja LaTeX template  ─►  <base>.tex  ─(--pdf)─►  <base>.pdf
                 └─►  embedded Markdown template  ─►  <base>.md
```

- Input data is validated against the `CVData` Pydantic model before
  rendering.
- The LaTeX template is a **file** passed with `-t`, rendered with
  LaTeX-safe Jinja delimiters (`(( ))`, `((* *))`, `((# #))`, `%%`).
- The Markdown template is **baked into `make_cv.py`** (`MARKDOWN_TEMPLATE`),
  uses standard Jinja delimiters, and is always written next to the
  `.tex` file — no CLI flag.

## Repo / data layout

The **code** lives in this repo (`py-make-my-cv`). The **CV content**
lives in a sibling folder `../my-cv` (a plain folder or a separate git
repo), never committed here:

```
<parent>/
├── py-make-my-cv/     # this repo: make_cv.py, tests, Docker, docs
└── my-cv/             # personal: *.tex.jinja template, *.yaml data,
                       #           generated *.tex / *.md / *.pdf
```

Inside the repo, `data/` is a gitignored bind-mount point; the Dev
Container mounts `../my-cv` there (`/app/data`). `.vscode/launch.json` is
also gitignored (it holds personal data-file names);
`.vscode/launch.example.json` is the checked-in template.

Reference files currently in `../my-cv`:
- `vojtech-krupicka-cv.yaml` — the real CV data (LaTeX-flavoured, see below)
- `hassas-resume.tex.jinja` — the LaTeX template in use (Jake's Resume style)
- `original.md` — the hand-written Markdown the CV started from; **stale
  content**, kept only as the structural reference for the Markdown output

## Key design decisions

- **Data is written LaTeX-first.** Free-text fields in the YAML already
  contain TeX markup/escaping: `\textbf{}`, `\emph{}`, `\&`, `\ `
  (thin space), `---`, inline `$…$`, `$\cdot$`, etc. The LaTeX template
  inserts them as-is.
- Because of that, the Markdown path runs every free-text field through
  `latex_to_markdown()` (registered as the Jinja `md` filter) to convert
  the common cases back to plain Markdown. It is deliberately
  best-effort — unrecognised markup passes through and may need a manual
  touch-up in the generated `.md`.
- The Markdown template tolerates missing `job.projects` / `job.description`
  (renders just the heading); the LaTeX template assumes one is present.
- `render_markdown()` post-processes the Jinja output (strip trailing
  whitespace, collapse 3+ newlines to 2) so the template itself can be
  written without obsessing over every blank line. Note: Jinja
  `trim_blocks` eats the newline after a line-ending `{% … %}` tag, so
  heading lines use inline `{{ … if … else "" }}` expressions instead.
- `requirements.txt` lists `kachlog` even though nothing imports it — it
  is installed for use inside the Dev Container. Leave it.

## Dev / test workflow

- Dev happens in the VS Code Dev Container (Debian + Python 3 + TeX Live),
  which runs as a non-root `vscode` user (UID 1000) so mounted files stay
  host-owned.
- Tests: `python3 -m unittest discover -s tests -v` from the repo root.
  `latexmk` is mocked, so no LaTeX install is needed to run them.
- The host used for some past edits had **no pip and no pydantic**; the
  suite must be run inside the container (or anywhere `pip install -r
  requirements.txt` has been done) to exercise the real Pydantic models.
