"""The primitive library: every validated primitive, by id (report §5.3.2, Table 5.2).

LIBRARY_VERSION lives in catalog.py, which needs no Manim; bump it there whenever a primitive
changes how it draws.
"""

from app.contracts import Primitive
from app.primitives.algebra_balance import AlgebraBalance
from app.primitives.angle_chaser import AngleChaser
from app.primitives.area_between_curves import AreaBetweenCurves
from app.primitives.area_under_curve import AreaUnderCurve
from app.primitives.bounds_interval import BoundsInterval
from app.primitives.catalog import LIBRARY_VERSION
from app.primitives.circle_theorems import CircleTheorems
from app.primitives.clock_timetable import ClockTimetable
from app.primitives.completing_square import CompletingSquare
from app.primitives.connected_rates import ConnectedRates
from app.primitives.coordinate_circle import CoordinateCircle
from app.primitives.coordinate_plotter import CoordinatePlotter
from app.primitives.curve_sketch import CurveSketch
from app.primitives.derivative_panels import DerivativePanels
from app.primitives.differentiation_stepper import DifferentiationStepper
from app.primitives.equation_transform import EquationTransform
from app.primitives.expansion_grid import ExpansionGrid
from app.primitives.fraction_model import FractionModel
from app.primitives.function_graph import FunctionGraph
from app.primitives.function_machine import FunctionMachine
from app.primitives.gradient_triangle import GradientTriangle
from app.primitives.graphical_solution import GraphicalSolution
from app.primitives.growth_decay import GrowthDecay
from app.primitives.index_laws import IndexLaws
from app.primitives.inequality_region import InequalityRegion
from app.primitives.inverse_graph import InverseGraph
from app.primitives.kinematics_graphs import KinematicsGraphs
from app.primitives.line_builder import LineBuilder
from app.primitives.number_line import NumberLine
from app.primitives.optimisation_scene import OptimisationScene
from app.primitives.parallel_perpendicular import ParallelPerpendicular
from app.primitives.percentage_bar import PercentageBar
from app.primitives.polygon_angles import PolygonAngles
from app.primitives.prime_factor_tree import PrimeFactorTree
from app.primitives.proportion_graph import ProportionGraph
from app.primitives.quadratic_explorer import QuadraticExplorer
from app.primitives.ratio_splitter import RatioSplitter
from app.primitives.secant_to_tangent import SecantToTangent
from app.primitives.sequence_pattern import SequencePattern
from app.primitives.simultaneous_equations import SimultaneousEquations
from app.primitives.standard_form import StandardForm
from app.primitives.surd_simplifier import SurdSimplifier
from app.primitives.table_of_values import TableOfValues
from app.primitives.tangent_normal import TangentNormal
from app.primitives.tangent_slide import TangentSlide
from app.primitives.travel_graph import TravelGraph
from app.primitives.unit_circle_waves import UnitCircleWaves
from app.primitives.venn_diagram import VennDiagram

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
        GrowthDecay,
        UnitCircleWaves,
        ConnectedRates,
        InverseGraph,
        SimultaneousEquations,
        TableOfValues,
        NumberLine,
        PrimeFactorTree,
        VennDiagram,
        FractionModel,
        PercentageBar,
        StandardForm,
        IndexLaws,
        SurdSimplifier,
        RatioSplitter,
        BoundsInterval,
        ClockTimetable,
        AngleChaser,
        PolygonAngles,
        CircleTheorems,
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
