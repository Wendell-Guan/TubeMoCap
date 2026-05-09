"""Right panel: takes browser + recording controls + compare chart."""
import os
import socket
import json
import time
import threading

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QComboBox, QHeaderView, QAbstractItemView, QFileDialog,
    QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer

from core.dataset import Dataset
from core.recorder import Recorder
from core.receiver import FaceReceiver
from core.body_receiver import BodyReceiver
from ui.compare_widget import CompareWidget
from ui.live2d_preview import Live2DPreviewWindow


class TakePanel(QWidget):
    def __init__(self, dataset: Dataset, recorder: Recorder,
                 face_rx: FaceReceiver, body_rx: BodyReceiver):
        super().__init__()
        self.dataset = dataset
        self.recorder = recorder
        self.face_rx = face_rx
        self.body_rx = body_rx
        self._motion_id = None
        self._takes = []
        self._build_ui()

        # Recording timer
        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._update_rec_display)

        # Wire recorder tick
        self.recorder.on_tick = self._on_rec_tick
        self._elapsed = 0.0
        # Called after a take is saved so MotionPanel can refresh its count
        self.on_takes_changed = None

    def set_dataset(self, dataset: Dataset):
        self.dataset = dataset
        self.refresh_takes()

    def set_motion(self, motion_id: str):
        self._motion_id = motion_id
        motion = self.dataset.get_motion(motion_id)
        self._motion_label.setText(f'动作：{motion.name if motion else "—"}')
        self.refresh_takes()

    def refresh_takes(self):
        self._takes = self.dataset.list_takes(self._motion_id) if self._motion_id else []
        self._table.setRowCount(0)
        for t in self._takes:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(f"Take {t['take_index']:03d}"))
            self._table.setItem(row, 1, QTableWidgetItem(f"{t['duration']:.1f}s"))
            self._table.setItem(row, 2, QTableWidgetItem(t['mode']))
            self._table.setItem(row, 3, QTableWidgetItem(
                f"{t['face_frame_count']}f / {t['body_frame_count']}f"))
        self._compare.set_takes(self._motion_id, self._takes)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Motion label
        self._motion_label = QLabel('动作：—')
        self._motion_label.setStyleSheet('font-weight: bold; font-size: 14px;')
        layout.addWidget(self._motion_label)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # ── Tab 1: Takes ──────────────────────────────────────────────
        takes_tab = QWidget()
        takes_layout = QVBoxLayout(takes_tab)
        takes_layout.setContentsMargins(4, 4, 4, 4)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(['名称', '时长', '模式', '帧数(脸/身)'])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        takes_layout.addWidget(self._table)

        # Take action buttons
        take_btns = QHBoxLayout()
        self._btn_play = QPushButton('▶ 回放到 Teto')
        self._btn_export = QPushButton('⬇ 导出')
        self._btn_del_take = QPushButton('🗑 删除')
        for btn in (self._btn_play, self._btn_export, self._btn_del_take):
            take_btns.addWidget(btn)
        takes_layout.addLayout(take_btns)
        self._btn_play.clicked.connect(self._on_play)
        self._btn_export.clicked.connect(self._on_export)
        self._btn_del_take.clicked.connect(self._on_delete_take)

        # Record group
        rec_group = QGroupBox('录制')
        rec_layout = QVBoxLayout(rec_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel('模式:'))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(['🎭 仅脸部', '🕺 仅身体', '🎬 脸部 + 身体'])
        self._mode_combo.setCurrentIndex(0)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()
        rec_layout.addLayout(mode_row)

        face_row = QHBoxLayout()
        face_row.addWidget(QLabel('脸部摄像头:'))
        self._face_cam_combo = QComboBox()
        for i in range(5):
            self._face_cam_combo.addItem(f'摄像头 {i}', i)
        self._face_cam_combo.setCurrentIndex(0)
        self._btn_start_face = QPushButton('启动')
        self._btn_start_face.clicked.connect(self._on_start_face)
        face_row.addWidget(self._face_cam_combo)
        face_row.addWidget(self._btn_start_face)
        face_row.addStretch()
        rec_layout.addLayout(face_row)

        body_row = QHBoxLayout()
        body_row.addWidget(QLabel('身体摄像头:'))
        self._cam_combo = QComboBox()
        for i in range(5):
            self._cam_combo.addItem(f'摄像头 {i}', i)
        self._cam_combo.setCurrentIndex(0)
        self._cam_combo.currentIndexChanged.connect(self._on_cam_changed)
        self._btn_start_body = QPushButton('启动')
        self._btn_start_body.clicked.connect(self._on_start_body)
        body_row.addWidget(self._cam_combo)
        body_row.addWidget(self._btn_start_body)
        body_row.addStretch()
        rec_layout.addLayout(body_row)

        ctrl_row = QHBoxLayout()
        self._btn_record = QPushButton('● 开始录制')
        self._btn_record.setStyleSheet(
            'background:#e74c3c; color:white; font-weight:bold; padding:6px 16px;'
        )
        self._btn_record.setFixedHeight(36)
        self._timer_label = QLabel('00:00.0')
        self._timer_label.setStyleSheet('font-size:16px; font-family:monospace;')
        ctrl_row.addWidget(self._btn_record)
        ctrl_row.addWidget(self._timer_label)
        ctrl_row.addStretch()
        rec_layout.addLayout(ctrl_row)
        self._btn_record.clicked.connect(self._on_record_clicked)
        takes_layout.addWidget(rec_group)

        tabs.addTab(takes_tab, '录制 & Takes')

        # ── Live2D Preview (floating window, created lazily) ──────────
        self._preview_win = Live2DPreviewWindow(self.face_rx)

        # Preview + model-change row
        preview_row = QHBoxLayout()
        self._btn_preview = QPushButton('🎭 打开 Teto 实时预览')
        self._btn_preview.setStyleSheet(
            'background:#0f3460; color:#e0e0e0; padding:5px 12px; border-radius:4px;'
        )
        self._btn_preview.clicked.connect(self._toggle_preview)
        preview_row.addWidget(self._btn_preview)

        self._btn_change_model = QPushButton('换模型')
        self._btn_change_model.setToolTip('选择 Live2D .model3.json 文件')
        self._btn_change_model.clicked.connect(self._on_change_model)
        preview_row.addWidget(self._btn_change_model)

        # Show current model name (folder name = model name)
        self._model_name_label = QLabel(self._model_display_name())
        self._model_name_label.setStyleSheet('color:#888; font-size:11px;')
        preview_row.addWidget(self._model_name_label)
        preview_row.addStretch()
        rec_layout.addLayout(preview_row)

        # ── Tab 2: Compare ────────────────────────────────────────────
        self._compare = CompareWidget(self.dataset)
        tabs.addTab(self._compare, '对比图表')

    # ── Model helpers ─────────────────────────────────────────────────

    def _model_display_name(self) -> str:
        """Return the model folder name as a short display label."""
        p = self._preview_win._model_path
        return os.path.basename(os.path.dirname(p)) if p else '—'

    def _on_change_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择 Live2D 模型文件', '',
            'Live2D 模型 (*.model3.json);;所有文件 (*)'
        )
        if path:
            self._preview_win.set_model(path)
            self._model_name_label.setText(
                os.path.basename(os.path.dirname(path))
            )

    # ── Preview toggle ────────────────────────────────────────────────

    def _toggle_preview(self):
        if self._preview_win.isVisible():
            self._preview_win.hide()
            self._btn_preview.setText('🎭 打开 Teto 实时预览')
        else:
            self._preview_win.show()
            self._btn_preview.setText('🎭 关闭 Teto 实时预览')

    # ── Mode / camera ─────────────────────────────────────────────────

    def _on_mode_changed(self, idx):
        modes = ['face', 'body', 'both']
        self.recorder.set_mode(modes[idx])

    def _on_cam_changed(self):
        idx = self._cam_combo.currentData()
        self.body_rx.set_camera(idx)

    def _on_start_face(self):
        if self.face_rx.mode == 'camera' and self.face_rx._running:
            self.face_rx.stop()
            self.face_rx.start_udp()
            self._btn_start_face.setText('启动')
        else:
            idx = self._face_cam_combo.currentData()
            self.face_rx.start_camera(idx)
            self._btn_start_face.setText('停止')
            QTimer.singleShot(2000, self._check_face_error)

    def _check_face_error(self):
        if self.face_rx.error:
            self._btn_start_face.setText('启动')
            QMessageBox.warning(
                self, '脸部摄像头启动失败',
                f'{self.face_rx.error}\n\n'
                '请确认摄像头权限已开启。'
            )

    def _on_start_body(self):
        if self.body_rx.is_running:
            self.body_rx.stop()
            self._btn_start_body.setText('启动')
        else:
            idx = self._cam_combo.currentData()
            self.body_rx.set_camera(idx)
            self.body_rx.start()
            self._btn_start_body.setText('停止')
            # Check for startup errors after 1.5 s
            QTimer.singleShot(1500, self._check_body_error)

    def _check_body_error(self):
        """Called 1.5 s after clicking 启动; shows error if camera failed."""
        if self.body_rx.error:
            self._btn_start_body.setText('启动')
            QMessageBox.warning(
                self, '摄像头启动失败',
                f'{self.body_rx.error}\n\n'
                '如果提示权限被拒绝，请前往：\n'
                '「系统设置 → 隐私与安全性 → 摄像头」\n'
                '为 Python 开启摄像头访问权限后重试。'
            )

    # ── Recording ─────────────────────────────────────────────────────

    def _on_rec_tick(self, elapsed: float):
        self._elapsed = elapsed

    def _update_rec_display(self):
        mins = int(self._elapsed) // 60
        secs = self._elapsed % 60
        self._timer_label.setText(f'{mins:02d}:{secs:04.1f}')

    def _on_record_clicked(self):
        if not self._motion_id:
            QMessageBox.warning(self, '提示', '请先在左侧选择一个动作')
            return
        if self.recorder.is_recording:
            # ── Stop ──────────────────────────────────────────────────
            frame_data = self.recorder.stop()
            self._rec_timer.stop()
            self._btn_record.setText('● 开始录制')
            self._btn_record.setStyleSheet(
                'background:#e74c3c; color:white; font-weight:bold; padding:6px 16px;'
            )
            face_n = len(frame_data['face_frames'])
            body_n = len(frame_data['body_frames'])
            if face_n > 0 or body_n > 0:
                self.dataset.save_take(self._motion_id, frame_data)
                self.refresh_takes()
                if self.on_takes_changed:
                    self.on_takes_changed()
            else:
                # No data captured — warn the user
                mode = self._mode_combo.currentText()
                QMessageBox.warning(
                    self, '录制为空',
                    f'本次录制（{mode}）没有捕获到任何数据帧。\n\n'
                    '• 脸部数据为空 → 请先点击脸部摄像头「启动」\n'
                    '• 身体数据为空 → 请先点击身体摄像头「启动」\n'
                    '  并确认摄像头权限已开启'
                )
        else:
            # ── Start ─────────────────────────────────────────────────
            self.recorder.start()
            self._rec_timer.start(100)
            self._btn_record.setText('⏹ 停止录制')
            self._btn_record.setStyleSheet(
                'background:#2ecc71; color:white; font-weight:bold; padding:6px 16px;'
            )

    # ── Take actions ──────────────────────────────────────────────────

    def _selected_take_index(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._takes):
            return None
        return self._takes[row]['take_index']

    def _on_play(self):
        """Replay a take by sending UDP packets to ZerolanLiveRobot on port 11574."""
        if not self._motion_id:
            return
        idx = self._selected_take_index()
        if idx is None:
            QMessageBox.warning(self, '提示', '请先选择一条 Take')
            return
        take = self.dataset.load_take(self._motion_id, idx)
        if not take or not take.get('face_frames'):
            QMessageBox.information(self, '提示', '该 Take 没有脸部数据，无法回放')
            return

        def _replay():
            from core.receiver import FaceData
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            frames = take['face_frames']
            if not frames:
                sock.close()
                return
            prev_t = 0.0
            for fr in frames:
                dt = fr['t'] - prev_t
                if dt > 0:
                    time.sleep(dt)
                prev_t = fr['t']
                fd = FaceData(
                    pitch=fr['pitch'], yaw=fr['yaw'], roll=fr['roll'],
                    eye_l=fr['eye_l'], eye_r=fr['eye_r'],
                    brow_l=fr['brow_l'], brow_r=fr['brow_r'],
                    mouth_open=fr['mouth_open'], mouth_form=fr['mouth_form'],
                    conf=0.9, success=True,
                )
                self.face_rx.inject(fd)
                payload = json.dumps({
                    'type': 'face',
                    'pitch': fr['pitch'], 'yaw': fr['yaw'], 'roll': fr['roll'],
                    'eye_l': fr['eye_l'], 'eye_r': fr['eye_r'],
                    'brow_l': fr['brow_l'], 'brow_r': fr['brow_r'],
                    'mouth_open': fr['mouth_open'], 'mouth_form': fr['mouth_form'],
                }).encode()
                sock.sendto(payload, ('127.0.0.1', 11574))
            sock.close()

        threading.Thread(target=_replay, daemon=True, name='Replay').start()

    def _on_export(self):
        idx = self._selected_take_index()
        if idx is None:
            QMessageBox.warning(self, '提示', '请先选择一条 Take')
            return
        fmt, ok = QFileDialog.getSaveFileName(
            self, '导出 Take', f'take_{idx:03d}',
            'CSV 文件 (*.csv);;NumPy 压缩包 (*.npz);;JSON 文件 (*.json)'
        )
        if not ok or not fmt:
            return
        if fmt.endswith('.csv'):
            self.dataset.export_take_csv(self._motion_id, idx, fmt)
        elif fmt.endswith('.npz'):
            self.dataset.export_take_npz(self._motion_id, idx, fmt)
        else:
            take = self.dataset.load_take(self._motion_id, idx)
            with open(fmt, 'w', encoding='utf-8') as f:
                json.dump(take, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, '完成', f'已导出到 {fmt}')

    def _on_delete_take(self):
        idx = self._selected_take_index()
        if idx is None:
            return
        reply = QMessageBox.question(self, '确认', f'删除 Take {idx:03d}？',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.dataset.delete_take(self._motion_id, idx)
            self.refresh_takes()
            if self.on_takes_changed:
                self.on_takes_changed()
