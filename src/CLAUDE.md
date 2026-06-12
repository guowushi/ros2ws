机器人应用源代码
- camera_pkg              ← 相机包，实现图像采集和目标检测
- modbus_pkg              ← MODBUS包，实现从PLC读取modbus数据，写入modbus数据
- model_processing_pkg    ← 模型处理包
- path_plan_pkg           ← 路径规划包，实现路径规划和导航功能
- motion_control_pkg      ← 运动控制包，实现运动控制功能
- robot_interfaces        ← 接口包
- robot_bringup           ← 启动包
- robot_ui                ← 界面包


每个包下
- config目录： 存放配置
- test目录：存放测试文件，每次测试结果使用MD格式保存下来，文件名为YYYY-MM-DD-HH-mm格式
- logs目录：存放日志

