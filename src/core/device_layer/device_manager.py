"""设备管理器 — 管理所有输出设备的生命周期.

设计模式:
    - 工厂模式: 根据类型创建设备实例
    - 注册表模式: 维护设备注册表
    - 单例模式: 全局唯一设备管理器
    - 观察者模式: 设备状态变更通知

线程安全: 使用 threading.RLock 保证并发安全.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Type

from src.core.device_layer.device_interface import (
    AbstractDevice,
    DeviceStatus,
    DeviceType,
)
from src.core.device_layer.devices.console_device import ConsoleDevice
from src.core.device_layer.devices.file_device import FileDevice
from src.core.device_layer.devices.network_device import NetworkDevice
from src.core.device_layer.devices.cloud_device import CloudDevice


class DeviceError(Exception):
    """设备相关错误基类."""

    def __init__(self, message: str, error_code: str = "DEVICE_ERROR") -> None:
        super().__init__(message)
        self.error_code: str = error_code
        self.timestamp: float = time.time()


class DeviceAlreadyRegisteredError(DeviceError):
    """设备已注册错误."""


class DeviceNotFoundError(DeviceError):
    """设备未找到错误."""


class DeviceNotAvailableError(DeviceError):
    """设备不可用错误."""


# 设备状态变更回调类型
DeviceCallback = Callable[[AbstractDevice, DeviceStatus, DeviceStatus], None]


class DeviceManager:
    """设备管理器 — 全局设备生命周期管理 (单例).

    使用示例:
        >>> dm = DeviceManager.get_instance()
        >>> device = dm.create_device(DeviceType.CONSOLE)
        >>> dm.register(device)
        >>> dm.activate("console-default")
        >>> dm.write_all("Hello World")
    """

    _instance: Optional["DeviceManager"] = None
    _lock: threading.Lock = threading.Lock()
    _rlock: threading.RLock = threading.RLock()

    # 设备工厂注册表: DeviceType → DeviceClass
    _factory_registry: Dict[DeviceType, Type[AbstractDevice]] = {
        DeviceType.CONSOLE: ConsoleDevice,
        DeviceType.FILE: FileDevice,
        DeviceType.NETWORK: NetworkDevice,
        DeviceType.CLOUD: CloudDevice,
    }

    def __init__(self) -> None:
        """私有构造 — 请使用 get_instance()."""
        if not hasattr(self, "_initialized"):
            self._registry: OrderedDict[str, AbstractDevice] = OrderedDict()
            self._callbacks: List[DeviceCallback] = []
            self._default_device_id: Optional[str] = None
            self._initialized: bool = True

    @classmethod
    def get_instance(cls) -> "DeviceManager":
        """获取 DeviceManager 单例."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例 (主要用于测试)."""
        with cls._lock:
            cls._instance = None

    @classmethod
    def register_device_factory(
        cls,
        device_type: DeviceType,
        factory: Type[AbstractDevice],
    ) -> None:
        """注册自定义设备工厂.

        Args:
            device_type: 设备类型.
            factory: 设备类.
        """
        cls._factory_registry[device_type] = factory

    # ---- 设备生命周期 ----

    def create_device(
        self,
        device_type: DeviceType,
        **kwargs: object,
    ) -> AbstractDevice:
        """工厂方法 — 创建设备实例.

        Args:
            device_type: 设备类型.
            **kwargs: 传递给设备构造函数的参数.

        Returns:
            设备实例.

        Raises:
            DeviceError: 未知的设备类型.
        """
        factory = self._factory_registry.get(device_type)
        if factory is None:
            raise DeviceError(
                f"Unknown device type: {device_type}",
                error_code="UNKNOWN_DEVICE_TYPE",
            )
        return factory(**kwargs)

    def register(self, device: AbstractDevice) -> str:
        """注册设备到注册表.

        Args:
            device: 设备实例.

        Returns:
            设备的 device_id.

        Raises:
            DeviceAlreadyRegisteredError: 设备 ID 冲突.
        """
        with self._rlock:
            did = device.device_id
            if did in self._registry:
                raise DeviceAlreadyRegisteredError(
                    f"Device {did} is already registered",
                    error_code="DEVICE_ALREADY_REGISTERED",
                )
            device.status = DeviceStatus.REGISTERED
            self._registry[did] = device
            if self._default_device_id is None:
                self._default_device_id = did
            return did

    def unregister(self, device_id: str) -> None:
        """注销设备.

        Args:
            device_id: 设备 ID.

        Raises:
            DeviceNotFoundError: 设备不存在.
        """
        with self._rlock:
            if device_id not in self._registry:
                raise DeviceNotFoundError(
                    f"Device {device_id} not found",
                    error_code="DEVICE_NOT_FOUND",
                )
            device = self._registry.pop(device_id)
            old_status = device.status
            device.status = DeviceStatus.UNREGISTERED
            self._notify(device, old_status, DeviceStatus.UNREGISTERED)
            device.close()
            if self._default_device_id == device_id:
                self._default_device_id = next(iter(self._registry), None)

    def activate(self, device_id: str) -> None:
        """激活设备.

        Args:
            device_id: 设备 ID.
        """
        with self._rlock:
            device = self._get_or_raise(device_id)
            old_status = device.status
            device.status = DeviceStatus.ACTIVE
            self._notify(device, old_status, DeviceStatus.ACTIVE)

    def deactivate(self, device_id: str) -> None:
        """停用设备.

        Args:
            device_id: 设备 ID.
        """
        with self._rlock:
            device = self._get_or_raise(device_id)
            old_status = device.status
            device.status = DeviceStatus.DRAINING
            self._notify(device, old_status, DeviceStatus.DRAINING)

    # ---- 查询方法 ----

    def get_device(self, device_id: str) -> AbstractDevice:
        """获取设备实例.

        Args:
            device_id: 设备 ID.

        Returns:
            设备实例.
        """
        with self._rlock:
            return self._get_or_raise(device_id)

    def get_active_devices(self) -> List[AbstractDevice]:
        """获取所有活跃设备."""
        with self._rlock:
            return [
                d for d in self._registry.values()
                if d.status == DeviceStatus.ACTIVE
            ]

    def get_default_device(self) -> Optional[AbstractDevice]:
        """获取默认设备."""
        with self._rlock:
            if self._default_device_id:
                return self._registry.get(self._default_device_id)
            return None

    def set_default_device(self, device_id: str) -> None:
        """设置默认设备."""
        with self._rlock:
            self._get_or_raise(device_id)
            self._default_device_id = device_id

    def list_devices(self) -> List[AbstractDevice]:
        """列出所有已注册设备."""
        with self._rlock:
            return list(self._registry.values())

    # ---- 写入操作 ----

    def write_all(self, data: str) -> Dict[str, int]:
        """向所有活跃设备写入数据.

        Args:
            data: 待写入的数据.

        Returns:
            {device_id: bytes_written} 映射.
        """
        results: Dict[str, int] = {}
        with self._rlock:
            for device in self.get_active_devices():
                try:
                    results[device.device_id] = device.write(data)
                except Exception as exc:
                    device.metrics.error_count += 1
                    raise DeviceError(
                        f"Write to {device.device_id} failed: {exc}",
                        error_code="WRITE_FAILED",
                    ) from exc
        return results

    def write_to(self, device_id: str, data: str) -> int:
        """向指定设备写入数据.

        Args:
            device_id: 设备 ID.
            data: 待写入的数据.

        Returns:
            写入的字节数.
        """
        with self._rlock:
            device = self._get_or_raise(device_id)
            if device.status != DeviceStatus.ACTIVE:
                raise DeviceNotAvailableError(
                    f"Device {device_id} is not active (status={device.status.name})",
                    error_code="DEVICE_NOT_ACTIVE",
                )
            return device.write(data)

    def flush_all(self) -> None:
        """刷新所有活跃设备."""
        with self._rlock:
            for device in self.get_active_devices():
                device.flush()

    def close_all(self) -> None:
        """关闭所有设备."""
        with self._rlock:
            for device in list(self._registry.values()):
                device.close()
                device.status = DeviceStatus.CLOSED
            self._registry.clear()
            self._default_device_id = None

    # ---- 回调管理 ----

    def add_callback(self, callback: DeviceCallback) -> None:
        """添加设备状态变更回调."""
        self._callbacks.append(callback)

    def remove_callback(self, callback: DeviceCallback) -> None:
        """移除设备状态变更回调."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # ---- 内部方法 ----

    def _get_or_raise(self, device_id: str) -> AbstractDevice:
        """获取设备或抛出异常."""
        device = self._registry.get(device_id)
        if device is None:
            raise DeviceNotFoundError(
                f"Device {device_id} not found",
                error_code="DEVICE_NOT_FOUND",
            )
        return device

    def _notify(
        self,
        device: AbstractDevice,
        old_status: DeviceStatus,
        new_status: DeviceStatus,
    ) -> None:
        """通知所有回调."""
        for cb in self._callbacks:
            try:
                cb(device, old_status, new_status)
            except Exception:
                pass  # 回调异常不影响主流程
