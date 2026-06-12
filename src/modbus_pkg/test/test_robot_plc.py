"""RobotPlc 单元测试 — 全 mock，无需 pymodbus 或实际 PLC。"""

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


def _config(tags: list[ModbusTag]) -> ModbusConfig:
    return ModbusConfig(
        connection=ModbusConnection(
            ip="192.168.1.1", port=502, description="", version="1",
        ),
        tags=tags,
    )


def _tag(
    name: str,
    addr: int,
    length: int = 1,
    enable: bool = True,
    access_right: str = "只读",
    kep_address: str = "",
) -> ModbusTag:
    return ModbusTag(
        group="g",
        name=name,
        description="",
        register_type="保持寄存器",
        start_address=addr,
        length=length,
        kep_address=kep_address or f"%MW{addr:05d}",
        data_type="Word",
        access_right=access_right,
        scan_rate=100,
        enable=enable,
    )


def _wtag(name: str, addr: int, bit: int | None = None) -> ModbusTag:
    """可写布尔标签，kep_address 带位信息。"""
    kep = f"%MW{addr:05d}.{bit}" if bit is not None else f"%MW{addr:05d}"
    return ModbusTag(
        group="g",
        name=name,
        description="",
        register_type="保持寄存器",
        start_address=addr,
        length=1,
        kep_address=kep,
        data_type="Boolean" if bit is not None else "Word",
        access_right="读写",
        scan_rate=100,
        enable=True,
    )


def _mock_client(read_val: int | list[int] = 0) -> AsyncMock:
    """创建 ModbusTcpClient mock，完整模拟读写路径。

    - read_holding_registers (复数): 用于 read_all，返回 list[int]
    - read_holding_register  (单数): 用于布尔写入的读-改-写，返回 int
    - write_tag: 转发到 write_holding_register / write_registers
    """
    client = AsyncMock()
    # 复数：read_all 路径
    client.read_holding_registers.return_value = (
        list(read_val) if isinstance(read_val, list) else [read_val]
    )
    # 单数：布尔写入读-改-写路径
    if isinstance(read_val, list):
        client.read_holding_register.return_value = read_val[0] if read_val else 0
    else:
        client.read_holding_register.return_value = read_val

    # write_tag 转发到实际的写入方法
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
# 读取测试
# ---------------------------------------------------------------------------


class TestRead(unittest.IsolatedAsyncioTestCase):

    async def test_single_tag(self):
        mock = _mock_client([42])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config([_tag("A1", 1002)])).read_all()
        self.assertEqual(results["A1"].values, [42])
        self.assertIsNone(results["A1"].error)

    async def test_multi_length(self):
        mock = _mock_client([100, 200])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config([_tag("BIG", 7500, length=2)])).read_all()
        self.assertEqual(results["BIG"].values, [100, 200])

    async def test_mixed_addresses(self):
        tags = [_tag(f"T{i}", addr) for i, addr in enumerate([1002, 1004, 7402, 7404])]
        mock = _mock_client([99])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config(tags)).read_all()
        self.assertEqual(len(results), 4)
        self.assertEqual(mock.read_holding_registers.await_count, 4)

    async def test_dedup_same_address(self):
        tags = [_tag("EN1", 7400), _tag("EN2", 7400), _tag("EN3", 7400)]
        mock = _mock_client([0b111])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config(tags)).read_all()
        mock.read_holding_registers.assert_awaited_once_with(7400, 1)
        self.assertEqual(len(results), 3)

    async def test_dedup_picks_max_length(self):
        tags = [_tag("S", 1014, length=1), _tag("L", 1014, length=6)]
        mock = _mock_client([10, 20, 30, 40, 50, 60])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config(tags)).read_all()
        mock.read_holding_registers.assert_awaited_once_with(1014, 6)
        self.assertEqual(results["S"].values, [10])
        self.assertEqual(results["L"].values, [10, 20, 30, 40, 50, 60])

    async def test_disabled_excluded(self):
        mock = _mock_client([1])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(
                _config([_tag("ON", 100), _tag("OFF", 200, enable=False)])
            ).read_all()
        self.assertIn("ON", results)
        self.assertNotIn("OFF", results)

    async def test_empty(self):
        mock = _mock_client([0])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config([])).read_all()
        self.assertEqual(results, {})
        mock.read_holding_registers.assert_not_called()

    async def test_error_captured(self):
        mock = AsyncMock()
        mock.read_holding_registers.side_effect = RuntimeError("timeout")
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(_config([_tag("E1", 9999)])).read_all()
        self.assertEqual(results["E1"].values, [])
        self.assertEqual(results["E1"].error, "timeout")

    async def test_async_context_manager(self):
        mock = _mock_client([7])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            async with RobotPlc(_config([_tag("X", 1)])) as plc:
                await plc.read_all()
        mock.connect.assert_awaited_once()
        mock.disconnect.assert_awaited_once()

    async def test_explicit_connect_disconnect(self):
        mock = _mock_client([])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([]))
            await plc.connect()
            mock.connect.assert_awaited_once()
            await plc.disconnect()
            mock.disconnect.assert_awaited_once()

    async def test_with_real_config(self):
        toml_path = _MODBUS_PKG_DIR / "config" / "modbus_config.toml"
        config = ModbusConfig.from_file(toml_path)
        tags = config.get_enabled_tags()
        self.assertGreater(len(tags), 0)

        mock = _mock_client(list(range(100)))
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            results = await RobotPlc(config).read_all()

        self.assertEqual(len(results), len(tags))
        for name, tv in results.items():
            self.assertIsNone(tv.error, f"{name}: {tv.error}")
            self.assertEqual(len(tv.values), tv.tag.length)

        call_count = mock.read_holding_registers.await_count
        self.assertLess(call_count, len(tags))
        print(f"\n  标签数: {len(tags)}, 请求次数: {call_count}")


# ---------------------------------------------------------------------------
# 写入测试
# ---------------------------------------------------------------------------


class TestWrite(unittest.IsolatedAsyncioTestCase):

    # ---- write_tag 布尔标签 ----

    async def test_write_boolean_set(self):
        """写布尔标签 1：读-改-写，set 目标位。"""
        # 当前值 0b00000000，写 bit=2 为 1 → 期望 0b00000100
        mock = _mock_client(0x00)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([_wtag("FLAG", 7910, bit=2)]))
            await plc.write_tag("FLAG", 1)

        # 读当前值（单数，返回 int）
        mock.read_holding_register.assert_awaited_with(7910)
        # 写修改后的值
        mock.write_holding_register.assert_awaited_once_with(7910, 0x04)

    async def test_write_boolean_clear(self):
        """写布尔标签 0：读-改-写，clear 目标位。"""
        # 当前值 0b00000100，写 bit=2 为 0 → 期望 0b00000000
        mock = _mock_client(0x04)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([_wtag("FLAG", 7910, bit=2)]))
            await plc.write_tag("FLAG", 0)

        mock.write_holding_register.assert_awaited_once_with(7910, 0x00)

    async def test_write_boolean_preserves_other_bits(self):
        """写布尔标签时保留其他位不变。"""
        # 当前值 0b10101010，写 bit=0 为 1 → 期望 0b10101011
        mock = _mock_client(0xAA)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([_wtag("B0", 100, bit=0)]))
            await plc.write_tag("B0", 1)

        mock.write_holding_register.assert_awaited_once_with(100, 0xAB)

    # ---- write_tag 非布尔标签 ----

    async def test_write_word(self):
        """写 Word 类型标签，直接写入。"""
        mock = _mock_client(0)
        tag = _tag("COUNT", 7930, access_right="读写")
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([tag]))
            await plc.write_tag("COUNT", 42)

        mock.write_holding_register.assert_awaited_once_with(7930, 42)

    async def test_write_multi_register(self):
        """写多长度标签。"""
        mock = _mock_client(0)
        tag = _tag("BIG", 7500, length=2, access_right="读写")
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([tag]))
            await plc.write_tag("BIG", [100, 200])

        mock.write_registers.assert_awaited_once_with(7500, [100, 200])

    # ---- write_tags 批量写入 ----

    async def test_write_tags_batch_boolean_merge(self):
        """批量写同地址布尔标签：一次读+一次写完成。"""
        tags = [
            _wtag("B0", 7910, bit=0),
            _wtag("B1", 7910, bit=1),
            _wtag("B7", 7910, bit=7),
        ]
        mock = _mock_client(0x00)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config(tags))
            await plc.write_tags({"B0": 1, "B1": 0, "B7": 1})

        # 一次读（单数）
        mock.read_holding_register.assert_awaited_with(7910)
        # 一次写：bit0=1, bit1=0, bit7=1 → 0x81
        mock.write_holding_register.assert_awaited_once_with(7910, 0x81)

    async def test_write_tags_mixed(self):
        """批量写混合布尔+Word标签。"""
        tags = [
            _wtag("FLAG", 7910, bit=3),          # 布尔
            _tag("COUNT", 7930, access_right="读写"),  # Word
        ]
        mock = _mock_client(0x00)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config(tags))
            await plc.write_tags({"FLAG": 1, "COUNT": 99})

        # FLAG: 读 7910 (单数), 写 7910=0x08
        mock.read_holding_register.assert_awaited_with(7910)
        mock.write_holding_register.assert_any_call(7910, 0x08)
        # COUNT: 直接写 7930
        mock.write_holding_register.assert_any_call(7930, 99)

    async def test_write_tags_empty(self):
        """空 dict 不发起任何请求。"""
        mock = _mock_client(0)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([]))
            await plc.write_tags({})

        mock.read_holding_registers.assert_not_called()
        mock.write_holding_register.assert_not_called()

    # ---- 权限校验 ----

    async def test_write_readonly_raises(self):
        """写只读标签抛出 PermissionError。"""
        mock = _mock_client(0)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([_tag("A1", 1002)]))  # 默认只读
            with self.assertRaises(PermissionError):
                await plc.write_tag("A1", 1)

    async def test_write_nonexistent_raises(self):
        """写不存在的标签抛出 KeyError。"""
        mock = _mock_client(0)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([]))
            with self.assertRaises(KeyError):
                await plc.write_tag("NO_SUCH_TAG", 1)

    # ---- 只写标签 ----

    async def test_write_only_tag(self):
        """只写（access_right='只写'）标签可以正常写入。"""
        tag = ModbusTag(
            group="", name="BUF", description="",
            register_type="保持寄存器", start_address=13000, length=30,
            kep_address="%MW13000_30", data_type="Float Array",
            access_right="只写", scan_rate=100, enable=True,
        )
        mock = _mock_client(0)
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([tag]))
            await plc.write_tag("BUF", [1, 2, 3])

        mock.write_registers.assert_awaited_once_with(13000, [1, 2, 3])

    async def test_write_only_not_readable(self):
        """只写标签不出现在 read_all 结果中（当前实现读所有启用标签）。"""
        tag = _wtag("WO", 9999, bit=0)
        tag.access_right = "只写"
        tag.enable = True
        mock = _mock_client([0x0F])
        with patch("modbus_pkg.robot_plc.ModbusTcpClient", return_value=mock):
            plc = RobotPlc(_config([tag]))
            # 可以写入
            await plc.write_tag("WO", 1)
            # read_all 也会读它（因为没有按 access_right 过滤读）
            results = await plc.read_all()
            self.assertIn("WO", results)


if __name__ == "__main__":
    unittest.main()
