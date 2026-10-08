#!/usr/bin/env python3
"""Sincroniza os ficheiros (fichas, slides, enunciados...) do Moodle do ISEP.

Usa a API da app mobile do Moodle. Só descarrega o que é novo ou foi alterado.

    python3 moodle_sync.py            # cadeiras em curso
    python3 moodle_sync.py --all      # todas as cadeiras onde estás inscrito
    python3 moodle_sync.py --list     # só mostra as cadeiras
    python3 moodle_sync.py -c ESINF   # só cadeiras cujo nome contém "ESINF"
    python3 moodle_sync.py --dry-run  # mostra o que ia sacar sem sacar
    python3 moodle_sync.py --forums   # anúncios/discussões recentes (--since 14d por defeito)
    python3 moodle_sync.py --forums -c ESINF --since 30d
    python3 moodle_sync.py --login    # (re)faz login e guarda o token
    python3 moodle_sync.py --logout   # apaga o token guardado
"""
import argparse
import getpass
import html
import json
import os
import re
import sys
import time
from datetime import datetime
import urllib.parse
import urllib.request
from pathlib import Path

SITE = "https://moodle.isep.ipp.pt"
TOKEN_FILE = Path.home() / ".config" / "moodle-sync" / "token"
DEFAULT_OUT = Path.home() / "Documents" / "ISEP" / "Moodle"
UA = "Mozilla/5.0 (Macintosh) MoodleMobile"


def http(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60)


def get_token(force_login=False):
    if os.environ.get("MOODLE_TOKEN") and not force_login:
        return os.environ["MOODLE_TOKEN"]
    if TOKEN_FILE.exists() and not force_login:
        return TOKEN_FILE.read_text().strip()
    if not sys.stdin.isatty():
        sys.exit(f"NO_TOKEN: sem login. Corre num terminal: python3 {Path(__file__).resolve()} --login")

    print("Login no Moodle do ISEP (a password só é enviada ao moodle.isep.ipp.pt, não fica guardada).")
    user = input("Utilizador (ex: 1231234): ").strip()
    pwd = getpass.getpass("Password: ")
    with http(f"{SITE}/login/token.php",
              {"username": user, "password": pwd, "service": "moodle_mobile_app"}) as r:
        res = json.load(r)
    if "token" not in res:
        sys.exit(f"Login falhou: {res.get('error') or res}")
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(res["token"])
    TOKEN_FILE.chmod(0o600)
    print(f"Token guardado em {TOKEN_FILE}\n")
    return res["token"]


class Moodle:
    def __init__(self, token):
        self.token = token

    def call(self, fn, **params):
        data = {"wstoken": self.token, "wsfunction": fn, "moodlewsrestformat": "json"}
        for k, v in params.items():
            if isinstance(v, list):
                for i, item in enumerate(v):
                    for kk, vv in item.items():
                        data[f"{k}[{i}][{kk}]"] = vv
            else:
                data[k] = v
        with http(f"{SITE}/webservice/rest/server.php", data) as r:
            res = json.load(r)
        if isinstance(res, dict) and res.get("exception"):
            if res.get("errorcode") in ("invalidtoken", "accessexception"):
                TOKEN_FILE.unlink(missing_ok=True)
                sys.exit(f"NO_TOKEN: token inválido/expirado. Corre num terminal: python3 {Path(__file__).resolve()} --login")
            raise RuntimeError(f"{fn}: {res.get('message')}")
        return res

    def courses(self, all_courses):
        if not all_courses:
            try:
                res = self.call("core_course_get_enrolled_courses_by_timeline_classification",
                                classification="inprogress", limit=0)
                return res["courses"]
            except RuntimeError:
                pass  # fallback abaixo
        uid = self.call("core_webservice_get_site_info")["userid"]
        cs = self.call("core_enrol_get_users_courses", userid=uid)
        if not all_courses:
            now = time.time()
            cs = [c for c in cs if not c.get("enddate") or c["enddate"] > now]
        return cs

    def download(self, fileurl, dest, mtime):
        sep = "&" if "?" in fileurl else "?"
        tmp = dest.with_name(dest.name + ".part")
        with http(f"{fileurl}{sep}token={self.token}") as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)
        tmp.replace(dest)
        if mtime:
            os.utime(dest, (mtime, mtime))


def clean(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name[:150] or "_"


def iter_files(sections):
    """Gera (pasta_relativa, ficheiro) para cada ficheiro em recursos/pastas/etc."""
    for i, sec in enumerate(sections):
        sec_name = clean(f"{i:02d} {sec.get('name') or 'Secção'}")
        for mod in sec.get("modules", []):
            if mod.get("modname") in ("forum", "url", "label", "page"):
                continue
            files = [c for c in mod.get("contents") or [] if c.get("type") == "file"]
            if not files:
                continue
            base = Path(sec_name)
            # Pastas e recursos com vários ficheiros ficam numa subpasta com o nome da atividade
            if mod["modname"] == "folder" or len(files) > 1:
                base = base / clean(mod["name"])
            for f in files:
                sub = (f.get("filepath") or "/").strip("/")
                rel = base / Path(*[clean(p) for p in sub.split("/")]) if sub else base
                yield rel, f


def html_to_text(s):
    s = re.sub(r"\s+", " ", s or "")  # quebras de linha no HTML não contam
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", s or "")
    s = re.sub(r"(?i)<li[^>]*>", "- ", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = "\n".join(line.strip() for line in s.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def parse_since(v):
    if v == "all":
        return 0
    m = re.fullmatch(r"(\d+)([hdw])", v)
    if m:
        n, unit = int(m[1]), m[2]
        return time.time() - n * {"h": 3600, "d": 86400, "w": 604800}[unit]
    return datetime.strptime(v, "%Y-%m-%d").timestamp()


def fmt_time(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def forums(m, courses, needles, since, args):
    """Mostra discussões dos fóruns modificadas desde `since` e saca os anexos dos posts."""
    by_id = {c["id"]: c for c in courses}
    params = {f"courseids[{i}]": c["id"] for i, c in enumerate(courses)}
    shown = files = 0
    for fo in m.call("mod_forum_get_forums_by_courses", **params):
        c = by_id.get(fo["course"], {})
        cname = clean(c.get("shortname") or str(fo["course"]))
        hay = f"{c.get('shortname', '')} {c.get('fullname', '')} {fo['name']}".lower()
        if needles and not any(n in hay for n in needles):
            continue
        if not fo.get("numdiscussions"):
            continue

        header_done = False
        page = 0
        while True:
            res = m.call("mod_forum_get_forum_discussions", forumid=fo["id"], page=page, perpage=25)
            ds = res.get("discussions", [])
            if not ds:
                break
            stop = False
            for d in ds:
                last = max(d.get("timemodified") or 0, d.get("modified") or 0)
                if last < since:
                    # Ordenadas por último post; as afixadas vêm primeiro, por isso só paramos nas outras
                    if not d.get("pinned"):
                        stop = True
                    continue
                if not header_done:
                    print(f"\n######## {cname} / {fo['name']}")
                    header_done = True
                shown += 1
                files += print_discussion(m, d, args.out / cname / "Forum" / clean(fo["name"]), args)
            if stop or len(ds) < 25:
                break
            page += 1
    print(f"\n{shown} discussão(ões) desde {fmt_time(since) if since else 'sempre'}, {files} anexo(s) novo(s).")


def print_discussion(m, d, folder, args):
    posts = m.call("mod_forum_get_discussion_posts", discussionid=d["discussion"],
                   sortby="created", sortdirection="ASC")["posts"]
    pin = " [afixado]" if d.get("pinned") else ""
    print(f"\n=== {d['name']}{pin}  ({len(posts)} post(s))")
    print(f"    {posts[0]['urls']['discuss'] if posts else ''}")
    downloaded = 0
    for p in posts:
        indent = "    " if p.get("hasparent") else ""
        print(f"\n{indent}--- {p['author']['fullname']} · {fmt_time(p['timecreated'])}")
        text = html_to_text(p["message"])
        if args.max_chars and len(text) > args.max_chars:
            text = text[:args.max_chars] + " [...]"
        print("\n".join(indent + line for line in text.splitlines()))
        for a in p.get("attachments") or []:
            dest = folder / clean(d["name"]) / clean(a["filename"])
            print(f"{indent}    [anexo] {dest}")
            if dest.exists() or args.dry_run:
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Anexos de posts vêm com `url` (pluginfile.php); com token tem de ser webservice/pluginfile.php
                url = a.get("fileurl") or a["url"]
                if "/webservice/pluginfile.php" not in url:
                    url = url.replace("/pluginfile.php", "/webservice/pluginfile.php", 1)
                m.download(url, dest, a.get("timemodified") or 0)
                downloaded += 1
            except Exception as e:
                print(f"{indent}      ! falhou: {e}")
    return downloaded


def main():
    ap = argparse.ArgumentParser(description="Sacar ficheiros do Moodle do ISEP")
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("-c", "--course", action="append", help="filtrar cadeiras por nome (repetível)")
    ap.add_argument("--all", action="store_true", help="incluir cadeiras antigas")
    ap.add_argument("--list", action="store_true", help="só listar cadeiras")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--forums", action="store_true", help="ler fóruns em vez de sacar ficheiros")
    ap.add_argument("--since", default="14d", help="com --forums: 7d, 24h, 2w, 2026-09-01 ou all (default 14d)")
    ap.add_argument("--max-chars", type=int, default=3000, help="com --forums: corta posts maiores (0 = sem limite)")
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--logout", action="store_true")
    args = ap.parse_args()

    if args.logout:
        TOKEN_FILE.unlink(missing_ok=True)
        print("Token apagado.")
        return

    if args.login:
        get_token(force_login=True)
        print("Login OK.")
        return

    m = Moodle(get_token())
    courses = m.courses(args.all)
    if args.forums:
        # O filtro também apanha nomes de fóruns (ex: o fórum "ESINF" dentro da página SEM_3_PI)
        forums(m, courses, [n.lower() for n in args.course or []], parse_since(args.since), args)
        return
    if args.course:
        needles = [n.lower() for n in args.course]
        courses = [c for c in courses
                   if any(n in (c.get("shortname", "") + " " + c.get("fullname", "")).lower()
                          for n in needles)]

    if args.list or not courses:
        print(f"{len(courses)} cadeira(s):")
        for c in courses:
            print(f"  [{c['id']}] {c.get('shortname')} - {c.get('fullname')}")
        return

    new = updated = skipped = failed = 0
    for c in courses:
        cname = clean(c.get("shortname") or c.get("fullname") or str(c["id"]))
        print(f"\n== {cname}")
        try:
            sections = m.call("core_course_get_contents", courseid=c["id"])
        except Exception as e:
            print(f"   ! não consegui ler a cadeira: {e}")
            failed += 1
            continue
        for rel, f in iter_files(sections):
            dest = args.out / cname / rel / clean(f["filename"])
            mtime = f.get("timemodified") or 0
            if dest.exists():
                st = dest.stat()
                same_size = not f.get("filesize") or st.st_size == f["filesize"]
                if same_size and (not mtime or int(st.st_mtime) >= mtime):
                    skipped += 1
                    continue
                tag = "~"
            else:
                tag = "+"
            print(f"   {tag} {rel / dest.name}")
            if args.dry_run:
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                m.download(f["fileurl"], dest, mtime)
                if tag == "+":
                    new += 1
                else:
                    updated += 1
            except Exception as e:
                print(f"     ! falhou: {e}")
                failed += 1

    print(f"\nFeito: {new} novos, {updated} atualizados, {skipped} já tinhas, {failed} falhas → {args.out}")


if __name__ == "__main__":
    main()
