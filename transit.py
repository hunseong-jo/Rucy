# -*- coding: utf-8 -*-
"""
대중교통(버스) — 인천·경기(부천)·서울 실시간 도착 정보

세 지역이 전부 다른 API라 지역별 어댑터를 둡니다(공공데이터포털 키 하나로 셋 다 됨):
  · 인천  apis.data.go.kr/6280000  (XML, 태그가 대문자. 도착정보에 버스 번호가 없어
          노선ID→번호 변환이 필요 — getBusRouteNo 결과를 파일에 캐시)
  · 경기  apis.data.go.kr/6410000  (구 주소는 404 — **v2 경로만 삶**. format=json 지원)
  · 서울  ws.bus.go.kr             (⚠️https가 먹통이라 **http로만** 붙는다. 실측 2026-07-14.
          도착정보(getStationByUid)에 버스 번호가 같이 와서 변환 불필요)

정류장 이름이 여러 지역에 있을 수 있어 사용자 지역 우선(인천→경기→서울)으로 찾고,
region 인자로 못박을 수 있습니다. 같은 이름 정류장 두 개(상·하행)는 둘 다 보여줍니다.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(_DIR, "keys", "data_go_kr.txt")
CACHE_FILE = os.path.join(_DIR, "memory", "transit_cache.json")   # 노선ID → 버스번호

SETUP_GUIDE = (
    "버스 도착 정보를 보려면 공공데이터포털(data.go.kr) 인증키가 필요합니다.\n"
    "keys/data_go_kr.txt 에 키를 저장해 주세요. (신청: 인천 15059084·15056529·15058487, "
    "경기 15080346·15080666, 서울 15000314·15000303 — 전부 자동승인)"
)


def _key():
    try:
        with open(KEY_FILE, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    except OSError:
        return ""


def _fetch(url, params, timeout=15):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(url + "?" + q, headers={"User-Agent": "lucy-agent"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _xml_items(raw):
    """<itemList> 항목들을 {소문자태그: 값} 목록으로. 서울·인천이 같은 뼈대(msgBody/itemList)."""
    root = ET.fromstring(raw)
    items = []
    for el in root.iter():
        if el.tag.lower().endswith("itemlist"):
            items.append({c.tag.lower(): (c.text or "").strip() for c in el})
    return items


def _json_body(raw):
    """경기 v2(format=json)의 몸통. msgHeader.resultCode 0·4(결과없음) 외는 오류로 던짐."""
    data = json.loads(raw.decode("utf-8"))
    resp = data.get("response", data)
    head = resp.get("msgHeader") or {}
    code = str(head.get("resultCode", "0"))
    if code not in ("0", "4"):
        raise RuntimeError(f"경기 API 오류 {code}: {head.get('resultMessage')}")
    return resp.get("msgBody") or {}


def _listify(v):
    """경기 v2는 결과가 1개면 dict, 여러 개면 list로 옴 — 항상 list로."""
    if not v:
        return []
    return v if isinstance(v, list) else [v]


def _cache_load():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _cache_save(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except OSError:
        pass                                    # 캐시는 못 써도 기능은 살아야 함


def _min(sec_or_min, already_min=False):
    """초(인천)·분(경기)을 '곧 도착 / N분 뒤'로."""
    try:
        n = int(sec_or_min)
    except (TypeError, ValueError):
        return ""
    m = n if already_min else n // 60
    return "곧 도착" if m <= 1 else f"{m}분 뒤"


# ── 서울 (ws.bus.go.kr — http 전용) ──────────────────────────────
def _seoul_stops(name, key):
    raw = _fetch("http://ws.bus.go.kr/api/rest/stationinfo/getStationByName",
                 {"serviceKey": key, "stSrch": name})
    return [{"region": "서울", "id": it.get("stid", ""), "ars": it.get("arsid", ""),
             "name": it.get("stnm", "")} for it in _xml_items(raw)]


def _seoul_arrivals(stop, key):
    raw = _fetch("http://ws.bus.go.kr/api/rest/stationinfo/getStationByUid",
                 {"serviceKey": key, "arsId": stop["ars"]})
    lines = []
    for it in _xml_items(raw):
        no = it.get("rtnm", "?")
        direction = it.get("adirection", "")
        msg = it.get("arrmsg1", "")
        if it.get("arrmsg2") and it["arrmsg2"] not in ("", "출발대기"):
            msg += f", 다음 {it['arrmsg2']}"
        head = f"{no}번" + (f" ({direction} 방면)" if direction else "")
        lines.append((no, f"  {head}: {msg}"))
    return lines


# ── 인천 (6280000 — XML 대문자 태그, 노선번호는 캐시로 변환) ─────
def _incheon_stops(name, key):
    raw = _fetch("https://apis.data.go.kr/6280000/busStationService/getBusStationNmList",
                 {"serviceKey": key, "pageNo": 1, "numOfRows": 10, "bstopNm": name})
    out = []
    for it in _xml_items(raw):
        sid = it.get("bstopid") or it.get("bstop_id", "")
        nm = it.get("bstopnm") or it.get("bstop_nm", "")
        if sid:
            out.append({"region": "인천", "id": sid, "name": nm})
    return out


def _incheon_via_routes(bstop_id, key, cache):
    """정류소를 지나는 노선표: ROUTEID → (버스번호, 행선지). 도착정보에 번호가 없어서
    이걸로 바꿔 붙인다(⚠️getBusRouteNo는 번호→노선 방향이라 반대로는 못 씀, 실측).
    노선 개편은 드무니 정류소 단위로 파일 캐시."""
    hit = cache.get("incheon_stop", {}).get(str(bstop_id))
    if hit:
        return hit
    routes = {}
    raw = _fetch("https://apis.data.go.kr/6280000/busStationService/getBusStationViaRouteList",
                 {"serviceKey": key, "pageNo": 1, "numOfRows": 200, "bstopId": bstop_id})
    for it in _xml_items(raw):
        rid = it.get("routeid", "")
        if rid:
            routes[rid] = (it.get("routeno", "?"), it.get("destination", ""))
    if routes:
        cache.setdefault("incheon_stop", {})[str(bstop_id)] = routes
    return routes


def _incheon_arrivals(stop, key):
    cache = _cache_load()
    try:
        routes = _incheon_via_routes(stop["id"], key, cache)
    except Exception:
        routes = {}                              # 번호를 못 바꿔도 도착 정보는 보여준다
    raw = _fetch("https://apis.data.go.kr/6280000/busArrivalService/getAllRouteBusArrivalList",
                 {"serviceKey": key, "pageNo": 1, "numOfRows": 30, "bstopId": stop["id"]})
    lines = []
    for it in _xml_items(raw):
        no, dest = routes.get(it.get("routeid", ""), (f"노선{it.get('routeid', '?')}", ""))
        when = _min(it.get("arrivalestimatetime"))
        rest = it.get("rest_stop_count", "")
        extra = f" ({rest}정거장 전)" if rest else ""
        last = " · 막차" if it.get("lastbusyn") in ("1", "Y") else ""
        head = f"{no}번" + (f" ({dest} 방면)" if dest else "")
        lines.append((no, f"  {head}: {when}{extra}{last}"))
    _cache_save(cache)
    return lines


# ── 경기 = 부천 포함 (6410000 v2 — JSON) ─────────────────────────
def _gyeonggi_stops(name, key):
    raw = _fetch("https://apis.data.go.kr/6410000/busstationservice/v2/getBusStationListv2",
                 {"serviceKey": key, "keyword": name, "format": "json"})
    out = []
    for it in _listify(_json_body(raw).get("busStationList")):
        out.append({"region": str(it.get("regionName") or "경기"),
                    "id": str(it.get("stationId", "")),
                    "name": str(it.get("stationName", ""))})
    return out


def _gyeonggi_route_name(route_id, key, cache):
    rid = str(route_id)
    hit = cache.get("gyeonggi", {}).get(rid)
    if hit:
        return hit
    try:
        raw = _fetch("https://apis.data.go.kr/6410000/busrouteservice/v2/getBusRouteInfoItemv2",
                     {"serviceKey": key, "routeId": rid, "format": "json"})
        item = _json_body(raw).get("busRouteInfoItem") or {}
        no = str(item.get("routeName") or "")
        if no:
            cache.setdefault("gyeonggi", {})[rid] = no
            return no
    except Exception:
        pass
    return f"노선{rid}"


def _gyeonggi_arrivals(stop, key):
    raw = _fetch("https://apis.data.go.kr/6410000/busarrivalservice/v2/getBusArrivalListv2",
                 {"serviceKey": key, "stationId": stop["id"], "format": "json"})
    cache = _cache_load()
    lines = []
    for it in _listify(_json_body(raw).get("busArrivalList")):
        no = str(it.get("routeName") or "") or _gyeonggi_route_name(it.get("routeId", ""), key, cache)
        t1, loc1 = it.get("predictTime1"), it.get("locationNo1")
        when = _min(t1, already_min=True)
        if not when:
            continue
        extra = f" ({loc1}정거장 전)" if loc1 else ""
        nxt = _min(it.get("predictTime2"), already_min=True)
        lines.append((no, f"  {no}번: {when}{extra}" + (f", 다음 {nxt}" if nxt else "")))
    _cache_save(cache)
    return lines


REGIONS = [
    ("인천", _incheon_stops, _incheon_arrivals),
    ("경기", _gyeonggi_stops, _gyeonggi_arrivals),
    ("서울", _seoul_stops, _seoul_arrivals),
]


def home(config):
    """'집 앞 버스' — config transit.home에 박아둔 정류장·노선만 골라 본다.
    정류장 id는 방면(동암남부역행)까지 고른 것이라 반대편 차는 안 섞인다."""
    entries = (config or {}).get("transit", {}).get("home", [])
    if not entries:
        return ("집 앞 정류장이 아직 설정되지 않았습니다. "
                "config.json의 transit.home에 정류장과 버스 번호를 넣어 주세요.")
    key = _key()
    if not key:
        return SETUP_GUIDE
    out = []
    for e in entries:
        arrive = {r[0]: r[2] for r in REGIONS}.get(e.get("region", "인천"), _incheon_arrivals)
        stop = {"region": e.get("region", "인천"), "id": str(e.get("id", "")),
                "name": e.get("stop", ""), "ars": str(e.get("id", ""))}
        try:
            lines = arrive(stop, key)
        except Exception as ex:
            out.append(f"{e.get('bus')}번({e.get('stop')}): 조회 실패 ({type(ex).__name__})")
            continue
        want = str(e.get("bus", "")).strip()
        picked = [l[1].strip() for l in lines if l[0] == want] if want else [l[1].strip() for l in lines]
        note = f" — {e['note']}" if e.get("note") else ""
        if picked:
            out.append(f"{e.get('stop')}{note}\n  " + "\n  ".join(picked))
        else:
            out.append(f"{e.get('stop')}{note}\n  {want}번: 지금 오는 차가 없습니다.")
    return "[집 앞 버스]\n" + "\n\n".join(out)


# ── 지하철 (서울 열린데이터광장 실시간 도착 — 수도권 전철을 폭넓게 커버) ─────
# ⚠️버스와 키가 다릅니다: 버스=공공데이터포털(data.go.kr), 지하철=서울 열린데이터광장
#   (data.seoul.go.kr). 키가 없으면 'sample' 키로도 돌아가지만(실측) 5건 제한·시험용이라
#   정식 키를 안내합니다. ⚠️https는 443이 먹통 — 서울 버스 API처럼 **http로만**(실측 2026-07-14).
# 동암역(경인선 1호선) 실측: subwayId 1001, 방면·행선지·도착문구가 그대로 옵니다.
SUBWAY_KEY_FILE = os.path.join(_DIR, "keys", "seoul_subway.txt")

SUBWAY_GUIDE = (
    "지하철 도착 정보의 정식 인증키가 없어 시험용(sample) 키로 조회했습니다(최대 5건).\n"
    "서울 열린데이터광장(data.seoul.go.kr)에서 인증키를 받아 keys/seoul_subway.txt에 "
    "저장하면 제한 없이 조회됩니다. (가입 → 인증키 신청 — 자동승인, 버스 키와는 별개)"
)

_SUBWAY_LINES = {
    "1001": "1호선", "1002": "2호선", "1003": "3호선", "1004": "4호선",
    "1005": "5호선", "1006": "6호선", "1007": "7호선", "1008": "8호선",
    "1009": "9호선", "1061": "중앙선", "1063": "경의중앙선", "1065": "공항철도",
    "1067": "경춘선", "1075": "수인분당선", "1077": "신분당선", "1081": "경강선",
    "1092": "우이신설선", "1093": "서해선", "1032": "GTX-A",
}


def _subway_key():
    try:
        with open(SUBWAY_KEY_FILE, "r", encoding="utf-8-sig") as f:
            key = f.read().strip()
        if key:
            return key, False
    except OSError:
        pass
    return "sample", True                        # 시험용 키 — 동작하되 5건 제한


def subway(station, line="", config=None):
    """역 이름(+선택: 노선)으로 수도권 전철 실시간 도착을 사람이 읽을 문장으로."""
    station = (station or "").strip().replace(" ", "")
    if station in ("집", "집앞", ""):
        home = (config or {}).get("transit", {}).get("home_subway", {})
        station = str(home.get("station") or "")
        line = line or str(home.get("line") or "")
        if not station:
            return ("어느 역인지 알려주세요. (단골 역을 정해두려면 config.json의 "
                    "transit.home_subway에 station을 넣으세요)")
    if station.endswith("역") and len(station) > 1:
        station = station[:-1]                   # API는 '동암역'이 아니라 '동암'으로 찾습니다

    key, is_sample = _subway_key()
    rows = 5 if is_sample else 30
    url = ("http://swopenapi.seoul.go.kr/api/subway/" + urllib.parse.quote(key)
           + f"/json/realtimeStationArrival/0/{rows}/" + urllib.parse.quote(station))
    req = urllib.request.Request(url, headers={"User-Agent": "lucy-agent"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # 오류는 두 모양으로 옵니다(실측): 성공은 errorMessage 안에 INFO-000,
    # '없는 역'은 **맨 바깥에** code=INFO-200. 둘 다 봐야 합니다.
    head = data.get("errorMessage") or data
    code = str(head.get("code") or "")
    if code == "INFO-200" or not data.get("realtimeArrivalList"):
        return f"'{station}'역의 도착 정보를 찾지 못했습니다. 역 이름을 확인해 주세요(예: 동암, 부평)."
    if code and code != "INFO-000":
        return (f"지하철 조회 실패 ({code}: {head.get('message', '')})"
                + ("\n" + SUBWAY_GUIDE if is_sample else ""))

    want = line.replace("호선", "").replace(" ", "")
    out = []
    for it in data["realtimeArrivalList"]:
        nm = _SUBWAY_LINES.get(str(it.get("subwayId")), "")
        if want and want not in nm.replace("호선", ""):
            continue                             # '1호선만' 같은 노선 필터
        dest = (it.get("bstatnNm") or "").strip()
        msg = re.sub(r"\[(\d+)\]", r"\1", it.get("arvlMsg2") or "")   # [6]번째 → 6번째
        kind = it.get("btrainSttus") or ""
        kind = f" {kind}" if kind in ("급행", "특급", "ITX") else ""
        last = " · 막차" if str(it.get("lstcarAt")) == "1" else ""
        updn = it.get("updnLine") or ""
        out.append(f"  {nm} {updn}{kind} {dest}행: {msg}{last}")
    if not out:
        return f"{station}역에 지금 오는 {line or '열차'} 정보가 없습니다."
    body = f"[{station}역 실시간 도착]\n" + "\n".join(out[:12])
    if is_sample:
        body += "\n\n" + SUBWAY_GUIDE
    return body


def arrivals(stop_name, bus="", region=""):
    """정류장 이름(+선택: 버스번호·지역)으로 실시간 도착 정보를 사람이 읽을 문장으로."""
    key = _key()
    if not key:
        return SETUP_GUIDE
    stop_name = (stop_name or "").strip()
    if not stop_name:
        return "정류장 이름을 알려주세요. (예: 부평역, 부천역, 서울역)"

    order = REGIONS
    if region:
        picked = [r for r in REGIONS if r[0] in region or region in r[0]
                  or (r[0] == "경기" and "부천" in region)]
        order = picked or REGIONS

    tried, blocked = [], []
    for rname, find, arrive in order:
        try:
            stops = find(stop_name, key)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                blocked.append(rname)            # 키 미반영/미신청 — 다른 지역은 계속
                continue
            raise
        except Exception:
            continue
        tried.append(rname)
        if not stops:
            continue

        out = []
        for stop in stops[:2]:                   # 같은 이름 상·하행 정류장 둘 다
            try:
                lines = arrive(stop, key)
            except Exception as e:
                out.append(f"[{stop['region']}] {stop['name']}: 도착 정보 조회 실패 ({type(e).__name__})")
                continue
            if bus:
                want = str(bus).replace("번", "").strip()
                exact = [l for l in lines if l[0] == want]   # '66'이 '661'을 물지 않게
                lines = exact or [l for l in lines if want in l[0]]
            body = "\n".join(l[1] for l in lines[:12])
            out.append(f"[{stop['region']}] {stop['name']}\n" + (body or "  지금 오는 버스가 없습니다."))
        if len(stops) > 2:
            shown = {stop["name"] for stop in stops[:2]}
            others = ", ".join(dict.fromkeys(                 # 이름 중복 제거(순서 유지)
                s["name"] for s in stops[2:] if s["name"] not in shown))
            if others:
                out.append(f"(같은 이름 정류장 더 있음: {others} — 동네 이름을 붙여 다시 물어보세요)")
        return "\n\n".join(out)

    if blocked and not tried:
        return ("공공데이터포털 키가 아직 반영되지 않았습니다(" + ", ".join(blocked) +
                "). 신청 승인 후 보통 1시간쯤 걸립니다 — 나중에 다시 물어보세요.")
    return f"'{stop_name}' 정류장을 {'·'.join(tried) or '어느 지역에서도'} 찾지 못했습니다. 정확한 정류장 이름으로 다시 물어보세요."
