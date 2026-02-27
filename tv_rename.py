#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电视剧剧集批量重命名工具 - 交互式增强版
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

# 尝试导入彩色输出库
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    HAS_COLORAMA = True
except ImportError:
    HAS_COLORAMA = False
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

if not hasattr(Style, 'DIM'):
    Style.DIM = '\033[2m'


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
    logger = logging.getLogger('tv_rename')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler()
    formatter = ColoredFormatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = setup_logger()


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def print_banner():
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║{Style.BRIGHT} 🐾 电视剧批量重命名工具 {Style.RESET_ALL}{Fore.CYAN}                              ║
║                                            小爪子出品  ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)


def print_section(title: str):
    print(f"\n{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{Style.BRIGHT} {title}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")


def print_success(message: str):
    print(f"{Fore.GREEN}✓{Style.RESET_ALL} {message}")


def print_error(message: str):
    print(f"{Fore.RED}✗{Style.RESET_ALL} {message}")


def print_warning(message: str):
    print(f"{Fore.YELLOW}⚠{Style.RESET_ALL} {message}")


def print_info(message: str):
    print(f"{Fore.CYAN}ℹ{Style.RESET_ALL} {message}")


@contextmanager
def timer(description: str = "操作"):
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"{Style.DIM}{description} 耗时：{elapsed:.2f}秒{Style.RESET_ALL}")


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
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
    season: int
    episode: int
    title: Optional[str] = None
    original_name: str = ""
    file_size: Optional[int] = None
    file_path: str = ""


@dataclass
class RenameResult:
    success: bool
    old_name: str
    new_name: str
    error: Optional[str] = None


@dataclass
class FolderItem:
    """文件夹项"""
    name: str
    path: str
    is_dir: bool
    file_count: int = 0  # 视频文件数量
    size: Optional[int] = None


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
        pass
    
    @abstractmethod
    def list_folders(self, path: str) -> List[Dict]:
        """列出目录内容（包含文件夹和文件）"""
        pass
    
    @abstractmethod
    def rename_file(self, old_path: str, new_name: str) -> bool:
        pass
    
    @abstractmethod
    def get_root_path(self) -> str:
        pass
    
    def test_connection(self) -> bool:
        try:
            self.list_folders(self.root_path)
            return True
        except Exception as e:
            logger.error(f"连接测试失败：{e}")
            return False
    
    def format_size(self, size_bytes: int) -> str:
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
        
        if not base_url:
            raise ValueError("Alist base_url 不能为空")
        if not token:
            raise ValueError("Alist token 不能为空")
    
    @retry(max_attempts=3, delay=1.0)
    def list_folders(self, path: str) -> List[Dict]:
        """列出目录内容"""
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
                logger.debug(f"找到 {len(content)} 个项目")
                return content
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
        except Exception as e:
            logger.error(f"Alist 请求错误：{e}")
            raise
    
    def list_files(self, path: str) -> List[Dict]:
        """只返回文件"""
        content = self.list_folders(path)
        return [f for f in content if f.get("is_dir") == False]
    
    @retry(max_attempts=3, delay=1.0)
    def rename_file(self, old_path: str, new_name: str) -> bool:
        import requests
        url = f"{self.base_url}/api/fs/rename"
        old_path = old_path.replace("\\", "/")
        payload = {"path": old_path, "name": new_name}
        
        try:
            logger.debug(f"重命名：{old_path} → {new_name}")
            resp = requests.post(url, json=payload, headers=self.headers, timeout=self.request_timeout)
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") == 200:
                logger.info(f"重命名成功：{Path(old_path).name} → {new_name}")
                return True
            else:
                logger.error(f"重命名失败：{data.get('message', '未知错误')}")
                return False
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
        
        if not access_token:
            raise ValueError("百度网盘 access_token 不能为空")
    
    @retry(max_attempts=3, delay=1.5)
    def list_folders(self, path: str) -> List[Dict]:
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
                # 统一格式：isdir=1 是文件夹，isdir=0 是文件
                files = []
                for f in data["list"]:
                    f["is_dir"] = (f.get("isdir") == 1)
                    files.append(f)
                logger.debug(f"找到 {len(files)} 个项目")
                return files
            else:
                logger.error(f"百度网盘列表失败：{data.get('errmsg', '未知错误')}")
                return []
        except Exception as e:
            logger.error(f"百度网盘请求错误：{e}")
            raise
    
    def list_files(self, path: str) -> List[Dict]:
        content = self.list_folders(path)
        return [f for f in content if f.get("is_dir") == False]
    
    @retry(max_attempts=3, delay=1.5)
    def rename_file(self, old_path: str, new_name: str) -> bool:
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
                logger.error(f"重命名失败：{data.get('errmsg', '未知错误')}")
                return False
        except Exception as e:
            logger.error(f"重命名错误：{e}")
            raise
    
    def get_root_path(self) -> str:
        return self.root_path


# ─────────────────────────────────────────────────────────────
# 交互式文件夹浏览器
# ─────────────────────────────────────────────────────────────

class FolderBrowser:
    """交互式文件夹浏览器"""
    
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.rmvb'}
    
    def __init__(self, storage: BaseStorage):
        self.storage = storage
        self.current_path = storage.get_root_path()
        self.history = []  # 路径历史
    
    def count_video_files(self, items: List[Dict]) -> int:
        """统计视频文件数量"""
        count = 0
        for item in items:
            if not item.get("is_dir"):
                ext = Path(item.get("name", "")).suffix.lower()
                if ext in self.VIDEO_EXTS:
                    count += 1
        return count
    
    def display_folder(self, path: str) -> List[FolderItem]:
        """显示文件夹内容"""
        try:
            items = self.storage.list_folders(path)
        except Exception as e:
            print_error(f"无法访问目录：{e}")
            return []
        
        if not items:
            print_warning("此目录为空")
            return []
        
        # 排序：文件夹在前，文件在后
        folders = [i for i in items if i.get("is_dir")]
        files = [i for i in items if not i.get("is_dir")]
        folders.sort(key=lambda x: x.get("name", "").lower())
        files.sort(key=lambda x: x.get("name", "").lower())
        
        folder_items = []
        
        # 显示父目录选项
        if path != "/":
            print(f"{Fore.CYAN}  [..]{Style.RESET_ALL} 返回上级目录")
        
        # 显示文件夹
        for i, folder in enumerate(folders, 1):
            name = folder.get("name", "未知")
            folder_path = f"{path}/{name}".replace("//", "/")
            print(f"{Fore.BLUE}  [{i}]{Style.RESET_ALL} 📁 {name}/")
            folder_items.append(FolderItem(name=name, path=folder_path, is_dir=True))
        
        # 显示文件（带视频文件统计）
        if files:
            video_count = self.count_video_files(files)
            print(f"\n{Style.DIM}  文件 ({len(files)}个，视频：{video_count}个):{Style.RESET_ALL}")
            
            for i, file in enumerate(files, len(folders) + 1):
                name = file.get("name", "未知")
                ext = Path(name).suffix.lower()
                icon = "🎬" if ext in self.VIDEO_EXTS else "📄"
                size = file.get("size", 0)
                size_str = self.storage.format_size(size) if size else "?"
                print(f"  [{i}] {icon} {name} ({size_str})")
                folder_items.append(FolderItem(name=name, path=f"{path}/{name}".replace("//", "/"), is_dir=False, size=size))
        
        return folder_items
    
    def select_folder_interactive(self) -> Optional[str]:
        """交互式选择文件夹"""
        print_section("浏览文件夹")
        print_info("使用数字选择文件夹，输入 'q' 返回上级，'c' 确认选择当前目录")
        
        while True:
            print(f"\n{Fore.CYAN}📁 当前路径：{Style.BRIGHT}{self.current_path}{Style.RESET_ALL}")
            items = self.display_folder(self.current_path)
            
            if not items:
                print_warning("空目录，按 'q' 返回上级")
            
            # 获取用户输入
            try:
                choice = input(f"\n{Fore.GREEN}选择 [1-{len(items)}]/q/c: {Style.RESET_ALL}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}已取消{Style.RESET_ALL}")
                return None
            
            if choice == 'c':
                # 确认选择当前目录
                confirm = input(f"确认选择 {self.current_path} ? [y/N]: ").strip().lower()
                if confirm == 'y':
                    return self.current_path
            
            elif choice == 'q':
                # 返回上级
                if self.current_path == "/":
                    print_warning("已经在根目录")
                else:
                    self.current_path = "/".join(self.current_path.split("/")[:-1]) or "/"
            
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    item = items[idx]
                    if item.is_dir:
                        self.current_path = item.path
                    else:
                        print_warning(f"{item.name} 是文件，不是文件夹")
                else:
                    print_error(f"请输入 1-{len(items)} 之间的数字")
            else:
                print_error("无效输入，请输入数字、q 或 c")


# ─────────────────────────────────────────────────────────────
# 电视剧重命名器
# ─────────────────────────────────────────────────────────────

class TVRenamer:
    """电视剧重命名器"""
    
    PATTERNS = [
        (r'[Ss](\d+)[Ee](\d+)', 2),
        (r'[Ss]eason\s*(\d+)[\s_.]*[Ee]pisode\s*(\d+)', 2),
        (r'(\d{1,2})x(\d{2})', 2),
        (r'第\s*(\d+)\s*[集話]', 1),
        (r'[Ee][Pp]?(\d{2,})', 1),
        (r'(\d{2,})\s*[集話]', 1),
    ]
    
    VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.rmvb'}
    
    def __init__(self, storage: BaseStorage, verbose: bool = False):
        self.storage = storage
        self.verbose = verbose
        if verbose:
            logger.setLevel(logging.DEBUG)
    
    def parse_episode(self, filename: str) -> Optional[EpisodeInfo]:
        name_without_ext = Path(filename).stem
        season = 1
        episode = None
        
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
                    return EpisodeInfo(season=season, episode=episode, original_name=filename)
        
        logger.debug(f"无法解析：{filename}")
        return None
    
    def generate_new_name(self, info: EpisodeInfo, template: str) -> Optional[str]:
        ext = Path(info.original_name).suffix.lower()
        if ext not in self.VIDEO_EXTS:
            return None
        
        try:
            new_name_base = template.format(season=info.season, episode=info.episode)
        except Exception as e:
            logger.error(f"模板格式化失败：{e}")
            return None
        
        return f"{new_name_base}{ext}"
    
    def process_directory(self, path: str, template: str, dry_run: bool = True) -> Tuple[List[EpisodeInfo], List[Tuple[str, str]]]:
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
            ext = Path(filename).suffix.lower()
            
            if ext not in self.VIDEO_EXTS:
                skipped.append(filename)
                continue
            
            episode_info = self.parse_episode(filename)
            if not episode_info:
                unparseable.append(filename)
                continue
            
            episode_info.file_path = f"{path}/{filename}".replace("//", "/")
            episodes.append(episode_info)
            
            new_name = self.generate_new_name(episode_info, template)
            if not new_name:
                continue
            
            if new_name != filename:
                changes.append((filename, new_name))
            else:
                skipped.append(filename)
        
        # 统计信息
        print(f"\n{Fore.WHITE}{Style.BRIGHT}统计信息:{Style.RESET_ALL}")
        print(f"  {Fore.GREEN}可识别剧集：{len(episodes)}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}需要重命名：{len(changes)}{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}已符合/跳过：{len(skipped)}{Style.RESET_ALL}")
        if unparseable:
            print(f"  {Fore.RED}无法识别：{len(unparseable)}{Style.RESET_ALL}")
        
        # 预览表格
        if changes:
            print(f"\n{Fore.WHITE}{Style.BRIGHT}重命名预览:{Style.RESET_ALL}")
            print(f"{Style.DIM}{'原始文件名':<50} → {'新文件名':<30}{Style.RESET_ALL}")
            print(f"{Style.DIM}{'─' * 85}{Style.RESET_ALL}")
            
            for old_name, new_name in changes[:20]:
                old_display = old_name[:47] + "..." if len(old_name) > 50 else old_name
                print(f"{old_display:<50} {Fore.YELLOW}→{Style.RESET_ALL} {Fore.GREEN}{new_name}{Style.RESET_ALL}")
            
            if len(changes) > 20:
                print(f"{Style.DIM}  ... 还有 {len(changes) - 20} 个文件{Style.RESET_ALL}")
        
        if unparseable and self.verbose:
            print(f"\n{Fore.YELLOW}无法识别的文件:{Style.RESET_ALL}")
            for name in unparseable[:10]:
                print(f"  - {name}")
            if len(unparseable) > 10:
                print(f"  ... 还有 {len(unparseable) - 10} 个")
        
        return episodes, changes
    
    def apply_changes(self, path: str, changes: List[Tuple[str, str]]) -> List[RenameResult]:
        print_section("执行重命名")
        
        results = []
        total = len(changes)
        
        for i, (old_name, new_name) in enumerate(changes, 1):
            old_path = f"{path}/{old_name}".replace("//", "/")
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
            
            time.sleep(0.2)
        
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
    default_config = {
        "storage_type": "alist",
        "alist": {
            "base_url": "http://localhost:5244",
            "token": "",
            "root_path": "/"
        },
        "baidu": {
            "access_token": "",
            "root_path": "/"
        },
        "name_template": "S{season:02d}E{episode:02d}",
        "dry_run": True,
        "verbose": False,
        "interactive": True
    }
    
    if not os.path.exists(config_path):
        print_warning(f"配置文件 {config_path} 不存在，将使用交互模式")
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
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
# 交互式配置向导
# ─────────────────────────────────────────────────────────────

def interactive_setup() -> Dict:
    """交互式配置向导"""
    print_section("配置向导")
    
    # 选择存储类型
    print("\n选择存储类型:")
    print(f"  {Fore.BLUE}[1]{Style.RESET_ALL} Alist / OpenList")
    print(f"  {Fore.BLUE}[2]{Style.RESET_ALL} 百度网盘")
    
    while True:
        choice = input(f"\n{Fore.GREEN}选择 [1/2]: {Style.RESET_ALL}").strip()
        if choice == '1':
            storage_type = 'alist'
            break
        elif choice == '2':
            storage_type = 'baidu'
            break
        print_error("请输入 1 或 2")
    
    # 获取配置
    if storage_type == 'alist':
        print("\n请输入 Alist 配置:")
        base_url = input(f"  服务地址 (默认：http://localhost:5244): ").strip() or "http://localhost:5244"
        token = input(f"  Token: ").strip()
        
        if not token:
            print_error("Token 不能为空")
            return None
        
        config = {
            "storage_type": "alist",
            "alist": {
                "base_url": base_url,
                "token": token,
                "root_path": "/"
            }
        }
    else:
        print("\n请输入百度网盘配置:")
        access_token = input(f"  Access Token: ").strip()
        
        if not access_token:
            print_error("Access Token 不能为空")
            return None
        
        config = {
            "storage_type": "baidu",
            "baidu": {
                "access_token": access_token,
                "root_path": "/"
            }
        }
    
    # 命名模板
    print(f"\n{Fore.CYAN}命名模板:{Style.RESET_ALL}")
    print(f"  S{{season:02d}}E{{episode:02d}} → S01E01.mp4")
    print(f"  Season {{season}} Episode {{episode}} → Season 1 Episode 1.mp4")
    template = input(f"\n模板 (默认：S{{season:02d}}E{{episode:02d}}): ").strip() or "S{season:02d}E{episode:02d}"
    config["name_template"] = template
    
    return config


# ─────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────

def main():
    print_banner()
    
    # 加载配置
    config = load_config()
    
    if config.get("verbose", False):
        logger.setLevel(logging.DEBUG)
    
    # 检查是否有必要配置
    storage_type = config.get("storage_type", "alist")
    need_setup = False
    
    if storage_type == "alist":
        if not config.get("alist", {}).get("token"):
            need_setup = True
    else:
        if not config.get("baidu", {}).get("access_token"):
            need_setup = True
    
    # 如果需要配置，运行向导
    if need_setup:
        print_warning("缺少必要配置，启动配置向导...")
        setup_config = interactive_setup()
        if not setup_config:
            print_error("配置失败")
            sys.exit(1)
        
        # 合并配置
        config.update(setup_config)
    
    # 创建存储实例
    try:
        storage = create_storage(config)
    except Exception as e:
        print_error(f"初始化存储失败：{e}")
        sys.exit(1)
    
    # 测试连接
    print_info("测试连接...")
    if not storage.test_connection():
        print_error("无法连接到存储服务")
        sys.exit(1)
    print_success("连接正常")
    
    # 交互式选择文件夹
    if config.get("interactive", True):
        browser = FolderBrowser(storage)
        selected_path = browser.select_folder_interactive()
        if not selected_path:
            sys.exit(0)
    else:
        # 使用配置中的路径
        if storage_type == "alist":
            selected_path = config.get("alist", {}).get("root_path", "/")
        else:
            selected_path = config.get("baidu", {}).get("root_path", "/")
    
    # 获取模板
    template = config.get("name_template", "S{season:02d}E{episode:02d}")
    print_info(f"命名模板：{template}")
    
    # 创建重命名器
    renamer = TVRenamer(storage, verbose=config.get("verbose", False))
    
    # 处理目录
    with timer("扫描"):
        episodes, changes = renamer.process_directory(selected_path, template, dry_run=config.get("dry_run", True))
    
    if not changes:
        print_info("无需重命名")
        sys.exit(0)
    
    # 预览模式询问
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
                results = renamer.apply_changes(selected_path, changes)
            
            failed = [r for r in results if not r.success]
            if failed:
                print(f"\n{Fore.RED}失败详情:{Style.RESET_ALL}")
                for r in failed:
                    print(f"  {r.old_name}: {r.error}")
        else:
            print(f"\n{Fore.CYAN}已取消{Style.RESET_ALL}")
    else:
        print(f"\n{Fore.GREEN}{Style.BRIGHT}开始执行重命名...{Style.RESET_ALL}\n")
        with timer("重命名"):
            results = renamer.apply_changes(selected_path, changes)
        
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
