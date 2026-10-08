---
name: moodle
description: Vai ao Moodle do ISEP (moodle.isep.ipp.pt) sacar fichas, slides, enunciados, soluções e outros ficheiros das cadeiras do utilizador, e depois lê-os. Usa esta skill sempre que o utilizador pedir algo do Moodle ("saca as fichas", "vai ao moodle", "a ficha 3 de ESINF", "o enunciado do trabalho", "os slides da última aula", "há coisas novas no moodle?") e para os fóruns ("há anúncios novos?", "o prof disse alguma coisa sobre o teste?", "já responderam à dúvida sobre a USEI05?", "o que perguntaram no fórum de LAPR3?"). Usa-a também quando precisares do material de uma cadeira do ISEP que não está em ~/Documents/ISEP/Moodle. Também serve para resolver ou explicar uma ficha que esteja no Moodle.
---

# Moodle ISEP

O script `scripts/moodle_sync.py` (só usa a biblioteca standard) fala com a API da app mobile do Moodle e espelha os ficheiros das cadeiras para:

```
~/Documents/ISEP/Moodle/<shortname da cadeira>/<NN Nome da secção>/[<atividade>/]<ficheiro>
```

Só descarrega o que é novo ou foi alterado (compara o tamanho e o `timemodified`), por isso podes voltar a corrê-lo à vontade.

## Comandos

```bash
S=~/.claude/skills/moodle/scripts/moodle_sync.py
python3 $S --list              # cadeiras em curso (id, shortname, fullname)
python3 $S -c ESINF            # sincroniza só as cadeiras cujo nome contém "ESINF" (pode repetir -c)
python3 $S                     # sincroniza todas as cadeiras em curso
python3 $S --dry-run -c BDDAD  # mostra o que ia descarregar, sem descarregar
python3 $S --all --list        # inclui cadeiras de anos anteriores

# Fóruns (anúncios, dúvidas aos docentes, client questions do PI)
python3 $S --forums                       # todas as discussões com atividade nos últimos 14 dias
python3 $S --forums -c ESINF --since 30d  # --since aceita 24h, 7d, 2w, 2026-09-01 ou all
python3 $S --forums -c "client questions" --since all --max-chars 0   # 0 = posts sem cortes
```

No output, `+` é um ficheiro novo e `~` um ficheiro atualizado. A última linha tem o resumo.

## Como trabalhar

1. **Sincroniza só o que precisas.** Se o pedido é sobre uma cadeira, usa `-c <cadeira>`. Se não sabes o shortname, corre `--list` primeiro. Para "há coisas novas?", corre sem `-c` e mostra a lista dos `+`/`~`.
2. **Encontra o ficheiro** com `find ~/Documents/ISEP/Moodle/<cadeira> -iname '*ficha*'` (ou com `ls` nas secções). As fichas costumam chamar-se "TP", "PL", "Ficha", "Exercícios", "Worksheet", com um número. As secções estão numeradas pela ordem do Moodle (`00` é a secção geral do topo).
3. **Lê o ficheiro.** PDFs com a tool Read (usa `pages` se tiver mais de 10 páginas). Para .docx e .pptx usa as skills respetivas. Os .zip extraem-se para uma pasta ao lado.
4. **Responde ao pedido.** Pode ser resumir, resolver ou explicar. Indica sempre o caminho do ficheiro como link.

## Fóruns

`--forums` imprime as discussões com posts dentro do período, das mais recentes para as mais antigas. Para cada uma mostra o título, o link e os posts por ordem (autor, data e texto). As respostas aparecem indentadas e as discussões afixadas têm a marca `[afixado]`. Os anexos dos posts são descarregados para `~/Documents/ISEP/Moodle/<cadeira>/Forum/<fórum>/<discussão>/` (ver as linhas `[anexo]`).

- O `-c` também filtra pelo **nome do fórum**. Os fóruns de dúvidas por cadeira (ESINF, BDDAD, LAPR3 - Client Questions, ...) estão na página do projeto integrador (`SEM_3_PI ...`) e não dentro da cadeira. Por isso `-c ESINF` apanha tanto os anúncios de ESINF como o fórum ESINF do PI.
- Se o output for muito grande, baixa o `--since`, filtra com `-c` ou usa `--max-chars 500`. Para ler uma discussão inteira, usa `--max-chars 0`.
- Quando resumires, separa o que é dos docentes (anúncios, respostas) do que são dúvidas dos alunos. Diz quais as perguntas que ainda não têm resposta e inclui o link da discussão.
- Isto é só leitura. A skill não publica nem responde nos fóruns.

## Login (NO_TOKEN)

Se o script sair com `NO_TOKEN`, não há token ou ele expirou. O login pede o número de aluno e a password de forma interativa, por isso **é o utilizador que o faz**. Nunca peças a password no chat nem a escrevas em lado nenhum. Diz-lhe para correr isto num terminal:

```bash
python3 ~/.claude/skills/moodle/scripts/moodle_sync.py --login
```

O token fica guardado em `~/.config/moodle-sync/token` (chmod 600). Depois do login, continua a tarefa.

## Notas

- A sincronização normal só saca ficheiros de recursos, pastas e outras atividades com anexos. Os fóruns são tratados à parte com `--forums`. Links (URL) e páginas são ignorados.
- As cadeiras "em curso" incluem algumas de anos anteriores, porque o ISEP não lhes põe data de fim. Para sincronizar ficheiros, usa `-c` com as cadeiras deste semestre.
- Se uma cadeira der erro ao ler o conteúdo, o script continua para as outras e conta-a como falha.
- `--logout` apaga o token.
