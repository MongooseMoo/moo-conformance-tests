# Portable checkpoint fault fixture

## Goal
Q authorized making the checkpoint fixture and diagnostics portable to Barn
while preserving every failure, callback-context and recovery assertion in #163.

## State
Isolated controller repair based on main. Barn's combined candidate now fails
only the two checkpoint fixture cases; its ordinary PR CI passes.

## Decisions and why
Smallest change, about 45 production lines: obstruct both supported temporary
paths (Test.db.new.#1# and Test.db.tmp), validate both before creating/removing
owned symlinks, and keep publication obstruction unchanged. Add a nonempty
contains_any list to the existing log assertion so each case can require its
branch-specific diagnostic from either supported engine. Existing contains
and not_contains assertions retain their meanings. No engine-name inference.
Barn source: db/format/checkpoint_stage.go BeginCheckpoint and Serialize;
db/format/checkpoint_publication.go publishHashedCheckpointPair.

## Surprises
The managed profile.json placeholder is not populated by current CI templates;
do not infer engine identity from a nonexistent manifest in the server directory.

## Next step
Publish this controller repair, read PR CI, merge after successful validation,
then update #163 data and run both candidate PRs against the prepared Barn head.
