# SDR-0003: Node incident damage ratio

Status: Option A selected and implemented for experimental alpha.

## Equation or behavior

The existing behavior is retained and renamed `node_incident_damage_ratio`:

```text
ratio_i = sum_j Z_edge[i, j] / (sum_(a<b) Z_edge[a, b] + epsilon)
```

Every unique edge contributes to two incident nodes. When total edge damage is
non-zero, the node values therefore sum to approximately two. They are not
probabilities and are not a partition of unity.

## Source

The definition comes from the stable specification in this repository and PR #1
commit `edbbc1e8990297dbecb72fd83172153946fc7117`.

## Engineering assumptions

The metric represents incident evidence relative to total unique-edge evidence. It is
used for candidate ranking only and does not establish physical causality.

## Alternatives considered

Option B, division by twice the unique-edge total, would produce a probability-like
sum of one. It was rejected for this version because it silently changes the numerical
meaning frozen in PR #1.

## Compatibility impact

The public result field is renamed to `node_incident_damage_ratio`. A compatibility
property named `node_concentration` returns the same unchanged values. The model
manifest stores `mcift.node-incident-damage-ratio.v1` to make semantics explicit.

## Versioning impact

Changing the denominator or treating values as probabilities requires a new node
metric identifier, schema migration, updated fixtures, and a new SDR.

## Approval status

Option A is implemented for compatibility. It is not a causal-localization claim.
