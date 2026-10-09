#!/usr/bin/env python3
"""Lê o portal do ISEP (portal.isep.ipp.pt/intranet): horários e qualquer página da intranet.

    python3 portal.py horario                    # o teu horário desta semana
    python3 portal.py horario --weeks 4          # esta semana e as 3 seguintes
    python3 portal.py horario --week 2026-11-02  # a semana que contém esse dia
    python3 portal.py horario --class 12345      # horário de uma turma (id aparece no output)
    python3 portal.py horario --room 3267        # horário de uma sala
    python3 portal.py horario --weeks 15 --ics ~/horario.ics
    python3 portal.py menu                       # todas as páginas do menu da intranet
    python3 portal.py get educacao/ver_calendario_escolar.aspx   # qualquer página, em texto
    python3 portal.py --login | --logout

Só faz leituras: nunca submete formulários do portal (requerimentos, pagamentos, refeições...).
"""
import argparse
import getpass
import html
import http.cookiejar
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://portal.isep.ipp.pt/intranet/"
CONF = Path.home() / ".config" / "moodle-sync"
COOKIES = CONF / "portal_cookies.txt"
USER_FILE = CONF / "portal_user.json"
KEYCHAIN = "isep-portal"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
HORARIO = BASE + "ver_horario/ver_horario.aspx"
ESTUDANTE = BASE + "areapessoal/estudante.aspx/"
SERAA = BASE + "escolas/isep/seraa/wsSERAAhelper.asmx/"
ENTIDADE = {"user": "aluno", "class": "turma", "room": "sala"}
DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


class SessionExpired(Exception):
    pass


def logged_out(page):
    return re.search(r"txtPasswordISEP|Guest\.aspx", page) is not None


class Portal:
    def __init__(self):
        self.jar = http.cookiejar.MozillaCookieJar(str(COOKIES))
        if COOKIES.exists():
            self.jar.load(ignore_discard=True, ignore_expires=True)
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.op.addheaders = [("User-Agent", UA)]

    def _open(self, url, data=None, headers=None):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        with self.op.open(req, timeout=60) as r:
            charset = r.headers.get_content_charset() or "iso-8859-1"
            return r.geturl(), r.read().decode(charset, "replace")

    def save(self):
        CONF.mkdir(parents=True, exist_ok=True)
        self.jar.save(ignore_discard=True, ignore_expires=True)
        COOKIES.chmod(0o600)

    def login(self, user, pwd):
        _, page = self._open(BASE)
        fields = dict(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page))
        fields = {k: html.unescape(v) for k, v in fields.items()}
        fields.update({
            "ctl00$ContentPlaceHolderMain$txtLoginISEP": user,
            "ctl00$ContentPlaceHolderMain$txtPasswordISEP": pwd,
            "ctl00$ContentPlaceHolderMain$btLoginISEP.x": "20",
            "ctl00$ContentPlaceHolderMain$btLoginISEP.y": "10",
        })
        body = urllib.parse.urlencode(fields, encoding="iso-8859-1").encode()
        url, page = self._open(BASE, body, {"Content-Type": "application/x-www-form-urlencoded"})
        if logged_out(page):
            return False
        self.save()
        return True

    def get(self, path):
        url = urllib.parse.urljoin(BASE, path)
        if not url.startswith("https://portal.isep.ipp.pt/"):
            sys.exit(f"Só leio páginas do portal.isep.ipp.pt (recebi {url})")
        final, page = self._open(url)
        if logged_out(page):
            raise SessionExpired
        return final, page

    def call(self, url, **params):
        """Chama um WebMethod ASP.NET (POST JSON) e devolve o campo "d"."""
        url = urllib.parse.urljoin(BASE, url)
        body = json.dumps(params).encode()
        try:
            _, text = self._open(url, body, {"Content-Type": "application/json; charset=utf-8"})
            return json.loads(text)["d"]
        except urllib.error.HTTPError as e:
            if e.code == 500 and not logged_out(self._open(BASE + "conta/AreaDeTrabalho.aspx")[1]):
                raise RuntimeError(f"{url} falhou no servidor (500) com {params}")
            raise SessionExpired
        except (json.JSONDecodeError, KeyError):
            raise SessionExpired

    def method(self, name, **params):
        return self.call(f"{HORARIO}/{name}", **params)


def keychain_get():
    if sys.platform != "darwin" or not USER_FILE.exists():
        return None
    user = json.loads(USER_FILE.read_text()).get("login")
    r = subprocess.run(["security", "find-generic-password", "-a", user, "-s", KEYCHAIN, "-w"],
                       capture_output=True, text=True)
    return (user, r.stdout.rstrip("\n")) if r.returncode == 0 else None


def interactive_login(p):
    if not sys.stdin.isatty():
        sys.exit(f"NO_SESSION: sem sessão no portal. Corre num terminal: python3 {Path(__file__).resolve()} --login")
    print("Login no portal do ISEP (a password só é enviada ao portal.isep.ipp.pt).")
    user = input("Utilizador (ex: 1231234): ").strip()
    pwd = getpass.getpass("Password: ")
    if not p.login(user, pwd):
        sys.exit("Login falhou: utilizador ou password errados.")
    info = {"login": user, "code": find_user_code(p)}
    USER_FILE.write_text(json.dumps(info))
    USER_FILE.chmod(0o600)
    if sys.platform != "darwin":
        print(f"Sessão guardada em {COOKIES}\n")
        return
    ans = input("Guardar a password no Keychain do macOS para o login ser automático quando a sessão expirar? [s/N] ")
    if ans.strip().lower() in ("s", "sim", "y", "yes"):
        subprocess.run(["security", "add-generic-password", "-U", "-a", user, "-s", KEYCHAIN, "-w", pwd], check=True)
        print("Guardada no Keychain (serviço 'isep-portal').")
    print(f"Sessão guardada em {COOKIES}\n")


def session(p, fn):
    """Corre fn(); se a sessão expirou, refaz o login pelo Keychain (se houver) e tenta outra vez."""
    try:
        return fn()
    except SessionExpired:
        creds = keychain_get()
        if not creds or not p.login(*creds):
            sys.exit(f"NO_SESSION: a sessão do portal expirou. Corre num terminal: python3 {Path(__file__).resolve()} --login")
        return fn()


def find_user_code(p):
    _, page = p.get("conta/AreaDeTrabalho.aspx")
    m = re.search(r"ver_horario\.aspx\?user=(\d+)", page)
    if not m:
        sys.exit("Não encontrei o teu código de utilizador na página inicial do portal.")
    return m.group(1)


def user_code(p):
    if USER_FILE.exists():
        code = json.loads(USER_FILE.read_text()).get("code")
        if code:
            return code
    return session(p, lambda: find_user_code(p))


def strip(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def jsdate(m):
    # o portal gera datas que transbordam (ex: dia 32 de novembro), como o new Date() do JS aceita
    y, mo, d, h, mi = map(int, m)
    return datetime(y + mo // 12, mo % 12 + 1, 1) + timedelta(days=d - 1, hours=h, minutes=mi)


def parse_events(js):
    events = []
    for block in re.split(r"\{\s*'id':\s*\d+\s*,", js)[1:]:
        dates = re.findall(r"new Date\((\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", block)
        if len(dates) < 2:
            continue
        title = (re.search(r"'title':\s*'(.*?)',\s*'body'", block, re.S) or [None, ""])[1]
        body = (re.search(r"'body':\s*'(.*?)',\s*'footer'", block, re.S) or [None, ""])[1]
        footer = (re.search(r"'footer':\s*'(.*?)'\s*,?\s*(?:readOnly|\})", block, re.S) or [None, ""])[1]
        words = strip(title).split()
        uc = re.search(r'ver_edicoes_disciplina\.aspx\?id=(\d+)">([^<&]+)', title)
        sumario = re.search(r'href="([^"]*view_lesson[^"]*)"', footer)
        events.append({
            "start": jsdate(dates[0]), "end": jsdate(dates[1]),
            "uc": uc[2].strip() if uc else (words[0] if words else ""),
            "uc_id": uc[1] if uc else None,
            "tipo": words[1] if uc and len(words) > 1 else "",
            "docentes": re.findall(r'docente\.aspx\?codeuser=\d+"><b>([^<]+)', body),
            "salas": [{"id": i, "nome": n} for i, n in re.findall(r'room=(\d+)"><b>([^<]+)', body)],
            "turmas": [{"id": i, "nome": n, "curso": c}
                       for c, i, n in re.findall(r'title="([^"]*)" href="[^"]*class=(\d+)"><b>([^<]+)', body)],
            "texto": strip(title + " " + body) if not uc else "",
            "sumario": urllib.parse.urljoin(HORARIO, html.unescape(sumario[1])) if sumario else None,
        })
    return sorted(events, key=lambda e: e["start"])


def fetch_week(p, day, kind, code, me):
    def go():
        week = p.method("getCodeWeekByData", data=day.isoformat())
        js = p.method("mudar_semana", code_week=week, code_user=code,
                      entidade=ENTIDADE[kind], code_user_code=me)
        return week, parse_events(js or "")
    return session(p, go)


def ics(events):
    def esc(s):
        return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//isep-portal//horario//PT", "CALSCALE:GREGORIAN",
           "BEGIN:VTIMEZONE", "TZID:Europe/Lisbon",
           "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0000", "TZOFFSETTO:+0100", "TZNAME:WEST",
           "DTSTART:19700329T010000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
           "BEGIN:STANDARD", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0000", "TZNAME:WET",
           "DTSTART:19701025T020000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
           "END:VTIMEZONE"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for e in events:
        sala = ", ".join(s["nome"] for s in e["salas"])
        desc = "\n".join(filter(None, [
            "Docentes: " + ", ".join(e["docentes"]) if e["docentes"] else "",
            "Turmas: " + ", ".join(t["nome"] for t in e["turmas"]) if e["turmas"] else "",
            e["texto"], e["sumario"] or ""]))
        uid = f"{e['start']:%Y%m%dT%H%M}-{e['uc']}-{e['tipo']}-{sala}".replace(" ", "")
        out += ["BEGIN:VEVENT", f"UID:{esc(uid)}@portal.isep.ipp.pt", f"DTSTAMP:{stamp}",
                f"DTSTART;TZID=Europe/Lisbon:{e['start']:%Y%m%dT%H%M00}",
                f"DTEND;TZID=Europe/Lisbon:{e['end']:%Y%m%dT%H%M00}",
                f"SUMMARY:{esc(' '.join(filter(None, [e['uc'], e['tipo']])) or e['texto'][:60])}",
                f"LOCATION:{esc(sala)}", f"DESCRIPTION:{esc(desc)}", "END:VEVENT"]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def cmd_horario(p, args):
    kind, code = "user", None
    for k in ("class", "room"):
        if getattr(args, k):
            kind, code = k, getattr(args, k)
    me = user_code(p)
    code = code or me
    start = date.fromisoformat(args.week) if args.week else date.today()
    start -= timedelta(days=start.weekday())
    events, ids = [], {"turmas": {}, "salas": {}}
    for i in range(args.weeks):
        week, evs = fetch_week(p, start + timedelta(weeks=i), kind, code, me)
        events += evs
        if not args.json and not args.ics:
            print(f"== Semana de {start + timedelta(weeks=i):%d/%m/%Y} (code_week {week}) ==")
            last = None
            for e in evs:
                day = e["start"].date()
                if day != last:
                    print(f"{DIAS[day.weekday()]} {day:%d/%m}")
                    last = day
                where = ", ".join(s["nome"] for s in e["salas"])
                who = ", ".join(t["nome"] for t in e["turmas"])
                what = " ".join(filter(None, [e["uc"], e["tipo"]])) or e["texto"]
                print(f"  {e['start']:%H:%M}-{e['end']:%H:%M}  {what:<12} {', '.join(e['docentes']):<8} {where:<6} {who}")
            if not evs:
                print("  (sem aulas)")
            print()
        for e in evs:
            ids["turmas"].update({t["nome"]: t["id"] for t in e["turmas"]})
            ids["salas"].update({s["nome"]: s["id"] for s in e["salas"]})
    if args.json:
        print(json.dumps(events, default=str, ensure_ascii=False, indent=1))
    elif args.ics:
        path = Path(args.ics).expanduser()
        path.write_text(ics(events), encoding="utf-8")
        print(f"{len(events)} aulas escritas em {path}")
    else:
        for k, v in ids.items():
            if v:
                print(f"ids de {k}: " + ", ".join(f"{n}={i}" for n, i in sorted(v.items())))


def form_values(s):
    """Troca cada <select> pela opção escolhida e cada campo de texto pelo valor preenchido."""
    def sel(m):
        opt = re.search(r'(?is)<option[^>]*selected[^>]*>(.*?)</option>', m[0])
        return f" {strip(opt[1])} " if opt else " "
    s = re.sub(r"(?is)<select.*?</select>", sel, s)
    s = re.sub(r'(?is)<textarea[^>]*>(.*?)</textarea>', r" \1 ", s)

    def inp(m):
        tag = m[0]
        kind = (re.search(r'type="?(\w+)', tag, re.I) or [None, "text"])[1].lower()
        if kind in ("radio", "checkbox"):
            return " [x] " if re.search(r"\bchecked\b", tag, re.I) else ""
        if kind in ("text", "email", "tel", "date", "number"):
            v = re.search(r'value="([^"]*)"', tag, re.I)
            return f" {v[1]} " if v else " "
        return " "
    return re.sub(r"(?is)<input[^>]*>", inp, s)


def html_text(s, links=False):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s or "")
    s = form_values(s)
    if links:
        s = re.sub(r'(?is)<a[^>]*href="([^"#][^"]*)"[^>]*>(.*?)</a>',
                   lambda m: f"{m[2]} <{html.unescape(m[1])}>" if strip(m[2]) else "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = re.sub(r"(?i)<br\s*/?>|</?(tr|p|div|li|h\d|table|legend|thead|tbody)\b[^>]*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = [re.sub(r"[ \t]*\t[ \t]*", "\t", l).strip(" \t") for l in s.split("\n")]
    return "\n".join(l for l in lines if l).strip()


def page_text(page, links=False):
    i = page.find('class="layout_main"')
    return html_text(page[page.find(">", i) + 1:] if i >= 0 else page, links)


def show(d, raw=False):
    if raw or not isinstance(d, str):
        print(d if isinstance(d, str) else json.dumps(d, ensure_ascii=False, indent=1))
    elif d.lstrip()[:1] in ("{", "["):
        print(json.dumps(json.loads(d), ensure_ascii=False, indent=1))
    else:
        print(html_text(d))


def anos(p, me):
    return json.loads(session(p, lambda: p.call(SERAA + "GetStudentYearEditions", cst=int(me))))["years"]


def escolher_ano(lista, pedido):
    """pedido pode ser o código (41) ou o nome (2026/2027 ou 2026); default: o mais recente."""
    if not pedido:
        return lista[-1]
    for a in lista:
        if pedido in (str(a["code"]), a["name"]) or a["name"].startswith(pedido):
            return a
    sys.exit(f"Ano letivo '{pedido}' não encontrado. Disponíveis: " + ", ".join(a["name"] for a in lista))


def cmd_aluno(p, args):
    me = user_code(p)
    ep = {"notas": ("getStudentFileEvent", {"cuser": me}),
          "percurso": ("getDisciplinesEvent", {"cuser": me}),
          "dividas": ("getDividas", {"cuser": me}),
          "requerimentos": ("getRequerimentos", {"code": me})}[args.cmd]
    show(session(p, lambda: p.call(ESTUDANTE + ep[0], **ep[1])), args.raw)


def cmd_parciais(p, args):
    me = user_code(p)
    lista = anos(p, me)
    for a in ([escolher_ano(lista, args.ano)] if args.ano else lista):
        d = session(p, lambda: p.call(ESTUDANTE + "getPartialGradesEventCode",
                                      code_user=me, code_year_edition=str(a["code"])))
        texto = html_text(d)
        print(f"== {a['name']} ==\n{texto or '(sem notas parciais)'}\n")


def cmd_faltas(p, args):
    me = user_code(p)
    a = escolher_ano(anos(p, me), args.ano)
    res = json.loads(session(p, lambda: p.call(SERAA + "GetStudentAttendance", cst=int(me), cye=a["code"])))
    f = res.get("faltas") or {}
    if args.json:
        print(json.dumps(f, ensure_ascii=False, indent=1))
        return
    print(f"== Assiduidade {a['name']} ==")
    for per in f.get("PeriodosLetivos") or []:
        print(f"\n{per['Name']}")
        for uc in per.get("UCs") or []:
            r, at = uc.get("ResumoFaltas") or {}, uc.get("ResumoAtrasos") or {}
            just = sum((t.get("ResumoFaltas") or {}).get("totalFaltasJustificadas", 0) for t in uc.get("TiposAula") or [])
            linha = f"  {uc['Id']:<7} {uc['Name']}: {r.get('Numero', 0)} faltas ({r.get('Horas', 0)}h)"
            if just:
                linha += f", {just} justificadas"
            if at.get("Numero"):
                linha += f", {at['Numero']} atrasos"
            print(linha)
            for t in uc.get("TiposAula") or []:
                for x in t.get("Faltas") or []:
                    tipo = "atraso" if x.get("Atraso") else (x.get("TypeCodeDesc") or "falta")
                    print(f"      {t['Id']:<3} {x['Dia']} {x['Hora']}  {x['NumHoras']}h  {tipo}")
    if not f.get("PeriodosLetivos"):
        print("(sem informação de assiduidade)")


def cmd_call(p, args):
    path, _, name = args.endpoint.rpartition("/")
    if not re.match(r"(?i)get", name):
        sys.exit("Por segurança, o call só chama métodos de leitura (cujo nome começa por get/Get).")
    me = user_code(p)
    params = json.loads(args.params.replace("{me}", me)) if args.params else {}
    show(session(p, lambda: p.call(args.endpoint, **params)), args.raw)


def cmd_menu(p, args):
    _, page = session(p, lambda: p.get("conta/AreaDeTrabalho.aspx"))
    m = re.search(r'(?is)<ul[^>]*id="smart-menu[^"]*".*?</ul>\s*</div>', page)
    menu = m[0] if m else page
    for href, label in re.findall(r'(?is)<a[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', menu):
        href = urllib.parse.urljoin(BASE + "conta/", html.unescape(href))
        print(f"{strip(label):<50} {href.replace(BASE, '')}")


def cmd_get(p, args):
    final, page = session(p, lambda: p.get(args.path))
    print(f"# {final}\n")
    print(page if args.raw else page_text(page, args.links))


def main():
    ap = argparse.ArgumentParser(description="Ler o portal do ISEP")
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--logout", action="store_true", help="apaga a sessão e a password do Keychain")
    sub = ap.add_subparsers(dest="cmd")
    h = sub.add_parser("horario", help="horário semanal (teu, de uma turma ou de uma sala)")
    g = h.add_mutually_exclusive_group()
    g.add_argument("--class", dest="class", metavar="ID", help="id da turma")
    g.add_argument("--room", metavar="ID", help="id da sala")
    h.add_argument("--week", metavar="AAAA-MM-DD", help="um dia da semana pretendida (default: hoje)")
    h.add_argument("--weeks", type=int, default=1, help="quantas semanas a partir dessa (default 1)")
    h.add_argument("--json", action="store_true")
    h.add_argument("--ics", metavar="FICHEIRO", help="exportar para calendário (.ics)")
    sub.add_parser("menu", help="lista as páginas do menu da intranet")
    gp = sub.add_parser("get", help="mostra qualquer página da intranet em texto")
    gp.add_argument("path", help="ex: educacao/ver_calendario_escolar.aspx ou URL completo")
    gp.add_argument("--links", action="store_true", help="mostra o destino dos links")
    gp.add_argument("--raw", action="store_true", help="HTML em bruto")
    for name, desc in [("notas", "notas finais de todas as UCs (ficha do estudante)"),
                       ("percurso", "inscrição atual: UCs, turmas, ECTS, estatuto"),
                       ("dividas", "conta corrente: faturas, pagamentos, valores pendentes"),
                       ("requerimentos", "os teus requerimentos")]:
        sub.add_parser(name, help=desc).add_argument("--raw", action="store_true", help="HTML em bruto")
    pp = sub.add_parser("parciais", help="notas parciais (avaliação contínua, época normal, recurso)")
    pp.add_argument("--ano", help="ano letivo, ex: 2025/2026 (default: todos)")
    fp = sub.add_parser("faltas", help="assiduidade: faltas e atrasos por UC e tipo de aula")
    fp.add_argument("--ano", help="ano letivo, ex: 2025/2026 (default: o atual)")
    fp.add_argument("--json", action="store_true")
    cp = sub.add_parser("call", help="chama um WebMethod de leitura do portal (avançado)")
    cp.add_argument("endpoint", help="ex: areapessoal/estudante.aspx/getDividas")
    cp.add_argument("params", nargs="?", help='JSON, ex: \'{"cuser": "{me}"}\' ({me} = o teu código)')
    cp.add_argument("--raw", action="store_true")
    args = ap.parse_args()

    if args.logout:
        COOKIES.unlink(missing_ok=True)
        if USER_FILE.exists():
            user = json.loads(USER_FILE.read_text()).get("login")
            if sys.platform == "darwin":
                subprocess.run(["security", "delete-generic-password", "-a", user, "-s", KEYCHAIN], capture_output=True)
            USER_FILE.unlink()
        print("Sessão do portal apagada.")
        return
    p = Portal()
    if args.login:
        interactive_login(p)
        if not args.cmd:
            return
    if not COOKIES.exists() and not keychain_get():
        interactive_login(p)
    cmds = {"horario": cmd_horario, "menu": cmd_menu, "get": cmd_get, "parciais": cmd_parciais,
            "faltas": cmd_faltas, "call": cmd_call, **dict.fromkeys(["notas", "percurso", "dividas", "requerimentos"], cmd_aluno)}
    cmds.get(args.cmd, lambda *_: ap.print_help())(p, args)


if __name__ == "__main__":
    main()
