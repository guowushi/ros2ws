"""RobotPlc - 机器人PLC数据读写类。

使用 ModbusConfig 解析配置文件，使用 ModbusTcpClient 批量读取/写入所有地址。
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config_parser import ModbusConfig, ModbusTag
from .modbus_client import ModbusTcpClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_FMT = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 记录当前激活的 handler，便于按类型开关
_console_handler: Optional[logging.StreamHandler] = None
_file_handler: Optional[logging.FileHandler] = None


def enable_console_log(level: int = logging.INFO) -> None:
    """开启 console 日志。"""
    global _console_handler
    if _console_handler is not None:
        return
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(level)
    _console_handler.setFormatter(_FMT)
    logger.addHandler(_console_handler)


def disable_console_log() -> None:
    """关闭 console 日志。"""
    global _console_handler
    if _console_handler is not None:
        logger.removeHandler(_console_handler)
        _console_handler = None


def enable_file_log(
    path: str | Path | None = None, level: int = logging.INFO
) -> None:
    """开启文件日志。

    Args:
        path: 日志目录，默认 ``modbus_pkg/logs/``。
        level: 日志级别，默认 INFO。
    """
    global _file_handler
    if _file_handler is not None:
        return
    if path is None:
        path = Path(__file__).resolve().parent.parent / "logs"
    log_dir = Path(path)
    log_dir.mkdir(parents=True, exist_ok=True)
    _file_handler = logging.FileHandler(
        log_dir / "robot_plc.log", encoding="utf-8"
    )
    _file_handler.setLevel(level)
    _file_handler.setFormatter(_FMT)
    logger.addHandler(_file_handler)


def disable_file_log() -> None:
    """关闭文件日志。"""
    global _file_handler
    if _file_handler is not None:
        logger.removeHandler(_file_handler)
        _file_handler = None


# 默认：仅 console 开，文件关
enable_console_log()


def _parse_kep_bit(kep_address: str) -> Optional[int]:
    """从 kep_address 解析位位置。``%MW07910.0`` → 0，无位信息 → None。"""
    m = re.match(r"^%MW\d+\.(\d+)$", kep_address, re.IGNORECASE)
    return int(m.group(1)) if m else None


@dataclass
class TagValue:
    """标签读取结果。"""

    tag: ModbusTag
    values: list[int]
    error: Optional[str] = None


class RobotPlc:
    """机器人PLC数据读写器。

    封装 ModbusConfig 和 ModbusTcpClient，提供一键读写标签的功能。
    读取时相同起始地址只请求一次；写入布尔标签时自动读-改-写，保护共享地址的其他位。

    使用示例::

        config = ModbusConfig.from_file("config/modbus_config.toml")
        async with RobotPlc(config) as plc:
            # 读取全部标签
            results = await plc.read_all()
            # 写入单个标签
            await plc.write_tag("PATHS_COMPUTE_FINISHED_FLAG", 1)
            # 批量写入（同地址布尔标签合并为一次写操作）
            await plc.write_tags({"SCAN_REQ": 1, "SCAN_END": 0})
    """

    def __init__(self, config: ModbusConfig, timeout: float = 3.0) -> None:
        self._config = config
        self._client = ModbusTcpClient(config.connection, timeout=timeout)
        # 缓存：可写标签名 → tag
        self._writable_by_name: dict[str, ModbusTag] = {}
        self._init_writable_cache()

    # ---- 连接管理 ----

    @property
    def connected(self) -> bool:
        return self._client.connected

    async def connect(self) -> None:
        """建立 MODBUS 连接。"""
        await self._client.connect()

    async def disconnect(self) -> None:
        """断开 MODBUS 连接。"""
        await self._client.disconnect()

    async def __aenter__(self) -> RobotPlc:
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.disconnect()

    # ---- 读取 ----

    async def read_all(self) -> dict[str, TagValue]:
        """读取所有启用的标签。

        按起始地址分组去重后批量读取，同一地址只发一次 MODBUS 请求，
        结果按标签名索引返回。
        """
        enabled = self._config.get_enabled_tags()
        if not enabled:
            return {}

        # 按起始地址分组去重
        addr_to_tags: dict[int, list[ModbusTag]] = {}
        for tag in enabled:
            if tag.start_address not in addr_to_tags:
                addr_to_tags[tag.start_address] = []
            addr_to_tags[tag.start_address].append(tag)

        results: dict[str, TagValue] = {}
        for addr, tags in addr_to_tags.items():
            max_length = max(t.length for t in tags)
            try:
                values = await self._client.read_holding_registers(addr, max_length)
                for tag in tags:
                    results[tag.name] = TagValue(
                        tag=tag,
                        values=values[: tag.length],
                    )
            except Exception as e:
                logger.error("读取地址 %d 失败: %s", addr, e)
                for tag in tags:
                    results[tag.name] = TagValue(
                        tag=tag,
                        values=[],
                        error=str(e),
                    )

        return results

    # ---- 写入 ----

    def _init_writable_cache(self) -> None:
        """缓存所有可写标签名 → tag 映射。"""
        self._writable_by_name.clear()
        for t in self._config.tags:
            if t.access_right in ("读写", "只写"):
                self._writable_by_name[t.name] = t

    def _resolve_writable(self, name: str) -> ModbusTag:
        """按名称查找可写标签，未找到或只读时抛出异常。"""
        if name not in self._writable_by_name:
            tag = self._config.get_tag(name)
            if tag is None:
                raise KeyError(f"标签 '{name}' 不存在")
            raise PermissionError(f"标签 '{name}' 为只读，不可写入")
        return self._writable_by_name[name]

    async def write_tag(self, name: str, value: int | list[int]) -> None:
        """写入单个标签。

        布尔标签共享地址时自动读-改-写，保护同一寄存器上的其他位。::

            await plc.write_tag("SCAN_REQ", 1)
            await plc.write_tag("PATHS_COUNT", 42)
            await plc.write_tag("USER_NAME", [0x41, 0x42, ...])  # 多长度
        """
        tag = self._resolve_writable(name)
        bit = _parse_kep_bit(tag.kep_address)

        if bit is not None:
            # 布尔标签：读-改-写，只修改目标位
            current = await self._client.read_holding_register(tag.start_address)
            if value:
                new_val = current | (1 << bit)
            else:
                new_val = current & ~(1 << bit)
            await self._client.write_holding_register(tag.start_address, new_val)
            logger.info(
                "写入 %s (addr=%d, bit=%d): %d → %d",
                name, tag.start_address, bit, current, new_val,
            )
        else:
            await self._client.write_tag(tag, value)
            logger.info("写入 %s (addr=%d): %s", name, tag.start_address, value)


    async def write_tags(self, values: dict[str, int | list[int]]) -> None:
        """批量写入多个标签。

        同地址的布尔标签自动合并为一次读-改-写，减少 MODBUS 请求次数。::

            await plc.write_tags({
                "SCAN_READY": 1,
                "SCAN_REQ": 0,
                "SCAN_SPEED": 500,
            })
        """
        if not values:
            return

        # 解析并验证全部标签
        resolved: dict[str, tuple[ModbusTag, int | list[int]]] = {}
        for name, value in values.items():
            resolved[name] = (self._resolve_writable(name), value)

        # 按起始地址分组
        by_addr: dict[int, list[tuple[str, ModbusTag, int | list[int]]]] = defaultdict(list)
        for name, (tag, value) in resolved.items():
            by_addr[tag.start_address].append((name, tag, value))

        for addr, entries in by_addr.items():
            # 分离布尔标签（有位信息）和直接写入标签
            bool_entries = [
                (name, tag, val)
                for name, tag, val in entries
                if _parse_kep_bit(tag.kep_address) is not None
            ]
            direct_entries = [
                (name, tag, val)
                for name, tag, val in entries
                if _parse_kep_bit(tag.kep_address) is None
            ]

            if bool_entries:
                # 读-改-写：一次读取 + 一次写入完成所有布尔标签
                current = await self._client.read_holding_register(addr)
                new_val = current
                names = []
                for name, tag, value in bool_entries:
                    bit = _parse_kep_bit(tag.kep_address)
                    if value:
                        new_val |= 1 << bit
                    else:
                        new_val &= ~(1 << bit)
                    names.append(name)
                if new_val != current:
                    await self._client.write_holding_register(addr, new_val)
                logger.info(
                    "批量写入 %s (addr=%d): 0x%04X → 0x%04X",
                    names, addr, current, new_val,
                )

            for name, tag, value in direct_entries:
                await self._client.write_tag(tag, value)
                logger.info("写入 %s (addr=%d): %s", name, tag.start_address, value)

    