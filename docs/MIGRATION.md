# Step 1 migration record

## Scope and source revisions

This migration establishes a small runnable Step-1 project on `ABCG-controller/main`.
It does not modify the source repository or the existing destination `static-crowd-area` branch.

| Source | Pinned commit | Use |
|---|---|---|
| [Crowd-Management main](https://github.com/Wu-kaixin/Crowd-Management/tree/2e87d4914b9f3a65e363994cb00bc4938b010a2f) | `2e87d4914b9f3a65e363994cb00bc4938b010a2f` | Established static ABCG algorithms and regression tests |
| [Crowd-Management feature/jupedsim-step1](https://github.com/Wu-kaixin/Crowd-Management/tree/fe45551e8b0a8c14dd5d5734b445a46c83e302c5) | `fe45551e8b0a8c14dd5d5734b445a46c83e302c5` | Selected code snapshot, JuPedSim source, heterogeneity and alpha boundary updates |
| [ABCG-controller static-crowd-area](https://github.com/Wu-kaixin/ABCG-controller/tree/fba02ec5e3bd6ce1a01c803caab95d5895d63e7c) | `fba02ec5e3bd6ce1a01c803caab95d5895d63e7c` | Scenario and decentralized interface contracts, scenario tests |
| ABCG-controller main before migration | `74ec359199845c2571a82cf4c71df8dca010b227` | Preserved parent history and MIT license |

The source `math-verification-main-v1` branch was also compared: its `src/` and
`tests/` differ from source main only in a package initialization line. Its old
mathematical reports do not certify the adapted deployment policy or new runner.

## File mapping

Paths in the first column are relative to `Crowd-Management/src/crowd_management/`.

| Source | Destination | Treatment |
|---|---|---|
| `controllers/abcg_v2.py` | `controller/abcg.py` | Retained feedback/state machine and episode API; runtime `dt*k_p` validation added |
| `controllers/safety.py` | `controller/safety.py` | Retained deterministic velocity half-space/speed-ball projection |
| `controllers/assignment.py` | `controller/assignment.py` | Retained Hungarian assignment and reserve/identity contracts |
| `controllers/resources.py` | `controller/resources.py` | Retained length-based count policy, hysteresis and capacity state |
| `controllers/periodic_arc_cvt.py` | `controller/coverage.py` | Retained uniform periodic CVT; added explicit weighted discrete Lloyd planner |
| `estimation/boundary_v2.py` | `controller/boundary.py` | Retained radial/alpha/bootstrap estimators and strict normal-offset checks; added separate buffer deployment builder |
| `estimation/boundary.py` | `controller/radial.py` | Retained radial primitives required by the estimator |
| `geometry/arclength.py` | `controller/arclength.py` | Retained periodic sampling, distances, self-intersection and gap helpers |
| `types.py` | `controller/common.py` | Kept only required numerical helpers; omitted old configuration hierarchy |
| `crowd/jupedsim_static.py` | `environment.py` | Adapted spacing, seeded generation and finite point-cloud validation |
| `crowd/heterogeneity.py` | `environment.py` | Simplified bounded sampling; added demand weight and finite validation |
| `runtime/*` | `run.py` | Retained the independent-seed multiprocessing approach with a small executor, not the old runtime package |
| `reporting/*`, experiment artifact writers | `run.py`, `visualization.py` | Simplified strict JSON, numeric traces, provenance and shared scene plotting |
| Seven core test files | `tests/` | Imports redirected; synthetic boundary fixtures made local to tests |
| Target branch `scenarios/*`, `interfaces/decentralized.py` | `scene.py`, `interfaces.py` | Flattened layout; opening names additionally validated |

Both repositories use the same MIT copyright/license. The target LICENSE is unchanged.
No copied module imports `crowd_management`; the source checkout is not required at runtime.

## Deliberate differences

1. **Minimal layout.** No nested experiment/evaluation/reporting pipeline, old G6/PR6
   orchestration, frozen report artifacts, presentations, Mathematica reports, or
   old evacuation material is copied. These remain accessible at the pinned source.
2. **Real initial motion.** Guide initial states come from the room perimeter or
   explicit user positions, independently of ABCG targets. The previous endpoint
   baseline-as-initial-state runner is not reused.
3. **Separate crowd and deployment geometry.** Estimate with zero offset first;
   build an explicit Shapely polygon buffer and parameterize that deployment curve
   by its own length. Original normal-offset functionality and its failure tests
   remain available. The new policy is not claimed mathematically identical.
4. **No truth leakage.** The environment alone sees spawn vertices. The estimator
   receives points; the demand model receives observed individual weights. Room
   geometry is known to safety. Spawn support is not treated as the true occupied
   crowd boundary in reported metrics.
5. **Heterogeneity has explicit roles.** Radii influence spacing and conservative
   scalar safety thresholds; weights influence discrete coverage targets. Desired
   speeds and time gaps are stored but inactive in a static experiment.
6. **Conservative safety semantics.** The source iterative projection is preserved;
   it is not relabeled as a certified optimal QP, ORCA, or a CBF. Failure to satisfy
   its tolerance reports a failure. Executed piecewise-linear paths are checked
   independently, including initial states.
7. **No silent fallback.** No dynamic or communication-limited mode, unknown YAML
   parameter, invalid offset, insufficient guide capacity or failed plan is
   silently converted into a successful static run.
8. **Research metrics.** Resource `g_req` is an average arc spacing budget. Weighted
   CVT does not certify the worst gap. Final gaps, errors and safety are reported
   independently. No dynamic-containment or globally optimal deployment claim.

## Validation

Local suite: **78 tests passed** on Python 3.12, including 60 migrated core/scenario
checks and 18 integration checks. The two default seed-0 trajectories were also
compared between serial and process-pool execution and were exactly identical.

The checked-in [validation.json](validation.json) and
[validation_runs.csv](validation_runs.csv) contain the results for both provided
scenes with seeds 0–9, including status, error, gaps and safety margins.
These are a small migration smoke benchmark, not a held-out robustness study.

Commands:

```bash
python -m pytest -q
python run.py --config configs/step1/square.yaml --output results/square_batch --seeds 0 1 2 3 4 5 6 7 8 9 --workers auto --no-plots
python run.py --config configs/step1/rectangle.yaml --output results/rectangle_batch --seeds 0 1 2 3 4 5 6 7 8 9 --workers auto --no-plots
```

CI runs Python 3.12 tests on Ubuntu and Windows. Local validation was performed on
Linux; CI status is separate from the local result. The full trajectory artifacts
are reproducible via the commands and are intentionally ignored by Git.
