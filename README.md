# moodle-isep-skill

A [Claude Code](https://claude.com/claude-code) skill for ISEP's Moodle. Ask Claude for "the ESINF worksheet 3" and it pulls the file from Moodle and reads it. From there it can summarize it, explain it or help you solve it.

It talks to the same API the Moodle mobile app uses, so there's no page scraping. It only downloads files that are new or changed since the last run.

## Install

```bash
git clone https://github.com/tomf07/moodle-isep-skill ~/.claude/skills/moodle
python3 ~/.claude/skills/moodle/scripts/moodle_sync.py --login
```

The login step asks for your student number and password. Your password only goes to moodle.isep.ipp.pt and never gets saved. What gets saved is a token, in `~/.config/moodle-sync/token`.

## Usage

In Claude Code, type `/moodle` or just ask normally:

- "get me the latest BDDAD slides"
- "anything new on moodle?"
- "solve exercise 2 from the ARQCP PL sheet"

You can also run the script on its own:

```bash
python3 scripts/moodle_sync.py --list      # courses you're taking now
python3 scripts/moodle_sync.py -c ESINF    # sync one course
python3 scripts/moodle_sync.py             # sync all current courses
python3 scripts/moodle_sync.py --dry-run   # show what it would download
python3 scripts/moodle_sync.py --all       # include past courses too
```

Files land in `~/Documents/ISEP/Moodle/<course>/<section>/`. Use `-o <folder>` if you want them somewhere else.

You need Python 3.8 or newer. There are no dependencies.
