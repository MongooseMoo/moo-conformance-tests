You are a coding subagent working in C:\Users\Q\code\moo-conformance-tests.

Task: commit only the foreman coordination records for the coverage work.

You are not alone in this codebase. Do not revert or modify any existing changes. Do not stage broad directories. Do not touch old untracked logs or unrelated artifacts.

Required scope:
- prompts/coverage-background-threads.md
- prompts/coverage-read-stdin.md
- prompts/coverage-optional-extensions.md
- prompts/coverage-network-matrix.md
- prompts/coverage-exec-portable.md
- prompts/coverage-records-commit.md
- reports/coverage-foreman-notes.md
- reports/coverage-background-threads-report.md

Requirements:
1. Verify the branch and status.
2. Confirm those paths are the only paths you stage.
3. Run `git diff --check --` on those paths before committing.
4. Commit with a descriptive message.
5. Write reports/coverage-records-commit-report.md with the exact staged files, command outcomes, and commit hash.
6. Commit reports/coverage-records-commit-report.md in a second commit.

Do not ask questions. If any required path is missing, report that plainly in reports/coverage-records-commit-report.md and do not stage substitutes.
