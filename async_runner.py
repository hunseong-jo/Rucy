# -*- coding: utf-8 -*-
"""
비동기 및 병렬 실행 엔진 (async_runner.py)
"""
import asyncio
import html
import re
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _sync_fetch_url(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            page = resp.read(600000).decode("utf-8", errors="replace")
        page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        return re.sub(r"\s+", " ", text).strip()[:6000]
    except Exception as e:
        return f"요청 실패 ({type(e).__name__}): {e}"


async def async_fetch_url(url, timeout=15):
    """단일 URL 비동기 가져오기"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_fetch_url, url, timeout)


async def async_fetch_urls(urls, timeout=15):
    """여러 URL 병렬 스크래핑"""
    tasks = [async_fetch_url(u, timeout) for u in urls]
    return await asyncio.gather(*tasks)


async def async_run_tools(tool_calls):
    """
    여러 도구를 병렬로 실행합니다.
    tool_calls: [(func, args_dict), ...]
    """
    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, fn, args) for fn, args in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)


def run_async(coro):
    """동기 코드에서 비동기 코루틴을 쉽게 실행할 수 있도록 지원하는 헬퍼"""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
