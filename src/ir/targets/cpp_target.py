"""C++ 目标转译器."""

from src.core.processing_layer.ir_transpiler import (
    AbstractTranspiler,
    IROutput,
    IRNode,
    TargetLanguage,
)


class CppTarget:
    """C++ 转译入口."""

    def __init__(self) -> None:
        from src.core.processing_layer.ir_transpiler import CppTranspiler
        self._transpiler: AbstractTranspiler = CppTranspiler()

    def compile(self, message: str = "Hello World") -> IROutput:
        """编译为 C++."""
        from src.core.processing_layer.ir_transpiler import IRBuilder
        builder = IRBuilder()
        ir_tree = builder.build_custom(message) if message != "Hello World" else builder.build_hello_world()
        return self._transpiler.transpile(ir_tree)

    @property
    def target_language(self) -> TargetLanguage:
        return TargetLanguage.CPP
