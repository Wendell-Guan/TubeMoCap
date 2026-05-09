"""Matplotlib comparison chart embedded in PyQt5."""
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QScrollArea, QPushButton
)
from PyQt5.QtCore import Qt
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from core.dataset import Dataset

FACE_PARAMS = [
    'pitch', 'yaw', 'roll',
    'eye_l', 'eye_r',
    'brow_l', 'brow_r',
    'mouth_open', 'mouth_form',
]
COLORS = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']


class CompareWidget(QWidget):
    def __init__(self, dataset: Dataset):
        super().__init__()
        self.dataset = dataset
        self._motion_id = None
        self._takes = []
        self._build_ui()

    def set_takes(self, motion_id: Optional[str], takes: List[Dict]):
        self._motion_id = motion_id
        self._takes = takes
        self._rebuild_checkboxes()
        self._replot()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('参数:'))
        self._param_combo = QComboBox()
        self._param_combo.addItems(FACE_PARAMS)
        self._param_combo.setCurrentText('pitch')
        self._param_combo.currentTextChanged.connect(self._replot)
        ctrl.addWidget(self._param_combo)
        ctrl.addStretch()
        self._btn_plot = QPushButton('刷新图表')
        self._btn_plot.clicked.connect(self._replot)
        ctrl.addWidget(self._btn_plot)
        layout.addLayout(ctrl)

        # Take checkboxes (scrollable)
        scroll = QScrollArea()
        scroll.setMaximumHeight(80)
        scroll.setWidgetResizable(True)
        cb_widget = QWidget()
        self._cb_layout = QHBoxLayout(cb_widget)
        self._cb_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(cb_widget)
        layout.addWidget(scroll)
        self._checkboxes: List[QCheckBox] = []

        # Matplotlib figure
        self._figure = Figure(figsize=(8, 3), tight_layout=True)
        self._ax = self._figure.add_subplot(111)
        self._canvas = FigureCanvas(self._figure)
        layout.addWidget(self._canvas)

    def _rebuild_checkboxes(self):
        for cb in self._checkboxes:
            self._cb_layout.removeWidget(cb)
            cb.deleteLater()
        self._checkboxes = []
        for i, t in enumerate(self._takes):
            cb = QCheckBox(f"Take {t['take_index']:03d}")
            cb.setChecked(i < 5)  # first 5 checked by default
            color = COLORS[i % len(COLORS)]
            cb.setStyleSheet(f'color: {color}; font-weight: bold;')
            cb.stateChanged.connect(self._replot)
            self._cb_layout.addWidget(cb)
            self._checkboxes.append(cb)
        self._cb_layout.addStretch()

    def _replot(self):
        self._ax.clear()
        param = self._param_combo.currentText()
        has_data = False
        for i, (t, cb) in enumerate(zip(self._takes, self._checkboxes)):
            if not cb.isChecked():
                continue
            if not self._motion_id:
                continue
            take = self.dataset.load_take(self._motion_id, t['take_index'])
            if not take:
                continue
            frames = take.get('face_frames', [])
            if not frames:
                continue
            ts = [fr['t'] for fr in frames]
            vals = [fr.get(param, 0.0) for fr in frames]
            color = COLORS[i % len(COLORS)]
            self._ax.plot(ts, vals, color=color, linewidth=1.2,
                          label=f"Take {t['take_index']:03d}")
            has_data = True

        if has_data:
            self._ax.legend(loc='upper right', fontsize=8)
        self._ax.set_xlabel('time (s)', fontsize=8)
        self._ax.set_ylabel(param, fontsize=8)
        self._ax.set_title(f'参数对比: {param}', fontsize=10)
        self._ax.grid(True, alpha=0.3)
        self._figure.patch.set_facecolor('#1a1a2e')
        self._ax.set_facecolor('#16213e')
        self._ax.tick_params(colors='#aaaaaa', labelsize=7)
        self._ax.title.set_color('#ffffff')
        self._ax.xaxis.label.set_color('#aaaaaa')
        self._ax.yaxis.label.set_color('#aaaaaa')
        for spine in self._ax.spines.values():
            spine.set_edgecolor('#444444')
        self._canvas.draw()
