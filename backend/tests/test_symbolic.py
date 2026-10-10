import pytest
import sympy as sp

from app.primitives.symbolic import (
    ExpressionError,
    equivalent,
    exact,
    failing_samples,
    format_number,
    latex_number,
    parse_equation,
    parse_expression,
    sample_points,
    written_latex,
)

X = sp.Symbol("x", real=True)


@pytest.mark.parametrize(
    "text",
    [
        '__import__("os").system("ls")',
        "x.n()",
        "exec(1)",
        "open(x)",
        "lambda: 1",
        "x; y",
        "[x]",
        "E**x",
        "1e5",
        "",
        "x" * 201,
    ],
)
def test_anything_but_plain_maths_is_refused(text):
    with pytest.raises(ExpressionError):
        parse_expression(text)


def test_allowed_variables_can_be_restricted():
    assert parse_expression("x**2 - 3*x", {"x"}) == X**2 - 3 * X
    with pytest.raises(ExpressionError, match="unknown name 'y'"):
        parse_expression("x + y", {"x"})


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        ("(8 - 2)/(4 - 1)", r"\frac{8 - 2}{4 - 1}"),
        ("6/3", r"\frac{6}{3}"),
        ("(3/4)*(8/9)", r"\frac{3}{4} \times \frac{8}{9}"),
        ("3*(x - 4) = 2*x + 1", r"3 \left(x - 4\right) = 2 x + 1"),
        ("(x - 2)*(x - 3)", r"\left(x - 2\right) \left(x - 3\right)"),
        ("-0.5*x + 4", "-0.5 x + 4"),
        ("x^3 - 3*x", "x^{3} - 3 x"),
        ("3*4", r"3 \times 4"),
        ("3 - (-2)", r"3 - \left(-2\right)"),
        ("a - (b + c)", r"a - \left(b + c\right)"),
        ("y_1 + sqrt(x)", r"y_{1} + \sqrt{x}"),
        ("2*sin(x) + ln(x)", r"2 \sin\left(x\right) + \ln\left(x\right)"),
    ],
)
def test_display_keeps_the_written_form(text, shown):
    # SymPy's printer would reorder terms and rewrite (3/4)*(8/9) as 3 * 1/4 * 8 * 1/9.
    assert written_latex(text) == shown


def test_display_refuses_what_parsing_refuses():
    with pytest.raises(ExpressionError):
        written_latex('__import__("os")')


def test_evaluated_form_is_used_for_checking():
    assert parse_expression("6/3") == 2


def test_equations_and_equivalence():
    lhs, rhs = parse_equation("2*x + 3 = 7")
    assert (lhs, rhs) == (2 * X + 3, 7)
    with pytest.raises(ExpressionError):
        parse_equation("x = 1 = 2")
    assert equivalent(parse_expression("x**2 - 1"), parse_expression("(x - 1)*(x + 1)"))
    assert not equivalent(parse_expression("6/4"), parse_expression("2"))


def test_domain_samples():
    assert failing_samples(1 / X, X, sample_points(-1, 1, 5)) == [0]
    assert failing_samples(X**2, X, sample_points(-3, 3)) == []


def test_numbers_are_exact_and_formatted_for_narration_and_latex():
    assert exact(0.1) * 3 == sp.Rational(3, 10)
    assert format_number(sp.Integer(6)) == "6"
    assert format_number(sp.Rational(-1, 2)) == "-1/2"
    assert format_number(sp.sqrt(2)) == "1.41"
    assert latex_number(sp.Rational(-1, 2)) == r"-\frac{1}{2}"
