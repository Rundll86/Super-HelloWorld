# PLAN.md — Super-HelloWorld CI/CD 实时流程规划

> **版本**: v1.0.0  
> **作者**: DevOps & Platform Engineering Team  
> **最后更新**: 2026-06-20

---

## 目录

1. [CI/CD 流水线总览](#1-cicd-流水线总览)
2. [分支策略](#2-分支策略)
3. [CI 阶段详解](#3-ci-阶段详解)
4. [CD 阶段详解](#4-cd-阶段详解)
5. [环境矩阵](#5-环境矩阵)
6. [监控与告警](#6-监控与告警)
7. [回滚策略](#7-回滚策略)
8. [灾难恢复](#8-灾难恢复)

---

## 1. CI/CD 流水线总览

```
Git Push
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│                    CI Pipeline (GitHub Actions)                │
│                                                                │
│  Stage 1: Lint & Format    →  Ruff + Black + MyPy            │
│  Stage 2: Unit Tests       →  pytest + coverage (>=90%)      │
│  Stage 3: Security Scan    →  Bandit + Safety + Trivy        │
│  Stage 4: Build            →  Docker multi-stage build       │
│  Stage 5: Integration Test →  docker-compose test stack      │
│  Stage 6: IR Validation    →  验证所有目标语言IR生成          │
│  Stage 7: Push Artifacts   →  Docker Registry + PyPI         │
│                                                                │
└──────────────┬───────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│                    CD Pipeline (ArgoCD / Flux)                 │
│                                                                │
│  Stage 1: Dev Deploy       →  dev cluster (自动)              │
│  Stage 2: Staging Deploy   →  staging cluster (自动)          │
│  Stage 3: Canary Deploy    →  production 10% 流量 (自动)     │
│  Stage 4: Smoke Test       →  Hello World 验证 (自动)        │
│  Stage 5: Full Rollout     →  production 100% (手动审批)     │
│  Stage 6: Post-deploy      →  监控 + 日志验证 (自动)         │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

## 2. 分支策略

| 分支 | 用途 | 环境 | 审批 |
|------|------|------|------|
| `main` | 生产就绪代码 | Production | Required (2 approvers) |
| `develop` | 集成开发分支 | Staging | Required (1 approver) |
| `feature/*` | 功能开发 | Dev (per-branch) | None |
| `hotfix/*` | 紧急修复 | All | Required (1 approver) |
| `release/*` | 发布候选 | Staging → Prod | Required (2 approvers) |

### 分支保护规则

- `main`: 禁止直接 push，必须通过 PR，需要 CI 全绿
- `develop`: 需要 CI Lint+Test 通过
- 所有 PR 必须关联 Issue / User Story

## 3. CI 阶段详解

### Stage 1: Lint & Format

```yaml
触发: push / pull_request
运行: ubuntu-latest
步骤:
  1. Checkout 代码
  2. Setup Python 3.12
  3. pip install ruff black mypy
  4. ruff check src/ tests/
  5. black --check --diff src/ tests/
  6. mypy --strict src/
超时: 5min
失败: 阻止后续阶段
```

### Stage 2: Unit Tests

```yaml
触发: Stage 1 通过
矩阵:
  python: [3.10, 3.11, 3.12]
  os: [ubuntu-latest, windows-latest, macos-latest]
步骤:
  1. Setup Python
  2. pip install -r requirements-dev.txt
  3. pytest --cov=src --cov-report=xml --cov-fail-under=90
  4. 上传覆盖率到 Codecov
超时: 15min
```

### Stage 3: Security Scan

```yaml
触发: Stage 2 通过
步骤:
  1. Bandit 静态安全分析
  2. Safety 依赖漏洞检查
  3. Trivy Docker 镜像扫描
  4. Secret 泄露检测 (trufflehog)
超时: 10min
```

### Stage 4: Build

```yaml
触发: Stage 3 通过
步骤:
  1. docker build --target production -t super-helloworld:${GITHUB_SHA}
  2. docker tag 版本号
  3. docker save 缓存
超时: 10min
```

### Stage 5: Integration Test

```yaml
触发: Stage 4 通过
步骤:
  1. docker compose -f docker-compose.test.yml up -d
  2. 等待健康检查通过
  3. 运行集成测试套件
  4. 验证 CLI 所有命令
  5. docker compose down
超时: 20min
```

### Stage 6: IR Validation

```yaml
触发: Stage 5 通过
步骤:
  1. 运行 IR 生成所有目标语言
  2. 验证生成的 AST 结构完整性
  3. 检查 source map 正确性
目标语言: JavaScript, Java, C++, Rust, WASM
```

### Stage 7: Push Artifacts

```yaml
触发: Stage 6 通过 (main 分支)
步骤:
  1. docker push 到容器仓库
  2. twine upload 到 PyPI
  3. 更新 Helm Chart 版本
```

## 4. CD 阶段详解

### 部署工具链

- **GitOps**: ArgoCD
- **Helm Chart**: `charts/super-helloworld/`
- **容器编排**: Kubernetes 1.28+
- **Service Mesh**: Istio (可选)

### Canary 发布策略

```
Step 1: 部署 canary-v2 (10% replicas)
Step 2: 等待 5min，监控错误率
Step 3: 如果错误率 < 0.01%，提升至 50%
Step 4: 等待 5min
Step 5: 如果一切正常，滚动更新至 100%
Step 6: 下线 canary-v1

任意步骤失败 → 自动回滚
```

## 5. 环境矩阵

| 环境 | 集群 | 副本数 | 自动扩缩 | 域名 |
|------|------|--------|---------|------|
| dev | dev-k8s | 1 | No | dev-helloworld.internal |
| staging | staging-k8s | 2 | CPU > 70% | staging-helloworld.internal |
| production | prod-k8s (multi-AZ) | 3-10 | CPU > 60% | helloworld.enterprise.com |

## 6. 监控与告警

### 四大黄金信号

| 信号 | 指标 | 告警阈值 |
|------|------|---------|
| Latency | p99 打印延迟 | > 100ms |
| Traffic | Hello World 打印 QPS | 偏离基线 50% |
| Errors | 打印失败率 | > 0.1% |
| Saturation | 缓冲区使用率 | > 80% |

### 告警通道

1. PagerDuty (P1 - 打印服务不可用)
2. Slack #helloworld-alerts (P2 - 性能劣化)
3. Email (P3 - 恶意打印检测)

### Dashboard (Grafana)

- Hello World 打印实时计数
- 缓冲区栈深度
- 各设备输出延迟
- 恶意行为检测次数
- 云端日志上传成功率

## 7. 回滚策略

### 自动回滚条件

- 错误率 > 1% 持续 2min
- 健康检查连续失败 3 次
- 内存使用超过 limit 的 90%

### 回滚步骤

```
1. ArgoCD 自动触发 rollback 到上一个健康版本
2. 通知 on-call 工程师
3. 创建 postmortem 文档
4. 执行 RCA (Root Cause Analysis)
```

## 8. 灾难恢复

### RTO / RPO

- **RTO** (恢复时间目标): < 5 分钟
- **RPO** (恢复点目标): < 1 分钟 (云端日志)

### 灾备策略

- 多 AZ 部署 (至少 3 个)
- 跨 Region 云端日志复制
- 定期备份 IR 配置 (每日)
- 混沌工程测试 (每月)

### 演练计划

- 季度灾难恢复演练
- 年度全链路压测 (目标: 10000 QPS Hello World)

---

*本规划由 DevOps Center of Excellence 维护，任何修改需通过 RFC 流程。*
