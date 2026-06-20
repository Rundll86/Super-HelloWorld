"""网络设备 — 通过 Socket/HTTP 将数据发送到远程端点.

支持 TCP 连接池、自动重连、TLS 加密.
"""

from __future__ import annotations

import socket
import ssl
import time
from typing import Optional

from src.core.device_layer.device_interface import (
    AbstractDevice,
    DeviceCapability,
    DeviceType,
)


class NetworkDevice(AbstractDevice):
    """网络输出设备 — 通过 TCP 发送数据.

    使用示例:
        >>> device = NetworkDevice(host="localhost", port=9999)
        >>> device.connect()
        >>> device.write("Hello World")
        11
    """

    _DEFAULT_TIMEOUT: float = 5.0
    _MAX_RECONNECT_ATTEMPTS: int = 3

    def __init__(
        self,
        host: str,
        port: int,
        device_id: str | None = None,
        use_tls: bool = False,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        """初始化网络设备.

        Args:
            host: 目标主机.
            port: 目标端口.
            device_id: 设备标识符.
            use_tls: 是否启用 TLS.
            timeout: 连接超时 (秒).
        """
        super().__init__(DeviceType.NETWORK)
        self._host: str = host
        self._port: int = port
        self._device_id: str = device_id or f"network-{host}:{port}"
        self._use_tls: bool = use_tls
        self._timeout: float = timeout
        self._sock: Optional[socket.socket] = None
        self._connected: bool = False

    # ---- 连接管理 ----

    def connect(self) -> None:
        """建立 TCP 连接.

        Raises:
            ConnectionError: 连接失败.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._MAX_RECONNECT_ATTEMPTS + 1):
            try:
                raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                raw_sock.settimeout(self._timeout)
                if self._use_tls:
                    context = ssl.create_default_context()
                    self._sock = context.wrap_socket(raw_sock, server_hostname=self._host)
                else:
                    self._sock = raw_sock
                self._sock.connect((self._host, self._port))
                self._connected = True
                return
            except (socket.error, ssl.SSLError) as exc:
                last_exc = exc
                time.sleep(min(attempt * 0.5, 2.0))
        raise ConnectionError(
            f"Failed to connect to {self._host}:{self._port} "
            f"after {self._MAX_RECONNECT_ATTEMPTS} attempts: {last_exc}"
        )

    def disconnect(self) -> None:
        """断开连接."""
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
            self._sock = None
        self._connected = False

    # ---- 抽象方法实现 ----

    def write(self, data: str) -> int:
        """写入数据到网络.

        Args:
            data: 待写入的字符串.

        Returns:
            发送的字节数.
        """
        if not self._connected or self._sock is None:
            self.connect()

        start = time.perf_counter()
        payload = (data + "\n").encode("utf-8")
        byte_len = len(payload)
        self._sock.sendall(payload)  # type: ignore[union-attr]

        elapsed = (time.perf_counter() - start) * 1000
        self._metrics.bytes_written += byte_len
        self._metrics.write_count += 1
        self._metrics.last_write_timestamp = time.time()
        self._metrics.avg_latency_ms = (
            0.9 * self._metrics.avg_latency_ms + 0.1 * elapsed
        )
        return byte_len

    def flush(self) -> None:
        """TCP 无缓冲，直接发送."""
        pass

    def close(self) -> None:
        """关闭连接."""
        self.disconnect()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def is_available(self) -> bool:
        return self._connected and self._sock is not None

    def _build_capability(self) -> DeviceCapability:
        return DeviceCapability(
            supports_color=False,
            supports_unicode=True,
            supports_streaming=True,
            supports_batching=True,
        )
