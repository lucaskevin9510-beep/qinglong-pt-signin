#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
百度贴吧 APP 自动回帖脚本（青龙）

默认配置：
- pt吧公开水楼
- fid=352902
- tid=9739080249
- 回复“绑定”
- 每次连续回复 4 条
- 每条间隔 1 秒

已于 2026-09-01 使用贴吧 iOS APP 22.9.1.0 协议实际验证。
所有账号凭据均从青龙环境变量读取，仓库不保存真实 BDUSS 或唯一设备 ID。
"""

import hashlib
import json
import os
import random
import sys
import time
from http.cookies import SimpleCookie
from typing import Dict, Optional

import requests

DEFAULT_KW = "pt"
DEFAULT_FID = "352902"
DEFAULT_TID = "9739080249"
DEFAULT_CONTENT = "绑定"

APP_VERSION = os.getenv("TIEBA_APP_VERSION", "22.9.1.0").strip() or "22.9.1.0"
CLIENT_TYPE = "1"
OS_VERSION = os.getenv("TIEBA_OS_VERSION", "18.7").strip() or "18.7"

APP_LOGIN_URL = "https://tiebac.baidu.com/c/s/login"
POST_URL = os.getenv(
    "TIEBA_POST_URL",
    "https://tiebac.baidu.com/c/c/post/add",
).strip()

KW = os.getenv("TIEBA_KW", DEFAULT_KW).strip() or DEFAULT_KW
FID = os.getenv("TIEBA_FID", DEFAULT_FID).strip() or DEFAULT_FID
TID = os.getenv("TIEBA_TID", DEFAULT_TID).strip() or DEFAULT_TID
CONTENT = os.getenv("TIEBA_CONTENT", DEFAULT_CONTENT)

POST_COUNT = int(os.getenv("TIEBA_POST_COUNT", "4") or "4")
POST_INTERVAL_MIN = float(os.getenv("TIEBA_POST_INTERVAL_MIN", "1") or "1")
POST_INTERVAL_MAX = float(os.getenv("TIEBA_POST_INTERVAL_MAX", "1") or "1")
DELAY_MAX = int(os.getenv("TIEBA_DELAY_MAX", "0") or "0")
DRY_RUN = os.getenv("TIEBA_DRY_RUN", "0").strip() == "1"

SIGN_SUFFIX = "tiebaclient!!!"
TIMEOUT = (8, 20)

APP_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    f"tieba/{APP_VERSION} skin/default"
)


class TiebaError(RuntimeError):
    pass


def parse_cookie_value(cookie_text: str, key: str) -> str:
    if not cookie_text:
        return ""

    cookie = SimpleCookie()
    try:
        cookie.load(cookie_text)
        morsel = cookie.get(key)
        if morsel:
            return morsel.value
    except Exception:
        pass

    for part in cookie_text.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name.strip() == key:
            return value.strip()
    return ""


def get_bduss() -> str:
    bduss = os.getenv("TIEBA_BDUSS", "").strip()
    if bduss:
        return bduss

    cookie_text = os.getenv("TIEBA_COOKIE", "").strip()
    bduss = parse_cookie_value(cookie_text, "BDUSS")
    if bduss:
        return bduss

    raise TiebaError(
        "缺少登录凭据：请设置 TIEBA_BDUSS，"
        "或设置包含 BDUSS 的 TIEBA_COOKIE。"
    )


def masked(value: str, left: int = 4, right: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= left + right:
        return "*" * len(value)
    return f"{value[:left]}...{value[-right:]}"


def app_sign(params: Dict[str, str]) -> str:
    raw = "".join(
        f"{key}={params[key]}"
        for key in sorted(params)
        if key != "sign"
    )
    return hashlib.md5(
        (raw + SIGN_SUFFIX).encode("utf-8")
    ).hexdigest().upper()


def optional_app_params() -> Dict[str, str]:
    """未来如接口要求更完整设备参数，可通过环境变量补充。"""
    mapping = {
        "_client_id": "TIEBA_CLIENT_ID",
        "cuid": "TIEBA_CUID",
        "idfv": "TIEBA_IDFV",
        "z_id": "TIEBA_Z_ID",
        "stoken": "TIEBA_STOKEN",
    }
    result: Dict[str, str] = {}
    for param_name, env_name in mapping.items():
        value = os.getenv(env_name, "").strip()
        if value:
            result[param_name] = value
    return result


def make_session(bduss: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": APP_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Connection": "keep-alive",
        }
    )
    session.cookies.set("BDUSS", bduss, domain=".baidu.com", path="/")
    return session


def app_login(session: requests.Session, bduss: str):
    payload: Dict[str, str] = {
        "BDUSS": bduss,
        "bdusstoken": bduss,
        "_client_type": CLIENT_TYPE,
        "_client_version": APP_VERSION,
        "_os_version": OS_VERSION,
        "from": "appstore",
        "subapp_type": "tieba",
        "net_type": "1",
        "first_login": "1",
        "_timestamp": str(int(time.time() * 1000)),
    }
    payload.update(optional_app_params())
    payload["sign"] = app_sign(payload)

    resp = session.post(
        APP_LOGIN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
        allow_redirects=False,
    )

    if 300 <= resp.status_code < 400:
        raise TiebaError(
            f"APP 登录接口发生重定向：HTTP {resp.status_code} -> "
            f"{resp.headers.get('Location', '')}"
        )
    if resp.status_code != 200:
        raise TiebaError(
            f"APP 登录校验失败：HTTP {resp.status_code}，"
            f"响应：{resp.text[:300]}"
        )

    try:
        data = resp.json()
    except Exception as exc:
        raise TiebaError(
            f"APP 登录接口返回非 JSON：{resp.text[:500]}"
        ) from exc

    error_code = str(data.get("error_code", data.get("errno", "")))
    error_msg = str(data.get("error_msg", data.get("errmsg", "")) or "").strip()
    if error_code not in {"0", ""}:
        raise TiebaError(
            f"APP 登录失败：error_code={error_code or 'unknown'}"
            + (f"，error_msg={error_msg}" if error_msg else "")
        )

    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    anti = data.get("anti") if isinstance(data.get("anti"), dict) else {}

    username = str(user.get("name") or user.get("user_name") or "").strip()
    tbs = str(anti.get("tbs") or data.get("tbs") or "").strip()
    if not tbs:
        raise TiebaError("APP 登录成功，但响应中没有 anti.tbs。")

    return tbs, username


def build_post_payload(bduss: str, tbs: str) -> Dict[str, str]:
    payload: Dict[str, str] = {
        "BDUSS": bduss,
        "_client_type": CLIENT_TYPE,
        "_client_version": APP_VERSION,
        "_os_version": OS_VERSION,
        "anonymous": "0",
        "content": CONTENT,
        "fid": FID,
        "from": "tieba",
        "kw": KW,
        "net_type": "1",
        "tbs": tbs,
        "tid": TID,
        "title": "",
    }
    payload.update(optional_app_params())
    payload["sign"] = app_sign(payload)
    return payload


def extract_post_id(data: dict) -> Optional[str]:
    candidates = [data.get("post_id"), data.get("pid")]
    nested = data.get("data")
    if isinstance(nested, dict):
        candidates.extend([nested.get("post_id"), nested.get("pid")])
    for item in candidates:
        if item not in (None, ""):
            return str(item)
    return None


def post_once(session: requests.Session, payload: Dict[str, str]) -> dict:
    resp = session.post(
        POST_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=TIMEOUT,
        allow_redirects=False,
    )

    if 300 <= resp.status_code < 400:
        raise TiebaError(
            f"发布请求发生重定向：HTTP {resp.status_code} -> "
            f"{resp.headers.get('Location', '')}"
        )
    if resp.status_code != 200:
        raise TiebaError(
            f"发布失败：HTTP {resp.status_code}，响应：{resp.text[:300]}"
        )

    try:
        return resp.json()
    except Exception as exc:
        raise TiebaError(
            f"发布接口返回非 JSON：{resp.text[:500]}"
        ) from exc


def main() -> int:
    print("========== 百度贴吧 APP 自动回帖 ==========")
    print(f"📱 APP 模式：Tieba iOS {APP_VERSION}")
    print(f"🌐 发布接口：{POST_URL}")
    print(f"📌 吧名：{KW}吧")
    print(f"🆔 fid：{FID}")
    print(f"🧵 tid：{TID}")
    print(f"💬 本次回复：{CONTENT}")
    print(f"🔢 本次连续发布：{POST_COUNT} 条")

    if POST_COUNT < 1:
        print("❌ TIEBA_POST_COUNT 必须 >= 1")
        return 2

    try:
        bduss = get_bduss()
    except TiebaError as exc:
        print(f"❌ {exc}")
        return 2

    print(f"🔐 BDUSS：{masked(bduss)}")
    session = make_session(bduss)

    try:
        tbs, username = app_login(session, bduss)
    except TiebaError as exc:
        print(f"❌ 登录校验失败：{exc}")
        return 3

    print("✅ APP 登录校验成功")
    if username:
        print(f"👤 用户：{username}")
    print(f"🧩 TBS：{masked(tbs)}")

    if DELAY_MAX > 0:
        delay = random.randint(0, DELAY_MAX)
        print(f"⏳ 随机等待 {delay} 秒后发布...")
        time.sleep(delay)

    preview_payload = build_post_payload(bduss, tbs)
    if DRY_RUN:
        print("🧪 DRY RUN：未真正发送发布请求")
        print(
            json.dumps(
                {
                    k: masked(v) if k in {"BDUSS", "stoken"} else v
                    for k, v in preview_payload.items()
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    interval_min = max(0.0, min(POST_INTERVAL_MIN, POST_INTERVAL_MAX))
    interval_max = max(0.0, max(POST_INTERVAL_MIN, POST_INTERVAL_MAX))

    success_count = 0
    failed_count = 0
    post_ids = []

    print(f"🚀 开始连续发布 {POST_COUNT} 条“{CONTENT}”...")

    for i in range(1, POST_COUNT + 1):
        print(f"\n[{i}/{POST_COUNT}] 正在发布“{CONTENT}”...")
        payload = build_post_payload(bduss, tbs)

        try:
            data = post_once(session, payload)
        except TiebaError as exc:
            failed_count += 1
            print(f"❌ 第 {i} 条请求失败：{exc}")
        else:
            error_code = str(data.get("error_code", data.get("errno", "")))
            error_msg = str(data.get("error_msg", data.get("errmsg", "")) or "").strip()

            if error_code in {"0", ""}:
                success_count += 1
                post_id = extract_post_id(data)
                if post_id:
                    post_ids.append(post_id)
                    print(f"✅ 第 {i} 条发布成功，post_id：{post_id}")
                else:
                    print(f"✅ 第 {i} 条发布成功")
            else:
                failed_count += 1
                print(f"❌ 第 {i} 条贴吧返回失败：error_code={error_code or 'unknown'}")
                if error_msg:
                    print(f"📝 error_msg：{error_msg}")

                lowered = error_msg.lower()
                if (
                    "验证码" in error_msg
                    or "验证" in error_msg
                    or "vcode" in lowered
                    or "风控" in error_msg
                ):
                    print("🛡️ 检测到验证/风控，本次停止继续发布。")
                    break

        if i < POST_COUNT:
            wait = random.uniform(interval_min, interval_max)
            print(f"⏳ {wait:.1f} 秒后发布下一条...")
            time.sleep(wait)

    print("\n========== 发布汇总 ==========")
    print(f"✅ 成功：{success_count}/{POST_COUNT}")
    print(f"❌ 失败：{failed_count}")
    if post_ids:
        print("🧱 post_id：")
        for pid in post_ids:
            print(f"   - {pid}")
    print(f"🔗 帖子：https://tieba.baidu.com/p/{TID}")
    print("========== 任务结束 ==========")

    return 0 if success_count == POST_COUNT else 5


if __name__ == "__main__":
    sys.exit(main())
