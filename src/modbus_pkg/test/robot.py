import asyncio
from ..modbus_pkg.config_parser import ModbusConfig
from ..modbus_pkg.robot_plc import RobotPlc

config = ModbusConfig.from_file("config/modbus_config.toml")

async def main():
    async with RobotPlc(config) as plc:
        # 读取全部标签
        results = await plc.read_all()
        print(f"读取结果: {results}")
        
        # 写入单个标签
        await plc.write_tag("PATHS_COMPUTE_FINISHED_FLAG", 1)
        
        # 批量写入
        await plc.write_tags({"SCAN_REQ": 1, "SCAN_END": 0})

if __name__ == "__main__":
    asyncio.run(main())