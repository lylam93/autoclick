from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.domain.models import AppConfig, TargetWindow
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
        self._discovered_windows: dict[int, TargetWindow] = {}

        self.setWindowTitle("Advanced Background Auto-Clicker")
        self.resize(1080, 760)
        self.setMinimumSize(920, 680)

        self._build_ui()
        self._populate_from_config(self._config)
        self._wire_events()
        self._append_log("Python + PySide6 scaffold is ready.")
        self._sync_runtime_status()
        self._handle_refresh_windows()

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
            "Step 3: background click dispatch is wired through Win32 messages, with a test action ready for Notepad or browser targets."
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

        self.target_meta_value = QLabel("HWND: -, Click HWND: -, Class: -, PID: -")
        self.target_meta_value.setProperty("role", "muted")

        self.window_list = QListWidget()
        self.window_list.setAlternatingRowColors(True)

        buttons = QHBoxLayout()
        self.refresh_windows_button = QPushButton("Refresh Windows")
        self.use_selected_window_button = QPushButton("Use Selected")
        self.use_selected_window_button.setEnabled(False)
        self.pick_window_button = QPushButton("Crosshair Picker")
        self.pick_window_button.setEnabled(False)
        buttons.addWidget(self.refresh_windows_button)
        buttons.addWidget(self.use_selected_window_button)
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

        self.capture_hint = QLabel(
            "Background click test uses the current primary point. Hotkey capture becomes active in Step 4."
        )
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
        self.test_click_button = QPushButton("Test Background Click")
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        layout.addWidget(self.save_config_button)
        layout.addWidget(self.test_click_button)
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
        self._render_target_window(config.target_window)

    def _wire_events(self) -> None:
        self.refresh_windows_button.clicked.connect(self._handle_refresh_windows)
        self.use_selected_window_button.clicked.connect(self._handle_apply_selected_window)
        self.window_list.currentItemChanged.connect(self._handle_window_selection_changed)
        self.window_list.itemDoubleClicked.connect(self._handle_window_item_double_clicked)
        self.save_config_button.clicked.connect(self._handle_save_config)
        self.test_click_button.clicked.connect(self._handle_test_background_click)
        self.start_button.clicked.connect(self._handle_start)
        self.stop_button.clicked.connect(self._handle_stop)

    def _handle_refresh_windows(self) -> None:
        windows = self._window_service.list_windows()
        self._discovered_windows = {window.hwnd: window for window in windows if window.hwnd is not None}
        self.window_list.clear()

        if not windows:
            self.window_list.addItem("No visible titled windows were found.")
            self.use_selected_window_button.setEnabled(False)
            self._append_log("Refresh complete. No visible titled windows were found.")
            return

        selected_hwnd = self._config.target_window.hwnd
        selected_item: QListWidgetItem | None = None

        for window in windows:
            item = QListWidgetItem(self._format_window_item(window))
            item.setData(Qt.ItemDataRole.UserRole, window)
            self.window_list.addItem(item)

            if selected_hwnd and window.hwnd == selected_hwnd:
                selected_item = item

        if selected_item is not None:
            self.window_list.setCurrentItem(selected_item)

        self._append_log(f"Refresh complete. Found {len(windows)} visible titled windows.")

    def _handle_window_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        has_selection = current is not None and current.data(Qt.ItemDataRole.UserRole) is not None
        self.use_selected_window_button.setEnabled(has_selection)

    def _handle_window_item_double_clicked(self, _item: QListWidgetItem) -> None:
        self._handle_apply_selected_window()

    def _handle_apply_selected_window(self) -> None:
        item = self.window_list.currentItem()
        if item is None:
            self._append_log("Select a window first.")
            return

        selected_window = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(selected_window, TargetWindow):
            self._append_log("The selected row does not contain a valid window target.")
            return

        self._set_target_window(selected_window)
        self._append_log(
            f"Selected target window: {selected_window.title} "
            f"(HWND={selected_window.hwnd}, Class={selected_window.class_name or '-'})"
        )

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

    def _handle_test_background_click(self) -> None:
        if self._config.target_window.hwnd is None:
            self._append_log("Select and apply a target window before testing background click.")
            return

        resolved_target = self._window_service.resolve_click_target(self._config.target_window)
        if resolved_target is None:
            self._append_log("The selected target window is no longer valid.")
            return

        self._set_target_window(resolved_target)
        point = self._config.points[0]
        result = self._click_engine.send_test_click(
            resolved_target,
            point,
            button=self._config.click_settings.mouse_button,
            use_post_message=False,
        )

        if resolved_target.child_hwnd and resolved_target.child_hwnd != resolved_target.hwnd:
            self._append_log(
                f"Resolved effective click target to child HWND {resolved_target.child_hwnd} "
                f"({resolved_target.class_name or 'UnknownClass'})."
            )

        self._sync_runtime_status()
        self._append_log(result.message)

    def _handle_start(self) -> None:
        self._click_engine.start()
        self._sync_runtime_status()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self._append_log(self._click_engine.status.last_message)

    def _handle_stop(self) -> None:
        self._click_engine.stop()
        self._sync_runtime_status()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._append_log(self._click_engine.status.last_message)

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _set_target_window(self, target_window: TargetWindow) -> None:
        self._config.target_window = replace(target_window)
        self._render_target_window(self._config.target_window)

    def _render_target_window(self, target_window: TargetWindow) -> None:
        if target_window.hwnd is None:
            self.target_title_value.setText("No target selected")
            self.target_meta_value.setText("HWND: -, Click HWND: -, Class: -, PID: -")
            return

        self.target_title_value.setText(target_window.title or "Selected target")
        self.target_meta_value.setText(
            f"HWND: {target_window.hwnd or '-'}, "
            f"Click HWND: {target_window.effective_hwnd or '-'}, "
            f"Class: {target_window.class_name or '-'}, "
            f"PID: {target_window.process_id or '-'}"
        )

    def _sync_runtime_status(self) -> None:
        self.status_value.setText(self._click_engine.status.state)
        self.click_count_value.setText(
            f"Completed clicks: {self._click_engine.status.completed_clicks}"
        )

    def _format_window_item(self, target_window: TargetWindow) -> str:
        class_name = target_window.class_name or "UnknownClass"
        process_id = target_window.process_id if target_window.process_id is not None else "-"
        return (
            f"{target_window.title} | "
            f"Class={class_name} | "
            f"PID={process_id} | "
            f"HWND={target_window.hwnd}"
        )
