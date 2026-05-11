# address-copilot-comments

A skill that helps AI agents triage and address GitHub Copilot pull request
review comments. It guides agents through thread-aware GitHub review
inspection, classification of comments as valid, nitpicky, wrong, or obsolete,
fix planning, focused implementation, separate review-fix commits, branch
pushing, thread resolution, Copilot re-review requests, and repeat review
loops until no meaningful Copilot comments remain.

The skill is designed for Copilot-as-reviewer workflows where generated review
feedback should be treated as a hypothesis to verify against the codebase, not
as instructions to apply blindly.

The full agent instructions live in [`SKILL.md`](SKILL.md).

## Install

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --skill address-copilot-comments
```

## Usage

Invoke the skill explicitly when you want to inspect and address Copilot PR
review comments; it does not auto-load on intent:

- **Claude Code:** type `/address-copilot-comments` and then describe the PR
  review loop.
- **Codex:** type `$address-copilot-comments` and then describe the PR review
  loop.

Example: `$address-copilot-comments` then "check the unresolved Copilot
comments on this PR, tell me which ones are valid, and fix the real issues."

You can use the skill in either hands-on or autonomous mode. In hands-on mode,
the agent triages comments and proposes fixes before editing. In autonomous
mode, the agent fixes valid comments, commits and pushes changes, resolves
fixed or obsolete threads, re-requests Copilot review, and repeats until the
review is clean or only dismissible comments remain.

A typical session:

1. **Mode selection.** The agent confirms whether you want hands-on triage or
   autonomous fix-and-review iteration.
2. **PR context.** The agent resolves the repository, PR number, branch, and
   current head SHA from the local checkout or a supplied PR URL.
3. **Thread-aware triage.** The agent reads GitHub review threads with GraphQL
   so unresolved, outdated, and inline-location status are preserved.
4. **Classification.** Each Copilot thread is classified as valid, nitpicky,
   wrong, obsolete, or needing a user decision, with evidence from the code,
   tests, or PR state.
5. **Focused fixes.** Valid comments are addressed with scoped code changes and
   targeted verification. Fix clusters are committed separately.
6. **Review loop.** After pushing, the agent resolves fixed threads,
   re-requests Copilot review, waits for new feedback, and repeats the loop
   until the PR is clean enough to stop.

For the full agent-facing protocol, including GraphQL queries, thread
resolution, Copilot re-review, polling behavior, and stop criteria, see
[`SKILL.md`](SKILL.md).

## Dependencies

The agent checks these as part of the workflow when they're needed.

### Required

- **GitHub CLI (`gh`)** - used to inspect PR metadata, query review threads,
  resolve fixed threads, and re-request Copilot review. Install it with
  Homebrew or from GitHub if it is not already available:

  ```bash
  brew install gh
  ```

- **Authenticated GitHub CLI session** - required for private repositories,
  GraphQL review-thread queries, review-thread resolution, and review requests:

  ```bash
  gh auth login
  ```

- **Local git checkout for the PR branch** - used to inspect code, make fixes,
  run verification, commit focused fix clusters, and push the PR branch.

### Optional

- **GitHub connector or app access** - useful for PR metadata or high-level
  summaries when available, but the skill still requires thread-aware GraphQL
  data for unresolved review-thread state.
