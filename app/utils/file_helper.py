import re
import os

def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """清理文件名中的非法字符，避免在 Windows 磁盘写入失败"""
    # 替换 Windows 文件名禁用字符: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/*?:"<>|]', '_', filename)
    # 去除首尾空格和换行
    cleaned = cleaned.strip()
    # 避免名字过长
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].strip()
    return cleaned or "douyin_video"

def format_bytes(size_bytes: int) -> str:
    """格式化文件大小为易读格式 (B, KB, MB, GB)"""
    if not size_bytes or size_bytes <= 0:
        return "0 MB"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
