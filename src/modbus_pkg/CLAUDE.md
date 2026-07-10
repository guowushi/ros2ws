# 配置文件说明
- modbus_config.toml为PLC的配置文件，包含PLC的地址、端口、数据位、停止位、校验位等信息
- start_address为PLC的起始地址，用于读取标签的地址偏移量
- kep_address 为施耐德PLC的地址写法
- length为PLC的标签数量，用于读取标签的长度
- scale为标签的缩放因子，用于将读取到的原始值转换为物理值
  - data_type为标签的数据类型，可选值为 int32（32位有符号整数）、uint32（32位无符号整数）、string（字符串）、float（32位浮点数）、bool（布尔值，按位提取）

# 代码编写要求
- 在 robot_plc.py 中实现具体的PLC读取方法
- 多个连续的地址标签，批量读取
- 写入bool类型标签时，需要将布尔值转换为0或1，先读取标签，再写入

