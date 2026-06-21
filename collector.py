#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HOT 스포츠 쇼츠 — 골/하이라이트 자동 수집기 (v3)
- 한국 방송사/공식 채널 + 쿠팡플레이·SPOTV + 해외 공식 채널의 유튜브 RSS를 읽어
  '골/하이라이트'만 추려 data.json 으로 저장. 쇼츠·일반영상 모두 포함.
- 임베드 막힌 영상은 화면(index.html)에서 자동으로 걸러지므로 여기선 '넓게' 모읍니다.
- 채널을 더 넣거나 거르는 단어를 고치려면 아래 CHANNELS / 단어 목록만 수정하세요.
"""
import urllib.request, urllib.error, re, json, html, sys, concurrent.futures
from datetime import datetime, timezone

# ── 통과 단어(하나는 있어야 통과) / 제외 단어(있으면 탈락) ──
GOOD_KO = ["하이라이트","골","골모음","골 모음","골장면","골 장면","득점","멀티골","원더골",
           "홈런","끝내기","만루","역전","결승골","결승","명장면","베스트","슈퍼플레이","호수비",
           "덩크","버저비터","버저","스파이크","블로킹","mvp","세리머니","리액션","반응","오열","눈물","분노","역대급","움짤"]
GOOD_EN = ["goal","goals","highlight","highlights","home run","homer","walk-off","walkoff",
           "top plays","top 10","top 5","game winner","buzzer","full highlights","best plays",
           "wondergoal","game recap","condensed game"]
NOISE   = ["인터뷰","기자회견","프리뷰","예고","전망","관전포인트","응원","추첨","현장",
           "비하인드","폰터뷰","예능","생중계","중계예고","하프타임","클리닝타임","위클리",
           "당구","pba","lpba","3쿠션","포켓볼",
           "광고","협찬","ppl","이벤트","공지","예매","티켓","구독","브이로그",
           "리뷰","승부예측","예측","대진","후보","시상","어워드","이달의","올해의","생각나는","미리보기","약속",
           "풀경기","풀 경기","풀버전","풀 버전","풀영상","풀 영상","풀타임","다시보기","생중계","중계방송","경기다시","풀하이라이트","풀 하이라이트","full match","full game","livestream",
           "preview","interview","press conference","press","podcast","reaction","analysis",
           "draft","combine","quiz","trailer","fantasy","fpl","behind the scenes","documentary",
           "explained","mic'd","clubhouse","mixtape","all-access","inside the nba"]

# ── 전세계 유명 선수·구단 (영어 제목 통과 + 종목 분류 공용) ──
SOCCER_STARS = [
  "messi","ronaldo","cristiano","mbappe","haaland","salah","bellingham","vinicius","vini jr",
  "kane","de bruyne","lewandowski","lamine yamal","yamal","griezmann","neymar","modric","benzema",
  "kvaratskhelia","rodri","saka","odegaard","foden","cole palmer","rashford","musiala","wirtz",
  "kimmich","van dijk","rudiger","courtois","alisson","ederson","dybala","lautaro","osimhen",
  "vlahovic","mahrez","suarez","di maria","pulisic","isak","nunez","gakpo","bruno fernandes",
  "casemiro","garnacho","endrick","pedri","ter stegen","gundogan","muller","gnabry",
  "alphonso davies","hakimi","donnarumma","dembele","vitinha","lookman","mbeumo"]
SOCCER_BIG = [
  "real madrid","barcelona","man city","manchester","man utd","liverpool","arsenal","chelsea",
  "tottenham","newcastle","aston villa","bayern","dortmund","psg","juventus","inter milan",
  "ac milan","atletico","napoli","champions league","el clasico","clasico","derby","fa cup","europa league"]
MLB_STARS = [
  "ohtani","shohei","aaron judge","judge","mike trout","trout","mookie","betts","juan soto","soto",
  "acuna","skenes","bryce harper","freddie freeman","fernando tatis","tatis","bobby witt","jose ramirez",
  "yordan alvarez","devers","bellinger","machado","arenado","kershaw","verlander","degrom","strider",
  "jazz chisholm","gunnar henderson","corbin carroll","julio rodriguez","corey seager","altuve",
  "bregman","yamamoto","imanaga","darvish","seiya suzuki"]
MLB_BIG = ["dodgers","yankees","astros","braves","red sox","white sox","cubs","world series"]
NBA_STARS = [
  "lebron","stephen curry","curry","kevin durant","durant","jokic","doncic","luka doncic","giannis",
  "wembanyama","tatum","embiid","gilgeous","shai","anthony edwards","ja morant","devin booker",
  "donovan mitchell","jalen brunson","haliburton","sabonis","karl-anthony towns","damian lillard",
  "jimmy butler","kawhi","paul george","anthony davis","zion","kyrie","james harden","banchero",
  "chet holmgren","trae young","jaylen brown"]
NBA_BIG = ["lakers","warriors","celtics","nuggets","knicks","timberwolves","nba finals"]

# ── 종목 자동 분류 키워드(제목 기준, 위에서부터 우선) ──
SPORT_WORDS = [
  ("worldcup",   ["월드컵","world cup","worldcup","북중미"]),
  ("esports",    ["lck","리그오브레전드","league of legends","롤드컵","페이커","faker","젠지","e스포츠","esports"]),
  ("mma",        ["ufc","격투기","종합격투기","파이터","옥타곤","서브미션","테이크다운","로드fc","road fc","블랙컴뱃","주짓수","무에타이"]),
  ("athletics",  ["육상","마라톤","100m","200m","400m","높이뛰기","멀리뛰기","계주","단거리","장거리","육상연맹"]),
  ("baseball",   ["야구","홈런","끝내기","만루","타자","투수","선발","안타","도루","kbo","mlb","npb",
                  "home run","homer","walk-off","baseball","inning"] + MLB_STARS + MLB_BIG),
  ("basketball", ["농구","덩크","버저","3점","자유투","리바운드","nba","kbl","euroleague",
                  "dunk","buzzer","basketball"] + NBA_STARS + NBA_BIG),
  ("volleyball", ["배구","스파이크","블로킹","리시브","세터","v리그","vnl","volleyball","spike"]),
  ("soccer",     ["축구","골","슈팅","프리킥","페널티","코너킥","epl","프리미어","라리가","분데스",
                  "세리에","리그앙","챔피언스","손흥민","이강인","김민재","황희찬","k리그","kleague",
                  "goal","soccer","football","premier","laliga","bundesliga"] + SOCCER_STARS + SOCCER_BIG),
]

# ── 한국팀/선수/리그(한국 탭) ──
KOR = ["대한민국","한국","korea","손흥민","heung-min","son heung","황희찬","이강인","김민재",
       "kim min-jae","양민혁","배준호","김하성","ha-seong","이정후","jung hoo","배지환","류현진","ryu",
       "kbo","k리그","kleague","두산","lg 트윈스","kt 위즈","ssg","nc 다이노스","kia","롯데","삼성 라이온즈",
       "한화","키움","kbl"]

# 해외 공식채널: 한글제목이 아니어도 한국선수가 들어가면 통과
KOR_EN = ["heung-min","son heung","kim min-jae","min-jae","lee kang-in","kang-in",
          "hwang hee","jung hoo","ha-seong","jung-hoo","south korea","korea nt"]

# 해외 빅네임/빅클럽/빅매치 (영어 제목 허용 기준) = 위 선수·구단 목록 전체
STAR_EN = SOCCER_STARS + SOCCER_BIG + MLB_STARS + MLB_BIG + NBA_STARS + NBA_BIG

# ── 채널: (표시, 채널ID, 기본종목 or "auto", 한국채널여부) ──
# (표시, 채널ID, 기본종목, 한국채널, 전용채널)  ※전용채널=True면 '하이라이트' 단어 없어도 그 종목 클립으로 받음
CHANNELS = [
  ("스브스스포츠","UCk4XjBsDuzItvsuVGiDdKqQ","auto",True,False),
  ("SBS Sports","UCqsKWTIu7IhBjLFZS2s1ULQ","auto",True,False),
  ("스탐","UCArK9MK34LsQzPJrl5TZmYA","auto",True,False),
  ("MBC Sports+","UCMkrtzkegsLZJ1s6H7S0eKw","auto",True,False),
  ("JTBC Sports","UCTdZyOFVzontd9MZOJDg8Qw","worldcup",True,True),
  ("KBS N SPORTS","UCdkrHEDb1xT3gts9lct12Ug","auto",True,False),
  ("쿠팡플레이","UCnBht7BrOx-A328KFXgysqQ","auto",True,False),
  ("SPOTV","UCtm_QoN2SIxwCE-59shX7Qg","auto",True,False),
  ("KBO","UCoVz66yWHzVsXAFG8WhJK9g","baseball",True,True),
  ("엠스플야구","UCDHIto3v5jKVLMaVlaMF-Gg","baseball",True,True),
  ("K리그","UCYVxbD_KLbC39PPW9iTBcmQ","soccer",True,True),
  ("K LEAGUE","UCak5ZEX4BjijJcf7fdppuIQ","soccer",True,True),
  ("LCK","UCw1DsweY9b2AKGjV4kGJP1A","esports",True,True),
  ("ROAD FC","UCQ2TX8Q2iVhXhJ0G3NuyEbA","mma",True,True),
  ("tvN SPORTS","UCtybqqaTj6Nx74Azdz1KrsA","auto",True,False),
  ("대한육상연맹","UCJtsER5EcWP6w3DgcyP22Uw","athletics",True,True),
  ("FIFA","UCpcTrCXblq78GZrTUTLWeBw","worldcup",False,False),
  ("EPL","UCG5qGWdu8nIRZqJ_GgDwQ-w","soccer",False,False),
  ("MLB","UCoLrcjPV5PbUrUyXq5mjc_A","baseball",False,False),
  ("NBA","UCWJ2lWNubArHWmf3FIHbfcQ","basketball",False,False),
  ("Volleyball World","UCNMg6XDhRZI2QzL4pWOvP_w","volleyball",False,True),
  ("World Athletics","UCQk7fWv15ChjMJLCRVmtApw","athletics",False,True),
  ("FIBA Basketball","UCtInrnU3QbWqFGsdKT1GZtg","basketball",False,True),
  ("CheerS & Sports","UC2nsP5D6eG2RSFLqA24AAsw","cheers",False,True),
]

SPORT_LABEL={"worldcup":"월드컵","soccer":"축구","baseball":"야구","basketball":"농구","volleyball":"배구","mma":"격투기","athletics":"육상","esports":"LOL","etc":"스포츠","cheers":"HOT"}
HANGUL=re.compile(r"[가-힣]")   # 제목에 한글이 있어야 통과(해외 영어 쇼츠 제외)
UA={"User-Agent":"Mozilla/5.0 (compatible; NudeSportsBot/1.0)","Accept-Language":"ko,en;q=0.8"}

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8","replace")

def embeddable(vid):
    """유튜브 oEmbed로 임베드 가능여부 확인. 401(임베드불가)/404(삭제·비공개)면 제외, 그 외/오류는 안전하게 포함."""
    u="https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v="+vid
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=6) as r:
            return r.status==200
    except urllib.error.HTTPError as e:
        if e.code in (401,404): return False
        return True
    except Exception:
        return True

ROLL_DAYS = 14        # 일반 종목 보관 기간(일): 최근 N일 업로드만 유지
WC_WINDOW = 45        # ★월드컵 보관 기간(일): 대회 전체 커버 후 자동 정리
PER_LEAGUE_CAP = 40   # 일반 종목별 최대 보관 개수
PER_LEAGUE_LONG = 5   # 종목별 가로(롱폼) 최대 개수
OTHER_CAP = 240       # 비(非)월드컵 전체 최대 개수
WC_CAP = 300          # ★월드컵 안전 상한(사실상 전부 보관)

def parse_pub(p):
    """RSS published(ISO) 또는 'YYYY-MM-DD' 를 timezone-aware datetime 으로. 실패시 None."""
    if not p: return None
    p=p.strip()
    try:
        return datetime.fromisoformat(p.replace("Z","+00:00"))
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S","%Y-%m-%d"):
        try:
            d=datetime.strptime(p,fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def load_existing():
    """기존 data.json 을 읽어 누적 병합의 바탕으로 사용. 없거나 깨지면 빈 목록."""
    try:
        with open("data.json",encoding="utf-8") as f:
            d=json.load(f)
            return d if isinstance(d,list) else []
    except Exception:
        return []

def drop_dead(items):
    """죽은(임베드불가) 영상 제거. 과다제거(40% 미만 생존)면 비정상으로 보고 필터 건너뜀(안전)."""
    ok={}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
            futs={ex.submit(embeddable,o["youtubeId"]):o for o in items}
            for fut in concurrent.futures.as_completed(futs):
                ok[futs[fut]["youtubeId"]]=fut.result()
    except Exception as ex:
        print(f"[경고] 임베드체크 실패 → 건너뜀: {ex}", file=sys.stderr); return items
    alive=[o for o in items if ok.get(o["youtubeId"],True)]
    if len(alive) >= max(1,int(len(items)*0.4)):
        print(f"임베드체크: {len(items)}개 중 {len(items)-len(alive)}개 제거", file=sys.stderr)
        return alive
    print(f"[경고] 임베드체크 과다제거({len(alive)}/{len(items)}) → 건너뜀", file=sys.stderr)
    return items

def feed_entries(xml, source):
    for m in re.finditer(r"<entry>(.*?)</entry>", xml, re.S):
        e=m.group(1)
        vid=re.search(r"<yt:videoId>(.*?)</yt:videoId>",e)
        ttl=re.search(r"<title>(.*?)</title>",e)
        pub=re.search(r"<published>(.*?)</published>",e)
        lnk=re.search(r'<link rel="alternate" href="(.*?)"',e)
        sts=re.search(r'<media:statistics views="(\d+)"',e)
        if not (vid and ttl): continue
        link=lnk.group(1) if lnk else ""
        yield {"youtubeId":vid.group(1).strip(),
               "title":html.unescape(ttl.group(1)).strip(),
               "published":pub.group(1).strip() if pub else "",
               "channel":source,
               "short":"/shorts/" in link,
               "views":int(sts.group(1)) if sts else 0}

def has(text, words):
    t=text.lower()
    return any(w.lower() in t for w in words)

YOUTH = ["중고","중학","고등","고교","u20","u18","u16","u14","꿈나무","유소년","학생부","초등","종별","주니어","생활체육","clubs"]

def classify(title, default):
    if has(title, SPORT_WORDS[0][1]): return "worldcup"
    if default!="auto": return default
    for key,words in SPORT_WORDS:
        if has(title, words): return key
    return "etc"

def parse_match(title, fallback):
    m=re.search(r"(?:^|[\s｜|\[\]/(])([가-힣A-Za-z]{2,12})\s*(?:vs|VS|Vs|:|대)\s*([가-힣A-Za-z]{2,12})(?:[\s｜|\]/)]|$)", title)
    return f"{m.group(1)} vs {m.group(2)}" if m else fallback

def roll_finalize(new_items, existing, now, dead_filter=None):
    """기존+신규 병합 → 최근 ROLL_DAYS 윈도우 → 정렬 → 죽은영상제거 → 종목/전체 상한. 순수함수(테스트용)."""
    now_iso=now.isoformat()
    bymap={}
    for it in existing:
        if it.get("youtubeId"): bymap[it["youtubeId"]]=it
    for it in new_items:
        vid=it.get("youtubeId")
        if not vid: continue
        it["first_seen"]=bymap[vid].get("first_seen", now_iso) if vid in bymap else now_iso
        bymap[vid]=it   # 조회수·제목 등 최신 메타로 갱신
    merged=list(bymap.values())

    def within(it):
        win = WC_WINDOW if it.get("league")=="worldcup" else ROLL_DAYS
        p=parse_pub(it.get("published",""))
        if p is not None:
            return -1 <= (now-p).days <= win
        fs=parse_pub(it.get("first_seen",""))
        return (now-fs).days <= win if fs is not None else True
    merged=[it for it in merged if within(it)]

    merged.sort(key=lambda x:(1 if x.get("short") else 0, x.get("views",0)), reverse=True)
    if dead_filter: merged=dead_filter(merged)

    capped=[]; per={}; perns={}; wc=0; others=0
    for o in merged:                       # 이미 쇼츠우선+조회순 정렬됨
        k=o.get("league","etc")
        if k=="worldcup":                  # ★월드컵: 종목/전체 상한 면제, 사실상 전부
            if wc>=WC_CAP: continue
            wc+=1; capped.append(o); continue
        if others>=OTHER_CAP: continue     # 비월드컵 전체 상한
        if per.get(k,0)>=PER_LEAGUE_CAP: continue
        if not o.get("short"):
            if perns.get(k,0)>=PER_LEAGUE_LONG: continue
            perns[k]=perns.get(k,0)+1
        per[k]=per.get(k,0)+1; others+=1; capped.append(o)
    return capped

def main():
    seen,out=set(),[]
    for src,cid,default,is_kor,trusted in CHANNELS:
        url=f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        try: xml=fetch(url)
        except Exception as ex:
            print(f"[경고] {src} 읽기 실패: {ex}", file=sys.stderr); continue
        for it in feed_entries(xml, src):
            t=it["title"]
            if not trusted and not has(t, GOOD_KO+GOOD_EN) and not has(t, STAR_EN): continue   # 전용채널·빅네임은 통과단어 없어도 OK
            if has(t, NOISE): continue
            if not HANGUL.search(t):
                if not trusted and (is_kor or not has(t, KOR_EN+STAR_EN)): continue   # 일반채널 해외: 한국선수·빅스타·빅매치만 / 전용채널은 면제
            if it["youtubeId"] in seen: continue
            seen.add(it["youtubeId"])
            sport=classify(t, default)
            if sport=="athletics" and has(t, YOUTH): continue   # 육상은 성인부만
            it["league"]=sport
            it["match"]=parse_match(t, SPORT_LABEL.get(sport,"경기"))
            it["tags"]=["kor"] if has(t, KOR) else []
            it["kor_src"]=is_kor
            out.append(it)
    out=roll_finalize(out, load_existing(), datetime.now(timezone.utc), dead_filter=drop_dead)
    with open("data.json","w",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=1)
    by={}
    for o in out: by[o["league"]]=by.get(o["league"],0)+1
    print(f"수집 완료: {len(out)}개  "+" ".join(f"{k}:{v}" for k,v in by.items()))

if __name__=="__main__":
    main()
