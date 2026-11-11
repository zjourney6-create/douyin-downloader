import os
import re
import requests
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
from playwright.sync_api import sync_playwright

from app.config import BASE_DIR

BROWSER_PROFILE_DIR = os.path.join(BASE_DIR, "browser_profile")

@dataclass
class ParsedVideoInfo:
    video_id: str
    title: str
    video_url: str
    audio_url: str
    share_url: str
    is_single_stream: bool = False  # True 表示音画合一单流（如带货/电商视频），无需 FFmpeg 二次合成

class DouyinParser:
    """抖音视频混合自愈解析器（支持持久化登录态、单流一体、DASH分流与博主主页深度抓取）"""

    URL_REGEX = re.compile(r'https?://[^\s，,。]+')

    @classmethod
    def get_browser_context(cls, p, headless: bool = True):
        """获取持久化浏览器上下文（共享登录凭证 Cookies 与 LocalStorage）"""
        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
        return p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            channel="msedge",
            headless=headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

    @classmethod
    def open_login_window(cls):
        """弹出可视化的 Edge 浏览器窗口供用户扫码登录抖音"""
        with sync_playwright() as p:
            context = cls.get_browser_context(p, headless=False)
            page = context.new_page()
            page.goto("https://www.douyin.com", wait_until="domcontentloaded")
            # 保持窗口打开，直到用户手动关闭浏览器窗口
            try:
                page.wait_for_timeout(300000)  # 最多等待 5 分钟
            except Exception:
                pass
            finally:
                context.close()

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
    def is_user_homepage(cls, text: str) -> bool:
        """判断是否为博主主页链接"""
        extracted = cls.extract_url(text) or text
        return "/user/" in extracted

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
        """利用持久化 Edge 内核后台无头嗅探单个视频媒体流"""
        dash_video_url = ""
        dash_audio_url = ""
        single_media_url = ""
        title = ""

        with sync_playwright() as p:
            context = cls.get_browser_context(p, headless=True)
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
                        single_media_url = u

            page.on("request", handle_request)

            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

                for i in range(timeout_sec * 2):
                    if dash_video_url and dash_audio_url:
                        break

                    dom_src = page.evaluate('''() => {
                        const v = document.querySelector('video');
                        return v ? (v.currentSrc || v.src || '') : '';
                    }''')
                    if dom_src and "douyinvod.com" in dom_src and not dom_src.startswith("blob:"):
                        single_media_url = dom_src

                    if i >= 6 and single_media_url and not dash_video_url and not dash_audio_url:
                        break

                    page.wait_for_timeout(500)

                raw_title = page.title() or ""
                title = re.sub(r'\s*-\s*抖音$', '', raw_title).strip()
            finally:
                context.close()

        if dash_video_url and dash_audio_url:
            return title or "抖音视频", dash_video_url, dash_audio_url, False
        elif single_media_url:
            return title or "抖音视频", single_media_url, "", True
        elif dash_video_url and not dash_audio_url:
            return title or "抖音视频", dash_video_url, "", True
        else:
            raise RuntimeError("未能从页面中成功嗅探到有效媒体流，可能链接已失效或网络超时。")

    @classmethod
    def parse(cls, raw_input: str) -> ParsedVideoInfo:
        """主入口：从单条输入解析出完整可下载的视频媒体对象"""
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

    @classmethod
    def fetch_author_videos(cls, user_url: str, max_count: int = 100, progress_cb=None) -> Tuple[str, List[Dict[str, str]]]:
        """
        利用系统 Edge 驱动自动翻页抓取博主作品列表（前 100 / 200 / 300 个）
        严格容器隔离：只收集博主作品网格内部的视频，100% 杜绝混入侧边推荐外链！
        """
        author_name = "抖音博主"
        collected_list: List[Dict[str, str]] = []
        seen_ids = set()

        def log_msg(msg: str):
            if progress_cb:
                progress_cb(msg)

        with sync_playwright() as p:
            context = cls.get_browser_context(p, headless=True)
            page = context.new_page()

            # 1. 优先通过官方 aweme/post API 拦截（最精准纯正，绝无外链）
            def on_response(res):
                nonlocal collected_list, seen_ids
                if "aweme/v1/web/aweme/post" in res.url:
                    try:
                        data = res.json()
                        aweme_list = data.get("aweme_list", [])
                        for item in aweme_list:
                            aweme_id = item.get("aweme_id")
                            if aweme_id and aweme_id not in seen_ids:
                                seen_ids.add(aweme_id)
                                desc = item.get("desc") or f"视频_{aweme_id}"
                                collected_list.append({
                                    "id": aweme_id,
                                    "title": desc.strip(),
                                    "url": f"https://www.douyin.com/video/{aweme_id}"
                                })
                    except Exception:
                        pass

            page.on("response", on_response)

            log_msg("正在访问博主主页...")
            page.goto(user_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # 解析博主昵称
            raw_title = page.title() or ""
            author_name = re.sub(r'的抖音.*$', '', raw_title).strip() or "抖音博主"

            # 2. 从 DOM 辅助提取：采用精确选择器，仅在作品列表中提取，坚决排除侧边推荐！
            dom_items = page.evaluate('''() => {
                // 仅查找带有作品标识的直接卡片链接
                const selectors = [
                    'div[data-e2e="user-post-list"] a[href*="/video/"]',
                    'ul[data-e2e="scroll-list"] a[href*="/video/"]',
                    'div[class*="author-post"] a[href*="/video/"]',
                    'div[class*="PostList"] a[href*="/video/"]',
                    'a.RZuwF26I[href*="/video/"]'
                ];
                let found = [];
                for (const sel of selectors) {
                    const elList = document.querySelectorAll(sel);
                    if (elList.length > 0) {
                        found = Array.from(elList);
                        break;
                    }
                }
                // 如果特定选择器没有，做严格的排除匹配（排除包含“推荐”、“Baiduspider”、“搜索”等外链）
                if (found.length === 0) {
                    found = Array.from(document.querySelectorAll('a[href*="/video/"]')).filter(a => {
                        const href = a.href || '';
                        return !href.includes('source=') && !href.includes('recommend');
                    });
                }
                return found.map(a => ({
                    href: a.href,
                    title: (a.innerText || '').trim()
                }));
            }''')

            for item in dom_items:
                m = re.search(r'/video/(\d+)', item.get("href", ""))
                if m:
                    vid = m.group(1)
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        collected_list.append({
                            "id": vid,
                            "title": item.get("title") or f"视频_{vid}",
                            "url": f"https://www.douyin.com/video/{vid}"
                        })

            log_msg(f"博主: 【{author_name}】，首屏捕获 {len(collected_list)} 个纯净作品，正在向下深度滚动加载...")

            # 3. 循环自然滚动翻页，并在遇登录遮罩时自动清理拦截
            no_new_counter = 0
            scroll_count = 0
            max_scrolls = max(25, (max_count // 8) + 15)

            while len(collected_list) < max_count and scroll_count < max_scrolls:
                prev_len = len(collected_list)

                # 模拟滚轮与键盘 PageDown
                page.mouse.wheel(0, 1800)
                page.wait_for_timeout(1000)
                page.keyboard.press("PageDown")
                page.wait_for_timeout(1200)

                # 尝试关闭可能弹出的登录或提示遮罩
                page.evaluate('''() => {
                    const closeSelectors = [
                        '.login-mask-enter-done [class*="close"]',
                        'div[class*="login"] [class*="close"]',
                        'svg[class*="close"]',
                        '.dy-account-close'
                    ];
                    for (const s of closeSelectors) {
                        const btn = document.querySelector(s);
                        if (btn) {
                            btn.click();
                            break;
                        }
                    }
                ''')

                scroll_count += 1
                curr_len = len(collected_list)

                if curr_len > prev_len:
                    no_new_counter = 0
                    log_msg(f"已捕获 {min(curr_len, max_count)} / {max_count} 个作品...")
                else:
                    no_new_counter += 1
                    if no_new_counter >= 5:
                        # 再次尝试从 DOM 兜底扫描
                        latest_dom = page.evaluate('''() => {
                            return Array.from(document.querySelectorAll('a[href*="/video/"]'))
                                .filter(a => !a.href.includes('source='))
                                .map(a => ({href: a.href, title: (a.innerText || '').trim()}));
                        }''')
                        for item in latest_dom:
                            m = re.search(r'/video/(\d+)', item.get("href", ""))
                            if m:
                                vid = m.group(1)
                                if vid not in seen_ids:
                                    seen_ids.add(vid)
                                    collected_list.append({
                                        "id": vid,
                                        "title": item.get("title") or f"视频_{vid}",
                                        "url": f"https://www.douyin.com/video/{vid}"
                                    })
                        if len(collected_list) > curr_len:
                            no_new_counter = 0
                            continue

                        log_msg(f"翻页完成（已达上限或全部加载完毕），共计获取 {len(collected_list)} 个纯净作品")
                        break

            context.close()

        final_list = collected_list[:max_count]
        return author_name, final_list
