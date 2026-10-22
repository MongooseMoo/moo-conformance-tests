# Managed server bound-port discovery

## Goal
Remove the free-port probe/close/start allocation window for Barn's managed CI runs, following Barn issue 423's startup failure. The old port occupant is unknown.

## State
Based on main 6e55e6c. Q authorized diagnosing and fixing the two CI failures. Implemented optional CLI/log-pattern discovery (server.py and plugin.py), README usage, and focused managed-server tests. No local CI steps run; awaiting PR CI.

## Decisions and why
Smallest change: one opt-in server-port-pattern option (about 40 source lines) that lets a server bind port 0 and extracts its actual port from its existing startup log before connecting. Barn already logs the primary TCP listener port; no server protocol or Barn binary change is needed. Read only the current process's log section. Preserve the selected port on explicit restart, as existing transport semantics require. Add focused managed-server tests and documentation (about 70 lines). Keep native startup failures visible; no startup retries.

## Surprises
The failed CI log proves EADDRINUSE, not which process occupied that port. This removes the source-visible allocation window without inventing a historical owner.

## Next step
Publish companion PR and inspect exact-head CI. Barn's workflow must not use the new option against main until this companion change is merged. No merge authorization supplied; request it only with the concrete reviewed result and CI evidence.
