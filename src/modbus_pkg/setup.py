from setuptools import setup

package_name = "modbus_pkg"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", ["config/modbus_config.toml"]),
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("lib/" + package_name, ["scripts/plc_worker"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    scripts=["scripts/plc_worker"],
    entry_points={
        "console_scripts": [
            "plc_worker = modbus_pkg.plc_worker:main",
        ],
    },
)
