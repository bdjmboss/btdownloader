# -*- coding: utf-8 -*-
"""BT 下载器（Kivy 安卓版）- 全功能多任务版

依赖：kivy, libtorrent（libtorrent 可选，缺失时自动进入 mock 模式）
特性：多任务管理、选择性下载文件、自动更新 Tracker、完成通知+打开目录、
删除可选删文件、上下行限速、配置持久化、状态颜色、顺序下载(边下边播)、
全局统计、深色模式。
"""

import kivy
kivy.require('2.1.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
import threading
import time
import os
import json
import random
import urllib.request
import urllib.parse

try:
    from kivy.core.window import Window
    WINDOW_AVAILABLE = True
except Exception:
    WINDOW_AVAILABLE = False

try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    LIBTORRENT_AVAILABLE = False
    lt = None

from kivy.utils import platform
IS_ANDROID = platform == 'android'


def _setup_cjk_font():
    """注册系统中文字体，解决安卓上中文显示为方块的问题"""
    candidates = [
        '/system/fonts/NotoSansCJK-Regular.ttc',
        '/system/fonts/NotoSansSC-Regular.otf',
        '/system/fonts/NotoSansCJKsc-Regular.otf',
        '/system/fonts/DroidSansFallbackFull.ttf',
        '/system/fonts/DroidSansFallback.ttf',
        '/system/fonts/SourceHanSansCN-Regular.otf',
        '/system/fonts/Miui-Regular.ttf',
    ]
    from kivy.core.text import LabelBase, DEFAULT_FONT
    for path in candidates:
        if os.path.exists(path):
            try:
                LabelBase.register(DEFAULT_FONT, path)
                print(f'已注册中文字体: {path}')
                return
            except Exception as e:
                print(f'注册字体失败 {path}: {e}')


if IS_ANDROID:
    _setup_cjk_font()


def _default_save_dir():
    """默认下载目录：安卓用外部存储 Download 目录，桌面用 ~/Downloads"""
    if IS_ANDROID:
        ext = os.environ.get('EXTERNAL_STORAGE') or '/storage/emulated/0'
        path = os.path.join(ext, 'Download', 'BTDownloader')
    else:
        path = os.path.expanduser('~/Downloads')
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        path = os.path.expanduser('~/Downloads')
    return path


# 状态对应的颜色 (R,G,B,A)：下载中=蓝、暂停=橙、完成/做种=绿、错误=红、等待=灰
STATE_COLORS = {
    'queued': (0.5, 0.5, 0.5, 1),
    'checking': (0.5, 0.5, 0.5, 1),
    'metadata': (1.0, 0.6, 0.0, 1),
    'downloading': (0.0, 0.5, 1.0, 1),
    'paused': (1.0, 0.6, 0.0, 1),
    'finished': (0.0, 0.8, 0.0, 1),
    'seeding': (0.0, 0.8, 0.0, 1),
    'error': (1.0, 0.0, 0.0, 1),
}

# 状态中文标签
STATE_LABELS = {
    'queued': '等待中',
    'checking': '检查文件',
    'metadata': '获取元数据',
    'downloading': '下载中',
    'paused': '已暂停',
    'finished': '已完成',
    'seeding': '做种中',
    'error': '错误',
}

# Tracker 列表获取地址（按顺序尝试，成功即止）
TRACKER_URLS = [
    'https://cdn.jsdelivr.net/gh/ngosang/trackerslist/trackers_best.txt',
    'https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_best.txt',
]


class Config:
    """配置管理类：JSON 持久化到 config.json"""

    DEFAULTS = {
        'save_dir': '',
        'max_concurrent': 5,
        'download_rate_limit': 0,   # 字节/秒，0=不限
        'upload_rate_limit': 0,
        'sequential_download': False,
        'delete_files_on_remove': False,
        'notify_on_complete': True,
        'trackers': [],
        'last_tracker_sync': 0,
        'dark_mode': False,
    }

    def __init__(self, path):
        self.path = path
        self.data = dict(self.DEFAULTS)
        self.data['save_dir'] = _default_save_dir()
        self.load()

    def load(self):
        """从磁盘加载配置"""
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    for k, v in saved.items():
                        self.data[k] = v
        except Exception as e:
            print(f'加载配置失败: {e}')

    def save(self):
        """保存配置到磁盘"""
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f'保存配置失败: {e}')

    def get(self, key):
        return self.data.get(key, self.DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()


class Task:
    """单个下载任务封装类"""

    def __init__(self, name, source, save_path, handle=None, mock=False):
        self.name = name
        self.source = source
        self.save_path = save_path
        self.handle = handle          # libtorrent torrent_handle
        self.mock = mock
        self.progress = 0.0
        self.state = 'queued'
        self.dl_rate = 0.0            # KB/s
        self.ul_rate = 0.0            # KB/s
        self.peers = 0
        self.eta = '未知'
        self.total_size = 0
        self.files = []               # [{'path','size','priority','index'}]
        self.completed = False
        self.notified = False
        self._mock_paused = False
        self._mock_total = 0

    # ---------- mock 模式 ----------
    def update_mock(self):
        """更新 mock 模式进度"""
        if self._mock_paused:
            self.state = 'paused'
            self.dl_rate = 0
            self.ul_rate = 0
            return
        self.progress = min(100.0, self.progress + random.uniform(0.5, 3.0))
        self.dl_rate = random.uniform(50, 500)
        self.ul_rate = random.uniform(10, 50)
        self.peers = random.randint(5, 50)
        remaining = self._mock_total * (1 - self.progress / 100.0)
        if self.dl_rate > 0 and remaining > 0:
            eta = remaining / (self.dl_rate * 1024.0)
            self.eta = BtDownloaderApp._format_time(eta)
        else:
            self.eta = '未知'
        self.state = 'downloading'
        if self.progress >= 100.0:
            self.state = 'finished'
            self.completed = True
            self.progress = 100.0
            self.eta = '已完成'

    # ---------- 真实模式 ----------
    def update_real(self):
        """从 libtorrent handle 更新状态"""
        if not self.handle:
            return
        try:
            status = self.handle.status()
            try:
                paused = self.handle.is_paused()
            except Exception:
                paused = False

            if not status.has_metadata:
                self.state = 'metadata'
                self.progress = status.progress * 100
                self.peers = status.num_peers
                return

            self.progress = status.progress * 100
            self.dl_rate = status.download_rate / 1024.0
            self.ul_rate = status.upload_rate / 1024.0
            self.peers = status.num_peers
            try:
                self.total_size = status.total_wanted
            except Exception:
                pass

            if paused:
                self.state = 'paused'
            else:
                try:
                    if status.is_seeding:
                        self.state = 'seeding'
                        self.completed = True
                    elif status.is_finished:
                        self.state = 'finished'
                        self.completed = True
                    else:
                        self.state = BtDownloaderApp._lt_state_to_key(status.state)
                except Exception:
                    self.state = BtDownloaderApp._lt_state_to_key(status.state)

            if self.completed:
                self.eta = '已完成'
            elif self.dl_rate > 0:
                try:
                    remaining = status.total_wanted - status.total_wanted_done
                    eta = remaining / (self.dl_rate * 1024.0)
                    self.eta = BtDownloaderApp._format_time(eta) if eta > 0 else '未知'
                except Exception:
                    self.eta = '未知'
            else:
                self.eta = '未知'
        except Exception as e:
            print(f'更新任务状态出错: {e}')
            self.state = 'error'

    # ---------- 文件列表 ----------
    def load_files(self):
        """加载文件列表（首次获取元数据后调用）"""
        if self.mock:
            if not self.files:
                self.files = [{
                    'path': f'file_{i+1}.bin',
                    'size': random.randint(50, 200) * 1024 * 1024,
                    'priority': 4,
                    'index': i,
                } for i in range(random.randint(2, 5))]
                self._mock_total = sum(f['size'] for f in self.files)
            return
        if not self.handle:
            return
        try:
            info = self.handle.get_torrent_info()
            fs = info.files()
            self.files = []
            for i in range(len(fs)):
                f = fs[i]
                priority = 4
                try:
                    priority = self.handle.file_priority(i)
                except Exception:
                    pass
                self.files.append({
                    'path': f.path,
                    'size': f.size,
                    'priority': priority,
                    'index': i,
                })
            self.total_size = sum(f['size'] for f in self.files)
        except Exception as e:
            print(f'加载文件列表出错: {e}')

    def set_file_priority(self, index, priority):
        """设置文件优先级（0=不下载, 4=正常, 7=最高）"""
        if 0 <= index < len(self.files):
            self.files[index]['priority'] = priority
        if self.mock or not self.handle:
            return
        try:
            self.handle.file_priority(index, priority)
        except Exception as e:
            print(f'设置文件优先级出错: {e}')

    # ---------- 控制 ----------
    def pause(self):
        if self.mock:
            self._mock_paused = True
            self.state = 'paused'
            return
        if self.handle:
            try:
                self.handle.pause()
            except Exception as e:
                print(f'暂停出错: {e}')

    def resume(self):
        if self.mock:
            self._mock_paused = False
            self.state = 'downloading'
            return
        if self.handle:
            try:
                self.handle.resume()
            except Exception as e:
                print(f'恢复出错: {e}')

    def set_sequential(self, enable):
        """设置顺序下载（边下边播）"""
        if self.mock or not self.handle:
            return
        try:
            self.handle.set_sequential_download(enable)
        except Exception:
            try:
                if enable:
                    self.handle.set_flags(lt.torrent_flags.sequential_download)
                else:
                    self.handle.unset_flags(lt.torrent_flags.sequential_download)
            except Exception as e:
                print(f'设置顺序下载出错: {e}')


class BtDownloaderApp(App):
    """主应用类：管理 UI 与监控"""

    def build(self):
        self.title = 'BT下载器'

        # 配置文件路径（user_data_dir 在安卓上是可写的应用私有目录）
        config_path = os.path.join(self.user_data_dir, 'config.json')
        self.config = Config(config_path)

        # 下载会话
        if LIBTORRENT_AVAILABLE:
            try:
                self.session = lt.session()
                self._apply_session_settings()
                self.mock_mode = False
            except Exception as e:
                print(f'初始化 libtorrent 失败，进入 mock 模式: {e}')
                self.session = None
                self.mock_mode = True
        else:
            self.session = None
            self.mock_mode = True

        self.tasks = []              # Task 列表
        self.selected_task = None
        self.running = True
        self.trackers = list(self.config.get('trackers') or [])
        self._last_detail_file_count = -1

        # 主题
        self._update_theme()

        # 主布局
        self.root = BoxLayout(orientation='vertical', padding=5, spacing=5)

        # 顶部标题栏
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=5)
        self.title_label = Label(text='BT下载器', font_size='20sp', bold=True,
                                 color=self.theme_text)
        header.add_widget(self.title_label)
        if self.mock_mode:
            self.mock_badge = Label(text='[Mock模式]', color=(1, 0.5, 0, 1),
                                    size_hint_x=0.4, markup=True, font_size='14sp')
        else:
            self.mock_badge = Label(text='', size_hint_x=0.4)
        header.add_widget(self.mock_badge)
        self.root.add_widget(header)

        # Tab 按钮栏
        tab_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=5)
        self.tab_btn_list = Button(text='任务列表')
        self.tab_btn_detail = Button(text='任务详情')
        self.tab_btn_settings = Button(text='设置')
        self.tab_btn_list.bind(on_press=lambda x: self._switch_tab('list'))
        self.tab_btn_detail.bind(on_press=lambda x: self._switch_tab('detail'))
        self.tab_btn_settings.bind(on_press=lambda x: self._switch_tab('settings'))
        for b in (self.tab_btn_list, self.tab_btn_detail, self.tab_btn_settings):
            tab_bar.add_widget(b)
        self.root.add_widget(tab_bar)

        # 内容容器
        self.content = BoxLayout(orientation='vertical')
        self.root.add_widget(self.content)

        # 构建 3 个视图
        self._build_list_view()
        self._build_detail_view()
        self._build_settings_view()

        self.current_tab = None
        self._switch_tab('list')

        # 启动后台监控线程（单线程轮询所有任务）
        self.monitor_thread = threading.Thread(target=self._monitor_all, daemon=True)
        self.monitor_thread.start()

        # 后台拉取 tracker 列表（静默降级）
        if LIBTORRENT_AVAILABLE:
            threading.Thread(target=self._fetch_trackers, daemon=True).start()

        # 定时刷新 UI（Kivy 主线程）
        Clock.schedule_interval(self._refresh_ui, 0.5)

        return self.root

    # =========================================================
    # 配置 / 主题
    # =========================================================
    def _update_theme(self):
        """根据深色模式设置主题颜色"""
        if self.config.get('dark_mode'):
            self.theme_bg = (0.12, 0.12, 0.16, 1)
            self.theme_text = (1, 1, 1, 1)
        else:
            self.theme_bg = (0.95, 0.95, 0.97, 1)
            self.theme_text = (0.1, 0.1, 0.1, 1)
        if WINDOW_AVAILABLE:
            try:
                Window.clearcolor = self.theme_bg
            except Exception:
                pass

    def _apply_session_settings(self):
        """应用 libtorrent session 全局设置"""
        if not self.session:
            return
        try:
            settings = self.session.get_settings()
            settings['listen_interfaces'] = '0.0.0.0:6881,[::]:6881'
            settings['connections_limit'] = 200
            settings['active_downloads'] = int(self.config.get('max_concurrent') or 5)
            settings['active_limit'] = 30
            settings['enable_dht'] = True
            settings['enable_lsd'] = True
            settings['enable_upnp'] = True
            settings['enable_natpmp'] = True
            settings['cache_size'] = 256 * 1024
            # 上下行限速
            settings['download_rate_limit'] = int(self.config.get('download_rate_limit') or 0)
            settings['upload_rate_limit'] = int(self.config.get('upload_rate_limit') or 0)
            self.session.apply_settings(settings)

            self.session.add_dht_router('router.bittorrent.com', 6881)
            self.session.add_dht_router('router.utorrent.com', 6881)
            self.session.add_dht_router('dht.transmissionbt.com', 6881)
        except Exception as e:
            print(f'应用 session 设置出错: {e}')

    def _apply_rate_limits(self):
        """应用上下行限速"""
        if not self.session:
            return
        try:
            settings = self.session.get_settings()
            settings['download_rate_limit'] = int(self.config.get('download_rate_limit') or 0)
            settings['upload_rate_limit'] = int(self.config.get('upload_rate_limit') or 0)
            self.session.apply_settings(settings)
        except Exception as e:
            print(f'应用限速出错: {e}')

    # =========================================================
    # 视图构建
    # =========================================================
    def _lbl(self, text, **kw):
        """创建带主题文字色的 Label"""
        kw.setdefault('color', self.theme_text)
        return Label(text=text, **kw)

    def _build_list_view(self):
        """任务列表视图"""
        self.list_view = BoxLayout(orientation='vertical', spacing=5)

        # 输入区（持久化，不会被刷新清空）
        input_box = BoxLayout(orientation='vertical', size_hint_y=None, height=80, spacing=5)
        input_box.add_widget(self._lbl('磁力链接或种子文件路径:', size_hint_y=None, height=22))
        self.source_input = TextInput(hint_text='输入磁力链接或种子路径', multiline=False,
                                      size_hint_y=None, height=40)
        input_box.add_widget(self.source_input)
        self.list_view.add_widget(input_box)

        add_btn = Button(text='添加任务', size_hint_y=None, height=45,
                         background_color=(0, 0.5, 1, 1))
        add_btn.bind(on_press=self.add_task)
        self.list_view.add_widget(add_btn)

        # 任务列表容器（动态刷新）
        self.list_view.add_widget(self._lbl('任务列表（点击查看详情）:', size_hint_y=None,
                                            height=22))
        self.list_scroll = ScrollView()
        self.list_container = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.list_container.bind(minimum_height=self.list_container.setter('height'))
        self.list_scroll.add_widget(self.list_container)
        self.list_view.add_widget(self.list_scroll)

    def _build_detail_view(self):
        """任务详情视图"""
        self.detail_view = BoxLayout(orientation='vertical', spacing=5)

        # 返回按钮
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=40, spacing=5)
        back_btn = Button(text='返回列表', size_hint_x=0.4)
        back_btn.bind(on_press=lambda x: self._switch_tab('list'))
        self.detail_name_label = Label(text='未选择任务', font_size='16sp', bold=True,
                                       color=self.theme_text, size_hint_x=0.6)
        top_bar.add_widget(back_btn)
        top_bar.add_widget(self.detail_name_label)
        self.detail_view.add_widget(top_bar)

        # 进度条
        prog_box = BoxLayout(orientation='vertical', size_hint_y=None, height=60)
        self.detail_progress_bar = ProgressBar(max=100, value=0, size_hint_y=None, height=20)
        self.detail_progress_label = Label(text='0.0%', font_size='18sp', color=self.theme_text,
                                            size_hint_y=None, height=22)
        prog_box.add_widget(self.detail_progress_bar)
        prog_box.add_widget(self.detail_progress_label)
        self.detail_view.add_widget(prog_box)

        # 状态信息网格
        info_grid = GridLayout(cols=4, size_hint_y=None, height=120, spacing=3)
        info_grid.add_widget(self._lbl('状态:', bold=True))
        self.detail_state_label = Label(text='-', color=(0.5, 0.5, 0.5, 1))
        info_grid.add_widget(self.detail_state_label)
        info_grid.add_widget(self._lbl('大小:', bold=True))
        self.detail_size_label = Label(text='-', color=self.theme_text)
        info_grid.add_widget(self.detail_size_label)
        info_grid.add_widget(self._lbl('下载:', bold=True))
        self.detail_speed_label = Label(text='0 KB/s', color=self.theme_text)
        info_grid.add_widget(self.detail_speed_label)
        info_grid.add_widget(self._lbl('上传:', bold=True))
        self.detail_ul_label = Label(text='0 KB/s', color=self.theme_text)
        info_grid.add_widget(self.detail_ul_label)
        info_grid.add_widget(self._lbl('节点:', bold=True))
        self.detail_peers_label = Label(text='0', color=self.theme_text)
        info_grid.add_widget(self.detail_peers_label)
        info_grid.add_widget(self._lbl('剩余:', bold=True))
        self.detail_eta_label = Label(text='未知', color=self.theme_text)
        info_grid.add_widget(self.detail_eta_label)
        self.detail_view.add_widget(info_grid)

        # 全局统计
        self.detail_stats_label = Label(text='统计: DHT 0 | 总下载 0 KB/s | 总上传 0 KB/s | 连接 0 | Tracker 0',
                                        size_hint_y=None, height=30, font_size='12sp',
                                        color=self.theme_text, halign='left', valign='middle')
        self.detail_stats_label.text_size = (None, 30)
        self.detail_view.add_widget(self.detail_stats_label)

        # 操作按钮
        btn_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=45, spacing=5)
        self.detail_pause_btn = Button(text='暂停', background_color=(1, 0.6, 0, 1))
        self.detail_pause_btn.bind(on_press=self._on_pause_resume)
        open_btn = Button(text='打开目录', background_color=(0, 0.5, 1, 1))
        open_btn.bind(on_press=self._on_open_dir)
        del_btn = Button(text='删除任务', background_color=(1, 0, 0, 1))
        del_btn.bind(on_press=self._on_remove)
        btn_bar.add_widget(self.detail_pause_btn)
        btn_bar.add_widget(open_btn)
        btn_bar.add_widget(del_btn)
        self.detail_view.add_widget(btn_bar)

        # 文件列表
        self.detail_view.add_widget(self._lbl('文件列表（点击勾选切换下载）:', size_hint_y=None,
                                             height=22))
        self.file_scroll = ScrollView()
        self.file_container = GridLayout(cols=1, spacing=3, size_hint_y=None)
        self.file_container.bind(minimum_height=self.file_container.setter('height'))
        self.file_scroll.add_widget(self.file_container)
        self.detail_view.add_widget(self.file_scroll)

    def _build_settings_view(self):
        """设置视图"""
        self.settings_view = BoxLayout(orientation='vertical', spacing=5)
        sv = ScrollView()
        inner = BoxLayout(orientation='vertical', size_hint_y=None, spacing=6)
        inner.bind(minimum_height=inner.setter('height'))

        def add_row(label_text, widget, height=70):
            row = BoxLayout(orientation='vertical', size_hint_y=None, height=height, spacing=2)
            row.add_widget(self._lbl(label_text, size_hint_y=None, height=20, font_size='13sp'))
            row.add_widget(widget)
            inner.add_widget(row)

        # 保存目录
        self.s_save_dir = TextInput(text=self.config.get('save_dir') or '', multiline=False,
                                     size_hint_y=None, height=38)
        add_row('保存目录:', self.s_save_dir)

        # 并发数
        self.s_max_concurrent = TextInput(text=str(self.config.get('max_concurrent') or 5),
                                          multiline=False, size_hint_y=None, height=38,
                                          input_filter='int')
        add_row('最大并发任务数:', self.s_max_concurrent)

        # 下载限速
        self.s_dl_limit = TextInput(text=self._format_rate(self.config.get('download_rate_limit')),
                                    multiline=False, size_hint_y=None, height=38)
        add_row('下载限速(0=不限, 可带KB/MB):', self.s_dl_limit)

        # 上传限速
        self.s_ul_limit = TextInput(text=self._format_rate(self.config.get('upload_rate_limit')),
                                    multiline=False, size_hint_y=None, height=38)
        add_row('上传限速(0=不限, 可带KB/MB):', self.s_ul_limit)

        # 开关按钮（用 ToggleButton state down 表示开）
        def make_toggle(text, state_key):
            cur = bool(self.config.get(state_key))
            tb = ToggleButton(text=text + (' [开]' if cur else ' [关]'),
                              state='down' if cur else 'normal',
                              size_hint_y=None, height=40)
            tb.config_key = state_key
            tb.label_text = text
            tb.bind(on_press=self._on_toggle_setting)
            return tb

        self.t_sequential = make_toggle('顺序下载(边下边播)', 'sequential_download')
        self.t_delete = make_toggle('删除时同时删文件', 'delete_files_on_remove')
        self.t_notify = make_toggle('完成时通知', 'notify_on_complete')
        self.t_dark = make_toggle('深色模式', 'dark_mode')
        inner.add_widget(self.t_sequential)
        inner.add_widget(self.t_delete)
        inner.add_widget(self.t_notify)
        inner.add_widget(self.t_dark)

        # tracker 信息
        self.tracker_info_label = Label(text=self._tracker_info_text(), size_hint_y=None,
                                        height=40, font_size='12sp', color=self.theme_text,
                                        halign='left', valign='middle')
        self.tracker_info_label.text_size = (None, 40)
        inner.add_widget(self.tracker_info_label)

        sync_btn = Button(text='立即同步 Tracker 列表', size_hint_y=None, height=40,
                          background_color=(0, 0.5, 1, 1))
        sync_btn.bind(on_press=lambda x: threading.Thread(target=self._fetch_trackers,
                                                          daemon=True).start())
        inner.add_widget(sync_btn)

        # 保存按钮
        save_btn = Button(text='保存设置', size_hint_y=None, height=50,
                          background_color=(0, 0.8, 0, 1))
        save_btn.bind(on_press=self._on_save_settings)
        inner.add_widget(save_btn)

        sv.add_widget(inner)
        self.settings_view.add_widget(sv)

    # =========================================================
    # Tab 切换
    # =========================================================
    def _switch_tab(self, tab):
        if self.current_tab == tab:
            return
        self.current_tab = tab
        self.content.clear_widgets()
        if tab == 'list':
            self.content.add_widget(self.list_view)
            self.tab_btn_list.background_color = (0, 0.5, 1, 1)
            self.tab_btn_detail.background_color = (0.5, 0.5, 0.5, 1)
            self.tab_btn_settings.background_color = (0.5, 0.5, 0.5, 1)
        elif tab == 'detail':
            self.content.add_widget(self.detail_view)
            self.tab_btn_detail.background_color = (0, 0.5, 1, 1)
            self.tab_btn_list.background_color = (0.5, 0.5, 0.5, 1)
            self.tab_btn_settings.background_color = (0.5, 0.5, 0.5, 1)
            self._last_detail_file_count = -1
        elif tab == 'settings':
            self.content.add_widget(self.settings_view)
            self.tab_btn_settings.background_color = (0, 0.5, 1, 1)
            self.tab_btn_list.background_color = (0.5, 0.5, 0.5, 1)
            self.tab_btn_detail.background_color = (0.5, 0.5, 0.5, 1)

    # =========================================================
    # 任务管理
    # =========================================================
    def _derive_name(self, source):
        """从源推导任务名"""
        if source.startswith('magnet:'):
            try:
                parsed = urllib.parse.urlparse(source)
                params = urllib.parse.parse_qs(parsed.query)
                dns = params.get('dn')
                if dns:
                    return dns[0][:40]
            except Exception:
                pass
            return '磁力任务'
        if os.path.isfile(source):
            return os.path.basename(source)
        return source[:30]

    def add_task(self, instance):
        """添加新任务"""
        source = self.source_input.text.strip()
        if not source:
            self._show_error('请输入磁力链接或种子路径')
            return
        save_path = self.config.get('save_dir') or os.path.expanduser('~/Downloads')
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except Exception as e:
                self._show_error(f'无法创建目录: {e}')
                return

        max_c = int(self.config.get('max_concurrent') or 5)
        if len(self.tasks) >= max_c:
            self._show_error(f'已达最大任务数上限 ({max_c})，请先删除已完成任务')
            return

        name = self._derive_name(source)
        if self.mock_mode:
            self._start_mock_task(source, save_path, name)
        else:
            self._add_task_real(source, save_path, name)

    def _add_task_real(self, source, save_path, name):
        """添加真实 libtorrent 任务"""
        try:
            params = {
                'save_path': save_path,
                'storage_mode': lt.storage_mode_t.storage_mode_sparse,
            }
            if os.path.isfile(source):
                info = lt.torrent_info(source)
                params['ti'] = info
            else:
                params['url'] = source
            handle = self.session.add_torrent(params)

            # 为新任务添加 tracker
            for i, tr in enumerate(self.trackers):
                try:
                    handle.add_tracker({'url': tr, 'tier': i})
                except Exception:
                    pass
            # 顺序下载
            if self.config.get('sequential_download'):
                try:
                    handle.set_sequential_download(True)
                except Exception:
                    try:
                        handle.set_flags(lt.torrent_flags.sequential_download)
                    except Exception:
                        pass

            task = Task(name, source, save_path, handle=handle, mock=False)
            self.tasks.append(task)
            self.source_input.text = ''
            self._show_info('任务已添加')
        except Exception as e:
            self._show_error(f'无法添加任务: {e}')

    def _start_mock_task(self, source, save_path, name):
        """添加 mock 任务"""
        task = Task(name, source, save_path, mock=True)
        task.load_files()
        if task._mock_total == 0:
            task._mock_total = random.randint(100, 500) * 1024 * 1024
        self.tasks.append(task)
        self.source_input.text = ''
        self._show_info('任务已添加（Mock 模式）')

    def _select_task(self, task):
        """选中任务，跳转详情"""
        self.selected_task = task
        self._switch_tab('detail')

    def _on_pause_resume(self, instance):
        task = self.selected_task
        if not task:
            return
        if task.state == 'paused':
            task.resume()
        else:
            task.pause()

    def _on_open_dir(self, instance):
        task = self.selected_task
        if not task:
            return
        self._open_directory(task.save_path)

    def _on_remove(self, instance):
        task = self.selected_task
        if not task:
            return
        self._show_remove_confirm(task)

    def remove_task(self, task, delete_files):
        """移除任务"""
        if task in self.tasks:
            self.tasks.remove(task)
        if not task.mock and task.handle and self.session:
            try:
                if delete_files:
                    self.session.remove_torrent(task.handle, lt.options_t.delete_files)
                else:
                    self.session.remove_torrent(task.handle)
            except Exception as e:
                print(f'移除任务出错: {e}')
        if self.selected_task is task:
            self.selected_task = None
            self._switch_tab('list')

    # =========================================================
    # 文件优先级切换
    # =========================================================
    def _toggle_file_priority(self, instance, task, index):
        if not task or index >= len(task.files):
            return
        f = task.files[index]
        new_pri = 0 if f['priority'] > 0 else 4
        task.set_file_priority(index, new_pri)
        instance.text = self._file_button_text(f['path'], f['size'], new_pri)

    # =========================================================
    # 监控线程（后台，不直接更新 UI）
    # =========================================================
    def _monitor_all(self):
        """单线程轮询所有任务，更新 Task 数据"""
        while self.running:
            for task in list(self.tasks):
                try:
                    if task.mock:
                        task.update_mock()
                    else:
                        task.update_real()
                        # 首次获取元数据后加载文件列表
                        if not task.files and task.handle:
                            try:
                                st = task.handle.status()
                                if st.has_metadata:
                                    task.load_files()
                            except Exception:
                                pass
                    # 完成通知（仅一次）
                    if task.completed and not task.notified:
                        task.notified = True
                        if self.config.get('notify_on_complete'):
                            Clock.schedule_once(lambda dt, t=task: self._show_complete_popup(t))
                except Exception as e:
                    print(f'监控任务出错: {e}')
            time.sleep(1)

    # =========================================================
    # Tracker 拉取（后台，静默降级）
    # =========================================================
    def _fetch_trackers(self):
        """从 TRACKER_URLS 拉取 tracker 列表，成功即止"""
        for url in TRACKER_URLS:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read().decode('utf-8', errors='ignore')
                trackers = [line.strip() for line in data.splitlines()
                            if line.strip() and not line.strip().startswith('#')]
                if trackers:
                    self.trackers = trackers
                    self.config.set('trackers', trackers)
                    self.config.set('last_tracker_sync', int(time.time()))
                    print(f'已同步 {len(trackers)} 个 tracker（来源: {url}）')
                    Clock.schedule_once(lambda dt: self._update_tracker_info_label())
                    return
            except Exception as e:
                print(f'拉取 tracker 失败 ({url}): {e}')
                continue
        print('所有 tracker 源均不可用，使用已存配置')
        Clock.schedule_once(lambda dt: self._update_tracker_info_label())

    # =========================================================
    # UI 刷新（Kivy 主线程，由 Clock 调度）
    # =========================================================
    def _refresh_ui(self, dt):
        """定时刷新当前视图"""
        if self.current_tab == 'list':
            self._refresh_list_view()
        elif self.current_tab == 'detail':
            self._refresh_detail_view()

    def _refresh_list_view(self):
        """刷新任务列表"""
        self.list_container.clear_widgets()
        if not self.tasks:
            self.list_container.add_widget(self._lbl('暂无任务，请添加磁力链接或种子路径',
                                                     size_hint_y=None, height=40, font_size='14sp'))
            return
        for task in self.tasks:
            self.list_container.add_widget(self._make_task_card(task))

    def _make_task_card(self, task):
        """构建单个任务卡片"""
        card = BoxLayout(orientation='vertical', size_hint_y=None, height=72, spacing=2)
        color = STATE_COLORS.get(task.state, (0, 0, 0, 1))
        state_txt = STATE_LABELS.get(task.state, task.state)
        rgb = self._rgb(color)
        summary = (f'{task.name}\n[color={rgb}]{state_txt}[/color]  '
                   f'{task.progress:.1f}%  {task.dl_rate:.0f}KB/s  {task.peers}节点')
        btn = Button(text=summary, markup=True, font_size='13sp', halign='left', valign='middle')
        btn.text_size = (None, 60)
        btn.bind(on_press=lambda x, t=task: self._select_task(t))
        card.add_widget(btn)
        pb = ProgressBar(max=100, value=task.progress, size_hint_y=None, height=8)
        card.add_widget(pb)
        return card

    def _refresh_detail_view(self):
        """刷新详情视图"""
        task = self.selected_task
        if not task:
            self.detail_name_label.text = '未选择任务'
            self.detail_progress_bar.value = 0
            self.detail_progress_label.text = '0.0%'
            self.file_container.clear_widgets()
            return

        self.detail_name_label.text = task.name
        self.detail_progress_bar.value = task.progress
        self.detail_progress_label.text = f'{task.progress:.1f}%'
        color = STATE_COLORS.get(task.state, (0.1, 0.1, 0.1, 1))
        self.detail_state_label.color = color
        self.detail_state_label.text = STATE_LABELS.get(task.state, task.state)
        self.detail_size_label.text = self._format_size(task.total_size) if task.total_size else '-'
        self.detail_speed_label.text = f'{task.dl_rate:.1f} KB/s'
        self.detail_ul_label.text = f'{task.ul_rate:.1f} KB/s'
        self.detail_peers_label.text = str(task.peers)
        self.detail_eta_label.text = task.eta

        # 暂停/继续按钮文本
        self.detail_pause_btn.text = '继续' if task.state == 'paused' else '暂停'

        # 全局统计
        self.detail_stats_label.text = self._stats_text()

        # 文件列表（仅当数量变化时重建，避免点击丢失）
        if len(task.files) != self._last_detail_file_count:
            self._last_detail_file_count = len(task.files)
            self.file_container.clear_widgets()
            for f in task.files:
                fb = Button(text=self._file_button_text(f['path'], f['size'], f['priority']),
                            font_size='12sp', size_hint_y=None, height=34, halign='left',
                            valign='middle')
                fb.text_size = (None, 34)
                fb.bind(on_press=lambda x, t=task, idx=f['index']: self._toggle_file_priority(x, t, idx))
                self.file_container.add_widget(fb)

    def _stats_text(self):
        """构造全局统计文本"""
        if self.session:
            try:
                st = self.session.status()
                dht = st.dht_nodes
                tdl = st.download_rate / 1024.0
                tul = st.upload_rate / 1024.0
                conns = st.num_peers
                trackers = len(self.trackers)
            except Exception:
                dht = tdl = tul = conns = trackers = 0
        else:
            dht = 0
            tdl = sum(t.dl_rate for t in self.tasks)
            tul = sum(t.ul_rate for t in self.tasks)
            conns = sum(t.peers for t in self.tasks)
            trackers = len(self.trackers)
        return (f'统计: DHT {dht} | 总下载 {tdl:.0f}KB/s | 总上传 {tul:.0f}KB/s | '
                f'连接 {conns} | Tracker {trackers}')

    def _update_tracker_info_label(self):
        if hasattr(self, 'tracker_info_label'):
            self.tracker_info_label.text = self._tracker_info_text()

    def _tracker_info_text(self):
        n = len(self.trackers)
        ts = self.config.get('last_tracker_sync') or 0
        if ts:
            try:
                tstr = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))
            except Exception:
                tstr = '未知'
        else:
            tstr = '未同步'
        return f'Tracker: {n} 个 | 上次同步: {tstr}'

    # =========================================================
    # 设置交互
    # =========================================================
    def _on_toggle_setting(self, instance):
        key = instance.config_key
        new_val = instance.state == 'down'
        instance.text = instance.label_text + (' [开]' if new_val else ' [关]')
        self.config.set(key, new_val)
        # 深色模式立即生效（重建视图推迟到下一帧，避免在事件分发中改动控件树）
        if key == 'dark_mode':
            self._update_theme()
            Clock.schedule_once(lambda dt: self._rebuild_views())
        # 顺序下载应用到现有任务
        if key == 'sequential_download':
            for t in self.tasks:
                t.set_sequential(new_val)

    def _on_save_settings(self, instance):
        try:
            save_dir = self.s_save_dir.text.strip() or _default_save_dir()
            self.config.set('save_dir', save_dir)
            max_c = max(1, int(self.s_max_concurrent.text or 5))
            self.config.set('max_concurrent', max_c)
            self.config.set('download_rate_limit', self._parse_rate(self.s_dl_limit.text))
            self.config.set('upload_rate_limit', self._parse_rate(self.s_ul_limit.text))
        except Exception as e:
            self._show_error(f'保存失败: {e}')
            return
        # 应用到 session
        if self.session:
            try:
                settings = self.session.get_settings()
                settings['active_downloads'] = int(self.config.get('max_concurrent') or 5)
                self.session.apply_settings(settings)
            except Exception:
                pass
        self._apply_rate_limits()
        self._show_info('设置已保存')

    def _rebuild_views(self):
        """主题切换后重建视图以应用文字色"""
        self._build_list_view()
        self._build_detail_view()
        self._build_settings_view()
        # 切回当前 tab
        cur = self.current_tab
        self.current_tab = None
        self._switch_tab(cur or 'list')

    # =========================================================
    # 弹窗
    # =========================================================
    def _show_complete_popup(self, task):
        """任务完成弹窗 + 打开目录"""
        content = BoxLayout(orientation='vertical', spacing=5, padding=5)
        content.add_widget(Label(text=f'下载完成！\n{task.name}'))
        btn_box = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=45)
        open_btn = Button(text='打开目录')
        close_btn = Button(text='关闭')
        btn_box.add_widget(open_btn)
        btn_box.add_widget(close_btn)
        content.add_widget(btn_box)
        popup = Popup(title='完成', content=content, size_hint=(0.85, 0.35))
        open_btn.bind(on_press=lambda x: self._open_directory(task.save_path))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def _show_remove_confirm(self, task):
        """删除任务确认弹窗（可选删文件）"""
        content = BoxLayout(orientation='vertical', spacing=5, padding=5)
        content.add_widget(Label(text=f'删除任务？\n{task.name}'))
        btn_box = BoxLayout(orientation='horizontal', spacing=5, size_hint_y=None, height=45)
        del_files_btn = Button(text='删任务+文件', background_color=(1, 0, 0, 1))
        del_only_btn = Button(text='仅删任务', background_color=(0.8, 0.5, 0, 1))
        cancel_btn = Button(text='取消')
        btn_box.add_widget(del_files_btn)
        btn_box.add_widget(del_only_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)
        popup = Popup(title='删除任务', content=content, size_hint=(0.9, 0.4))

        def do_remove(delete_files):
            popup.dismiss()
            self.remove_task(task, delete_files)

        del_files_btn.bind(on_press=lambda x: do_remove(True))
        del_only_btn.bind(on_press=lambda x: do_remove(False))
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()

    def _show_error(self, message):
        self._popup_message('提示', message)

    def _show_info(self, message):
        self._popup_message('提示', message)

    def _popup_message(self, title, message):
        content = BoxLayout(orientation='vertical', padding=5)
        content.add_widget(Label(text=message))
        btn = Button(text='确定', size_hint_y=None, height=40)
        content.add_widget(btn)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.3))
        btn.bind(on_press=popup.dismiss)
        popup.open()

    # =========================================================
    # 工具方法
    # =========================================================
    def _open_directory(self, path):
        """打开目录，失败则提示路径"""
        if not path:
            self._show_error('未设置保存目录')
            return
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except Exception as e:
            self._show_error(f'目录不存在且无法创建:\n{path}\n{e}')
            return
        opened = False
        # Windows
        try:
            if os.name == 'nt':
                os.startfile(path)
                opened = True
        except Exception:
            opened = False
        # Linux 桌面
        if not opened:
            try:
                import subprocess
                subprocess.Popen(['xdg-open', path])
                opened = True
            except Exception:
                opened = False
        # 安卓：尝试用 Intent 调起文件管理器
        if not opened and IS_ANDROID:
            try:
                from jnius import autoclass
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                intent = Intent(Intent.ACTION_VIEW)
                intent.setDataAndType(Uri.parse('file://' + path), 'resource/folder')
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                PythonActivity.mActivity.startActivity(intent)
                opened = True
            except Exception:
                opened = False
        if not opened:
            # 无可用方法，仅提示路径
            self._show_error(f'无法自动打开目录，路径:\n{path}')

    def _file_button_text(self, path, size, priority):
        mark = '[下载]' if priority > 0 else '[跳过]'
        return f'{mark} {path} ({self._format_size(size)})'

    @staticmethod
    def _rgb(c):
        return '#%02x%02x%02x' % (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))

    @staticmethod
    def _parse_rate(text):
        """解析限速文本为字节/秒，支持 0 / 500 / 500KB / 1MB"""
        text = (text or '').strip().lower()
        if not text:
            return 0
        mult = 1
        for suf, m in (('gb', 1024 ** 3), ('mb', 1024 ** 2), ('kb', 1024)):
            if text.endswith(suf):
                mult = m
                text = text[:-len(suf)]
                break
        try:
            return int(float(text.strip()) * mult)
        except Exception:
            return 0

    @staticmethod
    def _format_rate(rate):
        """格式化限速为可读文本"""
        rate = int(rate or 0)
        if rate <= 0:
            return '0'
        if rate >= 1024 ** 2:
            return f'{rate / 1024 ** 2:.1f}MB'
        if rate >= 1024:
            return f'{rate / 1024:.0f}KB'
        return str(rate)

    @staticmethod
    def _lt_state_to_key(state):
        """libtorrent 状态码 -> 状态键"""
        if not LIBTORRENT_AVAILABLE:
            return 'downloading'
        try:
            mapping = {
                lt.torrent_status.queued_for_checking: 'queued',
                lt.torrent_status.checking_files: 'checking',
                lt.torrent_status.downloading_metadata: 'metadata',
                lt.torrent_status.downloading: 'downloading',
                lt.torrent_status.finished: 'finished',
                lt.torrent_status.seeding: 'seeding',
                lt.torrent_status.allocating: 'checking',
                lt.torrent_status.checking_resume_data: 'checking',
            }
            return mapping.get(state, 'downloading')
        except Exception:
            return 'downloading'

    @staticmethod
    def _format_size(bytes_size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f'{bytes_size:.1f} {unit}'
            bytes_size /= 1024.0
        return f'{bytes_size:.1f} PB'

    @staticmethod
    def _format_time(seconds):
        if seconds < 60:
            return f'{int(seconds)}秒'
        elif seconds < 3600:
            return f'{int(seconds / 60)}分钟'
        else:
            h = int(seconds / 3600)
            m = int((seconds % 3600) / 60)
            return f'{h}小时{m}分钟'

    @staticmethod
    def _get_state_string(state):
        """libtorrent 状态码 -> 中文描述（保留原接口）"""
        if not LIBTORRENT_AVAILABLE:
            return {3: '下载中', 4: '完成', 5: '做种中'}.get(state, '未知状态')
        states = {
            lt.torrent_status.queued_for_checking: '排队检查',
            lt.torrent_status.checking_files: '检查文件',
            lt.torrent_status.downloading_metadata: '下载元数据',
            lt.torrent_status.downloading: '下载中',
            lt.torrent_status.finished: '完成',
            lt.torrent_status.seeding: '做种中',
            lt.torrent_status.allocating: '分配空间',
            lt.torrent_status.checking_resume_data: '检查恢复数据',
        }
        return states.get(state, '未知状态')

    def on_start(self):
        """启动后请求存储权限（安卓）"""
        if IS_ANDROID:
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                ])
            except Exception as e:
                print(f'请求存储权限失败: {e}')

    def on_stop(self):
        """应用退出时停止监控"""
        self.running = False
        try:
            self.config.save()
        except Exception:
            pass


if __name__ == '__main__':
    BtDownloaderApp().run()
