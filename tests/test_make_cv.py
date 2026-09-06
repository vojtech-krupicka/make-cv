"""
test_make_cv.py

Unit tests for make_cv.py, using the standard library's unittest module.

Run with:
    python3 -m unittest test_make_cv.py -v
or simply:
    python3 -m unittest -v
(discovered automatically from the `test_*.py` naming convention)
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

import make_cv
from make_cv import (
    CVData,
    Education,
    Experience,
    JobProject,
    Language,
    Skills,
    build_jinja_env,
    check_overwrite,
    compile_pdf,
    load_data,
    print_log_file,
    render_tex,
    resolve_output_paths,
    validate_data,
)

# --------------------------------------------------------------------------
# Shared fixture data: a minimal-but-complete valid CV data set.
# --------------------------------------------------------------------------

MINIMAL_VALID_DATA = {
    "fullname": "Jane Doe",
    "phone": "+1 555 0100",
    "email": "jane@example.com",
    "address": "Springfield, USA",
    "position": "Software Engineer",
    "summary": "Experienced engineer.",
    "education": {
        "university": "State University",
        "address": "Springfield, USA",
        "faculty": "Faculty of Engineering",
        "timespan": "2010 -- 2014",
        "fields_of_study": ["B.Sc., Computer Science"],
    },
    "experience": [
        {
            "company": "Acme Corp",
            "address": "Springfield, USA",
            "position": "Backend Developer",
            "timespan": "2014 -- 2020",
            "description": ["Built things.", "Fixed things."],
        }
    ],
    "skills": [{"key": "Languages", "value": "Python, Go"}],
    "languages": [{"name": "English", "description": "Native"}],
    "hobbies": "Reading, hiking",
}


class TestLoadData(unittest.TestCase):
    """Tests for load_data(): YAML/JSON parsing based on file suffix."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = Path(self.tmp_dir.name)

    def test_loads_yaml_file(self) -> None:
        yaml_path = self.tmp_path / "data.yaml"
        yaml_path.write_text("fullname: Jane Doe\nemail: jane@example.com\n")
        result = load_data(yaml_path)
        self.assertEqual(result, {"fullname": "Jane Doe", "email": "jane@example.com"})

    def test_loads_yml_file(self) -> None:
        yml_path = self.tmp_path / "data.yml"
        yml_path.write_text("fullname: Jane Doe\n")
        result = load_data(yml_path)
        self.assertEqual(result, {"fullname": "Jane Doe"})

    def test_loads_json_file(self) -> None:
        json_path = self.tmp_path / "data.json"
        json_path.write_text(json.dumps({"fullname": "Jane Doe"}))
        result = load_data(json_path)
        self.assertEqual(result, {"fullname": "Jane Doe"})

    def test_empty_file_yields_empty_dict(self) -> None:
        yaml_path = self.tmp_path / "empty.yaml"
        yaml_path.write_text("")
        result = load_data(yaml_path)
        self.assertEqual(result, {})

    def test_unsupported_suffix_raises_value_error(self) -> None:
        txt_path = self.tmp_path / "data.txt"
        txt_path.write_text("fullname: Jane Doe\n")
        with self.assertRaises(ValueError):
            load_data(txt_path)

    def test_non_mapping_top_level_raises_value_error(self) -> None:
        yaml_path = self.tmp_path / "list.yaml"
        yaml_path.write_text("- one\n- two\n")
        with self.assertRaises(TypeError):
            load_data(yaml_path)


class TestValidateData(unittest.TestCase):
    """Tests for validate_data() and the CVData model tree itself."""

    def test_valid_data_passes(self) -> None:
        result = validate_data(MINIMAL_VALID_DATA)
        self.assertIsInstance(result, CVData)
        self.assertEqual(result.fullname, "Jane Doe")
        self.assertEqual(len(result.experience), 1)
        self.assertIsInstance(result.experience[0], Experience)
        self.assertEqual(result.experience[0].company, "Acme Corp")

    def test_missing_required_field_exits(self) -> None:
        bad_data = dict(MINIMAL_VALID_DATA)
        del bad_data["fullname"]
        with self.assertRaises(SystemExit) as ctx:
            validate_data(bad_data)
        self.assertEqual(ctx.exception.code, 1)

    def test_optional_fields_default_to_none(self) -> None:
        result = validate_data(MINIMAL_VALID_DATA)
        self.assertIsNone(result.linkedin)
        self.assertIsNone(result.github)

    def test_experience_supports_projects_instead_of_description(self) -> None:
        data = dict(MINIMAL_VALID_DATA)
        data["experience"] = [
            {
                "company": "Acme Corp",
                "address": "Springfield, USA",
                "position": "Backend Developer",
                "projects": [
                    {"name": "Project A", "description": ["Did X."]},
                    {"name": "Project B"},
                ],
            }
        ]
        result = validate_data(data)
        self.assertIsInstance(result.experience[0].projects[0], JobProject)
        self.assertEqual(result.experience[0].projects[0].name, "Project A")
        # timespan defaults to "" when omitted
        self.assertEqual(result.experience[0].timespan, "")

    def test_skills_and_language_round_trip(self) -> None:
        skill = Skills(key="Languages", value="Python, Go")
        lang = Language(name="English", description="Native")
        self.assertEqual(skill.key, "Languages")
        self.assertEqual(lang.description, "Native")


class TestJinjaRendering(unittest.TestCase):
    """Tests for build_jinja_env()/render_tex() and the LaTeX-safe delimiters."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = Path(self.tmp_dir.name)

    def test_variable_substitution(self) -> None:
        template_path = self.tmp_path / "template.tex.jinja"
        template_path.write_text(r"Hello, ((( fullname ))) !")
        result = render_tex(template_path, {"fullname": "Jane Doe"})
        self.assertEqual(result, "Hello, Jane Doe !")

    def test_block_tags_and_loop(self) -> None:
        template_path = self.tmp_path / "template.tex.jinja"
        template_path.write_text("((* for skill in skills *))\n- ((( skill )))\n((* endfor *))")
        result = render_tex(template_path, {"skills": ["Python", "Go"]})
        self.assertIn("- Python", result)
        self.assertIn("- Go", result)

    def test_line_statement_prefix(self) -> None:
        template_path = self.tmp_path / "template.tex.jinja"
        template_path.write_text("%% if show\nvisible\n%% endif")
        result = render_tex(template_path, {"show": True})
        self.assertEqual(result.strip(), "visible")

    def test_comment_is_stripped(self) -> None:
        template_path = self.tmp_path / "template.tex.jinja"
        template_path.write_text("before((# a comment #))after")
        result = render_tex(template_path, {})
        self.assertEqual(result, "beforeafter")

    def test_default_curly_brace_syntax_is_untouched(self) -> None:
        """LaTeX's own { } should pass through unmodified, unlike default Jinja2."""
        template_path = self.tmp_path / "template.tex.jinja"
        template_path.write_text(r"\textbf{((( name )))}")
        result = render_tex(template_path, {"name": "Jane"})
        self.assertEqual(result, r"\textbf{Jane}")

    def test_undefined_variable_raises(self) -> None:
        template_path = self.tmp_path / "template.tex.jinja"
        template_path.write_text("(((missing)))")
        with self.assertRaises(Exception):
            render_tex(template_path, {})


class TestResolveOutputPaths(unittest.TestCase):
    """Tests for resolve_output_paths()."""

    def test_no_output_arg_derives_from_data_file(self) -> None:
        data_path = Path("/some/dir/vojtech-krupicka.yaml")
        tex_path, pdf_path = resolve_output_paths(data_path, None)
        self.assertEqual(tex_path, Path("/some/dir/vojtech-krupicka.tex"))
        self.assertEqual(pdf_path, Path("/some/dir/vojtech-krupicka.pdf"))

    def test_output_arg_without_suffix(self) -> None:
        data_path = Path("/some/dir/data.yaml")
        tex_path, pdf_path = resolve_output_paths(data_path, "/out/cv")
        self.assertEqual(tex_path, Path("/out/cv.tex"))
        self.assertEqual(pdf_path, Path("/out/cv.pdf"))

    def test_output_arg_with_suffix_is_stripped(self) -> None:
        data_path = Path("/some/dir/data.yaml")
        tex_path, pdf_path = resolve_output_paths(data_path, "/out/cv.tex")
        self.assertEqual(tex_path, Path("/out/cv.tex"))
        self.assertEqual(pdf_path, Path("/out/cv.pdf"))

    def test_output_arg_relative_path(self) -> None:
        data_path = Path("/some/dir/data.json")
        tex_path, pdf_path = resolve_output_paths(data_path, "cv")
        self.assertEqual(tex_path, Path("cv.tex"))
        self.assertEqual(pdf_path, Path("cv.pdf"))


class TestCheckOverwrite(unittest.TestCase):
    """Tests for check_overwrite()."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = Path(self.tmp_dir.name)

    def test_no_existing_files_passes_without_overwrite(self) -> None:
        targets = [self.tmp_path / "a.tex", self.tmp_path / "a.pdf"]
        check_overwrite(targets, overwrite=False)  # should not raise

    def test_existing_file_without_overwrite_exits(self) -> None:
        existing = self.tmp_path / "a.tex"
        existing.write_text("content")
        with self.assertRaises(SystemExit) as ctx:
            check_overwrite([existing], overwrite=False)
        self.assertEqual(ctx.exception.code, 1)

    def test_existing_file_with_overwrite_passes(self) -> None:
        existing = self.tmp_path / "a.tex"
        existing.write_text("content")
        check_overwrite([existing], overwrite=True)  # should not raise


class TestCompilePdf(unittest.TestCase):
    """
    Tests for compile_pdf().

    latexmk itself is mocked out so these tests run without a LaTeX
    installation; they check that make_cv drives the temp-dir/log/copy
    workflow correctly rather than testing latexmk itself.
    """

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = Path(self.tmp_dir.name)
        self.tex_path = self.tmp_path / "cv.tex"
        self.tex_path.write_text(r"\documentclass{article}")
        self.pdf_path = self.tmp_path / "output" / "cv.pdf"

    def _output_dir_from_cmd(self, cmd: list[str]) -> Path:
        for arg in cmd:
            if arg.startswith("-output-directory="):
                return Path(arg.split("=", 1)[1])
        raise AssertionError("no -output-directory= argument found in cmd")

    @patch("make_cv.shutil.which", return_value=None)
    def test_missing_latexmk_exits(self, mock_which: MagicMock) -> None:
        with self.assertRaises(SystemExit) as ctx:
            compile_pdf(self.tex_path, self.pdf_path)
        self.assertEqual(ctx.exception.code, 1)

    @patch("make_cv.shutil.which", return_value="/usr/bin/latexmk")
    @patch("make_cv.subprocess.run")
    def test_latexmk_failure_exits(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="some output", stderr="an error")
        with self.assertRaises(SystemExit) as ctx:
            compile_pdf(self.tex_path, self.pdf_path)
        self.assertEqual(ctx.exception.code, 1)
        self.assertFalse(self.pdf_path.exists())

    @patch("make_cv.shutil.which", return_value="/usr/bin/latexmk")
    @patch("make_cv.subprocess.run")
    def test_successful_build_copies_pdf_and_cleans_up_temp_dir(
        self, mock_run: MagicMock, mock_which: MagicMock
    ) -> None:
        captured_tmp_dir: dict[str, Path] = {}

        def fake_latexmk(cmd, *args, **kwargs):
            out_dir = self._output_dir_from_cmd(cmd)
            captured_tmp_dir["path"] = out_dir
            (out_dir / "cv.log").write_text("This is the build log.\n")
            (out_dir / "cv.pdf").write_bytes(b"%PDF-1.4 fake pdf content")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = fake_latexmk

        compile_pdf(self.tex_path, self.pdf_path)

        self.assertTrue(self.pdf_path.exists())
        self.assertEqual(self.pdf_path.read_bytes(), b"%PDF-1.4 fake pdf content")
        # The temp directory latexmk built in should be cleaned up afterwards.
        self.assertFalse(captured_tmp_dir["path"].exists())

    @patch("make_cv.shutil.which", return_value="/usr/bin/latexmk")
    @patch("make_cv.subprocess.run")
    def test_missing_output_pdf_after_success_exits(self, mock_run: MagicMock, mock_which: MagicMock) -> None:
        # latexmk reports success but never actually produces the PDF.
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        with self.assertRaises(SystemExit) as ctx:
            compile_pdf(self.tex_path, self.pdf_path)
        self.assertEqual(ctx.exception.code, 1)


class TestPrintLogFile(unittest.TestCase):
    """Tests for print_log_file()."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = Path(self.tmp_dir.name)

    def test_prints_existing_log_contents(self) -> None:
        log_path = self.tmp_path / "cv.log"
        log_path.write_text("Line one.\nLine two.\n")

        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_log_file(log_path)
        output = buffer.getvalue()
        self.assertIn("Line one.", output)
        self.assertIn("Line two.", output)
        self.assertIn("cv.log", output)

    def test_missing_log_file_prints_notice_without_raising(self) -> None:
        import io
        from contextlib import redirect_stdout

        missing_path = self.tmp_path / "does-not-exist.log"
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_log_file(missing_path)  # should not raise
        self.assertIn("no log file found", buffer.getvalue())


class TestParseArgs(unittest.TestCase):
    """Tests for the argparse CLI definition."""

    def test_required_args_parsed(self) -> None:
        args = make_cv.parse_args(["-t", "template.tex.jinja", "-d", "data.yaml"])
        self.assertEqual(args.template, Path("template.tex.jinja"))
        self.assertEqual(args.data, Path("data.yaml"))
        self.assertIsNone(args.output)
        self.assertFalse(args.pdf)
        self.assertFalse(args.overwrite)

    def test_all_flags_parsed(self) -> None:
        args = make_cv.parse_args(
            [
                "-t",
                "template.tex.jinja",
                "-d",
                "data.yaml",
                "-o",
                "out/cv",
                "--pdf",
                "--overwrite",
            ]
        )
        self.assertEqual(args.output, "out/cv")
        self.assertTrue(args.pdf)
        self.assertTrue(args.overwrite)

    def test_missing_required_args_raises_system_exit(self) -> None:
        with self.assertRaises(SystemExit):
            make_cv.parse_args(["-t", "template.tex.jinja"])  # missing -d


class TestMainIntegration(unittest.TestCase):
    """
    End-to-end test of main(): data file -> validation -> rendered .tex,
    without invoking latexmk (PDF compilation is tested separately/mocked).
    """

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.tmp_path = Path(self.tmp_dir.name)

        self.template_path = self.tmp_path / "template.tex.jinja"
        self.template_path.write_text(
            r"\documentclass{article}\begin{document}"
            "Hello, ((( fullname ))) !"
            r"\end{document}"
        )

        self.data_path = self.tmp_path / "data.yaml"
        import yaml

        self.data_path.write_text(yaml.safe_dump(MINIMAL_VALID_DATA))

    def test_main_renders_tex_file(self) -> None:
        out_base = self.tmp_path / "cv"
        make_cv.main(
            [
                "-t",
                str(self.template_path),
                "-d",
                str(self.data_path),
                "-o",
                str(out_base),
            ]
        )
        tex_path = out_base.with_suffix(".tex")
        self.assertTrue(tex_path.exists())
        content = tex_path.read_text()
        self.assertIn("Hello, Jane Doe !", content)
        self.assertFalse(out_base.with_suffix(".pdf").exists())

    def test_main_refuses_to_overwrite_without_flag(self) -> None:
        out_base = self.tmp_path / "cv"
        tex_path = out_base.with_suffix(".tex")
        tex_path.parent.mkdir(parents=True, exist_ok=True)
        tex_path.write_text("existing content")

        with self.assertRaises(SystemExit) as ctx:
            make_cv.main(
                [
                    "-t",
                    str(self.template_path),
                    "-d",
                    str(self.data_path),
                    "-o",
                    str(out_base),
                ]
            )
        self.assertEqual(ctx.exception.code, 1)
        # Original content must be untouched.
        self.assertEqual(tex_path.read_text(), "existing content")

    def test_main_missing_template_exits(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            make_cv.main(
                [
                    "-t",
                    str(self.tmp_path / "does-not-exist.tex.jinja"),
                    "-d",
                    str(self.data_path),
                ]
            )
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
