"""协议适配器 — 将内部 IR 表示转换为设备可理解的输出协议.

作为转接层的顶层模块，负责:
    - 将处理层的 IR 转为设备命令
    - 设备能力协商
    - 输出格式组装
    - 协议版本管理
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.adapter_layer.buffer_stack import BufferStack
from src.core.adapter_layer.stream_adapter import Encoding, StreamAdapter
from src.core.device_layer.device_interface import AbstractDevice, DeviceCapability


class ProtocolVersion(Enum):
    """协议版本."""

    V1_0 = "1.0"
    V2_0 = "2.0"


@dataclass(frozen=True)
class DeviceCommand:
    """设备命令 (不可变).

    这是协议适配器向设备层发送的标准化命令。
    """

    command_type: str  # write / flush / close / reset
    payload: str
    protocol_version: ProtocolVersion = ProtocolVersion.V2_0
    encoding: Encoding = Encoding.UTF8
    metadata: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        """序列化为 JSON."""
        return json.dumps(
            {
                "command_type": self.command_type,
                "payload": self.payload,
                "protocol_version": self.protocol_version.value,
                "encoding": self.encoding.value,
                "metadata": self.metadata,
                "timestamp": self.timestamp,
            },
            ensure_ascii=False,
        )


@dataclass
class CapabilityNegotiation:
    """能力协商结果."""

    device_id: str
    device_capability: DeviceCapability
    negotiated_encoding: Encoding
    supports_color: bool
    supports_batching: bool
    max_payload_size: int = 65536


class ProtocolAdapter:
    """协议适配器 — IR 到设备命令的桥接.

    使用示例:
        >>> adapter = ProtocolAdapter()
        >>> adapter.negotiate(console_device)
        >>> cmd = adapter.build_write_command("Hello World")
        >>> adapter.execute(cmd, console_device)
    """

    def __init__(self, protocol_version: ProtocolVersion = ProtocolVersion.V2_0) -> None:
        """初始化协议适配器.

        Args:
            protocol_version: 使用的协议版本.
        """
        self._protocol_version: ProtocolVersion = protocol_version
        self._stream_adapter: StreamAdapter = StreamAdapter()
        self._negotiations: Dict[str, CapabilityNegotiation] = {}
        self._command_history: List[DeviceCommand] = []

    # ---- 能力协商 ----

    def negotiate(self, device: AbstractDevice) -> CapabilityNegotiation:
        """与设备进行能力协商.

        根据设备能力选择合适的编码和协议参数。

        Args:
            device: 目标设备.

        Returns:
            协商结果.
        """
        capability = device.capability
        negotiated_encoding = (
            Encoding.UTF8
            if capability.supports_unicode
            else Encoding.ASCII
        )

        negotiation = CapabilityNegotiation(
            device_id=device.device_id,
            device_capability=capability,
            negotiated_encoding=negotiated_encoding,
            supports_color=capability.supports_color,
            supports_batching=capability.supports_batching,
        )
        self._negotiations[device.device_id] = negotiation
        return negotiation

    # ---- 命令构建 ----

    def build_write_command(self, payload: str) -> DeviceCommand:
        """构建写入命令.

        Args:
            payload: 要输出的内容.

        Returns:
            标准设备命令.
        """
        cmd = DeviceCommand(
            command_type="write",
            payload=payload,
            protocol_version=self._protocol_version,
            metadata={"source": "protocol_adapter"},
        )
        self._command_history.append(cmd)
        return cmd

    def build_flush_command(self) -> DeviceCommand:
        """构建刷新命令."""
        cmd = DeviceCommand(
            command_type="flush",
            payload="",
            protocol_version=self._protocol_version,
        )
        self._command_history.append(cmd)
        return cmd

    def build_close_command(self) -> DeviceCommand:
        """构建关闭命令."""
        cmd = DeviceCommand(
            command_type="close",
            payload="",
            protocol_version=self._protocol_version,
        )
        self._command_history.append(cmd)
        return cmd

    # ---- 命令执行 ----

    def execute(self, command: DeviceCommand, device: AbstractDevice) -> int:
        """执行设备命令.

        Args:
            command: 设备命令.
            device: 目标设备.

        Returns:
            写入的字节数.

        Raises:
            ValueError: 未知的命令类型.
        """
        neg = self._negotiations.get(device.device_id)
        encoding = neg.negotiated_encoding if neg else Encoding.UTF8

        if command.command_type == "write":
            # 编码转换 (如果需要)
            if command.encoding != encoding:
                payload = self._stream_adapter.transcode(
                    command.payload, command.encoding, encoding
                )
            else:
                payload = command.payload
            return device.write(payload)

        elif command.command_type == "flush":
            device.flush()
            return 0

        elif command.command_type == "close":
            device.close()
            return 0

        else:
            raise ValueError(f"Unknown command type: {command.command_type}")

    def broadcast(self, payload: str, devices: List[AbstractDevice]) -> Dict[str, int]:
        """向多个设备广播同一命令.

        Args:
            payload: 输出内容.
            devices: 目标设备列表.

        Returns:
            {device_id: bytes_written} 映射.
        """
        results: Dict[str, int] = {}
        for device in devices:
            if device.device_id not in self._negotiations:
                self.negotiate(device)
            cmd = self.build_write_command(payload)
            results[device.device_id] = self.execute(cmd, device)
        return results

    # ---- BufferStack 集成 ----

    def buffer_to_command(self, buffer: BufferStack) -> DeviceCommand:
        """从 BufferStack 构建写入命令.

        Args:
            buffer: 字符缓冲区.

        Returns:
            设备写入命令.
        """
        payload = self._stream_adapter.buffer_to_string(buffer)
        return self.build_write_command(payload)

    def command_to_buffer(self, command: DeviceCommand, buffer: BufferStack) -> None:
        """将命令的 payload 推入缓冲区.

        Args:
            command: 设备命令.
            buffer: 目标缓冲区.
        """
        buffer.clear()
        self._stream_adapter.string_to_buffer(command.payload, buffer)

    # ---- 查询 ----

    @property
    def protocol_version(self) -> ProtocolVersion:
        """当前协议版本."""
        return self._protocol_version

    @property
    def command_count(self) -> int:
        """已发出的命令总数."""
        return len(self._command_history)

    def get_negotiation(self, device_id: str) -> Optional[CapabilityNegotiation]:
        """获取设备的协商结果."""
        return self._negotiations.get(device_id)

    def clear_history(self) -> None:
        """清空命令历史."""
        self._command_history.clear()
