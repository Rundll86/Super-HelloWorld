"""Super-HelloWorld — 企业级 Hello World 打印基础设施主入口.

使用方式:
    # 编程 API
    $ python -m src.main

    # CLI 模式
    $ python -m src.cli print --style colored

架构分层:
    ┌─────────────────────────────────────┐
    │         CLI / API 控制层             │
    ├─────────────────────────────────────┤
    │  处理层: OutputStream / Renderer     │
    │  / Scheduler / SecurityMonitor      │
    │  / IRTranspiler                      │
    ├─────────────────────────────────────┤
    │  转接层: BufferStack / StreamAdapter │
    │  / ProtocolAdapter                   │
    ├─────────────────────────────────────┤
    │  设备层: CharacterReader /           │
    │  DeviceManager / AbstractDevice     │
    └─────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional

from src.core.device_layer.character_reader import CharacterReader, CharacterSet
from src.core.device_layer.device_interface import DeviceType
from src.core.device_layer.device_manager import DeviceManager
from src.core.adapter_layer.buffer_stack import BufferStack, BufferMode
from src.core.adapter_layer.stream_adapter import Encoding, StreamAdapter
from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
from src.core.processing_layer.renderer import Renderer, RenderStyle, ANSIColor
from src.core.processing_layer.output_stream import OutputStream
from src.core.processing_layer.security_monitor import SecurityMonitor
from src.core.processing_layer.ir_transpiler import IRTranspiler, TargetLanguage
from src.cloud.log_uploader import LogUploader, CloudProvider, LogLevel

# 结构化日志配置
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("super-helloworld")


class HelloWorldEngine:
    """Hello World 打印引擎 — 将所有模块组装为完整流水线.

    这是整个企业级打印系统的高层编排器。

    使用示例:
        >>> engine = HelloWorldEngine()
        >>> engine.setup_default_pipeline()
        >>> result = engine.print_hello_world()
        >>> print(result)
        Hello World
    """

    def __init__(self) -> None:
        """初始化打印引擎."""
        # --- 设备层 ---
        self._device_manager: DeviceManager = DeviceManager.get_instance()
        self._character_reader: CharacterReader = CharacterReader()

        # --- 转接层 ---
        self._buffer: BufferStack = BufferStack(max_size=65536, mode=BufferMode.FIFO)
        self._stream_adapter: StreamAdapter = StreamAdapter()
        self._protocol_adapter: ProtocolAdapter = ProtocolAdapter()

        # --- 处理层 ---
        self._renderer: Renderer = Renderer(default_style=RenderStyle.PLAIN)
        self._output_stream: OutputStream = OutputStream(
            buffer=self._buffer,
            protocol_adapter=self._protocol_adapter,
            device_manager=self._device_manager,
        )
        self._security_monitor: SecurityMonitor = SecurityMonitor.get_instance()
        self._ir_transpiler: IRTranspiler = IRTranspiler()

        # --- 云服务 ---
        self._log_uploader: LogUploader = LogUploader(provider=CloudProvider.AWS)

        # 统计
        self._total_prints: int = 0

    # ================================================================
    # 流水线配置
    # ================================================================

    def setup_default_pipeline(
        self,
        style: RenderStyle = RenderStyle.PLAIN,
    ) -> HelloWorldEngine:
        """配置默认打印流水线 (Console + Cloud).

        Args:
            style: 渲染风格.

        Returns:
            self (链式调用).
        """
        # 注册并激活控制台设备
        console = self._device_manager.create_device(DeviceType.CONSOLE)
        self._device_manager.register(console)
        self._device_manager.activate(console.device_id)

        # 注册并激活云端设备
        cloud = self._device_manager.create_device(DeviceType.CLOUD)
        self._device_manager.register(cloud)
        self._device_manager.activate(cloud.device_id)

        # 协商协议
        self._protocol_adapter.negotiate(console)
        self._protocol_adapter.negotiate(cloud)

        # 订阅到输出流
        self._output_stream.subscribe_device(console)
        self._output_stream.subscribe_device(cloud)

        # 设置渲染风格
        self._renderer.default_style = style

        # 启动云日志上传器
        self._log_uploader.start()

        logger.info(
            "Default pipeline configured: console + cloud, style=%s",
            style.value,
        )
        return self

    # ================================================================
    # 核心操作
    # ================================================================

    def print_hello_world(
        self,
        style: Optional[RenderStyle] = None,
        encoding: CharacterSet = CharacterSet.UTF8,
    ) -> str:
        """执行完整的 Hello World 打印流水线.

        整个流水线:
            1. CharacterReader 读取字符序列
            2. 推入 BufferStack
            3. SecurityMonitor 安全扫描
            4. Renderer 渲染
            5. OutputStream 多播分发
            6. LogUploader 云端记录

        Args:
            style: 渲染风格 (可选).
            encoding: 字符编码.

        Returns:
            实际输出的字符串.
        """
        start_time = time.perf_counter()
        message = "Hello World"

        # Step 1: 字符读取
        char_stream = self._character_reader.read(message, encoding=encoding)
        logger.debug("Character stream: %d tokens", len(char_stream))

        # Step 2: 推入缓冲区
        self._buffer.clear()
        self._buffer.push_all([t.char for t in char_stream])
        logger.debug("Buffer: %d chars", self._buffer.size)

        # Step 3: 安全扫描
        sec_event = self._security_monitor.scan(
            message,
            {"source": "engine", "encoding": encoding.value},
        )
        if sec_event:
            logger.warning(
                "Security alert: [%s] %s",
                sec_event.level.value,
                sec_event.message,
            )
            self._log_uploader.log_security_event(
                sec_event.message,
                sec_event.level.value,
                "hello_world_engine",
            )

        # Step 4: 渲染
        rendered = self._renderer.render(message, style=style)
        logger.debug("Rendered: %s", rendered.style.value)

        # Step 5: 输出流分发
        results = self._output_stream.emit(rendered.output)
        logger.info("Emitted to %d subscribers", len(results))

        # Step 6: 云端日志
        latency_ms = (time.perf_counter() - start_time) * 1000
        for device_id in results:
            self._log_uploader.log_hello_world(
                device_id,
                success=True,
                latency_ms=latency_ms,
            )

        self._total_prints += 1
        return rendered.output

    def print_custom(
        self,
        message: str,
        style: Optional[RenderStyle] = None,
    ) -> str:
        """打印自定义消息.

        Args:
            message: 自定义消息.
            style: 渲染风格.

        Returns:
            实际输出的字符串.
        """
        start_time = time.perf_counter()
        rendered = self._renderer.render(message, style=style)
        self._output_stream.emit(rendered.output)

        latency_ms = (time.perf_counter() - start_time) * 1000
        self._log_uploader.log(
            message=f"Custom message printed: {message[:50]}",
            level=LogLevel.INFO,
            module="engine",
            action="custom_print",
            latency_ms=latency_ms,
        )
        self._total_prints += 1
        return rendered.output

    # ================================================================
    # IR 转译
    # ================================================================

    def transpile_to(self, target: TargetLanguage) -> str:
        """转译 Hello World 到目标语言.

        Args:
            target: 目标语言.

        Returns:
            目标语言的源代码.
        """
        output = self._ir_transpiler.transpile_to(target)
        return output.source_code

    def transpile_all(self) -> dict[TargetLanguage, str]:
        """转译到所有支持的语言.

        Returns:
            {语言: 源代码} 映射.
        """
        outputs = self._ir_transpiler.transpile_all()
        return {lang: out.source_code for lang, out in outputs.items()}

    # ================================================================
    # 关闭
    # ================================================================

    def shutdown(self) -> None:
        """优雅关闭引擎."""
        logger.info("Shutting down HelloWorldEngine...")
        self._output_stream.close()
        self._device_manager.close_all()
        self._log_uploader.stop()
        logger.info("HelloWorldEngine shutdown complete. Total prints: %d", self._total_prints)

    # ================================================================
    # 属性
    # ================================================================

    @property
    def total_prints(self) -> int:
        """总打印次数."""
        return self._total_prints

    @property
    def device_manager(self) -> DeviceManager:
        """设备管理器."""
        return self._device_manager

    @property
    def output_stream(self) -> OutputStream:
        """输出流."""
        return self._output_stream

    @property
    def renderer(self) -> Renderer:
        """渲染器."""
        return self._renderer

    @property
    def ir_transpiler(self) -> IRTranspiler:
        """IR 转译器."""
        return self._ir_transpiler

    @property
    def log_uploader(self) -> LogUploader:
        """日志上传器."""
        return self._log_uploader

    @property
    def stats(self) -> dict:
        """引擎统计信息."""
        return {
            "total_prints": self._total_prints,
            "render_count": self._renderer.render_count,
            "buffer_utilization": self._buffer.utilization,
            "stream_state": self._output_stream.state.value,
            "ir_transpile_count": self._ir_transpiler.transpile_count,
            "cloud_uploads": self._log_uploader.stats["uploaded"],
            "security_events": self._security_monitor.get_stats()["total_events"],
        }


# ================================================================
# 主入口
# ================================================================

def main() -> int:
    """编程 API 主入口.

    执行完整的 Hello World 打印流水线并显示统计。

    Returns:
        退出码.
    """
    print("=" * 60)
    print("  Super-HelloWorld v1.0.0")
    print("  Enterprise-Grade Hello World Printing Infrastructure")
    print("=" * 60)
    print()

    engine = HelloWorldEngine()

    try:
        # ---- 设置默认流水线 ----
        engine.setup_default_pipeline(style=RenderStyle.PLAIN)

        # ---- 打印 Hello World ----
        print("[1] Printing Hello World (plain)...")
        result = engine.print_hello_world()
        print(f"    Output: {result}")

        # ---- 彩色打印 ----
        print("[2] Printing Hello World (colored)...")
        result = engine.print_hello_world(style=RenderStyle.COLORED)
        print(f"    Output: {result}")

        # ---- IR 转译演示 ----
        print("\n[3] IR Transpilation Demo:")
        for lang in [TargetLanguage.JAVASCRIPT, TargetLanguage.RUST]:
            code = engine.transpile_to(lang)
            print(f"    --- {lang.value} ---")
            for line in code.strip().split("\n"):
                print(f"    {line}")

        # ---- 安全扫描演示 ----
        print("\n[4] Security Monitor Demo:")
        sec_stats = engine._security_monitor.get_stats()
        print(f"    Security events: {sec_stats['total_events']}")
        print(f"    Rule hits: {sec_stats.get('rule_hits', {})}")

        # ---- 云端日志 ----
        upload_stats = engine.log_uploader.stats
        print(f"\n[5] Cloud Log Uploader:")
        print(f"    Uploaded: {upload_stats['uploaded']}")
        print(f"    Failed: {upload_stats['failed']}")

        # ---- 引擎统计 ----
        print(f"\n[6] Engine Stats:")
        for k, v in engine.stats.items():
            print(f"    {k}: {v}")

    finally:
        engine.shutdown()

    print("\n" + "=" * 60)
    print("  Pipeline completed successfully!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
