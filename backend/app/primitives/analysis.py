"""Numerical and symbolic analysis of y = f(x) shared by the graph primitives: sampling, zeros
and vertical asymptotes.

Zeros are exact for rational functions (SymPy's real roots) and found by bisection otherwise,
then recognised as exact where they are simple (such as pi or a surd)."""

import math

import numpy as np
import sympy as sp

from app.primitives.symbolic import exact

X = sp.Symbol("x", real=True)

MAX_FEATURES = 4


def samples(f: sp.Expr, lo: float, hi: float, count: int = 801):
    numeric = sp.lambdify(X, f, "math")
    xs = np.linspace(lo, hi, count)
    ys = np.empty(count)
    for i, x in enumerate(xs):
        try:
            value = complex(numeric(float(x)))
            ys[i] = value.real if abs(value.imag) < 1e-9 else math.nan
        except (ValueError, ZeroDivisionError, OverflowError, TypeError):
            ys[i] = math.nan
    return xs, ys


def vertical_asymptotes(f: sp.Expr, lo: float, hi: float) -> list:
    if not f.is_rational_function(X):
        candidates = []
        try:
            from sympy.calculus.singularities import singularities

            found = singularities(f, X, sp.Interval(exact(lo), exact(hi)))
            if isinstance(found, sp.FiniteSet):
                candidates = list(found)
        except (NotImplementedError, ValueError, TypeError):
            return []
    else:
        denominator = sp.denom(sp.together(f))
        candidates = [r for r in sp.Poly(denominator, X).real_roots()] if denominator.has(X) else []
    out = []
    for x in candidates:
        if lo < float(x) < hi:
            try:
                limit = sp.limit(f, X, x, "+")
            except (NotImplementedError, ValueError):
                continue
            if limit.is_infinite and x not in out:
                out.append(sp.nsimplify(x))
    return sorted(out, key=float)[:MAX_FEATURES]


def zeros(expr: sp.Expr, lo: float, hi: float, poles: list) -> list:
    """The zeros of expr in [lo, hi], in order: exact for rational functions, else by
    bisection between samples that change sign (away from the poles)."""
    if expr.is_number:
        return []
    if expr.is_rational_function(X):
        numerator, denominator = sp.fraction(sp.together(expr))
        if not numerator.has(X):
            return []
        roots = []
        for root in sp.Poly(numerator, X).real_roots():
            if lo - 1e-12 <= float(root) <= hi + 1e-12 and denominator.subs(X, root) != 0:
                value = root if not isinstance(root, sp.CRootOf) else float(root)
                if value not in roots:
                    roots.append(value)
        return roots
    xs, ys = samples(expr, lo, hi, 2001)
    numeric = sp.lambdify(X, expr, "math")
    roots = []
    for i in range(len(xs) - 1):
        a, b = ys[i], ys[i + 1]
        if not (math.isfinite(a) and math.isfinite(b)):
            continue
        if a == 0:
            roots.append(float(xs[i]))
        elif a * b < 0 and all(abs(xs[i] - float(p)) > 1e-3 for p in poles):
            x0, x1 = xs[i], xs[i + 1]
            for _ in range(60):
                mid = (x0 + x1) / 2
                if numeric(x0) * numeric(mid) <= 0:
                    x1 = mid
                else:
                    x0 = mid
            roots.append(round((x0 + x1) / 2, 10))
    out = []
    for r in roots:
        guess = sp.nsimplify(r, [sp.pi], tolerance=1e-9)
        exact_root = guess if abs(float(guess) - r) < 1e-9 and sp.count_ops(guess) < 6 else r
        if all(abs(float(exact_root) - float(o)) > 1e-6 for o in out):
            out.append(exact_root)
    return out
