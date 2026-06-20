"""CLI — 命令行接口，控制 Super-HelloWorld 全部配置.

支持的命令:
    print         : 打印 Hello World
    cron          : 管理定时任务
    device        : 管理输出设备
    ir            : IR 转译管理
    security      : 安全监控查询
    cloud         : 云日志管理

使用示例:
    $ super-helloworld print
    $ super-helloworld print --style colored --device file
    $ super-helloworld cron add --name "hourly-hello" --schedule "0 * * * *"
    $ super-helloworld ir transpile --target javascript
    $ super-helloworld device list
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass


@dataclass
class CLIConfig:
    """CLI 全局配置."""

    verbose: bool = False
    output_format: str = "text"  # text / json / yaml
    config_file: str | None = None


def _create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器."""
    parser = argparse.ArgumentParser(
        prog="super-helloworld",
        description="Enterprise-grade Hello World printing infrastructure",
        epilog="Built with 200% over-engineering by Enterprise Architecture Team.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="super-helloworld v1.0.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ---- print ----
    print_parser = subparsers.add_parser("print", help="Print Hello World")
    print_parser.add_argument(
        "--message",
        "-m",
        default="Hello World",
        help="Custom message to print",
    )
    print_parser.add_argument(
        "--style",
        "-s",
        choices=["plain", "colored", "rich", "minimal", "json", "xml"],
        default="plain",
        help="Render style (default: plain)",
    )
    print_parser.add_argument(
        "--device",
        "-d",
        default="console",
        help="Target device type (console/file/network/cloud)",
    )
    print_parser.add_argument(
        "--output-file",
        "-o",
        default=None,
        help="Output file path (for file device)",
    )
    print_parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Character encoding (utf-8/ascii/gbk/utf-16)",
    )
    print_parser.add_argument(
        "--repeat",
        "-n",
        type=int,
        default=1,
        help="Number of times to print",
    )

    # ---- cron ----
    cron_parser = subparsers.add_parser("cron", help="Manage cron schedules")
    cron_sub = cron_parser.add_subparsers(dest="cron_action")

    cron_add = cron_sub.add_parser("add", help="Add a cron job")
    cron_add.add_argument("--name", "-n", required=True, help="Job name")
    cron_add.add_argument("--schedule", "-s", required=True, help="Cron expression (5 fields)")
    cron_add.add_argument("--style", default="plain", help="Render style")

    cron_sub.add_parser("list", help="List all cron jobs")
    cron_sub.add_parser("start", help="Start the scheduler")
    cron_sub.add_parser("stop", help="Stop the scheduler")
    cron_sub.add_parser("status", help="Show scheduler status")

    cron_remove = cron_sub.add_parser("remove", help="Remove a cron job")
    cron_remove.add_argument("--name", "-n", required=True, help="Job name")

    cron_enable = cron_sub.add_parser("enable", help="Enable a cron job")
    cron_enable.add_argument("--name", "-n", required=True, help="Job name")

    cron_disable = cron_sub.add_parser("disable", help="Disable a cron job")
    cron_disable.add_argument("--name", "-n", required=True, help="Job name")

    # ---- device ----
    dev_parser = subparsers.add_parser("device", help="Manage output devices")
    dev_sub = dev_parser.add_subparsers(dest="device_action")

    dev_sub.add_parser("list", help="List registered devices")
    dev_register = dev_sub.add_parser("register", help="Register a device")
    dev_register.add_argument(
        "--type",
        "-t",
        required=True,
        choices=["console", "file", "network", "cloud"],
        help="Device type",
    )
    dev_register.add_argument("--id", required=True, help="Device ID")
    dev_register.add_argument("--path", default=None, help="File path (file device)")
    dev_register.add_argument("--host", default="localhost", help="Host (network device)")
    dev_register.add_argument("--port", type=int, default=9999, help="Port (network device)")
    dev_register.add_argument(
        "--provider",
        default="aws",
        choices=["aws", "gcp", "azure", "aliyun"],
        help="Cloud provider",
    )

    dev_remove = dev_sub.add_parser("remove", help="Remove a device")
    dev_remove.add_argument("--id", required=True, help="Device ID")

    dev_activate = dev_sub.add_parser("activate", help="Activate a device")
    dev_activate.add_argument("--id", required=True, help="Device ID")

    dev_sub.add_parser("metrics", help="Show device metrics")

    # ---- ir ----
    ir_parser = subparsers.add_parser("ir", help="IR transpilation management")
    ir_sub = ir_parser.add_subparsers(dest="ir_action")

    ir_transpile = ir_sub.add_parser("transpile", help="Transpile Hello World to target language")
    ir_transpile.add_argument(
        "--target",
        "-t",
        choices=["javascript", "java", "cpp", "rust", "wasm"],
        required=True,
        help="Target language",
    )
    ir_transpile.add_argument("--message", "-m", default="Hello World", help="Custom message")

    ir_sub.add_parser("all", help="Transpile to all supported languages")
    ir_sub.add_parser("ir-tree", help="Show the IR tree")
    ir_export = ir_sub.add_parser("export", help="Export all transpiled files")
    ir_export.add_argument("--output-dir", "-o", default="./output", help="Output directory")

    # ---- security ----
    sec_parser = subparsers.add_parser("security", help="Security monitor management")
    sec_sub = sec_parser.add_subparsers(dest="security_action")

    sec_sub.add_parser("stats", help="Show security statistics")
    sec_sub.add_parser("events", help="Show recent security events")
    sec_scan = sec_sub.add_parser("scan", help="Scan a message for threats")
    sec_scan.add_argument("--message", "-m", required=True, help="Message to scan")

    # ---- cloud ----
    cloud_parser = subparsers.add_parser("cloud", help="Cloud log management")
    cloud_sub = cloud_parser.add_subparsers(dest="cloud_action")

    cloud_sub.add_parser("stats", help="Show cloud upload statistics")
    cloud_sub.add_parser("start", help="Start cloud log uploader")
    cloud_sub.add_parser("stop", help="Stop cloud log uploader")

    return parser


def run_cli(args: list[str] | None = None) -> int:
    """运行 CLI — 主入口.

    Args:
        args: 命令行参数列表 (默认 sys.argv[1:]).

    Returns:
        退出码 (0 成功, 1 失败).
    """
    parser = _create_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    try:
        return _dispatch(parsed)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    """分发命令到对应处理函数."""
    command = args.command
    output_format = getattr(args, "format", "text")

    handlers = {
        "print": _cmd_print,
        "cron": _cmd_cron,
        "device": _cmd_device,
        "ir": _cmd_ir,
        "security": _cmd_security,
        "cloud": _cmd_cloud,
    }

    handler = handlers.get(command)
    if handler is None:
        print(f"Unknown command: {command}", file=sys.stderr)
        return 1

    result = handler(args)

    if output_format == "json" and result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif result is not None and isinstance(result, str):
        print(result)
    elif isinstance(result, dict):
        _print_dict(result)

    return 0


# ============================================================
# 命令处理函数
# ============================================================


def _cmd_print(args: argparse.Namespace) -> dict | None:
    """处理 print 命令."""
    from src.cloud.log_uploader import LogUploader
    from src.core.adapter_layer.buffer_stack import BufferStack
    from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
    from src.core.device_layer.character_reader import CharacterReader, CharacterSet
    from src.core.device_layer.device_interface import DeviceType
    from src.core.device_layer.device_manager import DeviceManager
    from src.core.processing_layer.output_stream import OutputStream
    from src.core.processing_layer.renderer import Renderer, RenderStyle
    from src.core.processing_layer.security_monitor import SecurityMonitor

    message = args.message
    style = RenderStyle(args.style)
    encoding = CharacterSet(args.encoding.upper().replace("-", ""))
    device_type = DeviceType[args.device.upper()]

    # 1. 设备层: 注册设备
    dm = DeviceManager.get_instance()
    device = dm.create_device(
        device_type,
        file_path=args.output_file or "/tmp/hello.log",  # nosec B108 — CLI default path
    )
    dm.register(device)
    dm.activate(device.device_id)

    # 2. 读取字符
    reader = CharacterReader()
    char_stream = reader.read(message, encoding=encoding)

    # 3. 推入缓冲区
    buffer = BufferStack(max_size=65536)
    buffer.push_all([t.char for t in char_stream])

    # 4. 渲染
    renderer = Renderer(default_style=style)
    rendered = renderer.render(message, style=style)

    # 5. 安全扫描
    monitor = SecurityMonitor.get_instance()
    sec_event = monitor.scan(rendered.output, {"source": "cli", "device_id": device.device_id})

    # 6. 输出
    adapter = ProtocolAdapter()
    adapter.negotiate(device)
    stream = OutputStream(buffer=buffer, protocol_adapter=adapter)
    stream.subscribe_device(device)

    results: dict = {"prints": []}
    for i in range(args.repeat):
        res = stream.emit(rendered.output)
        results["prints"].append({"index": i + 1, "result": res})

    # 7. 云端日志
    uploader = LogUploader()
    uploader.start()
    uploader.log_hello_world(device.device_id, success=True)
    uploader.stop()

    results["device"] = device.device_id
    results["style"] = style.value
    results["encoding"] = encoding.value
    results["char_count"] = len(char_stream)

    if sec_event:
        results["security_alert"] = {
            "level": sec_event.level.value,
            "message": sec_event.message,
        }

    return results


def _cmd_cron(args: argparse.Namespace) -> dict | None:
    """处理 cron 命令."""
    from src.core.adapter_layer.buffer_stack import BufferStack
    from src.core.adapter_layer.protocol_adapter import ProtocolAdapter
    from src.core.device_layer.device_manager import DeviceManager
    from src.core.processing_layer.output_stream import OutputStream
    from src.core.processing_layer.renderer import Renderer, RenderStyle
    from src.core.processing_layer.scheduler import CronScheduler

    scheduler = CronScheduler()
    action = args.cron_action

    if action == "add":
        _ = DeviceManager.get_instance()
        buffer = BufferStack()
        adapter = ProtocolAdapter()
        stream = OutputStream(buffer=buffer, protocol_adapter=adapter)
        renderer = Renderer(default_style=RenderStyle(args.style or "plain"))
        scheduler.add_hello_world_job(
            job_id=args.name,
            cron_expression=args.schedule,
            renderer=renderer,
            output_stream=stream,
        )
        return {"status": "added", "job": args.name, "schedule": args.schedule}

    elif action == "list":
        jobs = scheduler.list_jobs()
        return {
            "jobs": [
                {
                    "id": j.job_id,
                    "cron": j.cron_expression,
                    "enabled": j.enabled,
                    "runs": j.run_count,
                }
                for j in jobs
            ]
        }

    elif action == "start":
        scheduler.start()
        return {"status": "started"}

    elif action == "stop":
        scheduler.stop()
        return {"status": "stopped"}

    elif action == "status":
        return scheduler.get_stats()

    elif action == "remove":
        scheduler.remove_job(args.name)
        return {"status": "removed", "job": args.name}

    elif action == "enable":
        scheduler.enable_job(args.name)
        return {"status": "enabled", "job": args.name}

    elif action == "disable":
        scheduler.disable_job(args.name)
        return {"status": "disabled", "job": args.name}

    return {"error": "Unknown cron action"}


def _cmd_device(args: argparse.Namespace) -> dict | None:
    """处理 device 命令."""
    from src.core.device_layer.device_interface import DeviceType
    from src.core.device_layer.device_manager import DeviceManager

    dm = DeviceManager.get_instance()
    action = args.device_action

    if action == "list":
        devices = dm.list_devices()
        return {
            "devices": [
                {
                    "id": d.device_id,
                    "type": d.device_type.name,
                    "status": d.status.name,
                    "available": d.is_available,
                }
                for d in devices
            ]
        }

    elif action == "register":
        device_type = DeviceType[args.type.upper()]
        kwargs = {"device_id": args.id}
        if args.type == "file" and args.path:
            kwargs["file_path"] = args.path
        elif args.type == "network":
            kwargs["host"] = args.host
            kwargs["port"] = args.port
        elif args.type == "cloud":
            from src.core.device_layer.devices.cloud_device import CloudProvider

            kwargs["provider"] = CloudProvider(args.provider)

        device = dm.create_device(device_type, **kwargs)
        dm.register(device)
        dm.activate(device.device_id)
        return {"status": "registered", "device_id": device.device_id}

    elif action == "remove":
        dm.unregister(args.id)
        return {"status": "removed", "device_id": args.id}

    elif action == "activate":
        dm.activate(args.id)
        return {"status": "activated", "device_id": args.id}

    elif action == "metrics":
        devices = dm.list_devices()
        return {
            "metrics": [
                {
                    "id": d.device_id,
                    "bytes_written": d.metrics.bytes_written,
                    "write_count": d.metrics.write_count,
                    "error_count": d.metrics.error_count,
                    "avg_latency_ms": round(d.metrics.avg_latency_ms, 3),
                }
                for d in devices
            ]
        }

    return {"error": "Unknown device action"}


def _cmd_ir(args: argparse.Namespace) -> dict | str | None:
    """处理 ir 命令."""
    from src.core.processing_layer.ir_transpiler import IRTranspiler, TargetLanguage

    transpiler = IRTranspiler()
    action = args.ir_action

    if action == "transpile":
        target = TargetLanguage(args.target)
        output = transpiler.transpile_to(target, message=args.message)
        print(output.source_code)
        return None

    elif action == "all":
        outputs = transpiler.transpile_all()
        for lang, out in outputs.items():
            print(f"===== {lang.value} =====")
            print(out.source_code)
        return None

    elif action == "ir-tree":
        return transpiler.export_ir_json()

    elif action == "export":
        result = transpiler.export_all_to_files(args.output_dir)
        return {
            "status": "exported",
            "output_dir": args.output_dir,
            "files": {lang.value: path for lang, path in result.items()},
        }

    return {"error": "Unknown IR action"}


def _cmd_security(args: argparse.Namespace) -> dict | None:
    """处理 security 命令."""
    from src.core.processing_layer.security_monitor import SecurityMonitor

    monitor = SecurityMonitor.get_instance()
    action = args.security_action

    if action == "stats":
        return monitor.get_stats()

    elif action == "events":
        events = monitor.get_events()
        return {
            "events": [
                {
                    "level": e.level.value,
                    "rule": e.rule_name,
                    "message": e.message,
                    "source": e.source,
                }
                for e in events
            ]
        }

    elif action == "scan":
        event = monitor.scan(args.message, {"source": "cli-scan"})
        if event:
            return {
                "threat_detected": True,
                "level": event.level.value,
                "rule": event.rule_name,
                "message": event.message,
            }
        return {"threat_detected": False, "message": "Clean"}

    return {"error": "Unknown security action"}


def _cmd_cloud(args: argparse.Namespace) -> dict | None:
    """处理 cloud 命令."""
    from src.cloud.log_uploader import LogUploader

    uploader = LogUploader()
    action = args.cloud_action

    if action == "stats":
        return uploader.stats

    elif action == "start":
        uploader.start()
        return {"status": "started"}

    elif action == "stop":
        uploader.stop()
        return {"status": "stopped"}

    return {"error": "Unknown cloud action"}


# ============================================================
# 工具函数
# ============================================================


def _print_dict(data: dict, indent: int = 0) -> None:
    """递归打印字典."""
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            _print_dict(value, indent + 1)
        elif isinstance(value, list):
            print(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    _print_dict(item, indent + 2)
                    print()
                else:
                    print(f"{prefix}  - {item}")
        else:
            print(f"{prefix}{key}: {value}")


if __name__ == "__main__":
    sys.exit(run_cli())
