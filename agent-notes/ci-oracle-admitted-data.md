# Oracle selection during the Toast 2.8 cutover

## Goal

Select the Toast revision matching the admitted expectation data for data PRs,
controller PRs and default-branch pushes, so the 2.8 data can land without
leaving push and controller checks on the previous oracle.

## State

Updated the existing reusable workflow and its workflow tests. Publication and
CI are next. No expectation data changes.

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

Publish the controller-only PR, require the existing CI, then merge before
conformance #217 and remove the transitional selector after the data cutover.
