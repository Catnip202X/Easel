#!/usr/bin/env python3
"""浏览器启动策略（各 Playwright 脚本共用）。

为什么：Playwright 自带的 Chromium 落后于 Chrome 稳定版（1.64.1 带的是 156.0.8078.4，
早于修复 CVE-2026-118306 的 156.0.8078.73），而且 Playwright 默认关闭 Chromium 沙箱。
策略：默认驱动本机 Google Chrome（channel="chrome"，随 Chrome 自动更新），并打开 Chromium 沙箱。

环境变量：
  EASEL_BROWSER_CHANNEL   chrome（默认）| chromium（回退到 Playwright 自带内核）| msedge …
  EASEL_CHROMIUM_SANDBOX  1（默认）| 0 —— 容器里以 root 运行时 Chrome 拒绝开沙箱，须设 0
                          （未设置时 root 自动关、其余自动开）

用法：
  kwargs = browser_launch.launch_kwargs(LAUNCH_ARGS, headless=True, locale="zh-CN")
  p.chromium.launch_persistent_context(str(profile), **kwargs)
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

_SANDBOX_OFF_FLAGS = ("--no-sandbox", "--disable-setuid-sandbox")

_CHROME_PATHS = {
    "darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ],
    "linux": [
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
    ],
    "win32": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
}


def channel() -> str | None:
    """Playwright 的 `channel`；None 表示用 Playwright 自带的 Chromium。"""
    v = os.environ.get("EASEL_BROWSER_CHANNEL", "chrome").strip().lower()
    return None if v in ("", "chromium", "bundled") else v


def sandbox_enabled() -> bool:
    v = os.environ.get("EASEL_CHROMIUM_SANDBOX")
    if v is not None:
        return v.strip().lower() not in ("0", "false", "no", "off")
    # root 下 Chrome 不允许开沙箱（容器常见）；其余一律开
    return not (hasattr(os, "geteuid") and os.geteuid() == 0)


def launch_kwargs(args=None, **kwargs) -> dict:
    """合并出 chromium.launch / launch_persistent_context 的关键字参数。

    传入的 args 里的 --no-sandbox / --disable-setuid-sandbox 一律剔除；沙箱关闭时
    由 Playwright 自己补 --no-sandbox。
    """
    kwargs["args"] = [a for a in (args or []) if a not in _SANDBOX_OFF_FLAGS]
    kwargs["chromium_sandbox"] = sandbox_enabled()
    ch = channel()
    if ch:
        kwargs["channel"] = ch
    return kwargs


def browser_path(p=None) -> str | None:
    """launch_kwargs() 实际会启动的浏览器；找不到返回 None。

    p 为 sync_playwright() 句柄，仅在回退到自带 Chromium 时用来取 executable_path。
    """
    ch = channel()
    if ch is None:
        try:
            path = p.chromium.executable_path if p is not None else None
        except Exception:
            path = None
        return path if path and Path(path).exists() else None
    if ch == "chrome":
        for cand in _CHROME_PATHS.get(sys.platform, []):
            cand = os.path.expanduser(cand)
            if Path(cand).is_file():
                return cand
        for exe in ("google-chrome", "google-chrome-stable", "chrome"):
            found = shutil.which(exe)
            if found:
                return found
        return None
    return f"<channel {ch}>"  # 其它 channel 交给 Playwright 自己解析


def install_hint() -> str:
    if channel() is None:
        return "playwright install chromium"
    return "安装 Google Chrome，或设 EASEL_BROWSER_CHANNEL=chromium 后 playwright install chromium"
