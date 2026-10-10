"""The primitive library: every validated primitive, by id (report §5.3.2, Table 5.2).

Bump LIBRARY_VERSION whenever a primitive changes how it draws. The version is part of the
variant cache key, so changed primitives never reuse videos rendered by older code.
"""

from app.contracts import Primitive
from app.primitives.equation_transform import EquationTransform
from app.primitives.function_graph import FunctionGraph
from app.primitives.gradient_triangle import GradientTriangle

LIBRARY_VERSION = "0.1.0"

PRIMITIVES: dict[str, type[Primitive]] = {
    cls.primitive_id: cls for cls in (FunctionGraph, GradientTriangle, EquationTransform)
}


class UnknownPrimitiveError(KeyError):
    pass


def get_primitive(primitive_id: str) -> Primitive:
    try:
        return PRIMITIVES[primitive_id]()
    except KeyError:
        raise UnknownPrimitiveError(f"no primitive named {primitive_id!r}") from None
