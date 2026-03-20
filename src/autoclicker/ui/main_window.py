from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.domain.models import AppConfig
from autoclicker.services.click_engine import ClickEngine
from autoclicker.services.config_store import ConfigStore
from autoclicker.services.hotkey_service import HotkeyService
from autoclicker.services.window_service import WindowService


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        config_store: ConfigStore,
        window_service: WindowService,
        click_engine: ClickEngine,
        hotkey_service: HotkeyService,
    ) -> None:
        super().__init__()
        self._config_store = config_store
        self._window_service = window_service
        self._click_engine = click_engine
        self._hotkey_service = hotkey_service
        self._config = self._config_store.load()

        self.setWindowTitle("Advanced Background Auto-Clicker")
        self.resize(1080, 760)
        self.setMinimumSize(920, 680)

        self._build_ui()
        self._populate_from_config(self._config)
        self._wire_events()
        self._append_log("Python + PySide6 scaffold is ready.")

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        header = self._build_header()
        top_row = QHBoxLayout()
        top_row.setSpacing(18)
        top_row.addWidget(self._build_target_group(), 2)
        top_row.addWidget(self._build_click_settings_group(), 2)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(18)
        bottom_row.addWidget(self._build_hotkeys_group(), 1)
        bottom_row.addWidget(self._build_status_group(), 2)

        actions = self._build_actions()

        layout.addWidget(header)
        layout.addLayout(top_row)
        layout.addLayout(bottom_row)
        layout.addLayout(actions)

        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("Advanced Background Auto-Clicker")
        title.setStyleSheet("font-size: 22pt; font-weight: 700; color: #f7d9aa;")

        subtitle = QLabel(
            "Step 1 scaffold: app shell, service boundaries, and a UI ready for Win32 integration."
        )
        subtitle.setProperty("role", "muted")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return wrapper

    def _build_target_group(self) -> QGroupBox:
        group = QGroupBox("Target Window")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.target_title_value = QLabel("No target selected")
        self.target_title_value.setStyleSheet("font-size: 13pt; font-weight: 600;")

        self.target_meta_value = QLabel("HWND: -, Class: -, PID: -")
        self.target_meta_value.setProperty("role", "muted")

        self.window_list = QListWidget()
        self.window_list.addItem("Window enumeration will appear here in Step 2.")

        buttons = QHBoxLayout()
        self.refresh_windows_button = QPushButton("Refresh Windows")
        self.pick_window_button = QPushButton("Crosshair Picker")
        self.pick_window_button.setEnabled(False)
        buttons.addWidget(self.refresh_windows_button)
        buttons.addWidget(self.pick_window_button)

        layout.addWidget(self.target_title_value)
        layout.addWidget(self.target_meta_value)
        layout.addWidget(self.window_list, 1)
        layout.addLayout(buttons)
        return group

    def _build_click_settings_group(self) -> QGroupBox:
        group = QGroupBox("Click Settings")
        form = QFormLayout(group)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 3_600_000)
        self.delay_spin.setSuffix(" ms")

        self.random_delay_checkbox = QCheckBox("Enable random delay range")

        self.random_min_spin = QSpinBox()
        self.random_min_spin.setRange(1, 3_600_000)
        self.random_min_spin.setSuffix(" ms")

        self.random_max_spin = QSpinBox()
        self.random_max_spin.setRange(1, 3_600_000)
        self.random_max_spin.setSuffix(" ms")

        self.max_clicks_spin = QSpinBox()
        self.max_clicks_spin.setRange(0, 10_000_000)
        self.max_clicks_spin.setSpecialValueText("Unlimited")

        self.primary_point_value = QLabel("(0, 0)")
        self.primary_point_value.setStyleSheet("font-size: 12pt; font-weight: 600;")

        self.capture_hint = QLabel("Hotkey capture becomes active in Step 4.")
        self.capture_hint.setProperty("role", "muted")
        self.capture_hint.setWordWrap(True)

        form.addRow("Base delay", self.delay_spin)
        form.addRow("", self.random_delay_checkbox)
        form.addRow("Random minimum", self.random_min_spin)
        form.addRow("Random maximum", self.random_max_spin)
        form.addRow("Max clicks", self.max_clicks_spin)
        form.addRow("Primary point", self.primary_point_value)
        form.addRow("", self.capture_hint)
        return group

    def _build_hotkeys_group(self) -> QGroupBox:
        group = QGroupBox("Hotkeys")
        form = QFormLayout(group)
        form.setSpacing(12)

        self.start_stop_hotkey = QLineEdit()
        self.capture_hotkey = QLineEdit()

        self.start_stop_hotkey.setPlaceholderText("Press a key...")
        self.capture_hotkey.setPlaceholderText("Press a key...")

        hotkey_note = QLabel("Editable UI bindings are scaffolded now; native registration lands in Step 6.")
        hotkey_note.setWordWrap(True)
        hotkey_note.setProperty("role", "muted")

        form.addRow("Start / Stop", self.start_stop_hotkey)
        form.addRow("Get Position", self.capture_hotkey)
        form.addRow("", hotkey_note)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Status & Logs")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self.status_value = QLabel("Ready")
        self.status_value.setStyleSheet("font-size: 18pt; font-weight: 700;")

        self.click_count_value = QLabel("Completed clicks: 0")
        self.click_count_value.setProperty("role", "muted")

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)

        layout.addWidget(self.status_value)
        layout.addWidget(self.click_count_value)
        layout.addWidget(self.log_output, 1)
        return group

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.save_config_button = QPushButton("Save Config")
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        layout.addWidget(self.save_config_button)
        layout.addStretch(1)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        return layout

    def _populate_from_config(self, config: AppConfig) -> None:
        self.delay_spin.setValue(config.click_settings.delay_ms)
        self.random_delay_checkbox.setChecked(config.click_settings.use_random_delay)
        self.random_min_spin.setValue(config.click_settings.random_min_ms)
        self.random_max_spin.setValue(config.click_settings.random_max_ms)
        self.max_clicks_spin.setValue(config.click_settings.max_clicks or 0)
        self.start_stop_hotkey.setText(config.hotkeys.start_stop)
        self.capture_hotkey.setText(config.hotkeys.capture_point)

        point = config.points[0]
        self.primary_point_value.setText(f"({point.x}, {point.y})")

        if config.target_window.hwnd:
            self.target_title_value.setText(config.target_window.title or "Selected target")
            self.target_meta_value.setText(
                f"HWND: {config.target_window.hwnd}, "
                f"Class: {config.target_window.class_name or '-'}, "
                f"PID: {config.target_window.process_id or '-'}"
            )

    def _wire_events(self) -> None:
        self.refresh_windows_button.clicked.connect(self._handle_refresh_windows)
        self.save_config_button.clicked.connect(self._handle_save_config)
        self.start_button.clicked.connect(self._handle_start)
        self.stop_button.clicked.connect(self._handle_stop)

    def _handle_refresh_windows(self) -> None:
        windows = self._window_service.list_windows()
        self.window_list.clear()

        if not windows:
            self.window_list.addItem("No windows are listed yet. Step 2 will add Win32 enumeration.")
            self._append_log("Refresh requested. Window enumeration is not implemented yet.")
            return

        for window in windows:
            self.window_list.addItem(f"{window.title} [HWND={window.hwnd}]")

    def _handle_save_config(self) -> None:
        self._config.click_settings.delay_ms = self.delay_spin.value()
        self._config.click_settings.use_random_delay = self.random_delay_checkbox.isChecked()
        self._config.click_settings.random_min_ms = self.random_min_spin.value()
        self._config.click_settings.random_max_ms = self.random_max_spin.value()
        self._config.click_settings.max_clicks = self.max_clicks_spin.value() or None
        self._config.hotkeys.start_stop = self.start_stop_hotkey.text().strip() or "F8"
        self._config.hotkeys.capture_point = self.capture_hotkey.text().strip() or "F9"

        self._config_store.save(self._config)
        self._append_log(f"Configuration saved to {self._config_store.path}.")

    def _handle_start(self) -> None:
        self._click_engine.start()
        self.status_value.setText(self._click_engine.status.state)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._append_log(self._click_engine.status.last_message)

    def _handle_stop(self) -> None:
        self._click_engine.stop()
        self.status_value.setText(self._click_engine.status.state)
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._append_log(self._click_engine.status.last_message)

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
