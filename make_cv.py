#!/usr/bin/env python3
"""
make_cv.py

Render a LaTeX (.tex) file from a Jinja2 template and a YAML/JSON data
file, validate the data with a Pydantic model, and optionally compile
the result to PDF. A plain-Markdown (.md) rendering, using a template
baked into this module, is always written alongside the .tex file.

Tested target: Python 3 as shipped with Debian Bookworm (3.11).

Requirements (install with pip):
    pip install jinja2 pyyaml pydantic

For --pdf you additionally need a LaTeX distribution providing
`latexmk` and `pdflatex` (e.g. `apt install texlive-latex-extra latexmk`,
or `texlive-full` for a fuller install).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, Field, ValidationError

# --------------------------------------------------------------------------
# Pydantic data model
# --------------------------------------------------------------------------
# Schema for the CV data file (YAML or JSON). Free text fields (summary,
# description bullets, etc.) are expected to already contain any
# LaTeX-escaping/markup needed (e.g. "\&", "\\textbf{...}") since they are
# inserted into the template as-is.


class Education(BaseModel):
    """A single (most recent / highest) degree entry."""

    university: str = Field(..., description="Name of the university/school.")
    address: str = Field(..., description="City/country of the university.")
    faculty: str = Field(..., description="Faculty or department name.")
    timespan: str = Field(default="", description="Study period, e.g. '2006 -- 2012'.")
    fields_of_study: list[str] = Field(
        ...,
        description=(
            "One entry per degree/thesis, as a ready-to-render LaTeX string (may include \\textbf, \\emph, etc.)."
        ),
    )


class JobProject(BaseModel):
    """A notable project within a single job (Experience entry)."""

    name: str = Field(..., description="Project name/title.")
    timespan: str = Field(default="", description="Project period, e.g. '2018 -- 2026'.")
    description: list[str] | None = Field(
        default=None,
        description="Bullet points describing the project, in display order.",
    )


class Experience(BaseModel):
    """A single job/employer entry in the work-experience section."""

    company: str = Field(..., description="Employer/company name.")
    address: str = Field(..., description="City/country of the employer.")
    position: str = Field(..., description="Job title held at this company.")
    timespan: str = Field(default="", description="Employment period, e.g. '2012 -- 2026'.")
    projects: list[JobProject] | None = Field(
        default=None,
        description=(
            "Notable projects at this job, used instead of (or alongside) "
            "a flat 'description' list for jobs with multiple distinct "
            "projects worth breaking out."
        ),
    )
    description: list[str] | None = Field(
        default=None,
        description=("Bullet points describing this job, for jobs simple enough not to need a 'projects' breakdown."),
    )


class Skills(BaseModel):
    """One row of the skills section: a category and its contents."""

    key: str = Field(..., description="Skill category label, e.g. 'Languages'.")
    value: str = Field(..., description="Comma-separated skills within that category.")


class Language(BaseModel):
    """A spoken/written language and the candidate's proficiency in it."""

    name: str = Field(..., description="Language name, e.g. 'English'.")
    description: str = Field(..., description="Proficiency level or free-text description.")


class CVData(BaseModel):
    """Schema for the input YAML/JSON data file."""

    model_config = {"extra": "allow"}

    fullname: str = Field(..., description="Full name as shown in the CV header.")

    phone: str = Field(..., description="Phone number (LaTeX-escaped if needed).")
    email: str = Field(..., description="Contact email address.")
    address: str = Field(..., description="City/country of residence.")
    linkedin: str | None = Field(default=None, description="Full LinkedIn profile URL, if any.")
    github: str | None = Field(default=None, description="Full GitHub profile URL, if any.")

    position: str = Field(..., description="Headline job title shown under the name.")
    summary: str = Field(..., description="Short professional summary/profile paragraph.")

    education: Education = Field(..., description="Education entry.")
    experience: list[Experience] = Field(..., description="Work experience entries, most recent first.")
    skills: list[Skills] = Field(..., description="Skill categories, in display order.")
    languages: list[Language] = Field(..., description="Languages spoken, in display order.")
    hobbies: str = Field(..., description="Freeform hobbies/interests line.")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

YAML_SUFFIXES = {".yaml", ".yml"}
JSON_SUFFIXES = {".json"}


def load_data(data_path: Path) -> dict[str, Any]:
    """Load a YAML or JSON file into a plain dict, based on its suffix."""
    suffix = data_path.suffix.lower()
    text = data_path.read_text(encoding="utf-8")

    if suffix in YAML_SUFFIXES:
        raw = yaml.safe_load(text)
    elif suffix in JSON_SUFFIXES:
        raw = json.loads(text)
    else:
        raise ValueError(f"Unsupported data file suffix '{suffix}'. Expected one of: .yaml, .yml, .json")

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise TypeError(f"Top-level content of '{data_path}' must be a mapping/object, got {type(raw).__name__}.")
    return raw


def validate_data(raw: dict[str, Any]) -> CVData:
    """Validate raw data against the CVData Pydantic model."""
    try:
        return CVData.model_validate(raw)
    except ValidationError as exc:
        print("Input data failed validation:\n", file=sys.stderr)
        print(exc, file=sys.stderr)
        sys.exit(1)


def build_jinja_env(template_path: Path) -> Environment:
    """
    Build a Jinja2 environment with LaTeX-friendly delimiters.

    Jinja2's default {{ }} / {% %} / {# #} syntax collides with LaTeX's own
    use of curly braces and '#', so we remap Jinja2's syntax to sequences
    that don't appear in normal LaTeX source:

        variables:   (( var ))
        blocks:      ((* if cond *)) ... ((* endif *))
        comments:    ((# comment #))
        line stmts:  %% for item in items
    """
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        block_start_string="((*",
        block_end_string="*))",
        variable_start_string="((",
        variable_end_string="))",
        comment_start_string="((#",
        comment_end_string="#))",
        line_statement_prefix="%%",
        line_comment_prefix="%#",
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    return env


def render_tex(template_path: Path, data: dict[str, Any]) -> str:
    env = build_jinja_env(template_path)
    template = env.get_template(template_path.name)
    return template.render(**data)


# --------------------------------------------------------------------------
# Markdown output
# --------------------------------------------------------------------------
# The CV data is written LaTeX-first: free-text fields already contain TeX
# markup/escaping (\textbf{}, \&, \ , ---, inline $...$, etc.). For the
# Markdown rendering we translate the common cases back to plain Markdown,
# then render an embedded (baked-in) Jinja template. The Markdown file is
# always written alongside the .tex file, using the same base name.

_TEX_MARKUP_RE = [
    (re.compile(r"\\textbf\{([^{}]*)\}"), r"**\1**"),
    (re.compile(r"\\(?:emph|textit)\{([^{}]*)\}"), r"*\1*"),
    (re.compile(r"\\texttt\{([^{}]*)\}"), r"`\1`"),
]

_TEX_SYMBOLS = {
    r"\cdot": "\u00b7",
    r"\times": "\u00d7",
    r"\ldots": "\u2026",
    r"\dots": "\u2026",
}


def latex_to_markdown(text: str) -> str:
    """Best-effort conversion of LaTeX-flavoured free text to plain Markdown.

    Handles the markup that actually shows up in the CV data: ``\\textbf``/
    ``\\emph`` become ``**``/``*``, backslash-escaped characters are
    unescaped, TeX spacing (``\\ ``, ``~``) and dashes (``--``, ``---``) are
    normalised, and inline math ``$...$`` delimiters are dropped. Anything
    it doesn't recognise is passed through untouched.
    """
    if not text:
        return text

    result = text
    for pattern, repl in _TEX_MARKUP_RE:
        result = pattern.sub(repl, result)

    result = re.sub(r"\$([^$]*)\$", r"\1", result)
    for tex, char in _TEX_SYMBOLS.items():
        result = result.replace(tex, char)

    result = result.replace("\\ ", " ").replace("~", " ").replace("\\\\", " ")
    result = re.sub(r"\\([&%#_${}])", r"\1", result)
    result = result.replace("---", "\u2014").replace("--", "\u2013")
    result = re.sub(r"[ \t]{2,}", " ", result)
    return result.strip()


MARKDOWN_TEMPLATE = """\
# {{ fullname }}

{{ phone | md }} \u00b7 {{ email }}\
{% if linkedin %} \u00b7 {{ linkedin | replace("https://", "") | replace("http://", "") }}{% endif %}\
{% if github %} \u00b7 {{ github | replace("https://", "") | replace("http://", "") }}{% endif %} \u00b7 {{ address }}

**{{ position | md }}**

{{ summary | md }}

---

## Experience

{% for job in experience %}
### {{ job.company | md }}{{ (", " ~ (job.address | md)) if job.address else "" }} \u2014 *{{ job.position | md }}*{{ (" \u2014 " ~ (job.timespan | md)) if job.timespan else "" }}

{% if job.projects %}
{% for project in job.projects %}
**{{ project.name | md }}{% if project.timespan %} ({{ project.timespan | md }}){% endif %}**

{% if project.description %}
{% for item in project.description %}
- {{ item | md }}
{% endfor %}

{% endif %}
{% endfor %}
{% elif job.description %}
{% for item in job.description %}
- {{ item | md }}
{% endfor %}

{% endif %}
{% endfor %}
## Technical Skills

{% for skill in skills %}
- **{{ skill.key | md }}:** {{ skill.value | md }}
{% endfor %}

## Education

**{{ education.university | md }}** \u2014 {{ education.faculty | md }}{{ (" (" ~ (education.timespan | md) ~ ")") if education.timespan else "" }}

{% for item in education.fields_of_study %}
- {{ item | md }}
{% endfor %}

## Languages

{% for lang in languages %}
- **{{ lang.name | md }}** \u2014 {{ lang.description | md }}
{% endfor %}

## Hobbies

{{ hobbies | md }}
"""


def build_markdown_env() -> Environment:
    """Jinja2 environment for the embedded Markdown template (standard
    delimiters; no filesystem loader)."""
    env = Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False,
        undefined=StrictUndefined,
    )
    env.filters["md"] = latex_to_markdown
    return env


def render_markdown(data: dict[str, Any]) -> str:
    """Render the CV data to Markdown using the baked-in template."""
    template = build_markdown_env().from_string(MARKDOWN_TEMPLATE)
    rendered = template.render(**data)
    rendered = re.sub(r"[ \t]+\n", "\n", rendered)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip() + "\n"


def resolve_output_paths(data_path: Path, output_arg: str | None) -> tuple[Path, Path]:
    """
    Work out the .tex and .pdf output paths.

    If --output is given, its stem (suffix stripped, if any) is used as
    the base name for both files, in the directory it points to.
    Otherwise the base name is derived from the data file's name (suffix
    stripped), placed alongside the data file.
    """
    if output_arg:
        out_path = Path(output_arg)
        base = out_path.with_suffix("")
    else:
        base = data_path.with_suffix("")

    tex_path = base.with_suffix(".tex")
    pdf_path = base.with_suffix(".pdf")
    return tex_path, pdf_path


def check_overwrite(paths: list[Path], overwrite: bool) -> None:
    existing = [p for p in paths if p.exists()]
    if existing and not overwrite:
        names = ", ".join(str(p) for p in existing)
        print(
            f"Error: output file(s) already exist: {names}\nUse --overwrite to allow replacing them.",
            file=sys.stderr,
        )
        sys.exit(1)


def print_log_file(log_path: Path) -> None:
    """Print the contents of a LaTeX .log file, if it exists."""
    if not log_path.is_file():
        print(f"(no log file found at {log_path})")
        return
    print(f"----- {log_path.name} -----")
    print(log_path.read_text(encoding="utf-8", errors="replace"))
    print(f"----- end {log_path.name} -----")


def compile_pdf(tex_path: Path, pdf_path: Path) -> None:
    """
    Compile tex_path to PDF using latexmk.

    All of latexmk's auxiliary/output files (.aux, .log, .fls, .fdb_latexmk,
    the intermediate .pdf, etc.) are built in a temporary directory so they
    never land next to the source. Only the final PDF is copied to
    pdf_path; the .log is printed for visibility before the temp dir is
    cleaned up.
    """
    if shutil.which("latexmk") is None:
        print(
            "Error: 'latexmk' was not found on PATH. Install a LaTeX "
            "distribution (e.g. `apt install texlive-latex-extra latexmk`) "
            "to use --pdf.",
            file=sys.stderr,
        )
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="make_cv_latex_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        jobname = pdf_path.stem

        cmd = [
            "latexmk",
            "-pdf",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"-output-directory={tmp_path}",
            f"-jobname={jobname}",
            str(tex_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        log_path = tmp_path / f"{jobname}.log"
        tmp_pdf_path = tmp_path / f"{jobname}.pdf"

        if result.returncode != 0:
            print("LaTeX compilation failed:\n", file=sys.stderr)
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            print_log_file(log_path)
            sys.exit(1)

        if not tmp_pdf_path.exists():
            print(
                f"Error: latexmk reported success but '{tmp_pdf_path.name}' was not produced.",
                file=sys.stderr,
            )
            print_log_file(log_path)
            sys.exit(1)

        print_log_file(log_path)

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(tmp_pdf_path, pdf_path)
        # tmp_dir (and all its .aux/.fls/.fdb_latexmk/etc. clutter) is
        # removed automatically when this `with` block exits.


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a LaTeX file (and a Markdown sidecar) from a Jinja2 template and a YAML/JSON data file, "
            "and optionally compile the LaTeX to PDF."
        )
    )
    parser.add_argument(
        "-t",
        "--template",
        required=True,
        type=Path,
        help="Path to the Jinja2 template file.",
    )
    parser.add_argument(
        "-d",
        "--data",
        required=True,
        type=Path,
        help="Path to the input YAML/JSON data file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output base name (no suffix needed). If omitted, the name is "
            "derived from the data file, with the .tex/.md/.pdf suffix "
            "added as appropriate."
        ),
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Additionally compile the rendered .tex file to PDF.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting existing output .tex/.md/.pdf files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    template_path: Path = args.template
    data_path: Path = args.data

    if not template_path.is_file():
        print(f"Error: template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    if not data_path.is_file():
        print(f"Error: data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    tex_path, pdf_path = resolve_output_paths(data_path, args.output)
    md_path = tex_path.with_suffix(".md")

    targets = [tex_path, md_path] + ([pdf_path] if args.pdf else [])
    check_overwrite(targets, args.overwrite)

    raw_data = load_data(data_path)
    validated = validate_data(raw_data)
    print(validated.model_dump_json())

    # Render using the validated data (as a plain dict) so the templates
    # see exactly the fields defined/allowed by CVData.
    data = validated.model_dump()
    rendered = render_tex(template_path, data)

    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {tex_path}")

    md_path.write_text(render_markdown(data), encoding="utf-8")
    print(f"Wrote {md_path}")

    if args.pdf:
        compile_pdf(tex_path, pdf_path)
        print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
