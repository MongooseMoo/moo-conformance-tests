# Startup and checkpoint callback controller support

## Goal

Enable real Toast startup-script and startup-line callback tests for Q's approved
server-to-softcode conformance inventory. Q authorized PR publication and CI
babysitting; merging remains unapproved.

## State

Optional restart_server.arguments is parsed as a list of NUL-free strings,
forwarded by the runner, and inserted immediately after the executable for one
launch. Documentation and focused schema, transport and process tests added.
This controller branch intentionally contains no candidate conformance YAML.
PR #161 is published; controller checks passed and Toast matrix is pending.
Startup data is temporarily untracked here for active authoring and will move
to its own data branch. A confined checkpoint_fault exec fixture now exercises
write and publication failure branches that chmod cannot reach.

## Decisions and why

Smallest change: one optional field using the existing restart action and process
launcher, approximately 30 production lines plus focused tests/docs. Literal
tokens avoid shell interpretation and preserve MOO strings. No persistent
command override or new host action is needed. Toast server.cc:2019-2032 parses
--start-line/--start-script; :2318-2328 runs them before server_started.

Toast db_file.cc:1159-1197 distinguishes write failure from output publication
failure. The fixture uses only Test.db.new and its first temporary checkpoint in
a managed directory, preserves any previous output, and removes only its own
obstruction. It uses the existing exec fixture installer; no new host action.

## Surprises

The repository requires controller changes to reach main before dependent test
data can be admitted. Independent callback data remains in its separate branch.

## Next step

Publish this controller PR and follow CI. Continue independent callback data;
prepare startup cases against this field without claiming trusted-controller
acceptance before this dependency is merged.
