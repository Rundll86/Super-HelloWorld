"""输出字符流 — 观察者模式实现的输出调度器.

Output Stream 是处理层的核心调度模块，负责:
    - 管理订阅者 (设备 + 回调)
    - 字符流的多播分发
    - 流控制 (背压)
    - 错误隔离 (一个订阅者失败不影响其他)
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.adapter_layer.buffer_stack import BufferStack
from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
from src.core.device_layer.device_interface import AbstractDevice
from src.core.device_layer.device_manager import DeviceManager


class StreamState(Enum):
    """输出流状态."""

    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    DRAINING = "draining"
    CLOSED = "closed"


class OutputError(Exception):
    """输出流错误."""

    def __init__(self, message: str, error_code: str = "OUTPUT_ERROR") -> None:
        super().__init__(message)
        self.error_code: str = error_code
        self.timestamp: float = time.time()


# 订阅者类型: (设备ID, 回调函数, 过滤器)
Subscriber = tuple[str, Callable[[str], Any], Optional[Callable[[str], bool]]]


class OutputStream:
    """输出字符流 — 基于观察者模式的多播管道.

    使用示例:
        >>> buf = BufferStack(max_size=1024)
        >>> stream = OutputStream(buffer=buf, protocol_adapter=adapter)
        >>> stream.subscribe_device(console_device)
        >>> stream.emit("Hello World")
        >>> stream.close()
    """

    def __init__(
        self,
        buffer: BufferStack,
        protocol_adapter: ProtocolAdapter,
        device_manager: Optional[DeviceManager] = None,
        max_subscribers: int = 32,
    ) -> None:
        """初始化输出流.

        Args:
            buffer: 缓冲区栈.
            protocol_adapter: 协议适配器.
            device_manager: 设备管理器 (可选).
            max_subscribers: 最大订阅者数.
        """
        self._buffer: BufferStack = buffer
        self._protocol_adapter: ProtocolAdapter = protocol_adapter
        self._device_manager: DeviceManager = device_manager or DeviceManager.get_instance()
        self._max_subscribers: int = max_subscribers
        self._subscribers: List[Subscriber] = []
        self._state: StreamState = StreamState.IDLE
        self._lock: threading.RLock = threading.RLock()
        self._total_emitted: int = 0
        self._total_errors: int = 0

    # ---- 订阅管理 ----

    def subscribe_device(self, device: AbstractDevice) -> None:
        """订阅一个输出设备.

        Args:
            device: 输出设备.

        Raises:
            OutputError: 订阅者数量超限.
        """
        with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                raise OutputError(
                    f"Max subscribers ({self._max_subscribers}) reached",
                    error_code="MAX_SUBSCRIBERS",
                )

            def device_callback(data: str) -> int:
                cmd = self._protocol_adapter.build_write_command(data)
                return self._protocol_adapter.execute(cmd, device)

            self._subscribers.append((device.device_id, device_callback, None))

    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[str], Any],
        filter_fn: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """订阅自定义回调.

        Args:
            subscriber_id: 订阅者 ID.
            callback: 回调函数.
            filter_fn: 过滤器 (返回 True 才触发回调).
        """
        with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                raise OutputError(
                    f"Max subscribers ({self._max_subscribers}) reached",
                    error_code="MAX_SUBSCRIBERS",
                )
            self._subscribers.append((subscriber_id, callback, filter_fn))

    def unsubscribe(self, subscriber_id: str) -> None:
        """取消订阅.

        Args:
            subscriber_id: 订阅者 ID.
        """
        with self._lock:
            self._subscribers = [
                s for s in self._subscribers if s[0] != subscriber_id
            ]

    # ---- 数据发射 ----

    def emit(self, data: str) -> Dict[str, Any]:
        """向所有订阅者发射数据.

        错误隔离: 一个订阅者失败不影响其他订阅者。

        Args:
            data: 要发射的数据.

        Returns:
            {subscriber_id: result} 映射.
        """
        self._state = StreamState.STREAMING
        results: Dict[str, Any] = {}

        with self._lock:
            subscribers = list(self._subscribers)

        for sub_id, callback, filter_fn in subscribers:
            # 应用过滤器
            if filter_fn is not None and not filter_fn(data):
                continue

            try:
                results[sub_id] = callback(data)
            except Exception as exc:
                self._total_errors += 1
                results[sub_id] = {"error": str(exc)}

        self._total_emitted += 1
        self._state = StreamState.IDLE
        return results

    def emit_hello_world(self) -> Dict[str, Any]:
        """发射 'Hello World'."""
        return self.emit("Hello World")

    def emit_from_buffer(self) -> Dict[str, Any]:
        """从缓冲区读取数据并发射."""
        data = "".join(self._buffer.peek_all())
        if not data:
            return {}
        result = self.emit(data)
        self._buffer.clear()
        return result

    # ---- 流控制 ----

    def pause(self) -> None:
        """暂停流."""
        with self._lock:
            self._state = StreamState.PAUSED

    def resume(self) -> None:
        """恢复流."""
        with self._lock:
            if self._state == StreamState.PAUSED:
                self._state = StreamState.IDLE

    def drain(self) -> None:
        """排空缓冲区并关闭."""
        self._state = StreamState.DRAINING
        self.emit_from_buffer()
        self._state = StreamState.CLOSED

    def close(self) -> None:
        """关闭输出流."""
        with self._lock:
            self._subscribers.clear()
        self._state = StreamState.CLOSED

    # ---- 查询 ----

    @property
    def state(self) -> StreamState:
        """当前流状态."""
        return self._state

    @property
    def subscriber_count(self) -> int:
        """当前订阅者数量."""
        return len(self._subscribers)

    @property
    def stats(self) -> Dict[str, Any]:
        """流统计信息."""
        return {
            "state": self._state.value,
            "subscribers": len(self._subscribers),
            "total_emitted": self._total_emitted,
            "total_errors": self._total_errors,
            "error_rate": (
                self._total_errors / max(self._total_emitted, 1)
            ),
        }

    @property
    def buffer(self) -> BufferStack:
        """关联的缓冲区."""
        return self._buffer

    def __repr__(self) -> str:
        return (
            f"OutputStream(state={self._state.value}, "
            f"subscribers={len(self._subscribers)}, "
            f"emitted={self._total_emitted})"
        )
