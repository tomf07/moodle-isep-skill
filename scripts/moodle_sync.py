#!/usr/bin/env python3
"""Sincroniza os ficheiros (fichas, slides, enunciados...) do Moodle do ISEP.

Usa a API da app mobile do Moodle. Só descarrega o que é novo ou foi alterado.

    python3 moodle_sync.py            # cadeiras em curso
    python3 moodle_sync.py --all      # todas as cadeiras onde estás inscrito
    python3 moodle_sync.py --list     # só mostra as cadeiras
    python3 moodle_sync.py -c ESINF   # só cadeiras cujo nome contém "ESINF"
    python3 moodle_sync.py --dry-run  # mostra o que ia sacar sem sacar
    python3 moodle_sync.py --login    # (re)faz login e guarda o token
    python3 moodle_sync.py --logout   # apaga o token guardado
"""
import argparse
import getpass
import json
import os
import re
import sys
import time
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


def main():
    ap = argparse.ArgumentParser(description="Sacar ficheiros do Moodle do ISEP")
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("-c", "--course", action="append", help="filtrar cadeiras por nome (repetível)")
    ap.add_argument("--all", action="store_true", help="incluir cadeiras antigas")
    ap.add_argument("--list", action="store_true", help="só listar cadeiras")
    ap.add_argument("--dry-run", action="store_true")
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
    if args.course:
        needles = [n.lower() for n in args.course]
        courses = [c for c in courses
                   if any(n in (c.get("shortname", "") + " " + c.get("fullname", "")).lower()
                          for n in needles)]

    if args.list or not courses:
        print(f"{len(courses)} cadeira(s):")
        for c in courses:
            print(f"  [{c['id']}] {c.get('shortname')} — {c.get('fullname')}")
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
