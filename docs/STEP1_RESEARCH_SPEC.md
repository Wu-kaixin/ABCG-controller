# Step 1 Research Specification

## Objective

Develop and optimize ABCG for one static unknown crowd in a bounded two-dimensional environment while preserving clean interfaces for later dynamic and decentralized extensions.

## Canonical environments

Step 1 begins with two closed environment families:

1. **Square**: width = height.
2. **Rectangle**: width != height.

The environment boundary is known to the simulator and controller safety layer as workspace geometry. It is **not** the crowd boundary.

Future scenario types must be added through the same scenario interface rather than by branching control logic on hard-coded geometry names.

## Crowd model

The crowd is represented by a finite point set

$$
X_c = \{x_j \in \mathbb{R}^2\}_{j=1}^{N_c}.
$$

For Step 1,

$$
\dot{x}_j = 0.
$$

The crowd location, size, and occupied boundary are not directly supplied to ABCG. The estimator receives observations derived from the pedestrian states.

### Moderate heterogeneity

Each pedestrian may carry bounded attributes such as radius, preferred speed, and time gap. In Step 1 these attributes are part of the model/data contract, but preferred speed and time gap do not generate motion because the crowd is static.

No scientific claim about the effect of heterogeneity is permitted until an experiment explicitly varies these attributes and measures an outcome.

## Guide model

Guide agents are external robots or designated staff represented by positions

$$
p_i \in \mathbb{R}^2,
$$

with velocity input

$$
\dot{p}_i = u_i, \qquad \|u_i\| \le u_{\max}.
$$

Step 1 assumes unrestricted inter-guide communication and globally available observations. This assumption is temporary and explicit.

## Step 1 control pipeline

The intended pipeline is

`crowd observations -> boundary estimation -> deployment-curve construction -> guide-resource allocation -> periodic target planning -> identity-preserving assignment -> velocity feedback -> safety filter -> evaluation`.

Every stage must return explicit validity/failure states. Downstream stages must not fabricate geometry or targets after an upstream failure.

## Environment/crowd separation

The square or rectangle defines the workspace

$$
\Omega_{env} \subset \mathbb{R}^2.
$$

The unknown crowd occupies an unknown subset

$$
\Omega_c \subset \Omega_{env}.
$$

The controller must not equate $\partial\Omega_{env}$ with the crowd boundary $\partial\Omega_c$.

## Extensibility contracts

### Scenario extension

Later scenarios may introduce:

- wall openings/exits;
- larger spaces;
- non-rectangular environments;
- obstacles;
- multiple connected spaces.

These changes should implement the scenario protocol without rewriting ABCG core logic.

### Dynamic crowd extension (Step 2)

Step 2 may introduce multiple crowds and dynamics including translation, dispersion, splitting, and merging. These capabilities are out of scope for Step 1.

### Decentralized extension (Step 3)

Step 3 will restrict each guide to local sensing and local communication. Interfaces for local observations, neighbor messages, crowd-group hypotheses, and distributed resource allocation are reserved now, but the Step-1 implementation must use the global/unrestricted mode.

## Step 1 success criteria

A Step-1 experiment should separately report:

1. software execution success;
2. boundary-estimation validity;
3. deployment-geometry validity;
4. resource/planning/assignment validity;
5. closed-loop convergence;
6. sampled safety diagnostics;
7. final coverage/tracking metrics.

Failures remain in the denominator. A successful process execution is not equivalent to scientific success.

## Non-claims

Step 1 does not establish:

- dynamic crowd containment;
- human behavioral response to guides;
- decentralized operation;
- communication-limited robustness;
- real-world safety or effectiveness.
