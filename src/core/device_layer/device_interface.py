"""设备抽象接口 — 所有输出设备必须实现的契约.

符合 SPEC v1.0.0 第 7.1 节定义的接口契约。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto


class DeviceType(Enum):
    """设备类型枚举."""

    CONSOLE = auto()
    FILE = auto()
    NETWORK = auto()
    CLOUD = auto()
    CUSTOM = auto()


class DeviceStatus(Enum):
    """设备状态枚举."""

    UNREGISTERED = auto()
    REGISTERED = auto()
    ACTIVE = auto()
    ERROR = auto()
    DRAINING = auto()
    CLOSED = auto()


@dataclass(frozen=True)
class DeviceCapability:
    """设备能力描述 (不可变)."""

    supports_color: bool = False
    supports_unicode: bool = True
    supports_streaming: bool = False
    supports_batching: bool = False
    max_throughput_per_sec: int = 1_000_000
    preferred_encoding: str = "UTF-8"


@dataclass
class DeviceMetrics:
    """设备运行时指标."""

    bytes_written: int = 0
    write_count: int = 0
    error_count: int = 0
    last_write_timestamp: float = 0.0
    avg_latency_ms: float = 0.0


class AbstractDevice(ABC):
    """所有输出设备的抽象基类.

    每个设备实现必须提供:
        - write(data): 写入数据
        - flush():     刷新缓冲区
        - close():     关闭设备
        - device_id:   唯一设备标识
        - is_available: 设备可用性
    """

    def __init__(self, device_type: DeviceType) -> None:
        """初始化设备.

        Args:
            device_type: 设备类型枚举值.
        """
        self._device_type: DeviceType = device_type
        self._status: DeviceStatus = DeviceStatus.UNREGISTERED
        self._metrics: DeviceMetrics = DeviceMetrics()
        self._capability: DeviceCapability = self._build_capability()

    # ---------- 抽象方法 ----------

    @abstractmethod
    def write(self, data: str) -> int:
        """向设备写入数据.

        Args:
            data: 待写入的字符串.

        Returns:
            实际写入的字节数.

        Raises:
            DeviceError: 写入失败时抛出.
        """
        ...

    @abstractmethod
    def flush(self) -> None:
        """强制刷新设备缓冲区."""
        ...

    @abstractmethod
    def close(self) -> None:
        """关闭设备并释放资源."""
        ...

    @property
    @abstractmethod
    def device_id(self) -> str:
        """唯一设备标识符."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """设备当前是否可用."""
        ...

    # ---------- 模板方法 ----------

    @abstractmethod
    def _build_capability(self) -> DeviceCapability:
        """子类实现以声明设备能力."""
        ...

    # ---------- 公共方法 ----------

    @property
    def device_type(self) -> DeviceType:
        """设备类型."""
        return self._device_type

    @property
    def status(self) -> DeviceStatus:
        """设备当前状态."""
        return self._status

    @status.setter
    def status(self, value: DeviceStatus) -> None:
        self._status = value

    @property
    def capability(self) -> DeviceCapability:
        """设备能力描述."""
        return self._capability

    @property
    def metrics(self) -> DeviceMetrics:
        """设备运行时指标."""
        return self._metrics

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(id={self.device_id!r}, "
            f"type={self._device_type.name}, status={self._status.name})"
        )
