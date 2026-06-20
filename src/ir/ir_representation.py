"""IR 数据结构 — 中间表示核心类型.

定义 IR 节点、IR 输出 等核心不可变数据结构。
"""

from src.core.processing_layer.ir_transpiler import IRNode, IROutput, TargetLanguage

__all__ = ["IROutput", "IRNode", "TargetLanguage"]
