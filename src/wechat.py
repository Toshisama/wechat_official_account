"""微信测试号 API 封装：access_token 获取 + 客服消息推送（模板消息兜底）。"""
from __future__ import annotations

import time

import requests

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
CUSTOM_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/custom/send"
TEMPLATE_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/template/send"

# 客服消息文本上限（字节），超限会被微信拒绝
TEXT_MAX_BYTES = 2048

# 过期时间留 60s 余量，单次运行只需一次 token，内存缓存足够
_token_cache: dict[str, tuple[str, float]] = {}


def get_access_token(app_id: str, app_secret: str, force: bool = False) -> str:
    """获取 access_token（7200s 有效），进程内缓存。"""
    cached = _token_cache.get(app_id)
    if cached and not force and cached[1] > time.time() + 60:
        return cached[0]
    resp = requests.get(
        TOKEN_URL,
        params={
            "grant_type": "client_credential",
            "appid": app_id,
            "secret": app_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"获取 access_token 失败: {data}")
    _token_cache[app_id] = (data["access_token"], time.time() + data.get("expires_in", 7200))
    return data["access_token"]


def _post(url: str, token: str, payload: dict) -> dict:
    resp = requests.post(url, params={"access_token": token}, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_custom_text(token: str, openid: str, content: str) -> dict:
    """客服消息推送文本（测试号主通道）。返回微信响应。"""
    return _post(
        CUSTOM_SEND_URL,
        token,
        {"touser": openid, "msgtype": "text", "text": {"content": content}},
    )


def send_template_text(token: str, openid: str, template_id: str, content: str) -> dict:
    """模板消息兜底通道：内容过长时截断为摘要（模板字段有字数限制）。"""
    summary = content if len(content.encode("utf-8")) <= 200 else content[:60] + "…"
    payload = {
        "touser": openid,
        "template_id": template_id,
        "data": {"content": {"value": summary}},
    }
    return _post(TEMPLATE_SEND_URL, token, payload)
