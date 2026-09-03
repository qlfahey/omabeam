#!/usr/bin/env python3
import http.server, json, subprocess, secrets, socket, urllib.parse, time, os, re, glob, shlex, shutil, hmac, sys

VERSION = "0.5.0"
PORT = int(os.environ.get("OMABEAM_PORT", "8899"))
URLFILE = os.path.expanduser("~/.cache/omabeam/session")
os.makedirs(os.path.dirname(URLFILE), exist_ok=True)
os.environ.setdefault("YDOTOOL_SOCKET", "%s/.ydotool_socket" % (os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()))
HAS_OMASPACES = shutil.which("omaspaces") is not None

def check_deps():
    need = [c for c in ("hyprctl", "grim", "wtype") if not shutil.which(c)]
    if need:
        print("omabeam: missing required commands: %s" % ", ".join(need), file=sys.stderr)
        sys.exit(1)
    if not shutil.which("ydotool"):
        print("omabeam: warning — ydotool not found; touch/keyboard input will not work", file=sys.stderr)

def load_token():
    try:
        tok = open(URLFILE).read().splitlines()[1].strip()
        if tok:
            return tok
    except Exception:
        pass
    return secrets.token_urlsafe(16)

TOKEN = load_token()

SEEN = set()
def note_client(ip):
    if ip in SEEN:
        return
    SEEN.add(ip)
    print("omabeam: device connected from %s" % ip, flush=True)
    if shutil.which("notify-send"):
        try:
            subprocess.Popen(["notify-send", "omabeam", "A device connected (%s)" % ip],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("1.1.1.1", 80)); return s.getsockname()[0]
    finally:
        s.close()

def hj(*a):
    try:
        return json.loads(subprocess.run(["hyprctl", *a, "-j"], capture_output=True, text=True).stdout)
    except Exception:
        return None

CUR = {"addr": None, "geom": None}

# --- Compositor compatibility layer -----------------------------------------
# This Omarchy build binds `hyprctl dispatch` to a Lua parser (hl.dsp.*); a
# stock Hyprland uses classic string dispatchers. Detect which and speak it, so
# omabeam runs on both instead of only the machine it was written on.
def _hypr(s):
    return subprocess.run(["hyprctl", "dispatch", s], capture_output=True, text=True)

def _detect_mode():
    try:
        r = _hypr('hl.dsp.exec_cmd("true")')
        return "lua" if r.returncode == 0 and (r.stdout or "").strip() == "ok" else "classic"
    except Exception:
        return "classic"

DISPATCH_MODE = _detect_mode()

def dispatch(snip):  # raw passthrough (lua snippet); kept for lua-only call sites
    _hypr(snip)

def d_focus_ws(n):
    _hypr('hl.dsp.focus({ workspace = "%s" })' % n) if DISPATCH_MODE == "lua" else _hypr("workspace %s" % n)

def d_cursor(x, y):
    x, y = int(round(x)), int(round(y))
    _hypr('hl.dsp.cursor.move({ x = %d, y = %d })' % (x, y)) if DISPATCH_MODE == "lua" else _hypr("movecursor %d %d" % (x, y))

def d_focus_win(a):
    _hypr('hl.dsp.focus({ window = "address:%s" })' % a) if DISPATCH_MODE == "lua" else _hypr("focuswindow address:%s" % a)

def d_close(a):
    _hypr('hl.dsp.window.close({ window = "address:%s" })' % a) if DISPATCH_MODE == "lua" else _hypr("closewindow address:%s" % a)

def d_float(a, action):  # action in {on, off, toggle}
    if DISPATCH_MODE == "lua":
        _hypr('hl.dsp.window.float({ window = "address:%s", action = "%s" })' % (a, action))
    else:
        c = client_by_addr(a); fl = bool(c and c.get("floating"))
        if action == "toggle" or (action == "on" and not fl) or (action == "off" and fl):
            _hypr("togglefloating address:%s" % a)

def d_resize(a, w, h):
    _hypr('hl.dsp.window.resize({ window = "address:%s", x = %d, y = %d, relative = false })' % (a, w, h)) if DISPATCH_MODE == "lua" else _hypr("resizewindowpixel exact %d %d,address:%s" % (w, h, a))

def d_move(a, x, y):
    _hypr('hl.dsp.window.move({ window = "address:%s", x = %d, y = %d, relative = false })' % (a, x, y)) if DISPATCH_MODE == "lua" else _hypr("movewindowpixel exact %d %d,address:%s" % (x, y, a))

def d_fullscreen(a):
    if DISPATCH_MODE == "lua":
        _hypr('hl.dsp.window.fullscreen({ window = "address:%s", mode = "fullscreen" })' % a)
    else:
        d_focus_win(a); _hypr("fullscreen 0")

def d_to_ws(a, ws):
    _hypr('function() hl.dispatch(hl.dsp.window.move({ window = "address:%s", workspace = "%s", follow = false })) end' % (a, ws)) if DISPATCH_MODE == "lua" else _hypr("movetoworkspacesilent %s,address:%s" % (ws, a))

def focus_ws(n):
    d_focus_ws(n)

def mon_primary():
    return (hj("monitors") or [{}])[0]

def portrait_rect(pw, ph):
    m = mon_primary(); s = m.get("scale", 1) or 1
    lw, lh = round(m.get("width", 1920) / s), round(m.get("height", 1080) / s)
    rl, rt, rr, rb = (m.get("reserved") or [0, 0, 0, 0])
    uw, uh = lw - rl - rr - 16, lh - rt - rb - 16
    pa = (pw / ph) if ph else 0.5
    h = uh; w = h * pa
    if w > uw: w = uw; h = w / pa
    w, h = int(w), int(h)
    return w, h, rl + (uw - w) // 2 + 8, rt + (uh - h) // 2 + 8

def shape_window(addr, pw, ph, floated):
    w, h, x, y = portrait_rect(pw, ph)
    if CUR["geom"] == (addr, w, h, x, y):
        return
    CUR["geom"] = (addr, w, h, x, y)
    if not floated:
        d_float(addr, "on")
    d_resize(addr, w, h)
    d_move(addr, x, y)
    d_focus_win(addr)

def phone_enter(addr, pw, ph):
    c = client_by_addr(addr)
    if not c:
        return
    if CUR["addr"] != addr:
        CUR["geom"] = None
    CUR["addr"] = addr
    if c.get("workspace", {}).get("id") != (mon_primary().get("activeWorkspace") or {}).get("id"):
        focus_ws(c["workspace"]["id"])
    shape_window(addr, pw, ph, bool(c.get("floating")))

def phone_leave(addr):
    d_float(addr, "off")
    CUR["addr"] = None; CUR["geom"] = None

def clients():
    return [c for c in (hj("clients") or [])
            if c.get("mapped") and c.get("workspace", {}).get("id", 0) > 0 and c.get("size", [0, 0])[0] > 0]

def client_by_addr(addr):
    for c in (hj("clients") or []):
        if c.get("address") == addr:
            return c
    return None

def mon_logical():
    m = mon_primary()
    s = m.get("scale", 1) or 1
    return round(m.get("width", 1920) / s), round(m.get("height", 1080) / s)

def state():
    wss = hj("workspaces") or []
    p = mon_primary()
    px, py = p.get("x", 0), p.get("y", 0)
    active = (p.get("activeWorkspace") or {}).get("id")
    lw, lh = mon_logical()
    occ = {w["id"]: w.get("windows", 0) for w in wss}
    cs = clients()
    ids = sorted(set([1, 2, 3, 4, 5] + [w["id"] for w in wss if 0 < w["id"] <= 10]
                     + [c["workspace"]["id"] for c in cs]))
    wins = [{"ws": c["workspace"]["id"], "app": (c.get("class") or "").split(".")[-1],
             "title": c.get("title") or "", "x": c["at"][0] - px, "y": c["at"][1] - py,
             "w": c["size"][0], "h": c["size"][1], "addr": c.get("address", "")} for c in cs]
    return {"active": active, "lw": lw, "lh": lh,
            "workspaces": [{"id": i, "n": occ.get(i, 0)} for i in ids], "wins": wins}

def grab(addr=None):
    args = ["grim", "-t", "jpeg", "-q", "55"]
    if addr:
        c = client_by_addr(addr)
        if c:
            args += ["-g", "%d,%d %dx%d" % (c["at"][0], c["at"][1], c["size"][0], c["size"][1])]
    return subprocess.run(args + ["-"], capture_output=True).stdout

def move(lx, ly):
    d_cursor(lx, ly)

def to_screen(fx, fy, addr):
    if addr:
        c = client_by_addr(addr)
        if c:
            return c["at"][0] + fx * c["size"][0], c["at"][1] + fy * c["size"][1]
    lw, lh = mon_logical()
    return fx * lw, fy * lh

def click(fx, fy, addr, button="0xC0"):
    sx, sy = to_screen(fx, fy, addr)
    move(sx, sy)
    time.sleep(0.015)
    subprocess.run(["ydotool", "click", button], capture_output=True)

def scroll(dy):
    if CUR["addr"]:
        c = client_by_addr(CUR["addr"])
        if c:
            move(c["at"][0] + c["size"][0] / 2, c["at"][1] + c["size"][1] / 2)
    subprocess.run(["ydotool", "mousemove", "-w", "--", "0", str(int(dy))], capture_output=True)

def focus_addr(addr):
    d_focus_win(addr)

def theme():
    colors, mode = {}, "dark"
    path = os.path.expanduser("~/.local/state/omarchy/current/theme/colors.toml")
    try:
        for line in open(path):
            m = re.match(r'\s*([A-Za-z_]+)\s*=\s*"?(#[0-9A-Fa-f]{6})', line)
            if m: colors[m.group(1)] = m.group(2)
            mm = re.match(r'\s*mode\s*=\s*"?(\w+)', line)
            if mm: mode = mm.group(1)
    except Exception:
        pass
    font = subprocess.run(["omarchy", "font", "current"], capture_output=True, text=True).stdout.strip() or "monospace"
    def gi(opt):
        d = hj("getoption", opt) or {}
        try: return int(d.get("int", 0))
        except Exception: return 0
    return {"colors": colors, "mode": mode, "font": font,
            "border": gi("general:border_size"), "rounding": gi("decoration:rounding")}

def font_file():
    fam = theme()["font"]
    p = subprocess.run(["fc-match", "-f", "%{file}", fam], capture_output=True, text=True).stdout.strip()
    return p if p and os.path.exists(p) else None

def type_text(s):
    if CUR["addr"]: focus_addr(CUR["addr"])
    subprocess.run(["wtype", s], capture_output=True)

def key(name, mods=""):
    if CUR["addr"]: focus_addr(CUR["addr"])
    ms = [m for m in mods.split(",") if m]
    args = ["wtype"]
    for m in ms: args += ["-M", m]
    args += ["-k", name]
    for m in reversed(ms): args += ["-m", m]
    subprocess.run(args, capture_output=True)

def sh(*args):
    try: subprocess.Popen(list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception: pass

def sh_out(*args, timeout=6):
    try: return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout).stdout
    except Exception: return ""

def themes():
    cur = sh_out("omarchy", "theme", "current").strip()
    lst = [l.strip() for l in sh_out("omarchy", "theme", "list").splitlines() if l.strip()]
    return {"current": cur, "list": lst}

def layouts():
    res = []
    for l in sh_out("omaspaces", "list").splitlines():
        m = re.match(r'\s+(\S+)\s+(\d+)\s+tiles?\s*[·-]?\s*(.*)', l)
        if m:
            res.append({"name": m.group(1), "tiles": int(m.group(2)), "apps": m.group(3).strip()})
    return res

def win_action(addr, do):
    if do == "close":   d_close(addr)
    elif do == "float": d_float(addr, "toggle")
    elif do == "fs":    d_fullscreen(addr)

def move_win(addr, ws):
    d_to_ws(addr, ws)

OMARCHY = os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")
MENU_DEFAULT = OMARCHY + "/default/omarchy/omarchy-menu.jsonc"
MENU_USER = os.path.expanduser("~/.config/omarchy/extensions/omarchy-menu.jsonc")

def _strip_jsonc(raw):
    raw = re.sub(r'^\s*//[^\n]*(\n|$)', '', raw, flags=re.M)
    return re.sub(r',(\s*[}\]])', r'\1', raw)

def _parse_items(raw):
    try:
        obj = json.loads(_strip_jsonc(raw))
    except Exception:
        return {}
    src = obj.get("items") if isinstance(obj.get("items"), dict) else obj
    out = {}
    for i, v in src.items():
        if not isinstance(v, dict): continue
        parent = v.get("parent")
        if parent is None: parent = i.rsplit(".", 1)[0] if "." in i else "root"
        if i == "root": parent = ""
        out[i] = {"id": i, "parent": parent,
                  "kind": "action" if v.get("action") else ("link" if v.get("target") else "menu"),
                  "icon": v.get("icon", ""), "iconFont": v.get("iconFont", ""), "label": v.get("label", i),
                  "target": v.get("target", ""), "action": v.get("action", ""), "provider": v.get("provider", ""),
                  "when": v.get("when", ""), "checked": v.get("checked", "")}
    return out

def menu_items():
    d = {}
    try: d = _parse_items(open(MENU_DEFAULT).read())
    except Exception: pass
    try:
        for k, v in _parse_items(open(MENU_USER).read()).items():
            d[k] = v if k not in d else {**d[k], **v}
    except Exception: pass
    return d

GUARD_PRELUDE = (
    'declare -A __P=(); while read -r n; do __P[$n]=1; done < <(pacman -Qq 2>/dev/null)\n'
    'omarchy-pkg-present(){ local p; for p in "$@"; do [[ -n ${__P[$p]-} ]]||return 1;done;return 0;}\n'
    'omarchy-pkg-missing(){ local p; for p in "$@"; do [[ -n ${__P[$p]-} ]]||return 0;done;return 1;}\n'
    'omarchy-cmd-present(){ local c; for c in "$@"; do command -v "$c" &>/dev/null||return 1;done;return 0;}\n'
    'omarchy-cmd-missing(){ local c; for c in "$@"; do command -v "$c" &>/dev/null||return 0;done;return 1;}\n')

def eval_guards(items):
    lines = []
    for it in items.values():
        if it["when"]:    lines.append('if { %s; } >/dev/null 2>&1; then echo "%s|w|1"; else echo "%s|w|0"; fi' % (it["when"], it["id"], it["id"]))
        if it["checked"]: lines.append('if { %s; } >/dev/null 2>&1; then echo "%s|c|1"; else echo "%s|c|0"; fi' % (it["checked"], it["id"], it["id"]))
    wr, cr = {}, {}
    if not lines: return wr, cr
    try:
        out = subprocess.run(["bash", "-c", GUARD_PRELUDE + "\n".join(lines)], capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return wr, cr
    for ln in out.splitlines():
        p = ln.split("|")
        if len(p) == 3:
            (wr if p[1] == "w" else cr)[p[0]] = (p[2] == "1")
    return wr, cr

def app_rows():
    rows, seen = [], set()
    for d in [os.path.expanduser("~/.local/share/applications"), "/usr/share/applications", "/usr/local/share/applications"]:
        for f in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            did = os.path.basename(f)[:-8]
            if did in seen: continue
            try: txt = open(f).read()
            except Exception: continue
            if re.search(r'^\s*NoDisplay\s*=\s*true', txt, re.M | re.I): continue
            if re.search(r'^\s*Type\s*=\s*(?!Application)', txt, re.M | re.I): continue
            nm = re.search(r'^\s*Name\s*=\s*(.+)$', txt, re.M)
            if not nm: continue
            seen.add(did)
            rows.append({"id": "apps." + did, "parent": "apps", "kind": "action", "icon": "", "iconFont": "",
                         "label": nm.group(1).strip(), "target": "", "action": "gtk-launch " + shlex.quote(did),
                         "provider": "", "checked": False})
    rows.sort(key=lambda r: r["label"].lower())
    return rows

_MENU_CACHE = {"t": 0, "data": None}
def menu_tree():
    if _MENU_CACHE["data"] and time.time() - _MENU_CACHE["t"] < 4:
        return _MENU_CACHE["data"]
    items = menu_items()
    wr, cr = eval_guards(items)
    out = []
    for it in items.values():
        if it["when"] and wr.get(it["id"]) is False: continue
        out.append({"id": it["id"], "parent": it["parent"], "kind": it["kind"], "icon": it["icon"],
                    "iconFont": it["iconFont"], "label": it["label"], "target": it["target"],
                    "action": it["action"], "provider": it["provider"],
                    "checked": bool(it["checked"] and cr.get(it["id"]))})
    if any(i["provider"] == "apps" for i in out):
        out += app_rows()
    # omaspaces additions, folded into the same menu
    out.append({"id": "spaces", "parent": "root", "kind": "menu", "icon": "\U000f00c8", "iconFont": "", "label": "Spaces", "target": "", "action": "", "provider": "", "checked": False})
    out.append({"id": "spaces.fullcontrol", "parent": "spaces", "kind": "action", "icon": "\U000f0379", "iconFont": "", "label": "Full desktop control", "target": "", "action": "app:fullcontrol", "provider": "", "checked": False})
    if HAS_OMASPACES:
        out.append({"id": "spaces.build", "parent": "spaces", "kind": "action", "icon": "\U000f0b4c", "iconFont": "", "label": "Build a workspace", "target": "", "action": "app:build", "provider": "", "checked": False})
        for l in layouts():
            out.append({"id": "spaces.layout." + l["name"], "parent": "spaces", "kind": "action", "icon": "\U000f04ac", "iconFont": "",
                        "label": "Open " + l["name"], "target": "", "action": "omaspaces apply " + shlex.quote(l["name"]),
                        "provider": "", "checked": False})
        out.append({"id": "spaces.save", "parent": "spaces", "kind": "action", "icon": "\U000f0193", "iconFont": "", "label": "Save current space", "target": "", "action": "app:save", "provider": "", "checked": False})
    # phone-usable pickers: Theme becomes an in-menu list; Background cycles directly
    byid = {i["id"]: i for i in out}
    if "style.theme" in byid:
        byid["style.theme"]["kind"] = "menu"; byid["style.theme"]["action"] = ""
        th = themes()
        for n in th["list"]:
            sl = "style.theme." + re.sub(r'[^a-z0-9]+', '-', n.lower()).strip('-')
            out.append({"id": sl, "parent": "style.theme", "kind": "action", "icon": "\U000f0c8c", "iconFont": "",
                        "label": n, "target": "", "action": "omarchy theme set " + shlex.quote(n), "provider": "",
                        "checked": (n == th["current"])})
    if "style.background" in byid:
        byid["style.background"]["kind"] = "action"; byid["style.background"]["action"] = "omarchy theme bg next"
    _MENU_CACHE.update(t=time.time(), data=out)
    return out

def menu_run(idv):
    action = ""
    for i in menu_tree():
        if i["id"] == idv:
            action = i.get("action", ""); break
    if action and not action.startswith("app:"):
        try: subprocess.Popen(["bash", "-lc", action], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception: pass

def apps_json():
    try:
        return json.loads(sh_out("omaspaces", "apps", "--json"))
    except Exception:
        return []

def build_layout(name, tiles_json, apply):
    try:
        tiles = json.loads(tiles_json)
    except Exception:
        return
    doc = json.dumps({"name": name, "tiles": tiles})
    sh = 'printf %s "$1" | omaspaces import "$2" -'
    if apply:
        sh += ' && omaspaces apply "$2"'
    try:
        subprocess.Popen(["bash", "-lc", sh, "omabeam", doc, name],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass

PAGE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "phone.html")).read()

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def ok(self, q):
        t = q.get("t", [""])[0] or ""
        good = hmac.compare_digest(t, TOKEN)
        if good:
            note_client(self.client_address[0])
        return good

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/": return self.send(200, PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/api/state": return self.send(200 if self.ok(q) else 403, state() if self.ok(q) else {"error": "token"})
        if u.path == "/api/theme": return self.send(200 if self.ok(q) else 403, theme() if self.ok(q) else {"error": "token"})
        if u.path == "/api/themes": return self.send(200 if self.ok(q) else 403, themes() if self.ok(q) else {"error": "token"})
        if u.path == "/api/layouts": return self.send(200 if self.ok(q) else 403, layouts() if self.ok(q) else {"error": "token"})
        if u.path == "/api/apps": return self.send(200 if self.ok(q) else 403, apps_json() if self.ok(q) else {"error": "token"})
        if u.path == "/api/menu": return self.send(200 if self.ok(q) else 403, menu_tree() if self.ok(q) else {"error": "token"})
        if u.path == "/font":
            if not self.ok(q): return self.send(403, {"error": "token"})
            f = font_file()
            if not f: return self.send(404, {"error": "no font"})
            return self.send(200, open(f, "rb").read(), "font/ttf")
        if u.path == "/stream":
            if not self.ok(q): return self.send(403, {"error": "token"})
            addr = q.get("addr", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    jpg = grab(addr)
                    if jpg:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(jpg))
                        self.wfile.write(jpg); self.wfile.write(b"\r\n")
                    time.sleep(0.07)
            except (BrokenPipeError, ConnectionResetError):
                return
            return
        self.send(404, {"error": "nope"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if not self.ok(q): return self.send(403, {"error": "token"})
        g = lambda k, d="": q.get(k, [d])[0]
        if u.path == "/api/focus":
            focus_ws(g("n")); return self.send(200, {"ok": True})
        if u.path == "/api/enter":
            try: phone_enter(g("addr"), float(g("pw", "360")), float(g("ph", "740")))
            except Exception: pass
            return self.send(200, {"ok": True})
        if u.path == "/api/leave":
            if g("addr"): phone_leave(g("addr"))
            return self.send(200, {"ok": True})
        if u.path == "/api/click":
            try: click(float(g("x", "0")), float(g("y", "0")), g("addr") or None)
            except Exception: pass
            return self.send(200, {"ok": True})
        if u.path == "/api/rclick":
            try: click(float(g("x", "0")), float(g("y", "0")), g("addr") or None, "0xC1")
            except Exception: pass
            return self.send(200, {"ok": True})
        if u.path == "/api/scroll":
            try: scroll(float(g("dy", "0")))
            except Exception: pass
            return self.send(200, {"ok": True})
        if u.path == "/api/type":
            if g("s"): type_text(g("s"))
            return self.send(200, {"ok": True})
        if u.path == "/api/key":
            if g("k"): key(g("k"), g("mods"))
            return self.send(200, {"ok": True})
        if u.path == "/api/win":
            if g("addr") and g("do"): win_action(g("addr"), g("do"))
            return self.send(200, {"ok": True})
        if u.path == "/api/movewin":
            if g("addr") and g("ws"): move_win(g("addr"), g("ws"))
            return self.send(200, {"ok": True})
        if u.path == "/api/settheme":
            if g("name"): sh("omarchy", "theme", "set", g("name"))
            return self.send(200, {"ok": True})
        if u.path == "/api/bgnext":
            sh("omarchy", "theme", "bg", "next"); return self.send(200, {"ok": True})
        if u.path == "/api/apply":
            if g("name"): sh("omaspaces", "apply", g("name"))
            return self.send(200, {"ok": True})
        if u.path == "/api/savelayout":
            if g("name"): sh("omaspaces", "save", g("name"))
            return self.send(200, {"ok": True})
        if u.path == "/api/toggle":
            if g("name"): sh("omarchy", "toggle", g("name"))
            return self.send(200, {"ok": True})
        if u.path == "/api/menurun":
            if g("id"): menu_run(g("id"))
            return self.send(200, {"ok": True})
        if u.path == "/api/buildlayout":
            if g("name") and g("tiles"): build_layout(g("name"), g("tiles"), g("apply") == "1")
            return self.send(200, {"ok": True})
        if u.path == "/api/rmlayout":
            if g("name"): sh("omaspaces", "rm", g("name"))
            return self.send(200, {"ok": True})
        self.send(404, {"error": "nope"})

def main():
    if "--version" in sys.argv:
        print("omabeam " + VERSION); return
    check_deps()
    url = "http://%s:%d/?t=%s" % (lan_ip(), PORT, TOKEN)
    fd = os.open(URLFILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(url + "\n" + TOKEN + "\n")
    print("omabeam %s [dispatch: %s] — scan on your phone (same Wi-Fi, stays on your network):\n  %s\n" % (VERSION, DISPATCH_MODE, url), flush=True)
    if shutil.which("qrencode"):
        subprocess.run(["qrencode", "-t", "ANSIUTF8", "-m", "2", url])
    print("\nAway from home? 'omabeam tunnel' opens a public link. 'omabeam rotate' revokes it.", flush=True)
    srv = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), H)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()

if __name__ == "__main__":
    main()
