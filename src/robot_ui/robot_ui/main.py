"""机器人打磨系统 HMI 启动入口。

使用 PySide6 加载 QML 界面，通过 Bridge 对象暴露 Python 接口供 QML 调用。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


def _src_dir() -> Path:
    """返回 src 目录，确保 modbus_pkg 等兄弟包可导入。"""
    return Path(__file__).resolve().parent.parent.parent


def _qml_dir() -> str:
    """返回 qml 文件目录。优先查找 colcon install 路径，回退到源码路径。"""
    candidates = [
        Path(__file__).parent.parent / "share" / "robot_ui" / "qml",
        Path(__file__).parent.parent / "qml",
    ]
    for p in candidates:
        if p.exists():
            return str(p.resolve())
    return str(Path(__file__).parent.parent / "qml")


class Bridge(QObject):
    """QML ↔ Python 桥接对象。

    所有 Slot 方法暴露给 QML 直接调用，Signal 用于主动向 QML 推送数据。
    """

    # 机器人关节角度更新 (A1-A6)
    jointAnglesChanged = Signal(float, float, float, float, float, float,
                                arguments=["a1", "a2", "a3", "a4", "a5", "a6"])

    # 笛卡尔坐标更新 (X, Y, Z, A, B, C)
    cartesianChanged = Signal(float, float, float, float, float, float,
                              arguments=["x", "y", "z", "a", "b", "c"])

    # 连接状态
    modbusStatusChanged = Signal(bool, arguments=["connected"])
    heartbeatChanged = Signal(bool, arguments=["alive"])

    # 工件编号
    workpieceNameChanged = Signal(str, arguments=["name"])

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._plc = None          # RobotPlc | None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_interval = 200  # ms
        self._heartbeat = False

    # ── 公开属性（QML 可直接绑定） ──

    @property
    def connected(self) -> bool:
        return self._plc is not None and self._plc.connected

    # ── 按钮槽 ──

    @Slot()
    def systemStart(self):
        """启动：连接 MODBUS 并开始轮询机器人坐标数据。"""
        print("[Bridge] 系统启动 — 初始化 MODBUS 连接 ...")

        # 确保可导入兄弟包 modbus_pkg
        modbus_path = str(_src_dir() / "modbus_pkg")
        if modbus_path not in sys.path:
            sys.path.insert(0, modbus_path)

        try:
            from modbus_pkg.config_parser import ModbusConfig
            from modbus_pkg.robot_plc import RobotPlc
        except ImportError as e:
            print(f"[Bridge] 导入 modbus_pkg 失败: {e}")
            self.modbusStatusChanged.emit(False)
            return

        # 查找配置文件
        config_path = self._find_config("modbus_config.toml")
        if config_path is None:
            print("[Bridge] 找不到 modbus_config.toml")
            self.modbusStatusChanged.emit(False)
            return

        print(f"[Bridge] 加载配置: {config_path}")
        config = ModbusConfig.from_file(config_path)

        # 连接 + 开始轮询
        self._plc = RobotPlc(config)
        asyncio.run(self._plc.connect())

        if self._plc.connected:
            print("[Bridge] MODBUS 连接成功，开始轮询")
            self.modbusStatusChanged.emit(True)
            self._poll_timer.start(self._poll_interval)
        else:
            print("[Bridge] MODBUS 连接失败")
            self.modbusStatusChanged.emit(False)

    @Slot()
    def systemStop(self):
        """停止轮询并断开 MODBUS。"""
        print("[Bridge] 系统停止")
        self._poll_timer.stop()
        if self._plc is not None:
            asyncio.run(self._plc.disconnect())
            self._plc = None
        self.modbusStatusChanged.emit(False)
        self.heartbeatChanged.emit(False)

    @Slot()
    def robotReturnToOrigin(self):
        print("[Bridge] 机器人回原点")

    @Slot()
    def emergencyStop(self):
        print("[Bridge] 急停")

    @Slot()
    def scanReady(self):
        print("[Bridge] 准备扫描")

    @Slot()
    def scanStart(self):
        print("[Bridge] 开始扫描")

    @Slot()
    def scanPause(self):
        print("[Bridge] 暂停扫描")

    @Slot()
    def scanEnd(self):
        print("[Bridge] 结束扫描")

    @Slot()
    def computePaths(self):
        print("[Bridge] 路径计算")

    @Slot()
    def startPolish(self):
        print("[Bridge] 开始打磨")

    @Slot()
    def pausePolish(self):
        print("[Bridge] 暂停打磨")

    @Slot()
    def toolQuickChange(self):
        print("[Bridge] 工具快换")

    @Slot()
    def cameraGrab(self):
        print("[Bridge] 相机抓取")

    @Slot()
    def cameraPutDown(self):
        print("[Bridge] 相机放下")

    @Slot()
    def railReturnToOrigin(self):
        print("[Bridge] 导轨回原点")

    # ── 内部：MODBUS 轮询 ──

    def _poll(self) -> None:
        """定时器回调：读取 MODBUS 数据并更新 QML。"""
        if self._plc is None or not self._plc.connected:
            return

        try:
            results = asyncio.run(self._plc.read_all())
        except Exception as e:
            print(f"[Bridge] 轮询失败: {e}")
            return

        # 心跳翻转
        self._heartbeat = not self._heartbeat
        self.heartbeatChanged.emit(self._heartbeat)

        # 提取关节角度
        joint_names = ["A1", "A2", "A3", "A4", "A5", "A6"]
        joint_values = self._get_values(results, joint_names)
        if len(joint_values) == 6:
            self.jointAnglesChanged.emit(*joint_values)

        # 提取笛卡尔坐标
        cart_names = ["X", "Y", "Z", "A", "B", "C"]
        cart_values = self._get_values(results, cart_names)
        if len(cart_values) == 6:
            self.cartesianChanged.emit(*cart_values)

        # 工件编号
        wn = results.get("WORKPIECE_NAME")
        if wn is not None and wn.error is None:
            self.workpieceNameChanged.emit("--")  # 字符串暂不解析

    @staticmethod
    def _get_values(results: dict, names: list[str]) -> list[float]:
        """从 TagValue 字典中按名称提取值列表，用于发射信号。"""
        out: list[float] = []
        for name in names:
            tv = results.get(name)
            if tv is None or tv.error or not tv.values:
                return []
            out.append(float(tv.values[0]))
        return out

    @staticmethod
    def _find_config(filename: str) -> Path | None:
        """查找 modbus 配置文件。"""
        candidates = [
            _src_dir() / "modbus_pkg" / "config" / filename,
            Path(__file__).parent.parent / "config" / filename,
        ]
        for p in candidates:
            if p.exists():
                return p.resolve()
        return None


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("robot_ui")

    engine = QQmlApplicationEngine()

    bridge = Bridge()
    engine.rootContext().setContextProperty("bridge", bridge)

    qml_dir = _qml_dir()
    engine.addImportPath(qml_dir)

    qml_path = os.path.join(qml_dir, "MainWindow.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        print("[Error] QML 加载失败，未能创建根对象", file=sys.stderr)
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
