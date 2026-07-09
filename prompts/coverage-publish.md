You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: publish the verified coverage work to origin/main.

You are not alone in this codebase. Do not revert or modify any existing changes. Do not stage broad directories. Do not touch old untracked logs or unrelated artifacts.

Prerequisites already established by reports/coverage-final-verifier-report.md:
- Verdict: MERGE.
- Current branch should be main.
- origin/master is absent; publish target is origin/main.

Required final record paths:
- prompts/coverage-final-verifier.md
- reports/coverage-final-verifier-report.md
- prompts/coverage-publish.md
- reports/coverage-publish-report.md

Requirements:
1. Verify branch, tracking state, and that `origin/main` is behind but not ahead before pushing.
2. Stage only:
   - prompts/coverage-final-verifier.md
   - reports/coverage-final-verifier-report.md
   - prompts/coverage-publish.md
3. Run `git diff --cached --check` and commit those final verifier/publish prompt records.
4. Write `reports/coverage-publish-report.md` with:
   - branch and ahead/behind state before push
   - exact staged files for the record commit
   - record commit hash
   - push command and result
   - final `git status --short --branch`
5. Stage only `reports/coverage-publish-report.md`, run `git diff --cached --check`, commit it.
6. Push `main` to `origin/main`.
7. After push, verify `git status --short --branch` and `git rev-list --left-right --count main...origin/main`.

Do not ask questions. If push fails, write that failure in the report and leave the branch unmodified beyond committed local records.
