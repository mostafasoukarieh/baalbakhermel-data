"""ينشر تدوينات معدّة يدوياً على أي مدونة من مدوّنات الحساب (دليل بعلبك والهرمل، Green Goal، LAPT...).

كل تدوينة مجلد في announcements/<الاسم>/ فيه:
  meta.json  {"blog_url": "https://www.baalbakhermel.com/", "title": "...", "labels": ["أخبار"], "draft": false}
  post.html  محتوى التدوينة
تُنشر مرة واحدة فقط، وتُسجَّل في announcements/state.json. التشغيل: workflow «تدوينات معدّة (announcements)» عند الرفع.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blogger_api import api, blog_id, token  # noqa: E402

ROOT = "announcements"
STATE = os.path.join(ROOT, "state.json")


def main():
    state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {}
    todo = [n for n in sorted(os.listdir(ROOT))
            if os.path.isfile(os.path.join(ROOT, n, "meta.json")) and n not in state]
    if not todo:
        print("لا جديد")
        return
    t = token()
    ids = {}
    for name in todo:
        meta = json.load(open(os.path.join(ROOT, name, "meta.json"), encoding="utf-8"))
        content = open(os.path.join(ROOT, name, "post.html"), encoding="utf-8").read()
        for k in ("blog_url", "title"):
            if not meta.get(k):
                sys.exit(f"{name}: meta.json ينقصه {k}")
        bid = ids.get(meta["blog_url"]) or blog_id(t, meta["blog_url"])
        ids[meta["blog_url"]] = bid
        p = api("POST", f"blogs/{bid}/posts/", t, query={"isDraft": "true"} if meta.get("draft") else None,
                body={"kind": "blogger#post", "title": meta["title"], "content": content, "labels": meta.get("labels", [])})
        state[name] = {"blog": meta["blog_url"], "post_id": p.get("id"), "status": p.get("status"), "url": p.get("url")}
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"{name}: {p.get('status')} {p.get('url')}")


if __name__ == "__main__":
    main()
