"""MoCap Studio -- entry point."""
import sys
import os

# Make sure dataset dir exists relative to script location
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# live2d Cubism Framework must be initialised BEFORE QApplication is created.
# ZerolanLiveRobot does the same in its prepare_main_thread() method.
try:
    import live2d.v3 as _live2d
    _live2d.init()
    print('[startup] live2d.init() OK')
except Exception as _e:
    print(f'[startup] live2d.init() skipped: {_e}')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('MoCap Studio')
    app.setOrganizationName('MoCap Studio')

    # Global font
    font = QFont('PingFang SC', 11) if sys.platform == 'darwin' else QFont('Segoe UI', 10)
    app.setFont(font)

    # Dark stylesheet
    app.setStyleSheet("""
        QMainWindow, QWidget { background: #1a1a2e; color: #e0e0e0; }
        QListWidget, QTableWidget { background: #16213e; border: 1px solid #444; color: #e0e0e0; }
        QListWidget::item:selected, QTableWidget::item:selected { background: #0f3460; }
        QPushButton { background: #0f3460; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; padding: 4px 10px; }
        QPushButton:hover { background: #16213e; border-color: #888; }
        QPushButton:pressed { background: #e94560; }
        QComboBox { background: #16213e; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; padding: 2px 6px; }
        QComboBox QAbstractItemView { background: #16213e; color: #e0e0e0; }
        QLineEdit { background: #16213e; color: #e0e0e0; border: 1px solid #444; border-radius: 4px; padding: 3px 6px; }
        QLabel { color: #e0e0e0; }
        QTabWidget::pane { border: 1px solid #444; }
        QTabBar::tab { background: #16213e; color: #aaaaaa; padding: 6px 14px; border-radius: 4px 4px 0 0; }
        QTabBar::tab:selected { background: #0f3460; color: #ffffff; }
        QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 8px; padding-top: 6px; color: #aaaaaa; }
        QGroupBox::title { subcontrol-origin: margin; padding: 0 4px; }
        QHeaderView::section { background: #0f3460; color: #e0e0e0; border: 1px solid #444; padding: 4px; }
        QScrollBar:vertical { background: #16213e; width: 10px; }
        QScrollBar::handle:vertical { background: #444; border-radius: 5px; }
        QCheckBox { color: #e0e0e0; }
        QStatusBar { background: #0f3460; color: #aaaaaa; }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
