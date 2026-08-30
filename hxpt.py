#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# cron: 13 9 * * *
# new Env("HXPT 好学签到")

"""
HXPT / 好学 青龙独立签到脚本

环境变量：
  HXPT_COOKIE    必填，好学完整 Cookie
  HXPT_BASE_URL  可选，默认 https://www.hxpt.org

依赖：
  requests

功能：
  - 检查 Cookie 登录状态
  - 读取头像下拉区域 cute-top-profile__summary / __stats
  - 尝试解析用户名、火花、上传量、下载量、分享率、做种积分等
  - 根据 attendance.php 链接的 is-attended 类判断今日签到
  - 未签到时访问 /attendance.php 完成签到
  - 签到后重新读取首页隐藏统计区
  - 遇到 2FA、验证码、人机验证或风控时停止，不尝试绕过

说明：
  好学的新主题把账户数据放在头像下拉区域。
  CSS 隐藏不会影响 requests 解析；只有 JS 后加载的数据才可能需要后续适配。
"""

import os
import re
from html import unescape
from html.parser import HTMLParser
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse

import requests


COOKIE = os.getenv("HXPT_COOKIE", "").strip()
BASE_URL = os.getenv("HXPT_BASE_URL", "https://www.hxpt.org").strip().rstrip("/")

TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def clean_text(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def cookie_dict(cookie: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def allowed_host(hostname: str) -> bool:
    host = (hostname or "").lower().strip(".")
    base_host = (urlparse(BASE_URL).hostname or "").lower().strip(".")
    if not base_host:
        return False
    return host == base_host or host.endswith("." + base_host)


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Connection": "keep-alive",
    })

    host = urlparse(BASE_URL).hostname or ""
    for key, value in cookie_dict(COOKIE).items():
        session.cookies.set(key, value, domain=host, path="/")

    return session


def safe_get(
    session: requests.Session,
    path: str,
    *,
    referer: Optional[str] = None,
) -> requests.Response:
    url = urljoin(BASE_URL + "/", path.lstrip("/"))

    resp = session.get(
        url,
        headers={"Referer": referer or (BASE_URL + "/")},
        timeout=TIMEOUT,
        allow_redirects=False,
    )

    redirects = 0
    while resp.status_code in (301, 302, 303, 307, 308):
        location = resp.headers.get("Location")
        if not location:
            break

        next_url = urljoin(resp.url, location)
        next_host = urlparse(next_url).hostname or ""

        if not allowed_host(next_host):
            raise RuntimeError(f"检测到外域跳转，已停止：{next_url}")

        redirects += 1
        if redirects > 5:
            raise RuntimeError("站内重定向次数过多")

        resp = session.get(
            next_url,
            headers={"Referer": resp.url},
            timeout=TIMEOUT,
            allow_redirects=False,
        )

    return resp


def detect_verification(text: str, final_url: str = "") -> Optional[str]:
    source = f"{final_url}\n{text or ''}"

    if re.search(r"take2fa\.php", final_url or "", flags=re.I):
        return "两步验证 / 2FA"

    if re.search(
        r"验证码|驗證碼|人机验证|人機驗證|机器人验证|機器人驗證|"
        r"captcha|geetest|turnstile|cloudflare challenge|cf-chl-|"
        r"just a moment|checking your browser|滑块验证|滑塊驗證",
        source,
        flags=re.I,
    ):
        return "验证码 / 人机验证 / 风控"

    return None


def page_is_login_page(html: str, final_url: str) -> bool:
    raw = html or ""
    text = clean_text(raw)

    if "login.php" in (final_url or "").lower():
        return True

    if re.search(
        r"请先登录|請先登錄|登录后才能访问|登錄後才能訪問|"
        r"you must be logged in|please log in",
        text,
        flags=re.I,
    ):
        return True

    if re.search(r"takelogin\.php", raw, flags=re.I):
        return True

    has_user = bool(re.search(
        r'<input[^>]+name=["\']username["\']',
        raw,
        flags=re.I,
    ))
    has_pass = bool(re.search(
        r'<input[^>]+(?:name=["\']password["\']|type=["\']password["\'])',
        raw,
        flags=re.I,
    ))
    return has_user and has_pass


def login_is_valid(html: str, final_url: str) -> bool:
    if page_is_login_page(html, final_url):
        return False

    return bool(re.search(
        r"logout\.php|usercp\.php|mybonus\.php|attendance\.php|"
        r"cute-top-profile|控制面板",
        html or "",
        flags=re.I,
    ))


class ClassTextExtractor(HTMLParser):
    """
    提取指定 class 元素及其所有子节点中的文本。
    可处理 div 内部多层嵌套，不依赖脆弱的正则闭合匹配。
    """

    def __init__(self, target_class: str):
        super().__init__(convert_charrefs=True)
        self.target_class = target_class
        self.depth = 0
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = (attrs_dict.get("class") or "").split()

        if self.active:
            self.depth += 1
            return

        if self.target_class in classes:
            self.active = True
            self.depth = 1

    def handle_endtag(self, tag):
        if not self.active:
            return

        self.depth -= 1
        if self.depth <= 0:
            self.active = False
            self.depth = 0

    def handle_data(self, data):
        if self.active and data:
            self.parts.append(data)

    def result(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def extract_class_text(html: str, class_name: str) -> str:
    parser = ClassTextExtractor(class_name)
    try:
        parser.feed(html or "")
    except Exception:
        return ""
    return parser.result()


def number_from_string(value: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "未获取"
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def parse_size(text: str, labels) -> Optional[str]:
    if not text:
        return None

    label_alt = "|".join(re.escape(x) for x in labels)
    m = re.search(
        rf"(?:{label_alt})\s*[:：]?\s*"
        rf"([0-9][0-9,.]*\s*[KMGTPE]?i?B)",
        text,
        flags=re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()

    return None


def parse_number(text: str, labels) -> Optional[float]:
    if not text:
        return None

    label_alt = "|".join(re.escape(x) for x in labels)
    m = re.search(
        rf"(?:{label_alt})\s*[:：]?\s*([0-9][0-9,.]*)",
        text,
        flags=re.I,
    )
    return number_from_string(m.group(1)) if m else None



def parse_hxpt_fire(html: str) -> Optional[float]:
    """
    好学首页头像下拉区已确认的真实结构：

      <font class="color_bonus">火花</font>
      [...]
      <a href="mybonusmine.php">我的火花</a>
      [...]
      101,391.3

    优先以 mybonusmine.php 为强锚点读取后续第一个数字，
    不扫描整页“火花”文本，避免误抓公告或其它统计值。
    """
    raw = html or ""

    patterns = [
        r'<a[^>]+href=["\'][^"\']*mybonusmine\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>'
        r'[\s\]\)】）:：&nbsp;]{0,160}'
        r'([0-9][0-9,.]*)',

        r'<a[^>]+href=["\'][^"\']*mybonusmine\.php[^"\']*["\'][^>]*>'
        r'[\s\S]*?</a>'
        r'([\s\S]{0,220}?)'
        r'([0-9][0-9,.]*)',
    ]

    for idx, pattern in enumerate(patterns):
        m = re.search(pattern, raw, flags=re.I)
        if not m:
            continue

        raw_num = m.group(1) if idx == 0 else m.group(2)
        value = number_from_string(raw_num)
        if value is not None:
            return value

    # 后备：仅截取 color_bonus + 火花 附近的小片段
    m = re.search(
        r'<font[^>]+class=["\'][^"\']*color_bonus[^"\']*["\'][^>]*>'
        r'\s*(?:火花)\s*</font>'
        r'([\s\S]{0,500}?)'
        r'(?=<font\b|</span>|</td>|$)',
        raw,
        flags=re.I,
    )
    if m:
        local = m.group(1)

        mm = re.search(
            r'mybonusmine\.php[\s\S]*?</a>[\s\S]{0,150}?([0-9][0-9,.]*)',
            local,
            flags=re.I,
        )
        if mm:
            return number_from_string(mm.group(1))

    return None


def parse_profile_stats(html: str) -> Dict[str, object]:
    """
    新主题主要数据藏在头像下拉菜单：
      cute-top-profile__summary
      cute-top-profile__stats

    两个区域合并后按明确标签解析。
    """
    summary = extract_class_text(html, "cute-top-profile__summary")
    stats = extract_class_text(html, "cute-top-profile__stats")
    combined = " ".join(x for x in [summary, stats] if x).strip()

    return {
        "raw": combined,
        "fire": parse_hxpt_fire(html),
        "uploaded": parse_size(combined, ["上传量", "上傳量", "Uploaded"]),
        "downloaded": parse_size(combined, ["下载量", "下載量", "Downloaded"]),
        "ratio": parse_number(combined, ["分享率", "Ratio"]),
        "seed_points": parse_number(
            combined,
            ["做种积分", "做種積分", "做种魔力", "Seed Points"],
        ),
        "makeup_cards": parse_number(combined, ["补签卡", "補簽卡"]),
    }


def parse_username(html: str) -> Optional[str]:
    summary = extract_class_text(html, "cute-top-profile__summary")
    profile = extract_class_text(html, "cute-top-profile")

    for text in [summary, profile]:
        if not text:
            continue

        # 常见“用户名 等级 / 上传 / 下载...”结构
        tokens = text.split()
        for token in tokens:
            if (
                1 <= len(token) <= 40
                and not re.search(
                    r"魔力|上传|下載|下载|分享率|控制面板|签到|補簽|补签|Ratio",
                    token,
                    flags=re.I,
                )
                and not re.fullmatch(r"[0-9.,]+", token)
            ):
                return token

    # NexusPHP 常规后备
    m = re.search(
        r'<a[^>]+href=["\'][^"\']*userdetails\.php\?id=\d+[^"\']*["\'][^>]*>'
        r'([\s\S]*?)</a>',
        html or "",
        flags=re.I,
    )
    return clean_text(m.group(1)) if m else None


def attendance_state(html: str) -> Dict[str, object]:
    """
    截图已确认：
      <a class="cute-top-profile__attendance-link is-attended"
         href="attendance.php"></a>

    is-attended => 今日已签到
    """
    raw = html or ""

    m = re.search(
        r'<a\b([^>]*href=["\'][^"\']*attendance\.php[^"\']*["\'][^>]*)>',
        raw,
        flags=re.I,
    )

    if not m:
        return {
            "found": False,
            "already": False,
        }

    attrs = m.group(1)
    already = bool(re.search(
        r'class=["\'][^"\']*\bis-attended\b[^"\']*["\']',
        attrs,
        flags=re.I,
    ))

    return {
        "found": True,
        "already": already,
    }


def parse_attendance_page(html: str) -> Dict[str, object]:
    text = clean_text(html)

    result: Dict[str, object] = {
        "success": False,
        "already": False,
        "reward": None,
        "message": "",
    }

    if re.search(
        r"签到成功|簽到成功|签到已得\s*[0-9,.]+|簽到已得\s*[0-9,.]+",
        text,
        flags=re.I,
    ):
        result["success"] = True

    if re.search(
        r"今天已经签到|今天已經簽到|今日已签到|今日已簽到|"
        r"已经签到过|已經簽到過|请勿重复签到|請勿重複簽到|"
        r"already signed",
        text,
        flags=re.I,
    ):
        result["success"] = True
        result["already"] = True

    reward_patterns = [
        r"签到已得\s*([0-9][0-9,.]*)",
        r"簽到已得\s*([0-9][0-9,.]*)",
        r"本次签到(?:获得|得到)?\s*([0-9][0-9,.]*)",
        r"本次簽到(?:獲得|得到)?\s*([0-9][0-9,.]*)",
        r"奖励\s*[:：]?\s*([0-9][0-9,.]*)",
    ]

    for pattern in reward_patterns:
        m = re.search(pattern, text, flags=re.I)
        if m:
            result["reward"] = number_from_string(m.group(1))
            result["success"] = True
            break

    # 保存简短站点返回
    if text:
        result["message"] = text[:300]

    return result


def print_stats(stats: Dict[str, object]) -> None:
    print(f"🔥 当前火花：{fmt_number(stats['fire'])}")
    print(f"⬆️ 上传量：{stats['uploaded'] or '未获取'}")
    print(f"⬇️ 下载量：{stats['downloaded'] or '未获取'}")

    if stats["ratio"] is not None:
        print(f"📈 分享率：{fmt_number(stats['ratio'])}")

    if stats["seed_points"] is not None:
        print(f"🌱 做种积分：{fmt_number(stats['seed_points'])}")

    if stats["makeup_cards"] is not None:
        print(f"🎫 补签卡：{fmt_number(stats['makeup_cards'])}")


def main() -> int:
    print("========== HXPT 好学 ==========\n")

    if not COOKIE:
        print("❌ 未配置环境变量 HXPT_COOKIE")
        return 1

    session = make_session()

    try:
        home_resp = safe_get(session, "/")
        home_resp.raise_for_status()
        home_html = home_resp.text or ""
    except Exception as e:
        print(f"❌ 无法访问好学首页：{e}")
        return 1

    verification = detect_verification(clean_text(home_html), home_resp.url)
    if verification:
        print(f"❌ 检测到{verification}")
        print("   脚本不会尝试绕过，请先人工处理。")
        return 1

    if not login_is_valid(home_html, home_resp.url):
        print("❌ 未能确认 Cookie 登录状态")
        print(f"   当前地址：{home_resp.url}")
        return 1

    username = parse_username(home_html) or "未获取"
    stats = parse_profile_stats(home_html)
    att = attendance_state(home_html)

    print("✅ Cookie 登录有效")
    print(f"👤 用户：{username}")
    print_stats(stats)

    if not stats["raw"]:
        print("⚠️ 首页 HTML 中未读取到头像隐藏统计区")
        print("   可能该区域由 JavaScript 后加载，签到功能仍可继续。")

    if att["found"] and att["already"]:
        print("📅 今日状态：已签到")
        print("⚠️ 今日已经签到，无需重复执行")
        print("\n执行完成 ✅")
        return 0

    if att["found"]:
        print("📅 今日状态：未签到")
    else:
        print("📅 今日状态：未签到或主题未返回明确状态")

    print("🎯 开始签到...")

    try:
        att_resp = safe_get(
            session,
            "/attendance.php",
            referer=BASE_URL + "/",
        )
        att_resp.raise_for_status()
        att_html = att_resp.text or ""
    except Exception as e:
        print(f"❌ 签到请求失败：{e}")
        return 1

    verification = detect_verification(clean_text(att_html), att_resp.url)
    if verification:
        print(f"❌ 签到页面触发{verification}")
        return 1

    if page_is_login_page(att_html, att_resp.url):
        print("❌ 签到页面提示登录失效")
        return 1

    parsed = parse_attendance_page(att_html)

    # 有些主题 attendance.php 会直接跳回首页，
    # 因此再根据返回 HTML 的 is-attended 类做一次确认。
    returned_att = attendance_state(att_html)
    if returned_att["found"] and returned_att["already"]:
        parsed["success"] = True

    if not parsed["success"]:
        print("❌ 未能确认签到成功")
        if parsed["message"]:
            print(f"   页面返回：{parsed['message']}")
        return 1

    print("⚠️ 今日已经签到，无需重复执行" if parsed["already"] else "✅ 签到成功")

    if parsed["reward"] is not None:
        print(f"🎁 今日签到：{fmt_number(parsed['reward'])} 火花")

    # 签到后重新读取头像统计区
    try:
        after_resp = safe_get(session, "/")
        after_html = after_resp.text or ""
        after_stats = parse_profile_stats(after_html)

        if after_stats["raw"]:
            print("\n📊 签到后账户数据")
            print_stats(after_stats)
    except Exception:
        pass

    print("\n执行完成 ✅")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n任务已中止")
        raise SystemExit(130)
    except Exception as e:
        print(f"\n❌ 脚本异常：{type(e).__name__}: {e}")
        raise SystemExit(1)
