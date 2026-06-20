"""安全监控器 — 责任链模式检测恶意 Hello World 打印行为.

检测规则:
    1. 非标准字符集打印 (全角/不可见字符)
    2. 高频打印 (>100次/秒)
    3. 非授权设备输出
    4. 缓冲区溢出攻击模式
    5. 编码注入攻击

单例模式: 全局唯一安全监控器.
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ThreatLevel(Enum):
    """威胁等级."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """安全事件."""

    event_id: str
    level: ThreatLevel
    rule_name: str
    message: str
    source: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


# 安全检查处理函数类型
SecurityHandler = Callable[[str, Dict[str, Any]], Optional[SecurityEvent]]


class SecurityRule:
    """安全检查规则 (责任链中的一环)."""

    def __init__(
        self,
        name: str,
        handler: SecurityHandler,
        level: ThreatLevel = ThreatLevel.MEDIUM,
        enabled: bool = True,
    ) -> None:
        """初始化规则.

        Args:
            name: 规则名称.
            handler: 检查函数.
            level: 威胁等级.
            enabled: 是否启用.
        """
        self.name: str = name
        self._handler: SecurityHandler = handler
        self.level: ThreatLevel = level
        self.enabled: bool = enabled
        self._next: Optional["SecurityRule"] = None
        self._hit_count: int = 0

    def set_next(self, rule: "SecurityRule") -> "SecurityRule":
        """设置责任链下一环."""
        self._next = rule
        return rule

    def check(self, data: str, context: Dict[str, Any]) -> Optional[SecurityEvent]:
        """执行检查.

        Args:
            data: 待检查的数据.
            context: 上下文信息.

        Returns:
            触发时返回 SecurityEvent，否则 None.
        """
        if not self.enabled:
            if self._next:
                return self._next.check(data, context)
            return None

        event = self._handler(data, context)
        if event is not None:
            self._hit_count += 1
            return event

        if self._next:
            return self._next.check(data, context)

        return None

    @property
    def hit_count(self) -> int:
        """命中次数."""
        return self._hit_count


class SecurityMonitor:
    """安全监控器 — 责任链模式的恶意行为检测 (单例).

    使用示例:
        >>> monitor = SecurityMonitor.get_instance()
        >>> event = monitor.scan("Hello World", {"device": "console"})
        >>> if event:
        ...     print(f"Threat detected: {event.message}")
    """

    _instance: Optional["SecurityMonitor"] = None
    _lock: threading.Lock = threading.Lock()

    # 高频检测窗口
    _RATE_WINDOW_SECONDS: float = 1.0
    _RATE_THRESHOLD: int = 100

    # 授权设备白名单
    _AUTHORIZED_DEVICE_PREFIXES: set[str] = {"console-", "file-", "network-", "cloud-"}

    def __init__(self) -> None:
        """私有构造 — 使用 get_instance()."""
        if not hasattr(self, "_initialized"):
            self._chain: Optional[SecurityRule] = None
            self._events: List[SecurityEvent] = []
            self._max_events: int = 1000
            self._call_times: defaultdict[str, List[float]] = defaultdict(list)
            self._locked_sources: set[str] = set()
            self._build_chain()
            self._initialized: bool = True

    @classmethod
    def get_instance(cls) -> "SecurityMonitor":
        """获取 SecurityMonitor 单例."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例 (测试用)."""
        with cls._lock:
            cls._instance = None

    def _build_chain(self) -> None:
        """组装责任链."""
        chain = SecurityRule(
            "non_standard_charset",
            self._check_non_standard_charset,
            ThreatLevel.MEDIUM,
        )
        chain.set_next(
            SecurityRule(
                "high_frequency",
                self._check_high_frequency,
                ThreatLevel.HIGH,
            )
        ).set_next(
            SecurityRule(
                "unauthorized_device",
                self._check_unauthorized_device,
                ThreatLevel.CRITICAL,
            )
        ).set_next(
            SecurityRule(
                "buffer_overflow_pattern",
                self._check_buffer_overflow_pattern,
                ThreatLevel.HIGH,
            )
        ).set_next(
            SecurityRule(
                "encoding_injection",
                self._check_encoding_injection,
                ThreatLevel.MEDIUM,
            )
        ).set_next(
            SecurityRule(
                "silent_character",
                self._check_silent_characters,
                ThreatLevel.LOW,
            )
        )
        self._chain = chain

    # ---- 公共 API ----

    def scan(
        self,
        data: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[SecurityEvent]:
        """扫描数据，检测恶意行为.

        Args:
            data: 待检查的数据.
            context: 上下文 (设备ID, 来源IP 等).

        Returns:
            检测到威胁时返回 SecurityEvent，否则 None.
        """
        ctx = context or {}
        source = ctx.get("source", ctx.get("device_id", "unknown"))

        # 频率计数
        now = time.time()
        self._call_times[source].append(now)
        # 清理过期记录
        self._call_times[source] = [
            t for t in self._call_times[source]
            if now - t <= self._RATE_WINDOW_SECONDS
        ]

        ctx["_rate"] = len(self._call_times[source])

        if self._chain is None:
            return None
        event = self._chain.check(data, ctx)

        if event is not None:
            self._record_event(event)
            if event.level == ThreatLevel.CRITICAL:
                self._locked_sources.add(source)

        return event

    def is_source_locked(self, source: str) -> bool:
        """检查来源是否已被锁定."""
        return source in self._locked_sources

    def unlock_source(self, source: str) -> None:
        """解锁来源."""
        self._locked_sources.discard(source)

    # ---- 安全检查规则 ----

    @staticmethod
    def _check_non_standard_charset(
        data: str,
        context: Dict[str, Any],
    ) -> Optional[SecurityEvent]:
        """检测非标准字符集 — 全角字符、不可见字符."""
        # 全角 Hello World
        fullwidth = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
        if data == fullwidth:
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.MEDIUM,
                rule_name="non_standard_charset",
                message="Full-width Hello World detected — possible evasion attempt",
                source=context.get("source", "unknown"),
                metadata={"data_preview": data[:50]},
            )
        # 零宽字符检测
        if re.search(r"[\u200b\u200c\u200d\u2060\ufeff]", data):
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.HIGH,
                rule_name="non_standard_charset",
                message="Zero-width characters detected in output",
                source=context.get("source", "unknown"),
            )
        return None

    @classmethod
    def _check_high_frequency(
        cls,
        data: str,
        context: Dict[str, Any],
    ) -> Optional[SecurityEvent]:
        """检测高频打印 — >100次/秒."""
        rate = context.get("_rate", 0)
        if rate > cls._RATE_THRESHOLD:
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.HIGH,
                rule_name="high_frequency",
                message=(
                    f"High-frequency Hello World detected: "
                    f"{rate} requests/sec (threshold: {cls._RATE_THRESHOLD})"
                ),
                source=context.get("source", "unknown"),
                metadata={"rate": rate},
            )
        return None

    def _check_unauthorized_device(
        self,
        data: str,
        context: Dict[str, Any],
    ) -> Optional[SecurityEvent]:
        """检测非授权设备."""
        device_id = context.get("device_id", "")
        if device_id and not any(
            device_id.startswith(prefix)
            for prefix in self._AUTHORIZED_DEVICE_PREFIXES
        ):
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.CRITICAL,
                rule_name="unauthorized_device",
                message=f"Unauthorized device attempted to print: {device_id}",
                source=device_id,
            )
        return None

    @staticmethod
    def _check_buffer_overflow_pattern(
        data: str,
        context: Dict[str, Any],
    ) -> Optional[SecurityEvent]:
        """检测缓冲区溢出模式 — 超长输入."""
        if len(data) > 10_000:  # 10KB 阈值
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.HIGH,
                rule_name="buffer_overflow_pattern",
                message=f"Oversized output detected: {len(data)} chars",
                source=context.get("source", "unknown"),
                metadata={"data_length": len(data)},
            )
        return None

    @staticmethod
    def _check_encoding_injection(
        data: str,
        context: Dict[str, Any],
    ) -> Optional[SecurityEvent]:
        """检测编码注入 — 异常编码序列."""
        # 检测非法的代理对 (surrogate)
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in data):
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.MEDIUM,
                rule_name="encoding_injection",
                message="Surrogate pair injection detected in output",
                source=context.get("source", "unknown"),
            )
        # 检测 BOM 注入
        if data.startswith("\ufeff") or data.startswith("\ufffe"):
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.MEDIUM,
                rule_name="encoding_injection",
                message="BOM (Byte Order Mark) injection detected",
                source=context.get("source", "unknown"),
            )
        return None

    @staticmethod
    def _check_silent_characters(
        data: str,
        context: Dict[str, Any],
    ) -> Optional[SecurityEvent]:
        """检测静默字符 — 控制字符混入."""
        # 检测非打印控制字符 (除了常见空白)
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", data):
            return SecurityEvent(
                event_id=f"sec-{int(time.time() * 1000)}",
                level=ThreatLevel.LOW,
                rule_name="silent_character",
                message="Non-printable control characters detected",
                source=context.get("source", "unknown"),
            )
        return None

    # ---- 事件管理 ----

    def _record_event(self, event: SecurityEvent) -> None:
        """记录安全事件."""
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    # ---- 查询 ----

    def get_events(
        self,
        level: Optional[ThreatLevel] = None,
        limit: int = 50,
    ) -> List[SecurityEvent]:
        """获取安全事件.

        Args:
            level: 过滤威胁等级.
            limit: 最大返回数.

        Returns:
            安全事件列表.
        """
        events = self._events
        if level is not None:
            events = [e for e in events if e.level == level]
        return events[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取安全监控统计."""
        total = len(self._events)
        return {
            "total_events": total,
            "by_level": {
                level.value: sum(1 for e in self._events if e.level == level)
                for level in ThreatLevel
            },
            "locked_sources": list(self._locked_sources),
            "rule_hits": {
                rule.name: rule.hit_count
                for rule in self._iter_chain()
            } if self._chain else {},
        }

    def _iter_chain(self) -> list[SecurityRule]:
        """迭代责任链."""
        rules: list[SecurityRule] = []
        current = self._chain
        while current is not None:
            rules.append(current)
            current = current._next  # type: ignore[assignment]
        return rules

    def clear_events(self) -> None:
        """清空事件历史."""
        self._events.clear()

    def clear_rate_limits(self) -> None:
        """清空频率限制记录."""
        self._call_times.clear()
