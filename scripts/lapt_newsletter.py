"""نشرة الفيزياء الأسبوعية لموقع تجمع أساتذة الفيزياء في لبنان (apt-lb.net).

كل عدد جديد يُرفع إلى lapt/issues/NN/ (ملفان: post.html و meta.json).
هذا السكربت:
  build   يصمّم صورة الغلاف cover.png لكل عدد لم يُنشر بعد
  publish ينشر كل عدد لم يُنشر بعد على بلوغر (مرة واحدة لكل عدد)
  check   يتأكد من الوصول إلى مدونة التجمع ويعرض آخر أعداد النشرة المنشورة
"""
import html, json, os, re, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blogger import access_token  # noqa: E402

BLOG_URL = "https://www.apt-lb.net/"
REPO = "mostafasoukarieh/baalbakhermel-data"
ROOT = "lapt"
ISSUES = os.path.join(ROOT, "issues")
STATE_FILE = os.path.join(ROOT, "state.json")
ASSETS = os.path.join(ROOT, "assets")
SERIES = "نشرة الفيزياء الأسبوعية"
DEFAULT_LABELS = [SERIES]


def load_state():
    return json.load(open(STATE_FILE, encoding="utf-8"))


def save_state(state):
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(STATE_FILE, "a", encoding="utf-8").write("\n")


def pending(state):
    """الأعداد الموجودة في المستودع ولم تُنشر بعد، مرتّبة."""
    out = []
    if not os.path.isdir(ISSUES):
        return out
    for name in sorted(os.listdir(ISSUES)):
        d = os.path.join(ISSUES, name)
        if not (os.path.isfile(os.path.join(d, "post.html")) and os.path.isfile(os.path.join(d, "meta.json"))):
            continue
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        if str(meta["issue"]) in state["published"]:
            continue
        out.append((d, meta))
    return out


def validate(d, meta):
    post = open(os.path.join(d, "post.html"), encoding="utf-8").read()
    problems = []
    for k in ("issue", "dates", "title", "cover_items"):
        if not meta.get(k):
            problems.append(f"meta.json ينقصه {k}")
    if len(meta.get("cover_items", [])) != 3:
        problems.append("cover_items يجب أن تكون 3 عناوين قصيرة")
    if post.count("COVER_URL") != 2:
        problems.append("post.html يجب أن يحتوي COVER_URL مرتين (الرابط والصورة)")
    if "أفكار محتوى" in post:
        problems.append("قسم «أفكار محتوى لـLAPT» لا يُنشر على الموقع")
    if "<style" in post:
        problems.append("لا تضع <style> في post.html؛ التنسيق يُضاف تلقائياً من lapt/assets/post-style.html")
    if problems:
        sys.exit(f"العدد {meta.get('issue')}: " + "؛ ".join(problems))
    return post


def api(method, path, token, body=None, query=None):
    url = "https://www.googleapis.com/blogger/v3/" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": "application/json; charset=utf-8"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Blogger API {method} {path}: {e.code} {e.read().decode()[:600]}")


def blog_id(token):
    return api("GET", "blogs/byurl", token, query={"url": BLOG_URL})["id"]


def series_labels(token, bid):
    """يأخذ وسوم آخر عدد منشور من النشرة ليبقى التصنيف كما هو على الموقع."""
    res = api("GET", f"blogs/{bid}/posts/search", token, query={"q": SERIES, "fetchBodies": "false"})
    for p in res.get("items", []):
        if SERIES in p.get("title", "") and p.get("labels"):
            return p["labels"]
    return DEFAULT_LABELS


def cmd_check():
    token = access_token()
    bid = blog_id(token)
    print("معرّف مدونة التجمع:", bid)
    res = api("GET", f"blogs/{bid}/posts/search", token, query={"q": SERIES, "fetchBodies": "false"})
    for p in res.get("items", [])[:8]:
        print("-", p.get("published", "")[:10], "|", p.get("title"), "|", p.get("labels"), "|", p.get("url"))
    print("الوسوم التي ستُستعمل:", series_labels(token, bid))


def cmd_build():
    from playwright.sync_api import sync_playwright
    state = load_state()
    todo = pending(state)
    if not todo:
        print("لا أعداد جديدة")
        return
    tpl = open(os.path.join(ASSETS, "cover-template.html"), encoding="utf-8").read()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        for d, meta in todo:
            validate(d, meta)
            page = (tpl.replace("{{ISSUE}}", str(meta["issue"]))
                       .replace("{{DATES}}", html.escape(meta["dates"]))
                       .replace("{{ITEMS}}", "".join(f"<li>{html.escape(x)}</li>" for x in meta["cover_items"])))
            tmp = os.path.join(ASSETS, "_cover.html")
            open(tmp, "w", encoding="utf-8").write(page)
            pg.goto("file://" + os.path.abspath(tmp))
            pg.wait_for_timeout(1000)
            pg.screenshot(path=os.path.join(d, "cover.png"))
            os.remove(tmp)
            print("الغلاف جاهز:", d)
        b.close()


def cmd_publish():
    state = load_state()
    todo = pending(state)
    if not todo:
        print("لا أعداد جديدة")
        return
    sha = os.environ.get("COMMIT_SHA", "main")
    forced = os.environ.get("LAPT_MODE", "auto")
    style = open(os.path.join(ASSETS, "post-style.html"), encoding="utf-8").read()
    token = access_token()
    bid = blog_id(token)
    labels = series_labels(token, bid)
    for d, meta in todo:
        post = validate(d, meta)
        if not os.path.isfile(os.path.join(d, "cover.png")):
            sys.exit(f"لا يوجد غلاف للعدد {meta['issue']}؛ شغّل build أولاً")
        cover = f"https://raw.githubusercontent.com/{REPO}/{sha}/{d}/cover.png".replace("\\", "/")
        content = post.replace("COVER_URL", cover).rstrip() + "\n\n" + style
        # أول عدد آلي يُحفظ مسودة للمراجعة، وبعده نشر مباشر
        mode = forced if forced in ("draft", "publish") else ("draft" if not state.get("auto_started") else "publish")
        query = {"isDraft": "true"} if mode == "draft" else None
        p = api("POST", f"blogs/{bid}/posts/", token, query=query,
                body={"kind": "blogger#post", "title": meta["title"], "content": content, "labels": labels})
        state["published"][str(meta["issue"])] = {"post_id": p.get("id"), "status": p.get("status"),
                                                  "url": p.get("url"), "cover": cover}
        state["last_issue"] = max(int(state.get("last_issue", 0)), int(meta["issue"]))
        state["auto_started"] = True
        save_state(state)
        print(f"العدد {meta['issue']}: {p.get('status')} {p.get('url') or p.get('id')}")


if __name__ == "__main__":
    {"check": cmd_check, "build": cmd_build, "publish": cmd_publish}[sys.argv[1] if len(sys.argv) > 1 else "check"]()
