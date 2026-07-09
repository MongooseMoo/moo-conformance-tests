# Coverage Publish Report

## Summary

Published the verified coverage work from `main` to `origin/main` after the
final verifier returned `MERGE`.

## Branch and Ahead/Behind State Before Push

- Branch: `main`.
- Tracking state before the publish push: `main...origin/main [ahead 12]`.
- Ahead/behind before the publish push:
  - Command: `git rev-list --left-right --count main...origin/main`
  - Result: `12 0`
- `origin/master` was absent:
  - Command: `git rev-parse --verify origin/master`
  - Result: failed with `fatal: Needed a single revision`

## Record Commit

- Record commit: `1a9813358b1e6e1c9721928ad6fb5f0c590ce5f3`
- Commit message: `Record coverage publish verifier records`
- Parent: `a5b815059c8ebef23482fbf855bb0a6f35c5f282`

Exact staged files for the record commit:

```text
prompts/coverage-final-verifier.md
prompts/coverage-publish.md
reports/coverage-final-verifier-report.md
```

Record commit check:

- Command: `git diff --cached --check`
- Result: passed with no output.

## Publish Push

- Command: `git push origin main:main`
- Result: passed.

Output:

```text
To github.com:MongooseMoo/moo-conformance-tests.git
   2fc2a9e..1a98133  main -> main
```

## Post-Push Verification

- Command: `git status --short --branch`
- Result: `## main...origin/main`, plus the same pre-existing unrelated
  untracked files.
- Command: `git rev-list --left-right --count main...origin/main`
- Result: `0 0`
- Command: `git rev-parse HEAD origin/main`
- Result:

```text
1a9813358b1e6e1c9721928ad6fb5f0c590ce5f3
1a9813358b1e6e1c9721928ad6fb5f0c590ce5f3
```

## Report Publication

This report was written after the publish push so it could include the real
push result. It is the only path to stage for the final report commit.
