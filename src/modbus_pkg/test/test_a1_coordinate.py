"""A1 坐标读取测试 — 全 mock，无需 pymodbus 或实际 PLC。

A1 是机器人关节轴角度（基座旋转关节 / Base / Shoulder Pan Joint），
对应 modbus_config.toml 中的标签：
  - name: A1
  - start_address: 1002
  - length: 1
  - data_type: Short
  - access_right: 只读
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# ---- 在导入 modbus_pkg 之前 mock pymodbus ----
sys.modules["pymodbus"] = MagicMock()
sys.modules["pymodbus.client"] = MagicMock()

# ---- 解决包路径 ----
_HERE = Path(__file__).resolve().parent
_MODBUS_PKG_DIR = _HERE.parent
sys.path.insert(0, str(_MODBUS_PKG_DIR))

from modbus_pkg.robot_plc import RobotPlc, TagValue
from modbus_pkg.config_parser import ModbusConfig, ModbusTag, ModbusConnection


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_a1_tag(
    enable: bool = True,
    access_right: str = "只读",
    start_address: int = 1002,
    length: int = 1,
    data_type: str = "Short",
) -> ModbusTag:
    """创建符合 A1 定义的 ModbusTag。"""
    return ModbusTag(
        group="机器人坐标",
        name="A1",
        description="关节轴角度基座旋转关节 (Base / Shoulder Pan Joint)",
        register_type="保持寄存器",
        start_address=start_address,
        length=length,
        kep_address="%MW01002",
        data_type=data_type,
        access_right=access_right,
        scan_rate=100,
        enable=enable,
    )


def _config_with_a1(**overrides) -> ModbusConfig:
    """创建仅包含 A1 标签的 ModbusConfig。"""
    tag = _make_a1_tag(**overrides)
    return ModbusConfig(
        connection=ModbusConnection(
            ip="192.168.3.100", port=502, description="test", version="1",
        ),
        tags=[tag],
    )


def _mock_client(read_val: int | list[int] = 0) -> AsyncMock:
    """创建 ModbusTcpClient mock。"""
    client = AsyncMock()
    client.read_holding_registers.return_value = (
        list(read_val) if isinstance(read_val, list) else [read_val]
    )
    if isinstance(read_val, list):
        client.read_holding_register.return_value = read_val[0] if read_val else 0
    else:
        client.read_holding_register.return_value = read_val

    async def _write_tag(tag, value):
        if tag.length == 1:
            if isinstance(value, list):
                value = value[0]
            await client.write_holding_register(tag.start_address, value)
        else:
            if isinstance(value, int):
                value = [value]
            await client.write_registers(tag.start_address, value)

    client.write_tag.side_effect = _write_tag
    return client


# ---------------------------------------------------------------------------
# A1 配置元数据测试
# ---------------------------------------------------------------------------


class TestA1Config(unittest.TestCase):
    """验证 A1 标签的配置元数据是否正确。"""

    def test_a1_tag_metadata(self):
        """A1 标签的基本字段应匹配 modbus_config.toml 中的定义。"""
        tag = _make_a1_tag()
        self.assertEqual(tag.name, "A1")
        self.assertEqual(tag.group, "机器人坐标")
        self.assertEqual(tag.start_address, 1002)
        self.assertEqual(tag.length, 1)
        self.assertEqual(tag.data_type, "Short")
        self.assertEqual(tag.access_right, "只读")
        self.assertEqual(tag.register_type, "保持寄存器")
        self.assertEqual(tag.kep_address, "%MW01002")
        self.assertTrue(tag.enable)

    def test_a1_from_real_config(self):
        """从真实 modbus_config.toml 加载的 A1 标签应与预期一致。"""
        toml_path = _MODBUS_PKG_DIR / "config" / "modbus_config.toml"
        config = ModbusConfig.from_file(toml_path)
        a1 = config.get_tag("A1")
        self.assertIsNotNone(a1, "A1 标签应存在于配置文件中")
        self.assertEqual(a1.start_address, 1002)
        self.assertEqual(a1.length, 1)
        self.assertEqual(a1.data_type, "Short")
        self.assertEqual(a1.access_right, "只读")
        self.assertEqual(a1.group, "机器人坐标")
        self.assertTrue(a1.enable)

    def test_a1_in_enabled_tags(self):
        """A1 应出现在 get_enabled_tags() 的结果中。"""
        toml_path = _MODBUS_PKG_DIR / "config" / "modbus_config.toml"
        config = ModbusConfig.from_file(toml_path)
        enabled = {t.name for t in config.get_enabled_tags()}
        self.assertIn("A1", enabled)

    def test_a1_in_robot_coordinates_group(self):
        """A1 应属于 '机器人坐标' 分组。"""
        toml_path = _MODBUS_PKG_DIR / "config" / "modbus_config.toml"
        config = ModbusConfig.from_file(toml_path)
        robot_tags = config.get_tags_by_group("机器人坐标")
        names = {t.name for t in robot_tags}
        self.assertIn("A1", names)
        # 验证 A1-A6 都在该分组中
        for joint in ["A1", "A2", "A3", "A4", "A5", "A6"]:
            self.assertIn(joint, names, f"{joint} 应在机器人坐标分组中")


# ---------------------------------------------------------------------------
# A1 读取测试（mock）
# ---------------------------------------------------------------------------


class TestA1Read(unittest.IsolatedAsyncioTestCase):
    """通过 mock 测试 A1 读取的各种场景。"""

    # ---- 基本读取 ----

    async def test_read_a1_basic(self):
        """读取 A1 标签，应返回正确的值。"""
        mock = _mock_client([180])  # 模拟关节角度 180（Short 类型）
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        self.assertIn("A1", results)
        self.assertEqual(results["A1"].values, [180])
        self.assertIsNone(results["A1"].error)

    async def test_read_a1_zero(self):
        """A1 值为 0 时正常返回。"""
        mock = _mock_client([0])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        self.assertEqual(results["A1"].values, [0])
        self.assertIsNone(results["A1"].error)

    async def test_read_a1_negative(self):
        """A1 值为负数（Short 的有符号范围），如 -90。"""
        mock = _mock_client([-90 & 0xFFFF])  # 模拟 PLC 返回的原始值
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        self.assertEqual(len(results["A1"].values), 1)

    async def test_read_a1_max_short(self):
        """A1 值为 Short 最大值 32767。"""
        mock = _mock_client([32767])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        self.assertEqual(results["A1"].values, [32767])
        self.assertIsNone(results["A1"].error)

    # ---- TagValue 结构 ----

    async def test_read_a1_tagvalue_has_tag_reference(self):
        """返回的 TagValue 应包含原始 tag 引用。"""
        mock = _mock_client([45])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        tv = results["A1"]
        self.assertIsInstance(tv, TagValue)
        self.assertEqual(tv.tag.name, "A1")
        self.assertEqual(tv.tag.start_address, 1002)
        self.assertEqual(tv.tag.data_type, "Short")

    # ---- 地址去重 ----

    async def test_read_a1_dedup_with_same_address_tag(self):
        """A1 和其他共享同一地址的标签应只发一次请求。"""
        a1 = _make_a1_tag()
        other = ModbusTag(
            group="其他", name="OTHER_AT_1002", description="共享地址",
            register_type="保持寄存器", start_address=1002, length=1,
            kep_address="%MW01002", data_type="Word",
            access_right="只读", scan_rate=100, enable=True,
        )
        config = ModbusConfig(
            connection=ModbusConnection(
                ip="192.168.3.100", port=502, description="", version="1",
            ),
            tags=[a1, other],
        )
        mock = _mock_client([90])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(config).read_all()
        self.assertIn("A1", results)
        self.assertIn("OTHER_AT_1002", results)
        self.assertEqual(results["A1"].values, [90])
        self.assertEqual(results["OTHER_AT_1002"].values, [90])
        # 同地址只发一次请求
        mock.read_holding_registers.assert_awaited_once_with(1002, 1)

    # ---- 禁用标签 ----

    async def test_read_a1_disabled_excluded(self):
        """禁用 A1 后不应出现在结果中。"""
        mock = _mock_client([1])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1(enable=False)).read_all()
        self.assertNotIn("A1", results)

    # ---- 错误处理 ----

    async def test_read_a1_error(self):
        """读取 A1 时发生通讯错误，错误信息应被捕获。"""
        mock = AsyncMock()
        mock.read_holding_registers.side_effect = ConnectionError("连接超时")
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        self.assertEqual(results["A1"].values, [])
        self.assertEqual(results["A1"].error, "连接超时")

    async def test_read_a1_timeout_error(self):
        """读取 A1 时超时，错误信息应正确传递。"""
        mock = AsyncMock()
        mock.read_holding_registers.side_effect = TimeoutError("读取超时")
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config_with_a1()).read_all()
        self.assertIn("A1", results)
        self.assertIsNotNone(results["A1"].error)
        self.assertIn("超时", results["A1"].error)

    # ---- 只读属性 ----

    async def test_read_a1_is_readonly(self):
        """A1 为只读标签，写入应抛出 PermissionError。"""
        mock = _mock_client([0])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config_with_a1())
            with self.assertRaises(PermissionError):
                await plc.write_tag("A1", 100)

    # ---- 连接管理 / 上下文管理器 ----

    async def test_read_a1_with_context_manager(self):
        """通过 async with 使用 RobotPlc 读取 A1。"""
        mock = _mock_client([15])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            async with RobotPlc(_config_with_a1()) as plc:
                results = await plc.read_all()
            self.assertEqual(results["A1"].values, [15])
        mock.connect.assert_awaited_once()
        mock.disconnect.assert_awaited_once()

    # ---- 真实配置文件集成测试 ----

    async def test_read_a1_with_real_config(self):
        """使用真实的 modbus_config.toml 读取 A1（mock 通讯层）。"""
        toml_path = _MODBUS_PKG_DIR / "config" / "modbus_config.toml"
        config = ModbusConfig.from_file(toml_path)

        # 确保 A1 标签存在且启用
        a1 = config.get_tag("A1")
        self.assertIsNotNone(a1)
        self.assertTrue(a1.enable)

        mock = _mock_client([123])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(config).read_all()

        # A1 应在结果中
        self.assertIn("A1", results)
        self.assertIsNone(results["A1"].error, f"A1 error: {results['A1'].error}")
        self.assertEqual(len(results["A1"].values), 1)
        print(f"\n  A1 读取值: {results['A1'].values[0]} (mock)")


# ---------------------------------------------------------------------------
# A1 与其他关节轴联合读取测试
# ---------------------------------------------------------------------------


class TestA1WithOtherJoints(unittest.IsolatedAsyncioTestCase):
    """A1 与 A2-A6 联合读取测试。"""

    def _joint_tag(self, name: str, addr: int) -> ModbusTag:
        """创建关节轴标签。"""
        return ModbusTag(
            group="机器人坐标", name=name,
            description=f"关节轴 {name}",
            register_type="保持寄存器", start_address=addr, length=1,
            kep_address=f"%MW{addr:05d}", data_type="Short",
            access_right="只读", scan_rate=100, enable=True,
        )

    async def test_read_all_joints_dedup(self):
        """A1-A6 各有独立地址，应各发一次请求（共 6 次）。"""
        joints = [
            self._joint_tag("A1", 1002),
            self._joint_tag("A2", 1004),
            self._joint_tag("A3", 1006),
            self._joint_tag("A4", 1008),
            self._joint_tag("A5", 1010),
            self._joint_tag("A6", 1012),
        ]
        config = ModbusConfig(
            connection=ModbusConnection(
                ip="192.168.3.100", port=502, description="", version="1",
            ),
            tags=joints,
        )
        mock = _mock_client([45])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(config).read_all()

        self.assertEqual(len(results), 6)
        for name in ["A1", "A2", "A3", "A4", "A5", "A6"]:
            self.assertIn(name, results)
            self.assertIsNone(results[name].error, f"{name} error: {results[name].error}")
        self.assertEqual(mock.read_holding_registers.await_count, 6)

    async def test_read_a1_a2_a3_only(self):
        """只读取 A1、A2、A3 三个关节轴。"""
        tags = [
            self._joint_tag("A1", 1002),
            self._joint_tag("A2", 1004),
            self._joint_tag("A3", 1006),
        ]
        config = ModbusConfig(
            connection=ModbusConnection(
                ip="192.168.3.100", port=502, description="", version="1",
            ),
            tags=tags,
        )
        # 模拟不同关节返回不同角度值
        call_count = 0
        mock_values = [[10], [20], [30]]

        async def _read(addr, length):
            nonlocal call_count
            val = mock_values[call_count]
            call_count += 1
            return val

        mock = AsyncMock()
        mock.read_holding_registers.side_effect = _read

        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(config).read_all()

        self.assertEqual(results["A1"].values, [10])
        self.assertEqual(results["A2"].values, [20])
        self.assertEqual(results["A3"].values, [30])


if __name__ == "__main__":
    unittest.main()
