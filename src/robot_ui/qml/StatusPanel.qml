import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    color: panelColor
    radius: 8

    property color panelColor: "#16213e"
    property color accentColor: "#0f3460"
    property color textColor: "#eee"
    property color greenColor: "#00b894"
    property color warningColor: "#fdcb6e"
    property color dangerColor: "#e17055"

    // ── 关节角度显示值 ──
    property string j1: "--.--"
    property string j2: "--.--"
    property string j3: "--.--"
    property string j4: "--.--"
    property string j5: "--.--"
    property string j6: "--.--"

    // ── 笛卡尔坐标显示值 ──
    property string cx: "--.--"
    property string cy: "--.--"
    property string cz: "--.--"
    property string ca: "--.--"
    property string cb: "--.--"
    property string cc: "--.--"

    // ── 接收 Bridge 信号 ──
    Connections {
        target: bridge

        function onJointAnglesChanged(a1, a2, a3, a4, a5, a6) {
            root.j1 = a1.toFixed(2)
            root.j2 = a2.toFixed(2)
            root.j3 = a3.toFixed(2)
            root.j4 = a4.toFixed(2)
            root.j5 = a5.toFixed(2)
            root.j6 = a6.toFixed(2)
        }

        function onCartesianChanged(x, y, z, a, b, c) {
            root.cx = x.toFixed(2)
            root.cy = y.toFixed(2)
            root.cz = z.toFixed(2)
            root.ca = a.toFixed(2)
            root.cb = b.toFixed(2)
            root.cc = c.toFixed(2)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Text {
            text: "状态信息"
            color: textColor
            font.pixelSize: 18
            font.bold: true
            Layout.alignment: Qt.AlignHCenter
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 机器人坐标 ──
        SectionLabel { text: "关节角度 (°)" }
        GridLayout {
            columns: 2
            rowSpacing: 4
            columnSpacing: 8
            Layout.fillWidth: true

            JointValue { label: "A1"; value: j1 }
            JointValue { label: "A2"; value: j2 }
            JointValue { label: "A3"; value: j3 }
            JointValue { label: "A4"; value: j4 }
            JointValue { label: "A5"; value: j5 }
            JointValue { label: "A6"; value: j6 }
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 笛卡尔坐标 ──
        SectionLabel { text: "笛卡尔坐标 (mm / °)" }
        GridLayout {
            columns: 2
            rowSpacing: 4
            columnSpacing: 8
            Layout.fillWidth: true

            CoordValue { label: "X"; value: cx }
            CoordValue { label: "Y"; value: cy }
            CoordValue { label: "Z"; value: cz }
            CoordValue { label: "A"; value: ca }
            CoordValue { label: "B"; value: cb }
            CoordValue { label: "C"; value: cc }
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 工艺参数 ──
        SectionLabel { text: "工艺参数" }
        GridLayout {
            columns: 2
            rowSpacing: 4
            Layout.fillWidth: true

            ParamRow { label: "打磨压力"; value: "--" }
            ParamRow { label: "工具转速"; value: "-- rpm" }
            ParamRow { label: "行走速度"; value: "-- mm/s" }
            ParamRow { label: "砂轮半径"; value: "-- mm" }
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 统计信息 ──
        SectionLabel { text: "当班统计" }
        GridLayout {
            columns: 2
            rowSpacing: 4
            Layout.fillWidth: true

            ParamRow { label: "开机时间"; value: "-- h" }
            ParamRow { label: "打磨时间"; value: "-- h" }
            ParamRow { label: "打磨面积"; value: "-- m²" }
        }

        Rectangle { Layout.preferredHeight: 1; Layout.fillWidth: true; color: accentColor }

        // ── 报警状态 ──
        SectionLabel { text: "报警状态" }
        RowLayout {
            spacing: 8
            Rectangle {
                width: 12; height: 12; radius: 6
                color: greenColor
            }
            Text { text: "无报警"; color: greenColor; font.pixelSize: 13 }
        }

        Item { Layout.fillHeight: true }
    }

    // ── 子组件 ──

    component SectionLabel: Text {
        color: "#8899aa"
        font.pixelSize: 12
        font.bold: true
    }

    component ParamRow: RowLayout {
        property alias label: labelText.text
        property alias value: valueText.text

        Text { id: labelText; color: "#667788"; font.pixelSize: 12; Layout.preferredWidth: 65 }
        Text { id: valueText; color: "white"; font.pixelSize: 13; font.bold: true }
    }

    component JointValue: ColumnLayout {
        property alias label: labelText.text
        property alias value: valueText.text

        spacing: 0
        Text { id: labelText; color: "#8899aa"; font.pixelSize: 11 }
        Text {
            id: valueText
            color: root.textColor
            font.pixelSize: 15
            font.bold: true
        }
    }

    component CoordValue: RowLayout {
        property alias label: labelText.text
        property alias value: valueText.text

        spacing: 4
        Text { id: labelText; color: "#8899aa"; font.pixelSize: 12; Layout.preferredWidth: 16 }
        Text {
            id: valueText
            color: root.textColor
            font.pixelSize: 14
            font.bold: true
        }
    }
}
