# TubeMoCap

**EN** | [中文](#中文说明)

An open-source motion capture dataset collection tool with a PyQt5 GUI.  
Record face tracking (OpenSeeFace → UDP) and body pose (MediaPipe → camera) as labeled, versioned datasets — multiple takes per motion label, visual comparison chart, ML-ready export, and Live2D avatar preview/replay built in.

![screenshot placeholder](docs/screenshot.png)

---

## Features

- **Motion Library** — Create, rename, delete named motion labels (e.g. "开心大笑", "点头", "挥手")
- **Multiple Takes** — Record as many takes per motion as you need; each is stored independently
- **Dual Tracking** — Face via OpenSeeFace UDP + body pose via MediaPipe camera (face only / body only / both)
- **Live2D Real-time Preview** — See the bundled Teto (重音テト) model respond to your face in real-time
- **Take Comparison Chart** — Matplotlib overlay of any face parameter across selected takes
- **Export** — CSV, NumPy `.npz`, or raw JSON
- **Live2D Replay** — Send a recorded take as UDP packets to a Live2D driver (port 11574)
- **Dark UI** — Dark theme throughout

---

## Requirements

- Python 3.10+
- A camera (built-in or USB webcam) for body tracking
- [OpenSeeFace](https://github.com/emilianavt/OpenSeeFace) for face tracking (separate download)

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

# 4. Install live2d-py (for Live2D preview — optional but recommended)
pip install live2d-py

# 5. Launch
python main.py
```

> **macOS camera permission:** On first run, click **启动** in the body camera row.
> macOS will request camera access — click **Allow**.
> If you accidentally denied it, go to:
> **System Settings → Privacy & Security → Camera → enable Python**

---

## Face Tracking Setup (OpenSeeFace)

Face tracking is optional. Without it you can still record body-only takes.

```bash
# Download OpenSeeFace (separate repo)
git clone https://github.com/emilianavt/OpenSeeFace.git
cd OpenSeeFace
pip install -r requirements.txt

# Run face tracker on your camera (index 0)
python facetracker.py -c 0 -W 640 -H 480 --model 3
```

OpenSeeFace sends UDP packets to `127.0.0.1:11573`. TubeMoCap listens on that port automatically.

---

## Usage Guide

### 1 — Create a Motion Label

In the **动作库** panel (left), click **+**, type a name, press OK.  
The motion appears in the list with take counter `(0)`.

### 2 — Record a Take

1. Select a motion in the left panel
2. In the **录制 & Takes** tab (right):
   - Choose **Mode**: face only / body only / face + body
   - For body: select camera index → click **启动**
   - Status bar shows: `脸部 ● 已连接` / `身体 ● 已连接` when data is flowing
3. Click **● 开始录制** — timer starts
4. Perform your motion
5. Click **⏹ 停止录制** — take is saved automatically

### 3 — Live2D Preview

Click **🎭 打开 Teto 实时预览** to open the floating Live2D window.  
The bundled 重音テト model responds to your face in real-time.  
Click **换模型** to load a different `.model3.json` file.

### 4 — Compare Takes

Switch to the **对比图表** tab, select takes with checkboxes,  
choose a face parameter from the dropdown, click **刷新图表**.

### 5 — Export

Select a take → **⬇ 导出** → choose CSV / NPZ / JSON.

### 6 — Replay to Live2D Driver

Select a take → **▶ 回放到 Teto** — replays face data as UDP packets (port 11574)  
to any Live2D driver that listens on that port (e.g. ZerolanLiveRobot).

---

## Project Structure

```
TubeMoCap/
├── main.py                  Entry point
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── core/
│   ├── receiver.py          OpenSeeFace UDP face receiver
│   ├── body_receiver.py     MediaPipe body receiver (background thread, Tasks API)
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
│   └── pose_landmarker_full.task   MediaPipe pose model (auto-used)
├── resources/
│   └── live2d/
│       └── 重音テト/         Bundled Live2D model (重音テト by Kasane Teto)
└── dataset/                 Your recorded data (gitignored)
```

---

## Data Format

### `dataset/motions.json`

```json
{
  "version": "1.0",
  "motions": [
    { "id": "uuid", "name": "开心大笑", "created_at": "..." }
  ]
}
```

### `dataset/takes/{motion_id}/{index:03d}.json`

- `face_frames`: `[{t, pitch, yaw, roll, eye_l, eye_r, brow_l, brow_r, mouth_open, mouth_form, conf}, ...]`
- `body_frames`: `[{t, shoulder_width_ref, landmarks: {name: [x,y,z,vis]}}, ...]`

---

## License

MIT License — see [LICENSE](LICENSE)

The bundled 重音テト Live2D model is property of its respective creators.
It is included for demonstration purposes only.

---

## 中文说明

TubeMoCap 是一个开源动作捕捉数据集采集工具。

### 快速开始

```bash
git clone https://github.com/Wendell-Guan/TubeMoCap.git
cd TubeMoCap
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install live2d-py
python main.py
```

### 摄像头权限（macOS）

首次点击「启动」时，macOS 会弹出摄像头授权请求，点「允许」即可。  
若之前误点了拒绝，前往：**系统设置 → 隐私与安全性 → 摄像头 → 开启 Python**

### 脸部追踪（OpenSeeFace，可选）

```bash
git clone https://github.com/emilianavt/OpenSeeFace.git
cd OpenSeeFace
pip install -r requirements.txt
python facetracker.py -c 0 -W 640 -H 480 --model 3
```

OpenSeeFace 会自动向 `127.0.0.1:11573` 发送 UDP 数据，TubeMoCap 会自动接收。

### 功能说明

| 功能 | 说明 |
|------|------|
| 动作库 | 新建/重命名/删除动作标签 |
| 录制 | 支持仅脸部/仅身体/两者同时录制 |
| Live2D 实时预览 | 内置重音テト模型，脸部追踪时实时驱动 |
| Take 对比图表 | 多条 Take 参数叠加比较 |
| 导出 | CSV / NumPy NPZ / JSON |
| UDP 回放 | 将 Take 回放给 Live2D 驱动（端口 11574） |
