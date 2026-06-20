"""Super-HelloWorld 完整测试套件.

覆盖:
    - 设备层: CharacterReader, DeviceManager, 所有设备实现
    - 转接层: BufferStack, StreamAdapter, ProtocolAdapter
    - 处理层: OutputStream, Renderer, Scheduler, SecurityMonitor, IRTranspiler
    - 云服务: LogUploader
    - CLI: 命令行参数解析

运行:
    pytest tests/ -v
    pytest tests/ -v --cov=src --cov-report=html
"""

from __future__ import annotations

import json
import os
import tempfile
import threading

import pytest

# ================================================================
# 测试工具
# ================================================================


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """每个测试前重置单例."""
    from src.core.device_layer.device_manager import DeviceManager
    from src.core.processing_layer.security_monitor import SecurityMonitor

    DeviceManager.reset_instance()
    SecurityMonitor.reset_instance()


# ================================================================
# 设备层测试
# ================================================================


class TestDeviceInterface:
    """设备抽象接口测试."""

    def test_device_type_enum(self) -> None:
        from src.core.device_layer.device_interface import DeviceType

        assert DeviceType.CONSOLE is not None
        assert DeviceType.FILE is not None
        assert DeviceType.NETWORK is not None
        assert DeviceType.CLOUD is not None

    def test_device_status_enum(self) -> None:
        from src.core.device_layer.device_interface import DeviceStatus

        assert DeviceStatus.UNREGISTERED is not None
        assert DeviceStatus.ACTIVE is not None
        assert DeviceStatus.CLOSED is not None

    def test_device_capability_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        from src.core.device_layer.device_interface import DeviceCapability

        cap = DeviceCapability(supports_color=True, supports_unicode=True)
        assert cap.supports_color is True
        with pytest.raises(FrozenInstanceError):
            cap.supports_color = False


class TestCharacterReader:
    """字符读取器测试."""

    def test_read_basic(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader, CharacterSet

        reader = CharacterReader()
        stream = reader.read("Hello", CharacterSet.UTF8)
        assert len(stream) == 5
        assert stream.tokens[0].char == "H"
        assert stream.tokens[0].position == 0
        assert stream.tokens[4].char == "o"
        assert stream.tokens[4].position == 4

    def test_read_hello_world(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader

        reader = CharacterReader()
        stream = reader.read_hello_world()
        assert len(stream) == 11  # "Hello World"
        chars = "".join(t.char for t in stream)
        assert chars == "Hello World"

    def test_read_empty_string(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader

        reader = CharacterReader()
        stream = reader.read("")
        assert len(stream) == 0

    def test_read_with_encoding(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader, CharacterSet

        reader = CharacterReader()
        stream = reader.read("Hello", CharacterSet.ASCII)
        assert len(stream) == 5
        assert stream.encoding == CharacterSet.ASCII

    def test_char_stream_peek_advance(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader

        reader = CharacterReader()
        stream = reader.read("AB")
        assert stream.peek() is not None
        assert stream.peek().char == "A"  # type: ignore[union-attr]
        assert stream.advance().char == "A"  # type: ignore[union-attr]
        assert stream.peek().char == "B"  # type: ignore[union-attr]
        assert stream.advance().char == "B"  # type: ignore[union-attr]
        assert stream.peek() is None

    def test_char_stream_reset(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader

        reader = CharacterReader()
        stream = reader.read("ABC")
        stream.advance()
        stream.advance()
        assert stream.remaining == 1
        stream.reset()
        assert stream.remaining == 3

    def test_total_chars_read(self) -> None:
        from src.core.device_layer.character_reader import CharacterReader

        reader = CharacterReader()
        reader.read("Hi")
        reader.read("There")
        assert reader.total_chars_read == 7


class TestDeviceManager:
    """设备管理器测试."""

    def test_singleton(self) -> None:
        from src.core.device_layer.device_manager import DeviceManager

        dm1 = DeviceManager.get_instance()
        dm2 = DeviceManager.get_instance()
        assert dm1 is dm2

    def test_create_and_register(self) -> None:
        from src.core.device_layer.device_interface import DeviceStatus
        from src.core.device_layer.device_manager import DeviceManager, DeviceType

        dm = DeviceManager.get_instance()
        device = dm.create_device(DeviceType.CONSOLE, device_id="test-console")
        dm.register(device)
        dm.activate("test-console")

        assert device.status == DeviceStatus.ACTIVE
        assert device.is_available

    def test_list_devices(self) -> None:
        from src.core.device_layer.device_manager import DeviceManager, DeviceType

        dm = DeviceManager.get_instance()
        d1 = dm.create_device(DeviceType.CONSOLE, device_id="c1")
        d2 = dm.create_device(DeviceType.FILE, file_path="/tmp/test.log", device_id="f1")
        dm.register(d1)
        dm.register(d2)

        devices = dm.list_devices()
        assert len(devices) == 2

    def test_write_all(self) -> None:
        from src.core.device_layer.device_manager import DeviceManager, DeviceType

        dm = DeviceManager.get_instance()
        device = dm.create_device(DeviceType.CONSOLE, device_id="console-write")
        dm.register(device)
        dm.activate("console-write")

        results = dm.write_all("Test")
        assert "console-write" in results
        assert results["console-write"] > 0

    def test_unregister(self) -> None:
        from src.core.device_layer.device_manager import DeviceManager, DeviceType

        dm = DeviceManager.get_instance()
        device = dm.create_device(DeviceType.CONSOLE, device_id="to-remove")
        dm.register(device)
        dm.unregister("to-remove")
        assert len(dm.list_devices()) == 0

    def test_duplicate_register_raises(self) -> None:
        from src.core.device_layer.device_manager import (
            DeviceAlreadyRegisteredError,
            DeviceManager,
            DeviceType,
        )

        dm = DeviceManager.get_instance()
        device = dm.create_device(DeviceType.CONSOLE, device_id="dupe")
        dm.register(device)
        with pytest.raises(DeviceAlreadyRegisteredError):
            dm.register(device)

    def test_not_found_raises(self) -> None:
        from src.core.device_layer.device_manager import (
            DeviceManager,
            DeviceNotFoundError,
        )

        dm = DeviceManager.get_instance()
        with pytest.raises(DeviceNotFoundError):
            dm.get_device("nonexistent")


class TestConsoleDevice:
    """控制台设备测试."""

    def test_basic_write(self) -> None:
        from src.core.device_layer.devices.console_device import ConsoleDevice

        device = ConsoleDevice(device_id="test-console")
        byte_len = device.write("Hello World")
        # "Hello World" = 11 bytes in UTF-8
        assert byte_len == 11

    def test_device_id(self) -> None:
        from src.core.device_layer.devices.console_device import ConsoleDevice

        device = ConsoleDevice(device_id="my-console")
        assert device.device_id == "my-console"


class TestFileDevice:
    """文件设备测试."""

    def test_write_to_file(self) -> None:
        from src.core.device_layer.devices.file_device import FileDevice

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".log") as f:
            temp_path = f.name

        try:
            device = FileDevice(file_path=temp_path, device_id="test-file")
            byte_len = device.write("Hello World")
            device.close()

            assert byte_len > 0
            with open(temp_path) as f:
                content = f.read()
            assert "Hello World" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestCloudDevice:
    """云端设备测试."""

    def test_write_and_buffer(self) -> None:
        from src.core.device_layer.devices.cloud_device import (
            CloudDevice,
            CloudProvider,
        )

        device = CloudDevice(
            provider=CloudProvider.AWS,
            device_id="test-cloud",
            batch_size=10,
        )
        device.write("Hello World")
        device.write("Hello Again")
        # 还没到 batch_size，缓冲区应有 2 条
        assert len(device._buffer) == 2

    def test_flush_batch(self) -> None:
        from src.core.device_layer.devices.cloud_device import (
            CloudDevice,
            CloudProvider,
        )

        device = CloudDevice(provider=CloudProvider.GCP, batch_size=5)
        for i in range(5):
            device.write(f"Log {i}")
        # 应该已自动刷新
        assert len(device._buffer) == 0


# ================================================================
# 转接层测试
# ================================================================


class TestBufferStack:
    """缓冲区栈测试."""

    def test_push_pop_lifo(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferMode, BufferStack

        buf = BufferStack(max_size=100, mode=BufferMode.LIFO)
        buf.push("A")
        buf.push("B")
        buf.push("C")
        assert buf.pop() == "C"
        assert buf.pop() == "B"
        assert buf.pop() == "A"

    def test_push_pop_fifo(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferMode, BufferStack

        buf = BufferStack(max_size=100, mode=BufferMode.FIFO)
        buf.push("A")
        buf.push("B")
        buf.push("C")
        assert buf.pop() == "A"
        assert buf.pop() == "B"
        assert buf.pop() == "C"

    def test_push_all(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack

        buf = BufferStack(max_size=100)
        buf.push_all(["H", "e", "l", "l", "o"])
        assert buf.size == 5

    def test_overflow_raises(self) -> None:
        from src.core.adapter_layer.buffer_stack import (
            BufferOverflowError,
            BufferStack,
        )

        buf = BufferStack(max_size=3)
        buf.push_all(["A", "B", "C"])
        with pytest.raises(BufferOverflowError):
            buf.push("D")

    def test_underflow_raises(self) -> None:
        from src.core.adapter_layer.buffer_stack import (
            BufferStack,
            BufferUnderflowError,
        )

        buf = BufferStack()
        with pytest.raises(BufferUnderflowError):
            buf.pop()

    def test_peek(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferMode, BufferStack

        buf = BufferStack(max_size=10, mode=BufferMode.FIFO)
        buf.push_all(["X", "Y", "Z"])
        peeked = buf.peek(2)
        assert peeked == ["X", "Y"]
        assert buf.size == 3  # unchanged

    def test_clear(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack

        buf = BufferStack()
        buf.push_all(["H", "i"])
        buf.clear()
        assert buf.is_empty

    def test_drain(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack

        buf = BufferStack()
        buf.push_all(["A", "B"])
        chars = buf.drain()
        assert chars == ["A", "B"]
        assert buf.is_empty

    def test_utilization(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack

        buf = BufferStack(max_size=100)
        buf.push_all(["X"] * 30)
        assert buf.utilization == 0.3

    def test_mode_switch(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferMode, BufferStack

        buf = BufferStack(mode=BufferMode.FIFO)
        buf.push_all(["1", "2", "3"])
        assert buf.pop() == "1"
        buf.mode = BufferMode.LIFO
        assert buf.pop() == "3"

    def test_stats(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack

        buf = BufferStack(max_size=100)
        buf.push_all(["A", "B"])
        stats = buf.stats
        assert stats["size"] == 2
        assert stats["max_size"] == 100
        assert "utilization" in stats


class TestStreamAdapter:
    """流适配器测试."""

    def test_transcode_utf8_to_ascii(self) -> None:
        from src.core.adapter_layer.stream_adapter import Encoding, StreamAdapter

        adapter = StreamAdapter()
        result = adapter.transcode("Hello", Encoding.UTF8, Encoding.ASCII)
        assert result == "Hello"

    def test_base64_roundtrip(self) -> None:
        from src.core.adapter_layer.stream_adapter import StreamAdapter

        adapter = StreamAdapter()
        encoded = adapter.to_base64("Hello World")
        decoded = adapter.from_base64(encoded)
        assert decoded == "Hello World"

    def test_hex_roundtrip(self) -> None:
        from src.core.adapter_layer.stream_adapter import StreamAdapter

        adapter = StreamAdapter()
        hex_str = adapter.to_hex("AB")
        assert adapter.from_hex(hex_str) == "AB"

    def test_html_escape(self) -> None:
        from src.core.adapter_layer.stream_adapter import (
            EscapeMode,
            StreamAdapter,
        )

        adapter = StreamAdapter()
        escaped = adapter.escape("<Hello>", EscapeMode.HTML)
        assert escaped == "&lt;Hello&gt;"

    def test_json_escape(self) -> None:
        from src.core.adapter_layer.stream_adapter import (
            EscapeMode,
            StreamAdapter,
        )

        adapter = StreamAdapter()
        escaped = adapter.escape('Hello "World"', EscapeMode.JSON)
        assert '\\"' in escaped

    def test_uppercase_transformer(self) -> None:
        from src.core.adapter_layer.stream_adapter import (
            StreamAdapter,
            UppercaseTransformer,
        )

        adapter = StreamAdapter()
        adapter.set_transformer(UppercaseTransformer())
        result = adapter.apply_transformer("hello")
        assert result == "HELLO"


class TestProtocolAdapter:
    """协议适配器测试."""

    def test_build_write_command(self) -> None:
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter

        adapter = ProtocolAdapter()
        cmd = adapter.build_write_command("Hello World")
        assert cmd.command_type == "write"
        assert cmd.payload == "Hello World"

    def test_negotiate(self) -> None:
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
        from src.core.device_layer.devices.console_device import ConsoleDevice

        device = ConsoleDevice(device_id="negotiate-test")
        adapter = ProtocolAdapter()
        neg = adapter.negotiate(device)
        assert neg.device_id == "negotiate-test"
        assert neg.supports_color is True

    def test_command_history(self) -> None:
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter

        adapter = ProtocolAdapter()
        adapter.build_write_command("A")
        adapter.build_write_command("B")
        adapter.build_flush_command()
        assert adapter.command_count == 3


# ================================================================
# 处理层测试
# ================================================================


class TestRenderer:
    """渲染器测试."""

    def test_plain_render(self) -> None:
        from src.core.processing_layer.renderer import Renderer, RenderStyle

        renderer = Renderer()
        result = renderer.render("Hello World", RenderStyle.PLAIN)
        assert result.output == "Hello World"
        assert result.style == RenderStyle.PLAIN

    def test_colored_render(self) -> None:
        from src.core.processing_layer.renderer import Renderer, RenderStyle

        renderer = Renderer()
        result = renderer.render("Hello", RenderStyle.COLORED)
        assert "\033[" in result.output
        assert "Hello" in result.output

    def test_json_render(self) -> None:
        from src.core.processing_layer.renderer import Renderer, RenderStyle

        renderer = Renderer()
        result = renderer.render("Hello", RenderStyle.JSON)
        parsed = json.loads(result.output)
        assert parsed["message"] == "Hello"

    def test_xml_render(self) -> None:
        from src.core.processing_layer.renderer import Renderer, RenderStyle

        renderer = Renderer()
        result = renderer.render("Hi", RenderStyle.XML)
        assert "<helloworld" in result.output
        assert "<message>Hi</message>" in result.output

    def test_minimal_render(self) -> None:
        from src.core.processing_layer.renderer import Renderer, RenderStyle

        renderer = Renderer()
        result = renderer.render("Hello World", RenderStyle.MINIMAL)
        assert " " not in result.output
        assert result.output == "HelloWorld"

    def test_render_hello_world(self) -> None:
        from src.core.processing_layer.renderer import Renderer

        renderer = Renderer()
        result = renderer.render_hello_world()
        assert result.output == "Hello World"

    def test_render_result_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        from src.core.processing_layer.renderer import Renderer

        renderer = Renderer()
        result = renderer.render("x")
        with pytest.raises(FrozenInstanceError):
            result.output = "y"

    def test_compose(self) -> None:
        from src.core.processing_layer.renderer import Renderer, RenderStyle

        renderer = Renderer()
        results = renderer.compose(
            [RenderStyle.PLAIN, RenderStyle.COLORED],
            "Hello",
        )
        assert len(results) == 2


class TestOutputStream:
    """输出字符流测试."""

    def test_subscribe_and_emit(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
        from src.core.processing_layer.output_stream import OutputStream

        buf = BufferStack(max_size=100)
        adapter = ProtocolAdapter()
        stream = OutputStream(buffer=buf, protocol_adapter=adapter)

        received: list[str] = []

        def callback(data: str) -> None:
            received.append(data)

        stream.subscribe("test-sub", callback)
        stream.emit("Hello World")

        assert received == ["Hello World"]

    def test_multiple_subscribers(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
        from src.core.processing_layer.output_stream import OutputStream

        buf = BufferStack()
        adapter = ProtocolAdapter()
        stream = OutputStream(buffer=buf, protocol_adapter=adapter)

        results: dict[str, str] = {}

        def make_cb(name: str):
            def cb(data: str) -> None:
                results[name] = data

            return cb

        stream.subscribe("a", make_cb("a"))
        stream.subscribe("b", make_cb("b"))
        stream.emit("Hello")

        assert results == {"a": "Hello", "b": "Hello"}

    def test_filter(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
        from src.core.processing_layer.output_stream import OutputStream

        buf = BufferStack()
        adapter = ProtocolAdapter()
        stream = OutputStream(buffer=buf, protocol_adapter=adapter)

        received: list[str] = []
        stream.subscribe(
            "filtered",
            lambda d: received.append(d),
            filter_fn=lambda d: "important" in d,
        )
        stream.emit("normal message")
        stream.emit("important message")

        assert received == ["important message"]

    def test_unsubscribe(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
        from src.core.processing_layer.output_stream import OutputStream

        buf = BufferStack()
        adapter = ProtocolAdapter()
        stream = OutputStream(buffer=buf, protocol_adapter=adapter)

        received: list[str] = []
        stream.subscribe("temp", lambda d: received.append(d))
        stream.unsubscribe("temp")
        stream.emit("no one should get this")
        assert received == []


class TestScheduler:
    """定时调度器测试."""

    def test_add_job(self) -> None:
        from src.core.processing_layer.scheduler import CronScheduler

        scheduler = CronScheduler()
        job = scheduler.add_job("test", "* * * * *", lambda: "done")
        assert job.job_id == "test"
        assert job.cron_expression == "* * * * *"
        assert job.enabled is True

    def test_invalid_cron_raises(self) -> None:
        from src.core.processing_layer.scheduler import (
            CronScheduler,
            SchedulerError,
        )

        scheduler = CronScheduler()
        with pytest.raises(SchedulerError):
            scheduler.add_job("bad", "invalid", lambda: None)

    def test_list_jobs(self) -> None:
        from src.core.processing_layer.scheduler import CronScheduler

        scheduler = CronScheduler()
        scheduler.add_job("j1", "* * * * *", lambda: None)
        scheduler.add_job("j2", "0 * * * *", lambda: None)
        assert len(scheduler.list_jobs()) == 2

    def test_cron_match(self) -> None:
        from src.core.processing_layer.scheduler import CronScheduler

        # Wildcard matches any
        assert CronScheduler._match_field(5, "*") is True
        # Exact match
        assert CronScheduler._match_field(5, "5") is True
        assert CronScheduler._match_field(5, "6") is False
        # Step
        assert CronScheduler._match_field(10, "*/5") is True
        assert CronScheduler._match_field(12, "*/5") is False
        # Range
        assert CronScheduler._match_field(3, "1-5") is True
        assert CronScheduler._match_field(8, "1-5") is False
        # Comma
        assert CronScheduler._match_field(3, "1,3,5") is True
        assert CronScheduler._match_field(4, "1,3,5") is False


class TestSecurityMonitor:
    """安全监控器测试."""

    def test_singleton(self) -> None:
        from src.core.processing_layer.security_monitor import SecurityMonitor

        m1 = SecurityMonitor.get_instance()
        m2 = SecurityMonitor.get_instance()
        assert m1 is m2

    def test_clean_message_passes(self) -> None:
        from src.core.processing_layer.security_monitor import SecurityMonitor

        monitor = SecurityMonitor.get_instance()
        event = monitor.scan("Hello World")
        assert event is None

    def test_fullwidth_detected(self) -> None:
        from src.core.processing_layer.security_monitor import SecurityMonitor

        monitor = SecurityMonitor.get_instance()
        fullwidth = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
        event = monitor.scan(fullwidth)
        assert event is not None
        assert event.level.value == "medium"

    def test_oversized_detected(self) -> None:
        from src.core.processing_layer.security_monitor import SecurityMonitor

        monitor = SecurityMonitor.get_instance()
        huge = "A" * 20_000
        event = monitor.scan(huge)
        assert event is not None
        assert event.rule_name == "buffer_overflow_pattern"

    def test_control_chars_detected(self) -> None:
        from src.core.processing_layer.security_monitor import SecurityMonitor

        monitor = SecurityMonitor.get_instance()
        event = monitor.scan("Hello\x00World")
        assert event is not None

    def test_get_stats(self) -> None:
        from src.core.processing_layer.security_monitor import SecurityMonitor

        monitor = SecurityMonitor.get_instance()
        monitor.scan("Hello")  # clean
        stats = monitor.get_stats()
        assert "total_events" in stats
        assert "by_level" in stats


class TestIRTranspiler:
    """IR 转译器测试."""

    def test_javascript_transpile(self) -> None:
        from src.core.processing_layer.ir_transpiler import (
            IRTranspiler,
            TargetLanguage,
        )

        transpiler = IRTranspiler()
        output = transpiler.transpile_to(TargetLanguage.JAVASCRIPT)
        assert "console.log" in output.source_code
        assert "Hello World" in output.source_code
        assert output.target_language == TargetLanguage.JAVASCRIPT

    def test_java_transpile(self) -> None:
        from src.core.processing_layer.ir_transpiler import (
            IRTranspiler,
            TargetLanguage,
        )

        transpiler = IRTranspiler()
        output = transpiler.transpile_to(TargetLanguage.JAVA)
        assert "public class HelloWorld" in output.source_code
        assert "System.out.println" in output.source_code

    def test_cpp_transpile(self) -> None:
        from src.core.processing_layer.ir_transpiler import (
            IRTranspiler,
            TargetLanguage,
        )

        transpiler = IRTranspiler()
        output = transpiler.transpile_to(TargetLanguage.CPP)
        assert "#include <iostream>" in output.source_code
        assert "std::cout" in output.source_code

    def test_rust_transpile(self) -> None:
        from src.core.processing_layer.ir_transpiler import (
            IRTranspiler,
            TargetLanguage,
        )

        transpiler = IRTranspiler()
        output = transpiler.transpile_to(TargetLanguage.RUST)
        assert "fn main()" in output.source_code
        assert "println!" in output.source_code

    def test_wasm_transpile(self) -> None:
        from src.core.processing_layer.ir_transpiler import (
            IRTranspiler,
            TargetLanguage,
        )

        transpiler = IRTranspiler()
        output = transpiler.transpile_to(TargetLanguage.WASM)
        assert "(module" in output.source_code
        assert "hello_world" in output.source_code

    def test_transpile_all(self) -> None:
        from src.core.processing_layer.ir_transpiler import IRTranspiler

        transpiler = IRTranspiler()
        results = transpiler.transpile_all()
        assert len(results) >= 5  # at least JS, Java, C++, Rust, WASM
        for _lang, output in results.items():
            assert output.source_code != ""

    def test_export_ir_json(self) -> None:
        from src.core.processing_layer.ir_transpiler import IRTranspiler

        transpiler = IRTranspiler()
        ir_json = transpiler.export_ir_json()
        parsed = json.loads(ir_json)
        assert parsed["node_type"] == "program"
        assert parsed["value"] == "hello_world"

    def test_custom_message(self) -> None:
        from src.core.processing_layer.ir_transpiler import (
            IRTranspiler,
            TargetLanguage,
        )

        transpiler = IRTranspiler()
        output = transpiler.transpile_to(
            TargetLanguage.JAVASCRIPT,
            message="Custom Message",
        )
        assert "Custom Message" in output.source_code


# ================================================================
# 云服务层测试
# ================================================================


class TestLogUploader:
    """日志上传器测试."""

    def test_log_entry(self) -> None:
        from src.cloud.log_uploader import LogEntry, LogLevel

        entry = LogEntry(
            message="Test",
            level=LogLevel.INFO,
            module="test",
        )
        assert entry.message == "Test"
        assert entry.level == LogLevel.INFO

        structured = entry.to_structured()
        assert structured["message"] == "Test"
        assert structured["trace_id"] != ""

    def test_log_hello_world(self) -> None:
        from src.cloud.log_uploader import LogUploader

        uploader = LogUploader(batch_size=5)
        uploader.start()
        uploader.log_hello_world("device-1", success=True)
        uploader.stop()
        stats = uploader.stats
        assert stats["uploaded"] == 1

    def test_log_security_event(self) -> None:
        from src.cloud.log_uploader import LogUploader

        uploader = LogUploader(batch_size=5)
        uploader.start()
        uploader.log_security_event(
            "Suspicious print",
            "high",
            "evil-device",
        )
        uploader.stop()
        assert uploader.stats["uploaded"] == 1


# ================================================================
# 集成测试
# ================================================================


class TestIntegration:
    """端到端集成测试."""

    def test_full_pipeline(self) -> None:
        """完整打印流水线: 字符读取 → 缓冲区 → 渲染 → 输出."""
        from src.core.adapter_layer.buffer_stack import BufferStack
        from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
        from src.core.device_layer.character_reader import CharacterReader
        from src.core.device_layer.device_manager import DeviceManager, DeviceType
        from src.core.processing_layer.output_stream import OutputStream
        from src.core.processing_layer.renderer import Renderer
        from src.core.processing_layer.security_monitor import SecurityMonitor

        # 设备层
        dm = DeviceManager.get_instance()
        device = dm.create_device(DeviceType.CONSOLE, device_id="integration-test")
        dm.register(device)
        dm.activate("integration-test")

        reader = CharacterReader()
        stream = reader.read_hello_world()

        # 转接层
        buf = BufferStack()
        buf.push_all([t.char for t in stream])

        adapter = ProtocolAdapter()
        adapter.negotiate(device)

        # 处理层
        renderer = Renderer()
        rendered = renderer.render_hello_world()

        monitor = SecurityMonitor.get_instance()
        event = monitor.scan(rendered.output)

        out = OutputStream(buffer=buf, protocol_adapter=adapter)
        out.subscribe_device(device)
        result = out.emit(rendered.output)

        assert event is None  # Hello World is clean
        assert "integration-test" in result
        assert buf.is_empty is False  # 源数据未被弹出

    def test_engine_pipeline(self) -> None:
        """HelloWorldEngine 编排器集成测试."""
        from src.main import HelloWorldEngine

        engine = HelloWorldEngine()
        engine.setup_default_pipeline()

        result = engine.print_hello_world()
        assert result == "Hello World"
        assert engine.total_prints == 1

        engine.shutdown()

    def test_engine_custom_print(self) -> None:
        from src.main import HelloWorldEngine

        engine = HelloWorldEngine()
        engine.setup_default_pipeline()

        result = engine.print_custom("Bonjour le Monde")
        assert result == "Bonjour le Monde"
        assert engine.total_prints == 1

        engine.shutdown()


# ================================================================
# CLI 测试
# ================================================================


class TestCLI:
    """CLI 命令行测试."""

    def test_print_command(self) -> None:
        from src.cli import run_cli

        ret = run_cli(["print", "--message", "Test CLI"])
        assert ret == 0

    def test_print_help(self, capsys) -> None:  # type: ignore[no-untyped-def]
        from src.cli import run_cli

        ret = run_cli([])
        # 无命令时应返回错误码
        assert ret == 1

    def test_ir_command(self) -> None:
        from src.cli import run_cli

        ret = run_cli(["ir", "transpile", "--target", "javascript"])
        assert ret == 0

    def test_security_scan_clean(self) -> None:
        from src.cli import run_cli

        ret = run_cli(["security", "scan", "--message", "Clean message"])
        assert ret == 0

    def test_security_scan_threat(self) -> None:
        from src.cli import run_cli

        fullwidth = "Ｈｅｌｌｏ　Ｗｏｒｌｄ"
        ret = run_cli(["security", "scan", "--message", fullwidth])
        assert ret == 0

    def test_device_list(self) -> None:
        from src.cli import run_cli

        ret = run_cli(["device", "list"])
        assert ret == 0

    def test_version_flag(self) -> None:
        from src.cli import run_cli

        # --version should print and exit
        try:
            ret = run_cli(["--version"])
        except SystemExit:
            ret = 0
        assert ret == 0


# ================================================================
# 性能 & 并发测试
# ================================================================


class TestConcurrency:
    """并发安全测试."""

    def test_buffer_concurrent_push(self) -> None:
        from src.core.adapter_layer.buffer_stack import BufferStack

        buf = BufferStack(max_size=10000)
        errors: list[Exception] = []

        def worker(start: int) -> None:
            for i in range(start, start + 100):
                try:
                    buf.push(chr(65 + (i % 26)))
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i * 100,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert buf.size == 1000
