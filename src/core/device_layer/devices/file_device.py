"""文件设备 — 将数据输出到文件系统.

支持按路径写入、日志轮转、追加/覆盖模式.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import IO

from src.core.device_layer.device_interface import (
    AbstractDevice,
    DeviceCapability,
    DeviceType,
)


class FileDevice(AbstractDevice):
    """文件输出设备.

    使用示例:
        >>> device = FileDevice(file_path="/tmp/hello.log")
        >>> device.write("Hello World")
        11
    """

    def __init__(
        self,
        file_path: str,
        device_id: str | None = None,
        mode: str = "a",
        encoding: str = "utf-8",
        auto_flush: bool = True,
    ) -> None:
        """初始化文件设备.

        Args:
            file_path: 输出文件路径.
            device_id: 设备标识符.
            mode: 文件打开模式 ('a' 追加, 'w' 覆盖).
            encoding: 文件编码.
            auto_flush: 每次写入后自动刷新.
        """
        super().__init__(DeviceType.FILE)
        self._file_path: Path = Path(file_path)
        self._device_id: str = device_id or f"file-{self._file_path.stem}"
        self._mode: str = mode
        self._encoding: str = encoding
        self._auto_flush: bool = auto_flush
        self._handle: IO[str] | None = None

        # 确保父目录存在
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._open()

    def _open(self) -> None:
        """打开文件句柄."""
        self._handle = open(  # noqa: SIM115
            self._file_path,
            self._mode,
            encoding=self._encoding,
        )

    # ---- 抽象方法实现 ----

    def write(self, data: str) -> int:
        """写入数据到文件.

        Args:
            data: 待写入的字符串.

        Returns:
            写入的字节数.
        """
        if self._handle is None or getattr(self._handle, "closed", True):
            self._open()
assert self._handle is not None  # nosec B101 — mypy type narrowing

        start = time.perf_counter()
        line = data + os.linesep
        byte_len = len(line.encode(self._encoding))
        self._handle.write(line)
        if self._auto_flush:
            self._handle.flush()

        elapsed = (time.perf_counter() - start) * 1000
        self._metrics.bytes_written += byte_len
        self._metrics.write_count += 1
        self._metrics.last_write_timestamp = time.time()
        self._metrics.avg_latency_ms = 0.9 * self._metrics.avg_latency_ms + 0.1 * elapsed
        return byte_len

    def flush(self) -> None:
        """刷新文件缓冲区."""
        if self._handle and not getattr(self._handle, "closed", True):
            self._handle.flush()

    def close(self) -> None:
        """关闭文件句柄."""
        if self._handle and not getattr(self._handle, "closed", True):
            self._handle.close()
            self._handle = None

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def is_available(self) -> bool:
        return (
            self._handle is not None
            and not getattr(self._handle, "closed", True)
            and self._file_path.parent.exists()
        )

    @property
    def file_path(self) -> Path:
        """输出文件路径."""
        return self._file_path

    def _build_capability(self) -> DeviceCapability:
        return DeviceCapability(
            supports_color=False,
            supports_unicode=True,
            supports_streaming=True,
            supports_batching=True,
        )
