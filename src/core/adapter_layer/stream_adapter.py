"""流适配器 — 负责字符编码转换与流格式适配.

策略模式实现多编码转换，支持:
    - UTF-8 ↔ UTF-16 ↔ ASCII ↔ GBK 互转
    - 字符逃逸/反转义
    - Base64 编码 (用于网络传输)
    - 大小写转换管道

作为转接层的核心组件，连接 BufferStack 与 ProtocolAdapter.
"""

from __future__ import annotations

import base64
import codecs
from enum import Enum
from typing import Callable, Dict, List, Optional

from src.core.adapter_layer.buffer_stack import BufferStack


class Encoding(Enum):
    """支持的编码格式."""

    UTF8 = "utf-8"
    UTF16 = "utf-16"
    UTF16LE = "utf-16-le"
    UTF16BE = "utf-16-be"
    ASCII = "ascii"
    GBK = "gbk"
    LATIN1 = "latin-1"
    BASE64 = "base64"


class EscapeMode(Enum):
    """转义模式."""

    NONE = "none"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    URL = "url"


@FunctionalInterface
class CharTransformer:
    """字符变换器 — 可组合的字符变换 Pipeline."""

    def transform(self, char: str) -> str:
        """变换单个字符."""
        return char

    def __or__(self, other: "CharTransformer") -> "CharTransformer":
        """链式组合: t1 | t2."""
        return _ChainedTransformer(self, other)


class _ChainedTransformer(CharTransformer):
    def __init__(self, first: CharTransformer, second: CharTransformer) -> None:
        self._first = first
        self._second = second

    def transform(self, char: str) -> str:
        return self._second.transform(self._first.transform(char))


class UppercaseTransformer(CharTransformer):
    """转大写变换器."""
    def transform(self, char: str) -> str:
        return char.upper()


class LowercaseTransformer(CharTransformer):
    """转小写变换器."""
    def transform(self, char: str) -> str:
        return char.lower()


class NoopTransformer(CharTransformer):
    """恒等变换器."""
    def transform(self, char: str) -> str:
        return char


class StreamAdapter:
    """流适配器 — 编码转换与字符流适配.

    使用示例:
        >>> adapter = StreamAdapter()
        >>> result = adapter.transcode("Hello", Encoding.UTF8, Encoding.ASCII)
        >>> result
        'Hello'
        >>> b64 = adapter.to_base64("Hello World")
        >>> adapter.from_base64(b64)
        'Hello World'
    """

    def __init__(self, default_encoding: Encoding = Encoding.UTF8) -> None:
        """初始化流适配器.

        Args:
            default_encoding: 默认编码.
        """
        self._default_encoding: Encoding = default_encoding
        self._transformer: CharTransformer = NoopTransformer()

    # ---- 编码转换 ----

    def transcode(
        self,
        data: str,
        from_encoding: Encoding,
        to_encoding: Encoding,
    ) -> str:
        """编码转换.

        路径: from_encoding → raw bytes → to_encoding → str

        Args:
            data: 源字符串.
            from_encoding: 源编码.
            to_encoding: 目标编码.

        Returns:
            转换后的字符串.

        Raises:
            UnicodeError: 编码/解码失败.
        """
        if from_encoding == Encoding.BASE64 or to_encoding == Encoding.BASE64:
            raise ValueError("Use to_base64/from_base64 for base64 operations")

        raw_bytes = data.encode(from_encoding.value)
        return raw_bytes.decode(to_encoding.value)

    def to_base64(self, data: str, encoding: Encoding = Encoding.UTF8) -> str:
        """编码为 Base64.

        Args:
            data: 源字符串.
            encoding: 中间编码.

        Returns:
            Base64 编码字符串.
        """
        raw_bytes = data.encode(encoding.value)
        return base64.b64encode(raw_bytes).decode("ascii")

    def from_base64(self, data: str, encoding: Encoding = Encoding.UTF8) -> str:
        """从 Base64 解码.

        Args:
            data: Base64 字符串.
            encoding: 目标编码.

        Returns:
            解码后的字符串.
        """
        raw_bytes = base64.b64decode(data)
        return raw_bytes.decode(encoding.value)

    def to_hex(self, data: str, encoding: Encoding = Encoding.UTF8) -> str:
        """转换为十六进制表示.

        Args:
            data: 源字符串.
            encoding: 编码.

        Returns:
            十六进制字符串.
        """
        return data.encode(encoding.value).hex()

    def from_hex(self, data: str, encoding: Encoding = Encoding.UTF8) -> str:
        """从十六进制解码.

        Args:
            data: 十六进制字符串.
            encoding: 目标编码.

        Returns:
            解码后的字符串.
        """
        return bytes.fromhex(data).decode(encoding.value)

    # ---- 转义 ----

    _ESCAPE_MAP: Dict[EscapeMode, Dict[str, str]] = {
        EscapeMode.HTML: {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"},
        EscapeMode.XML: {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"},
        EscapeMode.JSON: {'"': '\\"', "\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t"},
        EscapeMode.NONE: {},
    }

    def escape(self, data: str, mode: EscapeMode) -> str:
        """转义字符串.

        Args:
            data: 源字符串.
            mode: 转义模式.

        Returns:
            转义后的字符串.
        """
        esc_map = self._ESCAPE_MAP.get(mode, {})
        if not esc_map:
            return data
        result = data
        for char, replacement in esc_map.items():
            result = result.replace(char, replacement)
        return result

    def unescape(self, data: str, mode: EscapeMode) -> str:
        """反转义字符串."""
        esc_map = self._ESCAPE_MAP.get(mode, {})
        if not esc_map:
            return data
        result = data
        for char, replacement in reversed(list(esc_map.items())):
            result = result.replace(replacement, char)
        return result

    # ---- 字符变换 Pipeline ----

    def set_transformer(self, transformer: CharTransformer) -> None:
        """设置字符变换器."""
        self._transformer = transformer

    def apply_transformer(self, data: str) -> str:
        """对字符串应用当前变换器."""
        return "".join(self._transformer.transform(ch) for ch in data)

    # ---- BufferStack 适配 ----

    def buffer_to_string(self, buffer: BufferStack) -> str:
        """从 BufferStack 提取完整字符串.

        Args:
            buffer: 字符缓冲区栈.

        Returns:
            拼接后的完整字符串.
        """
        chars = buffer.peek_all()
        return "".join(chars)

    def string_to_buffer(self, data: str, buffer: BufferStack) -> None:
        """将字符串推入 BufferStack.

        Args:
            data: 源字符串.
            buffer: 目标缓冲区.
        """
        buffer.push_all(list(data))
