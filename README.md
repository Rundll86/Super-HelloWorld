# Super-HelloWorld

> **企业级 Hello World 打印基础设施**  
> 跨平台 · 跨设备 · 跨语言 · 99.999% 可用性

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Ruff](https://img.shields.io/badge/Lint-Ruff-amber)](https://docs.astral.sh/ruff/)
[![Mypy](https://img.shields.io/badge/Type-Mypy--strict-blue)](https://mypy-lang.org/)
[![Coverage](https://img.shields.io/badge/Coverage-90%25%2B-brightgreen)](.)
[![Tests](https://img.shields.io/badge/Tests-86%20passed-brightgreen)](.)

---

## 目录

- [1. 项目愿景](#1-项目愿景)
- [2. 架构设计](#2-架构设计)
- [3. 模块职责矩阵](#3-模块职责矩阵)
- [4. 快速开始](#4-快速开始)
- [5. 使用方式](#5-使用方式)
- [6. 开发指南](#6-开发指南)
- [7. 静态检查](#7-静态检查)
- [8. 测试](#8-测试)
- [9. 部署](#9-部署)
- [10. CI/CD 流水线](#10-cicd-流水线)
- [11. 技术规范摘要](#11-技术规范摘要)

---

## 1. 项目愿景

构建一个**跨平台、跨设备、跨语言**的企业级 "Hello World" 打印基础设施。确保在任何设备、任何平台、任何网络条件下，系统都能以 **99.999%** 的可用性稳定输出 `Hello World`。

### 核心目标

| 维度 | 目标 |
|------|------|
| **可靠性** | 五个九可用性 (99.999%)，年停机时间 < 5 分钟 |
| **兼容性** | 支持 Windows / Linux / macOS 三大平台 |
| **多设备** | 控制台、文件、网络、云端四种输出设备 |
| **多语言** | 将 Hello World 转译为 JavaScript / Java / C++ / Rust / WASM 五种目标语言 |
| **安全性** | 内置恶意打印检测、全角字符注入防御、缓冲区溢出保护 |
| **可观测性** | 结构化日志、Prometheus 指标、分布式追踪 |

---

## 2. 架构设计

系统采用 **4 层分层架构 + CLI 控制层 + 云服务层**，严格遵循依赖倒置原则，上层不直接依赖下层实现。

```
┌─────────────────────────────────────────────────────────┐
│                    CLI / API 控制层                       │
│                  (cli.py / main.py)                      │
├─────────────────────────────────────────────────────────┤
│                处理层 (Processing Layer)                  │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │ Output    │ │ Renderer │ │Scheduler │ │ Security  │ │
│  │ Stream    │ │          │ │(Cron)    │ │ Monitor   │ │
│  └───────────┘ └──────────┘ └──────────┘ └───────────┘ │
│  ┌─────────────────────────────────────────────────────┐ │
│  │         IR Transpiler (多语言中间表示)                │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                转接层 (Adapter Layer)                     │
│  ┌────────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │  BufferStack   │ │StreamAdapter │ │ProtocolAdapter │ │
│  │  (缓冲区栈)     │ │ (流适配器)    │ │ (协议适配器)    │ │
│  └────────────────┘ └──────────────┘ └────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                 设备层 (Device Layer)                     │
│  ┌────────────────┐ ┌──────────────┐ ┌────────────────┐ │
│  │CharacterReader │ │DeviceManager │ │DeviceInterface │ │
│  └────────────────┘ └──────────────┘ └────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Console  │ │  File    │ │ Network  │ │  Cloud    │  │
│  │ Device   │ │  Device  │ │ Device   │ │  Device   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
├─────────────────────────────────────────────────────────┤
│                  云服务层 (Cloud Layer)                   │
│  ┌─────────────────────────────────────────────────────┐ │
│  │          LogUploader (异步批量日志实时上云)            │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 设计模式

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **抽象工厂** | `DeviceManager.create_device()` | 按设备类型创建具体实例 |
| **单例** | `DeviceManager`, `SecurityMonitor` | 全局唯一实例，线程安全 |
| **观察者** | `OutputStream` → 设备订阅 | 数据变更时自动推送到所有订阅设备 |
| **责任链** | `SecurityMonitor` 扫描规则 | 消息依次通过多条安全检测规则 |
| **策略** | `StreamAdapter` 编码转换 | 运行时切换 UTF-8/ASCII/Base64/Hex 等策略 |
| **命令** | CLI 子命令 (`print`, `ir`, `security`) | 将请求封装为独立命令对象 |

---

## 3. 模块职责矩阵

| 模块 | 所属层 | 职责描述 | 上游依赖 |
|------|--------|---------|---------|
| `CharacterReader` | 设备层 | 字符序列读取与解析，支持多种字符集 | — |
| `DeviceManager` | 设备层 | 设备注册、发现、激活、生命周期管理 | `AbstractDevice` |
| `AbstractDevice` | 设备层 | 设备抽象接口（`write` / `flush` / `close`） | — |
| `ConsoleDevice` | 设备层 | 控制台标准输出设备 | `AbstractDevice` |
| `FileDevice` | 设备层 | 文件系统输出设备，支持追加/覆盖模式 | `AbstractDevice` |
| `CloudDevice` | 设备层 | 云端缓冲输出设备，支持批量刷新 | `AbstractDevice` |
| `NetworkDevice` | 设备层 | 网络 Socket 输出设备 | `AbstractDevice` |
| `BufferStack` | 转接层 | 基于双端队列的字符缓冲区，LIFO/FIFO 可切换 | — |
| `StreamAdapter` | 转接层 | 编码转换与流转码（UTF-8/UTF-16/ASCII/GBK/Base64/Hex） | `BufferStack` |
| `ProtocolAdapter` | 转接层 | IR → 设备协议转换，命令构建与协商 | `StreamAdapter` |
| `OutputStream` | 处理层 | 输出字符流调度中心（观察者模式） | `ProtocolAdapter` |
| `Renderer` | 处理层 | 多风格渲染引擎（Plain / Colored / JSON / XML / Minimal） | `OutputStream` |
| `CronScheduler` | 处理层 | 基于 Cron 表达式的定时打印调度器 | `Renderer` |
| `SecurityMonitor` | 处理层 | 恶意打印检测（全角注入 / 超大消息 / 控制字符） | `OutputStream` |
| `IRTranspiler` | 处理层 | Hello World → 多目标语言 AST IR 转译 | — |
| `LogUploader` | 云服务层 | 异步批量日志上传至 AWS / Azure / GCP | — |
| `HelloWorldEngine` | 控制层 | 完整流水线编排器，组装全部模块 | 全部 |
| CLI (`cli.py`) | 控制层 | 命令行交互入口，argparse 子命令体系 | `HelloWorldEngine` |

---

## 4. 快速开始

### 环境要求

- **Python** ≥ 3.10
- **Git**
- **Docker** (可选，用于容器化部署)

### 安装

```powershell
# 1. 克隆仓库
git clone <repo-url> super-helloworld
cd super-helloworld

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装开发依赖（可选）
pip install -r requirements-dev.txt
```

---

## 5. 使用方式

### 5.1 Demo 模式（一键体验完整流水线）

```powershell
python -m src.main
```

自动执行：设备注册 → 字符读取 → 缓冲推入 → 多风格渲染 → 安全扫描 → 云端日志上传 → Prometheus 指标暴露。

### 5.2 CLI 命令行

```powershell
# 打印 Hello World（彩色风格）
python -m src.cli print --message "Hello World" --style colored

# 输出到文件
python -m src.cli print --message "Hello" --device file --output hello.log

# 指定编码
python -m src.cli print --message "你好世界" --encoding gbk

# 重复打印
python -m src.cli print --message "Hi" --repeat 5

# 安全扫描
python -m src.cli security scan --message "Clean message"
python -m src.cli security scan --message "Ｈｅｌｌｏ　Ｗｏｒｌｄ"  # 检测全角注入

# IR 代码转译
python -m src.cli ir transpile --target javascript
python -m src.cli ir transpile --target rust
python -m src.cli ir transpile --target wasm --output ir_result.json

# 查看设备列表
python -m src.cli device list

# 查看版本
python -m src.cli --version

# 帮助信息
python -m src.cli --help
python -m src.cli print --help
```

### 5.3 Python API

```python
from src.main import HelloWorldEngine

# 初始化引擎并运行默认流水线
engine = HelloWorldEngine()
engine.setup_default_pipeline()

# 打印 Hello World
result = engine.print_hello_world()
print(result)  # Hello World

# 自定义消息打印
custom = engine.print_message("你好，世界！", style="colored")
print(custom.output)
```

---

## 6. 开发指南

### 6.1 项目结构

```
super-helloworld/
├── src/
│   ├── main.py                  # HelloWorldEngine — 流水线编排器
│   ├── cli.py                   # CLI 命令行入口
│   ├── core/
│   │   ├── device_layer/        # 设备层
│   │   │   ├── device_interface.py   # AbstractDevice 抽象接口
│   │   │   ├── device_manager.py     # DeviceManager 单例工厂
│   │   │   ├── character_reader.py   # CharacterReader 字符读取器
│   │   │   └── devices/              # 具体设备实现
│   │   │       ├── console_device.py
│   │   │       ├── file_device.py
│   │   │       ├── cloud_device.py
│   │   │       └── network_device.py
│   │   ├── adapter_layer/       # 转接层
│   │   │   ├── buffer_stack.py       # BufferStack 缓冲区栈
│   │   │   ├── stream_adapter.py     # StreamAdapter 流适配器
│   │   │   └── protocol_adapter.py   # ProtocolAdapter 协议适配器
│   │   └── processing_layer/    # 处理层
│   │       ├── output_stream.py      # OutputStream 输出流
│   │       ├── renderer.py           # Renderer 渲染引擎
│   │       ├── scheduler.py          # CronScheduler 定时调度
│   │       ├── security_monitor.py   # SecurityMonitor 安全监控
│   │       └── ir_transpiler.py      # IRTranspiler 多语言转译
│   ├── ir/                      # 中间表示及目标语言
│   │   ├── ir_representation.py
│   │   └── targets/
│   │       ├── javascript_target.py
│   │       ├── java_target.py
│   │       ├── cpp_target.py
│   │       ├── rust_target.py
│   │       └── wasm_target.py
│   └── cloud/                   # 云服务层
│       └── log_uploader.py      # LogUploader 异步批量上传
├── tests/
│   └── test_all.py              # 全部 86 个单元测试
├── k8s/                         # Kubernetes 部署清单
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── docker-compose.yml           # Docker Compose 多服务编排
├── Dockerfile                   # 多阶段 Docker 构建
├── pyproject.toml               # 项目配置 (ruff / mypy / pytest / bandit)
├── requirements.txt             # 生产依赖
├── requirements-dev.txt         # 开发依赖
├── SPEC.md                      # 详细技术规范
├── PLAN.md                      # CI/CD 流程规划
└── README.md                    # 本文件
```

### 6.2 编码规范

| 类别 | 规范 |
|------|------|
| Python 版本 | ≥ 3.10 |
| 类型注解 | 所有公共方法必须包含完整类型注解 |
| 文档字符串 | Google Style Docstring |
| 代码格式化 | Black (line-length=100) |
| 导入顺序 | `__future__` → stdlib → third-party → first-party |
| 命名 | 类 PascalCase / 函数 snake_case / 常量 UPPER_SNAKE / 私有 `_前缀` |
| 不可变性 | 核心数据结构使用 `@dataclass(frozen=True)` |
| 线程安全 | 缓冲区使用 `threading.RLock` 可重入锁；云端上传使用 `threading.Event` |

---

## 7. 静态检查

项目配置了严格的静态检查流水线，所有检查必须在 CI 中通过方可合并。

```powershell
# Lint 检查 (ruff)
ruff check src/ tests/

# 自动修复
ruff check --fix src/ tests/

# 类型检查 (mypy strict 模式)
mypy src/

# 安全审计 (bandit)
bandit -r src/

# 一键运行全部检查
ruff check src/ tests/ && mypy src/ && bandit -r src/
```

> **当前状态**: ruff 0 错误 / mypy strict 0 错误 / bandit 0 问题 ✅

---

## 8. 测试

### 运行测试

```powershell
# 运行全部测试
pytest tests/ -v

# 带覆盖率报告
pytest tests/ -v --cov=src --cov-report=term-missing

# 指定超时（防止死锁卡住）
pytest tests/ -v --timeout=30

# 只运行特定模块的测试
pytest tests/ -v -k "BufferStack"
pytest tests/ -v -k "CLI"
```

### 测试覆盖范围

| 测试类 | 测试数量 | 覆盖模块 |
|--------|---------|---------|
| `TestDeviceInterface` | 3 | 设备接口枚举与数据类 |
| `TestCharacterReader` | 6 | 字符读取与流操作 |
| `TestDeviceManager` | 6 | 设备管理器 CRUD |
| `TestConsoleDevice` | 2 | 控制台设备 |
| `TestFileDevice` | 1 | 文件设备 |
| `TestCloudDevice` | 2 | 云端设备 |
| `TestBufferStack` | 10 | 缓冲区栈全部操作 |
| `TestStreamAdapter` | 6 | 编码转换与转义 |
| `TestProtocolAdapter` | 3 | 协议构建与协商 |
| `TestRenderer` | 7 | 多风格渲染 |
| `TestOutputStream` | 4 | 输出流订阅与分发 |
| `TestScheduler` | 4 | Cron 调度器 |
| `TestSecurityMonitor` | 5 | 安全扫描规则 |
| `TestIRTranspiler` | 7 | 多语言 IR 转译 |
| `TestLogUploader` | 3 | 异步日志上传 |
| `TestIntegration` | 3 | 完整流水线集成 |
| `TestCLI` | 7 | 命令行接口 |
| `TestConcurrency` | 1 | 并发安全 |
| **合计** | **86** | 全部模块 |

> **覆盖率要求**: ≥ 90%，当前全部 86 个测试通过 ✅

---

## 9. 部署

### 9.1 Docker

```powershell
# 构建镜像
docker build -t super-helloworld .

# 运行容器
docker run -d -p 9090:9090 super-helloworld

# Docker Compose 一键部署（含调度器 + Prometheus + Grafana）
docker compose up -d

# 启动监控面板
docker compose --profile monitoring up -d

# 查看日志
docker compose logs -f

# 停止并清理
docker compose down -v
```

### 9.2 Kubernetes

```powershell
# 部署到 K8s 集群
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# 查看部署状态
kubectl get pods -l app=super-helloworld
kubectl logs -f deployment/super-helloworld
```

### 9.3 部署架构

```
                    ┌──────────────┐
                    │   Ingress    │
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │                         │
        ┌─────┴─────┐            ┌──────┴──────┐
        │  Service   │            │  Prometheus │
        │  :9090     │            │  :9091      │
        └─────┬─────┘            └──────┬──────┘
              │                         │
    ┌─────────┴─────────┐        ┌──────┴──────┐
    │   Deployment      │        │   Grafana   │
    │   replicas: 3-10  │        │   :3000     │
    │   HPA: CPU > 60%  │        └─────────────┘
    └───────────────────┘
```

---

## 10. CI/CD 流水线

CI/CD 在代码推送时自动触发，完整流水线包含 7 个阶段：

| 阶段 | 内容 | 超时 |
|------|------|------|
| **1. Lint & Format** | Ruff + Black + Mypy strict | 5 min |
| **2. Unit Tests** | pytest (Python 3.10/3.11/3.12 × Linux/Windows/macOS) | 15 min |
| **3. Security Scan** | Bandit + Safety + Trivy + Secret 检测 | 10 min |
| **4. Build** | Docker 多阶段构建 | 10 min |
| **5. Integration Test** | docker-compose 集成栈验证 | 20 min |
| **6. IR Validation** | 验证全部 5 种目标语言 IR 生成 | 5 min |
| **7. Push Artifacts** | Docker Registry + PyPI 发布 | 5 min |

### 分支策略

| 分支 | 用途 | 审批 |
|------|------|------|
| `main` | 生产就绪代码 | 2 人审批 |
| `develop` | 集成开发分支 | 1 人审批 |
| `feature/*` | 功能开发 | 无需审批 |
| `hotfix/*` | 紧急修复 | 1 人审批 |
| `release/*` | 发布候选 | 2 人审批 |

---

## 11. 技术规范摘要

### 设计原则

- **SOLID 原则**: 单一职责、开闭原则、里氏替换、接口隔离、依赖倒置
- **不可变数据**: 核心数据结构使用 `frozen=True` dataclass
- **防御式编程**: 参数校验、边界检查、异常层次化
- **线程安全**: `RLock` 可重入锁、`threading.Event` 信号量
- **零裸异常**: 所有异常类型必须显式指定

### 异常体系

```
SuperHelloWorldError (基类)
├── DeviceError
│   ├── DeviceAlreadyRegisteredError
│   └── DeviceNotFoundError
├── BufferError
│   ├── BufferOverflowError
│   └── BufferUnderflowError
├── RenderError
├── SecurityError
│   └── SecurityEvent
└── CloudUploadError
```

所有异常必须包含 `error_code: str` 与 `timestamp: float` 字段。

### 安全防护

- 全角/不可见字符注入检测
- 缓冲区溢出保护（`max_size` 硬限制）
- 超大消息拒绝（`max_message_length` 阈值）
- 控制字符过滤
- 高频打印限流（>100 次/秒触发告警）

### 可观测性

- **结构化日志**: `[timestamp] [level] [module] message`
- **Prometheus 指标**: 打印延迟 (p99)、吞吐量 (QPS)、失败率、缓冲区利用率
- **健康检查**: Docker HEALTHCHECK + Kubernetes liveness/readiness probe

---

## 许可证

MIT License © Enterprise Architecture Team

---

*本规范由 Enterprise Architecture Review Board 批准。任何违反 SPEC.md 规范的代码将被 CI Pipeline 自动拒绝。*
