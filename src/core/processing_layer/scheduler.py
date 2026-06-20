"""定时调度器 — 基于 Cron 表达式的 Hello World 定时打印.

支持:
    - 标准 5 字段 cron 表达式
    - 预设 (每分/每时/每天/每周)
    - 带时区的调度
    - 优雅启动/停止
    - 作业失败重试
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.core.processing_layer.renderer import RenderResult, RenderStyle, Renderer
from src.core.processing_layer.output_stream import OutputStream

logger = logging.getLogger(__name__)


class SchedulePreset(Enum):
    """预设调度."""

    EVERY_MINUTE = "* * * * *"
    EVERY_5_MINUTES = "*/5 * * * *"
    EVERY_HOUR = "0 * * * *"
    EVERY_DAY_MIDNIGHT = "0 0 * * *"
    EVERY_WEEK_MONDAY = "0 0 * * 1"


@dataclass
class ScheduledJob:
    """调度作业."""

    job_id: str
    cron_expression: str
    callback: Callable[[], Any]
    enabled: bool = True
    last_run: Optional[float] = None
    run_count: int = 0
    error_count: int = 0
    max_retries: int = 3


@dataclass
class JobResult:
    """作业执行结果."""

    job_id: str
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class SchedulerError(Exception):
    """调度器错误."""

    def __init__(self, message: str, error_code: str = "SCHEDULER_ERROR") -> None:
        super().__init__(message)
        self.error_code: str = error_code
        self.timestamp: float = time.time()


class CronScheduler:
    """Cron 定时调度器.

    使用示例:
        >>> def print_hello():
        ...     print("Hello World")
        >>> scheduler = CronScheduler()
        >>> scheduler.add_job("hello", "* * * * *", print_hello)
        >>> scheduler.start()
        >>> # ... 运行中 ...
        >>> scheduler.stop()
    """

    # 支持的 cron 字段范围
    _FIELD_RANGES = [
        (0, 59),   # 分钟
        (0, 23),   # 小时
        (1, 31),   # 日
        (1, 12),   # 月
        (0, 6),    # 星期 (0=周日)
    ]

    def __init__(self, tz: Optional[timezone] = None) -> None:
        """初始化调度器.

        Args:
            tz: 时区.
        """
        self._jobs: Dict[str, ScheduledJob] = OrderedDict()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.RLock = threading.RLock()
        self._tz: timezone = tz or timezone.utc
        self._results: List[JobResult] = []
        self._max_results: int = 1000

    # ---- 作业管理 ----

    def add_job(
        self,
        job_id: str,
        cron_expression: str,
        callback: Callable[[], Any],
        enabled: bool = True,
        max_retries: int = 3,
    ) -> ScheduledJob:
        """添加定时作业.

        Args:
            job_id: 作业 ID.
            cron_expression: Cron 表达式.
            callback: 回调函数.
            enabled: 是否启用.
            max_retries: 最大重试次数.

        Returns:
            ScheduledJob 对象.

        Raises:
            SchedulerError: 作业 ID 重复或 cron 表达式无效.
        """
        self._validate_cron(cron_expression)

        with self._lock:
            if job_id in self._jobs:
                raise SchedulerError(
                    f"Job {job_id!r} already exists",
                    error_code="DUPLICATE_JOB",
                )
            job = ScheduledJob(
                job_id=job_id,
                cron_expression=cron_expression,
                callback=callback,
                enabled=enabled,
                max_retries=max_retries,
            )
            self._jobs[job_id] = job
            return job

    def add_hello_world_job(
        self,
        job_id: str,
        cron_expression: str,
        renderer: Renderer,
        output_stream: OutputStream,
        style: RenderStyle = RenderStyle.PLAIN,
    ) -> ScheduledJob:
        """添加 Hello World 打印作业.

        Args:
            job_id: 作业 ID.
            cron_expression: Cron 表达式.
            renderer: 渲染器.
            output_stream: 输出流.
            style: 渲染风格.

        Returns:
            ScheduledJob 对象.
        """

        def hello_world_task() -> Dict[str, Any]:
            result = renderer.render_hello_world(style=style)
            return output_stream.emit(result.output)

        return self.add_job(job_id, cron_expression, hello_world_task)

    def remove_job(self, job_id: str) -> None:
        """移除作业.

        Args:
            job_id: 作业 ID.
        """
        with self._lock:
            self._jobs.pop(job_id, None)

    def enable_job(self, job_id: str) -> None:
        """启用作业."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.enabled = True

    def disable_job(self, job_id: str) -> None:
        """禁用作业."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.enabled = False

    # ---- 生命周期 ----

    def start(self) -> None:
        """启动调度器 (后台线程).

        Raises:
            SchedulerError: 调度器已运行.
        """
        with self._lock:
            if self._running:
                raise SchedulerError("Scheduler is already running", error_code="ALREADY_RUNNING")
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="cron-scheduler",
                daemon=True,
            )
            self._thread.start()
            logger.info("CronScheduler started with %d jobs", len(self._jobs))

    def stop(self, timeout: float = 5.0) -> None:
        """停止调度器.

        Args:
            timeout: 等待线程结束的超时 (秒).
        """
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("CronScheduler stopped. Total runs: %d", self.total_runs)

    # ---- 主循环 ----

    def _run_loop(self) -> None:
        """调度器主循环 — 每秒检查一次."""
        while self._running:
            now = datetime.now(self._tz)
            for job in list(self._jobs.values()):
                if not job.enabled:
                    continue
                if self._should_run(job, now):
                    self._execute_job(job)
            time.sleep(1)

    def _should_run(self, job: ScheduledJob, now: datetime) -> bool:
        """判断作业是否应在当前时间执行."""
        cron_parts = job.cron_expression.split()
        return all(
            self._match_field(getattr(now, field, 0) if field != "weekday" else now.weekday(), part)
            for field, part in zip(
                ["minute", "hour", "day", "month", "weekday"],
                cron_parts,
            )
        )

    def _execute_job(self, job: ScheduledJob) -> None:
        """执行作业 (带重试)."""
        for attempt in range(job.max_retries + 1):
            try:
                start = time.perf_counter()
                output = job.callback()
                elapsed = (time.perf_counter() - start) * 1000

                job.last_run = time.time()
                job.run_count += 1

                result = JobResult(
                    job_id=job.job_id,
                    success=True,
                    output=output,
                    duration_ms=elapsed,
                )
                self._record_result(result)
                return

            except Exception as exc:
                if attempt == job.max_retries:
                    job.error_count += 1
                    result = JobResult(
                        job_id=job.job_id,
                        success=False,
                        output=None,
                        error=str(exc),
                    )
                    self._record_result(result)
                    logger.error(
                        "Job %s failed after %d retries: %s",
                        job.job_id,
                        job.max_retries,
                        exc,
                    )
                else:
                    time.sleep(min(2 ** attempt, 30))

    def _record_result(self, result: JobResult) -> None:
        """记录执行结果."""
        self._results.append(result)
        if len(self._results) > self._max_results:
            self._results = self._results[-self._max_results:]

    # ---- Cron 解析 ----

    @classmethod
    def _validate_cron(cls, expression: str) -> None:
        """验证 cron 表达式."""
        parts = expression.strip().split()
        if len(parts) != 5:
            raise SchedulerError(
                f"Cron expression must have 5 fields, got {len(parts)}",
                error_code="INVALID_CRON",
            )

    @staticmethod
    def _match_field(value: int, pattern: str) -> bool:
        """匹配单个 cron 字段.

        Args:
            value: 当前值.
            pattern: cron 模式 (*, */n, n, n-m, n,m,...).

        Returns:
            是否匹配.
        """
        if pattern == "*":
            return True

        # 处理逗号分隔的多个值
        if "," in pattern:
            return any(
                CronScheduler._match_single(value, p.strip())
                for p in pattern.split(",")
            )

        return CronScheduler._match_single(value, pattern)

    @staticmethod
    def _match_single(value: int, pattern: str) -> bool:
        """匹配单个 cron 模式."""
        # */n 步进
        if pattern.startswith("*/"):
            step = int(pattern[2:])
            return value % step == 0
        # n-m 范围
        if "-" in pattern:
            lo, hi = map(int, pattern.split("-"))
            return lo <= value <= hi
        # 精确匹配
        return int(pattern) == value

    # ---- 查询 ----

    @property
    def running(self) -> bool:
        """调度器是否运行中."""
        return self._running

    @property
    def total_runs(self) -> int:
        """总执行次数."""
        return sum(j.run_count for j in self._jobs.values())

    @property
    def total_errors(self) -> int:
        """总错误次数."""
        return sum(j.error_count for j in self._jobs.values())

    def list_jobs(self) -> List[ScheduledJob]:
        """列出所有作业."""
        with self._lock:
            return list(self._jobs.values())

    def get_results(self, limit: int = 10) -> List[JobResult]:
        """获取最近的执行结果."""
        return self._results[-limit:]

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """获取指定作业."""
        return self._jobs.get(job_id)

    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计."""
        return {
            "running": self._running,
            "job_count": len(self._jobs),
            "total_runs": self.total_runs,
            "total_errors": self.total_errors,
            "jobs": {
                jid: {
                    "enabled": j.enabled,
                    "cron": j.cron_expression,
                    "runs": j.run_count,
                    "errors": j.error_count,
                    "last_run": j.last_run,
                }
                for jid, j in self._jobs.items()
            },
        }

    def __repr__(self) -> str:
        return (
            f"CronScheduler(running={self._running}, "
            f"jobs={len(self._jobs)}, runs={self.total_runs})"
        )
