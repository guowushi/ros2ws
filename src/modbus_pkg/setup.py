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
    ],
    install_requires=["setuptools"],
    zip_safe=True,
)
