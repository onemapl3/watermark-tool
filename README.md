<img width="1486" height="955" alt="screenshot" src="https://github.com/user-attachments/assets/1da8df66-4572-4ad6-8d69-07a932893ba8" /># 小红书水印工具

一款为小红书等社交媒体优化的图片水印工具，支持批量添加 PNG 透明水印。

## 功能特性

- **PNG 透明水印** - 支持带透明通道的水印图片
- **自由定位** - X/Y 轴滑块精确控制，支持超出边界（适配有内边距的水印）
- **快捷预设** - 9 个常用位置一键设置（左上、上中、右上、左中、居中、右中、左下、下中、右下）
- **大小透明度可调** - 滑块实时调整，预览即所得
- **横竖图设置自动保存** - 自动识别图片方向（横图/竖图），切换照片时自动保存当前设置，下次遇到同方向图片自动应用
- **选择性导出** - 支持单张导出或批量勾选导出，灵活选择要处理的照片
- **后台队列处理** - 导出时不阻塞操作，可继续浏览和调整其他照片

## 截图
![Uploading screenshot.png…]()



## 安装

### 环境要求

- Python 3.8+
- macOS / Linux / Windows

### 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
python app.py
```

浏览器会自动打开 http://127.0.0.1:5051

### 操作步骤

1. **导入照片** - 点击「打开文件夹」选择照片目录，或「选择图片」导入单张/多张
2. **上传水印** - 点击右侧上传区域选择 PNG 水印图片（透明背景效果最佳）
3. **调整设置** - 拖动滑块调整位置、大小、透明度，或点击快捷位置按钮
4. **选择照片** - 在左侧列表点击复选框勾选要导出的照片
5. **导出** - 点击「导出当前」导出单张，或「导出选中」批量导出

### 小技巧

- **水印有内边距？** X/Y 滑块支持 -20% 到 120%，可以让水印"超出"图片边界
- **横竖图设置不同？** 工具会自动识别并分别记忆横图/竖图的设置
- **批量处理？** 勾选多张后点击「导出选中」，后台队列处理不影响继续操作

## 配置

设置自动保存到 `../output/watermark_config.json`，包括：
- 横图设置（X/Y位置、大小、透明度）
- 竖图设置（X/Y位置、大小、透明度）

## 技术栈

- **后端**: Python + Flask
- **前端**: 原生 HTML/CSS/JavaScript（无需 Node.js）
- **图像处理**: Pillow (PIL)

## 开发

```bash
# 克隆仓库
git clone https://github.com/onemapl3/watermark-tool.git
cd watermark-tool

# 安装依赖
pip install -r requirements.txt

# 运行
python app.py
```

默认端口 5051，如需修改请编辑文件末尾的 `port` 变量。

## 许可证

[MIT License](LICENSE)

## 相关项目

- [stitch-tool](https://github.com/onemapl3/stitch-tool) - 小红书横图拼接工具

## 致谢

本项目使用 [Claude Code](https://claude.ai/claude-code) 辅助开发。
