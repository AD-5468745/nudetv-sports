#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
누드TV 스포츠 — 골/하이라이트 자동 수집기
- 종목별 공식 채널의 유튜브 RSS를 읽어 '골/하이라이트'만 추려 data.json 으로 저장.
- GitHub Actions가 30분마다 실행. 손볼 일 없음.
- 리그를 더 넣거나 거르는 단어를 고치려면 아래 LEAGUES 만 수정하면 됩니다.
"""
import urllib.request, re, json, html, sys

# ── 종목/리그 정의 ─────────────────────────────────────────
# key   : 화면 탭과 연결되는 코드
# label : 경기명을 못 뽑았을 때 카드에 표시할 라벨
# chans : (출처표시, 채널ID) 목록  ※ 채널 자체가 그 리그면 must 비워도 됨
# must  : 반드시 들어가야 할 단어(없으면 통과). 월드컵만 사용
# good  : 골/하이라이트류 단어 (하나는 있어야 통과)
# exc   : 제외 단어 (있으면 탈락)
GOAL_KO = ["골", "하이라이트", "골모음", "골 모음", "득점", "원더골", "멀티골"]
GOAL_EN = ["goal", "goals", "highlight", "highlights", "wondergoal"]
NOISE   = ["인터뷰", "기자회견", "프리뷰", "예고", "전망", "분석", "관전포인트", "응원", "추첨",
           "입중계", "현장", "preview", "interview", "press conference", "press", "podcast",
           "reaction", "analysis", "draft", "combine", "quiz", "trailer", "fantasy", "fpl",
           "behind the scenes", "documentary", "explained", "mic'd"]

LEAGUES = [
    {
        "key": "worldcup", "label": "2026 월드컵",
        "chans": [("KBS", "UCDIB1DOwPPe58M2fHPyVVDA"),
                  ("JTBC", "UCTdZyOFVzontd9MZOJDg8Qw"),
                  ("FIFA", "UCpcTrCXblq78GZrTUTLWeBw")],
        "must": ["월드컵", "북중미", "world cup", "worldcup", "fifa world cup"],
        "good": GOAL_KO + GOAL_EN + ["shorts"],
        "exc":  NOISE,
    },
    {
        "key": "epl", "label": "EPL",
        "chans": [("EPL", "UCG5qGWdu8nIRZqJ_GgDwQ-w")],   # Premier League 공식
        "must": [],
        "good": GOAL_EN + GOAL_KO + ["match action"],
        "exc":  NOISE + ["matchday live", "build-up", "uncut", "best of the month"],
    },
    {
        "key": "mlb", "label": "MLB",
        "chans": [("MLB", "UCoLrcjPV5PbUrUyXq5mjc_A")],   # MLB 공식
        "must": [],
        "good": GOAL_EN + ["home run", "walk-off", "walkoff", "game recap", "condensed game", "homer"],
        "exc":  NOISE + ["clubhouse", "art club", "doug out", "the show", "let's play ball"],
    },
    {
        "key": "nba", "label": "NBA",
        "chans": [("NBA", "UCWJ2lWNubArHWmf3FIHbfcQ")],   # NBA 공식
        "must": [],
        "good": GOAL_EN + ["top plays", "top 10", "top 5", "plays of the", "game recap", "full highlights", "game winner", "buzzer", "best plays"],
        "exc":  NOISE + ["mixtape", "all-access", "inside the nba"],
    },
]

# 한국 선수/팀 (종목 공통 — '한국' 탭에 모임)
KOR = ["대한민국", "한국", "korea", "손흥민", "heung-min", "son heung", "황희찬",
       "이강인", "김민재", "kim min-jae", "양민혁", "배준호",
       "김하성", "ha-seong", "이정후", "jung hoo", "배지환", "류현진", "ryu"]

UA = {"User-Agent": "Mozilla/5.0 (compatible; NudeSportsBot/1.0)", "Accept-Language": "ko,en;q=0.8"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def feed_entries(xml, source):
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        e = m.group(1)
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", e)
        ttl = re.search(r"<title>(.*?)</title>", e)
        pub = re.search(r"<published>(.*?)</published>", e)
        if not (vid and ttl):
            continue
        yield {
            "youtubeId": vid.group(1).strip(),
            "title": html.unescape(ttl.group(1)).strip(),
            "published": pub.group(1).strip() if pub else "",
            "channel": source,
        }


def has(text, words):
    t = text.lower()
    return any(w.lower() in t for w in words)


def parse_match(title, fallback):
    m = re.search(
        r"(?:^|[\s｜|\[\]/(])([가-힣A-Za-z]{2,12})\s*(?:vs|VS|Vs|:|대)\s*([가-힣A-Za-z]{2,12})(?:[\s｜|\]/)]|$)",
        title)
    return f"{m.group(1)} vs {m.group(2)}" if m else fallback


def main():
    seen, out = set(), []
    for lg in LEAGUES:
        for src, cid in lg["chans"]:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            try:
                xml = fetch(url)
            except Exception as ex:
                print(f"[경고] {lg['key']}/{src} 읽기 실패: {ex}", file=sys.stderr)
                continue
            for it in feed_entries(xml, src):
                t = it["title"]
                if lg["must"] and not has(t, lg["must"]):
                    continue
                if not has(t, lg["good"]):
                    continue
                if has(t, lg["exc"]):
                    continue
                if it["youtubeId"] in seen:
                    continue
                seen.add(it["youtubeId"])
                it["league"] = lg["key"]
                it["match"] = parse_match(t, lg["label"])
                it["tags"] = ["kor"] if has(t, KOR) else []
                out.append(it)

    out.sort(key=lambda x: x.get("published", ""), reverse=True)
    out = out[:80]
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    by = {}
    for o in out:
        by[o["league"]] = by.get(o["league"], 0) + 1
    print(f"수집 완료: {len(out)}개  " + " ".join(f"{k}:{v}" for k, v in by.items()))


if __name__ == "__main__":
    main()
