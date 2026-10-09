---
name: moodle
description: Vai ao Moodle do ISEP (moodle.isep.ipp.pt) sacar fichas, slides, enunciados, soluções e outros ficheiros das cadeiras do utilizador, e depois lê-os. Usa esta skill sempre que o utilizador pedir algo do Moodle ("saca as fichas", "vai ao moodle", "a ficha 3 de ESINF", "o enunciado do trabalho", "os slides da última aula", "há coisas novas no moodle?") e para os fóruns ("há anúncios novos?", "o prof disse alguma coisa sobre o teste?", "já responderam à dúvida sobre a USEI05?", "o que perguntaram no fórum de LAPR3?"). Usa-a também quando precisares do material de uma cadeira do ISEP que não está em ~/Documents/ISEP/Moodle. Também serve para resolver ou explicar uma ficha que esteja no Moodle. Usa-a ainda para o portal do ISEP (portal.isep.ipp.pt): horários ("que aulas tenho amanhã?", "em que sala é ESINF?", "horário da 2DB", "a sala B202 está livre?", "exporta o horário para o calendário"), notas finais e parciais ("que nota tive a MDISC?", "já saiu a nota de ESINF?", "qual é a minha média?"), faltas ("quantas faltas tenho a LAPR3?"), propinas e pagamentos, requerimentos, calendário escolar, datas de exames e qualquer outra página da intranet.
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

# Portal do ISEP (horários e intranet)

O script `scripts/portal.py` (também só usa a biblioteca padrão) lê o portal.isep.ipp.pt/intranet.

```bash
P=~/.claude/skills/moodle/scripts/portal.py
python3 $P horario                        # o horário do utilizador desta semana
python3 $P horario --week 2026-11-02      # a semana que contém esse dia
python3 $P horario --weeks 4              # 4 semanas seguidas
python3 $P horario --class 12345          # horário de uma turma
python3 $P horario --room 3267            # horário de uma sala (para ver se está livre)
python3 $P horario --json                 # dados estruturados (docentes, salas, turmas, link do sumário)
python3 $P horario --weeks 15 --ics ~/Downloads/horario.ics   # exportar para o calendário
python3 $P notas                          # notas finais de todas as UCs do plano (ECTS, nota, data)
python3 $P parciais                       # notas parciais: av. contínua, época normal, recurso (todos os anos)
python3 $P parciais --ano 2026/2027       # só um ano letivo
python3 $P faltas                         # faltas e atrasos por UC e tipo de aula (ano atual; --ano, --json)
python3 $P percurso                       # inscrição atual: UCs, turmas, ECTS, estatuto, bolsa
python3 $P dividas                        # conta corrente: faturas, pagamentos, valores pendentes
python3 $P requerimentos                  # requerimentos feitos
python3 $P menu                           # lista as 88 páginas do menu da intranet
python3 $P get educacao/ver_calendario_escolar.aspx           # qualquer página, em texto
python3 $P get <página> --links           # mostra também o destino dos links, para navegar
python3 $P call areapessoal/estudante.aspx/getAccessDataEvent '{"cuser": "{me}"}'   # WebMethod de leitura
```

- No fim do `horario` aparecem os ids das turmas e das salas (`2DA=12345`, `B202=3267`). Usa-os com `--class` e `--room`. Se não tiveres o id de uma turma ou sala, procura-o primeiro num horário onde ela apareça.
- Para notas, faltas, propinas e inscrição usa os comandos próprios. As notas vazias em `notas` são UCs ainda por fazer. A média calcula-se com as notas e os ECTS das UCs já feitas.
- Para tudo o resto (calendário escolar, notícias, avisos...), corre `menu`, escolhe a página e lê-a com `get`. Nos formulários, o `get` mostra o valor preenchido em cada campo. Se a página tiver links para os detalhes, usa `get --links` e segue-os.
- Muitas páginas carregam os dados depois de abrir, com pedidos `POST` a WebMethods (`pagina.aspx/getQualquerCoisa`). Se o `get` mostrar uma página vazia, faz `get --raw` e procura `url: "..."` e `var dados =` nos scripts. Depois chama o método com `call` (`{me}` é substituído pelo código do utilizador). O `call` só aceita métodos cujo nome começa por `get`.
- Mostra as horas e as salas tal como vêm do portal. `T`, `TP` e `PL` são o tipo de aula. As siglas de 3 letras são os docentes.
- **Só leitura.** Nunca uses o script para submeter formulários nem fazer ações (requerimentos, pagamentos, marcar refeições, inscrições). Se o utilizador quiser fazer uma dessas coisas, diz-lhe para a fazer ele no portal.
- `get areapessoal/ficha_do_aluno.aspx` mostra os dados pessoais do utilizador (NIF, documento de identificação, morada). Mostra só o campo que ele pediu, e não os copies para outros ficheiros.
- O portal também mostra dados de outras pessoas (fichas de docentes e funcionários). Abre-os só quando o utilizador pedir algo concreto, e não faças recolhas em massa.

## Login no portal (NO_SESSION)

Se o `portal.py` sair com `NO_SESSION`, a sessão expirou e não há password no Keychain. O utilizador tem de fazer o login num terminal (nunca peças a password no chat):

```bash
python3 ~/.claude/skills/moodle/scripts/portal.py --login
```

O login pergunta se pode guardar a password no Keychain do macOS (serviço `isep-portal`). Se o utilizador aceitar, o script volta a fazer login sozinho quando a sessão expira. Os cookies ficam em `~/.config/moodle-sync/portal_cookies.txt` (chmod 600). O comando `--logout` apaga a sessão e a password do Keychain.
