"""ABCG Step-1 algorithms; no simulator or file I/O dependencies."""
from .abcg import (
    ABCGv2Config, ABCGv2Controller, ConvergenceStateMachine, ControlOutput,
    EpisodeResult, integrate_guide_positions, nominal_guide_velocity,
)
from .assignment import (
    AssignmentConfig, AssignmentResult, IdentityPreservingAssigner,
    assign_guides_to_targets,
)
from .coverage import (
    CoveragePlan, PeriodicArcCVT, PeriodicArcCVTConfig, equal_arc_target_s,
    plan_equal_arc_coverage, plan_periodic_arc_coverage, periodic_uniform_coverage_cost,
)
from .resources import (
    ResourceDecision, ResourcePolicy, ResourcePolicyConfig, allocate_guide_resources,
)
from .safety import SafetyProjectionResult, VelocitySafetyConfig, project_velocity_safety

ABCGController = ABCGv2Controller
