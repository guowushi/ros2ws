"""通用 MODBUS TCP 客户端基类。

基于 pymodbus，提供同步和异步两种使用方式，封装常用寄存器读写操作。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient

from .config_parser import ModbusConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class RegisterValue:
    """单个寄存器的值及其地址信息。"""

    address: int
    value: int
    name: str = ""


# ---------------------------------------------------------------------------
# MODBUS TCP 客户端
# ---------------------------------------------------------------------------


class ModbusTcpClient:
    """通用 MODBUS TCP 客户端。

    封装 pymodbus AsyncModbusTcpClient，提供按地址/名称读写寄存器的便捷方法。
    支持 async with 上下文管理器。

    使用示例::

        async with ModbusTcpClient(connection) as client:
            # 读取单个保持寄存器
            val = await client.read_holding_register(1002)
            # 读取连续多个寄存器
            vals = await client.read_holding_registers(1002, 6)
            # 按标签名读取
            val = await client.read_tag(config.get_tag("A1"))
            # 写入单个寄存器
            await client.write_holding_register(1002, 180)
    """

    def __init__(self, connection: ModbusConnection, timeout: float = 3.0) -> None:
        self._connection = connection
        self._timeout = timeout
        self._client: Optional[AsyncModbusTcpClient] = None

    # ---- 连接管理 ----

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.connected

    async def connect(self) -> None:
        """建立 TCP 连接。"""
        if self.connected:
            return
        self._client = AsyncModbusTcpClient(
            host=self._connection.ip,
            port=self._connection.port,
            timeout=self._timeout,
        )
        await self._client.connect()
        logger.info("MODBUS 已连接 %s:%d", self._connection.ip, self._connection.port)

    async def disconnect(self) -> None:
        """关闭 TCP 连接。"""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("MODBUS 已断开")

    async def __aenter__(self) -> ModbusTcpClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.disconnect()

    def _require_client(self) -> AsyncModbusTcpClient:
        if self._client is None or not self._client.connected:
            raise RuntimeError("MODBUS 未连接，请先调用 connect()")
        return self._client

    # ---- 保持寄存器 读取 ----

    async def read_holding_register(self, address: int) -> int:
        """读取单个保持寄存器，返回其整数值。"""
        client = self._require_client()
        rr = await client.read_holding_registers(address, count=1)
        if rr.isError():
            raise ModbusError(f"读取保持寄存器 {address} 失败", rr)
        return rr.registers[0]

    async def read_holding_registers(
        self, address: int, count: int
    ) -> list[int]:
        """读取连续多个保持寄存器。"""
        if count <= 0:
            return []
        client = self._require_client()
        rr = await client.read_holding_registers(address, count=count)
        if rr.isError():
            raise ModbusError(f"读取保持寄存器 [{address}:{address+count}) 失败", rr)
        return list(rr.registers)

    # ---- 保持寄存器 写入 ----

    async def write_holding_register(self, address: int, value: int) -> None:
        """写入单个保持寄存器。"""
        client = self._require_client()
        rr = await client.write_register(address, value)
        if rr.isError():
            raise ModbusError(f"写入保持寄存器 {address} 失败", rr)

    async def write_holding_registers(
        self, address: int, values: list[int]
    ) -> None:
        """连续写入多个保持寄存器。"""
        if not values:
            return
        client = self._require_client()
        rr = await client.write_registers(address, values)
        if rr.isError():
            raise ModbusError(f"写入保持寄存器 [{address}:{address+len(values)}) 失败", rr)

    # ---- 线圈 读取 / 写入 ----

    async def read_coil(self, address: int) -> bool:
        """读取单个线圈。"""
        client = self._require_client()
        rr = await client.read_coils(address, count=1)
        if rr.isError():
            raise ModbusError(f"读取线圈 {address} 失败", rr)
        return rr.bits[0]

    async def read_coils(self, address: int, count: int) -> list[bool]:
        """连续读取多个线圈。"""
        if count <= 0:
            return []
        client = self._require_client()
        rr = await client.read_coils(address, count=count)
        if rr.isError():
            raise ModbusError(f"读取线圈 [{address}:{address+count}) 失败", rr)
        return list(rr.bits)

    async def write_coil(self, address: int, value: bool) -> None:
        """写入单个线圈。"""
        client = self._require_client()
        rr = await client.write_coil(address, value)
        if rr.isError():
            raise ModbusError(f"写入线圈 {address} 失败", rr)

    # ---- 便捷方法：按标签操作 ----

    async def read_tag(self, tag) -> int | list[int]:
        """根据 ModbusTag 读取寄存器值。

        单长度返回 int，多长度返回 list[int]。
        """
        from .config_parser import ModbusTag

        if tag.length == 1:
            return await self.read_holding_register(tag.start_address)
        return await self.read_holding_registers(tag.start_address, tag.length)

    async def write_tag(self, tag, value: int | list[int]) -> None:
        """根据 ModbusTag 写入寄存器值。"""
        if tag.length == 1:
            if isinstance(value, list):
                value = value[0]
            await self.write_holding_register(tag.start_address, value)
        else:
            if isinstance(value, int):
                value = [value]
            await self.write_holding_registers(tag.start_address, value)


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class ModbusError(Exception):
    """MODBUS 通信异常。"""

    def __init__(self, message: str, pdu=None) -> None:
        super().__init__(message)
        self.pdu = pdu
