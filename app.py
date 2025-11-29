import json
import logging
import os
import random
import threading
import time
from datetime import datetime

from flask import Flask, render_template, jsonify, request

try:
    from mrjet.downloader import MovieDownloader
    USE_CUSTOM_DOWNLOADER = True
except ImportError:
    USE_CUSTOM_DOWNLOADER = False
    logging.warning("Can't import custom downloader, use mrjet command.")

app = Flask(__name__)

# define config file path
CONFIG_FILE = 'config.json'
TASK_QUEUE_FILE = 'task_queue.txt'

# defualt config
DEFAULT_CONFIG = {
    'download_dir': './downloads',
    'min_interval': 7,
    'max_interval': 15,
    'resolution': ''
}

class DownloadManager:
    def __init__(self):
        self.tasks = []
        self.config = DEFAULT_CONFIG.copy()
        self.current_task = None
        self.is_running = False
        self.worker_thread = None
        self.downloader = None
        self.progress_lock = threading.Lock()

        if USE_CUSTOM_DOWNLOADER:
            try:
                self.downloader = MovieDownloader()
                logging.info("Init custom downloader.")
            except Exception as e:
                logging.error(f"Failed to init custom downloader: {e}")
                self.downloader = None

        self.load_config()
        self.load_tasks()

    def load_config(self):
        """load config file"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8')as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            else:
                self.save_config()
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            self.config = DEFAULT_CONFIG.copy()

    def save_config(self):
        """save config file"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def load_tasks(self):
        """load task queue"""
        self.tasks = []
        try:
            if os.path.exists(TASK_QUEUE_FILE):
                with open(TASK_QUEUE_FILE, 'r', encoding='utf-8') as f:
                    for line in f:
                        url = line.strip()
                        if url and not url.startswith("#"):
                            self.tasks.append({
                                'url': url,
                                'added_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'status': "Waitting..."
                            })
        except Exception as e:
            logging.error(f"Failed to load task queue: {e}")
            self.tasks = []

    def save_tasks(self):
        """save queue to file"""
        try:
            with open(TASK_QUEUE_FILE, 'w', encoding='utf-8') as f:
                for task in self.tasks:
                    f.write(task['url'] + '\n')
        except Exception as e:
            logging.error(f"Failed to save task queue: {e}")

    def add_task(self, url):
        """add download task"""
        task = {
            'url': url,
            'added_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Waitting...'
        }
        self.tasks.append(task)
        self.save_tasks()
        return task

    def remove_task(self, task_index):
        """remove task"""
        if 0 <= task_index < len(self.tasks):
            removed_task = self.tasks.pop(task_index)
            self.save_tasks()
            return removed_task
        return None

    def start_download_worker(self):
        """start download thread"""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = threading.Thread(target=self._download_worker)
            self.worker_thread.daemon = True
            self.worker_thread.start()

    def stop_download_worker(self):
        """stop download thread"""
        self.is_running = False

    def _progress_callback(self, progress_data):
        if self.current_task:
            with self.progress_lock:
                self.current_task['progress'] = progress_data
            logging.info(f"进度更新: {progress_data['stage']} - {progress_data['percent']}%")

    def _download_task(self, task):
        try:
            os.makedirs(self.config['download_dir'], exist_ok=True)
            with self.progress_lock:
                task['progress'] = {'stage': '准备中', 'percent': 0, 'raw_line': '正在准备下载...'}

            resolution = self.config.get('resolution', '')
            success = self.downloader.download_with_progress(
                url=task['url'],
                output_dir=self.config['download_dir'],
                resolution=resolution,
                progress_callback=self._progress_callback
            )

            return success
        except Exception as e:
            logging.error(f"download failed: {e}")
            with self.progress_lock:
                task['progress'] = {'stage': '失败', 'percent': 0, 'raw_line': f'下载失败: {str(e)}'}
            return False

    def _download_worker(self):
        """下载工作线程"""
        while self.is_running and self.downloader:
            if self.tasks:
                # 获取第一个任务
                task = self.tasks[0]
                with self.progress_lock:
                    task['status'] = '下载中'
                    task['start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.current_task = task

                try:
                    success = self._download_task(task)

                    if success:
                        with self.progress_lock:
                            task['status'] = '已完成'
                            task['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            task['progress'] = {'stage': '完成', 'percent': 100, 'raw_line': '下载完成'}
                        logging.info(f"下载成功: {task['url']}")
                    else:
                        with self.progress_lock:
                            task['status'] = '失败'
                            task['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            task['error'] = "下载失败"
                        logging.error(f"下载失败: {task['url']}")

                except Exception as e:
                    logging.error(f"下载过程异常: {e}")
                    with self.progress_lock:
                        task['status'] = '失败'
                        task['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        task['error'] = str(e)

                # 移除已完成/失败的任务
                if self.tasks and self.tasks[0]['url'] == task['url']:
                    self.tasks.pop(0)
                    self.save_tasks()

                self.current_task = None

                # 如果还有任务，等待随机时间后继续
                if self.tasks:
                    wait_minutes = random.randint(
                        self.config['min_interval'],
                        self.config['max_interval']
                    )
                    logging.info(f"等待 {wait_minutes} 分钟后下载下一个任务")
                    for _ in range(wait_minutes * 60):
                        if not self.is_running:
                            break
                        time.sleep(1)
            else:
                # 没有任务时休眠
                time.sleep(5)

download_manager = DownloadManager()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('download_manager.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


# 添加Flask路由（保持不变）
@app.route('/')
def index():
    """首页"""
    return render_template('task_index.html',
                           config=download_manager.config,
                           current_task=download_manager.current_task,
                           is_running=download_manager.is_running)


@app.route('/tasks')
def tasks():
    """任务管理页面"""
    return render_template('tasks.html',
                           tasks=download_manager.tasks,
                           current_task=download_manager.current_task,
                           is_running=download_manager.is_running)


@app.route('/api/add_task', methods=['POST'])
def api_add_task():
    """添加任务API"""
    url = request.form.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'URL不能为空'})

    # 简单的URL验证
    if not url.startswith(('http://', 'https://')):
        return jsonify({'success': False, 'error': 'URL格式不正确'})

    task = download_manager.add_task(url)
    return jsonify({'success': True, 'task': task})


@app.route('/api/remove_task', methods=['POST'])
def api_remove_task():
    """移除任务API"""
    task_index = request.form.get('task_index', type=int)
    if task_index is None:
        return jsonify({'success': False, 'error': '参数错误'})

    removed_task = download_manager.remove_task(task_index)
    if removed_task:
        return jsonify({'success': True, 'task': removed_task})
    else:
        return jsonify({'success': False, 'error': '任务不存在'})


@app.route('/api/update_config', methods=['POST'])
def api_update_config():
    """更新配置API"""
    download_dir = request.form.get('download_dir', '').strip()
    min_interval = request.form.get('min_interval', type=int)
    max_interval = request.form.get('max_interval', type=int)
    resolution = request.form.get('resolution', '').strip()

    if download_dir:
        download_manager.config['download_dir'] = download_dir

    if min_interval and 1 <= min_interval <= 60:
        download_manager.config['min_interval'] = min_interval

    if max_interval and 1 <= max_interval <= 60:
        download_manager.config['max_interval'] = max_interval

    if resolution:
        download_manager.config['resolution'] = resolution

    # 验证时间间隔
    if download_manager.config['min_interval'] > download_manager.config['max_interval']:
        download_manager.config['min_interval'], download_manager.config['max_interval'] = download_manager.config['max_interval'], download_manager.config['min_interval']

    download_manager.save_config()

    # 确保下载目录存在
    os.makedirs(download_manager.config['download_dir'], exist_ok=True)

    return jsonify({'success': True, 'config': download_manager.config})


@app.route('/api/start_download', methods=['POST'])
def api_start_download():
    """开始下载API"""
    if not download_manager.is_running:
        download_manager.start_download_worker()
    return jsonify({'success': True, 'is_running': download_manager.is_running})


@app.route('/api/stop_download', methods=['POST'])
def api_stop_download():
    """停止下载API"""
    if download_manager.is_running:
        download_manager.stop_download_worker()
    return jsonify({'success': True, 'is_running': download_manager.is_running})


@app.route('/api/status')
def api_status():
    """获取状态API"""
    current_progress = None
    if download_manager.current_task and 'progress' in download_manager.current_task:
        current_progress = download_manager.current_task['progress']

    return jsonify({
        'is_running': download_manager.is_running,
        'current_task': download_manager.current_task,
        'task_count': len(download_manager.tasks),
        'config': download_manager.config,
        'current_progress': current_progress
    })


if __name__ == '__main__':
    # 确保下载目录存在
    os.makedirs(download_manager.config['download_dir'], exist_ok=True)

    # 启动应用
    app.run(debug=True, host='0.0.0.0', port=5000)