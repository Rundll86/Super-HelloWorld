"""控制台设备 — 将数据输出到 stdout/stderr.

这是最常用的输出设备，支持颜色、Unicode 和即时刷新.
"""

from __future__ import annotations

import sys
import time

from src.core.device_layer.device_interface import (
    AbstractDevice,
    DeviceCapability,
    DeviceType,
)


class ConsoleDevice(AbstractDevice):
    """控制台输出设备.

    使用示例:
        >>> device = ConsoleDevice()
        >>> device.write("Hello World")
        11
    """

    def __init__(self, device_id: str = "console-default", use_stderr: bool = False) -> None:
        """初始化控制台设备.

        Args:
            device_id: 设备标识符.
            use_stderr: 是否输出到 stderr.
        """
        super().__init__(DeviceType.CONSOLE)
        self._device_id: str = device_id
        self._use_stderr: bool = use_stderr
        self._stream = sys.stderr if use_stderr else sys.stdout

    # ---- 抽象方法实现 ----

    def write(self, data: str) -> int:
        """写入数据到控制台.

        Args:
            data: 待写入的字符串.

        Returns:
            写入的字符数.
        """
        start = time.perf_counter()
        try:
            byte_len = len(data.encode("utf-8"))
            self._stream.write(data)
            self._stream.write("\n")
            self._stream.flush()
        except Exception:
            self._metrics.error_count += 1
            raise
        elapsed = (time.perf_counter() - start) * 1000
        self._metrics.bytes_written += byte_len
        self._metrics.write_count += 1
        self._metrics.last_write_timestamp = time.time()
        # 指数加权移动平均
        self._metrics.avg_latency_ms = (
            0.9 * self._metrics.avg_latency_ms + 0.1 * elapsed
        )
        return byte_len

    def flush(self) -> None:
        """刷新控制台缓冲区."""
        self._stream.flush()

    def close(self) -> None:
        """关闭控制台设备 (不真正关闭 stdin/stdout)."""
        self.flush()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def is_available(self) -> bool:
        return not self._stream.closed

    def _build_capability(self) -> DeviceCapability:
        return DeviceCapability(
            supports_color=True,
            supports_unicode=True,
            supports_streaming=True,
            supports_batching=False,
        )
