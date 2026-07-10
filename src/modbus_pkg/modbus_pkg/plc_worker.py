"""ModbusPlcNode -- ROS2 LifecycleNode wrapping RobotPlc for periodic MODBUS reading.

Replaces the QThread-based PlcWorker from rqt_modbus_config with a managed
lifecycle node.  Publishes connection status on ~/connection_status and
tag data on ~/data (both std_msgs/String, JSON payloads).
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import rclpy
from rclpy.lifecycle import LifecycleNode
from rclpy.lifecycle.node import LifecycleState, TransitionCallbackReturn
from std_msgs.msg import String

from modbus_pkg.config_parser import ModbusConfig
from modbus_pkg.robot_plc import RobotPlc, TagValue


# ---------------------------------------------------------------------------
#  helpers
# ---------------------------------------------------------------------------

def _find_default_config() -> Optional[str]:
    """3-tier config-file search: ament_index -> env -> dev workspace."""
    # 1. installed package via ament index
    try:
        from ament_index_python import get_package_share_directory
        path = os.path.join(
            get_package_share_directory("modbus_pkg"),
            "config", "modbus_config.toml",
        )
        if os.path.isfile(path):
            return path
    except Exception:
        pass

    # 2. environment variable
    env_path = os.environ.get("MODBUS_CONFIG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 3. development workspace (plc_worker.py is at modbus_pkg/modbus_pkg/)
    dev_path = (
        Path(__file__).resolve().parents[1] / "config" / "modbus_config.toml"
    )
    if dev_path.is_file():
        return str(dev_path)

    return None


def _tag_value_to_dict(tv: TagValue) -> dict:
    """Convert a TagValue to a JSON-serializable dict."""
    return {
        "values": tv.values,
        "error": tv.error,
        "group": tv.tag.group,
        "data_type": tv.tag.data_type,
        "start_address": tv.tag.start_address,
        "length": tv.tag.length,
        "scale": tv.tag.scale,
        "access_right": tv.tag.access_right,
    }


# ---------------------------------------------------------------------------
#  LifecycleNode
# ---------------------------------------------------------------------------

class ModbusPlcNode(LifecycleNode):
    """ROS2 managed lifecycle node for periodic MODBUS tag reading."""

    def __init__(self, node_name: str = "modbus_plc_node") -> None:
        super().__init__(node_name)

        # ---- internal state (guarded by _lock) ----
        self._config: Optional[ModbusConfig] = None
        self._plc: Optional[RobotPlc] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_ready = threading.Event()
        self._shutdown_requested = False
        self._lock = threading.Lock()

        # ---- thread-safe bridges: asyncio thread -> ROS2 thread ----
        self._status_queue: queue.Queue = queue.Queue(maxsize=200)
        self._data_queue: queue.Queue = queue.Queue(maxsize=200)
        self._read_pending = False  # guard against overlapping reads

        # ---- ROS2 interfaces (created in on_configure) ----
        self._conn_pub = None
        self._data_pub = None
        self._read_timer = None

        # ---- declare parameters ----
        self.declare_parameter("config_file", "")
        self.declare_parameter("read_period", 1.0)

    # =====================================================================
    #  Lifecycle callbacks
    # =====================================================================

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("on_configure()")

        config_file = self.get_parameter("config_file").value
        if not config_file:
            config_file = _find_default_config()
        if not config_file:
            self.get_logger().error(
                "No MODBUS config file found. "
                "Set config_file parameter or MODBUS_CONFIG_PATH env."
            )
            return TransitionCallbackReturn.ERROR

        try:
            self._config = ModbusConfig.from_file(str(config_file))
            self.get_logger().info(
                f"Loaded config: {config_file} ({len(self._config.tags)} tags)"
            )
        except Exception as exc:
            self.get_logger().error(f"Failed to load config: {exc}")
            return TransitionCallbackReturn.ERROR

        self._conn_pub = self.create_lifecycle_publisher(
            String, "~/connection_status", 10
        )
        self._data_pub = self.create_lifecycle_publisher(
            String, "~/data", 10
        )
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("on_activate()")

        self._shutdown_requested = False
        self._loop_ready.clear()

        t = threading.Thread(
            target=self._run_asyncio_loop,
            name="modbus-asyncio", daemon=True,
        )
        t.start()
        if not self._loop_ready.wait(5.0):
            self.get_logger().error("asyncio event-loop start timed out")
            return TransitionCallbackReturn.ERROR

        # fire-and-forget connect (status published via queue on next timer tick)
        self._schedule(self._do_connect())

        period = self.get_parameter("read_period").value
        self._read_timer = self.create_timer(period, self._on_read_timer)
        return TransitionCallbackReturn.SUCCESS

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("on_deactivate()")

        if self._read_timer is not None:
            self.destroy_timer(self._read_timer)
            self._read_timer = None

        self._schedule_shutdown()
        return TransitionCallbackReturn.SUCCESS

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("on_cleanup()")
        with self._lock:
            self._plc = None
            self._config = None
        if self._conn_pub is not None:
            self.destroy_publisher(self._conn_pub)
            self._conn_pub = None
        if self._data_pub is not None:
            self.destroy_publisher(self._data_pub)
            self._data_pub = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("on_shutdown()")
        self._schedule_shutdown()
        return TransitionCallbackReturn.SUCCESS

    # =====================================================================
    #  Asyncio thread
    # =====================================================================

    def _run_asyncio_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.close()
            with self._lock:
                self._loop = None

    def _schedule(self, coro):
        """Thread-safe coroutine dispatch to the asyncio thread."""
        if self._shutdown_requested:
            return None
        if not self._loop_ready.wait(3.0):
            self.get_logger().error("asyncio loop not ready, cannot schedule")
            return None
        loop = self._loop
        if loop and loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop)
        self.get_logger().error("asyncio loop not running, cannot schedule")
        return None

    def _schedule_shutdown(self) -> None:
        """Request graceful shutdown of the asyncio thread."""
        self._shutdown_requested = True
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._do_shutdown(), loop)
            loop.call_soon_threadsafe(loop.stop)
        self._loop_ready.clear()

    # =====================================================================
    #  Async PLC operations (run on asyncio thread, results -> queues)
    # =====================================================================

    async def _do_connect(self) -> None:
        config = self._config
        if config is None:
            self._status_queue.put((False, "no config loaded"))
            return
        try:
            self._status_queue.put((False, "connecting..."))
            plc = RobotPlc(config)
            await plc.connect()
            with self._lock:
                self._plc = plc
            self._status_queue.put((True, "connected"))
        except Exception as exc:
            with self._lock:
                self._plc = None
            self._status_queue.put((False, f"connect failed: {exc}"))

    async def _do_shutdown(self) -> None:
        plc = self._plc
        if plc is not None:
            try:
                await plc.disconnect()
            except Exception:
                pass
            with self._lock:
                self._plc = None
        self._status_queue.put((False, "disconnected"))

    async def _do_read(self) -> None:
        try:
            plc = self._plc
            if plc is None or not plc.connected:
                self._status_queue.put((False, "not connected, cannot read"))
                return
            results = await plc.read_all()
            self._data_queue.put(results)
        except Exception as exc:
            self._status_queue.put((False, f"read failed: {exc}"))
        finally:
            self._read_pending = False

    # =====================================================================
    #  ROS2 timer callback (executor thread -- ONLY place that publishes)
    # =====================================================================

    def _on_read_timer(self) -> None:
        # 1. drain connection-status queue -> publish
        while True:
            try:
                connected, message = self._status_queue.get_nowait()
            except queue.Empty:
                break
            self._publish_connection_status(connected, message)

        # 2. drain data queue -> publish
        while True:
            try:
                results = self._data_queue.get_nowait()
            except queue.Empty:
                break
            self._publish_data(results)

        # 3. schedule next async read (non-blocking)
        if not self._read_pending:
            self._read_pending = True
            self._schedule(self._do_read())

    # =====================================================================
    #  Publishing helpers (executor thread ONLY)
    # =====================================================================

    def _publish_connection_status(self, connected: bool, message: str) -> None:
        if self._conn_pub is None:
            return
        msg = String()
        msg.data = json.dumps(
            {"connected": connected, "message": message}, ensure_ascii=False
        )
        self._conn_pub.publish(msg)
        self.get_logger().info(f"connection: {message}")

    def _publish_data(self, results: dict[str, TagValue]) -> None:
        if self._data_pub is None:
            return
        tags_dict = {
            name: _tag_value_to_dict(tv) for name, tv in results.items()
        }
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tags": tags_dict,
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self._data_pub.publish(msg)
        errs = sum(1 for tv in results.values() if tv.error)
        if errs:
            self.get_logger().warning(
                f"read {len(results)} tags ({errs} errors)"
            )
        else:
            self.get_logger().debug(f"read {len(results)} tags OK")


# ---------------------------------------------------------------------------
#  entry point
# ---------------------------------------------------------------------------

def main(args=None):
    rclpy.init(args=args)
    node = ModbusPlcNode()

    if node.trigger_configure() != TransitionCallbackReturn.SUCCESS:
        node.get_logger().fatal("Configure failed, exiting")
        rclpy.shutdown()
        return 1

    if node.trigger_activate() != TransitionCallbackReturn.SUCCESS:
        node.get_logger().fatal("Activate failed, exiting")
        rclpy.shutdown()
        return 1

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
