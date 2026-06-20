"""字符读取器 — 从字符集中提取目标字符序列.

采用策略模式支持不同字符集，将 "Hello World" 逐字符解析为
可被下游模块消费的标准化字符流。

设计目标:
    - 支持多字符集: UTF-8, UTF-16, ASCII, GBK
    - 逐字符流式读取，支持预取 (lookahead)
    - 字符位置追踪 (source map 溯源)
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum


class CharacterSet(Enum):
    """支持的字符集枚举."""

    UTF8 = "utf-8"
    UTF16 = "utf-16"
    ASCII = "ascii"
    GBK = "gbk"
    LATIN1 = "latin-1"


@dataclass(frozen=True)
class CharToken:
    """单个字符令牌 (不可变).

    Attributes:
        char: 字符值.
        position: 在源字符串中的位置 (0-indexed).
        byte_offset: 字节偏移量.
        encoding: 使用的编码.
    """

    char: str
    position: int
    byte_offset: int
    encoding: CharacterSet


@dataclass
class CharStream:
    """字符流 — 已解析的字符令牌序列."""

    tokens: list[CharToken] = field(default_factory=list)
    source: str = ""
    encoding: CharacterSet = CharacterSet.UTF8
    _cursor: int = field(default=0, init=False)

    def __iter__(self) -> Iterator[CharToken]:
        return iter(self.tokens)

    def __len__(self) -> int:
        return len(self.tokens)

    def peek(self) -> CharToken | None:
        """查看当前字符但不移动游标."""
        if self._cursor < len(self.tokens):
            return self.tokens[self._cursor]
        return None

    def advance(self) -> CharToken | None:
        """读取当前字符并移动游标."""
        token = self.peek()
        if token is not None:
            self._cursor += 1
        return token

    def reset(self) -> None:
        """重置游标到起始位置."""
        self._cursor = 0

    @property
    def remaining(self) -> int:
        """剩余未读字符数."""
        return len(self.tokens) - self._cursor


class CharacterReader:
    """字符读取器 — 将字符串解析为标准化字符令牌流.

    使用示例:
        >>> reader = CharacterReader()
        >>> stream = reader.read("Hello", CharacterSet.UTF8)
        >>> for token in stream:
        ...     print(token.char, token.position)
        H 0
        e 1
        l 2
        l 3
        o 4
    """

    # ---- 多字节字符编码的字节宽度映射 ----
    _ENCODING_BYTE_WIDTHS = {
        CharacterSet.UTF8: 1,       # 变长，简化为 ASCII 范围
        CharacterSet.UTF16: 2,
        CharacterSet.ASCII: 1,
        CharacterSet.GBK: 2,
        CharacterSet.LATIN1: 1,
    }

    def __init__(self, default_encoding: CharacterSet = CharacterSet.UTF8) -> None:
        """初始化字符读取器.

        Args:
            default_encoding: 默认字符编码.
        """
        self._default_encoding: CharacterSet = default_encoding
        self._total_chars_read: int = 0

    # ---- 公共 API ----

    def read(
        self,
        source: str,
        encoding: CharacterSet | None = None,
    ) -> CharStream:
        """解析源字符串为 CharStream.

        Args:
            source: 源字符串.
            encoding: 字符编码，默认使用 UTF-8.

        Returns:
            包含所有字符令牌的 CharStream.

        Raises:
            ValueError: 字符串包含不可编码字符时抛出.
        """
        enc = encoding or self._default_encoding
        byte_width = self._ENCODING_BYTE_WIDTHS.get(enc, 1)

        tokens: list[CharToken] = []
        byte_offset = 0

        for idx, ch in enumerate(source):
            if not self._is_encodable(ch, enc):
                raise ValueError(
                    f"Character {ch!r} at position {idx} is not encodable in {enc.name}"
                )
            token = CharToken(
                char=ch,
                position=idx,
                byte_offset=byte_offset,
                encoding=enc,
            )
            tokens.append(token)
            byte_offset += len(ch.encode(enc.value)) if enc != CharacterSet.UTF8 else byte_width

        self._total_chars_read += len(tokens)
        return CharStream(tokens=tokens, source=source, encoding=enc)

    def read_hello_world(
        self,
        encoding: CharacterSet | None = None,
    ) -> CharStream:
        """便捷方法 — 直接读取 'Hello World'.

        Args:
            encoding: 字符编码.

        Returns:
            包含 'Hello World' 每个字符的 CharStream.
        """
        return self.read("Hello World", encoding=encoding)

    # ---- 内部方法 ----

    def _is_encodable(self, char: str, encoding: CharacterSet) -> bool:
        """检查字符是否可在指定编码中表示."""
        try:
            char.encode(encoding.value)
            return True
        except (UnicodeEncodeError, UnicodeDecodeError):
            return False

    @property
    def total_chars_read(self) -> int:
        """累计读取字符总数."""
        return self._total_chars_read
