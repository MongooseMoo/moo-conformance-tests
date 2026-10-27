# Startup callback controller support

## Goal

Enable real Toast startup-script and startup-line callback tests for Q's approved
server-to-softcode conformance inventory. Q authorized PR publication and CI
babysitting; merging remains unapproved.

## State

Optional restart_server.arguments is parsed as a list of NUL-free strings,
forwarded by the runner, and inserted immediately after the executable for one
launch. Documentation and focused schema, transport and process tests added.
This controller branch intentionally contains no candidate conformance YAML.

## Decisions and why

Smallest change: one optional field using the existing restart action and process
launcher, approximately 30 production lines plus focused tests/docs. Literal
tokens avoid shell interpretation and preserve MOO strings. No persistent
command override or new host action is needed. Toast server.cc:2019-2032 parses
--start-line/--start-script; :2318-2328 runs them before server_started.

## Surprises

The repository requires controller changes to reach main before dependent test
data can be admitted. Independent callback data remains in its separate branch.

## Next step

Publish this controller PR and follow CI. Continue independent callback data;
prepare startup cases against this field without claiming trusted-controller
acceptance before this dependency is merged.
