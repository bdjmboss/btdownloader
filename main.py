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

try:
    import libtorrent as lt
    LIBTORRENT_AVAILABLE = True
except ImportError:
    LIBTORRENT_AVAILABLE = False
    lt = None


class BtDownloaderApp(App):
    def build(self):
        self.title = 'BT下载器'

        # 下载会话
        if LIBTORRENT_AVAILABLE:
            self.session = lt.session()
            self._apply_settings()
            self.mock_mode = False
        else:
            self.session = None
            self.mock_mode = True
        
        self.torrent_handle = None
        self.running = False
        
        # 主布局
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # 标题
        title_label = Label(
            text='BT下载器',
            size_hint_y=None,
            height=50,
            font_size='24sp',
            bold=True
        )
        main_layout.add_widget(title_label)
        
        # 输入区域
        input_section = BoxLayout(orientation='vertical', size_hint_y=None, height=180, spacing=5)
        
        # 种子链接输入
        input_section.add_widget(Label(text='磁力链接或种子文件:', size_hint_y=None, height=25))
        self.source_input = TextInput(
            hint_text='输入磁力链接或种子路径',
            multiline=False,
            size_hint_y=None,
            height=40
        )
        input_section.add_widget(self.source_input)
        
        # 保存路径输入
        input_section.add_widget(Label(text='保存目录:', size_hint_y=None, height=25))
        self.path_input = TextInput(
            text=os.path.expanduser('~/Downloads'),
            multiline=False,
            size_hint_y=None,
            height=40
        )
        input_section.add_widget(self.path_input)
        
        main_layout.add_widget(input_section)
        
        # 操作按钮
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
        
        # 进度条
        progress_section = BoxLayout(orientation='vertical', size_hint_y=None, height=80)
        
        self.progress_bar = ProgressBar(max=100, value=0)
        progress_section.add_widget(self.progress_bar)
        
        self.progress_label = Label(text='0%', font_size='20sp')
        progress_section.add_widget(self.progress_label)
        
        main_layout.add_widget(progress_section)
        
        # 状态信息
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
        
        # 文件列表
        file_section = BoxLayout(orientation='vertical', spacing=5)
        file_section.add_widget(Label(text='文件列表:', bold=True, size_hint_y=None, height=25))
        
        scroll_view = ScrollView()
        self.file_list = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.file_list.bind(minimum_height=self.file_list.setter('height'))
        scroll_view.add_widget(self.file_list)
        file_section.add_widget(scroll_view)
        
        main_layout.add_widget(file_section)
        
        return main_layout
    
    def _apply_settings(self):
        """应用优化设置"""
        settings = self.session.get_settings()
        settings['listen_interfaces'] = '0.0.0.0:6881,[::]:6881'
        settings['connections_limit'] = 200
        settings['active_downloads'] = 5
        settings['active_limit'] = 30
        settings['enable_dht'] = True
        settings['enable_lsd'] = True
        settings['enable_upnp'] = True
        settings['enable_natpmp'] = True
        settings['cache_size'] = 256 * 1024
        self.session.apply_settings(settings)
        
        self.session.add_dht_router("router.bittorrent.com", 6881)
        self.session.add_dht_router("router.utorrent.com", 6881)
        self.session.add_dht_router("dht.transmissionbt.com", 6881)
    
    def start_download(self, instance):
        source = self.source_input.text.strip()
        save_path = self.path_input.text.strip()

        if not source:
            self._show_error('请输入磁力链接或种子路径')
            return

        if not save_path:
            save_path = os.path.expanduser('~/Downloads')
            self.path_input.text = save_path

        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except Exception as e:
                self._show_error(f'无法创建目录: {str(e)}')
                return

        if self.torrent_handle is not None:
            self.remove_download()

        if self.mock_mode:
            self._start_mock_download(source, save_path)
            return

        try:
            params = {
                'save_path': save_path,
                'storage_mode': lt.storage_mode_t.storage_mode_sparse,
            }

            if os.path.isfile(source):
                info = lt.torrent_info(source)
                params['ti'] = info
                self.torrent_handle = self.session.add_torrent(params)
            else:
                params['url'] = source
                self.torrent_handle = self.session.add_torrent(params)
                self.torrent_handle.force_dht_announce()

            self.running = True
            self.start_btn.disabled = True
            self.pause_btn.disabled = False
            self.remove_btn.disabled = False
            self.status_label.text = '正在准备下载...'

            self.monitor_thread = threading.Thread(target=self._monitor_download, daemon=True)
            self.monitor_thread.start()

        except Exception as e:
            self._show_error(f'无法添加任务: {str(e)}')

    def _start_mock_download(self, source, save_path):
        """模拟下载模式（无 libtorrent 时使用）"""
        self.running = True
        self.start_btn.disabled = True
        self.pause_btn.disabled = False
        self.remove_btn.disabled = False
        self.status_label.text = '模拟下载中（无libtorrent）'
        self._mock_progress = 0
        self._mock_total = random.randint(100, 500) * 1024 * 1024
        self._mock_files = []
        for i in range(random.randint(2, 5)):
            self._mock_files.append({
                'path': f'file_{i+1}.bin',
                'size': random.randint(50, 200) * 1024 * 1024
            })
        self.monitor_thread = threading.Thread(target=self._monitor_mock_download, daemon=True)
        self.monitor_thread.start()

    def _monitor_mock_download(self):
        """模拟下载监控"""
        while self.running:
            self._mock_progress = min(100, self._mock_progress + random.uniform(0.5, 3.0))
            dl_rate = random.uniform(50, 500)
            ul_rate = random.uniform(10, 50)
            peers = random.randint(5, 50)
            progress = self._mock_progress
            remaining = self._mock_total * (1 - progress / 100)
            eta = remaining / (dl_rate * 1024) if dl_rate > 0 else 0

            Clock.schedule_once(lambda dt: self._update_ui(
                progress, dl_rate, ul_rate, peers,
                self._format_time(eta) if eta > 0 else '未知',
                type('S', (), {'state': 3, 'has_metadata': True})()
            ))

            if progress >= 100:
                Clock.schedule_once(lambda dt: self._download_complete())
                break

            time.sleep(1)
    
    def pause_download(self, instance):
        if self.mock_mode:
            self.running = False
            self.pause_btn.disabled = True
            self.resume_btn.disabled = False
            self.status_label.text = '已暂停'
            return
        if self.torrent_handle:
            self.torrent_handle.pause()
            self.pause_btn.disabled = True
            self.resume_btn.disabled = False
            self.status_label.text = '已暂停'

    def resume_download(self, instance):
        if self.mock_mode:
            self.running = True
            self.pause_btn.disabled = False
            self.resume_btn.disabled = True
            self.status_label.text = '模拟下载中'
            self.monitor_thread = threading.Thread(target=self._monitor_mock_download, daemon=True)
            self.monitor_thread.start()
            return
        if self.torrent_handle:
            self.torrent_handle.resume()
            self.pause_btn.disabled = False
            self.resume_btn.disabled = True
            self.status_label.text = '正在下载...'
    
    def remove_download(self, instance=None):
        if self.mock_mode:
            self.running = False
            self.torrent_handle = None
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
            return
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
                status = self.torrent_handle.status()
                
                if not status.has_metadata:
                    Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', '正在获取元数据...'))
                    time.sleep(1)
                    continue
                
                progress = status.progress * 100
                dl_rate = status.download_rate / 1024
                ul_rate = status.upload_rate / 1024
                peers = status.num_peers
                
                if dl_rate > 0:
                    remaining = status.total_wanted - status.total_wanted_done
                    eta = remaining / (dl_rate * 1024)
                    eta_str = self._format_time(eta)
                else:
                    eta_str = '未知'
                
                # 更新UI
                Clock.schedule_once(lambda dt: self._update_ui(progress, dl_rate, ul_rate, peers, eta_str, status))
                
                if status.is_seeding:
                    Clock.schedule_once(lambda dt: self._download_complete())
                    break
                
                time.sleep(1)
            except Exception as e:
                print(f'监控出错: {e}')
                time.sleep(1)
    
    def _update_ui(self, progress, dl_rate, ul_rate, peers, eta_str, status):
        self.progress_bar.value = progress
        self.progress_label.text = f'{progress:.1f}%'
        self.dl_speed_label.text = f'{dl_rate:.1f} KB/s'
        self.ul_speed_label.text = f'{ul_rate:.1f} KB/s'
        self.peers_label.text = str(peers)
        self.eta_label.text = eta_str
        self.status_label.text = self._get_state_string(status.state)
        
        # 更新文件列表
        if status.has_metadata and len(self.file_list.children) == 0:
            self._update_file_list()
    
    def _update_file_list(self):
        if self.mock_mode:
            self.file_list.clear_widgets()
            for f in self._mock_files:
                file_label = Label(
                    text=f'{f["path"]} ({self._format_size(f["size"])})',
                    size_hint_y=None,
                    height=30,
                    text_size=(None, 30)
                )
                self.file_list.add_widget(file_label)
            return
        if self.torrent_handle and self.torrent_handle.status().has_metadata:
            info = self.torrent_handle.get_torrent_info()
            files = info.files()
            self.file_list.clear_widgets()
            for f in files:
                file_label = Label(
                    text=f'{f.path} ({self._format_size(f.size)})',
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
        
        # 显示完成提示
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
            lt.torrent_status.checking_resume_data: '检查恢复数据'
        }
        return states.get(state, '未知状态')


if __name__ == '__main__':
    BtDownloaderApp().run()
