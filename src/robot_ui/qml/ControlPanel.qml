import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    color: panelColor
    radius: 8

    property color panelColor: "#16213e"
    property color accentColor: "#0f3460"
    property color highlightColor: "#e94560"
    property color textColor: "#eee"
    property color greenColor: "#00b894"
    property color warningColor: "#fdcb6e"
    property color dangerColor: "#e17055"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        // 标题
        Text {
            text: "控制面板"
            color: textColor
            font.pixelSize: 18
            font.bold: true
            Layout.alignment: Qt.AlignHCenter
        }

        // ── 系统启动 ──
        CtrlButton {
            text: "启动"
            icon: "🚀"
            btnColor: greenColor
            onClicked: bridge.systemStart()
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 机器人操作 ──
        SectionLabel { text: "机器人操作" }

        CtrlButton {
            text: "回原点"
            icon: "🏠"
            btnColor: accentColor
            onClicked: bridge.robotReturnToOrigin()
        }

        CtrlButton {
            text: "急停"
            icon: "⏹"
            btnColor: dangerColor
            onClicked: bridge.emergencyStop()
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 扫描控制 ──
        SectionLabel { text: "扫描控制" }

        CtrlButton {
            text: "准备扫描"
            icon: "📷"
            btnColor: accentColor
            onClicked: bridge.scanReady()
        }

        CtrlButton {
            text: "开始扫描"
            icon: "▶"
            btnColor: greenColor
            onClicked: bridge.scanStart()
        }

        CtrlButton {
            text: "暂停扫描"
            icon: "⏸"
            btnColor: warningColor
            onClicked: bridge.scanPause()
        }

        CtrlButton {
            text: "结束扫描"
            icon: "⏹"
            btnColor: dangerColor
            onClicked: bridge.scanEnd()
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 打磨控制 ──
        SectionLabel { text: "打磨控制" }

        CtrlButton {
            text: "路径计算"
            icon: "📐"
            btnColor: accentColor
            onClicked: bridge.computePaths()
        }

        CtrlButton {
            text: "开始打磨"
            icon: "⚙"
            btnColor: greenColor
            onClicked: bridge.startPolish()
        }

        CtrlButton {
            text: "暂停打磨"
            icon: "⏸"
            btnColor: warningColor
            onClicked: bridge.pausePolish()
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 辅助操作 ──
        SectionLabel { text: "辅助操作" }

        CtrlButton {
            text: "工具快换"
            icon: "🔧"
            btnColor: accentColor
            onClicked: bridge.toolQuickChange()
        }

        CtrlButton {
            text: "相机抓取"
            icon: "📸"
            btnColor: accentColor
            onClicked: bridge.cameraGrab()
        }

        CtrlButton {
            text: "相机放下"
            icon: "📥"
            btnColor: accentColor
            onClicked: bridge.cameraPutDown()
        }

        CtrlButton {
            text: "导轨回原点"
            icon: "↔"
            btnColor: accentColor
            onClicked: bridge.railReturnToOrigin()
        }

        Item { Layout.fillHeight: true } // 弹簧，把按钮推向上方
    }

    // ── 子组件 ──

    component SectionLabel: Text {
        color: "#8899aa"
        font.pixelSize: 12
        font.bold: true
    }

    component CtrlButton: Rectangle {
        id: btn
        property string icon: ""
        property alias text: btnText.text
        property color btnColor: "#0f3460"
        signal clicked()

        Layout.fillWidth: true
        Layout.preferredHeight: 38
        radius: 6
        color: btnMouse.pressed ? Qt.darker(btnColor, 1.2) : btnColor

        RowLayout {
            anchors.centerIn: parent
            spacing: 8

            Text {
                text: icon
                font.pixelSize: 16
            }
            Text {
                id: btnText
                color: "white"
                font.pixelSize: 14
                font.bold: true
            }
        }

        MouseArea {
            id: btnMouse
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }
}
