"""A LaTeX cache that parallel render workers can share safely.

Manim compiles each formula in its tex directory and then deletes every non-SVG file there,
including files another process is still compiling. So each worker compiles in its own
directory, and finished SVGs are published to the shared cache with an atomic rename. Every
worker looks in the shared cache first, so a formula is compiled once for all of them, and
reads a private copy, because Manim writes a temporary file next to every SVG it reads.
"""

import os
import shutil
from pathlib import Path

import manim.mobject.text.tex_mobject as tex_mobject
from manim import config
from manim.utils import tex_file_writing

_original = tex_file_writing.tex_to_svg_file


def use_shared_tex_cache(shared_dir: Path) -> None:
    """Route this process's formula compilation through `shared_dir`."""
    shared_dir.mkdir(parents=True, exist_ok=True)

    def tex_to_svg_file(expression, environment=None, tex_template=None) -> Path:
        template = tex_template or config["tex_template"]
        if environment is not None:
            code = template.get_texcode_for_expression_in_env(expression, environment)
        else:
            code = template.get_texcode_for_expression(expression)
        name = f"{tex_file_writing.tex_hash(code)}.svg"
        shared = shared_dir / name
        private = config.get_dir("tex_dir") / name
        if private.is_file():
            return private
        if shared.is_file():
            # Manim writes a temporary file next to the SVG it reads, so it reads a private copy.
            private.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shared, private)
            return private
        compiled = _original(expression, environment, tex_template)
        partial = shared.with_name(f".{shared.stem}.{os.getpid()}.svg")
        shutil.copyfile(compiled, partial)
        partial.replace(shared)
        return compiled

    tex_mobject.tex_to_svg_file = tex_to_svg_file
