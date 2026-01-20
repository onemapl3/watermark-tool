#!/usr/bin/env python3
"""
水印工具 - Web版
支持选择性导出、单张导出、后台队列处理
"""

import os
import io
import json
import base64
import subprocess
import threading
import time
import uuid
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
from PIL import Image

app = Flask(__name__)

CONFIG_FILE = Path(__file__).parent.parent / 'output' / 'watermark_config.json'
export_tasks = {}

default_config = {
    'landscape': {'x': 95, 'y': 95, 'size': 15, 'opacity': 80},
    'portrait': {'x': 95, 'y': 95, 'size': 12, 'opacity': 80}
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return default_config.copy()

def save_config(config):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <title>水印工具</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 15px 0 20px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 20px;
        }
        .header h1 {
            font-size: 22px; font-weight: 600;
            background: linear-gradient(90deg, #f093fb 0%, #f5576c 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .header-actions { display: flex; gap: 10px; }
        .btn {
            padding: 8px 16px; border: none; border-radius: 8px; font-size: 13px;
            font-weight: 500; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 6px;
        }
        .btn-secondary { background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.15); }
        .btn-secondary:hover { background: rgba(255,255,255,0.15); }
        .btn-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .btn-success { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; }
        .btn:disabled { opacity: 0.4; cursor: not-allowed; }

        .main-layout { display: grid; grid-template-columns: 280px 1fr 300px; gap: 20px; }

        /* 左侧缩略图列表 */
        .thumb-panel {
            background: rgba(255,255,255,0.03); border-radius: 12px; padding: 15px;
            border: 1px solid rgba(255,255,255,0.08); max-height: calc(100vh - 150px); overflow-y: auto;
        }
        .thumb-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .thumb-header span { font-size: 13px; color: #888; }
        .thumb-actions { display: flex; gap: 8px; }
        .thumb-actions button {
            padding: 4px 10px; font-size: 11px; background: rgba(255,255,255,0.1);
            border: none; border-radius: 4px; color: #aaa; cursor: pointer;
        }
        .thumb-actions button:hover { background: rgba(255,255,255,0.2); color: #fff; }

        .thumb-grid { display: flex; flex-direction: column; gap: 8px; }
        .thumb-item {
            display: flex; align-items: center; gap: 10px; padding: 8px;
            background: rgba(255,255,255,0.02); border-radius: 8px; cursor: pointer;
            border: 2px solid transparent; transition: all 0.2s;
        }
        .thumb-item:hover { background: rgba(255,255,255,0.05); }
        .thumb-item.viewing { border-color: rgba(102, 126, 234, 0.5); background: rgba(102, 126, 234, 0.1); }
        .thumb-item.selected .thumb-checkbox { background: #38ef7d; border-color: #38ef7d; }
        .thumb-item.selected .thumb-checkbox::after {
            content: '✓'; color: #000; font-size: 10px; font-weight: bold;
        }
        .thumb-checkbox {
            width: 18px; height: 18px; border: 2px solid #555; border-radius: 4px;
            display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .thumb-img { width: 50px; height: 50px; object-fit: cover; border-radius: 4px; }
        .thumb-name { flex: 1; font-size: 11px; color: #aaa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .thumb-badge {
            font-size: 9px; padding: 2px 6px; border-radius: 3px;
        }
        .thumb-badge.landscape { background: rgba(102, 126, 234, 0.3); color: #667eea; }
        .thumb-badge.portrait { background: rgba(245, 87, 108, 0.3); color: #f5576c; }

        /* 中间预览区 */
        .preview-panel {
            background: rgba(255,255,255,0.03); border-radius: 12px; padding: 15px;
            border: 1px solid rgba(255,255,255,0.08); display: flex; flex-direction: column;
        }
        .preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .preview-title { font-size: 13px; color: #888; }
        .preview-container {
            flex: 1; background: #000; border-radius: 8px; display: flex;
            align-items: center; justify-content: center; min-height: 400px; position: relative;
        }
        .preview-placeholder { color: #444; text-align: center; }
        #previewCanvas { max-width: 100%; max-height: 60vh; }
        .preview-actions { display: flex; justify-content: center; gap: 10px; margin-top: 12px; }

        /* 右侧设置 */
        .settings-panel {
            background: rgba(255,255,255,0.03); border-radius: 12px; padding: 15px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .settings-title { font-size: 13px; color: #888; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.08); }
        .setting-group { margin-bottom: 18px; }
        .setting-label { font-size: 12px; color: #666; margin-bottom: 8px; display: flex; justify-content: space-between; }
        .setting-value { color: #fff; }
        .watermark-upload {
            border: 2px dashed rgba(255,255,255,0.15); border-radius: 8px; padding: 20px;
            text-align: center; cursor: pointer; margin-bottom: 12px;
        }
        .watermark-upload:hover { border-color: rgba(255,255,255,0.3); }
        .watermark-upload.has-image { border-style: solid; border-color: rgba(56, 239, 125, 0.5); }
        .watermark-preview { max-width: 100%; max-height: 60px; margin-top: 8px; }
        input[type="range"] {
            width: 100%; height: 4px; border-radius: 2px; background: rgba(255,255,255,0.1);
            -webkit-appearance: none; outline: none;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); cursor: pointer;
        }
        .position-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
        .position-btn {
            padding: 8px 4px; border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
            background: transparent; color: #888; font-size: 11px; cursor: pointer;
        }
        .position-btn:hover { border-color: rgba(255,255,255,0.3); color: #fff; }

        /* 任务队列 */
        .task-queue { position: fixed; bottom: 20px; right: 20px; width: 300px; z-index: 1000; }
        .task-item {
            background: rgba(20, 20, 40, 0.95); border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px; padding: 12px; margin-bottom: 8px; backdrop-filter: blur(10px);
        }
        .task-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .task-title { font-size: 12px; }
        .task-status { font-size: 10px; padding: 2px 8px; border-radius: 8px; }
        .task-status.processing { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
        .task-status.done { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .task-status.error { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        .task-progress { height: 3px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; }
        .task-progress-bar { height: 100%; background: linear-gradient(90deg, #f093fb, #f5576c); transition: width 0.3s; }
        .task-info { font-size: 10px; color: #666; margin-top: 6px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>水印工具</h1>
            <div class="header-actions">
                <input type="file" id="folderInput" webkitdirectory style="display:none" onchange="loadFolder(this)">
                <input type="file" id="fileInput" multiple accept="image/*" style="display:none" onchange="loadFiles(this)">
                <button class="btn btn-secondary" onclick="document.getElementById('folderInput').click()">📁 打开文件夹</button>
                <button class="btn btn-secondary" onclick="document.getElementById('fileInput').click()">🖼 选择图片</button>
            </div>
        </div>

        <div class="main-layout">
            <!-- 左侧：缩略图列表 -->
            <div class="thumb-panel">
                <div class="thumb-header">
                    <span>照片列表 (<span id="selectedCount">0</span>/<span id="totalCount">0</span>)</span>
                    <div class="thumb-actions">
                        <button onclick="selectAll()">全选</button>
                        <button onclick="selectNone()">全不选</button>
                    </div>
                </div>
                <div class="thumb-grid" id="thumbGrid"></div>
            </div>

            <!-- 中间：预览 -->
            <div class="preview-panel">
                <div class="preview-header">
                    <span class="preview-title">预览</span>
                    <span id="orientationBadge" style="font-size:11px;"></span>
                </div>
                <div class="preview-container">
                    <div class="preview-placeholder" id="placeholder">选择照片开始</div>
                    <canvas id="previewCanvas" style="display:none;"></canvas>
                </div>
                <div class="preview-actions">
                    <button class="btn btn-primary" onclick="exportCurrent()" id="exportCurrentBtn" disabled>导出当前</button>
                    <button class="btn btn-success" onclick="exportSelected()" id="exportSelectedBtn" disabled>导出选中 (<span id="exportCount">0</span>)</button>
                </div>
                <div style="margin-top:10px;">
                    <div style="display:flex;align-items:center;gap:8px;background:rgba(255,255,255,0.05);padding:8px 12px;border-radius:6px;">
                        <span style="font-size:11px;color:#666;">导出到:</span>
                        <input type="text" id="exportPath" style="flex:1;background:transparent;border:none;color:#fff;font-size:12px;outline:none;" placeholder="选择文件夹后自动设置">
                    </div>
                </div>
            </div>

            <!-- 右侧：设置 -->
            <div class="settings-panel">
                <div class="settings-title">水印设置</div>

                <div class="setting-group">
                    <div class="setting-label">水印图片</div>
                    <div class="watermark-upload" id="watermarkUpload" onclick="document.getElementById('watermarkInput').click()">
                        <input type="file" id="watermarkInput" accept="image/png" style="display:none" onchange="loadWatermark(this)">
                        <div id="watermarkPlaceholder" style="color:#666;font-size:12px;">点击上传PNG水印</div>
                        <img id="watermarkPreview" class="watermark-preview" style="display:none;">
                    </div>
                </div>

                <div class="setting-group">
                    <div class="setting-label"><span>X 位置</span><span class="setting-value"><span id="xValue">95</span>%</span></div>
                    <input type="range" id="xSlider" min="-20" max="120" value="95" oninput="updateSetting('x', this.value)">
                </div>

                <div class="setting-group">
                    <div class="setting-label"><span>Y 位置</span><span class="setting-value"><span id="yValue">95</span>%</span></div>
                    <input type="range" id="ySlider" min="-20" max="120" value="95" oninput="updateSetting('y', this.value)">
                </div>

                <div class="setting-group">
                    <div class="setting-label">快捷位置</div>
                    <div class="position-grid">
                        <button class="position-btn" onclick="setPos(5,5)">左上</button>
                        <button class="position-btn" onclick="setPos(50,5)">上中</button>
                        <button class="position-btn" onclick="setPos(95,5)">右上</button>
                        <button class="position-btn" onclick="setPos(5,50)">左中</button>
                        <button class="position-btn" onclick="setPos(50,50)">居中</button>
                        <button class="position-btn" onclick="setPos(95,50)">右中</button>
                        <button class="position-btn" onclick="setPos(5,95)">左下</button>
                        <button class="position-btn" onclick="setPos(50,95)">下中</button>
                        <button class="position-btn" onclick="setPos(95,95)">右下</button>
                    </div>
                </div>

                <div class="setting-group">
                    <div class="setting-label"><span>大小</span><span class="setting-value"><span id="sizeValue">15</span>%</span></div>
                    <input type="range" id="sizeSlider" min="3" max="50" value="15" oninput="updateSetting('size', this.value)">
                </div>

                <div class="setting-group">
                    <div class="setting-label"><span>透明度</span><span class="setting-value"><span id="opacityValue">80</span>%</span></div>
                    <input type="range" id="opacitySlider" min="10" max="100" value="80" oninput="updateSetting('opacity', this.value)">
                </div>

                <div style="font-size:10px;color:#555;text-align:center;margin-top:10px;">
                    横图/竖图设置分别保存
                </div>
            </div>
        </div>
    </div>

    <div class="task-queue" id="taskQueue"></div>

    <script>
        let photos = [];
        let currentIdx = -1;
        let watermarkImg = null;
        let watermarkBase64 = null;
        let config = {{ config | tojson }};
        let sourceDir = '';

        const canvas = document.getElementById('previewCanvas');
        const ctx = canvas.getContext('2d');

        async function loadFolder(input) {
            const files = Array.from(input.files).filter(f => /\\.(jpg|jpeg|png|heic)$/i.test(f.name));
            if (!files.length) { alert('未找到图片'); return; }

            if (files[0].webkitRelativePath) {
                const folderName = files[0].webkitRelativePath.split('/')[0];
                const resp = await fetch('/set_source', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({folder_name: folderName})
                });
                const data = await resp.json();
                if (data.full_path) {
                    sourceDir = data.full_path;
                    document.getElementById('exportPath').value = sourceDir + '/watermarked';
                }
            }
            initPhotos(files);
        }

        function loadFiles(input) {
            const files = Array.from(input.files).filter(f => /\\.(jpg|jpeg|png|heic)$/i.test(f.name));
            if (!files.length) return;
            initPhotos(files);
        }

        function initPhotos(files) {
            photos = files.map(f => ({
                file: f,
                name: f.name,
                url: URL.createObjectURL(f),
                selected: true,
                orientation: null,
                img: null
            }));
            currentIdx = 0;
            renderThumbList();
            loadCurrentPhoto();
            updateCounts();
        }

        function renderThumbList() {
            const grid = document.getElementById('thumbGrid');
            grid.innerHTML = '';
            photos.forEach((p, i) => {
                const div = document.createElement('div');
                div.className = 'thumb-item' + (p.selected ? ' selected' : '') + (i === currentIdx ? ' viewing' : '');
                div.innerHTML = `
                    <div class="thumb-checkbox" data-idx="${i}"></div>
                    <img class="thumb-img" src="${p.url}">
                    <span class="thumb-name">${p.name}</span>
                `;
                // 复选框点击
                div.querySelector('.thumb-checkbox').onclick = (e) => {
                    e.stopPropagation();
                    p.selected = !p.selected;
                    div.classList.toggle('selected', p.selected);
                    updateCounts();
                };
                // 整行点击预览
                div.onclick = () => viewPhoto(i);
                grid.appendChild(div);
            });
            document.getElementById('totalCount').textContent = photos.length;
        }

        function viewPhoto(idx) {
            if (currentIdx >= 0 && photos[currentIdx]?.orientation) {
                saveCurrentSettings();
            }
            currentIdx = idx;
            document.querySelectorAll('.thumb-item').forEach((el, i) => el.classList.toggle('viewing', i === idx));
            loadCurrentPhoto();
        }

        function loadCurrentPhoto() {
            if (currentIdx < 0 || !photos[currentIdx]) return;
            const photo = photos[currentIdx];
            const img = new Image();
            img.onload = () => {
                photo.img = img;
                photo.orientation = img.width > img.height ? 'landscape' : 'portrait';
                loadSettingsForOrientation(photo.orientation);
                renderPreview();
                document.getElementById('exportCurrentBtn').disabled = false;
                document.getElementById('orientationBadge').textContent = photo.orientation === 'landscape' ? '横图' : '竖图';
            };
            img.src = photo.url;
            document.getElementById('placeholder').style.display = 'none';
            canvas.style.display = 'block';
        }

        function loadSettingsForOrientation(orientation) {
            const s = config[orientation];
            document.getElementById('xSlider').value = s.x;
            document.getElementById('xValue').textContent = s.x;
            document.getElementById('ySlider').value = s.y;
            document.getElementById('yValue').textContent = s.y;
            document.getElementById('sizeSlider').value = s.size;
            document.getElementById('sizeValue').textContent = s.size;
            document.getElementById('opacitySlider').value = s.opacity;
            document.getElementById('opacityValue').textContent = s.opacity;
        }

        function saveCurrentSettings() {
            const photo = photos[currentIdx];
            if (!photo?.orientation) return;
            config[photo.orientation] = {
                x: parseInt(document.getElementById('xSlider').value),
                y: parseInt(document.getElementById('ySlider').value),
                size: parseInt(document.getElementById('sizeSlider').value),
                opacity: parseInt(document.getElementById('opacitySlider').value)
            };
            fetch('/save_config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(config)
            });
        }

        function loadWatermark(input) {
            const file = input.files[0];
            if (!file) return;
            const img = new Image();
            img.onload = () => {
                watermarkImg = img;
                document.getElementById('watermarkPreview').src = img.src;
                document.getElementById('watermarkPreview').style.display = 'block';
                document.getElementById('watermarkPlaceholder').style.display = 'none';
                document.getElementById('watermarkUpload').classList.add('has-image');
                const c = document.createElement('canvas');
                c.width = img.width; c.height = img.height;
                c.getContext('2d').drawImage(img, 0, 0);
                watermarkBase64 = c.toDataURL('image/png');
                renderPreview();
                updateCounts(); // 启用导出按钮
            };
            img.src = URL.createObjectURL(file);
        }

        function renderPreview() {
            const photo = photos[currentIdx];
            if (!photo?.img) return;
            const img = photo.img;
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);

            if (watermarkImg) {
                const x = parseInt(document.getElementById('xSlider').value);
                const y = parseInt(document.getElementById('ySlider').value);
                const size = parseInt(document.getElementById('sizeSlider').value);
                const opacity = parseInt(document.getElementById('opacitySlider').value) / 100;

                const wmW = img.width * size / 100;
                const wmH = wmW * (watermarkImg.height / watermarkImg.width);
                const maxX = img.width - wmW;
                const maxY = img.height - wmH;
                const posX = maxX * x / 100;
                const posY = maxY * y / 100;

                ctx.globalAlpha = opacity;
                ctx.drawImage(watermarkImg, posX, posY, wmW, wmH);
                ctx.globalAlpha = 1;
            }
        }

        function updateSetting(key, value) {
            document.getElementById(key + 'Value').textContent = value;
            renderPreview();
        }

        function setPos(x, y) {
            document.getElementById('xSlider').value = x;
            document.getElementById('xValue').textContent = x;
            document.getElementById('ySlider').value = y;
            document.getElementById('yValue').textContent = y;
            renderPreview();
        }

        function selectAll() {
            photos.forEach(p => p.selected = true);
            document.querySelectorAll('.thumb-item').forEach(el => el.classList.add('selected'));
            updateCounts();
        }

        function selectNone() {
            photos.forEach(p => p.selected = false);
            document.querySelectorAll('.thumb-item').forEach(el => el.classList.remove('selected'));
            updateCounts();
        }

        function updateCounts() {
            const count = photos.filter(p => p.selected).length;
            document.getElementById('selectedCount').textContent = count;
            document.getElementById('exportCount').textContent = count;
            document.getElementById('exportSelectedBtn').disabled = count === 0 || !watermarkBase64;
        }

        // 导出当前单张
        async function exportCurrent() {
            if (!watermarkBase64 || currentIdx < 0) {
                alert('请先上传水印图片'); return;
            }
            saveCurrentSettings();
            const photo = photos[currentIdx];
            startExport([photo], '导出当前');
        }

        // 导出选中的
        async function exportSelected() {
            if (!watermarkBase64) {
                alert('请先上传水印图片'); return;
            }
            saveCurrentSettings();
            const selected = photos.filter(p => p.selected);
            if (!selected.length) {
                alert('请选择要导出的照片'); return;
            }
            startExport(selected, '导出选中');
        }

        async function startExport(photoList, taskName) {
            let exportPath = document.getElementById('exportPath').value.trim();
            if (!exportPath) {
                exportPath = sourceDir ? (sourceDir + '/watermarked') : '';
            }

            const formData = new FormData();
            formData.append('export_path', exportPath);
            formData.append('watermark', watermarkBase64);
            formData.append('config', JSON.stringify(config));
            formData.append('count', photoList.length);

            photoList.forEach((p, i) => {
                formData.append('photo_' + i, p.file);
            });

            try {
                const resp = await fetch('/export_start', { method: 'POST', body: formData });
                const result = await resp.json();
                if (result.task_id) {
                    addTaskUI(result.task_id, taskName, photoList.length);
                    pollTask(result.task_id);
                } else {
                    alert('启动失败: ' + (result.error || '未知错误'));
                }
            } catch (e) {
                alert('导出失败: ' + e.message);
            }
        }

        function addTaskUI(taskId, name, total) {
            const queue = document.getElementById('taskQueue');
            const div = document.createElement('div');
            div.className = 'task-item';
            div.id = 'task-' + taskId;
            div.innerHTML = `
                <div class="task-header">
                    <span class="task-title">${name}</span>
                    <span class="task-status processing">处理中</span>
                </div>
                <div class="task-progress"><div class="task-progress-bar" style="width:0%"></div></div>
                <div class="task-info">0 / ${total}</div>
            `;
            queue.appendChild(div);
        }

        async function pollTask(taskId) {
            try {
                const resp = await fetch('/task_status/' + taskId);
                const data = await resp.json();
                const el = document.getElementById('task-' + taskId);
                if (!el) return;

                const pct = Math.round((data.current / data.total) * 100);
                el.querySelector('.task-progress-bar').style.width = pct + '%';
                el.querySelector('.task-info').textContent = data.message || (data.current + ' / ' + data.total);

                if (data.status === 'done') {
                    el.querySelector('.task-status').className = 'task-status done';
                    el.querySelector('.task-status').textContent = '完成';
                    setTimeout(() => el.remove(), 4000);
                } else if (data.status === 'error') {
                    el.querySelector('.task-status').className = 'task-status error';
                    el.querySelector('.task-status').textContent = '失败';
                } else {
                    setTimeout(() => pollTask(taskId), 300);
                }
            } catch (e) {
                console.error(e);
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, config=load_config())

@app.route('/set_source', methods=['POST'])
def set_source():
    data = request.get_json()
    folder_name = data.get('folder_name', '')
    for base in [Path.home() / 'Pictures', Path.home() / 'Desktop', Path.home() / 'Downloads', Path.home()]:
        candidate = base / folder_name
        if candidate.exists():
            return jsonify({'full_path': str(candidate)})
    return jsonify({'full_path': str(Path.home() / 'Desktop' / folder_name)})

@app.route('/save_config', methods=['POST'])
def save_config_route():
    save_config(request.get_json())
    return jsonify({'success': True})

@app.route('/export_start', methods=['POST'])
def export_start():
    try:
        count = int(request.form.get('count', 0))
        if count == 0:
            return jsonify({'error': '没有照片'})

        export_path = request.form.get('export_path', '').strip()
        if not export_path or export_path == '/watermarked':
            export_path = str(Path.home() / 'Desktop' / 'watermarked')
        print(f"[Export] Received export_path: {export_path}, count: {count}")
        watermark_data = request.form.get('watermark', '')
        cfg = json.loads(request.form.get('config', '{}'))

        temp_dir = Path('/tmp') / f'wm_{uuid.uuid4().hex[:8]}'
        temp_dir.mkdir(parents=True, exist_ok=True)

        photo_paths = []
        for i in range(count):
            f = request.files.get(f'photo_{i}')
            if f:
                p = temp_dir / Path(f.filename).name
                f.save(str(p))
                photo_paths.append(str(p))

        task_id = uuid.uuid4().hex[:10]
        export_tasks[task_id] = {'status': 'processing', 'current': 0, 'total': len(photo_paths), 'message': '准备中...'}

        t = threading.Thread(target=do_export, args=(task_id, photo_paths, export_path, watermark_data, cfg, temp_dir))
        t.daemon = True
        t.start()

        return jsonify({'task_id': task_id})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)})

def do_export(task_id, photo_paths, export_path, watermark_data, cfg, temp_dir):
    try:
        out_dir = Path(export_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Export] Output dir: {out_dir}")

        if watermark_data.startswith('data:'):
            watermark_data = watermark_data.split(',')[1]
        wm = Image.open(io.BytesIO(base64.b64decode(watermark_data))).convert('RGBA')

        exported_count = 0
        for i, p in enumerate(photo_paths):
            try:
                export_tasks[task_id]['current'] = i + 1
                export_tasks[task_id]['message'] = f'{i+1}/{len(photo_paths)} {Path(p).name}'

                img = Image.open(p).convert('RGBA')
                orient = 'landscape' if img.width > img.height else 'portrait'
                s = cfg.get(orient, cfg.get('landscape', {}))

                sz = s.get('size', 15) / 100
                op = s.get('opacity', 80) / 100
                xp = s.get('x', 95) / 100
                yp = s.get('y', 95) / 100

                wm_w = int(img.width * sz)
                wm_h = int(wm_w * wm.height / wm.width)
                wm_r = wm.resize((wm_w, wm_h), Image.Resampling.LANCZOS)

                if op < 1:
                    a = wm_r.split()[3].point(lambda x: int(x * op))
                    wm_r.putalpha(a)

                x = int((img.width - wm_w) * xp)
                y = int((img.height - wm_h) * yp)
                img.paste(wm_r, (x, y), wm_r)

                # 文件名：如果已存在则加时间戳
                base_name = Path(p).stem
                ext = Path(p).suffix or '.jpg'
                out_file = out_dir / f'wm_{base_name}{ext}'
                if out_file.exists():
                    ts = int(time.time() * 1000) % 100000
                    out_file = out_dir / f'wm_{base_name}_{ts}{ext}'

                img.convert('RGB').save(str(out_file), quality=95)
                exported_count += 1
                print(f"[Export] Saved: {out_file}")

            except Exception as e:
                print(f"[Export] Error processing {p}: {e}")

        export_tasks[task_id]['status'] = 'done'
        export_tasks[task_id]['message'] = f'完成 {exported_count} 张'
        subprocess.run(['open', str(out_dir)])

        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        time.sleep(30)
        export_tasks.pop(task_id, None)

    except Exception as e:
        import traceback; traceback.print_exc()
        export_tasks[task_id]['status'] = 'error'
        export_tasks[task_id]['message'] = str(e)

@app.route('/task_status/<task_id>')
def task_status(task_id):
    return jsonify(export_tasks.get(task_id, {'status': 'not_found'}))

if __name__ == '__main__':
    import webbrowser
    port = 5051
    threading.Timer(1.0, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    print(f'\n水印工具: http://127.0.0.1:{port}\n')
    app.run(port=port, debug=False, threaded=True)
