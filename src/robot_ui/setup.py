from setuptools import setup
import glob

package_name = "robot_ui"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/qml", glob.glob("qml/*.qml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "robot_ui = robot_ui.main:main",
        ],
    },
)
