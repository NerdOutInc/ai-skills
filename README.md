# Nerd Out's AI Skills

This is a collection of installable skills that can be used by AI agents.
Each skill lives in its own top-level folder with a `SKILL.md` file so the
`skills` CLI can discover and install it directly from this repository.

## Installation

Install a specific skill from this repository with:

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --skill address-copilot-comments
```

The installer will prompt for the install scope and target agent. To install
globally without prompts, add `--global --yes`:

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --skill address-copilot-comments --global --yes
```

To list the available skills before installing:

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --list
```

## Available Skills

These skills cover GitHub PR review loops and screencast production workflows.
The screencast skills are macOS-only: `screen-studio` depends on Screen Studio
and macOS UI automation, while `edit-narrated-screencasts` uses Apple Vision
for screencast screen analysis.

### [address-copilot-comments](address-copilot-comments/README.md)

The `address-copilot-comments` skill helps agents triage and address GitHub
Copilot pull request review comments. It guides thread-aware review inspection,
comment classification, hands-on or autonomous fix planning, scoped
implementation, separate review-fix commits, thread resolution, Copilot
re-review requests, and repeat review loops until no meaningful Copilot
comments remain.

### [edit-narrated-screencasts](edit-narrated-screencasts/README.md)

The `edit-narrated-screencasts` skill helps agents turn an existing screen
recording and separately recorded narration into a polished screencast. It
covers media inspection, local narration transcription, Apple Vision screen
analysis, narration/action timing maps, clip retiming, freeze frames, optional
project-specific intro/outro stills, transparent artifact patches, preview
renders, HQ renders, and timestamp contact-sheet verification.

### [screen-studio](screen-studio/README.md)

The `screen-studio` skill helps agents record polished, repeatable macOS
screencasts with [Screen Studio](https://screen.studio). It guides capture-scope
selection, clean Helium browser setup for web demos, scripted dry runs,
coordinate calibration with `cliclick`, Screen Studio shortcut usage, smoke
captures, and keeper-take verification with tools such as `ffprobe` and
timestamp contact sheets.
