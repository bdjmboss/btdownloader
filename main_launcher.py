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
import threading
import time
import os
import random


class MockTorrentSession:
    """模拟 BT 会话，用于在没有 libtorrent 的环境中测试 UI"""

    class MockTorrentHandle:
        def __init__(self, source, save_path):
            self.source = source
            self.save_path = save_path
            self._paused = False
            self._progress = 0
            self._download_rate = 0
            self._upload_rate = 0
            self._peers = 0
            self._has_metadata = True
            self._state = 3  # downloading
            self._files = []
            self._total_size = random.randint(100, 500) * 1024 * 1024  # 100-500 MB
            self._total_done = 0
            self._is_seeding = False
            self._generate_mock_files()

        def _generate_mock_files(self):
            num_files = random.randint(2, 6)
            file_types = ['.mkv', '.mp4', '.zip', '.rar', '.iso', '.pdf']
            for i in range(num_files):
                fname = f'video_{i+1}{random.choice(file_types)}'
                fsize = random.randint(50, 200) * 1024 * 1024  # 50-200 MB each
                self._files.append({'path': fname, 'size': fsize})

        def status(self):
            class MockStatus:
                pass
            s = MockStatus()
            s.progress = self._progress / 100.0
            s.download_rate = self._download_rate * 1024
            s.upload_rate = self._upload_rate * 1024
            s.num_peers = self._peers
            s.has_metadata = self._has_metadata
            s.state = self._state
            s.is_seeding = self._is_seeding
            s.total_wanted = self._total_size
            s.total_wanted_done = self._total_done
            return s

        def pause(self):
            self._paused = True
            self._state = 1  # checking_files (paused)

        def resume(self):
            self._paused = False
            self._state = 3  # downloading

        def force_dht_announce(self):
            pass

        def get_torrent_info(self):
            class MockInfo:
                pass
            info = MockInfo()
            info.files = lambda: self._files
            return info

    def __init__(self):
        self._settings = {}
        self._handles = []

    def get_settings(self):
        return self._settings

    def apply_settings(self, settings):
        self._settings = settings

    def add_dht_router(self, router, port):
        pass

    def add_torrent(self, params):
        source = params.get('url', params.get('ti', 'unknown'))
        save_path = params.get('save_path', '/sdcard/Download')
        handle = self.MockTorrentHandle(source, save_path)
        self._handles.append(handle)
        return handle

    def remove_torrent(self, handle):
        if handle in self._handles:
            self._handles.remove(handle)


class MockLibtorrent:
    """模拟 libtorrent 模块"""

    class storage_mode_t:
        storage_mode_sparse = 0

    class torrent_status:
        queued_for_checking = 0
        checking_files = 1
        downloading_metadata = 2
        downloading = 3
        finished = 4
        seeding = 5
        allocating = 6
        checking_resume_data = 7

    class torrent_info:
        def __init__(self, path):
            self._path = path

    @staticmethod
    def version():
        return '2.0.13.0 (mock)'


# 使用模拟 libtorrent
lt = MockLibtorrent()


class BtDownloaderApp(App):
    def build(self):
        self.title = 'BT下载器 (测试版)'

        self.session = MockTorrentSession()
        self.torrent_handle = None
        self.running = False

        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        title_label = Label(
            text='BT下载器 测试版',
            size_hint_y=None,
            height=50,
            font_size='24sp',
            bold=True
        )
        main_layout.add_widget(title_label)

        input_section = BoxLayout(orientation='vertical', size_hint_y=None, height=180, spacing=5)

        input_section.add_widget(Label(text='磁力链接或种子文件:', size_hint_y=None, height=25))
        self.source_input = TextInput(
            hint_text='输入磁力链接或种子路径',
            multiline=False,
            size_hint_y=None,
            height=40
        )
        input_section.add_widget(self.source_input)

        input_section.add_widget(Label(text='保存目录:', size_hint_y=None, height=25))
        self.path_input = TextInput(
            text='/sdcard/Download',
            multiline=False,
            size_hint_y=None,
            height=40
        )
        input_section.add_widget(self.path_input)

        main_layout.add_widget(input_section)

        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=5)

        self.start_btn = Button(text='开始下载', background_color=(0, 0.5, 1, 1))
        self.start_btn.bind(on_press=self.start_download)
        button_layout.add_widget(self.start_btn)

        self.pause_btn = Button(text='暂停', disabled=True, background_color=(1, 0.8, 0, 1))
        self.pause_btn.bind(on_press=self.pause_download)
        button_layout.add_widget(self.pause_btn)

        self.resume_btn = Button(text='继续', disabled=True, background_color=(0, 0.8, 0, 1))
        self.resume_btn.bind(on_press=self.resume_download)
        button_layout.add_widget(self.resume_btn)

        self.remove_btn = Button(text='删除', disabled=True, background_color=(1, 0, 0, 1))
        self.remove_btn.bind(on_press=self.remove_download)
        button_layout.add_widget(self.remove_btn)

        main_layout.add_widget(button_layout)

        progress_section = BoxLayout(orientation='vertical', size_hint_y=None, height=80)

        self.progress_bar = ProgressBar(max=100, value=0)
        progress_section.add_widget(self.progress_bar)

        self.progress_label = Label(text='0%', font_size='20sp')
        progress_section.add_widget(self.progress_label)

        main_layout.add_widget(progress_section)

        status_section = GridLayout(cols=2, size_hint_y=None, height=120, spacing=5)

        status_section.add_widget(Label(text='状态:', bold=True))
        self.status_label = Label(text='等待添加任务...', color=(0, 0.5, 1, 1))
        status_section.add_widget(self.status_label)

        status_section.add_widget(Label(text='下载速度:', bold=True))
        self.dl_speed_label = Label(text='0 KB/s')
        status_section.add_widget(self.dl_speed_label)

        status_section.add_widget(Label(text='上传速度:', bold=True))
        self.ul_speed_label = Label(text='0 KB/s')
        status_section.add_widget(self.ul_speed_label)

        status_section.add_widget(Label(text='节点数:', bold=True))
        self.peers_label = Label(text='0')
        status_section.add_widget(self.peers_label)

        status_section.add_widget(Label(text='剩余时间:', bold=True))
        self.eta_label = Label(text='未知')
        status_section.add_widget(self.eta_label)

        main_layout.add_widget(status_section)

        file_section = BoxLayout(orientation='vertical', spacing=5)
        file_section.add_widget(Label(text='文件列表:', bold=True, size_hint_y=None, height=25))

        scroll_view = ScrollView()
        self.file_list = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.file_list.bind(minimum_height=self.file_list.setter('height'))
        scroll_view.add_widget(self.file_list)
        file_section.add_widget(scroll_view)

        main_layout.add_widget(file_section)

        return main_layout

    def start_download(self, instance):
        source = self.source_input.text.strip()
        save_path = self.path_input.text.strip()

        if not source:
            self._show_error('请输入磁力链接或种子路径')
            return

        if not save_path:
            save_path = '/sdcard/Download'
            self.path_input.text = save_path

        if self.torrent_handle is not None:
            self.remove_download()

        try:
            params = {
                'save_path': save_path,
                'storage_mode': lt.storage_mode_t.storage_mode_sparse,
            }

            self.torrent_handle = self.session.add_torrent(params)
            self.running = True
            self.start_btn.disabled = True
            self.pause_btn.disabled = False
            self.remove_btn.disabled = False
            self.status_label.text = '正在准备下载...'

            self.monitor_thread = threading.Thread(target=self._monitor_download, daemon=True)
            self.monitor_thread.start()

        except Exception as e:
            self._show_error(f'无法添加任务: {str(e)}')

    def pause_download(self, instance):
        if self.torrent_handle:
            self.torrent_handle.pause()
            self.pause_btn.disabled = True
            self.resume_btn.disabled = False
            self.status_label.text = '已暂停'

    def resume_download(self, instance):
        if self.torrent_handle:
            self.torrent_handle.resume()
            self.pause_btn.disabled = False
            self.resume_btn.disabled = True
            self.status_label.text = '正在下载...'

    def remove_download(self, instance=None):
        if self.torrent_handle:
            self.session.remove_torrent(self.torrent_handle)
            self.torrent_handle = None
            self.running = False
            self.start_btn.disabled = False
            self.pause_btn.disabled = True
            self.resume_btn.disabled = True
            self.remove_btn.disabled = True
            self.progress_bar.value = 0
            self.progress_label.text = '0%'
            self.status_label.text = '任务已删除'
            self.dl_speed_label.text = '0 KB/s'
            self.ul_speed_label.text = '0 KB/s'
            self.peers_label.text = '0'
            self.eta_label.text = '未知'
            self.file_list.clear_widgets()

    def _monitor_download(self):
        while self.running:
            if not self.torrent_handle:
                break

            try:
                handle = self.torrent_handle

                if not handle._has_metadata:
                    Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', '正在获取元数据...'))
                    time.sleep(1)
                    continue

                # 模拟进度更新
                if not handle._paused:
                    handle._progress = min(100, handle._progress + random.uniform(0.5, 3.0))
                    handle._download_rate = random.uniform(50, 500)  # KB/s
                    handle._upload_rate = random.uniform(10, 50)  # KB/s
                    handle._peers = random.randint(5, 50)
                    handle._total_done = handle._total_size * handle._progress / 100.0

                progress = handle._progress
                dl_rate = handle._download_rate
                ul_rate = handle._upload_rate
                peers = handle._peers

                if dl_rate > 0 and progress < 100:
                    remaining = handle._total_size - handle._total_done
                    eta = remaining / (dl_rate * 1024)
                    eta_str = self._format_time(eta)
                elif progress >= 100:
                    eta_str = '已完成'
                else:
                    eta_str = '未知'

                state_str = self._get_state_string(handle._state)
                if handle._paused:
                    state_str = '已暂停'

                Clock.schedule_once(lambda dt: self._update_ui(progress, dl_rate, ul_rate, peers, eta_str, state_str))

                if progress >= 100:
                    handle._is_seeding = True
                    Clock.schedule_once(lambda dt: self._download_complete())
                    break

                time.sleep(1)
            except Exception as e:
                print(f'监控出错: {e}')
                time.sleep(1)

    def _update_ui(self, progress, dl_rate, ul_rate, peers, eta_str, state_str):
        self.progress_bar.value = progress
        self.progress_label.text = f'{progress:.1f}%'
        self.dl_speed_label.text = f'{dl_rate:.1f} KB/s'
        self.ul_speed_label.text = f'{ul_rate:.1f} KB/s'
        self.peers_label.text = str(peers)
        self.eta_label.text = eta_str
        self.status_label.text = state_str

        if len(self.file_list.children) == 0 and self.torrent_handle:
            self._update_file_list()

    def _update_file_list(self):
        if self.torrent_handle:
            info = self.torrent_handle.get_torrent_info()
            files = info._files
            self.file_list.clear_widgets()
            for f in files:
                file_label = Label(
                    text=f'{f["path"]} ({self._format_size(f["size"])})',
                    size_hint_y=None,
                    height=30,
                    text_size=(None, 30)
                )
                self.file_list.add_widget(file_label)

    def _download_complete(self):
        self.status_label.text = '下载完成！'
        self.dl_speed_label.text = '0 KB/s'
        self.eta_label.text = '已完成'
        self.progress_bar.value = 100
        self.progress_label.text = '100%'
        self.start_btn.disabled = False
        self.pause_btn.disabled = True
        self.resume_btn.disabled = True
        self.remove_btn.disabled = False
        self.running = False

        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text='下载任务已完成！'))
        popup = Popup(title='完成', content=content, size_hint=(0.8, 0.3))
        popup.open()

    def _show_error(self, message):
        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text=message))
        popup = Popup(title='错误', content=content, size_hint=(0.8, 0.3))
        popup.open()

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
        states = {
            0: '排队检查',
            1: '检查文件',
            2: '下载元数据',
            3: '下载中',
            4: '完成',
            5: '做种中',
            6: '分配空间',
            7: '检查恢复数据'
        }
        return states.get(state, '未知状态')


if __name__ == '__main__':
    BtDownloaderApp().run()
