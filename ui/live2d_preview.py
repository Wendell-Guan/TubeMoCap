"""
Live2D real-time preview — runs as a SEPARATE floating window.

Opening it as an independent QWidget (not embedded inside the main window)
avoids OpenGL context conflicts that cause segfaults on macOS.

The canvas is created LAZILY on first show() to avoid crashing the main app
if live2d initialisation fails.

Usage:
    win = Live2DPreviewWindow(face_rx)
    win.show()          # open floating window
    win.hide()          # hide it
"""
import os
from typing import Optional

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt5.QtCore import Qt

from core.receiver import FaceReceiver, FaceData
from ui.opengl_canvas import OpenGLCanvas

# Default model path — relative to the project root (main.py location)
_DEFAULT_MODEL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'resources', 'live2d', '重音テト', '重音テト.model3.json'
)


def _live2d_major() -> int:
    try:
        import live2d
        v = getattr(live2d, '__version__', '0.5.0')
        return int(v.split('.')[0])
    except Exception:
        return 0   # treat as < 6


class _Live2DCanvas(OpenGLCanvas):
    """Minimal OpenGL canvas that mirrors face tracking onto the Live2D model."""

    def __init__(self, model_path: str, face_rx: FaceReceiver):
        super().__init__()
        self._model_path = model_path
        self._face_rx = face_rx
        self.model = None
        self._ready = False
        # NOTE: Do NOT set WA_TranslucentBackground on QOpenGLWidget — crashes macOS.

    # ── OpenGL lifecycle ─────────────────────────────────────────────

    def on_init(self):
        try:
            import live2d.v3 as live2d
            if _live2d_major() < 6:
                try:
                    live2d.glewInit()
                except Exception as e:
                    print(f'[Live2DPreview] glewInit warning (non-fatal): {e}')
            self.model = live2d.LAppModel()
            self.model.LoadModelJson(self._model_path)
            self._ready = True
            print('[Live2DPreview] model loaded OK')
        except Exception as e:
            print(f'[Live2DPreview] init error: {e}')
        self.startTimer(int(1000 / 60))

    def timerEvent(self, _event):
        self.update()

    def on_draw(self):
        try:
            import live2d.v3 as live2d
            from live2d.v3 import StandardParams
        except ImportError:
            return

        live2d.clearBuffer(0.13, 0.14, 0.19, 1.0)
        if not self._ready or self.model is None:
            return

        self.model.Update()

        fd: Optional[FaceData] = self._face_rx.get()
        if fd and fd.success:
            self.model.SetParameterValue(StandardParams.ParamAngleX,    fd.yaw)
            self.model.SetParameterValue(StandardParams.ParamAngleY,    fd.pitch)
            self.model.SetParameterValue(StandardParams.ParamAngleZ,    fd.roll)
            self.model.SetParameterValue(StandardParams.ParamEyeLOpen,  max(0.0, fd.eye_l))
            self.model.SetParameterValue(StandardParams.ParamEyeROpen,  max(0.0, fd.eye_r))
            self.model.SetParameterValue(StandardParams.ParamEyeBallX,  fd.yaw   / 30.0)
            self.model.SetParameterValue(StandardParams.ParamEyeBallY,  fd.pitch / 25.0)
            self.model.SetParameterValue(StandardParams.ParamMouthOpenY, max(0.0, fd.mouth_open))
            self.model.SetParameterValue("ParamMouthForm",  fd.mouth_form)
            self.model.SetParameterValue("ParamBrowLY",     fd.brow_l * 8.0)
            self.model.SetParameterValue("ParamBrowRY",     fd.brow_r * 8.0)
            self.model.SetParameterValue(StandardParams.ParamBodyAngleX, fd.yaw   * 0.15)
            self.model.SetParameterValue(StandardParams.ParamBodyAngleY, fd.pitch * 0.10)
            try:
                self.model.SetParameterValue("ParamWatermarkOFF", 1.0)
            except Exception:
                pass

        self.model.Draw()

    def on_resize(self, w: int, h: int):
        if self.model:
            self.model.Resize(w, h)

    def reload(self, path: str):
        self._model_path = path
        self._ready = False
        if self.model:
            try:
                self.model.LoadModelJson(path)
                self._ready = True
            except Exception as e:
                print(f'[Live2DPreview] reload error: {e}')


class Live2DPreviewWindow(QWidget):
    """
    Standalone floating window that shows the Live2D model responding to
    face tracking in real time.

    The OpenGL canvas is created lazily on first show() to avoid impacting
    MoCap Studio startup if live2d / OpenGL initialisation fails.
    """

    def __init__(self, face_rx: FaceReceiver, model_path: str = _DEFAULT_MODEL):
        super().__init__(
            None,
            Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint
        )
        self.setWindowTitle('Teto — 实时预览')
        self.resize(420, 600)
        self._face_rx = face_rx
        self._model_path = model_path
        self._canvas: Optional[_Live2DCanvas] = None
        self._initialised = False

        # Build a placeholder layout; the real canvas is inserted on first show
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel('正在初始化 Live2D…')
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet('color:#888; font-size:13px; background:#1a1a2e;')
        self._layout.addWidget(self._placeholder)

    # ── public ───────────────────────────────────────────────────────

    def set_model(self, path: str):
        self._model_path = path
        if self._canvas:
            self._canvas.reload(path)

    # ── private ──────────────────────────────────────────────────────

    def showEvent(self, event):
        """Lazily create the OpenGL canvas on first show."""
        super().showEvent(event)
        if not self._initialised:
            self._initialised = True
            self._init_canvas()

    def _init_canvas(self):
        # Remove placeholder
        self._placeholder.setParent(None)

        if not os.path.exists(self._model_path):
            lbl = QLabel(
                '模型文件不存在\n\n'
                '请在 MoCap Studio 主界面\n点击「换模型」重新选择'
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color:#888; font-size:13px; background:#1a1a2e;')
            self._layout.addWidget(lbl)
            return

        try:
            import live2d.v3   # noqa — availability check
            self._canvas = _Live2DCanvas(self._model_path, self._face_rx)
            self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._layout.addWidget(self._canvas)
            print('[Live2DPreview] canvas added to window')
        except ImportError:
            lbl = QLabel('live2d-py 未安装\n\npip install live2d-py')
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color:#e74c3c; font-size:13px;')
            self._layout.addWidget(lbl)
        except Exception as e:
            lbl = QLabel(f'Live2D 初始化失败\n\n{e}')
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color:#e74c3c; font-size:13px; background:#1a1a2e;')
            self._layout.addWidget(lbl)
            print(f'[Live2DPreview] canvas init error: {e}')

    def closeEvent(self, event):
        # Don't destroy — just hide, so it can be re-opened
        self.hide()
        event.ignore()
