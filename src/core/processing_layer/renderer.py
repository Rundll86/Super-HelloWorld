"""渲染引擎 — 将字符流渲染为最终输出格式.

支持多种渲染管线:
    - Plain: 纯文本
    - Colored: ANSI 彩色
    - Rich: 富文本 (Markdown/HTML)
    - Minimal: 最小化输出 (去空格)
    - JSON: JSON 格式包装
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class RenderStyle(Enum):
    """渲染风格."""

    PLAIN = "plain"
    COLORED = "colored"
    RICH = "rich"
    MINIMAL = "minimal"
    JSON = "json"
    XML = "xml"


class ANSIColor:
    """ANSI 颜色代码."""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


@dataclass(frozen=True)
class RenderResult:
    """渲染结果 (不可变)."""

    output: str
    style: RenderStyle
    rendered_at: float
    metadata: Dict[str, Any]


class Renderer:
    """字符渲染引擎.

    使用示例:
        >>> renderer = Renderer()
        >>> result = renderer.render("Hello World", RenderStyle.COLORED)
        >>> result.output
        '\033[92mHello World\033[0m'
        >>> renderer.render_hello_world()
        RenderResult(output='Hello World', style=RenderStyle.PLAIN, ...)
    """

    _DEFAULT_MESSAGE: str = "Hello World"

    def __init__(
        self,
        default_style: RenderStyle = RenderStyle.PLAIN,
        color: ANSIColor | None = None,
    ) -> None:
        """初始化渲染器.

        Args:
            default_style: 默认渲染风格.
            color: 默认颜色 (仅 COLORED 风格).
        """
        self._default_style: RenderStyle = default_style
        self._default_color: ANSIColor = color or ANSIColor.GREEN
        self._render_count: int = 0

    # ---- 渲染方法 ----

    def render(
        self,
        message: str,
        style: Optional[RenderStyle] = None,
        color: Optional[ANSIColor] = None,
        **kwargs: Any,
    ) -> RenderResult:
        """渲染消息.

        Args:
            message: 输入消息.
            style: 渲染风格.
            color: 颜色.
            **kwargs: 风格特定的额外参数.

        Returns:
            渲染结果.
        """
        s = style or self._default_style
        c = color or self._default_color

        renderers = {
            RenderStyle.PLAIN: self._render_plain,
            RenderStyle.COLORED: lambda m: self._render_colored(m, c),
            RenderStyle.RICH: self._render_rich,
            RenderStyle.MINIMAL: self._render_minimal,
            RenderStyle.JSON: self._render_json,
            RenderStyle.XML: self._render_xml,
        }

        render_fn = renderers.get(s, self._render_plain)
        output = render_fn(message)

        self._render_count += 1
        return RenderResult(
            output=output,
            style=s,
            rendered_at=time.time(),
            metadata={"render_index": self._render_count, **kwargs},
        )

    def render_hello_world(
        self,
        style: Optional[RenderStyle] = None,
        **kwargs: Any,
    ) -> RenderResult:
        """渲染 Hello World.

        Args:
            style: 渲染风格.
            **kwargs: 额外参数.

        Returns:
            渲染结果.
        """
        return self.render(self._DEFAULT_MESSAGE, style=style, **kwargs)

    # ---- 私有渲染方法 ----

    @staticmethod
    def _render_plain(message: str) -> str:
        return message

    @staticmethod
    def _render_colored(message: str, color: ANSIColor) -> str:
        return f"{color}{message}{ANSIColor.RESET}"

    def _render_rich(self, message: str) -> str:
        """富文本渲染 — 带时间戳和前缀."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        return f"[{ts}] {ANSIColor.BOLD}▶{ANSIColor.RESET} {message}"

    @staticmethod
    def _render_minimal(message: str) -> str:
        """最小化 — 去除空格，压缩输出."""
        return message.replace(" ", "")

    @staticmethod
    def _render_json(message: str) -> str:
        """JSON 包装."""
        return json.dumps(
            {
                "message": message,
                "length": len(message),
                "timestamp": time.time(),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _render_xml(message: str) -> str:
        """XML 包装."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        return (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<helloworld timestamp="{ts}">\n'
            f"  <message>{message}</message>\n"
            f"</helloworld>"
        )

    # ---- 链式渲染 (Pipeline) ----

    def compose(
        self,
        styles: list[RenderStyle],
        message: str = "Hello World",
    ) -> list[RenderResult]:
        """按多个风格依次渲染.

        Args:
            styles: 风格列表.
            message: 输入消息.

        Returns:
            渲染结果列表.
        """
        results: list[RenderResult] = []
        current = message
        for style in styles:
            result = self.render(current, style=style)
            results.append(result)
            current = result.output
        return results

    # ---- 查询 ----

    @property
    def render_count(self) -> int:
        """渲染次数."""
        return self._render_count

    @property
    def default_style(self) -> RenderStyle:
        """默认渲染风格."""
        return self._default_style

    @default_style.setter
    def default_style(self, value: RenderStyle) -> None:
        self._default_style = value
