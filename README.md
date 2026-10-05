# moodle — skill do Claude Code para o Moodle do ISEP

Skill do [Claude Code](https://claude.com/claude-code) que vai ao Moodle do ISEP (`moodle.isep.ipp.pt`) buscar as fichas, os slides, os enunciados e os outros ficheiros das tuas cadeiras, e depois lê-os, resume-os ou resolve-os.

Usa a API da app mobile do Moodle, por isso não faz scraping. Só descarrega o que é novo ou foi alterado.

## Instalar

```bash
git clone https://github.com/tomf07/moodle-isep-skill ~/.claude/skills/moodle
python3 ~/.claude/skills/moodle/scripts/moodle_sync.py --login
```

O login pede o número de aluno e a password. A password só é enviada ao Moodle do ISEP e não fica guardada. O que fica guardado é um token em `~/.config/moodle-sync/token`.

## Usar

No Claude Code, escreve `/moodle` ou pede de forma natural, por exemplo "saca a ficha 3 de ESINF" ou "há coisas novas no moodle?".

O script também funciona sozinho:

```bash
python3 scripts/moodle_sync.py --list      # cadeiras em curso
python3 scripts/moodle_sync.py -c ESINF    # sincroniza uma cadeira
python3 scripts/moodle_sync.py             # sincroniza todas
python3 scripts/moodle_sync.py --dry-run   # mostra o que ia sacar
python3 scripts/moodle_sync.py --all       # inclui cadeiras antigas
```

Os ficheiros vão para `~/Documents/ISEP/Moodle/<cadeira>/<secção>/` (para mudar, usa `-o <pasta>`). Só precisa de Python 3.8+, sem dependências.
