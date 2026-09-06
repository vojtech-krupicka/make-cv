# Make My CV

A small, no-nonsense CV/resume generator: fill in a YAML or JSON data file,
render it into a LaTeX template with Jinja2, and (optionally) compile it
straight to PDF — with all of LaTeX's auxiliary-file clutter kept out of
your repository.

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

Render a LaTeX file from a Jinja2 template and a YAML/JSON data file, and
optionally compile it to PDF.

options:
  -h, --help            show this help message and exit
  -t TEMPLATE, --template TEMPLATE
                        Path to the Jinja2 template file.
  -d DATA, --data DATA  Path to the input YAML/JSON data file.
  -o OUTPUT, --output OUTPUT
                        Output base name (no suffix needed). If omitted, the
                        name is derived from the data file, with the .tex/.pdf
                        suffix added as appropriate.
  --pdf                 Additionally compile the rendered .tex file to PDF.
  --overwrite           Allow overwriting existing output .tex/.pdf files.
```

### Examples

Render only the `.tex` file, named after the data file (`vojtech-krupicka.tex`):

```bash
python3 make_cv.py -t template.tex.jinja -d vojtech-krupicka.yaml
```

Render and compile to PDF, choosing an explicit output base name:

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

## Running via Docker / VS Code Dev Container

The project ships with a `Dockerfile` (Debian Bookworm + Python 3 +
`latexmk`/TeX Live) and a `.devcontainer/devcontainer.json` that builds
straight from it.

**To open it in VS Code:**

1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.
2. Open this project folder in VS Code.
3. Run **Dev Containers: Reopen in Container** from the Command Palette
   (`Ctrl+Shift+P` / `Cmd+Shift+P`).
4. VS Code builds the image (Python, `latexmk`, TeX Live packages,
   `requirements.txt` deps) and reopens the folder inside the container,
   with the Python, LaTeX Workshop, and YAML extensions pre-installed.
5. Once inside, just run the script from the integrated terminal:

   ```bash
   python3 make_cv.py -t template.tex.jinja -d vojtech-krupicka.yaml -o output/cv --pdf --overwrite
   ```

**Without VS Code**, the same image works directly with plain Docker:

```bash
docker build -t make_cv .
docker run --rm -v "$PWD:/data" make_cv \
    -t /data/template.tex.jinja -d /data/vojtech-krupicka.yaml -o /data/output/cv --pdf --overwrite
```

## Data file format

The data file (YAML or JSON) is validated against the `CVData` Pydantic
model below before rendering. See
[`vojtech-krupicka.yaml`](./vojtech-krupicka.yaml) for a full real-world
example.

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

The project has a `unittest`-based test suite in `test_make_cv.py`, covering
data loading, Pydantic validation, Jinja2/LaTeX rendering, output-path
resolution, overwrite protection, PDF compilation, and CLI argument
parsing.

PDF compilation is tested by mocking out `latexmk`/`subprocess.run`, so the
suite runs fully without a LaTeX installation.

Run the whole suite from the project root:

```bash
python3 -m unittest test_make_cv.py -v
```

Or run a single test class or test case:

```bash
python3 -m unittest test_make_cv.TestValidateData -v
python3 -m unittest test_make_cv.TestCompilePdf.test_successful_build_copies_pdf_and_cleans_up_temp_dir -v
```

This works the same way inside the Docker/devcontainer setup, since
`requirements.txt` is installed there already; no LaTeX distribution is
needed just to run the tests.

## Project layout

```
.
├── make_cv.py               # main script
├── test_make_cv.py           # unittest test suite
├── requirements.txt          # Python dependencies
├── Dockerfile                 # Debian Bookworm + Python + latexmk/TeX Live
├── .devcontainer/
│   └── devcontainer.json      # VS Code Dev Container config
├── template.tex.jinja         # your Jinja2/LaTeX template (not included above)
└── vojtech-krupicka.yaml      # example data file
```