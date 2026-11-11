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
    is_single_stream: bool = False  # True 表示音画合一单流（如带货/电商视频），无需 FFmpeg 二次合成

class DouyinParser:
    """抖音视频混合自愈解析器（支持普通分流视频与带货/短视频单流一体视频）"""

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
        m1 = re.search(r'/video/(\d+)', final_url)
        if m1:
            video_id = m1.group(1)
        else:
            m2 = re.search(r'modal_id=(\d+)', final_url)
            if m2:
                video_id = m2.group(1)

        normalized_url = f"https://www.douyin.com/video/{video_id}" if video_id else final_url
        return normalized_url, video_id

    @classmethod
    def sniff_streams_via_edge(cls, target_url: str, timeout_sec: int = 25) -> Tuple[str, str, str, bool]:
        """
        利用系统 Edge 内核后台无头嗅探获取：
        1. 视频标题
        2. 视频流直链 (video_url)
        3. 音频流直链 (audio_url，若为单流则为空字符串)
        4. is_single_stream (是否为自带音频的完整MP4单流)
        """
        dash_video_url = ""
        dash_audio_url = ""
        single_media_url = ""
        title = ""

        with sync_playwright() as p:
            browser = p.chromium.launch(channel="msedge", headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            def handle_request(req):
                nonlocal dash_video_url, dash_audio_url, single_media_url
                u = req.url
                if "douyinvod.com" in u:
                    if "media-video" in u and not dash_video_url:
                        dash_video_url = u
                    elif "media-audio" in u and not dash_audio_url:
                        dash_audio_url = u
                    elif not single_media_url and ("media-video" not in u and "media-audio" not in u):
                        # 单流一体视频特征（如带货视频、普通 MP4 推流）
                        single_media_url = u

            page.on("request", handle_request)

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

                # 轮询等待媒体捕获
                for i in range(timeout_sec * 2):
                    # 模式A：已捕获到分流的两条轨
                    if dash_video_url and dash_audio_url:
                        break

                    # 检查 DOM 中的 video 标签 src / currentSrc
                    dom_src = page.evaluate('''() => {
                        const v = document.querySelector('video');
                        return v ? (v.currentSrc || v.src || '') : '';
                    }''')
                    if dom_src and "douyinvod.com" in dom_src and not dom_src.startswith("blob:"):
                        single_media_url = dom_src

                    # 模式B：等待 3 秒以上且已经捕获到单流，但页面未发起 DASH 分流请求
                    if i >= 6 and single_media_url and not dash_video_url and not dash_audio_url:
                        break

                    page.wait_for_timeout(500)

                raw_title = page.title() or ""
                title = re.sub(r'\s*-\s*抖音$', '', raw_title).strip()
            finally:
                browser.close()

        # 决策判断分流还是单流
        if dash_video_url and dash_audio_url:
            return title or "抖音视频", dash_video_url, dash_audio_url, False
        elif single_media_url:
            return title or "抖音视频", single_media_url, "", True
        elif dash_video_url and not dash_audio_url:
            # 仅捕获到视频轨且为普通 MP4
            return title or "抖音视频", dash_video_url, "", True
        else:
            raise RuntimeError("未能从页面中成功嗅探到有效媒体流，可能链接已失效或网络超时。")

    @classmethod
    def parse(cls, raw_input: str) -> ParsedVideoInfo:
        """主入口：从输入解析出完整可下载的视频媒体对象"""
        extracted = cls.extract_url(raw_input)
        if not extracted:
            raise ValueError("未检测到有效的抖音链接，请确认输入的链接格式。")

        real_url, video_id = cls.resolve_real_url(extracted)
        title, video_url, audio_url, is_single_stream = cls.sniff_streams_via_edge(real_url)

        return ParsedVideoInfo(
            video_id=video_id,
            title=title,
            video_url=video_url,
            audio_url=audio_url,
            share_url=real_url,
            is_single_stream=is_single_stream
        )
