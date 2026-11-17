# Oracle selection during the Toast 2.8 cutover

## Goal

Select the Toast revision matching the admitted expectation data for data PRs,
controller PRs and default-branch pushes, so the 2.8 data can land without
leaving push and controller checks on the previous oracle.

## State

The transition repair merged as #220, followed by the complete expectation
data in #217. The subsequent universal-pin cleanup removes this transitional
selector and its migration-only tests after the remaining data PRs land.

## Decisions and why

Use the 2.8-only flag argument suite already present in the complete expectation
update to identify upgraded data. Data PRs select their candidate tree;
controller and neutral runs select trusted data. Both Toast jobs consume the
same selected revision. Execute the real shell selector in the existing test
file for every combination of mode and data generation, including rejection
of an unadmitted mode.

## Surprises

The earlier mode-only staging selected the new oracle for unrelated old-data
PRs and the old oracle after the upgraded data became the trusted base.

## Next step

This transition is complete. Current delivery continues in
ci-universal-toast-2.8.md, which records the universal-pin cleanup.
