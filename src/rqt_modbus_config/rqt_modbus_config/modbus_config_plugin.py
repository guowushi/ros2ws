"""rqt plugin — 从 modbus_config.toml 读取数据并以表格形式展示。

提供连接信息面板、PLC 连接/读取功能、以及寄存器标签表格，
支持按分组筛选、文本搜索、自动轮询读取 PLC 数据。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from modbus_pkg.config_parser import ModbusConfig, ModbusTag
from modbus_pkg.robot_plc import TagValue, _parse_kep_bit
from python_qt_binding.QtCore import Qt, QTimer
from python_qt_binding.QtGui import QColor
from python_qt_binding.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from rqt_gui_py.plugin import Plugin

from .plc_worker import PlcWorker

# ------- 常量 -------
COLUMNS = [
    ("group", "分组"),
    ("name", "标签名"),
    ("description", "描述"),
    ("register_type", "寄存器类型"),
    ("start_address", "起始地址"),
    ("length", "长度"),
    ("kep_address", "KEP地址"),
    ("data_type", "数据类型"),
    ("access_right", "读写权限"),
    ("scan_rate", "扫描周期(ms)"),
    ("current_value", "当前值"),
    ("enable", "启用"),
]

COL_LABEL = [c[1] for c in COLUMNS]

# 分组行背景色（交替）
GROUP_COLORS = [
    QColor(240, 248, 255),  # alice blue
    QColor(255, 250, 240),  # floral white
]

DEFAULT_CONFIG_PATH = str(
    Path(__file__).resolve().parents[3]
    / "src/modbus_pkg/config/modbus_config.toml"
)


def _find_default_config() -> str | None:
    """查找默认的 modbus_config.toml 路径。

    优先从 ament_index 查找已安装的 modbus_pkg 包，
    其次尝试开发工作区路径，最后尝试常见路径。
    """
    try:
        from ament_index_python import get_package_share_directory
        share_dir = get_package_share_directory("modbus_pkg")
        path = os.path.join(share_dir, "config", "modbus_config.toml")
        if os.path.isfile(path):
            return path
    except Exception:
        pass
    if os.path.isfile(DEFAULT_CONFIG_PATH):
        return DEFAULT_CONFIG_PATH
    env_path = os.environ.get("MODBUS_CONFIG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    return None


class ModbusConfigPlugin(Plugin):
    """rqt 插件 — Modbus 配置表格查看器 + PLC 数据读取。"""

    def __init__(self, context):
        super().__init__(context)
        self.setObjectName("ModbusConfigPlugin")

        # ---- 状态 ----
        self._all_tags: list[ModbusTag] = []
        self._config: Optional[ModbusConfig] = None
        self._latest_values: dict[str, TagValue] = {}
        self._connected = False

        # ---- 主容器 ----
        self._main_widget = QWidget()
        self._main_layout = QVBoxLayout(self._main_widget)
        self._main_layout.setContentsMargins(6, 6, 6, 6)
        self._main_layout.setSpacing(6)

        # ---- 后台工作线程 ----
        self._worker = PlcWorker()
        self._worker.connection_changed.connect(self._on_connection_changed)
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.start()

        # ---- 连接信息面板 ----
        self._build_connection_panel()

        # ---- 工具栏 ----
        self._build_toolbar()

        # ---- 表格 ----
        self._build_table()

        # ---- 状态栏 ----
        self._status_label = QLabel("就绪")
        self._main_layout.addWidget(self._status_label)

        # ---- 自动轮询定时器 ----
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_poll_tick)

        # 注册到 rqt
        context.add_widget(self._main_widget)

        # 自动加载默认配置文件
        QTimer.singleShot(200, self._auto_load_default)

    # ==================================================================
    #  连接信息面板 (横向布局)
    # ==================================================================

    def _build_connection_panel(self) -> None:
        """构建连接信息面板 — 两行横向布局。"""
        group = QGroupBox("连接信息")
        vbox = QVBoxLayout(group)
        vbox.setContentsMargins(8, 6, 8, 6)
        vbox.setSpacing(6)

        # ---- 行1: IP / Port / 描述 / 版本 ----
        row1 = QHBoxLayout()
        row1.setSpacing(4)

        self._conn_ip = QLabel("—")
        self._conn_port = QLabel("—")
        self._conn_desc = QLabel("—")
        self._conn_ver = QLabel("—")

        row1.addWidget(QLabel("IP:"))
        row1.addWidget(self._conn_ip)
        row1.addWidget(self._make_sep())
        row1.addWidget(QLabel("端口:"))
        row1.addWidget(self._conn_port)
        row1.addWidget(self._make_sep())
        row1.addWidget(QLabel("描述:"))
        row1.addWidget(self._conn_desc)
        row1.addWidget(self._make_sep())
        row1.addWidget(QLabel("版本:"))
        row1.addWidget(self._conn_ver)
        row1.addStretch()
        vbox.addLayout(row1)

        # ---- 行2: 按钮 + 自动刷新 + 状态指示器 ----
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self._btn_connect = QPushButton("连接 PLC")
        self._btn_connect.setToolTip("建立 MODBUS TCP 连接")
        self._btn_connect.clicked.connect(self._on_connect_clicked)
        row2.addWidget(self._btn_connect)

        self._btn_disconnect = QPushButton("断开")
        self._btn_disconnect.setToolTip("断开 MODBUS TCP 连接")
        self._btn_disconnect.setEnabled(False)
        self._btn_disconnect.clicked.connect(self._on_disconnect_clicked)
        row2.addWidget(self._btn_disconnect)

        self._btn_read = QPushButton("读取数据")
        self._btn_read.setToolTip("立即读取全部寄存器标签")
        self._btn_read.setEnabled(False)
        self._btn_read.clicked.connect(self._on_read_clicked)
        row2.addWidget(self._btn_read)

        # 分隔
        row2.addWidget(self._make_sep())

        # 自动刷新
        self._auto_poll_cb = QCheckBox("自动刷新")
        self._auto_poll_cb.setToolTip("定时自动读取 PLC 数据")
        self._auto_poll_cb.setEnabled(False)
        self._auto_poll_cb.stateChanged.connect(self._on_auto_poll_changed)
        row2.addWidget(self._auto_poll_cb)

        self._poll_interval_spin = QSpinBox()
        self._poll_interval_spin.setRange(200, 60000)
        self._poll_interval_spin.setValue(1000)
        self._poll_interval_spin.setSuffix(" ms")
        self._poll_interval_spin.setToolTip("自动刷新间隔（毫秒）")
        self._poll_interval_spin.setEnabled(False)
        row2.addWidget(self._poll_interval_spin)

        row2.addStretch()

        # 连接状态指示器
        self._status_indicator = QLabel("● 未连接")
        self._status_indicator.setStyleSheet("color: #888; font-weight: bold;")
        row2.addWidget(self._status_indicator)

        vbox.addLayout(row2)
        self._main_layout.addWidget(group)

    @staticmethod
    def _make_sep() -> QLabel:
        """创建竖线分隔符。"""
        sep = QLabel("│")
        sep.setStyleSheet("color: #ccc;")
        sep.setFixedWidth(12)
        return sep

    # ==================================================================
    #  工具栏
    # ==================================================================

    def _build_toolbar(self) -> None:
        """构建工具栏：打开文件、分组筛选、搜索框、显示禁用开关。"""
        bar = QWidget()
        hbox = QHBoxLayout(bar)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(6)

        lbl = QLabel("配置文件:")
        hbox.addWidget(lbl)

        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("选择或输入 modbus_config.toml 路径…")
        self._file_edit.setReadOnly(True)
        hbox.addWidget(self._file_edit, 1)

        btn_open = QPushButton("打开…")
        btn_open.setToolTip("选择 modbus_config.toml 文件")
        btn_open.clicked.connect(self._on_open_file)
        hbox.addWidget(btn_open)

        btn_reload = QPushButton("重新加载")
        btn_reload.setToolTip("重新加载当前配置文件")
        btn_reload.clicked.connect(self._on_reload)
        hbox.addWidget(btn_reload)

        sep = QLabel("│")
        sep.setStyleSheet("color: #aaa;")
        hbox.addWidget(sep)

        lbl_grp = QLabel("分组:")
        hbox.addWidget(lbl_grp)
        self._group_combo = QComboBox()
        self._group_combo.setMinimumWidth(120)
        self._group_combo.setToolTip("按分组筛选标签")
        self._group_combo.currentTextChanged.connect(self._on_filter_changed)
        hbox.addWidget(self._group_combo)

        lbl_srch = QLabel("搜索:")
        hbox.addWidget(lbl_srch)
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("输入关键字筛选…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMinimumWidth(150)
        self._search_edit.textChanged.connect(self._on_filter_changed)
        hbox.addWidget(self._search_edit)

        self._show_disabled_cb = QCheckBox("显示禁用")
        self._show_disabled_cb.setToolTip("同时展示 enable=false 的标签")
        self._show_disabled_cb.stateChanged.connect(self._on_filter_changed)
        hbox.addWidget(self._show_disabled_cb)

        self._main_layout.addWidget(bar)

    # ==================================================================
    #  表格
    # ==================================================================

    def _build_table(self) -> None:
        """构建数据表格。"""
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COL_LABEL)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        self._table.setAlternatingRowColors(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setVisible(False)

        self._main_layout.addWidget(self._table, 1)

    # ==================================================================
    #  数据加载
    # ==================================================================

    def _auto_load_default(self) -> None:
        """启动后自动加载默认配置文件。"""
        default = _find_default_config()
        if default:
            self._load_config(default)

    def _on_open_file(self) -> None:
        """打开文件对话框选择配置文件。"""
        start_dir = (
            os.path.dirname(self._file_edit.text())
            if self._file_edit.text()
            else str(Path.home())
        )
        path, _ = QFileDialog.getOpenFileName(
            self._main_widget,
            "选择 MODBUS 配置文件",
            start_dir,
            "TOML 文件 (*.toml);;所有文件 (*)",
        )
        if path:
            self._load_config(path)

    def _on_reload(self) -> None:
        """重新加载当前文件。"""
        path = self._file_edit.text()
        if path and os.path.isfile(path):
            self._load_config(path)
        else:
            self._set_status("错误: 文件不存在 — " + (path or "(空)"), ok=False)

    def _load_config(self, path: str) -> None:
        """解析配置文件并填充界面。"""
        try:
            config = ModbusConfig.from_file(path)
            self._config = config
            self._file_edit.setText(path)
            self._set_status(f"已加载: {path}  ({len(config.tags)} 个标签)", ok=True)
        except Exception as e:
            self._set_status(f"解析失败: {e}", ok=False)
            return

        # 传递给后台 worker
        self._worker.set_config(config)

        # 清空旧数据
        self._latest_values.clear()

        # 连接信息
        conn = config.connection
        self._conn_ip.setText(conn.ip)
        self._conn_port.setText(str(conn.port))
        self._conn_desc.setText(conn.description)
        self._conn_ver.setText(conn.version)

        # 缓存标签列表
        self._all_tags = config.tags

        # 填充分组下拉框
        self._group_combo.blockSignals(True)
        self._group_combo.clear()
        self._group_combo.addItem("— 全部 —")
        for g in config.group_names:
            self._group_combo.addItem(g)
        self._group_combo.setCurrentIndex(0)
        self._group_combo.blockSignals(False)

        # 填充表格
        self._populate_table(self._all_tags)
        self._auto_resize_columns()

        # 更新按钮状态
        self._update_button_states()

    # ==================================================================
    #  表格填充
    # ==================================================================

    def _populate_table(self, tags: list[ModbusTag]) -> None:
        """将标签列表填充到表格中。"""
        self._table.setRowCount(0)
        self._table.setRowCount(len(tags))

        group_color_idx: dict[str, int] = {}
        next_color = 0

        for row, tag in enumerate(tags):
            # 分组背景色
            if tag.group:
                if tag.group not in group_color_idx:
                    group_color_idx[tag.group] = next_color
                    next_color = (next_color + 1) % len(GROUP_COLORS)
                bg = GROUP_COLORS[group_color_idx[tag.group]]
            else:
                bg = QColor(255, 255, 255)

            # 当前值
            value_text, value_fg, value_tip = self._format_current_value(tag.name)

            values = [
                tag.group,
                tag.name,
                tag.description,
                tag.register_type,
                str(tag.start_address),
                str(tag.length),
                tag.kep_address,
                tag.data_type,
                tag.access_right,
                str(tag.scan_rate),
                value_text,          # 当前值
                "✓" if tag.enable else "✗",
            ]

            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setBackground(bg)
                # 禁用行用灰色文字 (最后一列"启用"除外)
                if not tag.enable and col != len(values) - 1:
                    item.setForeground(QColor(160, 160, 160))
                # 当前值列特殊颜色
                if col == 10 and value_fg is not None and tag.enable:
                    item.setForeground(value_fg)
                if col == 10 and value_tip:
                    item.setToolTip(value_tip)
                # 起始地址右对齐
                if col == 4:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(row, col, item)

    # ==================================================================
    #  当前值格式化
    # ==================================================================

    def _format_current_value(self, tag_name: str) -> tuple[str, Optional[QColor], str]:
        """格式化标签当前值。

        Returns:
            (显示文本, 前景色(None=默认), 提示文本)
        """
        tv = self._latest_values.get(tag_name)
        if tv is None:
            return ("—", None, "")
        if tv.error:
            return ("ERR", QColor(220, 30, 30), tv.error)
        if not tv.values:
            return ("—", None, "")

        # 布尔标签：提取对应 bit 位
        if tv.tag.data_type == "Boolean":
            bit = _parse_kep_bit(tv.tag.kep_address)
            if bit is not None and tv.values:
                raw = tv.values[0]
                val = (raw >> bit) & 1
                return (str(val), None, f"原始寄存器值: {raw} (bit {bit})")

        # 单值
        if len(tv.values) == 1:
            return (str(tv.values[0]), None, "")

        # 多值
        text = ", ".join(str(v) for v in tv.values)
        return (text, None, "")

    # ==================================================================
    #  筛选
    # ==================================================================

    def _on_filter_changed(self) -> None:
        """分组 / 文本搜索 / 显示禁用变更时刷新表格。"""
        if not self._all_tags:
            return

        group = self._group_combo.currentText()
        keyword = self._search_edit.text().strip().lower()
        show_disabled = self._show_disabled_cb.isChecked()

        filtered: list[ModbusTag] = []
        for tag in self._all_tags:
            if not show_disabled and not tag.enable:
                continue
            if group and group != "— 全部 —" and tag.group != group:
                continue
            if keyword:
                haystack = (
                    tag.name + tag.description + tag.kep_address + tag.group
                ).lower()
                if keyword not in haystack:
                    continue
            filtered.append(tag)

        self._populate_table(filtered)
        self._set_status(
            f"显示 {len(filtered)} / {len(self._all_tags)} 个标签", ok=True
        )

    # ==================================================================
    #  PLC 操作回调
    # ==================================================================

    def _on_connect_clicked(self) -> None:
        """点击 '连接 PLC' 按钮。"""
        self._latest_values.clear()
        self._set_status("正在连接 PLC…", ok=True)
        self._status_indicator.setText("● 连接中…")
        self._status_indicator.setStyleSheet("color: #c90; font-weight: bold;")
        self._update_button_states()
        self._worker.schedule_connect()

    def _on_disconnect_clicked(self) -> None:
        """点击 '断开' 按钮。"""
        self._poll_timer.stop()
        self._worker.schedule_disconnect()

    def _on_read_clicked(self) -> None:
        """点击 '读取数据' 按钮。"""
        self._worker.schedule_read()

    def _on_poll_tick(self) -> None:
        """自动轮询触发。"""
        self._worker.schedule_read()

    def _on_auto_poll_changed(self, state: int) -> None:
        """自动刷新复选框状态变化。"""
        if state:
            self._poll_timer.start(self._poll_interval_spin.value())
        else:
            self._poll_timer.stop()

    # ==================================================================
    #  来自 PlcWorker 的信号回调 (在主线程执行)
    # ==================================================================

    def _on_connection_changed(self, connected: bool, message: str) -> None:
        """PLC 连接状态变化处理。"""
        self._connected = connected

        if connected:
            self._status_indicator.setText("● 已连接")
            self._status_indicator.setStyleSheet("color: green; font-weight: bold;")
            # 连接成功后自动读取一次
            self._worker.schedule_read()
        else:
            self._poll_timer.stop()
            if "失败" in message or "无法" in message:
                self._status_indicator.setText("● 错误")
                self._status_indicator.setStyleSheet("color: red; font-weight: bold;")
            else:
                self._status_indicator.setText("● 未连接")
                self._status_indicator.setStyleSheet("color: #888; font-weight: bold;")

        self._set_status(message, ok=connected)
        self._update_button_states()

    def _on_data_ready(self, results: dict) -> None:
        """PLC 数据读取完成处理。"""
        self._latest_values = results

        # 统计错误
        err_count = sum(1 for tv in results.values() if tv.error)
        if err_count:
            self._set_status(
                f"已读取 {len(results)} 个标签 (其中 {err_count} 个出错)", ok=False
            )
        else:
            self._set_status(f"已读取 {len(results)} 个标签", ok=True)

        # 刷新当前筛选视图的表格
        self._on_filter_changed()

    # ==================================================================
    #  按钮状态管理
    # ==================================================================

    def _update_button_states(self) -> None:
        """根据连接状态和配置状态更新按钮启用/禁用。"""
        has_config = self._config is not None

        # 连接中 (message == "连接中…")
        connecting = (
            self._status_indicator.text() == "● 连接中…"
        )

        if connecting:
            self._btn_connect.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
            self._btn_read.setEnabled(False)
            self._auto_poll_cb.setEnabled(False)
            self._poll_interval_spin.setEnabled(False)
        elif self._connected:
            self._btn_connect.setEnabled(False)
            self._btn_disconnect.setEnabled(True)
            self._btn_read.setEnabled(True)
            self._auto_poll_cb.setEnabled(True)
            self._poll_interval_spin.setEnabled(True)
        else:
            self._btn_connect.setEnabled(has_config)
            self._btn_disconnect.setEnabled(False)
            self._btn_read.setEnabled(False)
            self._auto_poll_cb.setEnabled(False)
            self._poll_interval_spin.setEnabled(False)

    # ==================================================================
    #  辅助
    # ==================================================================

    def _auto_resize_columns(self) -> None:
        """自适应列宽（限制最大宽度）。"""
        header = self._table.horizontalHeader()
        for i in range(self._table.columnCount()):
            self._table.resizeColumnToContents(i)
            width = header.sectionSize(i)
            if width > 350:
                header.resizeSection(i, 350)

    def _set_status(self, msg: str, ok: bool = True) -> None:
        """更新状态栏文案和颜色。"""
        self._status_label.setText(msg)
        if ok:
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setStyleSheet("color: red; font-weight: bold;")

    # ==================================================================
    #  生命周期
    # ==================================================================

    def shutdown_plugin(self) -> None:
        """插件卸载时清理。"""
        self._poll_timer.stop()
        self._worker.stop_worker()

    def save_settings(self, plugin_settings, instance_settings) -> None:
        """保存设置。"""
        instance_settings.set_value("config_file_path", self._file_edit.text())

    def restore_settings(self, plugin_settings, instance_settings) -> None:
        """恢复设置。"""
        path = instance_settings.value("config_file_path", "")
        if path and os.path.isfile(path):
            self._load_config(path)
