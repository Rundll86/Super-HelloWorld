"""云端设备 — 将数据输出到云平台.

支持 AWS CloudWatch、GCP Cloud Logging、Azure Monitor 等云日志服务.
通过适配器模式对接多层次云提供商.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from enum import Enum

from src.core.device_layer.device_interface import (
    AbstractDevice,
    DeviceCapability,
    DeviceType,
)


class CloudProvider(Enum):
    """云提供商枚举."""

    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ALIYUN = "aliyun"
    CUSTOM = "custom"


@dataclass
class CloudLogEntry:
    """云端日志条目."""

    message: str
    timestamp: float
    trace_id: str
    level: str = "INFO"
    labels: dict[str, str] | None = None

    def to_json(self) -> str:
        """序列化为 JSON."""
        return json.dumps(
            {
                "message": self.message,
                "timestamp": self.timestamp,
                "trace_id": self.trace_id,
                "level": self.level,
                "labels": self.labels or {},
            },
            ensure_ascii=False,
        )


class CloudDevice(AbstractDevice):
    """云端输出设备 — 模拟云日志写入.

    使用示例:
        >>> device = CloudDevice(provider=CloudProvider.AWS)
        >>> device.write("Hello World")
        11
    """

    def __init__(
        self,
        provider: CloudProvider = CloudProvider.AWS,
        device_id: str | None = None,
        log_group: str = "/super-helloworld/production",
        batch_size: int = 10,
        region: str = "us-east-1",
    ) -> None:
        """初始化云端设备.

        Args:
            provider: 云提供商.
            device_id: 设备标识符.
            log_group: 日志组名称.
            batch_size: 批量上传阈值.
            region: 云区域.
        """
        super().__init__(DeviceType.CLOUD)
        self._provider: CloudProvider = provider
        self._device_id: str = device_id or f"cloud-{provider.value}"
        self._log_group: str = log_group
        self._batch_size: int = batch_size
        self._region: str = region
        self._buffer: list[CloudLogEntry] = []

    # ---- 批量上传器 ----

    def _buffered_write(self, entry: CloudLogEntry) -> int:
        """缓冲写入，达到阈值后批量上传."""
        self._buffer.append(entry)
        byte_len = len(entry.to_json().encode("utf-8"))
        if len(self._buffer) >= self._batch_size:
            self.flush()
        return byte_len

    # ---- 抽象方法实现 ----

    def write(self, data: str) -> int:
        """写入数据到云端日志.

        Args:
            data: 待写入的字符串.

        Returns:
            写入的字节数.
        """
        start = time.perf_counter()
        entry = CloudLogEntry(
            message=data,
            timestamp=time.time(),
            trace_id=str(uuid.uuid4()),
            level="INFO",
            labels={
                "provider": self._provider.value,
                "log_group": self._log_group,
                "region": self._region,
            },
        )
        byte_len = self._buffered_write(entry)

        elapsed = (time.perf_counter() - start) * 1000
        self._metrics.bytes_written += byte_len
        self._metrics.write_count += 1
        self._metrics.last_write_timestamp = time.time()
        self._metrics.avg_latency_ms = (
            0.9 * self._metrics.avg_latency_ms + 0.1 * elapsed
        )
        return byte_len

    def flush(self) -> None:
        """批量上传缓冲区中的日志到云端."""
        if not self._buffer:
            return
        # 模拟云端上传
        entries_json = [e.to_json() for e in self._buffer]
        _ = json.dumps(entries_json, ensure_ascii=False)  # 实际生产中发送到云端
        self._buffer.clear()

    def close(self) -> None:
        """关闭前刷新缓冲区."""
        self.flush()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def is_available(self) -> bool:
        return True  # 云端设备假设始终可用 (有降级策略)

    @property
    def provider(self) -> CloudProvider:
        """云提供商."""
        return self._provider

    @property
    def log_group(self) -> str:
        """日志组."""
        return self._log_group

    def _build_capability(self) -> DeviceCapability:
        return DeviceCapability(
            supports_color=False,
            supports_unicode=True,
            supports_streaming=False,
            supports_batching=True,
            max_throughput_per_sec=10_000,
        )
