import re
from typing import Tuple, Optional, Dict


class AddressConverter:
    """
    Schneider PLC地址格式转Modbus标准地址格式
    """
    
    # Schneider类型到Modbus类型的映射
    TYPE_MAP = {
        'W': 'holding_register',    # %MW - 保持寄存器 (Memory Word)
        'X': 'coil',                # %MX - 线圈 (Memory Bit)
        'I': 'input_register',      # %IW - 输入寄存器 (Input Word)
        'Q': 'coil',                # %QX - 输出线圈 (Output Bit)
    }
    
    # Modbus功能码映射
    FUNCTION_CODES = {
        'holding_register': {'read': 0x03, 'write': 0x06, 'write_multiple': 0x10},
        'coil': {'read': 0x01, 'write': 0x05, 'write_multiple': 0x15},
        'input': {'read': 0x02},
        'input_register': {'read': 0x04},
    }
    
    @staticmethod
    def parse_kep_address(kep_address: str) -> Dict:
        """
        解析Schneider KEP地址格式
        
        支持的格式：
        - %MW01002          - 保持寄存器
        - %MW07400.0        - 保持寄存器的特定位
        - %MX54.7           - 线圈的特定位
        - M_%MW07520_16L    - 字符串数组
        - %MW07960_6        - 数组
        
        返回字典包含：
        - address_type: 地址类型 (holding_register, coil, input, input_register)
        - address: 基础地址
        - bit: 位位置 (如果有)
        - array_length: 数组长度 (如果有)
        - is_string: 是否为字符串
        """
        kep_address = kep_address.strip()
        
        # 处理M_%MWxxx_xxL格式（字符串）
        str_pattern = r'^M_%MW(\d+)_(\d+)L$'
        str_match = re.match(str_pattern, kep_address, re.IGNORECASE)
        if str_match:
            return {
                'address_type': 'holding_register',
                'address': int(str_match.group(1)),
                'bit': None,
                'array_length': int(str_match.group(2)),
                'is_string': True
            }
        
        # 处理M_%MWxxx_xx格式（字符串但没有L后缀）
        str_pattern2 = r'^M_%MW(\d+)_(\d+)$'
        str_match2 = re.match(str_pattern2, kep_address, re.IGNORECASE)
        if str_match2:
            return {
                'address_type': 'holding_register',
                'address': int(str_match2.group(1)),
                'bit': None,
                'array_length': int(str_match2.group(2)),
                'is_string': True
            }
        
        # 处理%MWxxx_xx格式（数组）
        mw_array_pattern = r'^%MW(\d+)_(\d+)$'
        mw_array_match = re.match(mw_array_pattern, kep_address, re.IGNORECASE)
        if mw_array_match:
            return {
                'address_type': 'holding_register',
                'address': int(mw_array_match.group(1)),
                'bit': None,
                'array_length': int(mw_array_match.group(2)),
                'is_string': False
            }
        
        # 处理%MWxxx.y格式（保持寄存器带位）
        mw_bit_pattern = r'^%MW(\d+)\.(\d+)$'
        mw_bit_match = re.match(mw_bit_pattern, kep_address, re.IGNORECASE)
        if mw_bit_match:
            return {
                'address_type': 'holding_register',
                'address': int(mw_bit_match.group(1)),
                'bit': int(mw_bit_match.group(2)),
                'array_length': 1,
                'is_string': False
            }
        
        # 处理%MWxxx格式（保持寄存器）
        mw_pattern = r'^%MW(\d+)$'
        mw_match = re.match(mw_pattern, kep_address, re.IGNORECASE)
        if mw_match:
            return {
                'address_type': 'holding_register',
                'address': int(mw_match.group(1)),
                'bit': None,
                'array_length': 1,
                'is_string': False
            }
        
        # 处理%MXxxx.y格式（线圈带位）
        mx_bit_pattern = r'^%MX(\d+)\.(\d+)$'
        mx_bit_match = re.match(mx_bit_pattern, kep_address, re.IGNORECASE)
        if mx_bit_match:
            return {
                'address_type': 'coil',
                'address': int(mx_bit_match.group(1)),
                'bit': int(mx_bit_match.group(2)),
                'array_length': 1,
                'is_string': False
            }
        
        # 处理%MXxxx格式（线圈）
        mx_pattern = r'^%MX(\d+)$'
        mx_match = re.match(mx_pattern, kep_address, re.IGNORECASE)
        if mx_match:
            return {
                'address_type': 'coil',
                'address': int(mx_match.group(1)),
                'bit': None,
                'array_length': 1,
                'is_string': False
            }
        
        # 处理%IWxxx格式（输入寄存器）
        iw_pattern = r'^%IW(\d+)$'
        iw_match = re.match(iw_pattern, kep_address, re.IGNORECASE)
        if iw_match:
            return {
                'address_type': 'input_register',
                'address': int(iw_match.group(1)),
                'bit': None,
                'array_length': 1,
                'is_string': False
            }
        
        # 处理%IXxxx.y格式（离散输入带位）
        ix_bit_pattern = r'^%IX(\d+)\.(\d+)$'
        ix_bit_match = re.match(ix_bit_pattern, kep_address, re.IGNORECASE)
        if ix_bit_match:
            return {
                'address_type': 'input',
                'address': int(ix_bit_match.group(1)),
                'bit': int(ix_bit_match.group(2)),
                'array_length': 1,
                'is_string': False
            }
        
        raise ValueError(f"无法解析地址格式: {kep_address}")
    
    @staticmethod
    def to_modbus_address(kep_address: str, zero_based: bool = True) -> Tuple[str, int, Optional[int]]:
        """
        转换为Modbus标准地址
        
        Args:
            kep_address: Schneider格式地址
            zero_based: 是否返回0索引地址（Modbus协议使用0索引）
        
        Returns:
            (address_type, modbus_address, bit_position)
            bit_position为None表示整个寄存器/线圈
        """
        parsed = AddressConverter.parse_kep_address(kep_address)
        
        # Modbus地址转换（Schneider使用1索引）
        address_offset = 1 if zero_based else 0
        modbus_address = parsed['address'] - address_offset
        
        return (parsed['address_type'], modbus_address, parsed['bit'])
    
    @staticmethod
    def get_function_code(kep_address: str, operation: str = 'read') -> Optional[int]:
        """
        获取对应的Modbus功能码
        
        Args:
            kep_address: Schneider格式地址
            operation: 'read' 或 'write' 或 'write_multiple'
        
        Returns:
            Modbus功能码
        """
        parsed = AddressConverter.parse_kep_address(kep_address)
        func_codes = AddressConverter.FUNCTION_CODES.get(parsed['address_type'])
        if func_codes:
            return func_codes.get(operation)
        return None
    
    @staticmethod
    def convert_csv_to_modbus(csv_file: str, output_file: str = None) -> list:
        """
        将CSV文件中的kep_address转换为Modbus格式
        
        Args:
            csv_file: CSV文件路径
            output_file: 输出文件路径（可选）
        
        Returns:
            转换后的记录列表
        """
        import csv
        
        converted_records = []
        
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                kep_address = row.get('PLC标签地址', '').strip()
                if not kep_address:
                    continue
                
                try:
                    parsed = AddressConverter.parse_kep_address(kep_address)
                    addr_type, modbus_addr, bit = AddressConverter.to_modbus_address(kep_address)
                    
                    converted_records.append({
                        '业务标志': row.get('业务标志', ''),
                        '读取分组': row.get('读取分组', ''),
                        '变量名': row.get('变量名', ''),
                        '变量说明': row.get('变量说明', ''),
                        '寄存器类型': row.get('寄存器类型', ''),
                        '寄存器起始地址': int(row.get('寄存器起始地址', 0)),
                        '寄存器数据长度': int(row.get('寄存器数据长度', 1)),
                        'PLC标签地址': kep_address,
                        'Modbus地址类型': addr_type,
                        'Modbus地址': modbus_addr,
                        '位位置': bit,
                        '数据类型': row.get('数据类型', ''),
                        '访问权限': row.get('访问权限', ''),
                        '启动标志': row.get('启动标志', ''),
                        '采集间隔(ms)': int(row.get('采集间隔（ms）', 1000))
                    })
                except ValueError as e:
                    print(f"转换失败 {kep_address}: {e}")
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = [
                    '业务标志', '读取分组', '变量名', '变量说明',
                    '寄存器类型', '寄存器起始地址', '寄存器数据长度',
                    'PLC标签地址', 'Modbus地址类型', 'Modbus地址', '位位置',
                    '数据类型', '访问权限', '启动标志', '采集间隔(ms)'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(converted_records)
        
        return converted_records


if __name__ == '__main__':
    # 测试转换
    test_addresses = [
        '%MW01002',
        '%MW07400.0',
        '%MX54.7',
        'M_%MW07520_16L',
        '%MW07960_6',
        '%MW07806_6'
    ]
    
    print("地址转换测试：")
    for addr in test_addresses:
        try:
            parsed = AddressConverter.parse_kep_address(addr)
            addr_type, modbus_addr, bit = AddressConverter.to_modbus_address(addr)
            func_code = AddressConverter.get_function_code(addr, 'read')
            print(f"{addr:20s} -> 类型:{addr_type:18s} 地址:{modbus_addr:6d} 位:{bit} 功能码:{hex(func_code) if func_code else 'N/A'}")
        except ValueError as e:
            print(f"{addr:20s} -> 解析失败: {e}")
    
    # 批量转换CSV
    input_csv = '/Users/guowushi/Project/ros2robot/doc/kepserver_to_modbus_complete.csv'
    output_csv = '/Users/guowushi/Project/ros2robot/doc/modbus_converted.csv'
    print(f"\n正在转换 {input_csv}...")
    records = AddressConverter.convert_csv_to_modbus(input_csv, output_csv)
    print(f"转换完成，共 {len(records)} 条记录，输出到 {output_csv}")
