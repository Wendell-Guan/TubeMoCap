"""Left panel: motion list with CRUD operations."""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from core.dataset import Dataset, Motion


class MotionPanel(QWidget):
    motion_selected = pyqtSignal(str)  # emits motion_id

    def __init__(self, dataset: Dataset):
        super().__init__()
        self.dataset = dataset
        self._selected_id = None
        self._build_ui()
        self.refresh()

    def set_dataset(self, dataset: Dataset):
        self.dataset = dataset
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel('Motion Library')
        title.setStyleSheet('font-weight: bold; font-size: 14px;')
        layout.addWidget(title)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText('Search...')
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        # List
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self._list)

        # Buttons
        btn_layout = QHBoxLayout()
        self._btn_add = QPushButton('+')
        self._btn_rename = QPushButton('Edit')
        self._btn_delete = QPushButton('Del')
        self._btn_add.setToolTip('New motion')
        self._btn_rename.setToolTip('Rename')
        self._btn_delete.setToolTip('Delete')
        for btn in (self._btn_add, self._btn_rename, self._btn_delete):
            btn.setFixedHeight(30)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        self._btn_add.clicked.connect(self._on_add)
        self._btn_rename.clicked.connect(self._on_rename)
        self._btn_delete.clicked.connect(self._on_delete)

    def refresh(self):
        query = self._search.text().lower() if hasattr(self, '_search') else ''
        self._list.clear()
        for m in self.dataset.motions():
            if query and query not in m.name.lower():
                continue
            count = self.dataset.take_count(m.id)
            item = QListWidgetItem(f'  {m.name}  ({count})')
            item.setData(Qt.UserRole, m.id)
            self._list.addItem(item)
            if m.id == self._selected_id:
                self._list.setCurrentItem(item)

    def _on_search(self):
        self.refresh()

    def _on_select(self, row):
        item = self._list.item(row)
        if item:
            self._selected_id = item.data(Qt.UserRole)
            self.motion_selected.emit(self._selected_id)

    def _on_add(self):
        name, ok = QInputDialog.getText(self, 'New Motion', 'Motion name:')
        if ok and name.strip():
            m = self.dataset.add_motion(name.strip())
            self._selected_id = m.id
            self.refresh()
            self.motion_selected.emit(m.id)

    def _on_rename(self):
        if not self._selected_id:
            return
        m = self.dataset.get_motion(self._selected_id)
        if not m:
            return
        name, ok = QInputDialog.getText(self, 'Rename', 'New name:', text=m.name)
        if ok and name.strip():
            self.dataset.rename_motion(self._selected_id, name.strip())
            self.refresh()

    def _on_delete(self):
        if not self._selected_id:
            return
        m = self.dataset.get_motion(self._selected_id)
        if not m:
            return
        count = self.dataset.take_count(m.id)
        msg = f'Delete "{m.name}"'
        if count:
            msg += f' and its {count} take(s)'
        msg += '?'
        reply = QMessageBox.question(self, 'Confirm Delete', msg,
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.dataset.delete_motion(self._selected_id)
            self._selected_id = None
            self.refresh()
