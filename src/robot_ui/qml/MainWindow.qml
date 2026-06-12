import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick3D

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 1280
    height: 800
    title: "机器人打磨控制系统"
    color: "#1a1a2e"

    // ── 全局颜色常量 ──
    readonly property color bgColor: "#1a1a2e"
    readonly property color panelColor: "#16213e"
    readonly property color accentColor: "#0f3460"
    readonly property color highlightColor: "#e94560"
    readonly property color textColor: "#eee"
    readonly property color greenColor: "#00b894"
    readonly property color warningColor: "#fdcb6e"
    readonly property color dangerColor: "#e17055"

    // ── 主布局 ──
    RowLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        // ═══════════════════════════════════════
        // 左侧：控制按钮面板
        // ═══════════════════════════════════════
        ControlPanel {
            id: controlPanel
            Layout.preferredWidth: 200
            Layout.fillHeight: true
        }

        // ═══════════════════════════════════════
        // 中间：三维模型显示区
        // ═══════════════════════════════════════
        Robot3DView {
            id: robot3DView
            Layout.fillWidth: true
            Layout.fillHeight: true
        }

        // ═══════════════════════════════════════
        // 右侧：状态信息面板
        // ═══════════════════════════════════════
        StatusPanel {
            id: statusPanel
            Layout.preferredWidth: 260
            Layout.fillHeight: true
        }
    }

    // ── 底部状态栏 ──
    StatusBar {
        id: statusBar
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 8
    }
}
