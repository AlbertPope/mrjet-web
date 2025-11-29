// 更新状态
function updateStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            // 更新状态显示
            document.querySelector('.status-item:nth-child(1) .value').textContent =
                data.is_running ? '运行中' : '已停止';
            document.querySelector('.status-item:nth-child(1) .value').className =
                'value ' + (data.is_running ? 'running' : 'stopped');

            document.querySelector('.status-item:nth-child(2) .value').textContent =
                data.current_task ? data.current_task.url : '无';

            document.querySelector('.status-item:nth-child(3) .value').textContent =
                data.task_count;

            // 更新进度显示
            const progressSection = document.querySelector('.progress-section');
            if (data.current_progress && data.current_task) {
                if (!progressSection) {
                    // 创建进度显示区域
                    const statusGrid = document.querySelector('.status-grid');
                    const newProgressSection = document.createElement('div');
                    newProgressSection.className = 'progress-section';
                    newProgressSection.innerHTML = `
                        <h3>当前进度</h3>
                        <div class="progress-info">
                            <span class="progress-stage">${data.current_progress.stage}</span>
                            <span class="progress-percent">${data.current_progress.percent}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${data.current_progress.percent}%;"></div>
                        </div>
                        <div class="progress-detail">
                            ${data.current_progress.raw_line}
                        </div>
                    `;
                    statusGrid.parentNode.insertBefore(newProgressSection, statusGrid.nextSibling);
                } else {
                    // 更新现有进度显示
                    document.querySelector('.progress-stage').textContent = data.current_progress.stage;
                    document.querySelector('.progress-percent').textContent = data.current_progress.percent + '%';
                    document.querySelector('.progress-fill').style.width = data.current_progress.percent + '%';
                    document.querySelector('.progress-detail').textContent = data.current_progress.raw_line;
                }
            } else if (progressSection) {
                // 移除进度显示
                progressSection.remove();
            }

            // 更新控制按钮
            const controlDiv = document.querySelector('.control-buttons');
            if (data.is_running) {
                controlDiv.innerHTML = `
                    <button onclick="stopDownload()" class="btn btn-stop">停止下载</button>
                    <a href="/tasks" class="btn btn-secondary">管理任务</a>
                `;
            } else {
                controlDiv.innerHTML = `
                    <button onclick="startDownload()" class="btn btn-start">开始下载</button>
                    <a href="/tasks" class="btn btn-secondary">管理任务</a>
                `;
            }
        });
}

// 开始下载
function startDownload() {
    fetch('/api/start_download', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateStatus();
            }
        });
}

// 停止下载
function stopDownload() {
    fetch('/api/stop_download', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateStatus();
            }
        });
}

// 添加任务
document.getElementById('taskForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);

    fetch('/api/add_task', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('任务添加成功!');
            this.reset();
            updateStatus();
        } else {
            alert('错误: ' + data.error);
        }
    });
});

// 保存配置
document.getElementById('configForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const formData = new FormData(this);

    fetch('/api/update_config', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('配置保存成功!');
        } else {
            alert('保存配置时出错');
        }
    });
});

// 每5秒更新一次状态
setInterval(updateStatus, 3000);