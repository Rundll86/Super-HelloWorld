# SPEC.md — Super-HelloWorld 企业级打印系统规范

> **版本**: v1.0.0  
> **作者**: Enterprise Architecture Team  
> **状态**: Approved  
> **最后更新**: 2026-06-20

---

## 目录

1. [项目愿景](#1-项目愿景)
2. [架构总览](#2-架构总览)
3. [分层设计规范](#3-分层设计规范)
4. [模块职责矩阵](#4-模块职责矩阵)
5. [编码规范](#5-编码规范)
6. [命名规范](#6-命名规范)
7. [接口契约](#7-接口契约)
8. [错误处理规范](#8-错误处理规范)
9. [日志与可观测性规范](#9-日志与可观测性规范)
10. [安全规范](#10-安全规范)
11. [测试规范](#11-测试规范)
12. [部署规范](#12-部署规范)

---

## 1. 项目愿景

构建一个**跨平台、跨设备、跨语言**的企业级 "Hello World" 打印基础设施。确保在任何设备、任何平台、任何网络条件下，系统都能以**99.999%** 的可用性稳定输出 `Hello World`。

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI 控制层                              │
│                    (cli.py / main.py)                         │
├─────────────────────────────────────────────────────────────┤
│                     处理层 (Processing Layer)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │Output    │ │Renderer  │ │Scheduler │ │Security       │  │
│  │Stream    │ │          │ │(Cron)    │ │Monitor        │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              IR Transpiler (多语言中间表示)            │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                   转接层 (Adapter Layer)                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐    │
│  │Buffer Stack  │ │Stream Adapter│ │Protocol Adapter  │    │
│  │(缓冲区栈)     │ │(流适配器)     │ │(协议适配器)       │    │
│  └──────────────┘ └──────────────┘ └──────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                    设备层 (Device Layer)                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐    │
│  │Character     │ │Device        │ │Device Interface  │    │
│  │Reader        │ │Manager       │ │(抽象设备接口)     │    │
│  └──────────────┘ └──────────────┘ └──────────────────┘    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │Console   │ │File      │ │Network   │ │Cloud         │  │
│  │Device    │ │Device    │ │Device    │ │Device        │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    云服务层 (Cloud Layer)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Log Uploader (日志实时上云)               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 3. 分层设计规范

### 3.1 设备层 (Device Layer)

**职责**：直接与物理/虚拟输出设备交互，封装设备差异。

- 所有设备实现 `AbstractDevice` 接口
- 字符读取器负责从字符集中提取目标字符序列
- 设备管理器采用**工厂模式 + 注册表模式**管理设备生命周期
- 设备支持热插拔（动态注册/注销）

### 3.2 转接层 (Adapter Layer)

**职责**：连接处理层与设备层，提供数据缓冲与协议转换。

- 缓冲区栈使用**双端队列**实现，支持 LIFO/FIFO 切换
- 流适配器负责字符编码转换 (UTF-8/UTF-16/ASCII/GBK)
- 协议适配器将内部 IR 转换为设备可理解的协议

### 3.3 处理层 (Processing Layer)

**职责**：核心业务逻辑，包括渲染、调度、安全和多语言转换。

- 输出流为**观察者模式**，设备作为订阅者
- 调度器基于 cron 表达式实现定时打印
- 安全监控器使用**责任链模式**检测恶意行为
- IR 转译器将 Hello World 转换为目标语言的 AST IR

## 4. 模块职责矩阵

| 模块 | 层 | 职责 | 依赖 |
|------|------|------|------|
| `CharacterReader` | 设备层 | 字符序列读取/解析 | 无 |
| `DeviceManager` | 设备层 | 设备注册/发现/生命周期 | `AbstractDevice` |
| `AbstractDevice` | 设备层 | 设备抽象接口定义 | 无 |
| `ConsoleDevice` | 设备层 | 控制台输出 | `AbstractDevice` |
| `FileDevice` | 设备层 | 文件输出 | `AbstractDevice` |
| `CloudDevice` | 设备层 | 云端输出 | `AbstractDevice` |
| `BufferStack` | 转接层 | 字符缓冲区栈 | 无 |
| `StreamAdapter` | 转接层 | 编码/流转换 | `BufferStack` |
| `ProtocolAdapter` | 转接层 | IR-设备协议转换 | `StreamAdapter` |
| `OutputStream` | 处理层 | 输出字符流调度 | `ProtocolAdapter` |
| `Renderer` | 处理层 | 字符渲染引擎 | `OutputStream` |
| `Scheduler` | 处理层 | Cron 定时调度 | `Renderer` |
| `SecurityMonitor` | 处理层 | 恶意打印检测 | `OutputStream` |
| `IRTranspiler` | 处理层 | 多语言 IR 转换 | 无 |
| `LogUploader` | 云服务层 | 日志云端存储 | 无 |
| `CLI` | 控制层 | 命令行接口 | 全部 |

## 5. 编码规范

### 5.1 通用规范

- **Python 版本**: >= 3.10
- **类型注解**: 所有公共方法必须有完整类型注解
- **文档字符串**: 使用 Google Style Docstring
- **代码格式化**: Black (line-length=100)
- **Lint**: Ruff
- **导入顺序**: `__future__` → stdlib → third-party → first-party

### 5.2 设计模式要求

- 抽象工厂 → 设备创建
- 单例 → 设备管理器、安全监控器
- 观察者 → 输出流
- 责任链 → 安全检查
- 策略 → 编码转换
- 命令 → CLI 操作

### 5.3 不可变性与线程安全

- 核心数据结构使用 `dataclass(frozen=True)`
- 缓冲区栈加 `threading.Lock`
- 设备管理器使用 `RLock` 可重入锁

## 6. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `character_reader.py` |
| 类 | PascalCase | `CharacterReader` |
| 函数/方法 | snake_case | `read_character()` |
| 常量 | UPPER_SNAKE | `MAX_BUFFER_SIZE` |
| 私有成员 | _leading_underscore | `_buffer` |
| 抽象方法 | 带 abstract 前缀装饰 | `abstract_device.py` |

## 7. 接口契约

### 7.1 AbstractDevice

```python
class AbstractDevice(ABC):
    @abstractmethod
    def write(self, data: str) -> int: ...
    @abstractmethod
    def flush(self) -> None: ...
    @abstractmethod
    def close(self) -> None: ...
    @property
    @abstractmethod
    def device_id(self) -> str: ...
    @property
    @abstractmethod
    def is_available(self) -> bool: ...
```

### 7.2 IROutput (中间表示输出)

```python
@dataclass(frozen=True)
class IROutput:
    message: str
    target_language: str
    ast_representation: dict
    source_map: dict
    encoding: str = "UTF-8"
```

## 8. 错误处理规范

- 使用自定义异常层次结构：
  - `SuperHelloWorldError` (基类)
  - `DeviceError`
  - `BufferError`
  - `RenderError`
  - `SecurityError`
  - `CloudUploadError`
- 所有异常必须包含 `error_code: str` 和 `timestamp: float`
- 不允许裸 `except:`，必须指定异常类型

## 9. 日志与可观测性规范

- 使用 `structlog` 结构化日志
- 日志级别：TRACE < DEBUG < INFO < WARN < ERROR < FATAL
- 每条日志包含：`timestamp`, `trace_id`, `module`, `action`, `result`
- Hello World 打印事件需记录完整审计日志
- 恶意行为检测触发 WARN 级别日志并上报

## 10. 安全规范

### 恶意打印检测规则

1. 非标准字符集打印 Hello World（如全角/不可见字符）
2. 高频打印（>100次/秒）
3. 非授权设备尝试输出
4. 缓冲区溢出攻击检测
5. 编码注入检测

## 11. 测试规范

- 单元测试覆盖率 >= 90%
- 使用 `pytest` + `pytest-cov`
- Mock 所有外部依赖
- 每个模块独立测试
- 集成测试覆盖完整打印流水线

## 12. 部署规范

### Docker

- 多阶段构建，最终镜像 < 200MB
- 非 root 用户运行
- HEALTHCHECK 指令
- 暴露 metrics 端口 9090

### Kubernetes

- Deployment replicas >= 3
- PodDisruptionBudget
- HorizontalPodAutoscaler
- ConfigMap 管理配置
- Secret 管理云凭证
- ServiceMonitor (Prometheus)

---

*本规范由 Enterprise Architecture Review Board 批准。任何违反此规范的代码将被 CI Pipeline 自动拒绝。*
