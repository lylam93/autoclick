from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from autoclicker.domain.models import AppConfig, RuntimeStatus, TargetWindow
from autoclicker.services.click_engine import ClickEngine
from autoclicker.services.config_store import ConfigStore
from autoclicker.services.hotkey_service import HotkeyService
from autoclicker.services.window_service import WindowService
from autoclicker.ui.hotkey_edit import HotkeyLineEdit


class HotkeyBridge(QObject):
    toggle_requested = Signal()
    capture_requested = Signal()


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
        self._pending_config_message = self._config_store.last_message
        self._discovered_windows: dict[int, TargetWindow] = {}
        self._hotkey_bridge = HotkeyBridge(self)
        self._last_terminal_message = self._click_engine.status.last_message
        self._pick_window_pending = False

        self.setWindowTitle("Advanced Background Auto-Clicker")
        self.resize(1080, 760)
        self.setMinimumSize(920, 680)

        self._build_ui()
        self._populate_from_config(self._config)
        self._wire_events()
        self._start_status_timer()
        self._append_log("Python + PySide6 scaffold is ready.")
        if self._pending_config_message:
            self._append_log(self._pending_config_message)
        self._sync_runtime_status()
        self._sync_action_states()
        self._apply_hotkeys(log_success=True)
        self._handle_refresh_windows()
        self._maybe_warn_about_default_point()

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
            "Step 9: the MVP now adds versioned persistence, runtime packaging support, and the delivery controls and crosshair picker from the earlier steps."
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

        picker_hint = QLabel(
            "Use Refresh Windows for the normal list, or Crosshair Picker to hover the real cursor over any desktop window and grab it after a short delay."
        )
        picker_hint.setProperty("role", "muted")
        picker_hint.setWordWrap(True)

        buttons = QHBoxLayout()
        self.refresh_windows_button = QPushButton("Refresh Windows")
        self.use_selected_window_button = QPushButton("Use Selected")
        self.use_selected_window_button.setEnabled(False)
        self.pick_window_button = QPushButton("Crosshair Picker")
        buttons.addWidget(self.refresh_windows_button)
        buttons.addWidget(self.use_selected_window_button)
        buttons.addWidget(self.pick_window_button)

        layout.addWidget(self.target_title_value)
        layout.addWidget(self.target_meta_value)
        layout.addWidget(self.window_list, 1)
        layout.addWidget(picker_hint)
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

        self.mouse_button_combo = QComboBox()
        self.mouse_button_combo.addItem("Left Click", "left")
        self.mouse_button_combo.addItem("Right Click", "right")

        self.delivery_mode_combo = QComboBox()
        self.delivery_mode_combo.addItem("SendMessage", "send")
        self.delivery_mode_combo.addItem("PostMessage", "post")

        self.primary_point_value = QLabel("(0, 0)")
        self.primary_point_value.setStyleSheet("font-size: 12pt; font-weight: 600;")

        self.capture_point_button = QPushButton("Capture Cursor Position")

        delivery_hint = QLabel(
            "SendMessage is the default path. If the target ignores it, switch to PostMessage and retest before starting a long loop."
        )
        delivery_hint.setProperty("role", "muted")
        delivery_hint.setWordWrap(True)

        self.capture_hint = QLabel(
            "Move the real cursor over the target window, then capture. Start uses the current point, button, delivery mode, delay profile, max-click limit, and hotkeys shown here."
        )
        self.capture_hint.setProperty("role", "muted")
        self.capture_hint.setWordWrap(True)

        form.addRow("Base delay", self.delay_spin)
        form.addRow("", self.random_delay_checkbox)
        form.addRow("Random minimum", self.random_min_spin)
        form.addRow("Random maximum", self.random_max_spin)
        form.addRow("Max clicks", self.max_clicks_spin)
        form.addRow("Mouse button", self.mouse_button_combo)
        form.addRow("Delivery mode", self.delivery_mode_combo)
        form.addRow("", delivery_hint)
        form.addRow("Primary point", self.primary_point_value)
        form.addRow("", self.capture_point_button)
        form.addRow("", self.capture_hint)
        return group

    def _build_hotkeys_group(self) -> QGroupBox:
        group = QGroupBox("Hotkeys")
        form = QFormLayout(group)
        form.setSpacing(12)

        self.start_stop_hotkey = HotkeyLineEdit()
        self.capture_hotkey = HotkeyLineEdit()
        self.apply_hotkeys_button = QPushButton("Apply Hotkeys")
        self.hotkey_status_value = QLabel("Global hotkeys are not registered.")
        self.hotkey_status_value.setWordWrap(True)
        self.hotkey_status_value.setProperty("role", "muted")

        hotkey_note = QLabel(
            "Click an input, press a combination like F8 or Ctrl+Shift+S, then apply. These hotkeys work even when the app is not focused."
        )
        hotkey_note.setWordWrap(True)
        hotkey_note.setProperty("role", "muted")

        form.addRow("Start / Stop", self.start_stop_hotkey)
        form.addRow("Get Position", self.capture_hotkey)
        form.addRow("", self.apply_hotkeys_button)
        form.addRow("", self.hotkey_status_value)
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
        self._set_combo_value(self.mouse_button_combo, config.click_settings.mouse_button, fallback="left")
        self._set_combo_value(self.delivery_mode_combo, config.click_settings.delivery_mode, fallback="send")
        self.start_stop_hotkey.setText(config.hotkeys.start_stop)
        self.capture_hotkey.setText(config.hotkeys.capture_point)

        point = config.points[0]
        self._render_primary_point(point.x, point.y)
        self._render_target_window(config.target_window)
        self._sync_delay_input_states()

    def _wire_events(self) -> None:
        self.refresh_windows_button.clicked.connect(self._handle_refresh_windows)
        self.use_selected_window_button.clicked.connect(self._handle_apply_selected_window)
        self.pick_window_button.clicked.connect(self._handle_pick_window_from_cursor)
        self.window_list.currentItemChanged.connect(self._handle_window_selection_changed)
        self.window_list.itemDoubleClicked.connect(self._handle_window_item_double_clicked)
        self.random_delay_checkbox.toggled.connect(self._sync_delay_input_states)
        self.capture_point_button.clicked.connect(self._handle_capture_point)
        self.apply_hotkeys_button.clicked.connect(self._handle_apply_hotkeys)
        self.save_config_button.clicked.connect(self._handle_save_config)
        self.test_click_button.clicked.connect(self._handle_test_background_click)
        self.start_button.clicked.connect(self._handle_start)
        self.stop_button.clicked.connect(self._handle_stop)
        self._hotkey_bridge.toggle_requested.connect(self._handle_hotkey_toggle)
        self._hotkey_bridge.capture_requested.connect(self._handle_hotkey_capture)

    def _start_status_timer(self) -> None:
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(200)
        self._status_timer.timeout.connect(self._handle_status_timer)
        self._status_timer.start()

    def _handle_status_timer(self) -> None:
        status = self._click_engine.status
        self._sync_runtime_status(status)
        self._sync_action_states(status)

        is_busy = status.state in {"Running", "Stopping"}
        if not is_busy and status.state in {"Stopped", "Error"} and status.last_message:
            if status.last_message != self._last_terminal_message:
                self._append_log(status.last_message)
                self._last_terminal_message = status.last_message

    def _handle_refresh_windows(self) -> None:
        windows = self._window_service.list_windows()
        self._discovered_windows = {window.hwnd: window for window in windows if window.hwnd is not None}
        self.window_list.clear()

        if not windows:
            item = QListWidgetItem("No visible titled windows were found.")
            item.setData(Qt.ItemDataRole.UserRole, None)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.window_list.addItem(item)
            self._sync_action_states()
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

        self._restore_saved_target_from_config(log_missing=False)
        self._sync_action_states()
        self._append_log(f"Refresh complete. Found {len(windows)} visible titled windows.")

    def _handle_window_selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        _ = current
        self._sync_action_states()

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

    def _handle_pick_window_from_cursor(self) -> None:
        if self._is_engine_busy():
            self._append_log("Stop the running click loop before using the cursor picker.")
            return

        if self._pick_window_pending:
            self._append_log("The cursor picker is already waiting for a target.")
            return

        self._pick_window_pending = True
        self.pick_window_button.setText("Picking in 2s...")
        self._sync_action_states()
        self._append_log(
            "Move the real cursor over the target window now. The picker will capture the window under the cursor in 2 seconds."
        )
        QTimer.singleShot(2000, self._finish_pick_window_from_cursor)

    def _finish_pick_window_from_cursor(self) -> None:
        self._pick_window_pending = False
        self.pick_window_button.setText("Crosshair Picker")

        if self._is_engine_busy():
            self._append_log("The cursor picker was cancelled because the click loop started running.")
            self._sync_action_states()
            return

        picked_target = self._window_service.pick_window_from_cursor()
        if picked_target is None or picked_target.hwnd is None:
            self._append_log("The cursor picker could not resolve a valid target window under the cursor.")
            self._sync_action_states()
            return

        previous_effective_hwnd = self._config.target_window.effective_hwnd
        self._set_target_window(picked_target)
        self._maybe_log_effective_target(previous_effective_hwnd, picked_target)
        self._append_log(
            f"Picked target window from cursor: {picked_target.title or 'Selected target'} "
            f"(HWND={picked_target.hwnd}, Click HWND={picked_target.effective_hwnd or '-'})."
        )
        self._sync_action_states()

    def _handle_capture_point(self) -> None:
        if self._pick_window_pending:
            self._append_log("Wait for the cursor picker to finish before capturing a point.")
            return

        if self._is_engine_busy():
            self._append_log("Stop the running click loop before capturing a new point.")
            return

        resolved_target = self._resolve_current_target("capturing a point")
        if resolved_target is None:
            return

        capture_result = self._window_service.capture_cursor_point(resolved_target)
        if not capture_result.success:
            self._append_log(capture_result.message)
            return

        primary_point = self._config.points[0]
        primary_point.x = capture_result.client_x
        primary_point.y = capture_result.client_y
        self._render_primary_point(primary_point.x, primary_point.y)
        self._append_log(capture_result.message)

    def _handle_apply_hotkeys(self) -> None:
        self._update_config_from_form()
        self._apply_hotkeys(log_success=True)

    def _handle_save_config(self) -> None:
        self._update_config_from_form()
        if self._save_config(log_to_ui=True):
            self._apply_hotkeys(log_success=True)

    def _handle_test_background_click(self) -> None:
        if self._pick_window_pending:
            self._append_log("Wait for the cursor picker to finish before sending a test click.")
            return

        if self._is_engine_busy():
            self._append_log("Stop the running click loop before sending a test click.")
            return

        self._update_config_from_form()
        self._maybe_warn_about_default_point()
        resolved_target = self._resolve_current_target("testing background click")
        if resolved_target is None:
            return

        point = self._config.points[0]
        result = self._click_engine.send_test_click(
            resolved_target,
            point,
            button=self._config.click_settings.mouse_button,
            use_post_message=self._current_use_post_message(),
        )

        self._sync_runtime_status()
        self._append_log(result.message)

    def _handle_start(self) -> None:
        if self._pick_window_pending:
            self._append_log("Wait for the cursor picker to finish before starting the click loop.")
            return

        if self._is_engine_busy():
            self._append_log("Background click loop is already running.")
            return

        self._update_config_from_form()
        self._maybe_warn_about_default_point()
        resolved_target = self._resolve_current_target("starting the click loop")
        if resolved_target is None:
            return

        started = self._click_engine.start_loop(
            resolved_target,
            self._config.points[0],
            self._config.click_settings,
            use_post_message=self._current_use_post_message(),
        )
        self._sync_runtime_status()
        self._sync_action_states()

        status = self._click_engine.status
        if status.last_message:
            self._append_log(status.last_message)
            self._last_terminal_message = status.last_message

        if not started:
            return

    def _handle_stop(self) -> None:
        self._click_engine.stop()
        self._sync_runtime_status()
        self._sync_action_states()

        status = self._click_engine.status
        if status.last_message:
            self._append_log(status.last_message)
            self._last_terminal_message = status.last_message

    def _handle_hotkey_toggle(self) -> None:
        if self._click_engine.status.state in {"Running", "Stopping"}:
            self._handle_stop()
            return
        self._handle_start()

    def _handle_hotkey_capture(self) -> None:
        self._handle_capture_point()

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _apply_hotkeys(self, *, log_success: bool) -> bool:
        result = self._hotkey_service.register(
            self._config.hotkeys,
            on_start_stop=self._hotkey_bridge.toggle_requested.emit,
            on_capture_point=self._hotkey_bridge.capture_requested.emit,
        )

        if result.normalized_start_stop:
            self.start_stop_hotkey.setText(result.normalized_start_stop)
            self._config.hotkeys.start_stop = result.normalized_start_stop
        if result.normalized_capture_point:
            self.capture_hotkey.setText(result.normalized_capture_point)
            self._config.hotkeys.capture_point = result.normalized_capture_point

        self.hotkey_status_value.setText(result.message)
        if result.success:
            self.hotkey_status_value.setStyleSheet("color: #b5bdcc;")
        else:
            self.hotkey_status_value.setStyleSheet("color: #ffb4a2;")

        if result.success and not log_success:
            return True

        self._append_log(result.message)
        return result.success

    def _save_config(self, *, log_to_ui: bool) -> bool:
        try:
            self._config_store.save(self._config)
        except OSError as exc:
            if log_to_ui:
                self._append_log(
                    f"Could not save configuration to {self._config_store.path.resolve()} ({exc})."
                )
            return False

        if log_to_ui and self._config_store.last_message:
            self._append_log(self._config_store.last_message)
        return True

    def _restore_saved_target_from_config(self, *, log_missing: bool) -> None:
        saved_target = self._config.target_window
        if saved_target.hwnd is None:
            return

        restored_target = self._window_service.rehydrate_target(saved_target)
        if restored_target is None:
            if log_missing:
                self._append_log(
                    "The saved target window from config is not available right now. Refresh and reselect it if needed."
                )
            return

        previous_parent_hwnd = saved_target.hwnd
        previous_effective_hwnd = saved_target.effective_hwnd
        self._set_target_window(restored_target)
        if (
            restored_target.hwnd != previous_parent_hwnd
            or restored_target.effective_hwnd != previous_effective_hwnd
        ):
            self._append_log(
                f"Restored saved target window from HWND {previous_parent_hwnd} "
                f"to HWND {restored_target.hwnd}."
            )
            self._maybe_log_effective_target(previous_effective_hwnd, restored_target)

    def _is_primary_point_default(self) -> bool:
        point = self._config.points[0]
        return point.x == 0 and point.y == 0

    def _maybe_warn_about_default_point(self) -> None:
        if self._is_primary_point_default():
            self._append_log(
                "Primary point is still the default (0, 0). If the target does not react, capture a real point inside the window first."
            )

    def _set_target_window(self, target_window: TargetWindow) -> None:
        self._config.target_window = replace(target_window)
        self._render_target_window(self._config.target_window)
        self._remember_discovered_window(self._config.target_window)
        self._select_window_in_list(self._config.target_window.hwnd)

    def _remember_discovered_window(self, target_window: TargetWindow) -> None:
        if target_window.hwnd is None:
            return

        display_window = self._window_service.get_window(target_window.hwnd)
        if display_window is None:
            display_window = TargetWindow(
                hwnd=target_window.hwnd,
                title=target_window.title,
                class_name=target_window.class_name,
                process_id=target_window.process_id,
            )

        self._discovered_windows[target_window.hwnd] = display_window
        item = self._find_window_item(target_window.hwnd)

        if item is None:
            if self.window_list.count() == 1 and self.window_list.item(0).data(Qt.ItemDataRole.UserRole) is None:
                self.window_list.clear()

            item = QListWidgetItem(self._format_window_item(display_window))
            item.setData(Qt.ItemDataRole.UserRole, display_window)
            self.window_list.addItem(item)
            return

        item.setText(self._format_window_item(display_window))
        item.setData(Qt.ItemDataRole.UserRole, display_window)

    def _resolve_current_target(self, action_name: str) -> TargetWindow | None:
        if self._config.target_window.hwnd is None:
            self._append_log(f"Select and apply a target window before {action_name}.")
            return None

        previous_parent_hwnd = self._config.target_window.hwnd
        previous_effective_hwnd = self._config.target_window.effective_hwnd
        resolved_target = self._window_service.rehydrate_target(self._config.target_window)
        if resolved_target is None:
            self._append_log("The selected target window is no longer valid. Refresh and select it again.")
            return None

        self._set_target_window(resolved_target)
        if resolved_target.hwnd != previous_parent_hwnd:
            self._append_log(
                f"Restored saved target window from HWND {previous_parent_hwnd} to HWND {resolved_target.hwnd}."
            )
        self._maybe_log_effective_target(previous_effective_hwnd, resolved_target)
        return resolved_target

    def _maybe_log_effective_target(
        self,
        previous_effective_hwnd: int | None,
        target_window: TargetWindow,
    ) -> None:
        child_hwnd = target_window.child_hwnd
        if child_hwnd and child_hwnd != target_window.hwnd and child_hwnd != previous_effective_hwnd:
            self._append_log(
                f"Resolved effective click target to child HWND {child_hwnd} "
                f"({target_window.class_name or 'UnknownClass'})."
            )

    def _find_window_item(self, hwnd: int | None) -> QListWidgetItem | None:
        if hwnd is None:
            return None

        for index in range(self.window_list.count()):
            item = self.window_list.item(index)
            target_window = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(target_window, TargetWindow) and target_window.hwnd == hwnd:
                return item
        return None

    def _select_window_in_list(self, hwnd: int | None) -> bool:
        item = self._find_window_item(hwnd)
        if item is None:
            return False

        self.window_list.setCurrentItem(item)
        return True

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

    def _render_primary_point(self, x: int, y: int) -> None:
        self.primary_point_value.setText(f"({x}, {y})")

    def _sync_runtime_status(self, status: RuntimeStatus | None = None) -> None:
        status = status or self._click_engine.status
        self.status_value.setText(status.state)
        self.click_count_value.setText(f"Completed clicks: {status.completed_clicks}")

    def _sync_action_states(self, status: RuntimeStatus | None = None) -> None:
        status = status or self._click_engine.status
        is_busy = status.state in {"Running", "Stopping"}
        interaction_locked = is_busy or self._pick_window_pending
        selected_item = self.window_list.currentItem()
        has_selection = selected_item is not None and selected_item.data(Qt.ItemDataRole.UserRole) is not None

        self.start_button.setEnabled(not interaction_locked)
        self.stop_button.setEnabled(is_busy)
        self.test_click_button.setEnabled(not interaction_locked)
        self.capture_point_button.setEnabled(not interaction_locked)
        self.save_config_button.setEnabled(not interaction_locked)
        self.refresh_windows_button.setEnabled(not interaction_locked)
        self.window_list.setEnabled(not interaction_locked)
        self.use_selected_window_button.setEnabled(not interaction_locked and has_selection)
        self.pick_window_button.setEnabled(not interaction_locked)
        self.pick_window_button.setText("Picking in 2s..." if self._pick_window_pending else "Crosshair Picker")
        self.apply_hotkeys_button.setEnabled(not interaction_locked)
        self.start_stop_hotkey.setEnabled(not interaction_locked)
        self.capture_hotkey.setEnabled(not interaction_locked)
        self.random_delay_checkbox.setEnabled(not interaction_locked)
        self.max_clicks_spin.setEnabled(not interaction_locked)
        self.mouse_button_combo.setEnabled(not interaction_locked)
        self.delivery_mode_combo.setEnabled(not interaction_locked)
        self._sync_delay_input_states()

    def _sync_delay_input_states(self) -> None:
        interaction_locked = self._is_engine_busy() or self._pick_window_pending
        use_random_delay = self.random_delay_checkbox.isChecked()

        self.delay_spin.setEnabled(not interaction_locked and not use_random_delay)
        self.random_min_spin.setEnabled(not interaction_locked and use_random_delay)
        self.random_max_spin.setEnabled(not interaction_locked and use_random_delay)

    def _set_combo_value(self, combo: QComboBox, value: str, *, fallback: str) -> None:
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(fallback)
        if index < 0:
            index = 0
        combo.setCurrentIndex(index)

    def _current_use_post_message(self) -> bool:
        return self._config.click_settings.delivery_mode == "post"

    def _update_config_from_form(self) -> None:
        self._config.click_settings.delay_ms = self.delay_spin.value()
        self._config.click_settings.use_random_delay = self.random_delay_checkbox.isChecked()
        self._config.click_settings.random_min_ms = self.random_min_spin.value()
        self._config.click_settings.random_max_ms = self.random_max_spin.value()
        self._config.click_settings.max_clicks = self.max_clicks_spin.value() or None
        self._config.click_settings.mouse_button = str(self.mouse_button_combo.currentData() or "left")
        self._config.click_settings.delivery_mode = str(self.delivery_mode_combo.currentData() or "send")
        self._config.hotkeys.start_stop = self.start_stop_hotkey.text().strip() or "F8"
        self._config.hotkeys.capture_point = self.capture_hotkey.text().strip() or "F9"

    def _is_engine_busy(self) -> bool:
        return self._click_engine.status.state in {"Running", "Stopping"}

    def _format_window_item(self, target_window: TargetWindow) -> str:
        class_name = target_window.class_name or "UnknownClass"
        process_id = target_window.process_id if target_window.process_id is not None else "-"
        return (
            f"{target_window.title} | "
            f"Class={class_name} | "
            f"PID={process_id} | "
            f"HWND={target_window.hwnd}"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self._status_timer.stop()
        self._update_config_from_form()
        self._click_engine.stop()
        self._hotkey_service.unregister()
        try:
            self._config_store.save(self._config)
        except OSError:
            pass
        super().closeEvent(event)




