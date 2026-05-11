---
name: address-copilot-comments
disable-model-invocation: true
description: >
  Triage and address GitHub Copilot pull request review comments. Covers
  thread-aware review inspection, comment classification, autonomous or hands-on
  review modes, fix planning, scoped implementation, separate review-fix
  commits, branch pushing, review-thread resolution, Copilot re-review
  requests, and repeat review loops. Use when asked to check unresolved Copilot
  review threads, fix valid feedback, or iterate until no meaningful new
  Copilot comments remain.
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
  re-request Copilot unless the user explicitly asked for that write action or
  selected **Autonomous mode** for this review loop.
- Do not implement comments that are wrong, speculative, or quality-negative.
  Explain why they should be dismissed instead.
- If a review comment asks for clarification or explanation rather than a code
  change, draft the response instead of forcing a code edit.
- If review comments conflict with each other or would cause a behavioral
  regression, surface the tradeoff before making changes.
- Before making code changes, follow the selected review mode: in
  **Autonomous mode**, proceed with valid fixes without asking for per-round
  approval; in **Hands-on mode**, present the plan and wait for approval before
  editing.
- Commit each approved or autonomous-mode fix cluster separately. Stage only the
  files for that cluster.
- Push only after all selected fix commits are created.
- Re-request Copilot review after pushing, then wait for the new review and
  inspect only new unresolved Copilot threads.
- Stop the loop only after Copilot has responded to the latest pushed head and
  there are no new unresolved Copilot comments, or every new/remaining Copilot
  comment is classified as wrong, obsolete, or a low-value nit that is not worth
  addressing.

## Workflow

### 1. Select Review Mode

At the start of the interaction, ask the user how much autonomy they want unless
their latest request already clearly selects a mode.

Prompt:

```text
How should I handle Copilot's review comments?

1. Autonomous mode: I will triage the comments, fix everything I judge valid,
   commit and push the changes, resolve fixed threads, re-request Copilot, and
   repeat until there are no meaningful unresolved Copilot comments.
2. Hands-on mode: I will triage the comments and propose changes first, then
   wait for your approval before editing files or performing GitHub write
   actions.
```

Mode behavior:

- **Autonomous mode** is explicit permission for this review loop to edit files,
  commit, push, reply to fixed threads, resolve fixed/obsolete threads, and
  re-request Copilot review. Still reject wrong or quality-negative comments;
  do not blindly appease Copilot.
- **Hands-on mode** is read-only until the user approves a specific plan. Fetch
  and classify comments, present the proposed fixes/dismissals, then wait.
- If the user says "address the comments", "fix everything valid", "resolve and
  re-request", or equivalent, treat that as Autonomous mode.
- If the user says "check them out", "review the comments", "show me the plan",
  or equivalent, treat that as Hands-on mode.

### 2. Resolve PR Context

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

### 3. Triage Unresolved Copilot Threads

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
  Nits do not block a PR from being considered clean unless the user wants them
  fixed.
- **Wrong:** based on a false premise, already handled by code/tests, conflicts
  with repo conventions, or would make behavior worse.
- **Obsolete:** attached to outdated code or already fixed by later commits.

For every classification, cite the concrete code path, test, or behavior that
supports the decision. If the evidence is unclear, mark it **Needs decision**
and ask the user.

### 4. Present The Plan

Always summarize the first triage in a compact table:

```text
Thread | Classification | Proposed action | Rationale
```

In Hands-on mode, ask the user what they want to do before editing. Offer clear
options such as:

- Fix all valid comments.
- Fix selected comments.
- Dismiss selected nit/wrong/obsolete comments.
- Pause for more investigation.

In Autonomous mode, proceed with all **Valid** items after the table and call
out anything left for dismissal in the final report. If Copilot has responded
to the latest head and there are no **Valid** or **Needs decision** comments,
consider the PR clean even if Copilot left comments classified as **Wrong**,
**Obsolete**, or low-value **Nit**.

### 5. Implement Approved Fixes

Implement only the approved items in Hands-on mode, or valid items in
Autonomous mode. Keep each change traceable to one thread or one tightly related
group of threads.

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

### 6. Push, Resolve, And Re-Request Review

After all selected fix commits are created:

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

### 7. Wait For The New Review

Poll the PR until Copilot has responded to the pushed head SHA or until a
reasonable timeout is reached. After re-requesting Copilot review, wait at
least 3 minutes before the first check; prefer 4 minutes unless the user asks
for a faster pass. Copilot often needs several minutes to generate a new
review, so do not spend poll attempts during this initial quiet period.

After the initial wait, poll every 45-60 seconds, up to 10 times by default.
This yields a total wait of roughly 11-14 minutes including the initial delay.
Do not wait forever without telling the user.

On each poll, compare:

- current PR `headRefOid`
- unresolved Copilot threads
- comment `createdAt` timestamps
- whether the thread is outdated

Treat a thread as new if it appeared after the last re-request or applies to
the latest pushed head and was not included in the previous triage.

If the polling window ends without a new Copilot response on the latest head,
report that Copilot has not produced new review comments yet or that review may
still be pending. Do not describe this as "no new comments" or "review is
clean" unless GitHub shows Copilot responded to the latest head and either
there are no new unresolved Copilot threads or all new unresolved Copilot
threads are classified as **Wrong**, **Obsolete**, or low-value **Nit**.

### 8. Repeat Or Stop

Repeat the triage-plan-fix-push-review loop for new unresolved Copilot threads.

Stop when:

- Copilot has responded to the latest head and there are no unresolved Copilot
  threads;
- Copilot has responded to the latest head and all new/remaining unresolved
  Copilot threads are wrong, obsolete, or nitpicky enough that they do not merit
  code changes; or
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
