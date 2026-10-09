# moodle-isep-skill

A [Claude Code](https://claude.com/claude-code) skill for ISEP students. It covers both of ISEP's sites:

- **Moodle** (`moodle_sync.py`): course files, slides, worksheets and forum posts. Ask for "the ESINF worksheet 3" and Claude pulls the file and reads it. From there it can summarize it, explain it or help you solve it.
- **Student portal** (`portal.py`): timetables, grades, absences, fees and anything else on portal.isep.ipp.pt. Ask "what classes do I have tomorrow?" or "what's my average?" and Claude looks it up.

Both scripts are plain Python (3.8 or newer) with no dependencies, and both only read. They never post, submit or change anything.

## Install

```bash
git clone https://github.com/tomf07/moodle-isep-skill ~/.claude/skills/moodle
python3 ~/.claude/skills/moodle/scripts/moodle_sync.py --login
python3 ~/.claude/skills/moodle/scripts/portal.py --login
```

Each login asks for your student number and password. Run them in a terminal yourself; Claude never asks for your password. If you skip one, Claude tells you to run it the first time it needs that site.

## Usage

In Claude Code, type `/moodle` or just ask normally:

- "get me the latest BDDAD slides"
- "anything new on moodle?"
- "solve exercise 2 from the ARQCP PL sheet"
- "did the teacher answer the USEI05 question in the ESINF forum?"
- "what classes do I have tomorrow, and in which rooms?"
- "is room B202 free on Thursday afternoon?"
- "did my ESINF grade come out? what's my average?"
- "how many absences do I have in LAPR3?"
- "do I owe anything in tuition?"
- "export my timetable to my calendar"

## Moodle

`moodle_sync.py` talks to the same API the Moodle mobile app uses, so it doesn't scrape pages. It only downloads files that are new or changed since the last run.

```bash
python3 scripts/moodle_sync.py --list      # courses you're taking now
python3 scripts/moodle_sync.py -c ESINF    # sync one course
python3 scripts/moodle_sync.py             # sync all current courses
python3 scripts/moodle_sync.py --dry-run   # show what it would download
python3 scripts/moodle_sync.py --all       # include past courses too

python3 scripts/moodle_sync.py --forums                     # forum posts from the last 14 days
python3 scripts/moodle_sync.py --forums -c ESINF --since 30d
```

Files land in `~/Documents/ISEP/Moodle/<course>/<section>/`. Use `-o <folder>` if you want them somewhere else.

`--forums` prints recent discussions with every post in order, and saves any attachments next to the course files. `--since` takes things like `24h`, `7d`, `2w`, `2026-09-01` or `all`.

## Portal

`portal.py` logs in to [portal.isep.ipp.pt](https://portal.isep.ipp.pt/intranet/) the way your browser does. It then calls the same requests the portal's own pages use, so you get the data without any clicking.

### Timetables

```bash
python3 scripts/portal.py horario                   # your timetable this week
python3 scripts/portal.py horario --week 2026-11-02 # the week containing that day
python3 scripts/portal.py horario --weeks 4         # 4 weeks in a row
python3 scripts/portal.py horario --class 12345     # a class's timetable
python3 scripts/portal.py horario --room 3267       # a room's timetable
python3 scripts/portal.py horario --json            # structured: teachers, rooms, classes, lesson summary links
python3 scripts/portal.py horario --weeks 15 --ics ~/horario.ics   # calendar file for Apple/Google Calendar
```

Class and room ids are printed at the bottom of every timetable (`2DA=12345, B202=3267`), so you can jump from your own timetable to a room's or another class's.

### Grades, absences, fees

```bash
python3 scripts/portal.py notas                     # final grades for every course in your plan
python3 scripts/portal.py parciais                  # partial grades: continuous assessment, exam, resit
python3 scripts/portal.py parciais --ano 2025/2026  # just one school year
python3 scripts/portal.py faltas                    # absences and late arrivals per course and class type
python3 scripts/portal.py percurso                  # current enrolment: courses, class, ECTS, status
python3 scripts/portal.py dividas                   # invoices, payments and anything pending
python3 scripts/portal.py requerimentos             # your requests
```

### Everything else

```bash
python3 scripts/portal.py menu                                      # every page in the intranet menu
python3 scripts/portal.py get educacao/ver_calendario_escolar.aspx  # any page, as text
python3 scripts/portal.py get <page> --links                        # include link targets, to follow them
python3 scripts/portal.py call areapessoal/estudante.aspx/getAccessDataEvent '{"cuser": "{me}"}'
```

`get` works for pages that show their content directly. On form pages it shows the value filled in for each field, not every option.

Many portal pages are empty at first and load their data afterwards through `page.aspx/getSomething` requests. `call` sends those requests directly, and `{me}` is replaced with your portal user code. It only allows method names that start with `get`, so it can't reach the portal's save and update methods.

Things it deliberately doesn't do: issue certificates or declarations, make requests, pay, book meals, sign up for exams. Those create something on your account, so do them on the portal yourself.

## What gets stored

| What | Where |
|---|---|
| Moodle token | `~/.config/moodle-sync/token` |
| Portal session cookies | `~/.config/moodle-sync/portal_cookies.txt` |
| Your portal login and user code | `~/.config/moodle-sync/portal_user.json` |
| Portal password (only if you said yes, macOS only) | Keychain, service `isep-portal` |

All three files are `chmod 600`. Your Moodle password is never saved, and your portal password is only kept in the Keychain if you agree when logging in. That lets the script log back in by itself when the session expires. Without it, run `portal.py --login` again whenever it says `NO_SESSION`.

To remove everything:

```bash
python3 scripts/moodle_sync.py --logout
python3 scripts/portal.py --logout
```

Passwords only ever go to moodle.isep.ipp.pt and portal.isep.ipp.pt. `portal.py get` refuses URLs outside portal.isep.ipp.pt.
