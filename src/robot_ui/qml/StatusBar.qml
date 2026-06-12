import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    height: 36
    color: "#16213e"
    radius: 6

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 24

        // MODBUS 连接状态
        RowLayout {
            spacing: 6
            Rectangle {
                width: 10; height: 10; radius: 5
                color: modbusConnected ? "#00b894" : "#e17055"
            }
            Text {
                text: modbusConnected ? "MODBUS 已连接" : "MODBUS 未连接"
                color: modbusConnected ? "#00b894" : "#e17055"
                font.pixelSize: 12
            }
        }

        // 心跳指示
        RowLayout {
            spacing: 6
            Rectangle {
                id: heartbeatDot
                width: 10; height: 10; radius: 5
                color: heartbeat ? "#00b894" : "#636e72"
                SequentialAnimation on color {
                    running: heartbeat
                    loops: Animation.Infinite
                    PropertyAnimation { to: "#00b894"; duration: 500 }
                    PropertyAnimation { to: "#00ffcc"; duration: 500 }
                }
            }
            Text {
                text: "PC 心跳"
                color: "#8899aa"
                font.pixelSize: 12
            }
        }

        Item { Layout.fillWidth: true }

        // 工件信息
        Text {
            text: "工件编号: " + workpieceName
            color: "#667788"
            font.pixelSize: 12
        }

        // 时间
        Text {
            text: new Date().toLocaleString(Qt.locale(), "yyyy-MM-dd hh:mm:ss")
            color: "#667788"
            font.pixelSize: 12
        }
    }

    // ── 绑定属性 ──
    property bool modbusConnected: false
    property bool heartbeat: false
    property string workpieceName: "--"

    Connections {
        target: bridge

        function onModbusStatusChanged(connected) {
            root.modbusConnected = connected
        }

        function onHeartbeatChanged(alive) {
            root.heartbeat = alive
        }

        function onWorkpieceNameChanged(name) {
            root.workpieceName = name
        }
    }
}
