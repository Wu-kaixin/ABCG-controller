# ABCG Step 1 Redevelopment Plan

This repository restarts the controller work from a narrow Step-1 contract instead of copying the full historical Crowd-Management codebase.

## Phase A — scenario and data contracts

Status: **started on `static-crowd-area`**.

- closed square environment;
- closed rectangle environment;
- environment/crowd-boundary separation;
- static crowd state;
- moderate heterogeneity attributes;
- future wall-opening and decentralized interfaces.

## Phase B — import only the reusable ABCG core

Port/re-derive modules individually from the existing Crowd-Management implementation only after each module's role and test contract is clear:

1. crowd-boundary estimator;
2. deployment-curve construction;
3. guide resource allocation;
4. periodic boundary-coverage planner;
5. identity-preserving assignment;
6. guide velocity feedback;
7. safety filter;
8. convergence/failure state machine.

Do not copy old benchmark orchestration, legacy branches, dynamic G7 logic, or evaluator-specific truth into the new controller core.

## Phase C — fix the known Step-1 geometry bottleneck

The previous source-pairing study identified deployment/safety offset self-intersection as the dominant boundary failure mode. The restarted implementation should therefore keep crowd-boundary estimation and deployment-curve construction as separate modules.

Candidate deployment construction to test:

$$
\widehat{\Omega}_d = \widehat{\Omega}_c \oplus B_{d_s},
\qquad
\Gamma_d = \partial \widehat{\Omega}_d.
$$

This is a candidate design, not yet a validated result. The legacy pointwise normal offset should be retained as an ablation baseline when it is ported.

## Phase D — canonical Step-1 optimization

Optimize and validate first on the two canonical environments. Experiments should cover multiple crowd locations, sizes, crowd point realizations, guide initial states, pedestrian heterogeneity seeds, and guide-resource levels.

Required outcome hierarchy:

- execution success;
- boundary validity;
- deployment-curve validity;
- planner/resource/assignment validity;
- closed-loop convergence;
- sampled safety diagnostics;
- final coverage and tracking metrics.

Development seeds and final holdout seeds must be separated before parameter tuning.

## Phase E — Step-1 freeze criteria

Step 1 may be frozen only after:

- both canonical environments have reproducible configs;
- all failure states remain explicit;
- controller truth leakage tests pass;
- the deployment geometry no longer fails systematically;
- the closed-loop controller is evaluated over held-out seeds;
- README numbers are generated from frozen artifacts;
- mathematical claims are aligned with the implemented discrete-time controller.

## Reserved future stages

### Step 2

Openings/exits, larger environments, multiple dynamic crowds, translation, dispersion, splitting, and merging.

### Step 3

Local sensing, local communication, decentralized crowd search/group identification, distributed guide allocation, and dynamic containment.
