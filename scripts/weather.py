"""نشرة طقس يومية لبعلبك والهرمل تُنشر على بلوغر بوسم «طقس» (مرة واحدة في اليوم)."""
import html, json, os, sys, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from blogger import BLOG_ID, access_token  # noqa: E402

LABELS = ["طقس"]
POST_HOUR = 7                     # ساعة النشر بتوقيت بيروت
WEATHER_PAGE_URL = os.environ.get("WEATHER_PAGE_URL", "")  # رابط صفحة الطقس المباشر (اختياري)
STATE_FILE = "weather-posted.json"
TZ = ZoneInfo("Asia/Beirut")

TOWNS = [
    ("بعلبك", 34.006, 36.218), ("الهرمل", 34.394, 36.385), ("دير الأحمر", 34.125, 36.130),
    ("شمسطار", 33.963, 36.060), ("بريتال", 33.945, 36.247), ("اللبوة", 34.196, 36.350),
    ("عرسال", 34.179, 36.420), ("الفاكهة", 34.233, 36.404), ("القاع", 34.343, 36.476),
]

WMO = {
    0: ("صحو", "☀️"), 1: ("صحو غالباً", "🌤️"), 2: ("غائم جزئياً", "⛅"), 3: ("غائم", "☁️"),
    45: ("ضباب", "🌫️"), 48: ("ضباب مع صقيع", "🌫️"),
    51: ("رذاذ خفيف", "🌦️"), 53: ("رذاذ", "🌦️"), 55: ("رذاذ كثيف", "🌧️"),
    56: ("رذاذ متجمّد", "🌧️"), 57: ("رذاذ متجمّد كثيف", "🌧️"),
    61: ("أمطار خفيفة", "🌦️"), 63: ("أمطار", "🌧️"), 65: ("أمطار غزيرة", "🌧️"),
    66: ("أمطار متجمّدة", "🌧️"), 67: ("أمطار متجمّدة غزيرة", "🌧️"),
    71: ("ثلوج خفيفة", "🌨️"), 73: ("ثلوج", "❄️"), 75: ("ثلوج كثيفة", "❄️"), 77: ("حبيبات ثلج", "🌨️"),
    80: ("زخات مطر خفيفة", "🌦️"), 81: ("زخات مطر", "🌧️"), 82: ("زخات مطر غزيرة", "⛈️"),
    85: ("زخات ثلج", "🌨️"), 86: ("زخات ثلج كثيفة", "❄️"),
    95: ("عواصف رعدية", "⛈️"), 96: ("عواصف رعدية مع برَد", "⛈️"), 99: ("عواصف رعدية مع برَد كثيف", "⛈️"),
}
AR_MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب",
             "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
AR_DAYS = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]


def w(code):
    return WMO.get(code, ("—", "🌡️"))


def ar_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{AR_DAYS[d.weekday()]} {d.day} {AR_MONTHS[d.month - 1]}"


def day_name(iso, i):
    return "اليوم" if i == 0 else "غداً" if i == 1 else AR_DAYS[datetime.strptime(iso, "%Y-%m-%d").weekday()]


def fetch():
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(t[1]) for t in TOWNS),
        "longitude": ",".join(str(t[2]) for t in TOWNS),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,snowfall_sum,wind_gusts_10m_max,sunrise,sunset",
        "timezone": "Asia/Beirut", "forecast_days": 3,
    })
    data = json.loads(urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + q, timeout=60).read())
    return data if isinstance(data, list) else [data]


def alerts(locs):
    groups = {}

    def add(key, label, town, day):
        g = groups.setdefault(key, {"label": label, "towns": [], "days": []})
        if town not in g["towns"]:
            g["towns"].append(town)
        if day not in g["days"]:
            g["days"].append(day)

    for (town, *_), loc in zip(TOWNS, locs):
        d = loc["daily"]
        for i in range(2):
            day, c = day_name(d["time"][i], i), d["weather_code"][i]
            if (d["snowfall_sum"][i] or 0) > 0 or c in (71, 73, 75, 77, 85, 86):
                add("snow", "❄️ تساقط ثلوج", town, day)
            if d["temperature_2m_min"][i] <= 0:
                add("frost", "🥶 صقيع وجليد — الحذر على الطرقات وحماية المزروعات", town, day)
            if (d["precipitation_sum"][i] or 0) >= 15:
                add("rain", "🌧️ أمطار غزيرة — احتمال تجمّع مياه وسيول", town, day)
            if (d["wind_gusts_10m_max"][i] or 0) >= 60:
                add("wind", "💨 رياح قوية (هبّات تفوق 60 كم/س)", town, day)
            if c >= 95:
                add("storm", "⛈️ عواصف رعدية", town, day)
            if d["temperature_2m_max"][i] >= 35:
                add("heat", "🔥 موجة حرّ — تجنّبوا الشمس وقت الظهيرة", town, day)
            if c in (45, 48):
                add("fog", "🌫️ ضباب — انتبهوا لانخفاض الرؤية أثناء القيادة", town, day)
    return list(groups.values())


def build(locs):
    b, h = locs[0]["daily"], locs[1]["daily"]
    today = b["time"][0]
    bt, bi = w(b["weather_code"][0])
    r = round
    title = (f"{bi} طقس بعلبك والهرمل اليوم {ar_date(today)}: {bt}، "
             f"والحرارة بين {r(b['temperature_2m_min'][0])} و{r(b['temperature_2m_max'][0])} درجة")

    p = []
    p.append(f"<p>الطقس اليوم في <b>بعلبك</b> {bt}، والحرارة بين {r(b['temperature_2m_min'][0])} "
             f"و{r(b['temperature_2m_max'][0])} درجة مئوية. وفي <b>الهرمل</b> {w(h['weather_code'][0])[0]}، "
             f"والحرارة بين {r(h['temperature_2m_min'][0])} و{r(h['temperature_2m_max'][0])} درجة.</p>")
    if (b["precipitation_probability_max"][0] or 0) >= 40:
        p.append(f"<p>احتمال هطول الأمطار في بعلبك اليوم {b['precipitation_probability_max'][0]}%.</p>")
    p.append(f"<p>شروق الشمس {b['sunrise'][0][11:16]} وغروبها {b['sunset'][0][11:16]}.</p>")

    if WEATHER_PAGE_URL:
        p.append(f"<p>👈 <a href='{html.escape(WEATHER_PAGE_URL)}'><b>تابعوا الطقس لحظة بلحظة</b></a></p>")
    al = alerts(locs)
    if al:
        p.append("<h3>⚠️ تنبيهات</h3><ul>" + "".join(
            f"<li><b>{html.escape(a['label'])}</b> — {'، '.join(a['days'])}: {'، '.join(a['towns'])}</li>"
            for a in al) + "</ul>")

    rows = []
    for (town, *_), loc in zip(TOWNS, locs):
        d = loc["daily"]
        t, ic = w(d["weather_code"][0])
        rows.append(f"<tr><td><b>{town}</b></td><td>{ic} {t}</td>"
                    f"<td dir='ltr'>{r(d['temperature_2m_min'][0])}° / {r(d['temperature_2m_max'][0])}°</td>"
                    f"<td dir='ltr'>{d['precipitation_probability_max'][0] or 0}%</td></tr>")
    p.append("<h3>🌡️ الطقس اليوم في البلدات</h3>"
             "<table border='1' cellpadding='7' style='border-collapse:collapse;width:100%;text-align:center'>"
             "<tr style='background:#e8f3f8'><th>البلدة</th><th>الحالة</th><th>الصغرى / العظمى</th><th>احتمال المطر</th></tr>"
             + "".join(rows) + "</table>")

    tt, ti = w(b["weather_code"][1])
    diff = b["temperature_2m_max"][1] - b["temperature_2m_max"][0]
    trend = "، مع انخفاض ملحوظ في الحرارة" if diff <= -3 else "، مع ارتفاع ملحوظ في الحرارة" if diff >= 3 else ""
    p.append(f"<h3>📅 غداً</h3><p>{ti} في بعلبك {tt}، والحرارة بين {r(b['temperature_2m_min'][1])} "
             f"و{r(b['temperature_2m_max'][1])} درجة{trend}.</p>")

    if WEATHER_PAGE_URL:
        p.append(f"<p style='text-align:center;margin:22px 0'><a href='{html.escape(WEATHER_PAGE_URL)}' "
                 "style='display:inline-block;background:#1e6091;color:#fff;text-decoration:none;"
                 "padding:12px 26px;border-radius:30px;font-weight:bold;font-size:1.05em'>"
                 "🌦️ الطقس المباشر وتوقعات الأسبوع ←</a></p>")
    p.append("<p><small>مصدر البيانات: Open-Meteo</small></p>")
    return today, title, "<div dir='rtl'>" + "".join(p) + "</div>"


def main():
    mode = os.environ.get("BLOGGER_MODE", "publish")
    force = os.environ.get("FORCE") == "1"
    now = datetime.now(TZ)
    if not force and now.hour < POST_HOUR:
        print("لم تحن الساعة بعد:", now.strftime("%H:%M"))
        return
    state = json.load(open(STATE_FILE, encoding="utf-8")) if os.path.exists(STATE_FILE) else {}
    if mode == "publish" and state.get("date") == now.strftime("%Y-%m-%d"):
        print("نُشرت نشرة اليوم سابقاً")
        return

    today, title, content = build(fetch())
    if os.environ.get("DRY_RUN") == "1":
        print(title)
        print(content)
        return

    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/"
    if mode != "publish":
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
    print("تم:", post.get("status"), post.get("url") or post.get("id"))
    if mode == "publish":   # المسودات التجريبية لا تمنع نشر نشرة اليوم
        json.dump({"date": today, "post_id": post.get("id"), "url": post.get("url")},
                  open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
