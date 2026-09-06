#!/usr/bin/env python3
"""
make_cv.py

Render a LaTeX (.tex) file from a Jinja2 template and a YAML/JSON data
file, validate the data with a Pydantic model, and optionally compile
the result to PDF.

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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, ValidationError

# --------------------------------------------------------------------------
# Pydantic data model
# --------------------------------------------------------------------------
# TODO: replace with the real fields for your CV data. Left permissive for
# now so the script runs end-to-end; tighten this up once the schema is
# finalized.


class Education(BaseModel):
    university: str
    address: str
    faculty: str
    timespan: str = ""
    fields_of_study: list[str]


class JobProject(BaseModel):
    name: str
    timespan: str = ""
    description: list[str] | None = None


class Experience(BaseModel):
    company: str
    address: str
    position: str
    timespan: str = ""
    projects: list[JobProject] | None = None
    description: list[str] | None = None


class Skills(BaseModel):
    key: str
    value: str


class Language(BaseModel):
    name: str
    description: str


class CVData(BaseModel):
    """Schema for the input YAML/JSON data file."""

    model_config = {"extra": "allow"}

    fullname: str

    phone: str
    email: str
    address: str
    linkedin: str | None = None
    github: str | None = None

    position: str
    summary: str

    education: Education
    experience: list[Experience]
    skills: list[Skills]
    languages: list[Language]
    hobbies: str


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
            "Render a LaTeX file from a Jinja2 template and a YAML/JSON data file, and optionally compile it to PDF."
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
            "derived from the data file, with the .tex/.pdf suffix added "
            "as appropriate."
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
        help="Allow overwriting existing output .tex/.pdf files.",
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

    targets = [tex_path] + ([pdf_path] if args.pdf else [])
    check_overwrite(targets, args.overwrite)

    raw_data = load_data(data_path)
    validated = validate_data(raw_data)
    print(validated.model_dump_json())

    # Render using the validated data (as a plain dict) so the template
    # sees exactly the fields defined/allowed by CVData.
    rendered = render_tex(template_path, validated.model_dump())

    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(rendered, encoding="utf-8")
    print(f"Wrote {tex_path}")

    if args.pdf:
        compile_pdf(tex_path, pdf_path)
        print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
