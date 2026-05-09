# TubeMoCap

**EN** | [中文](#中文说明)

An open-source motion capture dataset collection tool with a PyQt5 GUI.  
Record face tracking and body pose via MediaPipe (camera) as labeled, versioned datasets — multiple takes per motion label, visual comparison chart, ML-ready export, and Live2D avatar preview/replay built in.

---

## Features

- **Motion Library** — Create, rename, delete named motion labels (e.g. "smile", "nod", "wave")
- **Multiple Takes** — Record as many takes per motion as you need; each is stored independently
- **Built-in Dual Tracking** — Face + body pose via MediaPipe, using your camera directly (no external tools required)
- **Live2D Real-time Preview** — See the bundled Teto model respond to your face in real-time
- **Live2D Replay** — Replay a recorded take on the Live2D model to review your performance
- **Take Comparison Chart** — Matplotlib overlay of any face parameter across selected takes
- **Export** — CSV, NumPy `.npz`, or raw JSON
- **OpenSeeFace Support** — Optional UDP fallback for OpenSeeFace face tracking
- **Dark UI** — Dark theme throughout

---

## Requirements

- Python 3.10+
- A camera (built-in webcam or USB camera)

---

## Quick Start

```bash
# 1. Clone this repository
git clone https://github.com/Wendell-Guan/TubeMoCap.git
cd TubeMoCap

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate.bat     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch
python main.py
```

> **macOS camera permission:** On first run, click **启动** (Start) next to the face or body camera row.  
> macOS will request camera access — click **Allow**.  
> If you accidentally denied it, go to:  
> **System Settings → Privacy & Security → Camera → enable your terminal app (Terminal / iTerm)**

> **macOS Qt plugin issue:** If you see a "cocoa plugin not found" error, launch with:
> ```bash
> QT_QPA_PLATFORM_PLUGIN_PATH=venv/lib/python3.10/site-packages/PyQt5/Qt5/plugins python main.py
> ```

---

## Usage Guide

### 1 — Create a Motion Label

In the **动作库** (Motion Library) panel on the left, click **+**, type a name, press OK.  
The motion appears in the list with take counter `(0)`.

### 2 — Start Tracking

1. Select a motion in the left panel
2. In the **录制 & Takes** (Record & Takes) tab on the right:
   - Choose **Mode**: face only / body only / face + body
   - Select camera index for face and/or body (default: camera 0)
   - Click **启动** (Start) next to each camera row
   - Status bar shows: `脸部 ● 已连接` / `身体 ● 已连接` when tracking is active

> **Tip:** If camera 0 is occupied (e.g. by OBS Virtual Camera), try camera 1 or 2.

### 3 — Record a Take

1. Click **● 开始录制** (Start Recording) — timer starts
2. Perform your motion
3. Click **⏹ 停止录制** (Stop Recording) — take is saved automatically

### 4 — Live2D Preview

Click **🎭 打开 Teto 实时预览** to open the floating Live2D window.  
The bundled Teto model responds to your face in real-time.  
Click **换模型** (Change Model) to load a different `.model3.json` file.

### 5 — Replay on Live2D

Select a take → click **▶ 回放到 Teto** (Replay to Teto).  
The Live2D model will replay the recorded facial expressions from that take.

### 6 — Compare Takes

Switch to the **对比图表** (Compare Chart) tab, select takes with checkboxes,  
choose a face parameter from the dropdown, click **刷新图表** (Refresh Chart).

### 7 — Export

Select a take → **⬇ 导出** (Export) → choose CSV / NPZ / JSON.

---

## Face Tracking Backends

### Built-in (MediaPipe) — Default

Face tracking uses MediaPipe FaceLandmarker with blendshapes. Just select your camera and click **启动**.  
No external software required.

### OpenSeeFace (Optional)

TubeMoCap also listens on UDP port `11573` for OpenSeeFace packets.  
If you prefer OpenSeeFace, run it separately:

```bash
git clone https://github.com/emilianavt/OpenSeeFace.git
cd OpenSeeFace
pip install onnxruntime opencv-python pillow numpy
python facetracker.py -c 0 -W 640 -H 480 --model 3
```

---

## Project Structure

```
TubeMoCap/
├── main.py                  Entry point
├── requirements.txt
├── README.md
├── LICENSE
├── core/
│   ├── receiver.py          Face receiver (MediaPipe camera + OpenSeeFace UDP)
│   ├── body_receiver.py     MediaPipe body pose receiver
│   ├── recorder.py          Frame accumulation + take saving
│   └── dataset.py           Motion + take CRUD, export helpers
├── ui/
│   ├── main_window.py       Main PyQt5 window + status bar
│   ├── motion_panel.py      Left panel: motion list + CRUD
│   ├── take_panel.py        Right panel: takes table + recording controls
│   ├── compare_widget.py    Matplotlib comparison chart tab
│   ├── live2d_preview.py    Floating Live2D preview window
│   └── opengl_canvas.py     Base QOpenGLWidget canvas
├── models/
│   ├── pose_landmarker_full.task    MediaPipe body pose model
│   └── face_landmarker.task         MediaPipe face landmarker model
├── resources/
│   └── live2d/
│       └── 重音テト/         Bundled Live2D model (Kasane Teto)
└── dataset/                 Your recorded data (gitignored)
```

---

## Data Format

### `dataset/motions.json`

```json
{
  "version": "1.0",
  "motions": [
    { "id": "uuid", "name": "smile", "created_at": "..." }
  ]
}
```

### `dataset/takes/{motion_id}/{index:03d}.json`

- `face_frames`: `[{t, pitch, yaw, roll, eye_l, eye_r, brow_l, brow_r, mouth_open, mouth_form, conf}, ...]`
- `body_frames`: `[{t, shoulder_width_ref, landmarks: {name: [x,y,z,vis]}}, ...]`

---

## License

MIT License — see [LICENSE](LICENSE)

The bundled Kasane Teto (重音テト) Live2D model is property of its respective creators.  
It is included for demonstration purposes only.

---

## 中文说明

TubeMoCap 是一个开源动作捕捉数据集采集工具，支持面部和身体双通道追踪。

### 功能特点

| 功能 | 说明 |
|------|------|
| 动作库 | 新建/重命名/删除动作标签 |
| 内置脸部追踪 | 使用 MediaPipe FaceLandmarker，无需外部软件 |
| 身体追踪 | 使用 MediaPipe Pose，直接调用摄像头 |
| 录制 | 支持仅脸部/仅身体/两者同时录制 |
| Live2D 实时预览 | 内置重音テト模型，脸部追踪时实时驱动 |
| Live2D 回放 | 录制的 Take 可回放到 Live2D 模型上 |
| Take 对比图表 | 多条 Take 参数叠加比较 |
| 导出 | CSV / NumPy NPZ / JSON |
| OpenSeeFace 兼容 | 仍支持 OpenSeeFace UDP 数据接入（可选） |

### 快速开始

```bash
git clone https://github.com/Wendell-Guan/TubeMoCap.git
cd TubeMoCap
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 使用步骤

1. 在左侧「动作库」点 **+** 创建动作标签
2. 选择模式（仅脸部 / 仅身体 / 脸部+身体）
3. 选择摄像头编号，点 **启动**（如果摄像头 0 被 OBS 占用，换成 1 或 2）
4. 等状态栏显示 **● 已连接**
5. 点 **● 开始录制**，做完动作后点 **⏹ 停止录制**
6. 可打开 Teto 实时预览查看效果，或选择 Take 点 **▶ 回放到 Teto**

### 摄像头权限（macOS）

首次点击「启动」时，macOS 会弹出摄像头授权请求，点「允许」即可。  
若之前误点了拒绝，前往：**系统设置 → 隐私与安全性 → 摄像头 → 开启终端应用（Terminal / iTerm）**
