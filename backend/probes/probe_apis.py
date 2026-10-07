"""Probe public job/gig APIs for creative freelance (photo/video) results."""
import json, re, sys, time
from pathlib import Path
import httpx, feedparser

OUT = Path(__file__).resolve().parents[2] / "data" / "probes"
OUT.mkdir(parents=True, exist_ok=True)
UA = "FindJobGig/0.1 (personal job aggregator; contact: local)"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
CREATIVE = re.compile(
    r"photo(graph(er|y))?|video(grapher|graphy)?|videografer|fotografer|editor|editing|retouch|"
    r"cinematograph|filmmak|motion graphic|premiere|after effects|davinci|lightroom|photoshop|"
    r"content creator|youtube|reels|tiktok|drone", re.I)
KEYWORDS = ["photographer", "videographer", "video editor", "photo editor"]

client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": UA})
results = []


def probe(name, fn):
    t = time.time()
    try:
        items = fn()
        status, err = "ok", None
    except Exception as e:  # noqa
        items, status, err = [], "error", f"{type(e).__name__}: {e}"[:200]
    ms = int((time.time() - t) * 1000)
    creative = [i for i in items if CREATIVE.search(i["title"] + " " + i.get("extra", ""))]
    (OUT / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf8")
    results.append({"source": name, "status": status, "ms": ms, "total": len(items),
                    "creative": len(creative), "sample": [c["title"][:90] for c in creative[:4]], "error": err})
    print(f"{name:28} {status:5} {ms:6}ms total={len(items):4} creative={len(creative):4} {err or ''}", flush=True)


def dedup(items):
    seen, out = set(), []
    for i in items:
        if i["url"] not in seen:
            seen.add(i["url"]); out.append(i)
    return out


def remotive():
    items = []
    for kw in KEYWORDS + ["video"]:
        d = client.get("https://remotive.com/api/remote-jobs", params={"search": kw}).json()
        items += [{"title": j["title"], "url": j["url"], "extra": j.get("category", "") + " " + j.get("job_type", "")} for j in d["jobs"]]
        time.sleep(1)
    return dedup(items)


def remoteok():
    d = client.get("https://remoteok.com/api").json()
    return [{"title": j.get("position", ""), "url": j.get("url", ""), "extra": " ".join(j.get("tags", []))} for j in d[1:]]


def arbeitnow():
    items = []
    for page in (1, 2, 3):
        d = client.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page}).json()
        items += [{"title": j["title"], "url": j["url"], "extra": " ".join(j.get("tags", []) + j.get("job_types", []))} for j in d["data"]]
    return items


def jobicy():
    items = []
    for tag in ["video", "photography", "photo", "editor"]:
        d = client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50, "tag": tag}).json()
        items += [{"title": j["jobTitle"], "url": j["url"], "extra": " ".join(j.get("jobType", []) if isinstance(j.get("jobType"), list) else [str(j.get("jobType"))])} for j in d.get("jobs", [])]
        time.sleep(1)
    return dedup(items)


def himalayas():
    items = []
    for kw in KEYWORDS:
        r = client.get("https://himalayas.app/jobs/api/search", params={"q": kw})
        r.raise_for_status()
        d = r.json()
        items += [{"title": j["title"], "url": j.get("applicationLink") or j.get("guid", ""), "extra": j.get("employmentType", "")} for j in d.get("jobs", [])]
        time.sleep(1)
    return dedup(items)


def wwr():
    f = feedparser.parse(client.get("https://weworkremotely.com/remote-jobs.rss").content)
    return [{"title": e.title, "url": e.link, "extra": e.get("category", "")} for e in f.entries]


def hn():
    items = []
    for kw in KEYWORDS + ["video editing freelance"]:
        d = client.get("https://hn.algolia.com/api/v1/search_by_date",
                       params={"query": kw, "tags": "comment", "numericFilters": "created_at_i>%d" % (time.time() - 90 * 86400)}).json()
        for h in d["hits"]:
            story = (h.get("story_title") or "")
            if "hiring" in story.lower() or "freelancer" in story.lower():
                text = re.sub("<[^>]+>", " ", h.get("comment_text") or "")
                items.append({"title": text[:120].strip(), "url": f"https://news.ycombinator.com/item?id={h['objectID']}", "extra": story})
    return dedup(items)


def reddit(sub, query=None, flair_paid=False):
    def fn():
        url = f"https://www.reddit.com/r/{sub}/search.json" if query else f"https://www.reddit.com/r/{sub}/new.json"
        params = {"q": query, "restrict_sr": 1, "sort": "new", "limit": 100, "t": "month"} if query else {"limit": 100}
        r = client.get(url, params=params)
        r.raise_for_status()
        posts = [c["data"] for c in r.json()["data"]["children"]]
        out = []
        for p in posts:
            title, flair = p["title"], (p.get("link_flair_text") or "")
            if sub in ("forhire", "hiring", "freelance_forhire", "slavelabour") and "hiring" not in (title + flair).lower() and "task" not in (title + flair).lower():
                continue
            if flair_paid and "paid" not in flair.lower():
                continue
            out.append({"title": f"[{flair}] {title}" if flair else title, "url": "https://reddit.com" + p["permalink"], "extra": p.get("selftext", "")[:300]})
        return out
    return fn


def reddit_rss(sub, query=None, hiring_only=True):
    # Anonymous .json is 403-blocked; .rss works but 429s after ~2 quick requests,
    # so each call waits 15s first. Production should use Reddit OAuth (see VALIDATION.md).
    def fn():
        time.sleep(15)
        url = f"https://www.reddit.com/r/{sub}/search.rss" if query else f"https://www.reddit.com/r/{sub}/new.rss"
        r = client.get(url, params={"q": query, "restrict_sr": 1, "sort": "new"} if query else {})
        r.raise_for_status()
        f = feedparser.parse(r.content)
        keep = lambda t: not hiring_only or "hiring" in t.lower() or "[task]" in t.lower()
        return [{"title": e.title, "url": e.link, "extra": ""} for e in f.entries if keep(e.title)]
    return fn


def freelancer():
    items = []
    for kw in KEYWORDS + ["video editing", "photo retouching"]:
        r = client.get("https://www.freelancer.com/api/projects/0.1/projects/active/",
                       params={"query": kw, "limit": 30, "full_description": "true", "job_details": "true"})
        r.raise_for_status()
        for p in r.json()["result"]["projects"]:
            b = p.get("budget") or {}
            cur = (p.get("currency") or {}).get("code", "")
            items.append({"title": p["title"], "url": f"https://www.freelancer.com/projects/{p['seo_url']}",
                          "extra": " ".join(j["name"] for j in p.get("jobs", [])),
                          "budget": f"{cur} {b.get('minimum')}-{b.get('maximum')} {p.get('type')}"})
        time.sleep(1)
    return dedup(items)


def jobstreet():
    items = []
    for kw in ["videografer", "fotografer", "video editor", "photographer"]:
        r = client.get("https://id.jobstreet.com/api/jobsearch/v5/search",
                       params={"siteKey": "ID-Main", "keywords": kw, "page": 1, "pageSize": 30, "locale": "en-ID"},
                       headers={"User-Agent": BROWSER_UA})
        r.raise_for_status()
        for j in r.json().get("data", []):
            items.append({"title": j.get("title", ""), "url": f"https://id.jobstreet.com/job/{j.get('id')}",
                          "extra": " ".join(w.get("label", "") if isinstance(w, dict) else str(w) for w in (j.get("workTypes") or [])),
                          "company": j.get("advertiser", {}).get("description"), "salary": j.get("salaryLabel")})
        time.sleep(1)
    return dedup(items)


def kalibrr():
    items = []
    for kw in ["video editor", "photographer", "videographer"]:
        r = client.get("https://www.kalibrr.com/kjs/job_board/search",
                       params={"limit": 30, "offset": 0, "text": kw}, headers={"User-Agent": BROWSER_UA})
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            items.append({"title": j.get("name", ""), "url": f"https://www.kalibrr.com/c/{(j.get('company') or {}).get('code','')}/jobs/{j.get('id')}",
                          "extra": str(j.get("tenure", ""))})
        time.sleep(1)
    return dedup(items)


def glints():
    q = {"operationName": "searchJobs", "variables": {"data": {"SearchTerm": "video editor", "CountryCode": "ID", "limit": 30, "offset": 0, "includeExternalJobs": True}},
         "query": "query searchJobs($data: JobSearchConditionInput!) { searchJobs(data: $data) { jobsInPage { id title type company { name } } } }"}
    r = client.post("https://glints.com/api/v2/graphql?op=searchJobs", json=q, headers={"User-Agent": BROWSER_UA})
    r.raise_for_status()
    jobs = r.json()["data"]["searchJobs"]["jobsInPage"]
    return [{"title": j["title"], "url": f"https://glints.com/id/opportunities/jobs/{j['id']}", "extra": j.get("type", "")} for j in jobs]


def projects_co_id():
    r = client.get("https://projects.co.id/public/browse_projects/listing", params={"search": "video"}, headers={"User-Agent": BROWSER_UA})
    r.raise_for_status()
    from selectolax.parser import HTMLParser
    doc = HTMLParser(r.text)
    out = []
    for a in doc.css("h2 a, .project-title a, a[href*='/public/projects/']"):
        t = a.text(strip=True)
        if t:
            out.append({"title": t, "url": a.attributes.get("href", ""), "extra": ""})
    return dedup(out)


probe("remotive", remotive)
probe("remoteok", remoteok)
probe("arbeitnow", arbeitnow)
probe("jobicy", jobicy)
probe("himalayas", himalayas)
probe("weworkremotely_rss", wwr)
probe("hn_algolia", hn)
probe("reddit_forhire_rss", reddit_rss("forhire", "photographer OR videographer OR \"video editor\" OR \"photo editor\""))
probe("reddit_slavelabour_rss", reddit_rss("slavelabour", "video OR photo OR edit"))
probe("reddit_PhotoshopRequest_rss", reddit_rss("PhotoshopRequest", hiring_only=False))
probe("freelancer_com", freelancer)
probe("jobstreet_id", jobstreet)
probe("kalibrr", kalibrr)
probe("glints", glints)
probe("projects_co_id", projects_co_id)

(OUT / "_summary_apis.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf8")
