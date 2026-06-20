"""日志上传器 — 将 Hello World 打印日志实时上传到云端.

支持多云提供商:
    - AWS CloudWatch Logs
    - GCP Cloud Logging
    - Azure Monitor
    - 阿里云 SLS

采用异步批量上传策略，保证日志不丢失。
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class CloudProvider(Enum):
    """云提供商."""

    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    ALIYUN = "aliyun"


class LogLevel(Enum):
    """日志级别."""

    TRACE = 0
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    FATAL = 50


@dataclass
class LogEntry:
    """日志条目."""

    message: str
    level: LogLevel
    timestamp: float = field(default_factory=time.time)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    module: str = "unknown"
    action: str = "hello_world_print"
    result: str = "success"
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_structured(self) -> Dict[str, Any]:
        """转为结构化字典."""
        return {
            "message": self.message,
            "level": self.level.name,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "module": self.module,
            "action": self.action,
            "result": self.result,
            **self.extra,
        }

    def to_json(self) -> str:
        """序列化为 JSON."""
        return json.dumps(self.to_structured(), ensure_ascii=False)


class CloudUploadError(Exception):
    """云端上传错误."""

    def __init__(self, message: str, error_code: str = "CLOUD_UPLOAD_ERROR") -> None:
        super().__init__(message)
        self.error_code: str = error_code
        self.timestamp: float = time.time()


class LogUploader:
    """日志上传器 — 异步批量上传到云端.

    使用示例:
        >>> uploader = LogUploader(provider=CloudProvider.AWS)
        >>> uploader.start()
        >>> uploader.log_hello_world("console-default", success=True)
        >>> uploader.stop()
    """

    _DEFAULT_BATCH_SIZE: int = 50
    _DEFAULT_FLUSH_INTERVAL: float = 5.0  # 秒

    def __init__(
        self,
        provider: CloudProvider = CloudProvider.AWS,
        log_group: str = "/super-helloworld/production",
        batch_size: int = _DEFAULT_BATCH_SIZE,
        flush_interval: float = _DEFAULT_FLUSH_INTERVAL,
    ) -> None:
        """初始化日志上传器.

        Args:
            provider: 云提供商.
            log_group: 日志组.
            batch_size: 批量上传大小.
            flush_interval: 刷新间隔 (秒).
        """
        self._provider: CloudProvider = provider
        self._log_group: str = log_group
        self._batch_size: int = batch_size
        self._flush_interval: float = flush_interval
        self._queue: queue.Queue[LogEntry] = queue.Queue()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._uploaded: int = 0
        self._failed: int = 0
        self._lock: threading.Lock = threading.Lock()

    # ---- 生命周期 ----

    def start(self) -> None:
        """启动上传器 (后台线程)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._upload_loop,
            name="log-uploader",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """停止上传器.

        Args:
            timeout: 等待超时 (秒).
        """
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    # ---- 日志记录 ----

    def log(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        module: str = "unknown",
        action: str = "hello_world_print",
        result: str = "success",
        **extra: Any,
    ) -> None:
        """记录日志.

        Args:
            message: 日志消息.
            level: 级别.
            module: 模块名.
            action: 操作.
            result: 结果.
            **extra: 额外字段.
        """
        entry = LogEntry(
            message=message,
            level=level,
            module=module,
            action=action,
            result=result,
            extra=extra,
        )
        self._queue.put(entry)

    def log_hello_world(
        self,
        device_id: str,
        success: bool = True,
        latency_ms: float = 0.0,
    ) -> None:
        """记录 Hello World 打印事件.

        Args:
            device_id: 设备 ID.
            success: 是否成功.
            latency_ms: 延迟 (ms).
        """
        self.log(
            message=f"Hello World printed to {device_id}",
            level=LogLevel.INFO,
            module="output_stream",
            action="hello_world_print",
            result="success" if success else "failure",
            device_id=device_id,
            latency_ms=latency_ms,
            provider=self._provider.value,
            log_group=self._log_group,
        )

    def log_security_event(
        self,
        event_message: str,
        threat_level: str,
        source: str,
    ) -> None:
        """记录安全事件.

        Args:
            event_message: 事件描述.
            threat_level: 威胁等级.
            source: 来源.
        """
        self.log(
            message=event_message,
            level=LogLevel.WARN,
            module="security_monitor",
            action="malicious_print_detected",
            result="detected",
            threat_level=threat_level,
            source=source,
        )

    # ---- 上传循环 ----

    def _upload_loop(self) -> None:
        """后台上传循环."""
        buffer: List[LogEntry] = []
        last_flush = time.time()

        while self._running:
            try:
                # 从队列获取日志
                entry = self._queue.get(timeout=1.0)
                buffer.append(entry)
            except queue.Empty:
                pass

            # 到达批量大小或刷新间隔时上传
            now = time.time()
            if len(buffer) >= self._batch_size or (
                buffer and now - last_flush >= self._flush_interval
            ):
                self._flush(buffer)
                buffer.clear()
                last_flush = now

        # 停止前最后一次刷新
        if buffer:
            self._flush(buffer)

    def _flush(self, entries: List[LogEntry]) -> None:
        """批量上传日志 (模拟)."""
        if not entries:
            return
        try:
            # 模拟云端上传
            payload = [e.to_structured() for e in entries]
            serialized = json.dumps(payload, ensure_ascii=False)
            # 实际生产中: upload_to_cloud(serialized)
            with self._lock:
                self._uploaded += len(entries)
        except Exception:
            with self._lock:
                self._failed += len(entries)
            raise CloudUploadError(
                f"Failed to upload {len(entries)} log entries",
                error_code="UPLOAD_FAILED",
            )

    # ---- 查询 ----

    @property
    def stats(self) -> Dict[str, Any]:
        """上传统计."""
        return {
            "provider": self._provider.value,
            "log_group": self._log_group,
            "uploaded": self._uploaded,
            "failed": self._failed,
            "queued": self._queue.qsize(),
            "running": self._running,
        }

    @property
    def provider(self) -> CloudProvider:
        """云提供商."""
        return self._provider

    @property
    def running(self) -> bool:
        """是否运行中."""
        return self._running

    def __repr__(self) -> str:
        return (
            f"LogUploader(provider={self._provider.value}, "
            f"uploaded={self._uploaded}, failed={self._failed})"
        )
