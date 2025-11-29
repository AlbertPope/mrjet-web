function removeTask(index) {
    if (confirm('确定要删除这个任务吗？')) {
        const formData = new FormData();
        formData.append('index', index);

        fetch('/api/remove_task', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('任务删除成功!');
                location.reload();
            } else {
                alert('错误: ' + data.error);
            }
        });
    }
}

// 每10秒刷新页面以更新状态
setInterval(() => {
    location.reload();
}, 10000);