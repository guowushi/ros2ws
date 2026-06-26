"""PlcWorker — 后台线程，持有独立 asyncio 事件循环并封装 RobotPlc。

所有异步 PLC 操作在本线程的事件循环上运行，结果通过 Qt 信号投递回主线程。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

from modbus_pkg.config_parser import ModbusConfig
from modbus_pkg.robot_plc import RobotPlc, TagValue
from python_qt_binding.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class PlcWorker(QThread):
    """后台工作线程 — 管理 asyncio 事件循环和 RobotPlc 生命周期。

    主线程通过 ``schedule_*`` 方法提交异步任务，结果通过信号通知。
    """

    # ---- 信号 (跨线程投递到主线程) ----
    connection_changed = Signal(bool, str)
    """连接状态变化。参数: (connected: bool, message: str)。"""

    data_ready = Signal(dict)
    """读取完成。参数: results (dict[str, TagValue])。"""

    # ---- 构造与析构 ----

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config: Optional[ModbusConfig] = None
        self._plc: Optional[RobotPlc] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._shutdown_requested = False

    # ------------------------------------------------------------------
    #  QThread 生命周期
    # ------------------------------------------------------------------

    def run(self) -> None:
        """线程入口 — 创建事件循环并永久运行。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()  # 通知主线程事件循环已就绪
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()
            self._loop = None

    def stop_worker(self) -> None:
        """优雅关闭：断开 PLC → 停止事件循环 → 等待线程退出。

        在主线程调用，阻塞直到工作线程完全退出（最多等待 5 秒）。
        """
        self._shutdown_requested = True

        # 调度断开连接
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._do_shutdown(), self._loop)
            self._loop.call_soon_threadsafe(self._loop.stop)

        if not self.wait(5000):
            logger.warning("PlcWorker 线程未能及时退出")

    # ------------------------------------------------------------------
    #  主线程调用的公开接口 (非阻塞)
    # ------------------------------------------------------------------

    def set_config(self, config: ModbusConfig) -> None:
        """设置 MODBUS 配置（线程安全，可在连接前随时调用）。"""
        self._config = config

    def schedule_connect(self) -> None:
        """请求连接 PLC。立即返回，结果通过 :attr:`connection_changed` 信号通知。"""
        self._schedule(self._do_connect())

    def schedule_disconnect(self) -> None:
        """请求断开 PLC。立即返回。"""
        self._schedule(self._do_disconnect())

    def schedule_read(self) -> None:
        """请求读取全部标签。立即返回，结果通过 :attr:`data_ready` 信号通知。"""
        self._schedule(self._do_read())

    # ------------------------------------------------------------------
    #  内部：投递协程到工作线程事件循环
    # ------------------------------------------------------------------

    def _schedule(self, coro) -> None:
        """线程安全地将协程投递到工作线程的事件循环。

        等待 ``_loop_ready`` 事件确保循环已创建，然后通过
        ``run_coroutine_threadsafe`` 注入任务。
        """
        if self._shutdown_requested:
            return
        # 等待事件循环就绪（最多 3 秒）
        if not self._loop_ready.wait(3.0):
            logger.error("PlcWorker: 事件循环未就绪，放弃调度")
            return
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            logger.error("PlcWorker: 事件循环未运行，放弃调度")

    # ------------------------------------------------------------------
    #  异步操作 (在工作线程事件循环上执行)
    # ------------------------------------------------------------------

    async def _do_connect(self) -> None:
        """建立 MODBUS 连接。"""
        if self._config is None:
            self.connection_changed.emit(False, "未加载配置文件")
            return

        try:
            self.connection_changed.emit(False, "连接中…")
            self._plc = RobotPlc(self._config)
            await self._plc.connect()
            self.connection_changed.emit(True, "已连接")
        except Exception as e:
            self._plc = None
            self.connection_changed.emit(False, f"连接失败: {e}")

    async def _do_disconnect(self) -> None:
        """断开 MODBUS 连接。"""
        if self._plc is None:
            self.connection_changed.emit(False, "未连接")
            return

        try:
            await self._plc.disconnect()
        except Exception as e:
            logger.warning("断开连接时出错: %s", e)
        finally:
            self._plc = None
            self.connection_changed.emit(False, "已断开")

    async def _do_read(self) -> None:
        """读取全部标签并发射 :attr:`data_ready` 信号。"""
        if self._plc is None or not self._plc.connected:
            self.connection_changed.emit(False, "未连接，无法读取")
            return

        try:
            results = await self._plc.read_all()
            self.data_ready.emit(results)
        except Exception as e:
            logger.error("读取数据失败: %s", e)
            self.connection_changed.emit(False, f"读取失败: {e}")

    async def _do_shutdown(self) -> None:
        """关闭时清理：断开 PLC 连接。"""
        if self._plc is not None:
            try:
                await self._plc.disconnect()
            except Exception:
                pass
            self._plc = None
