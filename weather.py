# -*- coding: utf-8 -*-
"""
날씨 — Open-Meteo (무료 · 키 불필요 · 가입 불필요)

공공데이터포털(기상청 API)이 아니라 Open-Meteo를 쓰는 이유:
  · 키 발급·승인 절차가 없다 — 루시의 'pip·가입 최소' 원칙 유지.
  · 기상청 격자(nx, ny) 변환 없이 위경도로 바로 묻는다.
  · models=kma_seamless 를 주면 어차피 **같은 기상청(KMA) 모델**의 예보를 받는다.
    (그 모델이 삐끗하면 기본 모델로 한 번 물러선다 — 날씨가 안 나오는 것보단 낫다)

지역 이름 → 위경도도 Open-Meteo의 지오코딩(무키)으로 푼다. '수원', '부산 해운대'처럼
사용자가 어디를 묻든 그 자리에서 찾는다. 기본 지역은 config의 weather.location.
"""
import datetime
import json
import urllib.parse
import urllib.request

GEO_URL = "https://nominatim.openstreetmap.org/search"       # 지명 → 위경도 (OSM, 무키)
GEO_URL2 = "https://geocoding-api.open-meteo.com/v1/search"  # 예비
API_URL = "https://api.open-meteo.com/v1/forecast"

# WMO 날씨 코드 → 한국어 (Open-Meteo 문서의 코드표)
WMO = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
    45: "안개", 48: "짙은 안개",
    51: "이슬비", 53: "이슬비", 55: "굵은 이슬비", 56: "어는 이슬비", 57: "어는 이슬비",
    61: "약한 비", 63: "비", 65: "강한 비", 66: "어는 비", 67: "강한 어는 비",
    71: "약한 눈", 73: "눈", 75: "폭설", 77: "싸락눈",
    80: "소나기", 81: "소나기", 82: "강한 소나기", 85: "소낙눈", 86: "강한 소낙눈",
    95: "뇌우", 96: "우박을 동반한 뇌우", 99: "강한 우박 뇌우",
}


def _get(url, params):
    req = urllib.request.Request(
        url + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": "lucy-agent"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _locate(name):
    """
    지역 이름 → (위도, 경도, 표시용 이름)

    Open-Meteo의 지오코딩은 한국어 지명에 약합니다(실측: '서울'은 아예 못 찾고,
    '수원'은 수원시가 아니라 동명의 시골 마을을 줍니다). 그래서 한국어에 강한
    Nominatim(OSM)을 먼저 쓰고, 그쪽이 죽어 있으면 Open-Meteo로 물러섭니다.
    """
    try:
        hits = _get(GEO_URL, {"q": name, "format": "json", "limit": 1,
                              "accept-language": "ko"})
        if hits:
            h = hits[0]
            label = (h.get("display_name") or name).split(",")[0].strip()
            return float(h["lat"]), float(h["lon"]), label
    except Exception:
        pass                                    # 예비 지오코더로

    data = _get(GEO_URL2, {"name": name, "count": 1, "language": "ko"})
    hits = data.get("results") or []
    if not hits:
        raise ValueError(f"'{name}' 위치를 찾지 못했습니다 — 시·군·구 이름으로 다시 물어보세요")
    h = hits[0]
    label = h.get("name") or name
    if h.get("admin1") and h["admin1"] != label:
        label = f"{h['admin1']} {label}"
    return h["latitude"], h["longitude"], label


def _sky(code):
    return WMO.get(code, "흐림")


def _umbrella(prob, rain_mm):
    if prob >= 60 or rain_mm >= 5:
        return f"우산을 꼭 챙기세요 (강수확률 {prob}%)."
    if prob >= 30:
        return f"우산을 가방에 넣어두면 안심입니다 (강수확률 {prob}%)."
    return "우산은 필요 없겠습니다."


def _fetch(location, config=None):
    """지역 이름으로 예보 원자료를 받아옵니다. (표시용 지명, 응답 dict)"""
    location = (location or "").strip() \
        or (config or {}).get("weather", {}).get("location", "서울")
    lat, lon, label = _locate(location)

    params = {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code",
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "precipitation_probability_max,precipitation_sum"),
        "timezone": "Asia/Seoul", "forecast_days": 2,
    }
    # 기상청(KMA) 모델을 먼저 묻되, **HTTP 성공이어도 값이 전부 null인 빈 껍데기**를 줄 때가
    # 있습니다(실측 2026-07-13). 오류가 아니라서 except로는 못 잡고, 값을 보고 물러섭니다.
    try:
        data = _get(API_URL, dict(params, models="kma_seamless"))
    except Exception:
        data = {}
    if (data.get("current") or {}).get("temperature_2m") is None:
        data = _get(API_URL, params)                    # 기본(best_match) 모델
    return label, data


def rain_today(config=None, location=""):
    """오늘의 (강수확률 %, 예상 강수 mm, 하늘) + 지명 — 우산 알림이 숫자로 판단할 때 씁니다."""
    label, data = _fetch(location, config)
    day = data.get("daily", {})
    prob = int((day.get("precipitation_probability_max") or [0])[0] or 0)
    rain = (day.get("precipitation_sum") or [0])[0] or 0
    sky = _sky((day.get("weather_code") or [None])[0])
    return prob, rain, sky, label


def forecast(location, config=None):
    """지금·오늘·내일 날씨를 사람이 읽을 문장으로. location이 비면 config 기본 지역."""
    label, data = _fetch(location, config)
    cur, day = data.get("current", {}), data.get("daily", {})
    t_now = cur.get("temperature_2m")
    t_feel = cur.get("apparent_temperature")
    sky_now = _sky(cur.get("weather_code"))

    def daily(i):
        return {
            "sky": _sky((day.get("weather_code") or [None, None])[i]),
            "lo": (day.get("temperature_2m_min") or [None, None])[i],
            "hi": (day.get("temperature_2m_max") or [None, None])[i],
            "prob": int((day.get("precipitation_probability_max") or [0, 0])[i] or 0),
            "rain": (day.get("precipitation_sum") or [0, 0])[i] or 0,
        }

    today, tomorrow = daily(0), daily(1)
    lines = [
        f"{label} 날씨 — 지금 {t_now}℃ (체감 {t_feel}℃), {sky_now}",
        f"오늘: {today['lo']}~{today['hi']}℃ · 강수확률 {today['prob']}%"
        + (f" · 예상 강수 {today['rain']}mm" if today['rain'] else "") + f" · {today['sky']}",
        f"내일: {tomorrow['lo']}~{tomorrow['hi']}℃ · 강수확률 {tomorrow['prob']}% · {tomorrow['sky']}",
        _umbrella(today["prob"], today["rain"]),
    ]
    return "\n".join(lines)


def brief_line(config):
    """아침 브리핑용 한 덩어리. 실패해도 브리핑 전체를 죽이지 않게 문자열로만 돌려줍니다."""
    try:
        return forecast("", config)
    except Exception as e:
        return f"(날씨를 가져오지 못했습니다: {type(e).__name__})"
