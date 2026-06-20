"""WebAssembly 目标转译器."""

from src.core.processing_layer.ir_transpiler import (
    AbstractTranspiler,
    IROutput,
    TargetLanguage,
)


class WasmTarget:
    """WASM 转译入口."""

    def __init__(self) -> None:
        from src.core.processing_layer.ir_transpiler import WasmTranspiler
        self._transpiler: AbstractTranspiler = WasmTranspiler()

    def compile(self, message: str = "Hello World") -> IROutput:
        """编译为 WAT."""
        from src.core.processing_layer.ir_transpiler import IRBuilder
        builder = IRBuilder()
        ir_tree = builder.build_custom(message) if message != "Hello World" else builder.build_hello_world()
        return self._transpiler.transpile(ir_tree)

    @property
    def target_language(self) -> TargetLanguage:
        return TargetLanguage.WASM
