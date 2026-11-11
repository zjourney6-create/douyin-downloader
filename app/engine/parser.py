import re
import requests
from dataclasses import dataclass
from typing import Optional, Tuple
from playwright.sync_api import sync_playwright

@dataclass
class ParsedVideoInfo:
    video_id: str
    title: str
    video_url: str
    audio_url: str
    share_url: str

class DouyinParser:
    """抖音视频混合自愈解析器"""

    URL_REGEX = re.compile(r'https?://[^\s，,。]+')

    @classmethod
    def extract_url(cls, text: str) -> Optional[str]:
        """从用户粘贴的各种杂乱文本（含抖音口令）中提取真实 URL"""
        if not text:
            return None
        matches = cls.URL_REGEX.findall(text.strip())
        for match in matches:
            if "douyin.com" in match:
                return match
        return None

    @classmethod
    def resolve_real_url(cls, raw_url: str) -> Tuple[str, str]:
        """解析真实长链接与 video_id"""
        s = requests.Session()
        s.trust_env = False
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = s.get(raw_url, headers=headers, allow_redirects=True, timeout=10)
        final_url = resp.url

        # 从最终长链接或 modal_id 提取 video_id
        video_id = ""
        # 模式1: /video/7123456789...
        m1 = re.search(r'/video/(\d+)', final_url)
        if m1:
            video_id = m1.group(1)
        else:
            # 模式2: modal_id=7123456789...
            m2 = re.search(r'modal_id=(\d+)', final_url)
            if m2:
                video_id = m2.group(1)

        normalized_url = f"https://www.douyin.com/video/{video_id}" if video_id else final_url
        return normalized_url, video_id

    @classmethod
    def sniff_streams_via_edge(cls, target_url: str, timeout_sec: int = 25) -> Tuple[str, str, str]:
        """
        利用系统 Edge 内核后台无头嗅探获取：
        1. 视频标题
        2. 官方原始 H.265 (media-video) CDN 直链
        3. 官方原始 AAC (media-audio) CDN 直链
        """
        video_url = ""
        audio_url = ""
        title = ""

        with sync_playwright() as p:
            # 使用 Windows 预装的 Edge 浏览器内核
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            def handle_request(req):
                nonlocal video_url, audio_url
                u = req.url
                if "douyinvod.com" in u:
                    if "media-video" in u and not video_url:
                        video_url = u
                    elif "media-audio" in u and not audio_url:
                        audio_url = u

            page.on("request", handle_request)

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
                # 轮询等待音画两条流均被捕获
                for _ in range(timeout_sec * 2):
                    if video_url and audio_url:
                        break
                    page.wait_for_timeout(500)

                raw_title = page.title() or ""
                # 清理标题末尾的 " - 抖音" 后缀
                title = re.sub(r'\s*-\s*抖音$', '', raw_title).strip()
            finally:
                browser.close()

        if not video_url or not audio_url:
            raise RuntimeError("未能从页面中成功嗅探到完整音视频流，可能网络超时或链接已失效。")

        return title or "抖音视频", video_url, audio_url

    @classmethod
    def parse(cls, raw_input: str) -> ParsedVideoInfo:
        """主入口：从输入解析出完整可下载的视频媒体对象"""
        extracted = cls.extract_url(raw_input)
        if not extracted:
            raise ValueError("未检测到有效的抖音链接，请确认输入的链接格式。")

        real_url, video_id = cls.resolve_real_url(extracted)
        title, video_url, audio_url = cls.sniff_streams_via_edge(real_url)

        return ParsedVideoInfo(
            video_id=video_id,
            title=title,
            video_url=video_url,
            audio_url=audio_url,
            share_url=real_url
        )
