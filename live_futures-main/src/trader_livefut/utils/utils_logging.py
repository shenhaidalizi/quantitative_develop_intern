import logging
import os
from pathlib import Path

log_dir = Path(__file__).resolve().parent.parent.parent.parent / 'logs'
os.makedirs(log_dir, exist_ok=True)

def ignore_default_logging():
    logging.getLogger("urllib3").setLevel(logging.WARNING) # interesting.


def setRootLogger(log_filepath:str|None=None, log_filename:str|None=None, output_file=True, output_console=True, 
                  console_level=logging.INFO, file_level=logging.DEBUG, root_level=logging.DEBUG, level=None):
    """
    设置根日志记录器
    
    Args:
        log_filepath: 日志文件路径
        log_filename: 日志文件名
        output_file: 是否输出到文件
        output_console: 是否输出到控制台
        console_level: 控制台日志级别
        file_level: 文件日志级别  
        root_level: 根日志级别
        level: 统一设置所有级别（如果提供，会覆盖其他级别设置）
    """
    assert log_filepath is not None or log_filename is not None, "log_filepath and log_filename cannot be both None"
    if log_filepath is None and log_filename is not None:
        log_filepath = str(os.path.join(log_dir, log_filename))
    assert isinstance(log_filepath, str)
    
    # 🔧 修复：如果提供了level参数，使用它来设置所有级别
    if level is not None:
        console_level = level
        file_level = level
        root_level = level
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)
    
    # 🔧 修复：移除现有的处理器，避免重复添加
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if output_file:
        file_handler = logging.FileHandler(log_filepath)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(file_level)
        root_logger.addHandler(file_handler)

    if output_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(console_level)
        root_logger.addHandler(console_handler)
    
    ignore_default_logging()  # 🔧 修复：调用函数而不是检查变量
