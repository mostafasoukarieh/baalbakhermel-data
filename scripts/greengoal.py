"""الأخبار الرياضية ومباريات اليوم لموقع Green Goal Arena (www.greengoal.net).

المهمة اليومية في Claude ترفع إلى المستودع:
  greengoal/posts/<YYYY-MM-DD-NN>/meta.json + post.html   خبر رياضي (بعلبك-الهرمل / محلية / دولية)
  greengoal/matches/<YYYY-MM-DD>.json                     مباريات اليوم ونتائجها (تُحدَّث خلال اليوم)

هذا السكربت:
  validate  يفحص الملفات (يُشغَّل محلياً قبل الرفع، ويُشغَّل في GitHub قبل النشر)
  build     يصمّم صور الأغلفة cover.png للأخبار الجديدة ولمباريات اليوم
  publish   ينشر الأخبار الجديدة (مرة واحدة لكل خبر)، وينشئ تدوينة مباريات اليوم أو يحدّثها
  preview   يكتب greengoal/_preview/*.html لمعاينة التدوينات محلياً
  check     يتأكد من الوصول إلى مدونة Green Goal ويعرض آخر التدوينات ووسومها
"""
import hashlib, html, json, os, re, sys, urllib.parse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BLOG_URL = "https://www.greengoal.net/"
SHARE_URL = "https://www.greengoal.net/#news"
REPO = "mostafasoukarieh/baalbakhermel-data"
ROOT = "greengoal"
POSTS = os.path.join(ROOT, "posts")
MATCHES = os.path.join(ROOT, "matches")
ASSETS = os.path.join(ROOT, "assets")
STATE_FILE = os.path.join(ROOT, "state.json")
TODAY_FILE = os.path.join(ROOT, "today.json")
LEAGUE_FILE = os.path.join(ROOT, "league.json")
LEAGUE_PAGE_HTML = os.path.join("site", "greengoal-league-page.html")
LEAGUE_PAGE_TITLE = "دوري فانتازيا اللبناني: الترتيب والنتائج"
LEAGUE_PAGE_SLUG = "lebanese-league"
WHATSAPP = "96176705190"

SCOPES = ["بعلبك-الهرمل", "محلية", "دولية"]
MATCH_LABEL = "مباريات اليوم"
STATUS = {"upcoming": "لم تبدأ", "live": "جارية", "finished": "انتهت",
          "postponed": "تأجّلت", "cancelled": "أُلغيت", "unknown": "النتيجة غير مؤكدة"}
AR_MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب",
             "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
AR_DAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
FORBIDDEN = ["مصطفى", "لم أجد", "لم أستطع", "ملاحظة للمحرر", "TODO"]


def ar_date(iso, year=True):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month - 1]}" + (f" {d.year}" if year else "")


def e(s):
    return html.escape(str(s if s is not None else ""))


def load_json(path):
    return json.load(open(path, encoding="utf-8"))


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_state():
    return load_json(STATE_FILE)


# ---------------------------------------------------------------- الأخبار

def news_items():
    out = []
    if not os.path.isdir(POSTS):
        return out
    for name in sorted(os.listdir(POSTS)):
        d = os.path.join(POSTS, name)
        if os.path.isfile(os.path.join(d, "meta.json")) and os.path.isfile(os.path.join(d, "post.html")):
            out.append((d, name, load_json(os.path.join(d, "meta.json"))))
    return out


def validate_news(d, name, meta):
    problems = []
    post = open(os.path.join(d, "post.html"), encoding="utf-8").read()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}", name):
        problems.append("اسم المجلد يجب أن يكون YYYY-MM-DD-NN")
    for k in ("title", "label", "kicker", "cover_title", "summary", "sources"):
        if not meta.get(k):
            problems.append(f"meta.json ينقصه {k}")
    if meta.get("label") not in SCOPES:
        problems.append(f"label يجب أن يكون واحداً من: {'، '.join(SCOPES)}")
    if len(meta.get("cover_title", "")) > 70:
        problems.append("cover_title طويل (حتى 70 حرفاً)")
    for s in meta.get("sources", []):
        if not (isinstance(s, dict) and s.get("name") and str(s.get("url", "")).startswith("http")):
            problems.append("كل مصدر في sources يجب أن يكون {name, url} برابط كامل")
    if "<style" in post or "<script" in post:
        problems.append("لا <style> ولا <script> في post.html")
    if "<h1" in post:
        problems.append("لا <h1> في post.html (العنوان يُضاف تلقائياً)")
    for w in FORBIDDEN:
        if w in post or w in meta.get("title", ""):
            problems.append(f"عبارة داخلية لا تُنشر: «{w}»")
    if len(re.sub(r"<[^>]+>", "", post).split()) < 60:
        problems.append("الخبر قصير جداً (أقل من 60 كلمة)")
    return problems, post


# ---------------------------------------------------------------- المباريات

def match_days():
    if not os.path.isdir(MATCHES):
        return []
    return sorted(f[:-5] for f in os.listdir(MATCHES) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f))


def validate_day(day):
    data = load_json(os.path.join(MATCHES, day + ".json"))
    problems = []
    if data.get("date") != day:
        problems.append("date داخل الملف لا يطابق اسم الملف")
    groups = data.get("groups", [])
    if not groups:
        problems.append("لا مجموعات مباريات (groups)")
    for g in groups:
        if g.get("scope") not in SCOPES:
            problems.append(f"scope غير صحيح: {g.get('scope')}")
        if not g.get("competition"):
            problems.append("مسابقة بلا اسم")
        for m in g.get("matches", []):
            if not (m.get("home") and m.get("away")):
                problems.append(f"مباراة بلا فريقين في {g.get('competition')}")
            st = m.get("status", "upcoming")
            if st not in STATUS:
                problems.append(f"status غير معروف: {st}")
            if st in ("finished", "live") and (m.get("home_score") is None or m.get("away_score") is None):
                problems.append(f"{m.get('home')} – {m.get('away')}: مباراة {STATUS[st]} بلا نتيجة")
            if m.get("time") and not re.fullmatch(r"\d{2}:\d{2}", m["time"]):
                problems.append(f"الوقت بصيغة HH:MM بتوقيت بيروت: {m.get('time')}")
    for s in data.get("sources", []):
        if not str(s.get("url", "")).startswith("http"):
            problems.append("مصدر بلا رابط")
    return problems, data


def all_matches(data):
    return [m for g in data["groups"] for m in g.get("matches", [])]


def day_phase(data):
    ms = all_matches(data)
    if data.get("final") or (ms and all(m.get("status") in ("finished", "postponed", "cancelled") for m in ms)):
        return "results"
    if any(m.get("status") in ("finished", "live") for m in ms):
        return "partial"
    return "fixtures"


def day_title(data):
    phase = day_phase(data)
    d = ar_date(data["date"])
    if phase == "results":
        return f"نتائج مباريات {d}"
    if phase == "partial":
        return f"مباريات اليوم {d}: النتائج أولاً بأول"
    return f"مباريات اليوم {d}"


def day_labels(data):
    scopes = [s for s in SCOPES if any(g["scope"] == s and g.get("matches") for g in data["groups"])]
    return [MATCH_LABEL] + scopes


def score_html(m):
    st = m.get("status", "upcoming")
    if st in ("finished", "live"):
        s = f"<b>{e(m['home_score'])}</b><i>-</i><b>{e(m['away_score'])}</b>"
        if m.get("penalties"):
            s += f"<small>ترجيح {e(m['penalties'])}</small>"
        return f"<span class='gg-score gg-{st}'>{s}</span>"
    if st in ("postponed", "cancelled", "unknown"):
        return f"<span class='gg-score gg-off'>{STATUS[st]}</span>"
    return f"<span class='gg-score gg-up'>{e(m.get('time') or '—')}</span>"


def day_cover_items(data):
    """أهم ثلاث مباريات للغلاف: الأولوية لبعلبك-الهرمل ثم المحلية ثم الدولية."""
    out = []
    for s in SCOPES:
        for g in data["groups"]:
            if g["scope"] != s:
                continue
            for m in g.get("matches", []):
                st = m.get("status")
                if st in ("finished", "live"):
                    out.append(f"{m['home']} {m['home_score']} – {m['away_score']} {m['away']}")
                elif st in ("postponed", "cancelled"):
                    out.append(f"{m['home']} – {m['away']} ({STATUS[st]})")
                else:
                    out.append(f"{m['home']} – {m['away']}" + (f" ({m['time']})" if m.get("time") else ""))
    return out[:3]


def day_body(data):
    phase = day_phase(data)
    intro = {
        "fixtures": "أبرز مباريات كرة القدم اليوم في بعلبك-الهرمل ولبنان والعالم، والمواعيد بتوقيت بيروت. نحدّث هذه الصفحة بالنتائج خلال اليوم.",
        "partial": "مباريات اليوم مع النتائج التي انتهت حتى الآن، والمواعيد بتوقيت بيروت. نكمل التحديث حتى نهاية آخر مباراة.",
        "results": "النتائج النهائية لأبرز مباريات كرة القدم في بعلبك-الهرمل ولبنان والعالم.",
    }[phase]
    parts = [f"<p class='gg-lede'>{intro}</p>"]
    if data.get("headline"):
        parts.append(f"<div class='gg-pull'>{e(data['headline'])}</div>")
    for s in SCOPES:
        groups = [g for g in data["groups"] if g["scope"] == s and g.get("matches")]
        if not groups:
            continue
        parts.append(f"<h2><span class='gg-dot'></span>{e(s if s != 'محلية' else 'لبنان')}</h2>")
        for g in groups:
            rows = []
            for m in g["matches"]:
                extra = " · ".join(x for x in (m.get("venue"), m.get("channel"), m.get("note")) if x)
                rows.append(
                    "<div class='gg-match'>"
                    f"<span class='gg-team gg-home'>{e(m['home'])}</span>{score_html(m)}"
                    f"<span class='gg-team gg-away'>{e(m['away'])}</span>"
                    + (f"<span class='gg-extra'>{e(extra)}</span>" if extra else "")
                    + "</div>")
            parts.append(f"<div class='gg-comp'><h3>{e(g['competition'])}</h3>{''.join(rows)}</div>")
    if data.get("sources"):
        parts.append("<p class='gg-src'>المصادر: " + "، ".join(
            f"<a href='{e(s['url'])}' rel='nofollow noopener' target='_blank'>{e(s['name'])}</a>"
            for s in data["sources"]) + "</p>")
    if data.get("updated"):
        parts.append(f"<p class='gg-src'>آخر تحديث: {e(data['updated'])} بتوقيت بيروت</p>")
    return "".join(parts)


# ---------------------------------------------------------------- الدوري اللبناني (صفحة ثابتة)

def validate_league():
    if not os.path.exists(LEAGUE_FILE):
        return []
    d = load_json(LEAGUE_FILE)
    problems = []
    rows = d.get("standings") or []
    if len(rows) < 6:
        problems.append("standings: جدول الترتيب ناقص")
    teams = set()
    for i, t in enumerate(rows):
        for k in ("team", "p", "w", "d", "l", "gf", "ga", "pts"):
            if k not in t:
                problems.append(f"standings[{i}] ينقصه {k}")
        if all(k in t for k in ("p", "w", "d", "l", "pts")):
            if t["w"] + t["d"] + t["l"] != t["p"]:
                problems.append(f"{t['team']}: فاز+تعادل+خسر لا يساوي لعب")
            if t["w"] * 3 + t["d"] != t["pts"] and not t.get("deducted"):
                problems.append(f"{t['team']}: النقاط لا تساوي 3×فاز+تعادل (إن كان هناك خصم نقاط ضع deducted)")
        teams.add(t.get("team"))
    pts = [t.get("pts", 0) for t in rows]
    if pts != sorted(pts, reverse=True):
        problems.append("standings غير مرتّب حسب النقاط")
    for part in ("previous", "current"):
        for m in (d.get(part) or {}).get("matches", []):
            for k in ("date", "home", "away", "status"):
                if not m.get(k):
                    problems.append(f"{part}: مباراة ينقصها {k}")
            if m.get("status") not in STATUS:
                problems.append(f"{part}: status غير معروف {m.get('status')}")
            if m.get("status") in ("finished", "live") and (m.get("home_score") is None or m.get("away_score") is None):
                problems.append(f"{part}: {m.get('home')} – {m.get('away')} بلا نتيجة")
            for side in ("home", "away"):
                if m.get(side) and m[side] not in teams:
                    problems.append(f"{part}: الفريق «{m[side]}» غير موجود في جدول الترتيب (وحّد الأسماء)")
    return problems


def cmd_page():
    """ينشئ صفحة بلوغر الثابتة للدوري اللبناني أو يحدّث محتواها (البيانات نفسها تُقرأ من league.json)."""
    from blogger_api import api, blog_id, token
    state = load_state()
    t = token()
    bid = blog_id(t, BLOG_URL)
    content = open(LEAGUE_PAGE_HTML, encoding="utf-8").read()
    info = state.get("league_page") or {}
    if info.get("page_id"):
        p = api("PATCH", f"blogs/{bid}/pages/{info['page_id']}", t,
                body={"title": LEAGUE_PAGE_TITLE, "content": content})
    else:
        # العنوان الإنجليزي أولاً ليصير الرابط /p/lebanese-league.html، ثم العنوان العربي
        p = api("POST", f"blogs/{bid}/pages", t, query={"isDraft": "false"},
                body={"kind": "blogger#page", "title": LEAGUE_PAGE_SLUG, "content": content})
        p = api("PATCH", f"blogs/{bid}/pages/{p['id']}", t, body={"title": LEAGUE_PAGE_TITLE})
    state["league_page"] = {"page_id": p.get("id"), "url": p.get("url"), "status": p.get("status")}
    save_json(STATE_FILE, state)
    print("صفحة الدوري:", p.get("status"), p.get("url"))


# ---------------------------------------------------------------- القالب المشترك للتدوينة

def wrap(title, kicker, body, cover_url=None):
    share = urllib.parse.quote(f"{title}\n{SHARE_URL}")
    cover = (f"<div class='gg-cover'><a href='{cover_url}'><img src='{cover_url}' alt='{e(title)}' /></a></div>"
             if cover_url else "")
    style = open(os.path.join(ASSETS, "post-style.html"), encoding="utf-8").read()
    return (
        f"<div class='gg-post' dir='rtl'>{cover}"
        f"<div class='gg-wrap'><span class='gg-kicker'>{e(kicker)}</span>"
        f"{body}"
        "<div class='gg-closing'>"
        f"<a class='gg-cta gg-wa' href='https://wa.me/?text={share}' target='_blank' rel='noopener'>شارك الخبر عبر واتساب</a>"
        f"<p>⚽ <b>Green Goal Arena</b> – ملعب ميني فوتبول في الفاكهة – الجديدة. "
        f"للحجز: <a href='https://wa.me/{WHATSAPP}' target='_blank' rel='noopener'>واتساب 76705190</a> · "
        f"<a href='{SHARE_URL}'>كل الأخبار</a></p>"
        "</div></div></div>\n" + style)


def news_body(meta, post):
    src = "، ".join(f"<a href='{e(s['url'])}' rel='nofollow noopener' target='_blank'>{e(s['name'])}</a>"
                    for s in meta["sources"])
    return f"<p class='gg-lede'>{e(meta['summary'])}</p>{post.strip()}<p class='gg-src'>المصدر: {src}</p>"


# ---------------------------------------------------------------- الأوامر

def cmd_validate(strict=True):
    bad = []
    for d, name, meta in news_items():
        p, _ = validate_news(d, name, meta)
        bad += [f"{name}: {x}" for x in p]
    for day in match_days():
        p, _ = validate_day(day)
        bad += [f"matches/{day}: {x}" for x in p]
    bad += [f"league.json: {x}" for x in validate_league()]
    if bad:
        print("\n".join(bad))
        if strict:
            sys.exit(1)
    else:
        print("كل الملفات سليمة")
    return not bad


def file_hash(path):
    return hashlib.sha1(open(path, "rb").read()).hexdigest()[:12]


def pending(state):
    news = [(d, n, m) for d, n, m in news_items() if n not in state["posts"]]
    days = [day for day in match_days()
            if state["matches"].get(day, {}).get("hash") != file_hash(os.path.join(MATCHES, day + ".json"))]
    return news, days


def render_cover(pg, out, kicker, title, items, date_text):
    tpl = open(os.path.join(ASSETS, "cover-template.html"), encoding="utf-8").read()
    page = (tpl.replace("{{KICKER}}", e(kicker)).replace("{{TITLE}}", e(title))
               .replace("{{DATE}}", e(date_text))
               .replace("{{ITEMS}}", "".join(f"<li>{e(x)}</li>" for x in items)))
    tmp = os.path.join(ASSETS, "_cover.html")
    open(tmp, "w", encoding="utf-8").write(page)
    pg.goto("file://" + os.path.abspath(tmp))
    pg.wait_for_timeout(800)
    pg.screenshot(path=out)
    os.remove(tmp)


def cmd_build():
    from playwright.sync_api import sync_playwright
    cmd_validate()
    state = load_state()
    news, days = pending(state)
    if not news and not days:
        print("لا جديد")
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 630})
        for d, name, meta in news:
            render_cover(pg, os.path.join(d, "cover.png"), meta["label"] + " · " + meta["kicker"],
                         meta["cover_title"], [], ar_date(name[:10]))
            print("غلاف:", name)
        for day in days:
            data = load_json(os.path.join(MATCHES, day + ".json"))
            kick = {"fixtures": "مباريات اليوم", "partial": "النتائج أولاً بأول", "results": "النتائج النهائية"}[day_phase(data)]
            render_cover(pg, os.path.join(MATCHES, day + ".png"), kick,
                         "مباريات " + ar_date(day, year=False), day_cover_items(data), "المواعيد بتوقيت بيروت")
            print("غلاف مباريات:", day)
        b.close()


def cmd_preview():
    os.makedirs(os.path.join(ROOT, "_preview"), exist_ok=True)
    for d, name, meta in news_items():
        _, post = validate_news(d, name, meta)
        cov = "../posts/" + name + "/cover.png" if os.path.exists(os.path.join(d, "cover.png")) else None
        open(os.path.join(ROOT, "_preview", name + ".html"), "w", encoding="utf-8").write(
            "<meta charset='utf-8'><body style='margin:0;background:#eee'><h1 dir=rtl style='font-family:sans-serif;padding:10px'>"
            + e(meta["title"]) + "</h1>" + wrap(meta["title"], meta["kicker"], news_body(meta, post), cov))
    for day in match_days():
        data = load_json(os.path.join(MATCHES, day + ".json"))
        cov = "../matches/" + day + ".png" if os.path.exists(os.path.join(MATCHES, day + ".png")) else None
        open(os.path.join(ROOT, "_preview", "matches-" + day + ".html"), "w", encoding="utf-8").write(
            "<meta charset='utf-8'><body style='margin:0;background:#eee'><h1 dir=rtl style='font-family:sans-serif;padding:10px'>"
            + e(day_title(data)) + "</h1>" + wrap(day_title(data), "مباريات اليوم", day_body(data), cov))
    print("المعاينة في", os.path.join(ROOT, "_preview"))


def cmd_check():
    from blogger_api import api, blog_id, token
    t = token()
    bid = blog_id(t, BLOG_URL)
    print("معرّف مدونة Green Goal:", bid)
    res = api("GET", f"blogs/{bid}/posts", t, query={"maxResults": 10, "fetchBodies": "false", "status": "live"})
    for p in res.get("items", []):
        print("-", p.get("published", "")[:10], "|", p.get("title"), "|", p.get("labels"), "|", p.get("url"))
    print("المسودات:")
    res = api("GET", f"blogs/{bid}/posts", t, query={"maxResults": 5, "fetchBodies": "false", "status": "draft", "view": "AUTHOR"})
    for p in res.get("items", []):
        print("-", p.get("updated", "")[:16], "|", p.get("title"), "|", p.get("labels"))


def cmd_publish():
    from blogger_api import api, blog_id, token
    cmd_validate()
    state = load_state()
    news, days = pending(state)
    if not news and not days:
        print("لا جديد")
        return
    sha = os.environ.get("COMMIT_SHA", "main")
    forced = os.environ.get("GG_MODE", "auto")
    # أول نشر آلي يُحفظ مسودات للمراجعة، وبعده نشر مباشر
    mode = forced if forced in ("draft", "publish") else ("publish" if state.get("auto_started") else "draft")
    t = token()
    bid = blog_id(t, BLOG_URL)
    raw = f"https://raw.githubusercontent.com/{REPO}/{sha}/"

    for d, name, meta in news:
        _, post = validate_news(d, name, meta)
        cov = raw + f"{d}/cover.png".replace("\\", "/") if os.path.exists(os.path.join(d, "cover.png")) else None
        content = wrap(meta["title"], meta["label"] + " · " + meta["kicker"], news_body(meta, post), cov)
        p = api("POST", f"blogs/{bid}/posts/", t, query={"isDraft": "true"} if mode == "draft" else None,
                body={"kind": "blogger#post", "title": meta["title"], "content": content, "labels": [meta["label"]]})
        state["posts"][name] = {"post_id": p.get("id"), "status": p.get("status"), "url": p.get("url"),
                                "title": meta["title"], "label": meta["label"]}
        save_json(STATE_FILE, state)
        print(f"خبر {name}: {p.get('status')} {p.get('url') or p.get('id')}")

    for day in days:
        path = os.path.join(MATCHES, day + ".json")
        data = load_json(path)
        cov = raw + f"{MATCHES}/{day}.png".replace("\\", "/") if os.path.exists(os.path.join(MATCHES, day + ".png")) else None
        title = day_title(data)
        content = wrap(title, MATCH_LABEL, day_body(data), cov)
        body = {"kind": "blogger#post", "title": title, "content": content, "labels": day_labels(data)}
        prev = state["matches"].get(day)
        if prev and prev.get("post_id"):
            p = api("PATCH", f"blogs/{bid}/posts/{prev['post_id']}", t, body=body)
            if prev.get("status") == "DRAFT" and mode == "publish":
                p = api("POST", f"blogs/{bid}/posts/{prev['post_id']}/publish", t)
            action = "تحديث"
        else:
            p = api("POST", f"blogs/{bid}/posts/", t, query={"isDraft": "true"} if mode == "draft" else None, body=body)
            action = "إنشاء"
        state["matches"][day] = {"post_id": p.get("id"), "status": p.get("status"), "url": p.get("url"),
                                 "hash": file_hash(path), "phase": day_phase(data), "title": title}
        save_json(STATE_FILE, state)
        print(f"مباريات {day} ({action}): {p.get('status')} {p.get('url') or p.get('id')}")

    # آخر يوم مباريات للودجت في الصفحة الرئيسية
    if match_days():
        last = match_days()[-1]
        data = load_json(os.path.join(MATCHES, last + ".json"))
        data["post_url"] = state["matches"].get(last, {}).get("url") or ""
        data["title"] = day_title(data)
        data["phase"] = day_phase(data)
        save_json(TODAY_FILE, data)
    state["auto_started"] = True
    save_json(STATE_FILE, state)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    {"validate": cmd_validate, "build": cmd_build, "publish": cmd_publish,
     "preview": cmd_preview, "check": cmd_check, "page": cmd_page}[cmd]()
