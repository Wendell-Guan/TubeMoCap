"""Main application window."""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QLabel, QAction, QMenuBar, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from core.receiver import FaceReceiver
from core.body_receiver import BodyReceiver
from core.recorder import Recorder
from core.dataset import Dataset
from ui.motion_panel import MotionPanel
from ui.take_panel import TakePanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('MoCap Studio')
        self.resize(1100, 700)

        # Core objects
        self.face_rx = FaceReceiver()
        self.body_rx = BodyReceiver(camera_index=0)
        self.recorder = Recorder(self.face_rx, self.body_rx)
        self.dataset = Dataset('dataset')

        # Start UDP listener for OpenSeeFace (fallback, non-blocking)
        self.face_rx.start()

        # Build UI
        self._build_ui()
        self._build_menu()

        # Status update timer
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(500)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        self.motion_panel = MotionPanel(self.dataset)
        self.take_panel = TakePanel(self.dataset, self.recorder, self.face_rx, self.body_rx)

        splitter.addWidget(self.motion_panel)
        splitter.addWidget(self.take_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([260, 840])

        layout.addWidget(splitter)

        # Connect motion selection
        self.motion_panel.motion_selected.connect(self.take_panel.set_motion)

        # Refresh motion panel count when takes are added/deleted
        self.take_panel.on_takes_changed = self.motion_panel.refresh

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._face_status = QLabel('脸部: ○ 未连接')
        self._body_status = QLabel('身体: ○ 未连接')
        self.status_bar.addWidget(self._face_status)
        self.status_bar.addWidget(QLabel('  |  '))
        self.status_bar.addWidget(self._body_status)

    def _build_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu('文件')
        act_open = QAction('打开数据集目录…', self)
        act_open.triggered.connect(self._open_dataset)
        file_menu.addAction(act_open)

    def _open_dataset(self):
        path = QFileDialog.getExistingDirectory(self, '选择数据集目录')
        if path:
            self.dataset = Dataset(path)
            self.motion_panel.set_dataset(self.dataset)
            self.take_panel.set_dataset(self.dataset)

    def _update_status(self):
        if self.face_rx.is_active():
            self._face_status.setText('脸部: ● 已连接')
            self._face_status.setStyleSheet('color: #2ecc71')
        elif self.face_rx.error:
            self._face_status.setText(f'脸部: ✗ {self.face_rx.error[:40]}')
            self._face_status.setStyleSheet('color: #e67e22')
        else:
            self._face_status.setText('脸部: ○ 未连接')
            self._face_status.setStyleSheet('color: #e74c3c')

        if self.body_rx.is_active():
            self._body_status.setText('身体: ● 已连接')
            self._body_status.setStyleSheet('color: #2ecc71')
        elif self.body_rx.error:
            self._body_status.setText(f'身体: ✗ {self.body_rx.error[:40]}')
            self._body_status.setStyleSheet('color: #e67e22')
        else:
            self._body_status.setText('身体: ○ 未启动')
            self._body_status.setStyleSheet('color: #95a5a6')

    def closeEvent(self, event):
        self.face_rx.stop()
        self.body_rx.stop()
        event.accept()
