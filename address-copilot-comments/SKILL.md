---
name: address-copilot-comments
description: >
  Triage and address GitHub Copilot pull request review comments. Use when the
  user asks to check unresolved Copilot review threads, decide which comments
  are valid versus nitpicky or incorrect, plan fixes, implement approved
  changes, commit review-comment fixes separately, push the branch, re-request
  Copilot review, and iterate until no meaningful new Copilot comments remain.
---

# Address Copilot Comments

Use this skill for PR review loops where Copilot is acting as the reviewer. The
goal is to improve the codebase, not to blindly satisfy every generated
comment. Treat Copilot feedback as hypotheses that must be checked against the
code, tests, and product intent.

## Hard Rules

- Use thread-aware GitHub data. Do not rely on flat PR comment lists when
  unresolved status, inline locations, or outdated status matter.
- Use flat PR comments or connector comment lists only for lightweight top-level
  summaries. For unresolved review state, inline locations, and outdated status,
  use GraphQL review threads.
- Never mark a thread resolved until the issue has been fixed, the user has
  explicitly accepted dismissal, or the thread is demonstrably obsolete.
- Do not reply on GitHub, resolve review threads, submit a review, push, or
  re-request Copilot unless the user explicitly asked for that write action.
- Do not implement comments that are wrong, speculative, or quality-negative.
  Explain why they should be dismissed instead.
- If a review comment asks for clarification or explanation rather than a code
  change, draft the response instead of forcing a code edit.
- If review comments conflict with each other or would cause a behavioral
  regression, surface the tradeoff before making changes.
- Present a plan and ask the user what to do before making code changes, unless
  the user has already explicitly asked to fix all valid comments.
- Commit each approved fix or tightly related fix cluster separately. Stage only
  the files for that cluster.
- Push only after all approved commits are created.
- Re-request Copilot review after pushing, then wait for the new review and
  inspect only new unresolved Copilot threads.
- Stop the loop when there are no new unresolved Copilot comments, or when the
  remaining comments are all dismissed by the user as not worth addressing.

## Workflow

### 1. Resolve PR Context

Determine the repository, PR number, branch, and current head SHA.

- If the user supplied a PR URL or number, use it.
- Otherwise infer the PR from the current branch with `gh pr view`.
- Prefer local git context plus `gh pr view --json number,url,headRefName,headRefOid`
  for current-branch PRs.
- Confirm `gh` authentication with `gh auth status` if GitHub commands fail,
  then ask the user to authenticate with `gh auth login` if needed.
- Record the current PR head SHA before reading review threads. This helps
  distinguish new feedback from stale feedback after re-requesting review.
- If neither local git context nor `gh` can resolve the PR cleanly, say whether
  the blocker is missing repository scope, missing PR context, or CLI
  authentication, then ask for the missing repo/PR identifier or refreshed auth.

Useful commands:

```bash
gh pr view --json number,url,headRefName,headRefOid
gh auth status
gh api graphql -f owner=OWNER -f name=REPO -F number=PR_NUMBER -f query='
query($owner:String!, $name:String!, $number:Int!) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      headRefName
      headRefOid
      reviewThreads(first:100) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first:20) {
            nodes {
              author { login }
              body
              createdAt
              url
            }
          }
        }
      }
    }
  }
}'
```

### 2. Triage Unresolved Copilot Threads

Read review context with thread-aware GraphQL data. If a GitHub connector or app
is available, it may be useful for PR metadata, patch context, or top-level
comment summaries, but do not treat connector-only flat comments as the complete
source of review-thread truth.

Filter to unresolved threads where the relevant review comment is from
`copilot-pull-request-reviewer`. Keep human review comments separate and do not
resolve them as part of this loop unless the user explicitly includes them.
Group related comments by file or behavior area, and separate actionable change
requests from informational comments, approvals, already-resolved threads, and
duplicates.

Classify each thread:

- **Valid:** identifies a real bug, missing validation, broken edge case,
  incorrect docs, maintainability issue, security risk, or test gap.
- **Nit:** technically true but low value, stylistic, or not worth extra churn.
- **Wrong:** based on a false premise, already handled by code/tests, conflicts
  with repo conventions, or would make behavior worse.
- **Obsolete:** attached to outdated code or already fixed by later commits.

For every classification, cite the concrete code path, test, or behavior that
supports the decision. If the evidence is unclear, mark it **Needs decision**
and ask the user.

### 3. Present The Plan

Before editing, summarize the threads in a compact table:

```text
Thread | Classification | Proposed action | Rationale
```

Then ask the user what they want to do. Offer clear options such as:

- Fix all valid comments.
- Fix selected comments.
- Dismiss selected nit/wrong/obsolete comments.
- Pause for more investigation.

If the user already said to fix everything still valid, proceed with all
**Valid** items and call out anything left for dismissal.

### 4. Implement Approved Fixes

Implement only the approved items. Keep each change traceable to one thread or
one tightly related group of threads.

For each fix cluster:

1. Inspect the surrounding code and existing tests.
2. Make the smallest defensible change that improves behavior.
3. Add or update tests when the risk justifies it.
4. Run targeted verification for that cluster.
5. Stage only the files changed for that cluster.
6. Commit with a message that describes the behavior fixed, not the reviewer.

Good commit messages:

```text
Validate review-frame sheet dimensions
Allow render dry-run without ffmpeg
Reject invalid screencast path fields
```

Avoid messages like:

```text
Fix Copilot comment
Address review
```

### 5. Push, Resolve, And Re-Request Review

After all approved commits are created:

1. Push the PR branch.
2. Resolve the threads that were fixed, dismissed by user decision, or obsolete.
3. Re-request Copilot review.

Resolve a thread with GraphQL:

```bash
gh api graphql -f threadId=THREAD_ID -f query='
mutation($threadId:ID!) {
  resolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}'
```

Re-request Copilot:

```bash
gh pr edit PR_NUMBER --repo OWNER/REPO --add-reviewer @copilot
```

If GitHub refuses because Copilot already has a pending request, inspect the
review request state and continue to the waiting step.

If `gh` hits an auth or rate-limit issue mid-loop, stop and ask the user to
refresh authentication or wait rather than guessing from stale data.

### 6. Wait For The New Review

Poll the PR until Copilot has responded to the pushed head SHA or until a
reasonable timeout is reached. Prefer a short initial delay, then poll every
30-60 seconds. Do not wait forever without telling the user.

On each poll, compare:

- current PR `headRefOid`
- unresolved Copilot threads
- comment `createdAt` timestamps
- whether the thread is outdated

Treat a thread as new if it appeared after the last re-request or applies to
the latest pushed head and was not included in the previous triage.

### 7. Repeat Or Stop

Repeat the triage-plan-fix-push-review loop for new unresolved Copilot threads.

Stop when:

- there are no unresolved Copilot threads;
- all remaining unresolved Copilot threads are wrong, obsolete, or nitpicky and
  the user chooses not to address them; or
- a thread requires product judgment that the user has not provided.

When stopping, report:

- commits created and pushed;
- threads resolved;
- threads intentionally left open or dismissed, with reasons;
- verification run;
- current unresolved thread count;
- whether Copilot review is pending or complete.

## Quality Bar

Use Copilot feedback to raise code quality, not to accumulate defensive clutter.
Prefer fixes that clarify invariants, validate real boundaries, simplify
failure modes, or add useful coverage. Reject changes that only appease a
reviewer while making the code harder to read, less idiomatic for the repo, or
less aligned with user intent.
