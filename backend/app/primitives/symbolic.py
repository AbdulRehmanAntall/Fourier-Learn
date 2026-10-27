"""SymPy helpers shared by the primitives: safe parsing, checks and number formatting (§5.3.3).

Expressions come from a language model, so they are never evaluated as Python. Before SymPy
parses a string, it must contain only arithmetic characters, and every name in it must be a
known function or an allowed variable.
"""

import ast
import math
import re
from collections.abc import Collection, Iterable
from decimal import ROUND_HALF_UP, Decimal
from tokenize import TokenError

import sympy as sp
from sympy.parsing.sympy_parser import convert_xor, parse_expr, standard_transformations

MAX_EXPRESSION_LENGTH = 200

FUNCTIONS: dict[str, object] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "sqrt": sp.sqrt,
    "exp": sp.exp,
    "log": sp.log,
    "ln": sp.log,
    "abs": sp.Abs,
    "Abs": sp.Abs,
    "pi": sp.pi,
}

_ALLOWED_CHARACTERS = re.compile(r"[0-9A-Za-z_+\-*/^(). ]*")
# "x.real" would reach a Python attribute, so a dot may only be part of a number.
_ATTRIBUTE = re.compile(r"\.\s*[A-Za-z_]")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# A variable: one letter, optionally with a subscript, e.g. x, m, y_1, x_A.
_VARIABLE = re.compile(r"[A-Za-z](_[A-Za-z0-9]+)?")
_TRANSFORMATIONS = (*standard_transformations, convert_xor)


class ExpressionError(ValueError):
    """An expression that is not well formed or uses names that are not allowed."""


def parse_expression(
    text: str, variables: Collection[str] | None = None, *, evaluate: bool = True
) -> sp.Expr:
    """Parse one expression in SymPy syntax, e.g. "x**2 - 3*x" or "(8 - 2)/(4 - 1)".

    `variables` lists the allowed variable names; None allows any single-letter variable,
    optionally subscripted. With `evaluate=False` the expression keeps its written form
    ("6/3" stays a fraction), which is what is displayed.
    """
    if len(text) > MAX_EXPRESSION_LENGTH:
        raise ExpressionError(f"longer than {MAX_EXPRESSION_LENGTH} characters")
    if not text.strip():
        raise ExpressionError("empty expression")
    if not _ALLOWED_CHARACTERS.fullmatch(text) or "__" in text or _ATTRIBUTE.search(text):
        raise ExpressionError(f"contains characters that are not allowed: {text!r}")

    names = {}
    for name in _NAME.findall(text):
        if name in FUNCTIONS:
            continue
        allowed = name in variables if variables is not None else _VARIABLE.fullmatch(name)
        if not allowed or name == "E":
            raise ExpressionError(f"unknown name {name!r}")
        names[name] = sp.Symbol(name, real=True)

    try:
        expr = parse_expr(
            text,
            local_dict={**FUNCTIONS, **names},
            transformations=_TRANSFORMATIONS,
            evaluate=evaluate,
        )
    except (SyntaxError, TypeError, ValueError, TokenError) as error:
        raise ExpressionError(f"cannot parse {text!r}") from error
    if not isinstance(expr, sp.Expr):
        raise ExpressionError(f"not an expression: {text!r}")
    return expr


def parse_equation(text: str, variables: Collection[str] | None = None, *, evaluate: bool = True):
    """Parse "lhs = rhs" into its two sides."""
    if text.count("=") != 1:
        raise ExpressionError(f"an equation needs exactly one '=': {text!r}")
    lhs, rhs = text.split("=")
    return (
        parse_expression(lhs, variables, evaluate=evaluate),
        parse_expression(rhs, variables, evaluate=evaluate),
    )


def is_real_and_finite(value: sp.Expr) -> bool:
    value = sp.N(value)
    return bool(value.is_real) and bool(value.is_finite)


def sample_points(lo: float, hi: float, count: int = 41) -> list[sp.Rational]:
    """Evenly spaced exact sample points across [lo, hi], both ends included."""
    lo_r, hi_r = exact(lo), exact(hi)
    return [lo_r + (hi_r - lo_r) * sp.Rational(i, count - 1) for i in range(count)]


def failing_samples(expr: sp.Expr, variable: sp.Symbol, points: Iterable[sp.Expr]) -> list:
    """The sample points at which `expr` is not real and finite."""
    bad = []
    for point in points:
        try:
            ok = is_real_and_finite(expr.subs(variable, point))
        except (TypeError, ValueError, ZeroDivisionError):
            ok = False
        if not ok:
            bad.append(point)
    return bad


def exact(value: float | int | str) -> sp.Rational:
    """A number as an exact rational: 0.1 becomes 1/10, not a binary approximation."""
    return sp.nsimplify(str(value), rational=True)


def equivalent(a: sp.Expr, b: sp.Expr) -> bool:
    return sp.simplify(a - b) == 0


def format_number(value: sp.Expr) -> str:
    """A number as narration text: "6", "-1/2", or a decimal rounded to 2 places."""
    value = sp.nsimplify(value) if not isinstance(value, sp.Rational) else value
    if isinstance(value, sp.Integer):
        return str(int(value))
    if isinstance(value, sp.Rational) and abs(value.q) <= 100:
        return f"{value.p}/{value.q}"
    decimal = f"{float(sp.N(value)):.2f}".rstrip("0").rstrip(".")
    return "0" if decimal == "-0" else decimal


def latex_number(value: sp.Expr) -> str:
    """A number as LaTeX: "6", "-\\frac{1}{2}", or a rounded decimal."""
    text = format_number(value)
    if "/" in text:
        numerator, denominator = text.split("/")
        sign = "-" if numerator.startswith("-") else ""
        return rf"{sign}\frac{{{numerator.lstrip('-')}}}{{{denominator}}}"
    return text


_PRECEDENCE = {ast.Add: 1, ast.Sub: 1, ast.Mult: 2, ast.Div: 3, ast.Pow: 5}
_FUNCTION_LATEX = {
    "sin": r"\sin",
    "cos": r"\cos",
    "tan": r"\tan",
    "ln": r"\ln",
    "log": r"\log",
}


def written_latex(text: str) -> str:
    """LaTeX of an expression or equation exactly as written, for display.

    SymPy's printer reorders terms and rewrites unevaluated fractions ((3/4)*(8/9) comes out
    as 3 * 1/4 * 8 * 1/9), but a line of working must look the way it was written. The text is
    first checked by `parse_expression`, so only safe arithmetic reaches the Python parser.
    """
    if "=" in text:
        parse_equation(text)
        return " = ".join(written_latex(side) for side in text.split("="))
    parse_expression(text)
    return _to_latex(ast.parse(text.strip().replace("^", "**"), mode="eval").body)


def _to_latex(node: ast.expr) -> str:
    if isinstance(node, ast.Constant):
        return _number(node.value)
    if isinstance(node, ast.Name):
        if node.id == "pi":
            return r"\pi"
        base, _, subscript = node.id.partition("_")
        return f"{base}_{{{subscript}}}" if subscript else base
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return "-" + _wrap(node.operand, 2)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _to_latex(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        argument = _to_latex(node.args[0])
        name = node.func.id
        if name == "sqrt":
            return rf"\sqrt{{{argument}}}"
        if name in ("abs", "Abs"):
            return rf"\left|{argument}\right|"
        if name == "exp":
            return f"e^{{{argument}}}"
        return rf"{_FUNCTION_LATEX[name]}\left({argument}\right)"
    if isinstance(node, ast.BinOp):
        op = type(node.op)
        if op is ast.Div:
            return rf"\frac{{{_to_latex(node.left)}}}{{{_to_latex(node.right)}}}"
        if op is ast.Pow:
            return f"{_wrap(node.left, 6)}^{{{_to_latex(node.right)}}}"
        if op is ast.Mult:
            left, right = _wrap(node.left, 2), _right_operand(node.right, 2)
            # Write 2x, 3(x - 4) and (x - 2)(x - 3) side by side, but keep the sign where
            # juxtaposition would misread: 3 × 4, x × (-1), and fractions such as 3/4 × 8/9.
            needs_sign = right[0].isdigit() or right.startswith(r"\frac")
            needs_sign = needs_sign or isinstance(node.right, ast.UnaryOp)
            if needs_sign or isinstance(node.left, ast.BinOp) and type(node.left.op) is ast.Div:
                return rf"{left} \times {right}"
            return f"{left} {right}"
        sign = " + " if op is ast.Add else " - "
        # a - (b + c) keeps its brackets; a + (b + c) does not need them.
        right = _right_operand(node.right, 2 if op is ast.Sub else 1)
        return _to_latex(node.left) + sign + right
    raise ExpressionError("unsupported expression")  # pragma: no cover


def _right_operand(node: ast.expr, minimum: int) -> str:
    """A negative right operand keeps its brackets: 3 - (-2), x × (-1)."""
    if isinstance(node, ast.UnaryOp):
        return rf"\left({_to_latex(node)}\right)"
    return _wrap(node, minimum)


def _wrap(node: ast.expr, minimum: int) -> str:
    """LaTeX of `node`, in brackets if it binds less tightly than `minimum`."""
    text = _to_latex(node)
    if isinstance(node, ast.BinOp):
        precedence = _PRECEDENCE[type(node.op)]
    elif isinstance(node, ast.UnaryOp):
        precedence = 2
    else:
        return text
    return rf"\left({text}\right)" if precedence < minimum else text


def _number(value) -> str:
    return (
        str(int(value)) if float(value).is_integer() and not isinstance(value, bool) else str(value)
    )


def format_sf(value: sp.Expr | float, figures: int = 3) -> str:
    """A number to `figures` significant figures, as O Level states non-exact answers: 3.61,
    1250, 0.0123. Halves round up (2.625 to 2.63), from the exact value, not from a float.
    Whole numbers are shown in full. Trailing zeros are kept when the value was rounded (18.03
    is 18.0) and dropped when it is exact (2.5, not 2.50)."""
    exact_value = sp.N(value, 30)
    number = float(exact_value)
    if number == 0:
        return "0"
    if number.is_integer():
        return str(int(number))
    places = figures - 1 - math.floor(math.log10(abs(number)))
    quantum = Decimal(1).scaleb(-places)
    rounded = Decimal(str(exact_value)).quantize(quantum, rounding=ROUND_HALF_UP)
    if places <= 0:
        return str(int(rounded))
    text = format(rounded, "f")
    exact = abs(rounded - Decimal(str(exact_value))) <= Decimal("1e-12") * abs(rounded)
    if exact:
        text = text.rstrip("0").rstrip(".")
    return "0" if float(text) == 0 else text


def is_simple_exact(value: sp.Expr) -> bool:
    """Whether a value is worth showing exactly: a fraction with a small denominator, or a surd
    such as 2*sqrt(3) or sqrt(13)/2 with small numbers."""
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational):
        return abs(value.q) <= 100
    if value.free_symbols or not value.is_real or value.has(sp.pi, sp.exp, sp.log, sp.sin):
        return False
    return value.is_algebraic and sp.count_ops(value) <= 6 and len(str(value)) <= 16


def format_value(value: sp.Expr | float) -> str:
    """A number as narration text: exact when simple ("3/4", "2*sqrt(3)" read as "2 root 3"),
    otherwise to 3 significant figures. A Python float is a measurement, never made exact."""
    if isinstance(value, float):
        return format_sf(value)
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational) and abs(value.q) <= 100:
        return format_number(value)
    if is_simple_exact(value):
        return _speak_surd(str(value))
    return format_sf(value)


def latex_value(value: sp.Expr | float) -> str:
    """A number as LaTeX: exact when simple (\\frac{3}{4}, 2\\sqrt{3}), otherwise to 3
    significant figures."""
    if isinstance(value, float):
        return format_sf(value)
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational) and abs(value.q) <= 100:
        return latex_number(value)
    if is_simple_exact(value):
        return sp.latex(value)
    return format_sf(value)


def latex_approx(value: sp.Expr) -> str:
    """Exact and decimal together for a surd, e.g. \\sqrt{13} \\approx 3.61; a fraction or an
    integer alone."""
    value = sp.nsimplify(value)
    if isinstance(value, sp.Rational) and abs(value.q) <= 100:
        return latex_number(value)
    if is_simple_exact(value):
        return rf"{sp.latex(value)} \approx {format_sf(value)}"
    return format_sf(value)


def _speak_surd(text: str) -> str:
    return re.sub(r"sqrt\((\d+)\)", r"root \1", text).replace("*", " ")


def tidy_latex(expr: sp.Expr) -> str:
    """LaTeX of a computed expression in the order a teacher writes it: highest power first
    (-2x^2 + 4x + 1), and otherwise a positive term before a negative one (v - u rather than
    -u + v, 3 - x rather than -x + 3)."""
    expr = sp.sympify(expr)
    numerator, denominator = sp.fraction(sp.together(expr)) if _is_fraction(expr) else (expr, 1)
    if denominator != 1:
        top, bottom = tidy_latex(numerator), tidy_latex(denominator)
        return rf"\frac{{{top}}}{{{bottom}}}"
    if not isinstance(expr, sp.Add):
        return sp.latex(expr)
    terms = list(expr.as_ordered_terms())
    symbols = expr.free_symbols
    one_variable_polynomial = len(symbols) == 1 and expr.is_polynomial(*symbols)
    leads_by_degree = one_variable_polynomial and sp.degree(terms[0], *symbols) > 0
    if _negative(terms[0]) and not leads_by_degree:
        first_positive = next((t for t in terms if not _negative(t)), None)
        if first_positive is not None:
            terms.remove(first_positive)
            terms.insert(0, first_positive)
    text = sp.latex(terms[0])
    for term in terms[1:]:
        text += f" - {sp.latex(-term)}" if _negative(term) else f" + {sp.latex(term)}"
    return text


def _negative(term: sp.Expr) -> bool:
    coefficient, _ = term.as_coeff_Mul()
    return bool(coefficient.is_negative)


def _is_fraction(expr: sp.Expr) -> bool:
    _, denominator = sp.fraction(sp.together(expr))
    return denominator != 1 and not denominator.is_number


def latex_with_pi(value: sp.Expr, approx: bool = True) -> str:
    """A number that may be a multiple of pi, exactly: 20\\pi, \\frac{25}{9\\pi}, with its
    3 s.f. value beside it when `approx`; otherwise as `latex_approx`."""
    value = sp.nsimplify(value, [sp.pi])
    for power in (1, -1):
        ratio = sp.nsimplify(value / sp.pi**power)
        if value.has(sp.pi) and isinstance(ratio, sp.Rational) and abs(ratio.q) <= 1000:
            numerator, denominator = ratio.p, ratio.q
            if power == 1:
                top = (
                    r"\pi"
                    if numerator == 1
                    else (r"-\pi" if numerator == -1 else rf"{numerator}\pi")
                )
                exact_tex = top if denominator == 1 else rf"\frac{{{top}}}{{{denominator}}}"
            else:
                bottom = r"\pi" if denominator == 1 else rf"{denominator}\pi"
                exact_tex = rf"\frac{{{numerator}}}{{{bottom}}}"
            return rf"{exact_tex} \approx {format_sf(value)}" if approx else exact_tex
    return latex_approx(value) if approx else latex_value(value)
