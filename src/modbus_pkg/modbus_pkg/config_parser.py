"""MODBUS 配置文件解析器。

读取 modbus_config.toml，将 [modbus] 连接信息和 [[tags]] 列表解析为 Python 对象。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ModbusTag:
    """单个 MODBUS 寄存器标签。"""

    group: str
    name: str
    description: str
    register_type: str
    start_address: int
    length: int
    kep_address: str
    data_type: str
    access_right: str
    scan_rate: int
    enable: bool
    scale: float = 1.0


@dataclass
class ModbusConnection:
    """MODBUS 连接参数。"""

    ip: str
    port: int
    description: str
    version: str


@dataclass
class ModbusConfig:
    """解析后的 MODBUS 配置文件。"""

    connection: ModbusConnection
    tags: list[ModbusTag] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> ModbusConfig:
        """从 TOML 文件加载配置。"""
        with open(path, "rb") as f:
            raw = tomllib.load(f)

        modbus = raw["modbus"]
        connection = ModbusConnection(
            ip=modbus["ip"],
            port=modbus["port"],
            description=modbus.get("description", ""),
            version=modbus.get("version", ""),
        )

        tags = [
            ModbusTag(
                group=t.get("group", ""),
                name=t["name"],
                description=t.get("description", ""),
                register_type=t.get("register_type", ""),
                start_address=t["start_address"],
                length=t["length"],
                kep_address=t.get("kep_address", ""),
                data_type=t.get("data_type", ""),
                access_right=t.get("access_right", ""),
                scan_rate=t.get("scan_rate", 100),
                enable=t.get("enable", True),
                scale=t.get("scale", 1.0),
            )
            for t in raw.get("tags", [])
        ]

        return cls(connection=connection, tags=tags)

    # ---- 查询方法 ----

    def get_tag(self, name: str) -> Optional[ModbusTag]:
        """按名称查找标签，未找到返回 None。"""
        for t in self.tags:
            if t.name == name:
                return t
        return None

    def get_tags_by_group(self, group: str) -> list[ModbusTag]:
        """返回指定分组的所有标签。"""
        return [t for t in self.tags if t.group == group]

    def get_enabled_tags(self) -> list[ModbusTag]:
        """返回所有启用的标签。"""
        return [t for t in self.tags if t.enable]

    @property
    def group_names(self) -> list[str]:
        """所有不重复的分组名。"""
        seen: set[str] = set()
        result: list[str] = []
        for t in self.tags:
            if t.group and t.group not in seen:
                seen.add(t.group)
                result.append(t.group)
        return result
