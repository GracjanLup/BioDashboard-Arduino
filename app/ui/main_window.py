from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.bioscore import BioScoreCalculator, status_for_score
from app.charts import RealtimeChartWidget
from app.measurements import (
    MEASUREMENT_SPECS,
    final_test_value,
    format_test_value,
    gsr_assessment_detail,
    gsr_assessment_label,
    heart_status,
    invalid_measurement_reason,
    is_measurement_command,
    line_matches_command,
    measurement_name,
    measurement_spec,
    numeric_value_from_raw_line,
    spo2_status,
    temperature_status,
    value_for_command,
)
from app.models import STATUS_NORMAL, SensorSample
from app.serial.arduino_serial import ArduinoSerialWorker, available_ports
from app.serial.parser import ParsedMessage
from app.serial.protocol import SERIAL_BAUD_RATE, ArduinoCommand
from app.settings import AppSettings, SettingsManager
from app.storage import SessionStore, timestamped_path
from app.ui.theme import (
    THEME_HIGH_CONTRAST_DARK,
    THEME_MEDICAL_DARK,
    apply_theme,
    color_for_status,
)
from app.ui.sample_table_model import SampleTableModel
from app.ui.widgets import EventLog, MetricCard, StatusIndicator


BIOMONITOR_VIEW = "BIOMONITOR"


class MainWindow(QMainWindow):
    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        super().__init__()
        self.setWindowTitle("BioMonitor Dashboard")
        self.resize(1480, 920)

        self.settings_manager = settings_manager or SettingsManager()
        self.settings = self.settings_manager.load()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, self.settings.theme)
        storage_warning = ""
        try:
            self.session_store = SessionStore(self.settings.data_folder / "biomonitor.sqlite3")
        except (OSError, sqlite3.Error) as exc:
            fallback_folder = AppSettings().data_folder
            self.settings.data_folder = fallback_folder
            self.session_store = SessionStore(fallback_folder / "biomonitor.sqlite3")
            storage_warning = (
                f"Could not open the configured data folder. Using {fallback_folder}. Reason: {exc}"
            )
        self.score_calculator = BioScoreCalculator()

        self.serial_worker: ArduinoSerialWorker | None = None
        self.latest_readings = SensorSample(timestamp=datetime.now())
        self.selected_command = BIOMONITOR_VIEW
        self.current_test_sample_count = 0
        self.last_raw_line = "No serial data received yet."
        self.active_test_command: str | None = None
        self.active_test_started_at: datetime | None = None
        self.active_test_duration_seconds = 0
        self.active_test_values: list[float] = []
        self._invalid_reason_by_command: dict[str, str] = {}

        self.test_timer = QTimer(self)
        self.test_timer.setInterval(1000)
        self.test_timer.timeout.connect(self._update_test_progress)

        self.table_model = SampleTableModel()
        self._build_ui()
        self._populate_ports(self.settings.com_port)
        self._apply_settings_to_controls()
        self._set_connected(False)
        self._update_mode_indicator(ArduinoCommand.STOP.value)
        self._restore_saved_dashboard_data()
        self._refresh_history()
        self.event_log.append_event(
            f"Application ready. Loaded {len(self.session_store.samples)} saved samples."
        )
        if storage_warning:
            self.event_log.append_event(storage_warning, "ERROR")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._disconnect_serial()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_top_bar())

        body = QWidget()
        body.setObjectName("Body")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        self.dashboard_page = self._build_dashboard_page()
        self.history_page = self._build_history_page()
        self.settings_page = self._build_settings_page()
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.settings_page)
        body_layout.addWidget(self.stack, stretch=1)

        root_layout.addWidget(body, stretch=1)
        self.setCentralWidget(root)

    def _build_top_bar(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(66)

        title = QLabel("BioMonitor Dashboard")
        title.setObjectName("AppTitle")

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(150)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(lambda: self._populate_ports(self._current_port()))

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("PrimaryButton")
        self.connect_button.clicked.connect(self._connect_serial)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self._disconnect_serial)

        self.connection_indicator = StatusIndicator("OFFLINE")
        self.mode_indicator = QLabel("Mode: STOP")
        self.mode_indicator.setObjectName("ModeIndicator")

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(QLabel("Serial Port"))
        layout.addWidget(self.port_combo)
        layout.addWidget(refresh_button)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.disconnect_button)
        layout.addSpacing(10)
        layout.addWidget(self.connection_indicator)
        layout.addWidget(self.mode_indicator)
        return top_bar

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 18)
        layout.setSpacing(8)

        self.sidebar_group = QButtonGroup(self)
        self.sidebar_group.setExclusive(True)

        buttons = [
            ("BioMonitor", lambda: self._select_live_mode(BIOMONITOR_VIEW)),
            (
                MEASUREMENT_SPECS[ArduinoCommand.TEMP.value].page_title,
                lambda: self._select_live_mode(ArduinoCommand.TEMP.value),
            ),
            (
                MEASUREMENT_SPECS[ArduinoCommand.BPM.value].page_title,
                lambda: self._select_live_mode(ArduinoCommand.BPM.value),
            ),
            (
                MEASUREMENT_SPECS[ArduinoCommand.GSR.value].page_title,
                lambda: self._select_live_mode(ArduinoCommand.GSR.value),
            ),
            ("Data History", self._show_history_page),
            ("Settings", self._show_settings_page),
        ]

        for index, (label, callback) in enumerate(buttons):
            button = QPushButton(label)
            button.setObjectName("SidebarButton")
            button.setCheckable(True)
            button.clicked.connect(callback)
            self.sidebar_group.addButton(button, index)
            layout.addWidget(button)

        self.sidebar_group.button(0).setChecked(True)
        layout.addStretch()
        return sidebar

    def _build_dashboard_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        content = QWidget()
        content.setObjectName("PageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(18)

        self.live_page_title = QLabel("BioMonitor")
        self.live_page_title.setObjectName("SectionTitle")
        self.live_page_title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(self.live_page_title)

        self.test_guide_panel = self._build_test_guide_panel()
        layout.addWidget(self.test_guide_panel)

        self.controls_title = _section_title("Controls")
        layout.addWidget(self.controls_title)
        self.controls_panel = self._build_controls_panel()
        layout.addWidget(self.controls_panel)

        self.metrics_title = _section_title("Live Metrics")
        layout.addWidget(self.metrics_title)
        self.metrics_grid = QGridLayout()
        self.metrics_grid.setSpacing(14)

        self.temperature_card = MetricCard("Temperature", "\N{DEGREE SIGN}C")
        self.heart_card = MetricCard("Heart Rate", "BPM")
        self.spo2_card = MetricCard("SpO2", "%")
        self.gsr_card = MetricCard("GSR", "ADC")
        self.status_card = MetricCard("System Status")
        self.status_card.value_label.setText(STATUS_NORMAL)
        self.status_card.delta_label.setText("Baseline not configured")
        self.status_card.set_status(STATUS_NORMAL)

        self.metrics_grid.addWidget(self.temperature_card, 0, 0)
        self.metrics_grid.addWidget(self.heart_card, 0, 1)
        self.metrics_grid.addWidget(self.spo2_card, 0, 2)
        self.metrics_grid.addWidget(self.gsr_card, 0, 3)
        self.metrics_grid.addWidget(self.status_card, 0, 4)
        for column in range(5):
            self.metrics_grid.setColumnStretch(column, 1)

        layout.addLayout(self.metrics_grid)

        self.charts_title = _section_title("Real-Time Charts")
        layout.addWidget(self.charts_title)
        charts_grid = QGridLayout()
        charts_grid.setSpacing(14)

        self.temperature_chart = RealtimeChartWidget(
            "Temperature", "\N{DEGREE SIGN}C", "#63b3ed", y_range=(-20.0, 100.0)
        )
        self.heart_chart = RealtimeChartWidget("Heart Rate", "BPM", "#e78aa0")
        self.spo2_chart = RealtimeChartWidget("SpO2", "%", "#f6ad55", y_range=(70.0, 100.0))
        self.gsr_chart = RealtimeChartWidget("GSR", "ADC", "#68d391")

        charts = [
            self.temperature_chart,
            self.heart_chart,
            self.spo2_chart,
            self.gsr_chart,
        ]
        for chart in charts:
            chart.setMinimumHeight(245)

        charts_grid.addWidget(self.temperature_chart, 0, 0)
        charts_grid.addWidget(self.heart_chart, 0, 1)
        charts_grid.addWidget(self.gsr_chart, 1, 0)
        charts_grid.addWidget(self.spo2_chart, 1, 1)
        layout.addLayout(charts_grid)

        layout.addWidget(_section_title("Event Log"))
        self.event_log = EventLog()
        layout.addWidget(self.event_log)

        scroll.setWidget(content)
        self._apply_live_mode_visibility()
        self._update_selected_mode_controls()
        return scroll

    def _build_test_guide_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelCard")

        self.test_guide_title = QLabel("Test Protocol")
        self.test_guide_title.setObjectName("SectionTitle")
        self.test_guide_body = QLabel()
        self.test_guide_body.setObjectName("MutedLabel")
        self.test_guide_body.setWordWrap(True)
        self.test_guide_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.test_guide_body.setStyleSheet("font-size: 13px; line-height: 1.35;")

        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(14)
        status_grid.setVerticalSpacing(10)
        self.expected_serial_label = _detail_label("Expected Arduino data", "--")
        self.last_serial_label = _detail_label("Last Arduino line", self.last_raw_line)
        self.last_result_label = _detail_label("Latest valid result", "Waiting for Start Test.")
        self.test_state_label = _detail_label("Test state", "Ready.")
        for index, widget in enumerate(
            [
                self.expected_serial_label,
                self.last_serial_label,
                self.last_result_label,
                self.test_state_label,
            ]
        ):
            status_grid.addWidget(widget, index // 2, index % 2)

        self.test_progress_label = QLabel("Progress: not started")
        self.test_progress_label.setObjectName("MutedLabel")
        self.test_progress_bar = QProgressBar()
        self.test_progress_bar.setRange(0, 100)
        self.test_progress_bar.setValue(0)
        self.test_progress_bar.setTextVisible(True)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        layout.addWidget(self.test_guide_title)
        layout.addWidget(self.test_guide_body)
        layout.addLayout(status_grid)
        layout.addWidget(self.test_progress_label)
        layout.addWidget(self.test_progress_bar)
        return panel

    def _build_controls_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PanelCard")

        self.start_button = QPushButton("Start Test")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self._start_measurement)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_measurement)

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        for button in [self.start_button, self.stop_button]:
            layout.addWidget(button)
        layout.addStretch()
        return panel

    def _build_history_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PlainPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(_section_title("Data History"))

        self.history_summary = QLabel("No samples recorded.")
        self.history_summary.setObjectName("MutedLabel")
        layout.addWidget(self.history_summary)

        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.table_view, stretch=1)

        actions = QHBoxLayout()
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh_history)
        export_button = QPushButton("Export CSV")
        export_button.clicked.connect(self._export_csv)
        actions.addWidget(refresh_button)
        actions.addWidget(export_button)
        actions.addStretch()
        layout.addLayout(actions)
        return page

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PlainPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(_section_title("Settings"))

        panel = QFrame()
        panel.setObjectName("PanelCard")
        form = QFormLayout(panel)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)

        self.settings_port_combo = QComboBox()
        self.settings_refresh_button = QPushButton("Refresh Ports")
        self.settings_refresh_button.clicked.connect(
            lambda: self._populate_ports(
                str(self.settings_port_combo.currentData() or self.settings.com_port)
            )
        )

        port_row = QHBoxLayout()
        port_row.addWidget(self.settings_port_combo)
        port_row.addWidget(self.settings_refresh_button)
        form.addRow("COM port", port_row)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems([THEME_MEDICAL_DARK, THEME_HIGH_CONTRAST_DARK])
        form.addRow("Theme", self.theme_combo)

        self.data_folder_edit = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self._browse_data_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.data_folder_edit)
        folder_row.addWidget(browse_button)
        form.addRow("Data folder", folder_row)

        save_button = QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save_settings)
        form.addRow("", save_button)

        layout.addWidget(panel)
        layout.addStretch()
        return page

    def _populate_ports(self, selected_port: str | None = None) -> None:
        ports = available_ports()
        combos = [self.port_combo, self.settings_port_combo]

        for combo in combos:
            current = selected_port or combo.currentData() or self.settings.com_port
            combo.blockSignals(True)
            combo.clear()
            if ports:
                for port in ports:
                    combo.addItem(port, port)
                if current and current in ports:
                    combo.setCurrentIndex(ports.index(current))
            else:
                combo.addItem("No serial ports found", "")
            combo.blockSignals(False)

        self.event_log.append_event(
            f"Serial ports refreshed: {', '.join(ports) if ports else 'none'}",
            "INFO",
        )

    def _apply_settings_to_controls(self) -> None:
        self.data_folder_edit.setText(str(self.settings.data_folder))
        theme_index = self.theme_combo.findText(self.settings.theme)
        self.theme_combo.setCurrentIndex(max(theme_index, 0))

    def _current_port(self) -> str:
        data = self.port_combo.currentData()
        return str(data or "")

    def _show_dashboard_page(self) -> None:
        self.stack.setCurrentWidget(self.dashboard_page)

    def _show_history_page(self) -> None:
        self._stop_active_test_for_navigation()
        self._refresh_history()
        self.stack.setCurrentWidget(self.history_page)

    def _show_settings_page(self) -> None:
        self._stop_active_test_for_navigation()
        self.stack.setCurrentWidget(self.settings_page)

    def _stop_active_test_for_navigation(self) -> None:
        if self.active_test_command is not None:
            self._finish_individual_test(stopped_by_user=True)

    def _select_live_mode(self, command: str) -> None:
        if self.active_test_command is not None and command != self.active_test_command:
            self._finish_individual_test(stopped_by_user=True)

        spec = measurement_spec(command)
        if command == BIOMONITOR_VIEW:
            title = "BioMonitor"
        elif spec is not None:
            title = spec.page_title
        else:
            self.event_log.append_event(f"Unsupported view command: {command}", "ERROR")
            return
        self.selected_command = command
        self._clear_invalid_measurement(command)
        self.live_page_title.setText(title)
        self._apply_live_mode_visibility()
        self._update_selected_mode_controls()
        self._show_dashboard_page()
        self._update_mode_indicator(_ready_mode_for_view(command))

    def _apply_live_mode_visibility(self) -> None:
        command = self.selected_command
        show_overview = command == BIOMONITOR_VIEW
        show_temperature = show_overview or command == ArduinoCommand.TEMP.value
        show_heart = show_overview or command == ArduinoCommand.BPM.value
        show_gsr = show_overview or command == ArduinoCommand.GSR.value

        self.controls_title.setVisible(not show_overview)
        self.controls_panel.setVisible(not show_overview)
        self.metrics_title.setText("Latest Results" if show_overview else "Live Metrics")
        self.charts_title.setText("Measurement History" if show_overview else "Real-Time Charts")
        self.metrics_title.setVisible(True)
        self.charts_title.setVisible(True)
        self.temperature_card.setVisible(show_temperature)
        self.heart_card.setVisible(show_heart)
        self.spo2_card.setVisible(show_heart)
        self.gsr_card.setVisible(show_gsr)
        self.status_card.setVisible(show_overview)

        visible_columns = {
            0: show_temperature,
            1: show_heart,
            2: show_heart,
            3: show_gsr,
            4: show_overview,
        }
        for column, visible in visible_columns.items():
            self.metrics_grid.setColumnStretch(column, 1 if visible else 0)

        self.temperature_chart.setVisible(show_temperature)
        self.heart_chart.setVisible(show_heart)
        self.spo2_chart.setVisible(show_heart)
        self.gsr_chart.setVisible(show_gsr)

    def _update_selected_mode_controls(self) -> None:
        command = self.selected_command
        is_test = is_measurement_command(command)
        self.test_guide_panel.setVisible(is_test)
        if not is_test:
            return

        self.start_button.setText("Start Test")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        spec = measurement_spec(command)
        if spec is None:
            return

        self.test_guide_title.setText(spec.test_title)
        self.test_guide_body.setText(spec.instructions)
        self.expected_serial_label.setText(f"Expected Arduino data\n{spec.expected_serial}")
        if self.active_test_command == command:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            return

        self.last_serial_label.setText(f"Last Arduino line\n{self.last_raw_line}")
        self.last_result_label.setText("Latest valid result\nWaiting for Start Test.")
        self.test_state_label.setText("Test state\nReady. Connect Arduino, then click Start Test.")
        self.test_progress_bar.setValue(0)
        self.test_progress_label.setText(
            f"Progress: test duration {spec.duration_seconds} seconds."
        )

    def _is_serial_connected(self) -> bool:
        worker = self.serial_worker
        return bool(worker is not None and worker.isRunning())

    def _connect_serial(self) -> None:
        if self.serial_worker is not None and self.serial_worker.isRunning():
            self.event_log.append_event("Serial connection is already active.", "INFO")
            return
        if self.serial_worker is not None:
            self.serial_worker.deleteLater()
            self.serial_worker = None

        port = self._current_port()
        if not port:
            self.event_log.append_event("Select a serial port before connecting.", "ERROR")
            return

        self.settings.com_port = port
        try:
            self.settings_manager.save(self.settings)
        except OSError as exc:
            self.event_log.append_event(
                f"Could not remember the selected serial port: {exc}",
                "ERROR",
            )

        worker = ArduinoSerialWorker(port, parent=self)
        worker.connected.connect(self._on_serial_connected)
        worker.disconnected.connect(self._on_serial_disconnected)
        worker.finished.connect(self._on_serial_worker_finished)
        worker.raw_received.connect(self._on_raw_serial_received)
        worker.sample_received.connect(self._on_sample_received)
        worker.error.connect(self._on_serial_error)
        self.serial_worker = worker
        worker.start()
        self.event_log.append_event(f"Connecting to {port} at {SERIAL_BAUD_RATE} baud.")

    def _disconnect_serial(self) -> None:
        worker = self.serial_worker
        if worker is None:
            self._set_connected(False)
            return

        if worker.isRunning():
            worker.send_command(ArduinoCommand.STOP.value)
            worker.stop()
            if not worker.wait(3000):
                self.event_log.append_event(
                    "Serial worker did not stop cleanly; forcing shutdown.", "ERROR"
                )
                worker.terminate()
                worker.wait(1000)
        if self.serial_worker is worker:
            self.serial_worker = None
        self._set_connected(False)
        self._update_mode_indicator(ArduinoCommand.STOP.value)
        self.event_log.append_event("Disconnected from Arduino.")

    @Slot(str)
    def _on_serial_connected(self, port: str) -> None:
        self._set_connected(True)
        self.event_log.append_event(f"Connected to Arduino on {port}.")
        self._update_mode_indicator(_ready_mode_for_view(self.selected_command))

    @Slot()
    def _on_serial_disconnected(self) -> None:
        self._set_connected(False)
        self._update_mode_indicator(ArduinoCommand.STOP.value)

    @Slot()
    def _on_serial_worker_finished(self) -> None:
        worker = self.sender()
        if worker is self.serial_worker:
            self.serial_worker = None
        if worker is not None:
            worker.deleteLater()

    @Slot(str)
    def _on_serial_error(self, message: str) -> None:
        self.event_log.append_event(message, "ERROR")

    @Slot(str)
    def _on_raw_serial_received(self, line: str) -> None:
        self.last_raw_line = line
        if is_measurement_command(self.selected_command):
            self.last_serial_label.setText(f"Last Arduino line\n{line}")
            if self.active_test_command is not None:
                fallback_value = numeric_value_from_raw_line(line, self.active_test_command)
                if fallback_value is not None:
                    self._collect_individual_test_value(fallback_value, line)
                    return
            if not line_matches_command(line, self.selected_command):
                self.test_state_label.setText(
                    "Test state\nArduino is connected, but this line is not a valid "
                    "result for this test."
                )

    def _set_connected(self, connected: bool) -> None:
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        if connected:
            self.connection_indicator.set_status("CONNECTED")
        else:
            self.connection_indicator.set_status("OFFLINE")

    def _send_command(self, command: str, source: str) -> bool:
        worker = self.serial_worker
        if worker is None or not worker.isRunning():
            self.event_log.append_event(
                f"{source}: connect to Arduino before sending {command}.", "ERROR"
            )
            return False

        if not worker.send_command(command):
            return False

        self._update_mode_indicator(command)
        self.event_log.append_event(f"{source}: sent Arduino command {command}.", "USER")
        return True

    def _update_mode_indicator(self, mode: str) -> None:
        self.mode_indicator.setText(f"Mode: {mode}")

    def _start_measurement(self) -> None:
        self._start_individual_test()

    def _stop_measurement(self) -> None:
        if self.active_test_command is not None:
            self._finish_individual_test(stopped_by_user=True)
            return
        self._send_command(ArduinoCommand.STOP.value, source="Stop")

    def _start_individual_test(self) -> None:
        if self.active_test_command is not None:
            self.event_log.append_event("A test is already running.", "INFO")
            return

        spec = measurement_spec(self.selected_command)
        if spec is None:
            self.event_log.append_event("This test is not available yet.", "ERROR")
            return

        if not self._send_command(self.selected_command, source=self.start_button.text()):
            return

        self.active_test_command = self.selected_command
        self.active_test_started_at = datetime.now()
        self.active_test_duration_seconds = spec.duration_seconds
        self.active_test_values.clear()
        self.current_test_sample_count = 0
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.test_progress_bar.setValue(0)
        self.last_result_label.setText("Latest valid result\nCollecting samples...")
        self.test_state_label.setText(
            "Test state\nHold position steady until the progress bar completes."
        )
        self.test_timer.start()
        self.event_log.append_event(
            f"{spec.page_title}: collecting one final result for {spec.duration_seconds} seconds.",
            "USER",
        )

    def _update_test_progress(self) -> None:
        if self.active_test_command is None or self.active_test_started_at is None:
            self.test_timer.stop()
            return

        elapsed = int((datetime.now() - self.active_test_started_at).total_seconds())
        remaining = max(0, self.active_test_duration_seconds - elapsed)
        percent = min(100, int((elapsed / self.active_test_duration_seconds) * 100))
        self.test_progress_bar.setValue(percent)
        self.test_progress_label.setText(
            f"Progress: {elapsed}/{self.active_test_duration_seconds}s, {remaining}s remaining."
        )
        if elapsed >= self.active_test_duration_seconds:
            self._finish_individual_test(stopped_by_user=False)

    def _finish_individual_test(self, *, stopped_by_user: bool) -> None:
        command = self.active_test_command
        if command is None:
            self._send_command(ArduinoCommand.STOP.value, source="Stop")
            return

        self.test_timer.stop()
        self._send_command(ArduinoCommand.STOP.value, source="Stop")
        self.active_test_command = None
        self.active_test_started_at = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if not self.active_test_values:
            spec = measurement_spec(command)
            expected = spec.expected_serial if spec is not None else command
            self.test_state_label.setText(
                "Test state\nFinished, but no valid samples were received from Arduino. "
                f"Expected {expected}; last line was: {self.last_raw_line}"
            )
            self.last_result_label.setText("Latest valid result\nNo result saved.")
            self.event_log.append_event(
                f"{measurement_name(command)}: no valid data received. Expected {expected}; "
                f"last Arduino line: {self.last_raw_line}",
                "ERROR",
            )
            return

        final_value = final_test_value(self.active_test_values)
        sample = self._sample_from_final_value(command, final_value)
        self.session_store.append(sample)
        display_sample = self._latest_metrics_sample(sample.timestamp)
        self._update_live_metrics(display_sample)
        self._update_charts(sample)
        self._refresh_history()

        self.test_progress_bar.setValue(100)
        self.test_progress_label.setText("Progress: completed.")
        result_text = format_test_value(command, final_value)
        suffix = "stopped early" if stopped_by_user else "completed"
        self.last_result_label.setText(f"Latest valid result\n{result_text}")
        self.test_state_label.setText(f"Test state\nTest {suffix}. Final result was saved.")
        self.event_log.append_event(
            f"{measurement_name(command)}: final result saved: {result_text}.",
            "USER",
        )

    def _sample_from_final_value(self, command: str, value: float) -> SensorSample:
        sample = SensorSample(timestamp=datetime.now())
        if command == ArduinoCommand.TEMP.value:
            sample.temperature = value
            self.latest_readings.temperature = value
        elif command == ArduinoCommand.GSR.value:
            sample.gsr = value
            self.latest_readings.gsr = value
        elif command == ArduinoCommand.BPM.value:
            sample.heart_rate = value
            self.latest_readings.heart_rate = value
            sample.spo2 = self.latest_readings.spo2
            sample.pulse_valid = self.latest_readings.pulse_valid
            sample.pulse_temperature = self.latest_readings.pulse_temperature

        score = self.score_calculator.calculate_score(sample)
        sample.bioscore = score
        sample.status = status_for_score(score)
        return sample

    @Slot(object, str)
    def _on_sample_received(self, parsed: ParsedMessage, raw: str) -> None:
        if self.active_test_command is None:
            return
        self._collect_individual_test_sample(parsed, raw)

    def _collect_individual_test_sample(self, parsed: ParsedMessage, raw: str) -> None:
        command = self.active_test_command
        if command is None:
            return

        invalid_reason = invalid_measurement_reason(parsed, command)
        if invalid_reason is not None:
            self._report_invalid_measurement(command, invalid_reason, raw)
            self.last_serial_label.setText(f"Last Arduino line\n{raw}")
            self.last_result_label.setText("Latest valid result\nInvalid sample ignored.")
            self.test_state_label.setText(f"Test state\nInvalid sample: {invalid_reason}")
            return

        self._clear_invalid_measurement(command)
        if parsed.spo2 is not None:
            self.latest_readings.spo2 = parsed.spo2
        if parsed.pulse_valid is not None:
            self.latest_readings.pulse_valid = parsed.pulse_valid
        if parsed.pulse_temperature is not None:
            self.latest_readings.pulse_temperature = parsed.pulse_temperature

        value = value_for_command(parsed, command)
        self.last_serial_label.setText(f"Last Arduino line\n{raw}")
        if value is None:
            self.test_state_label.setText(
                "Test state\nArduino sent data, but not for the active test command."
            )
            return

        self._collect_individual_test_value(value, raw)

    def _collect_individual_test_value(self, value: float, raw: str) -> None:
        command = self.active_test_command
        if command is None:
            return

        self._clear_invalid_measurement(command)
        self.last_serial_label.setText(f"Last Arduino line\n{raw}")
        self.active_test_values.append(value)
        self.current_test_sample_count += 1
        self.last_result_label.setText(
            f"Latest valid result\nCurrent: {format_test_value(command, value)} "
            f"({self.current_test_sample_count} samples)"
        )
        self.test_state_label.setText("Test state\nCollecting valid samples for one final result.")

    def _update_live_metrics(self, sample: SensorSample) -> None:
        deltas = self.score_calculator.calculate_deltas(sample)

        self.temperature_card.set_value(sample.temperature, precision=1)
        self.temperature_card.set_delta(deltas.temperature, precision=1)
        self.temperature_card.set_status(temperature_status(sample.temperature))

        self.heart_card.set_value(sample.heart_rate, precision=0)
        self.heart_card.set_delta(deltas.heart_rate, precision=0)
        self.heart_card.set_status(heart_status(sample.heart_rate))

        self.spo2_card.set_value(sample.spo2, precision=0)
        self.spo2_card.set_delta(None)
        self.spo2_card.set_status(spo2_status(sample.spo2, sample.pulse_valid))

        self.gsr_card.set_value(sample.gsr, precision=0)
        self.gsr_card.delta_label.setText(gsr_assessment_detail(sample.gsr, deltas.gsr))
        self.gsr_card.set_status(gsr_assessment_label(sample.gsr, deltas.gsr))

        self.status_card.value_label.setText(sample.status)
        self.status_card.delta_label.setText(
            "Baseline state active"
            if self.score_calculator.has_baseline
            else "Baseline not configured"
        )
        self.status_card.set_status(sample.status)
        self.status_card.value_label.setStyleSheet(f"color: {color_for_status(sample.status)};")

    def _report_invalid_measurement(self, command: str, reason: str, raw: str) -> None:
        if self._invalid_reason_by_command.get(command) == reason:
            return

        self._invalid_reason_by_command[command] = reason
        test_name = measurement_name(command)
        self.event_log.append_event(
            f"{test_name} result is INVALID: {reason} Raw data: {raw}",
            "ERROR",
        )

    def _clear_invalid_measurement(self, command: str) -> None:
        self._invalid_reason_by_command.pop(command, None)

    def _update_charts(self, sample: SensorSample) -> None:
        self.temperature_chart.add_sample(sample.timestamp, sample.temperature)
        self.heart_chart.add_sample(sample.timestamp, sample.heart_rate)
        self.spo2_chart.add_sample(sample.timestamp, sample.spo2)
        self.gsr_chart.add_sample(sample.timestamp, sample.gsr)

    def _restore_saved_dashboard_data(self) -> None:
        samples = self.session_store.samples
        if not samples:
            return

        for sample in samples:
            self._update_charts(sample)
            if sample.temperature is not None:
                self.latest_readings.temperature = sample.temperature
            if sample.heart_rate is not None:
                self.latest_readings.heart_rate = sample.heart_rate
            if sample.spo2 is not None:
                self.latest_readings.spo2 = sample.spo2
            if sample.pulse_valid is not None:
                self.latest_readings.pulse_valid = sample.pulse_valid
            if sample.pulse_temperature is not None:
                self.latest_readings.pulse_temperature = sample.pulse_temperature
            if sample.gsr is not None:
                self.latest_readings.gsr = sample.gsr

        self._update_live_metrics(self._latest_metrics_sample(samples[-1].timestamp))

    def _latest_metrics_sample(self, timestamp: datetime) -> SensorSample:
        sample = SensorSample(
            timestamp=timestamp,
            temperature=self.latest_readings.temperature,
            heart_rate=self.latest_readings.heart_rate,
            spo2=self.latest_readings.spo2,
            pulse_valid=self.latest_readings.pulse_valid,
            pulse_temperature=self.latest_readings.pulse_temperature,
            gsr=self.latest_readings.gsr,
        )
        sample.bioscore = self.score_calculator.calculate_score(sample)
        sample.status = status_for_score(sample.bioscore)
        return sample

    def _refresh_history(self) -> None:
        samples = self.session_store.samples
        self.table_model.set_samples(list(reversed(samples[-1000:])))
        self.history_summary.setText(f"{len(samples)} saved samples.")

    def _clear_dashboard_display(self) -> None:
        self.latest_readings = SensorSample(timestamp=datetime.now())
        self.temperature_chart.clear()
        self.heart_chart.clear()
        self.spo2_chart.clear()
        self.gsr_chart.clear()
        self.table_model.set_samples([])
        self.history_summary.setText("No saved samples.")
        self.temperature_card.set_value(None)
        self.temperature_card.set_delta(None)
        self.temperature_card.set_status("WAITING")
        self.heart_card.set_value(None)
        self.heart_card.set_delta(None)
        self.heart_card.set_status("WAITING")
        self.spo2_card.set_value(None)
        self.spo2_card.set_delta(None)
        self.spo2_card.set_status("WAITING")
        self.gsr_card.set_value(None)
        self.gsr_card.delta_label.setText("Assessment: no data")
        self.gsr_card.set_status("NO DATA")
        self.status_card.value_label.setText(STATUS_NORMAL)
        self.status_card.delta_label.setText("Baseline not configured")
        self.status_card.set_status(STATUS_NORMAL)

    def _export_csv(self) -> None:
        if not self.session_store.samples:
            self.event_log.append_event("CSV export skipped: no samples recorded.", "ERROR")
            return

        default_path = timestamped_path(self.settings.data_folder, "biomonitor_session", ".csv")
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            str(default_path),
            "CSV Files (*.csv)",
        )
        if not selected:
            return

        try:
            path = self.session_store.export_csv(Path(selected))
        except OSError as exc:
            self.event_log.append_event(f"CSV export failed: {exc}", "ERROR")
            return
        self.event_log.append_event(f"CSV exported to {path}.", "USER")

    def _browse_data_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            self.data_folder_edit.text(),
        )
        if selected:
            self.data_folder_edit.setText(selected)

    def _save_settings(self) -> None:
        folder_text = self.data_folder_edit.text().strip()
        if not folder_text:
            self.event_log.append_event("Data folder cannot be empty.", "ERROR")
            return

        selected_port = (
            self.settings_port_combo.currentData() or self._current_port() or self.settings.com_port
        )
        new_settings = AppSettings(
            com_port=str(selected_port or ""),
            theme=self.theme_combo.currentText(),
            data_folder=Path(folder_text).expanduser().resolve(),
        )
        try:
            new_store = SessionStore(new_settings.data_folder / "biomonitor.sqlite3")
            self.settings_manager.save(new_settings)
        except (OSError, sqlite3.Error) as exc:
            self.event_log.append_event(f"Could not save settings: {exc}", "ERROR")
            return

        data_folder_changed = new_settings.data_folder != self.settings.data_folder
        self.settings = new_settings
        if data_folder_changed:
            self.session_store = new_store
            self._clear_dashboard_display()
            self._restore_saved_dashboard_data()

        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, self.settings.theme)
        self._apply_chart_theme()
        self._refresh_status_colors()
        self._populate_ports(self.settings.com_port)
        self._refresh_history()
        self.event_log.append_event("Settings saved.", "USER")

    def _apply_chart_theme(self) -> None:
        for chart in [
            self.temperature_chart,
            self.heart_chart,
            self.spo2_chart,
            self.gsr_chart,
        ]:
            chart.apply_theme()

    def _refresh_status_colors(self) -> None:
        self._set_connected(self._is_serial_connected())
        for card in [
            self.temperature_card,
            self.heart_card,
            self.spo2_card,
            self.gsr_card,
            self.status_card,
        ]:
            card.set_status(card.status.label.text())
        self.status_card.value_label.setStyleSheet(
            f"color: {color_for_status(self.status_card.value_label.text())};"
        )


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def _detail_label(title: str, value: str) -> QLabel:
    label = QLabel(f"{title}\n{value}")
    label.setObjectName("DetailLabel")
    label.setWordWrap(True)
    label.setMinimumHeight(58)
    return label


def _ready_mode_for_view(command: str) -> str:
    if command == BIOMONITOR_VIEW:
        return ArduinoCommand.STOP.value
    return f"{command} READY"
