# ABCG Controller

Adaptive Boundary-Coverage Guidance (ABCG) research repository.

## Active branch: `static-crowd-area`

This branch restarts Step 1 from a deliberately narrow and extensible research contract.

### Step 1 scope

- one **static**, **unknown** crowd;
- one bounded 2-D environment;
- initial environment types: **closed square** and **closed rectangle**;
- crowd geometry is **not** supplied to ABCG;
- guide agents may use global observations and unrestricted communication in Step 1;
- moderate crowd heterogeneity is represented explicitly;
- guide dynamics use velocity control;
- interfaces are reserved for future decentralized sensing/communication, but those limitations are **not active** in Step 1.

The environment boundary and the crowd boundary are different objects. The square/rectangle geometry defines the experimental workspace only. ABCG must estimate the crowd boundary from observed pedestrian positions.

## Research stages

### Step 1 — static crowd in closed areas

Establish and optimize the complete ABCG pipeline in controlled square and rectangular environments:

`observations -> crowd-boundary estimation -> deployment curve -> resource allocation -> target planning -> assignment -> guide velocity control -> safety filter -> evaluation`

Only Step 1 is implemented on this branch.

### Step 2 — future work

Introduce openings and larger/multiple environments, then dynamic crowds that may move, disperse, split, or merge.

### Step 3 — future work

Develop decentralized guide-agent algorithms under local sensing and local communication for crowd search, group identification, guide allocation, and dynamic containment.

## Repository layout

- `configs/step1/` — canonical square/rectangle Step-1 scenarios
- `docs/STEP1_RESEARCH_SPEC.md` — authoritative research contract
- `src/abcg_controller/scenarios/` — extensible environment interfaces
- `src/abcg_controller/crowd/` — crowd state and heterogeneity interfaces
- `src/abcg_controller/interfaces/` — future decentralized interfaces
- `tests/` — contract/regression tests

## Current status

This branch currently establishes the Step-1 research architecture and scenario contracts. It does **not** yet claim that the ABCG controller has been re-optimized or revalidated in this new repository.
