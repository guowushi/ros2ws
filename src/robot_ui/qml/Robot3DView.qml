import QtQuick
import QtQuick3D
import QtQuick3D.Helpers

Rectangle {
    id: root
    color: "#0d1117"
    radius: 8
    border.color: "#0f3460"
    border.width: 1

    // ── 3D 场景 ──
    View3D {
        id: view3D
        anchors.fill: parent
        anchors.margins: 4
        camera: camera
        // 环境光
        environment: SceneEnvironment {
            id: sceneEnvironment
            clearColor: "#1a1a2e"
            backgroundMode: SceneEnvironment.Color
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        // 透视相机
        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(600, 400, 800)
            eulerRotation: Qt.vector3d(-25, -35, 0)
            clipNear: 10
            clipFar: 5000
        }

        // 网格参考面
        Model {
            position: Qt.vector3d(0, -200, 0)
            scale: Qt.vector3d(10, 1, 10)
            source: "#Rectangle"
            materials: DefaultMaterial {
                diffuseColor: "#1a1a2e"
                lighting: DefaultMaterial.FragmentLighting
            }
        }

        // 网格线
        Repeater3D {
            model: 21
            delegate: Model {
                position: Qt.vector3d((index - 10) * 50, -199, 0)
                scale: Qt.vector3d(0.5, 1, 1000)
                source: "#Rectangle"
                materials: DefaultMaterial {
                    diffuseColor: "#222244"
                    lighting: DefaultMaterial.NoLighting
                }
            }
        }
        Repeater3D {
            model: 21
            delegate: Model {
                position: Qt.vector3d(0, -199, (index - 10) * 50)
                eulerRotation: Qt.vector3d(0, 90, 0)
                scale: Qt.vector3d(0.5, 1, 1000)
                source: "#Rectangle"
                materials: DefaultMaterial {
                    diffuseColor: "#222244"
                    lighting: DefaultMaterial.NoLighting
                }
            }
        }

        // ═══════════════════════════════════════
        // 简易工业机器人模型（6 轴关节臂）
        // ═══════════════════════════════════════

        Node {
            id: robotRoot
            position: Qt.vector3d(0, -200, 0)

            // 底座
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(0, -30, 0)
                scale: Qt.vector3d(1.2, 0.6, 1.2)
                materials: DefaultMaterial {
                    diffuseColor: "#445566"
                    specularAmount: 0.3
                    specularRoughness: 0.4
                }
            }

            // J1 — 基座旋转
            Node {
                id: joint1
                position: Qt.vector3d(0, 0, 0)
                eulerRotation.y: j1Angle

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(0, 15, 0)
                    scale: Qt.vector3d(0.7, 0.3, 0.7)
                    materials: DefaultMaterial {
                        diffuseColor: "#556677"
                        specularAmount: 0.3
                        specularRoughness: 0.4
                    }
                }

                // J2 — 肩部俯仰
                Node {
                    id: joint2
                    position: Qt.vector3d(0, 30, 0)
                    eulerRotation.x: j2Angle

                    Model {
                        source: "#Cylinder"
                        position: Qt.vector3d(0, 60, 40)
                        eulerRotation.z: 90
                        scale: Qt.vector3d(0.4, 1.2, 0.4)
                        materials: DefaultMaterial {
                            diffuseColor: "#667788"
                            specularAmount: 0.3
                            specularRoughness: 0.4
                        }
                    }

                    // J3 — 肘部
                    Node {
                        id: joint3
                        position: Qt.vector3d(0, 120, 80)
                        eulerRotation.x: j3Angle

                        Model {
                            source: "#Cylinder"
                            position: Qt.vector3d(0, 50, 30)
                            eulerRotation.z: 90
                            scale: Qt.vector3d(0.35, 1.0, 0.35)
                            materials: DefaultMaterial {
                                diffuseColor: "#778899"
                                specularAmount: 0.3
                                specularRoughness: 0.4
                            }
                        }

                        // J4 — 腕部旋转
                        Node {
                            id: joint4
                            position: Qt.vector3d(0, 100, 60)
                            eulerRotation.y: j4Angle

                            Model {
                                source: "#Cylinder"
                                position: Qt.vector3d(0, 20, 0)
                                scale: Qt.vector3d(0.3, 0.4, 0.3)
                                materials: DefaultMaterial {
                                    diffuseColor: "#889999"
                                    specularAmount: 0.3
                                    specularRoughness: 0.4
                                }
                            }

                            // J5 — 腕部俯仰
                            Node {
                                id: joint5
                                position: Qt.vector3d(0, 40, 0)
                                eulerRotation.x: j5Angle

                                Model {
                                    source: "#Cylinder"
                                    position: Qt.vector3d(0, 15, 15)
                                    eulerRotation.z: 90
                                    scale: Qt.vector3d(0.22, 0.35, 0.22)
                                    materials: DefaultMaterial {
                                        diffuseColor: "#99aaaa"
                                        specularAmount: 0.3
                                        specularRoughness: 0.4
                                    }
                                }

                                // J6 — 末端法兰
                                Node {
                                    id: joint6
                                    position: Qt.vector3d(0, 30, 30)
                                    eulerRotation.z: j6Angle

                                    Model {
                                        source: "#Cylinder"
                                        position: Qt.vector3d(0, 12, 0)
                                        scale: Qt.vector3d(0.25, 0.25, 0.25)
                                        materials: DefaultMaterial {
                                            diffuseColor: "#e94560"
                                            specularAmount: 0.5
                                            specularRoughness: 0.2
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // 方向光
        DirectionalLight {
            eulerRotation: Qt.vector3d(-40, 30, 0)
            brightness: 1.2
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(30, -30, 0)
            brightness: 0.5
        }
    }

    // ── 视角提示 ──
    Text {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 8
        text: "拖拽旋转 | 滚轮缩放"
        color: "#556677"
        font.pixelSize: 11
    }

    // ── 关节角度属性（由外部更新） ──
    property real j1Angle: 0
    property real j2Angle: 0
    property real j3Angle: 0
    property real j4Angle: 0
    property real j5Angle: 0
    property real j6Angle: 0

    // ── 接收 Bridge 关节角度信号 ──
    Connections {
        target: bridge

        function onJointAnglesChanged(a1, a2, a3, a4, a5, a6) {
            root.j1Angle = a1
            root.j2Angle = a2
            root.j3Angle = a3
            root.j4Angle = a4
            root.j5Angle = a5
            root.j6Angle = a6
        }
    }

    // ── 公开方法：更新机器人姿态 ──
    function updateJointAngles(a1, a2, a3, a4, a5, a6) {
        j1Angle = a1
        j2Angle = a2
        j3Angle = a3
        j4Angle = a4
        j5Angle = a5
        j6Angle = a6
    }
}
