"""IR 目标语言转译器."""

from src.ir.targets.cpp_target import CppTarget
from src.ir.targets.java_target import JavaTarget
from src.ir.targets.javascript_target import JavaScriptTarget
from src.ir.targets.rust_target import RustTarget
from src.ir.targets.wasm_target import WasmTarget

__all__ = ["JavaScriptTarget", "JavaTarget", "CppTarget", "RustTarget", "WasmTarget"]
