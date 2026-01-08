#!/usr/bin/env python3
"""
改进版本的GDS导出脚本，参考OpenROAD官方def2stream.py
用于将aes_secworks电路的DEF文件转换为GDS文件
"""

import pya
import os
import sys
import re

def export_aes_secworks_to_gds():
    """
    将aes_secworks电路的DEF文件转换为GDS文件
    """
    
    # 文件路径配置,请根据自己的设计文件顶层module名字和工艺做更改
    design_name = "aes"
    # 这里我以分步骤所生成的def文件为例，具体文件名查看步骤5 `route.tcl`脚本内容
    def_file = "./results/separated/routing/5_3_fillcell.def"
    tech_file = "./platforms/nangate45/FreePDK45.lyt"  # 技术文件
    tech_lef = "./platforms/nangate45/lef/NangateOpenCellLibrary.tech.lef"  #技术LEF文件路径
    macro_lef = "./platforms/nangate45/lef/NangateOpenCellLibrary.macro.mod.lef"
    std_gds = "./platforms/nangate45/gds/NangateOpenCellLibrary.gds"
    output_dir = "./results/separated/final"
    output_gds = f"{output_dir}/6_1_merged.gds"
    
    # 层映射文件（如果存在）
    layer_map = ""  # 设置为空字符串，如果有层映射文件请提供路径
    
    print("=== 改进版 DEF到GDS转换工具 ===")
    print(f"设计名称: {design_name}")
    print(f"输入DEF: {def_file}")
    print(f"技术文件: {tech_file}")
    
    # 检查必需文件
    required_files = [def_file, tech_file, tech_lef, macro_lef, std_gds]
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            return False
    
    if not os.path.exists(std_gds):
        print(f"警告: 标准单元GDS文件不存在 - {std_gds}")
    
    print("[INFO] 必需文件检查通过")
    errors = 0
    
    try:
        # 1. 加载技术文件（关键步骤！）
        print("[INFO] 加载技术文件...")
        tech_file_abs = os.path.abspath(tech_file)
        tech = pya.Technology()
        tech.load(tech_file_abs)
        layoutOptions = tech.load_layout_options

        # 尝试不同的API方式来配置LEF/DEF选项
        tech_lef_abs = os.path.abspath(tech_lef)
        macro_lef_abs = os.path.abspath(macro_lef)
        
        try:
            # 方法2: 尝试直接设置属性
            if hasattr(layoutOptions, 'lefdef_config'):
                layoutOptions.lefdef_config.lef_files = [tech_lef_abs, macro_lef_abs]
                # layout_options.lefdef_config.dbu = 0.001
                # layout_options.lefdef_config.read_all_layers = True
                print("[INFO] 使用直接属性配置LEF文件")
            
            print(f"[INFO] 成功配置LEF文件路径:")
            print(f"  技术LEF: {tech_lef_abs}")
            print(f"  标准单元LEF: {macro_lef_abs}")
            
        except Exception as e:
            print(f"[WARNING] LEF配置失败: {e}")
            print("[INFO] 将尝试仅使用DEF文件读取")
        
        # 设置层映射文件（如果存在）
        if len(layer_map) > 0 and os.path.exists(layer_map):
            layoutOptions.lefdef_config.map_file = layer_map
            print(f"[INFO] 使用层映射文件: {layer_map}")
        
        # 2. 创建主布局
        print("[INFO] 创建主布局...")
        main_layout = pya.Layout()
        
        # 显示加载DEF前的cell状态
        print("[INFO] 加载DEF前的cell状态...")
        for i in main_layout.each_cell():
            print(f"[INFO] '{i.name}'")
        
        # 3. 读取DEF文件（使用技术文件的布局选项）
        print("[INFO] 读取DEF文件...")
        main_layout.read(def_file, layoutOptions)
        
        # 4. 检查是否成功读取了目标cell
        if not main_layout.has_cell(design_name):
            print(f"[ERROR]: 在DEF中未找到顶层设计 '{design_name}'")
            print("可用的cell:")
            for cell in main_layout.each_cell():
                print(f"  - {cell.name}")
            return False
        
        print(f"[INFO] 成功找到顶层设计 '{design_name}'")
        
        # 5. 清理无用的cell（保留VIA_和填充相关的cell）
        top_cell_index = main_layout.cell(design_name).cell_index()
        print("[INFO] 清理无用cell...")
        for i in main_layout.each_cell():
            if i.cell_index() != top_cell_index:
                if not i.name.startswith("VIA_") and not i.name.endswith("_DEF_FILL"):
                    i.clear()
        
        # 6. 合并GDS文件
        print("[INFO] 合并GDS文件...")
        if os.path.exists(std_gds):
            print(f"\t{std_gds}")
            main_layout.read(std_gds)
        else:
            print("[WARNING] 标准单元GDS文件不存在，可能导致显示问题")
        
        # 7. 创建只包含顶层的新布局
        print(f"[INFO] 复制顶层cell '{design_name}'")
        top_only_layout = pya.Layout()
        top_only_layout.dbu = main_layout.dbu
        top = top_only_layout.create_cell(design_name)
        top.copy_tree(main_layout.cell(design_name))
        
        # 8. 检查缺失的cell
        print("[INFO] 检查缺失的cell...")
        missing_cell = False
        regex = None
        if "GDS_ALLOW_EMPTY" in os.environ:
            print("[INFO] 发现GDS_ALLOW_EMPTY环境变量")
            regex = os.getenv("GDS_ALLOW_EMPTY")
        
        for i in top_only_layout.each_cell():
            if i.is_empty():
                missing_cell = True
                if regex is not None and re.match(regex, i.name):
                    print(f"[WARNING] LEF Cell '{i.name}' 被忽略。匹配GDS_ALLOW_EMPTY。")
                else:
                    print(f"[ERROR] LEF Cell '{i.name}' 没有匹配的GDS/OAS cell。Cell将为空。")
                    errors += 1
        
        if not missing_cell:
            print("[INFO] 所有LEF cell都有匹配的GDS/OAS cell")
        
        # 9. 检查孤立cell
        print("[INFO] 检查孤立cell...")
        orphan_cell = False
        for i in top_only_layout.each_cell():
            if i.name != design_name and i.parent_cells() == 0:
                orphan_cell = True
                print(f"[ERROR] 发现孤立cell '{i.name}'")
                errors += 1
        
        if not orphan_cell:
            print("[INFO] 无孤立cell")
        
        # 10. 创建输出目录
        output_dir_path = os.path.dirname(output_gds)
        if not os.path.exists(output_dir_path):
            os.makedirs(output_dir_path)
        
        # 11. 写出GDS文件
        print(f"[INFO] 写出GDS文件: {output_gds}")
        top_only_layout.write(output_gds)
        
        # 12. 验证输出
        if os.path.exists(output_gds):
            file_size = os.path.getsize(output_gds)
            print(f"[SUCCESS] GDS文件生成成功!")
            print(f"文件路径: {output_gds}")
            print(f"文件大小: {file_size:,} bytes")
            
            # 显示统计信息
            top_cell = top_only_layout.top_cell()
            if top_cell:
                bbox = top_cell.bbox()
                if not bbox.empty():
                    width_um = bbox.width() * top_only_layout.dbu
                    height_um = bbox.height() * top_only_layout.dbu
                    area_um2 = width_um * height_um
                    print(f"芯片尺寸: {width_um:.3f} x {height_um:.3f} um")
                    print(f"芯片面积: {area_um2:.3f} um²")
            
            print(f"总cell数: {top_only_layout.cells()}")
            
            if errors > 0:
                print(f"[WARNING] 转换完成但有 {errors} 个错误")
                return False
            else:
                return True
        else:
            print("[ERROR] GDS文件生成失败")
            return False
            
    except Exception as e:
        print(f"[ERROR] 转换过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    
    # 检查KLayout环境
    try:
        import pya
        print("KLayout Python API 就绪")
    except ImportError:
        print("错误: 无法导入pya模块")
        print("请确保KLayout已正确安装")
        return False
    
    # 检查当前工作目录
    if not os.getcwd().endswith('flow'):
        print(f'[WARNING]: 工作路径应为 `OpenROAD-flow-scripts/flow`，当前为 {os.getcwd()}')
        return 0
    
    # 执行转换
    success = export_aes_secworks_to_gds()
    
    if success:
        print("\n" + "="*50)
        print("转换完成! 🎉")
        print("建议:")
        print("1. 用KLayout GUI打开GDS文件进行视觉检查")
        print("2. 验证所有标准单元都正确显示")
        print("3. 检查金属层和通孔连接")
        print("4. 如果仍有连接问题，检查LEF/GDS文件的层定义")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("转换失败 ❌")
        print("请检查上述错误信息并重试")
        print("="*50)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#klayout -b -r tcl/aes_secworks_def2stream.py