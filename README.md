# Nerd Out's AI Skills

This is a collection of installable skills that can be used by AI agents.
Each skill lives in its own top-level folder with a `SKILL.md` file so the
`skills` CLI can discover and install it directly from this repository.

## Installation

Install a specific skill from this repository with:

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --skill screen-studio
```

The installer will prompt for the install scope and target agent. To install
globally without prompts, add `--global --yes`:

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --skill screen-studio --global --yes
```

To list the available skills before installing:

```bash
npx skills add https://github.com/NerdOutInc/ai-skills --list
```

## Available Skills

### [screen-studio](screen-studio/README.md)

The `screen-studio` skill helps agents record polished, repeatable macOS screencasts
with [Screen Studio](https://screen.studio). It guides capture-scope selection, clean
Helium browser setup for web demos, scripted dry runs, coordinate calibration
with `cliclick`, Screen Studio shortcut usage, smoke captures, and keeper-take
verification with tools such as `ffprobe` and timestamp contact sheets.
