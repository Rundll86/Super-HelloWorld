"""缓冲区栈 — 双端字符缓冲区，支持 LIFO/FIFO 切换.

采用双端队列 (collections.deque) 实现高性能的字符缓冲，
支持:
    - LIFO (后进先出) 栈模式
    - FIFO (先进先出) 队列模式
    - 动态模式切换
    - 容量限制
    - 线程安全
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Iterator
from enum import Enum


class BufferError(Exception):
    """缓冲区错误基类."""

    def __init__(self, message: str, error_code: str = "BUFFER_ERROR") -> None:
        super().__init__(message)
        self.error_code: str = error_code
        self.timestamp: float = time.time()


class BufferOverflowError(BufferError):
    """缓冲区溢出错误."""


class BufferUnderflowError(BufferError):
    """缓冲区下溢错误."""


class BufferMode(Enum):
    """缓冲区操作模式."""

    LIFO = "lifo"  # 后进先出 (栈)
    FIFO = "fifo"  # 先进先出 (队列)


class BufferStack:
    """线程安全的双端字符缓冲区栈.

    使用示例:
        >>> buf = BufferStack(max_size=1024)
        >>> buf.push("H")
        >>> buf.push("e")
        >>> buf.push("l")
        >>> buf.push_all(["l", "o"])
        >>> buf.size
        5
        >>> buf.pop()
        'o'
        >>> "".join(buf.pop_all(4))
        'lleH'
    """

    def __init__(
        self,
        max_size: int = 65536,
        mode: BufferMode = BufferMode.LIFO,
    ) -> None:
        """初始化缓冲区栈.

        Args:
            max_size: 最大容量.
            mode: 操作模式 (LIFO/FIFO).
        """
        self._deque: deque[str] = deque(maxlen=max_size)
        self._max_size: int = max_size
        self._mode: BufferMode = mode
        self._lock: threading.Lock = threading.Lock()
        self._total_pushed: int = 0
        self._total_popped: int = 0

    # ---- 属性 ----

    @property
    def size(self) -> int:
        """当前缓冲区中的字符数."""
        with self._lock:
            return len(self._deque)

    @property
    def max_size(self) -> int:
        """缓冲区最大容量."""
        return self._max_size

    @property
    def mode(self) -> BufferMode:
        """当前操作模式."""
        return self._mode

    @mode.setter
    def mode(self, value: BufferMode) -> None:
        """切换操作模式."""
        with self._lock:
            self._mode = value

    @property
    def is_empty(self) -> bool:
        """缓冲区是否为空."""
        return self.size == 0

    @property
    def is_full(self) -> bool:
        """缓冲区是否已满."""
        return self.size >= self._max_size

    @property
    def utilization(self) -> float:
        """缓冲区利用率 (0.0 ~ 1.0)."""
        if self._max_size == 0:
            return 1.0
        return self.size / self._max_size

    @property
    def stats(self) -> dict[str, int | float]:
        """缓冲区统计信息."""
        return {
            "size": self.size,
            "max_size": self._max_size,
            "utilization": self.utilization,
            "total_pushed": self._total_pushed,
            "total_popped": self._total_popped,
        }

    # ---- 推入操作 ----

    def push(self, char: str) -> None:
        """推入单个字符.

        Args:
            char: 单个字符.

        Raises:
            BufferOverflowError: 缓冲区已满.
        """
        if len(char) != 1:
            raise BufferError(
                f"push() expects a single character, got {len(char)} chars",
                error_code="INVALID_CHAR",
            )
        with self._lock:
            if self.is_full:
                raise BufferOverflowError(
                    f"Buffer overflow: {self.size}/{self._max_size}",
                    error_code="BUFFER_OVERFLOW",
                )
            self._deque.append(char)
            self._total_pushed += 1

    def push_all(self, chars: list[str]) -> None:
        """推入多个字符.

        Args:
            chars: 字符列表.

        Raises:
            BufferOverflowError: 缓冲区容量不足.
        """
        with self._lock:
            if self.size + len(chars) > self._max_size:
                raise BufferOverflowError(
                    f"Cannot push {len(chars)} chars: "
                    f"{self.size}/{self._max_size} used",
                    error_code="BUFFER_OVERFLOW",
                )
            self._deque.extend(chars)
            self._total_pushed += len(chars)

    # ---- 弹出操作 ----

    def pop(self) -> str:
        """弹出一个字符.

        Returns:
            弹出的字符.

        Raises:
            BufferUnderflowError: 缓冲区为空.
        """
        with self._lock:
            if not self._deque:
                raise BufferUnderflowError(
                    "Buffer underflow: no characters available",
                    error_code="BUFFER_UNDERFLOW",
                )
            self._total_popped += 1
            if self._mode == BufferMode.LIFO:
                return self._deque.pop()
            else:
                return self._deque.popleft()

    def pop_all(self, count: int = -1) -> list[str]:
        """弹出多个字符.

        Args:
            count: 要弹出的字符数，-1 表示全部.

        Returns:
            弹出的字符列表.
        """
        with self._lock:
            if count == -1 or count >= len(self._deque):
                chars = list(self._deque)
                self._deque.clear()
                self._total_popped += len(chars)
                return chars
            chars = []
            for _ in range(count):
                if self._mode == BufferMode.LIFO:
                    chars.append(self._deque.pop())
                else:
                    chars.append(self._deque.popleft())
            self._total_popped += len(chars)
            return chars

    def peek(self, count: int = 1) -> list[str]:
        """查看字符但不弹出.

        Args:
            count: 要查看的字符数.

        Returns:
            字符列表.
        """
        with self._lock:
            items = list(self._deque)
            if self._mode == BufferMode.LIFO:
                items.reverse()
            return items[:count]

    def peek_all(self) -> list[str]:
        """查看所有字符但不弹出."""
        with self._lock:
            items = list(self._deque)
            if self._mode == BufferMode.LIFO:
                items.reverse()
            return items

    # ---- 清空 ----

    def clear(self) -> None:
        """清空缓冲区."""
        with self._lock:
            self._deque.clear()

    def drain(self) -> list[str]:
        """排空缓冲区并返回所有字符."""
        return self.pop_all(-1)

    # ---- 迭代 ----

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            items = list(self._deque)
        if self._mode == BufferMode.LIFO:
            items.reverse()
        return iter(items)

    def __repr__(self) -> str:
        return (
            f"BufferStack(size={self.size}, max={self._max_size}, "
            f"mode={self._mode.value}, util={self.utilization:.1%})"
        )
