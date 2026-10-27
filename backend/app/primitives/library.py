"""The primitive library: every validated primitive, by id (report §5.3.2, Table 5.2).

LIBRARY_VERSION lives in catalog.py, which needs no Manim; bump it there whenever a primitive
changes how it draws.
"""

from app.contracts import Primitive
from app.primitives.algebra_balance import AlgebraBalance
from app.primitives.area_between_curves import AreaBetweenCurves
from app.primitives.area_under_curve import AreaUnderCurve
from app.primitives.catalog import LIBRARY_VERSION
from app.primitives.completing_square import CompletingSquare
from app.primitives.coordinate_circle import CoordinateCircle
from app.primitives.coordinate_plotter import CoordinatePlotter
from app.primitives.curve_sketch import CurveSketch
from app.primitives.derivative_panels import DerivativePanels
from app.primitives.differentiation_stepper import DifferentiationStepper
from app.primitives.equation_transform import EquationTransform
from app.primitives.expansion_grid import ExpansionGrid
from app.primitives.function_graph import FunctionGraph
from app.primitives.function_machine import FunctionMachine
from app.primitives.gradient_triangle import GradientTriangle
from app.primitives.graphical_solution import GraphicalSolution
from app.primitives.inequality_region import InequalityRegion
from app.primitives.kinematics_graphs import KinematicsGraphs
from app.primitives.line_builder import LineBuilder
from app.primitives.optimisation_scene import OptimisationScene
from app.primitives.parallel_perpendicular import ParallelPerpendicular
from app.primitives.proportion_graph import ProportionGraph
from app.primitives.quadratic_explorer import QuadraticExplorer
from app.primitives.secant_to_tangent import SecantToTangent
from app.primitives.sequence_pattern import SequencePattern
from app.primitives.tangent_normal import TangentNormal
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
        AlgebraBalance,
        ExpansionGrid,
        CompletingSquare,
        QuadraticExplorer,
        InequalityRegion,
        SequencePattern,
        ProportionGraph,
        CurveSketch,
        FunctionMachine,
        GraphicalSolution,
        CoordinatePlotter,
        LineBuilder,
        ParallelPerpendicular,
        DerivativePanels,
        DifferentiationStepper,
        TangentNormal,
        AreaBetweenCurves,
        KinematicsGraphs,
        OptimisationScene,
        CoordinateCircle,
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
