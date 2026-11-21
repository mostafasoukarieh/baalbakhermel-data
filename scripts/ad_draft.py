"""ينشئ مسودة إعلان مبوّب في بلوغر (لا تُنشر إلا يدوياً). يستدعيه نموذج الإعلانات في Apps Script."""
import json, os, sys, urllib.error, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blogger import BLOG_ID, access_token  # noqa: E402

title = os.environ["AD_TITLE"].strip()
content = os.environ["AD_CONTENT"]
labels = [x.strip() for x in os.environ.get("AD_LABELS", "").split(",") if x.strip()]
if not title or not content:
    sys.exit("عنوان الإعلان أو محتواه فارغ")
req = urllib.request.Request(
    f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts/?isDraft=true", method="POST",
    data=json.dumps({"kind": "blogger#post", "title": title, "content": content, "labels": labels}).encode(),
    headers={"Authorization": "Bearer " + access_token(), "Content-Type": "application/json; charset=utf-8"})
try:
    post = json.loads(urllib.request.urlopen(req, timeout=60).read())
except urllib.error.HTTPError as e:
    sys.exit(f"فشل إنشاء المسودة: {e.code} {e.read().decode()[:500]}")
print(f"تم إنشاء مسودة الإعلان {os.environ.get('AD_ID', '')}: https://www.blogger.com/blog/post/edit/{BLOG_ID}/{post['id']}")
