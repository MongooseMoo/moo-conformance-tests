# Exec and Base64 exception conformance

## Goal

Publish the conformance cases for Barn issue #1196 alongside the Barn fix.

## State

Conformance PR #293 is open. The initial managed run verified the caught code, message, and value on both Barn and Toast. The baseline Barn run failed 21 assertions.

## Decisions and why

Keep the existing test identities and declare the forking requirement on the six cases that use fork. This lets Barn run the independent exec cases while preserving admission for forked cases.

## Surprises

Trusted validation uses the YAML path and case name as the identity. Moving a case to the builtin suite therefore removed its existing identity. CI rejected the move with `candidate conformance data deletes trusted-main identities`.

## Next step

Restore the exec identities, publish the correction to PR #293, and verify the PR checks.
