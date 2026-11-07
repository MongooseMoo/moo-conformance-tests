# Notify semantics

## Goal

Pin notification success returns and programmer permissions on bundled Test.db.
Open a PR and leave it unmerged; Barn must merge first when later authorized.

## State

Added connected wizard/self, other-connected-target programmer denial,
disconnected-target denial, and wizard disconnected success cases. Three managed
stock WSL Toast runs passed all five cases plus capability admission. Unchanged
Barn failed both connected return values and both permission denials; wizard
disconnected success already passed. Fixed Barn passes the same five cases,
existing notify call shapes, and admission.

Fixture: bundled `src/moo_conformance/_db/Test.db`, 2035 bytes, SHA-256
`1a3f23ebb549e02ccf5341668425118fcdc935b977096add87bc2a8ef29d408e`.
Managed lifecycles use disposable copies.

WSL Debian command, from this worktree, with
`UV_PROJECT_ENVIRONMENT=/root/.cache/uv/notify-toast-parity`:
`uv run moo-conformance _tests/builtins/notify_semantics.yaml --server-command="/root/src/toaststunt/build-release/moo {db} {db}.new -p {port}" -k "notify_semantics or capability_admission" -v --junitxml=/tmp/notify-toast-N.xml`.
First run omitted the file selector. Raw summaries from Debian XML files
`/tmp/notify-toast-{1,2,3}.xml`:

```text
6 passed, 13754 deselected, 1 warning in 257.57s (0:04:17)
6 passed, 1 warning in 6.97s
6 passed, 1 warning in 6.60s
```

Windows command with environment
`UV_PROJECT_ENVIRONMENT=C:/Users/Q/.cache/uv/notify-toast-parity-windows`:
`uv run moo-conformance _tests/builtins/notify_semantics.yaml --server-command='C:/Users/Q/code/barn-notify-toast-parity/bin/barn.exe -db {db} -port {port}' -k 'notify_semantics or capability_admission' -v --junitxml=C:/Users/Q/AppData/Local/Temp/notify-barn-before.xml`:

```text
expected value 1, but got 0
expected value [1, 0, 1], but got [1, 0, 0]
expected error E_PERM, but got success with value: 0
expected error E_PERM, but got success with value: 1
4 failed, 2 passed, 1 warning in 2.91s
```

Fixed Barn: same command with `--frozen`, both notify_semantics.yaml and
notify_call_shapes.yaml selectors, `-k 'notify or capability_admission'`, and
`notify-barn-after.xml`: `61 passed, 1 warning in 2.59s`.
Warnings concern pytest record_property/xunit2 compatibility.

## Decisions and why

Q explicitly authorized continuation of the existing plan. No merge, comments,
issues, or attribution. Stage only this note and builtins/notify_semantics.yaml.
Use managed stock WSL Toast and include capability_admission in every session.
The secondary raw socket API reads until quiet; it does not control OS send
capacity. Do not introduce a timing-dependent full-queue test or new transport.

## Surprises

Windows uv imported global options into the lockfile that older WSL uv rejected
before an optional fourth run. Restored that incidental delta; use --frozen for
subsequent runs. Three completed oracle runs are unaffected.

## Next step

Open the conformance PR and watch its checks. Leave unmerged, with Barn first
when merging is later authorized. Full-queue no_flush remains unverified.
