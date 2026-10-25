# CLAUDE.md

## Plan Mode Rules

1. Every plan includes a pre-commit step.
2. List every file to be created or modified.
3. Run `pre-commit run --files <changed_files>` before any commit.
4. If pre-commit fails, add a fix step before retrying.
5. Never mark a plan complete until pre-commit passes.
6. Include rollback steps for multi-file changes.
