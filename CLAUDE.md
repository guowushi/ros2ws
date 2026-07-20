
# 系统开发环境

## 系统环境
- 操作系统：Ubuntu 24
- ROS2版本：Jazzy  文档 https://docs.ros.org/en/jazzy
- ROS2安装路径： /opt/ros/jazzy

## 硬件环境
- 工控机（测试机器）：IP地址：192.168.3.100 ，管理员用户 robot，管理员密码11
- PLC：型号 Schneider Modicon M241 ；协议ModbusTCP，IP地址：192.168.3.7
- 相机：型号orbbec Gemini 435Le IP地址：192.168.1.10
- 机器人：型号，通信协议；IP地址：192.168.3.9

## 工控机（测试机器）软件环境
- ROS2版本：Jazzy 
- ROS2安装路径： /opt/ros/jazzy
- ROS2工作空间路径：~/ros2ws
- 三维建模包：gemini435le_3d_modeling  工作空间路径： ~/gemini435le_3d_modeling_ws
- 相机包： camera_py_pkg  工作空间路径： ~/camera_gemini435_ws

# 编译
- 进入ros2工作空间：cd ~/ros2ws
- 编译所有的ros2包：colcon build   


# 运行
- 运行lifecycle节点： ros2 run modbus_pkg robot_plc
- 
