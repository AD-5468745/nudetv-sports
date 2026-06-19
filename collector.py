#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
누드TV 스포츠 — 골/하이라이트 자동 수집기 (v2)
- 한국 방송사/공식 채널 + 쿠팡플레이·SPOTV + 해외 공식 채널의 유튜브 RSS를 읽어
  '골/하이라이트'만 추려 data.json 으로 저장. 쇼츠·일반영상 모두 포함.
- 임베드 막힌 영상은 화면(index.html)에서 자동으로 걸러지므로 여기선 '넓게' 모읍니다.
- 채널을 더 넣거나 거르는 단어를 고치려면 아래 CHANNELS / 단어 목록만 수정하세요.
"""
import urllib.request, re, json, html, sys

# ── 통과 단어(하나는 있어야 통과) / 제외 단어(있으면 탈락) ──
GOOD_KO = ["하이라이트","골","골모음","골 모음","골장면","골 장면","득점","멀티골","원더골",
           "홈런","끝내기","만루","역전","결승골","결승","명장면","베스트","슈퍼플레이","호수비",
           "덩크","버저비터","버저","스파이크","블로킹","mvp","풀영상","풀 하이라이트"]
GOOD_EN = ["goal","goals","highlight","highlights","home run","homer","walk-off","walkoff",
           "top plays","top 10","top 5","game winner","buzzer","full highlights","best plays",
           "wondergoal","game recap","condensed game"]
NOISE   = ["인터뷰","기자회견","프리뷰","예고","전망","관전포인트","응원","추첨","현장",
           "비하인드","폰터뷰","예능","생중계","중계예고","하프타임","클리닝타임","위클리",
           "광고","협찬","ppl","이벤트","공지","예매","티켓","구독","브이로그",
           "preview","interview","press conference","press","podcast","reaction","analysis",
           "draft","combine","quiz","trailer","fantasy","fpl","behind the scenes","documentary",
           "explained","mic'd","clubhouse","mixtape","all-access","inside the nba"]

# ── 종목 자동 분류 키워드(제목 기준, 위에서부터 우선) ──
SPORT_WORDS = [
  ("worldcup",   ["월드컵","world cup","worldcup","북중미"]),
  ("baseball",   ["야구","홈런","끝내기","만루","타자","투수","선발","안타","도루","kbo","mlb","npb",
                  "home run","homer","walk-off","baseball","inning"]),
  ("basketball", ["농구","덩크","버저","3점","자유투","리바운드","nba","kbl","euroleague",
                  "dunk","buzzer","basketball"]),
  ("volleyball", ["배구","스파이크","블로킹","리시브","세터","v리그","vnl","volleyball","spike"]),
  ("soccer",     ["축구","골","슈팅","프리킥","페널티","코너킥","epl","프리미어","라리가","분데스",
                  "세리에","리그앙","챔피언스","손흥민","이강인","김민재","황희찬","k리그","kleague",
                  "goal","soccer","football","premier","laliga","bundesliga"]),
]

# ── 한국팀/선수/리그(한국 탭) ──
KOR = ["대한민국","한국","korea","손흥민","heung-min","son heung","황희찬","이강인","김민재",
       "kim min-jae","양민혁","배준호","김하성","ha-seong","이정후","jung hoo","배지환","류현진","ryu",
       "kbo","k리그","kleague","두산","lg 트윈스","kt 위즈","ssg","nc 다이노스","kia","롯데","삼성 라이온즈",
       "한화","키움","kbl"]

# ── 채널: (표시, 채널ID, 기본종목 or "auto", 한국채널여부) ──
CHANNELS = [
  ("스브스스포츠","UCk4XjBsDuzItvsuVGiDdKqQ","auto",True),
  ("SBS Sports","UCqsKWTIu7IhBjLFZS2s1ULQ","auto",True),
  ("스탐","UCArK9MK34LsQzPJrl5TZmYA","auto",True),
  ("MBC Sports+","UCMkrtzkegsLZJ1s6H7S0eKw","auto",True),
  ("JTBC","UCTdZyOFVzontd9MZOJDg8Qw","auto",True),
  ("쿠팡플레이","UCnBht7BrOx-A328KFXgysqQ","auto",True),
  ("SPOTV","UCtm_QoN2SIxwCE-59shX7Qg","auto",True),
  ("KBO","UCoVz66yWHzVsXAFG8WhJK9g","baseball",True),
  ("엠스플야구","UCDHIto3v5jKVLMaVlaMF-Gg","baseball",True),
  ("K리그","UCYVxbD_KLbC39PPW9iTBcmQ","soccer",True),
  ("K LEAGUE","UCak5ZEX4BjijJcf7fdppuIQ","soccer",True),
  ("FIFA","UCpcTrCXblq78GZrTUTLWeBw","worldcup",False),
  ("EPL","UCG5qGWdu8nIRZqJ_GgDwQ-w","soccer",False),
  ("MLB","UCoLrcjPV5PbUrUyXq5mjc_A","baseball",False),
  ("NBA","UCWJ2lWNubArHWmf3FIHbfcQ","basketball",False),
]

SPORT_LABEL={"worldcup":"월드컵","soccer":"축구","baseball":"야구","basketball":"농구","volleyball":"배구","etc":"스포츠"}
UA={"User-Agent":"Mozilla/5.0 (compatible; NudeSportsBot/1.0)","Accept-Language":"ko,en;q=0.8"}

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8","replace")

def feed_entries(xml, source):
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        e=m.group(1)
        vid=re.search(r"<yt:videoId>(.*?)</yt:videoId>",e)
        ttl=re.search(r"<title>(.*?)</title>",e)
        pub=re.search(r"<published>(.*?)</published>",e)
        lnk=re.search(r'<link rel="alternate" href="(.*?)"',e)
        if not (vid and ttl): continue
        link=lnk.group(1) if lnk else ""
        yield {"youtubeId":vid.group(1).strip(),
               "title":html.unescape(ttl.group(1)).strip(),
               "published":pub.group(1).strip() if pub else "",
               "channel":source,
               "short":"/shorts/" in link}

def has(text, words):
    t=text.lower()
    return any(w.lower() in t for w in words)

def classify(title, default):
    if has(title, SPORT_WORDS[0][1]): return "worldcup"
    if default!="auto": return default
    for key,words in SPORT_WORDS:
        if has(title, words): return key
    return "etc"

def parse_match(title, fallback):
    m=re.search(r"(?:^|[\s｜|\[\]/(])([가-힣A-Za-z]{2,12})\s*(?:vs|VS|Vs|:|대)\s*([가-힣A-Za-z]{2,12})(?:[\s｜|\]/)]|$)", title)
    return f"{m.group(1)} vs {m.group(2)}" if m else fallback

def main():
    seen,out=set(),[]
    for src,cid,default,is_kor in CHANNELS:
        url=f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        try: xml=fetch(url)
        except Exception as ex:
            print(f"[경고] {src} 읽기 실패: {ex}", file=sys.stderr); continue
        for it in feed_entries(xml, src):
            t=it["title"]
            if not has(t, GOOD_KO+GOOD_EN): continue
            if has(t, NOISE): continue
            if it["youtubeId"] in seen: continue
            seen.add(it["youtubeId"])
            sport=classify(t, default)
            it["league"]=sport
            it["match"]=parse_match(t, SPORT_LABEL.get(sport,"경기"))
            it["tags"]=["kor"] if has(t, KOR) else []
            it["kor_src"]=is_kor
            out.append(it)
    out.sort(key=lambda x:x.get("published",""), reverse=True)   # 최신순
    out.sort(key=lambda x: 0 if x.get("kor_src") else 1)         # 안정정렬: 한국 채널 우선
    out=out[:80]
    with open("data.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=1)
    by={}
    for o in out: by[o["league"]]=by.get(o["league"],0)+1
    print(f"수집 완료: {len(out)}개  "+" ".join(f"{k}:{v}" for k,v in by.items()))

if __name__=="__main__":
    main()
