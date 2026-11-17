"""ينشر خبر أسعار المحروقات على مدونة بلوغر عند صدور جدول جديد (مرة واحدة لكل جدول)."""
import html, json, os, sys, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuel import ar_date  # noqa: E402

BLOG_ID = "87520547399987288"
LABELS = ["محروقات"]
USD_RATE = 89700  # سعر الدولار بالليرة المعتمد
# draft = مسودة تراجعها وتنشرها بنفسك، publish = نشر مباشر
MODE = os.environ.get("BLOGGER_MODE", "draft")
STATE_FILE = "posted.json"


def access_token():
    data = urllib.parse.urlencode({
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    res = urllib.request.urlopen("https://oauth2.googleapis.com/token", data=data, timeout=30)
    return json.loads(res.read())["access_token"]


def build_post(fuel, news):
    lines = news.strip().split("\n")
    title = lines[0].replace("⛽", "").strip()
    rows = "".join(
        f"<tr><td>{html.escape(i['name'])}</td><td dir='ltr'>{i['price']:,}</td>"
        f"<td dir='ltr'>${i['price'] / USD_RATE:.2f}</td>"
        f"<td dir='ltr' style='color:{'#b03a2e' if i['change'] > 0 else '#1e8449' if i['change'] < 0 else '#5b6b72'}'>"
        f"{'+' if i['change'] > 0 else ''}{i['change']:,}</td></tr>"
        for i in fuel["items"])
    body = (
        "<div dir='rtl'>"
        "<p>صدر عن وزارة الطاقة والمياه جدول جديد لأسعار المحروقات، وجاءت الأسعار على الشكل التالي:</p>"
        "<table border='1' cellpadding='8' style='border-collapse:collapse;width:100%;text-align:center'>"
        "<tr style='background:#fbefe6'><th>المادة</th><th>السعر (ل.ل.)</th><th>بالدولار</th><th>الفرق (ل.ل.)</th></tr>"
        f"{rows}</table>"
        "<p>الأسعار بالليرة اللبنانية لصفيحة 20 ليتر، وقارورة الغاز 10 كلغ.</p>"
        f"<p>السعر بالدولار محسوب على أساس {USD_RATE:,} ليرة للدولار.</p>"
        + (f"<p>الفرق مقارنة بجدول {ar_date(fuel['items'][0]['prev_date'])}.</p>" if fuel["items"][0].get("prev_date") else "") +
        "<p><small>المصدر: وزارة الطاقة والمياه</small></p>"
        "</div>")
    return title, body


def main():
    if not all(os.environ.get(k) for k in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET", "BLOGGER_REFRESH_TOKEN")):
        print("أسرار بلوغر غير موجودة، تخطّي النشر")
        return
    fuel = json.load(open("fuel.json", encoding="utf-8"))
    state = json.load(open(STATE_FILE, encoding="utf-8")) if os.path.exists(STATE_FILE) else {}
    if state.get("fuel_date") == fuel["date"]:
        print("سبق نشر خبر هذا الجدول:", fuel["date"])
        return

    title, content = build_post(fuel, open("fuel-news.txt", encoding="utf-8").read())
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    if MODE != "publish":
        url += "?isDraft=true"
    req = urllib.request.Request(url, method="POST",
                                 data=json.dumps({"kind": "blogger#post", "title": title,
                                                  "content": content, "labels": LABELS}).encode(),
                                 headers={"Authorization": "Bearer " + access_token(),
                                          "Content-Type": "application/json; charset=utf-8"})
    try:
        post = json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        sys.exit(f"فشل النشر على بلوغر: {e.code} {e.read().decode()[:500]}")

    state = {"fuel_date": fuel["date"], "post_id": post.get("id"), "status": post.get("status"),
             "url": post.get("url")}
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("تم إنشاء التدوينة:", post.get("status"), post.get("url") or post.get("id"))


if __name__ == "__main__":
    main()
