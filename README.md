# Make My CV

A small, no-nonsense CV/resume generator: fill in a YAML or JSON data file,
render it into a LaTeX template with Jinja2, and (optionally) compile it
straight to PDF — with all of LaTeX's auxiliary-file clutter kept out of
your repository. Every run also drops a plain-Markdown version of the same
CV next to the `.tex` file.

## Features

- **Jinja2 → LaTeX** rendering, using LaTeX-friendly delimiters so
  templates don't fight with LaTeX's own `{ }` syntax (see
  [Template syntax](#template-syntax) below).
- **YAML or JSON** input, auto-detected from the file suffix.
- **Pydantic v2 validation** of the input data before rendering, so typos
  and missing fields are caught with a clear error instead of a cryptic
  Jinja2/LaTeX failure.
- **Clean PDF builds**: compilation runs in a temporary directory via
  `latexmk`; only the final `.pdf` is copied back out, the build log is
  printed for visibility, and every `.aux`/`.fls`/`.fdb_latexmk`/etc. file
  is discarded automatically.
- **Markdown sidecar**: a `.md` version of the CV is always written next to
  the `.tex` file, from a template baked into `make_cv.py`. Common LaTeX
  markup in the data (`\textbf{}`, `\emph{}`, `\&`, `\ `, `---`, inline
  `$…$`) is converted back to plain Markdown.
- **Dockerized**, with a ready-to-use VS Code Dev Container.

## Requirements

Run locally (without Docker):

```bash
pip install -r requirements.txt
```

For `--pdf` you additionally need a LaTeX distribution providing
`latexmk`/`pdflatex` (e.g. `apt install texlive-latex-extra latexmk`, or
`texlive-full` for a fuller install). If you're using the provided
`Dockerfile` or devcontainer, this is already taken care of.

## Usage

```
usage: make_cv.py [-h] -t TEMPLATE -d DATA [-o OUTPUT] [--pdf] [--overwrite]

Render a LaTeX file (and a Markdown sidecar) from a Jinja2 template and a
YAML/JSON data file, and optionally compile the LaTeX to PDF.

options:
  -h, --help           show this help message and exit
  -t, --template TEMPLATE
                       Path to the Jinja2 template file.
  -d, --data DATA      Path to the input YAML/JSON data file.
  -o, --output OUTPUT  Output base name (no suffix needed). If omitted, the
                       name is derived from the data file, with the
                       .tex/.md/.pdf suffix added as appropriate.
  --pdf                Additionally compile the rendered .tex file to PDF.
  --overwrite          Allow overwriting existing output .tex/.md/.pdf files.
```

Each run writes `<base>.tex` **and** `<base>.md`; `--pdf` additionally
produces `<base>.pdf`. All of them are covered by the `--overwrite` check.

### Examples

Render the `.tex` and `.md` files, named after the data file
(`vojtech-krupicka.tex` / `vojtech-krupicka.md`):

```bash
python3 make_cv.py -t template.tex.jinja -d vojtech-krupicka.yaml
```

Render and also compile to PDF, choosing an explicit output base name:

```bash
python3 make_cv.py -t template.tex.jinja -d vojtech-krupicka.yaml \
    -o output/cv --pdf
```

Re-run over existing output files:

```bash
python3 make_cv.py -t template.tex.jinja -d vojtech-krupicka.yaml \
    -o output/cv --pdf --overwrite
```

### Template syntax

Jinja2's default `{{ }}` / `{% %}` / `{# #}` syntax collides with LaTeX's
own use of curly braces, so templates use a remapped syntax instead:

| Purpose         | Syntax                          |
| --------------- | -------------------------------- |
| Variables       | `(( variable ))`                 |
| Blocks          | `((* if cond *)) ... ((* endif *))` |
| Comments        | `((# a comment #))`              |
| Line statements | `%% for item in items`           |

### Markdown output

Alongside the `.tex` file, `make_cv.py` always writes a `<base>.md` file
rendered from a Jinja template **embedded in the script itself**
(`MARKDOWN_TEMPLATE` in `make_cv.py`) — there is no separate template file
and no flag to enable it. It uses standard Jinja delimiters (`{{ }}` /
`{% %}`), since Markdown has no quarrel with braces.

Because the data file is written LaTeX-first, free-text fields are passed
through a `latex_to_markdown()` filter that converts the common cases:

| In the data (LaTeX)      | In the `.md` output |
| ------------------------ | ------------------- |
| `\textbf{x}`             | `**x**`             |
| `\emph{x}` / `\textit{x}`| `*x*`               |
| `\&` `\%` `\#` `\_` `\$` | `&` `%` `#` `_` `$`  |
| `\ ` (TeX space), `\\`   | space               |
| `--` / `---`             | `–` / `—`           |
| `$…$` (inline math)      | delimiters dropped, `\cdot` → `·` |

Anything it doesn't recognise is left as-is, so unusual markup may need a
manual touch-up in the generated `.md`.

## Running via Docker / VS Code Dev Container

The project ships with a `Dockerfile` (Debian Bookworm + Python 3 +
`latexmk`/TeX Live) and a `.devcontainer/devcontainer.json` that builds
straight from it.

### Container layout

- The image builds from the `Dockerfile` at the repo root and runs as a
  non-root **`vscode`** user (UID/GID `1000`, passwordless `sudo`). Using
  UID `1000` means files written into the mounted folders stay owned by
  your host user rather than by `root`.
- The repo itself is mounted at **`/app`** (the workspace folder inside
  the container).
- A sibling **`my-cv`** folder — `../my-cv`, next to this repo on the host
  — is mounted at **`/app/data`**. This is where your personal CV inputs
  (Jinja/YAML) and generated outputs (`.tex`/`.pdf`) live, kept entirely
  out of this repo. It can be a plain directory or a separate git
  checkout (e.g. a private `my-cv` repo). **Create it before reopening in
  the container**, otherwise the bind mount fails:

  ```bash
  mkdir -p ../my-cv
  ```

  Inside the repo, `data/` is just the (gitignored) mount point for this
  folder.

### To open it in VS Code

1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.
2. Ensure a `../my-cv` folder exists next to this repo (see above).
3. Open this project folder in VS Code.
4. Run **Dev Containers: Reopen in Container** from the Command Palette
   (`Ctrl+Shift+P` / `Cmd+Shift+P`).
5. VS Code builds the image (Python, `latexmk`, TeX Live packages,
   `requirements.txt` deps) and reopens the folder inside the container,
   with the Python, Ruff, LaTeX Workshop, and YAML extensions
   pre-installed.
6. Once inside, run the script from the integrated terminal, pointing at
   files under `data/`:

   ```bash
   python3 make_cv.py -t data/template.tex.jinja -d data/your-cv.yaml -o data/output/cv --pdf --overwrite
   ```

### Debugging in VS Code

`.vscode/launch.json` holds a **"Make My CV"** debug configuration that
runs `make_cv.py` under `debugpy` with a fixed set of arguments. Because
those arguments reference personal data-file names, the real
`launch.json` is **gitignored**; a sanitised
[`.vscode/launch.example.json`](./.vscode/launch.example.json) is checked
in instead.

Copy it and adjust the `args` to your own template/data files:

```bash
cp .vscode/launch.example.json .vscode/launch.json
```

Then pick **"Make My CV"** in the Run and Debug panel (`F5`).

### Without VS Code

The same image works directly with plain Docker. Mount your inputs/outputs
folder at `/app/data`:

```bash
docker build -t make_cv .
docker run --rm -v "$(cd ../my-cv && pwd):/app/data" make_cv \
    -t /app/data/template.tex.jinja -d /app/data/your-cv.yaml -o /app/data/output/cv --pdf --overwrite
```

## Data file format

The data file (YAML or JSON) is validated against the `CVData` Pydantic
model below before rendering. Keep your own data and template files in the
`../my-cv` folder (mounted at `data/`), not in this repo.

## Model Schema

All models live in `make_cv.py`. Fields marked **required** have no
default and must be present in the data file; others fall back to the
listed default when omitted.

### `CVData` (root model)

The top-level schema for the whole data file. Allows extra, unrecognized
fields (`extra="allow"`) so you can stash additional data without failing
validation.

| Field        | Type                    | Required | Description                                     |
| ------------ | ----------------------- | :------: | ------------------------------------------------ |
| `fullname`   | `str`                   | ✅        | Full name as shown in the CV header.              |
| `phone`      | `str`                   | ✅        | Phone number (LaTeX-escaped if needed).           |
| `email`      | `str`                   | ✅        | Contact email address.                            |
| `address`    | `str`                   | ✅        | City/country of residence.                        |
| `linkedin`   | `str \| None`           |          | Full LinkedIn profile URL, if any. Default: `None`. |
| `github`     | `str \| None`           |          | Full GitHub profile URL, if any. Default: `None`. |
| `position`   | `str`                   | ✅        | Headline job title shown under the name.          |
| `summary`    | `str`                   | ✅        | Short professional summary/profile paragraph.     |
| `education`  | [`Education`](#education) | ✅     | Education entry.                                  |
| `experience` | `list[`[`Experience`](#experience)`]` | ✅ | Work experience entries, most recent first. |
| `skills`     | `list[`[`Skills`](#skills)`]` | ✅ | Skill categories, in display order.               |
| `languages`  | `list[`[`Language`](#language)`]` | ✅ | Languages spoken, in display order.               |
| `hobbies`    | `str`                   | ✅        | Freeform hobbies/interests line.                  |

### `Education`

A single (most recent / highest) degree entry.

| Field             | Type        | Required | Description                                                                                     |
| ----------------- | ----------- | :------: | ------------------------------------------------------------------------------------------------ |
| `university`      | `str`       | ✅        | Name of the university/school.                                                                    |
| `address`         | `str`       | ✅        | City/country of the university.                                                                    |
| `faculty`         | `str`       | ✅        | Faculty or department name.                                                                        |
| `timespan`        | `str`       |          | Study period, e.g. `'2006 -- 2012'`. Default: `""`.                                                |
| `fields_of_study` | `list[str]` | ✅        | One entry per degree/thesis, as a ready-to-render LaTeX string (may include `\textbf`, `\emph`, etc.). |

### `Experience`

A single job/employer entry in the work-experience section.

| Field         | Type                                       | Required | Description                                                                                          |
| ------------- | ------------------------------------------- | :------: | ------------------------------------------------------------------------------------------------------ |
| `company`     | `str`                                        | ✅        | Employer/company name.                                                                                  |
| `address`     | `str`                                        | ✅        | City/country of the employer.                                                                           |
| `position`    | `str`                                        | ✅        | Job title held at this company.                                                                         |
| `timespan`    | `str`                                        |          | Employment period, e.g. `'2012 -- 2026'`. Default: `""`.                                                |
| `projects`    | `list[`[`JobProject`](#jobproject)`] \| None` |    | Notable projects at this job, used instead of (or alongside) a flat `description` list for jobs with multiple distinct projects worth breaking out. Default: `None`. |
| `description` | `list[str] \| None`                          |          | Bullet points describing this job, for jobs simple enough not to need a `projects` breakdown. Default: `None`. |

### `JobProject`

A notable project within a single job (`Experience` entry).

| Field         | Type                | Required | Description                                              |
| ------------- | ------------------- | :------: | ---------------------------------------------------------- |
| `name`        | `str`               | ✅        | Project name/title.                                        |
| `timespan`    | `str`               |          | Project period, e.g. `'2018 -- 2026'`. Default: `""`.      |
| `description` | `list[str] \| None` |          | Bullet points describing the project, in display order. Default: `None`. |

### `Skills`

One row of the skills section: a category and its contents.

| Field   | Type  | Required | Description                                       |
| ------- | ----- | :------: | --------------------------------------------------- |
| `key`   | `str` | ✅        | Skill category label, e.g. `'Languages'`.           |
| `value` | `str` | ✅        | Comma-separated skills within that category.        |

### `Language`

A spoken/written language and the candidate's proficiency in it.

| Field         | Type  | Required | Description                          |
| ------------- | ----- | :------: | --------------------------------------- |
| `name`        | `str` | ✅        | Language name, e.g. `'English'`.        |
| `description` | `str` | ✅        | Proficiency level or free-text description. |

## Running tests

The project has a `unittest`-based test suite in `tests/test_make_cv.py`,
covering data loading, Pydantic validation, Jinja2/LaTeX rendering,
LaTeX→Markdown conversion and the Markdown template, output-path
resolution, overwrite protection, PDF compilation, and CLI argument
parsing.

PDF compilation is tested by mocking out `latexmk`/`subprocess.run`, so the
suite runs fully without a LaTeX installation.

Run the whole suite from the project root:

```bash
python3 -m unittest discover -s tests -v
```

Or run a single test class or test case:

```bash
python3 -m unittest tests.test_make_cv.TestValidateData -v
python3 -m unittest tests.test_make_cv.TestCompilePdf.test_successful_build_copies_pdf_and_cleans_up_temp_dir -v
```

This works the same way inside the Docker/devcontainer setup, since
`requirements.txt` is installed there already; no LaTeX distribution is
needed just to run the tests.

## Project layout

```
.
├── make_cv.py                 # main script
├── tests/
│   └── test_make_cv.py        # unittest test suite
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Debian Bookworm + Python + latexmk/TeX Live, runs as user "vscode"
├── .devcontainer/
│   └── devcontainer.json      # VS Code Dev Container config (mounts ../my-cv at /app/data)
├── .vscode/
│   ├── launch.example.json    # checked-in debug config template
│   ├── launch.json            # your personal debug config (gitignored)
│   └── settings.json          # editor / test-runner settings
└── data/                      # gitignored mount point for ../my-cv (templates + data + output)
```