#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电视剧剧集批量重命名工具 - 美化版
支持：Alist / OpenList / 百度网盘

作者：小爪子 🐾
"""

import os
import sys
import re
import json
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime
from contextlib import contextmanager

# 尝试导入彩色输出库，如果没有则使用 ANSI 转义码
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
    # 定义 ANSI 转义码作为后备
    class Fore:
        RED = '\033[91m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        BLUE = '\033[94m'
        MAGENTA = '\033[95m'
        CYAN = '\033[96m'
        WHITE = '\033[97m'
        RESET = '\033[39m'
    
    class Style:
        BRIGHT = '\033[1m'
        DIM = '\033[2m'
        RESET = '\033[22m'


# ─────────────────────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────────────────────

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        return super().format(record)


def setup_logger(verbose: bool = False) -> logging.Logger:
    """设置日志记录器"""
    logger = logging.getLogger('tv_rename')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    handler = logging.StreamHandler()
    formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


logger = setup_logger()


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def print_banner():
    """打印横幅"""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║{Style.BRIGHT} 🐾 电视剧批量重命名工具 {Style.RESET_ALL}{Fore.CYAN}                              ║
║                                            小爪子出品  ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{Style.BRIGHT} {title}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")


def print_success(message: str):
    """打印成功消息"""
    print(f"{Fore.GREEN}✓{Style.RESET_ALL} {message}")


def print_error(message: str):
    """打印错误消息"""
    print(f"{Fore.RED}✗{Style.RESET_ALL} {message}")


def print_warning(message: str):
    """打印警告消息"""
    print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} {message}")


def print_info(message: str):
    """打印信息消息"""
    print(f"{Fore.CYAN}ℹ{Style.RESET_ALL} {message}")


@contextmanager
def timer(description: str = "操作"):
    """计时器上下文管理器"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"{Style.DIM}{description} 耗时：{elapsed:.2f}秒{Style.RESET_ALL}")


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        raise
                    
                    logger.warning(f"{func.__name__} 失败，{current_delay:.1f}秒后重试 ({attempts}/{max_attempts}): {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
        
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────────────────────

@dataclass
class EpisodeInfo:
    """剧集信息"""
    season: int           # 季数
    episode: int          # 集数
    title: Optional[str] = None  # 可选的集标题
    original_name: str = ""      # 原始文件名
    file_size: Optional[int] = None  # 文件大小（字节）
    file_path: str = ""          # 完整路径


@dataclass
class RenameResult:
    """重命名结果"""
    success: bool
    old_name: str
    new_name: str
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# 存储后端基类
# ─────────────────────────────────────────────────────────────

class BaseStorage(ABC):
    """存储后端基类"""
    
    def __init__(self, root_path: str = "/"):
        self.root_path = root_path
        self.request_timeout = 30
        self.max_retries = 3
    
    @abstractmethod
    def list_files(self, path: str) -> List[Dict]:
        """列出目录下的文件"""
        pass
    
    @abstractmethod
    def rename_file(self, old_path: str, new_name: str) -> bool:
        """重命名文件"""
        pass
    
    @abstractmethod
    def get_root_path(self) -> str:
        """获取根路径"""
        pass
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            self.list_files(self.root_path)
            return True
        except Exception as e:
            logger.error(f"连接测试失败：{e}")
            return False
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# ─────────────────────────────────────────────────────────────
# Alist / OpenList 存储后端
# ─────────────────────────────────────────────────────────────

class AlistStorage(BaseStorage):
    """Alist / OpenList 存储后端"""
    
    def __init__(self, base_url: str, token: str, root_path: str = "/"):
        super().__init__(root_path)
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        
        # 验证配置
        if not base_url:
            raise ValueError("Alist base_url 不能为空")
        if not token:
            raise ValueError("Alist token 不能为空")
    
    @retry(max_attempts=3, delay=1.0)
    def list_files(self, path: str) -> List[Dict]:
        """列出目录下的文件"""
        import requests
        
        url = f"{self.base_url}/api/fs/list"
        payload = {
            "path": path,
            "password": "",
            "page": 1,
            "per_page": 0,
            "refresh": False
        }
        
        try:
            logger.debug(f"请求 Alist: {url}")
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                content = data.get("data", {}).get("content", [])
                files = [f for f in content if f.get("is_dir") == False]
                logger.debug(f"找到 {len(files)} 个文件")
                return files
            else:
                error_msg = data.get('message', '未知错误')
                logger.error(f"Alist 列表失败 [{data.get('code')}]: {error_msg}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error("Alist 请求超时")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"无法连接到 Alist 服务：{e}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Alist HTTP 错误：{e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Alist 响应解析失败：{e}")
            raise
        except Exception as e:
            logger.error(f"Alist 请求错误：{e}")
            raise
    
    @retry(max_attempts=3, delay=1.0)
    def rename_file(self, old_path: str, new_name: str) -> bool:
        """重命名文件"""
        import requests
        
        url = f"{self.base_url}/api/fs/rename"
        
        old_path = old_path.replace("\\", "/")
        parent_dir = "/".join(old_path.split("/")[:-1])
        
        payload = {
            "path": old_path,
            "name": new_name
        }
        
        try:
            logger.debug(f"重命名：{old_path} → {new_name}")
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                logger.info(f"重命名成功：{Path(old_path).name} → {new_name}")
                return True
            else:
                error_msg = data.get('message', '未知错误')
                logger.error(f"重命名失败：{error_msg}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("重命名请求超时")
            raise
        except Exception as e:
            logger.error(f"重命名错误：{e}")
            raise
    
    def get_root_path(self) -> str:
        return self.root_path


# ─────────────────────────────────────────────────────────────
# 百度网盘存储后端
# ─────────────────────────────────────────────────────────────

class BaiduStorage(BaseStorage):
    """百度网盘存储后端"""
    
    def __init__(self, access_token: str, root_path: str = "/"):
        super().__init__(root_path)
        self.access_token = access_token
        self.base_url = "https://pan.baidu.com/rest/2.0/xpan"
        
        # 验证配置
        if not access_token:
            raise ValueError("百度网盘 access_token 不能为空")
    
    @retry(max_attempts=3, delay=1.5)
    def list_files(self, path: str) -> List[Dict]:
        """列出目录下的文件"""
        import requests
        
        url = f"{self.base_url}/file"
        params = {
            "method": "list",
            "dir": path,
            "access_token": self.access_token,
            "order": "name",
            "limit": "1000"
        }
        
        try:
            logger.debug(f"请求百度网盘：{path}")
            resp = requests.get(url, params=params, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if "list" in data:
                files = [f for f in data["list"] if f.get("isdir") == 0]
                logger.debug(f"找到 {len(files)} 个文件")
                return files
            else:
                error_msg = data.get('errmsg', '未知错误')
                logger.error(f"百度网盘列表失败：{error_msg}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error("百度网盘请求超时")
            raise
        except Exception as e:
            logger.error(f"百度网盘请求错误：{e}")
            raise
    
    @retry(max_attempts=3, delay=1.5)
    def rename_file(self, old_path: str, new_name: str) -> bool:
        """重命名文件（使用 move 接口）"""
        import requests
        
        old_path = old_path.replace("\\", "/")
        parent_dir = "/".join(old_path.split("/")[:-1])
        
        url = f"{self.base_url}/filemanager"
        params = {
            "method": "move",
            "access_token": self.access_token,
            "async": "0"
        }
        
        payload = {
            "filelist": json.dumps([old_path]),
            "to": parent_dir,
            "newname": json.dumps([new_name])
        }
        
        try:
            logger.debug(f"重命名：{old_path} → {parent_dir}/{new_name}")
            resp = requests.post(url, params=params, data=payload, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("errno") == 0:
                logger.info(f"重命名成功：{Path(old_path).name} → {new_name}")
                return True
            else:
                error_msg = data.get('errmsg', '未知错误')
                logger.error(f"重命名失败：{error_msg}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("重命名请求超时")
            raise
        except Exception as e:
            logger.error(f"重命名错误：{e}")
            raise
    
    def get_root_path(self) -> str:
        return self.root_path


# ─────────────────────────────────────────────────────────────
# 电视剧重命名器
# ─────────────────────────────────────────────────────────────

class TVRenamer:
    """电视剧重命名器"""
    
    # 常见季集匹配模式（按优先级排序）
    PATTERNS = [
        # S01E01, S1E1 (最高优先级)
        (r'[Ss](\d+)[Ee](\d+)', 2),
        # Season 1 Episode 1
        (r'[Ss]eason\s*(\d+)[\s_.]*[Ee]pisode\s*(\d+)', 2),
        # 1x01, 01x01
        (r'(\d{1,2})x(\d{2})', 2),
        # 第 01 集，第 1 集
        (r'第\s*(\d+)\s*[集話]', 1),
        # EP01, E01, Ep01
        (r'[Ee][Pp]?(\d{2,})', 1),
        # 01 集，1 集
        (r'(\d{2,})\s*[集話]', 1),
    ]
    
    # 视频文件扩展名
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.rmvb'}
    
    def __init__(self, storage: BaseStorage, verbose: bool = False):
        self.storage = storage
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def parse_episode(self, filename: str) -> Optional[EpisodeInfo]:
        """从文件名解析剧集信息"""
        name_without_ext = Path(filename).stem
        
        season = 1  # 默认第 1 季
        episode = None
        
        # 尝试各种模式
        for pattern, group_count in self.PATTERNS:
            match = re.search(pattern, name_without_ext, re.IGNORECASE)
            if match:
                groups = match.groups()
                if group_count == 2 and len(groups) >= 2:
                    season = int(groups[0])
                    episode = int(groups[1])
                elif len(groups) >= 1:
                    episode = int(groups[0])
                
                if episode:
                    logger.debug(f"解析成功 [{filename}]: S{season:02d}E{episode:02d}")
                    return EpisodeInfo(
                        season=season,
                        episode=episode,
                        original_name=filename,
                        file_size=0,
                        file_path=""
                    )
        
        logger.debug(f"无法解析：{filename}")
        return None
    
    def generate_new_name(self, info: EpisodeInfo, template: str) -> Optional[str]:
        """生成新文件名"""
        ext = Path(info.original_name).suffix.lower()
        
        # 确保是视频文件
        if ext not in self.VIDEO_EXTS:
            return None
        
        try:
            new_name_base = template.format(season=info.season, episode=info.episode)
        except KeyError as e:
            logger.error(f"模板错误，未知字段：{e}")
            return None
        except Exception as e:
            logger.error(f"模板格式化失败：{e}")
            return None
        
        # 如果有标题，添加到文件名
        if info.title:
            # 清理标题中的非法字符
            safe_title = re.sub(r'[<>:"/\\|?*]', '', info.title)
            new_name = f"{new_name_base}.{safe_title}{ext}"
        else:
            new_name = f"{new_name_base}{ext}"
        
        return new_name
    
    def process_directory(self, path: str, template: str, dry_run: bool = True) -> Tuple[List[EpisodeInfo], List[Tuple[str, str]]]:
        """处理目录下的所有剧集文件"""
        print_section(f"扫描目录：{path}")
        
        try:
            files = self.storage.list_files(path)
        except Exception as e:
            print_error(f"无法列出目录：{e}")
            return [], []
        
        if not files:
            print_warning("未找到文件或无法访问目录")
            return [], []
        
        print_info(f"找到 {len(files)} 个文件")
        
        episodes = []
        changes = []
        skipped = []
        unparseable = []
        
        for file_info in files:
            filename = file_info.get("name", "")
            file_size = file_info.get("size", 0)
            
            # 跳过非视频文件
            ext = Path(filename).suffix.lower()
            if ext not in self.VIDEO_EXTS:
                skipped.append(filename)
                continue
            
            # 解析剧集信息
            episode_info = self.parse_episode(filename)
            if not episode_info:
                unparseable.append(filename)
                continue
            
            episode_info.file_size = file_size
            episode_info.file_path = f"{path}/{filename}".replace("//", "/")
            episodes.append(episode_info)
            
            # 生成新名称
            new_name = self.generate_new_name(episode_info, template)
            if not new_name:
                continue
            
            # 如果名称不同，记录下来
            if new_name != filename:
                changes.append((filename, new_name))
            else:
                skipped.append(filename)
        
        # 打印统计信息
        print(f"\n{Fore.WHITE}{Style.BRIGHT}统计信息:{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}可识别剧集：{len(episodes)}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}需要重命名：{len(changes)}{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}已符合/跳过：{len(skipped)}{Style.RESET_ALL}")
        if unparseable:
            print(f"  {Fore.RED}无法识别：{len(unparseable)}{Style.RESET_ALL}")
        
        # 打印预览表格
        if changes:
            print(f"\n{Fore.WHITE}{Style.BRIGHT}重命名预览:{Style.RESET_ALL}")
            print(f"{Style.DIM}{'原始文件名':<50} → {'新文件名':<30}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 85}{Style.RESET_ALL}")
            
            for old_name, new_name in changes[:20]:  # 最多显示 20 个
                old_display = old_name[:47] + "..." if len(old_name) > 50 else old_name
                print(f"{old_display:<50} {Fore.YELLOW}→{Style.RESET_ALL} {Fore.GREEN}{new_name}{Style.RESET_ALL}")
            
            if len(changes) > 20:
                print(f"{Style.DIM}  ... 还有 {len(changes) - 20} 个文件{Style.RESET_ALL}")
        
        # 显示无法识别的文件
        if unparseable and self.verbose:
            print(f"\n{Fore.YELLOW}无法识别的文件:{Style.RESET_ALL}")
            for name in unparseable[:10]:
                print(f"  - {name}")
            if len(unparseable) > 10:
                print(f"  ... 还有 {len(unparseable) - 10} 个")
        
        return episodes, changes
    
    def apply_changes(self, path: str, changes: List[Tuple[str, str]]) -> List[RenameResult]:
        """应用重命名更改"""
        print_section("执行重命名")
        
        results = []
        total = len(changes)
        
        for i, (old_name, new_name) in enumerate(changes, 1):
            old_path = f"{path}/{old_name}".replace("//", "/")
            
            # 显示进度
            progress = f"[{i}/{total}]"
            print(f"{Fore.CYAN}{progress}{Style.RESET_ALL} {old_name} ", end="")
            
            try:
                success = self.storage.rename_file(old_path, new_name)
                if success:
                    results.append(RenameResult(success=True, old_name=old_name, new_name=new_name))
                    print(f"{Fore.GREEN}✓{Style.RESET_ALL}")
                else:
                    results.append(RenameResult(success=False, old_name=old_name, new_name=new_name, error="API 返回失败"))
                    print(f"{Fore.RED}✗{Style.RESET_ALL}")
            except Exception as e:
                results.append(RenameResult(success=False, old_name=old_name, new_name=new_name, error=str(e)))
                print(f"{Fore.RED}✗ {e}{Style.RESET_ALL}")
            
            # 添加小延迟避免请求过快
            time.sleep(0.2)
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = total - success_count
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}重命名结果:{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}成功：{success_count}{Style.RESET_ALL}")
        if fail_count > 0:
            print(f"  {Fore.RED}失败：{fail_count}{Style.RESET_ALL}")
        
        return results


# ─────────────────────────────────────────────────────────────
# 配置管理
# ─────────────────────────────────────────────────────────────

def load_config(config_path: str = "config.json") -> Dict:
    """加载配置文件"""
    default_config = {
        "storage_type": "alist",
        "alist": {
            "base_url": "http://localhost:5244",
            "token": "",
            "root_path": "/电视剧"
        },
        "baidu": {
            "access_token": "",
            "root_path": "/电视剧"
        },
        "name_template": "S{season:02d}E{episode:02d}",
        "dry_run": True,
        "verbose": False
    }
    
    if not os.path.exists(config_path):
        print_warning(f"配置文件 {config_path} 不存在，使用默认配置")
        print_info("建议复制 config.example.json 并修改")
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 合并默认配置
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if k not in config[key]:
                            config[key][k] = v
        print_success(f"配置已加载：{config_path}")
        return config
    except json.JSONDecodeError as e:
        print_error(f"配置文件解析失败：{e}")
        return default_config
    except Exception as e:
        print_error(f"读取配置文件失败：{e}")
        return default_config


def create_storage(config: Dict) -> BaseStorage:
    """创建存储实例"""
    storage_type = config.get("storage_type", "alist").lower()
    
    if storage_type == "alist":
        alist_config = config.get("alist", {})
        try:
            storage = AlistStorage(
                base_url=alist_config.get("base_url", "http://localhost:5244"),
                token=alist_config.get("token", ""),
                root_path=alist_config.get("root_path", "/")
            )
            print_success("已连接 Alist / OpenList")
            return storage
        except ValueError as e:
            print_error(f"Alist 配置错误：{e}")
            raise
    
    elif storage_type == "baidu":
        baidu_config = config.get("baidu", {})
        try:
            storage = BaiduStorage(
                access_token=baidu_config.get("access_token", ""),
                root_path=baidu_config.get("root_path", "/")
            )
            print_success("已连接百度网盘")
            return storage
        except ValueError as e:
            print_error(f"百度网盘配置错误：{e}")
            raise
    
    else:
        print_error(f"不支持的存储类型：{storage_type}")
        raise ValueError(f"不支持的存储类型：{storage_type}")


# ─────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────

def main():
    """主函数"""
    print_banner()
    
    # 加载配置
    config = load_config()
    
    # 设置日志级别
    if config.get("verbose", False):
        logger.setLevel(logging.DEBUG)
    
    # 创建存储实例
    try:
        storage = create_storage(config)
    except Exception as e:
        print_error(f"初始化存储失败：{e}")
        print_info("请检查配置文件中的 token 和路径")
        sys.exit(1)
    
    # 测试连接
    print_info("测试连接...")
    if not storage.test_connection():
        print_error("无法连接到存储服务")
        sys.exit(1)
    print_success("连接正常")
    
    # 创建重命名器
    renamer = TVRenamer(storage, verbose=config.get("verbose", False))
    
    # 获取路径
    storage_type = config.get("storage_type", "alist")
    if storage_type == "alist":
        path = config.get("alist", {}).get("root_path", "/")
    else:
        path = config.get("baidu", {}).get("root_path", "/")
    
    # 获取模板
    template = config.get("name_template", "S{season:02d}E{episode:02d}")
    print_info(f"命名模板：{template}")
    
    # 处理目录
    with timer("扫描"):
        episodes, changes = renamer.process_directory(path, template, dry_run=config.get("dry_run", True))
    
    if not changes:
        print_info("无需重命名")
        sys.exit(0)
    
    # 如果是预览模式，询问是否执行
    if config.get("dry_run", True):
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}⚠️  当前为预览模式，未实际重命名{Style.RESET_ALL}")
        
        try:
            response = input(f"\n{Fore.CYAN}是否执行重命名？[y/N]: {Style.RESET_ALL}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Fore.YELLOW}已取消{Style.RESET_ALL}")
            sys.exit(0)
        
        if response == 'y':
            print(f"\n{Fore.GREEN}{Style.BRIGHT}开始执行重命名...{Style.RESET_ALL}\n")
            with timer("重命名"):
                results = renamer.apply_changes(path, changes)
            
            # 显示失败详情
            failed = [r for r in results if not r.success]
            if failed:
                print(f"\n{Fore.RED}失败详情:{Style.RESET_ALL}")
                for r in failed:
                    print(f"  {r.old_name}: {r.error}")
        else:
            print(f"\n{Fore.CYAN}已取消{Style.RESET_ALL}")
    else:
        # 直接执行
        print(f"\n{Fore.GREEN}{Style.BRIGHT}开始执行重命名...{Style.RESET_ALL}\n")
        with timer("重命名"):
            results = renamer.apply_changes(path, changes)
        
        # 显示失败详情
        failed = [r for r in results if not r.success]
        if failed:
            print(f"\n{Fore.RED}失败详情:{Style.RESET_ALL}")
            for r in failed:
                print(f"  {r.old_name}: {r.error}")
    
    print(f"\n{Fore.GREEN}✨ 完成！{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}用户中断{Style.RESET_ALL}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Fore.RED}{Style.BRIGHT}发生错误：{e}{Style.RESET_ALL}")
        logger.exception("详细错误信息:")
        sys.exit(1)
