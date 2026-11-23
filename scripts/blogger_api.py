"""دوال مشتركة لواجهة Blogger API (بمفاتيح بلوغر نفسها المستعملة للدليل)."""
import json, sys, urllib.error, urllib.parse, urllib.request

from blogger import access_token


def token():
    return access_token()


def api(method, path, tok, body=None, query=None):
    url = "https://www.googleapis.com/blogger/v3/" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Content-Type": "application/json; charset=utf-8"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=60).read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Blogger API {method} {path}: {e.code} {e.read().decode()[:600]}")


def blog_id(tok, blog_url):
    return api("GET", "blogs/byurl", tok, query={"url": blog_url})["id"]
