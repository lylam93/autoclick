from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_app_theme(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#13161d"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f4efe4"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1a202b"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#222938"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#f4efe4"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#13161d"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f4efe4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#222938"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f4efe4"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#e39b42"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#101214"))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QWidget {
            background-color: #13161d;
            color: #f4efe4;
            font-family: "Segoe UI";
            font-size: 10pt;
        }
        QMainWindow {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 1,
                stop: 0 #13161d,
                stop: 0.45 #1a202b,
                stop: 1 #1f262f
            );
        }
        QGroupBox {
            border: 1px solid #323b4d;
            border-radius: 14px;
            margin-top: 12px;
            padding: 16px 14px 14px 14px;
            font-weight: 600;
            background-color: rgba(34, 41, 56, 0.85);
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #f1c27a;
        }
        QPushButton {
            border: none;
            border-radius: 10px;
            padding: 10px 14px;
            background-color: #e39b42;
            color: #101214;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #efac55;
        }
        QPushButton:disabled {
            background-color: #556074;
            color: #d1d5db;
        }
        QLineEdit, QSpinBox, QListWidget, QPlainTextEdit {
            border: 1px solid #404a60;
            border-radius: 10px;
            padding: 8px;
            background-color: #0f131a;
        }
        QLabel[role="muted"] {
            color: #b5bdcc;
        }
        """
    )

