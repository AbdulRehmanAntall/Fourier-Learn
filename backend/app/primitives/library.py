"""The primitive library: every validated primitive, by id (report §5.3.2, Table 5.2).

LIBRARY_VERSION lives in catalog.py, which needs no Manim; bump it there whenever a primitive
changes how it draws.
"""

from app.contracts import Primitive
from app.primitives.area_under_curve import AreaUnderCurve
from app.primitives.catalog import LIBRARY_VERSION
from app.primitives.equation_transform import EquationTransform
from app.primitives.function_graph import FunctionGraph
from app.primitives.gradient_triangle import GradientTriangle
from app.primitives.secant_to_tangent import SecantToTangent
from app.primitives.tangent_slide import TangentSlide
from app.primitives.travel_graph import TravelGraph

PRIMITIVES: dict[str, type[Primitive]] = {
    cls.primitive_id: cls
    for cls in (
        FunctionGraph,
        GradientTriangle,
        TangentSlide,
        SecantToTangent,
        TravelGraph,
        AreaUnderCurve,
        EquationTransform,
    )
}


class UnknownPrimitiveError(KeyError):
    pass


def get_primitive(primitive_id: str) -> Primitive:
    try:
        return PRIMITIVES[primitive_id]()
    except KeyError:
        raise UnknownPrimitiveError(f"no primitive named {primitive_id!r}") from None


__all__ = ["LIBRARY_VERSION", "PRIMITIVES", "UnknownPrimitiveError", "get_primitive"]
