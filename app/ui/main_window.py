"""Main window for BioMonitor Dashboard."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QTimer, Qt, Slot
from PySide6.QtWidgets import (
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
    QSpinBox,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.bioscore import BioScoreCalculator, status_for_score
from app.charts import RealtimeChartWidget
from app.models import STATUS_AROUSED, STATUS_NORMAL, STATUS_RELAX, SensorDeltas, SensorSample
from app.serial.arduino_serial import ArduinoSerialWorker, available_ports
from app.serial.parser import ParsedMessage
from app.serial.protocol import ArduinoCommand
from app.settings import AppSettings, SettingsManager
from app.storage import SessionStore, timestamped_path
from app.ui.theme import (
    COLOR_MUTED,
    COLOR_SUCCESS,
    color_for_status,
)
from app.ui.widgets import EventLog, MetricCard, StatusIndicator


class SampleTableModel(QAbstractTableModel):
    """Qt table model for session samples."""

    HEADERS = [
        "Timestamp",
        "Temp \N{DEGREE SIGN}C",
        "BPM",
        "SpO2 %",
        "Pulse OK",
        "GSR",
        "Status",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._samples: list[SensorSample] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._samples)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or role not in (Qt.DisplayRole, Qt.TextAlignmentRole):
            return None

        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter

        sample = self._samples[index.row()]
        column = index.column()
        if column == 0:
            return sample.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        if column == 1:
            return _format_number(sample.temperature, 1)
        if column == 2:
            return _format_number(sample.heart_rate, 0)
        if column == 3:
            return _format_number(sample.spo2, 0)
        if column == 4:
            return _format_bool(sample.pulse_valid)
        if column == 5:
            return _format_number(sample.gsr, 0)
        if column == 6:
            return sample.status
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return self.HEADERS[section]

    def set_samples(self, samples: list[SensorSample]) -> None:
        """Replace table contents."""

        self.beginResetModel()
        self._samples = samples
        self.endResetModel()


class MainWindow(QMainWindow):
    """Main BioMonitor Dashboard window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BioMonitor Dashboard")
        self.resize(1480, 920)

        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load()
        if self.settings.baud_rate == 9600:
            self.settings.baud_rate = 115200
        self.session_store = SessionStore(self.settings.data_folder / "biomonitor.sqlite3")
        self.score_calculator = BioScoreCalculator()

        self.serial_worker: ArduinoSerialWorker | None = None
        self.latest_temperature: float | None = None
        self.latest_heart_rate: float | None = None
        self.latest_spo2: float | None = None
        self.latest_pulse_valid: bool | None = None
        self.latest_pulse_temperature: float | None = None
        self.latest_gsr: float | None = None
        self.current_mode = ArduinoCommand.STOP.value
        self.selected_command = ArduinoCommand.ALL.value
        self.selected_page_title = "Full BioMonitor"
        self.last_status = STATUS_NORMAL
        self.current_test_sample_count = 0
        self.last_raw_line = "No serial data received yet."
        self.active_test_command: str | None = None
        self.active_test_started_at: datetime | None = None
        self.active_test_duration_seconds = 0
        self.active_test_values: list[float] = []

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

        self.connection_indicator = StatusIndicator("OFFLINE", COLOR_MUTED)
        self.mode_indicator = QLabel("Mode: STOP")
        self.mode_indicator.setObjectName("MutedLabel")
        self.mode_indicator.setStyleSheet(
            "padding: 6px 10px; border-radius: 7px; background: #111821; "
            "border: 1px solid #263341;"
        )

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
            (
                "Full BioMonitor",
                lambda: self._select_live_mode(
                    ArduinoCommand.ALL.value,
                    "Full BioMonitor",
                ),
            ),
            (
                "Temperature Monitor",
                lambda: self._select_live_mode(
                    ArduinoCommand.TEMP.value,
                    "Temperature Monitor",
                ),
            ),
            (
                "Heart Rate Monitor",
                lambda: self._select_live_mode(
                    ArduinoCommand.BPM.value,
                    "Heart Rate Monitor",
                ),
            ),
            (
                "GSR Monitor",
                lambda: self._select_live_mode(
                    ArduinoCommand.GSR.value,
                    "GSR Monitor",
                ),
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

        self.live_page_title = QLabel("Full BioMonitor")
        self.live_page_title.setObjectName("SectionTitle")
        self.live_page_title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(self.live_page_title)

        self.test_guide_panel = self._build_test_guide_panel()
        layout.addWidget(self.test_guide_panel)

        self.metrics_title = _section_title("Live Metrics")
        layout.addWidget(self.metrics_title)
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(14)

        self.temperature_card = MetricCard("Temperature", "\N{DEGREE SIGN}C")
        self.heart_card = MetricCard("Heart Rate", "BPM")
        self.spo2_card = MetricCard("SpO2", "%")
        self.gsr_card = MetricCard("GSR", "ADC")
        self.status_card = MetricCard("System Status")
        self.status_card.value_label.setText(STATUS_NORMAL)
        self.status_card.delta_label.setText("Baseline state: --")
        self.status_card.set_status(STATUS_NORMAL)

        metrics_grid.addWidget(self.temperature_card, 0, 0)
        metrics_grid.addWidget(self.heart_card, 0, 1)
        metrics_grid.addWidget(self.spo2_card, 0, 2)
        metrics_grid.addWidget(self.gsr_card, 0, 3)
        metrics_grid.addWidget(self.status_card, 0, 4)
        for column in range(5):
            metrics_grid.setColumnStretch(column, 1)

        layout.addLayout(metrics_grid)

        self.charts_title = _section_title("Real-Time Charts")
        layout.addWidget(self.charts_title)
        charts_grid = QGridLayout()
        charts_grid.setSpacing(14)

        history = self.settings.chart_history_seconds
        self.temperature_chart = RealtimeChartWidget(
            "Temperature", "\N{DEGREE SIGN}C", "#63b3ed", history, y_range=(-20.0, 100.0)
        )
        self.heart_chart = RealtimeChartWidget("Heart Rate", "BPM", "#e78aa0", history)
        self.spo2_chart = RealtimeChartWidget(
            "SpO2", "%", "#f6ad55", history, y_range=(70.0, 100.0)
        )
        self.gsr_chart = RealtimeChartWidget("GSR", "ADC", "#68d391", history)

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

        self.controls_title = _section_title("Controls")
        layout.addWidget(self.controls_title)
        layout.addWidget(self._build_controls_panel())

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
        self.test_guide_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
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
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
            lambda: self._populate_ports(self._current_port())
        )

        port_row = QHBoxLayout()
        port_row.addWidget(self.settings_port_combo)
        port_row.addWidget(self.settings_refresh_button)
        form.addRow("COM port", port_row)

        self.baud_spin = QSpinBox()
        self.baud_spin.setRange(1200, 115200)
        self.baud_spin.setSingleStep(1200)
        form.addRow("Baud rate", self.baud_spin)

        self.sampling_spin = QSpinBox()
        self.sampling_spin.setRange(100, 10000)
        self.sampling_spin.setSingleStep(100)
        self.sampling_spin.setSuffix(" ms")
        form.addRow("Sampling interval", self.sampling_spin)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Medical Dark", "High Contrast Dark"])
        form.addRow("Theme", self.theme_combo)

        self.history_spin = QSpinBox()
        self.history_spin.setRange(30, 3600)
        self.history_spin.setSingleStep(30)
        self.history_spin.setSuffix(" s")
        form.addRow("Chart history length", self.history_spin)

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
        combos = [self.port_combo]
        if hasattr(self, "settings_port_combo"):
            combos.append(self.settings_port_combo)

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
        self.baud_spin.setValue(self.settings.baud_rate)
        self.sampling_spin.setValue(self.settings.sampling_interval_ms)
        self.history_spin.setValue(self.settings.chart_history_seconds)
        self.data_folder_edit.setText(str(self.settings.data_folder))
        theme_index = self.theme_combo.findText(self.settings.theme)
        self.theme_combo.setCurrentIndex(max(theme_index, 0))

    def _current_port(self) -> str:
        data = self.port_combo.currentData()
        return str(data or "")

    def _show_dashboard_page(self) -> None:
        self.stack.setCurrentWidget(self.dashboard_page)

    def _show_history_page(self) -> None:
        self._refresh_history()
        self.stack.setCurrentWidget(self.history_page)

    def _show_settings_page(self) -> None:
        self.stack.setCurrentWidget(self.settings_page)

    def _select_live_mode(
        self,
        command: str,
        title: str,
    ) -> None:
        self.selected_command = command
        self.selected_page_title = title
        self.live_page_title.setText(title)
        self._apply_live_mode_visibility()
        self._update_selected_mode_controls()
        self._show_dashboard_page()
        self._update_mode_indicator(f"{command} READY")

    def _apply_live_mode_visibility(self) -> None:
        command = self.selected_command
        show_all = command == ArduinoCommand.ALL.value
        show_temperature = show_all or command == ArduinoCommand.TEMP.value
        show_heart = show_all or command == ArduinoCommand.BPM.value
        show_gsr = show_all or command == ArduinoCommand.GSR.value

        self.metrics_title.setVisible(True)
        self.charts_title.setVisible(True)
        self.temperature_card.setVisible(show_temperature)
        self.heart_card.setVisible(show_heart)
        self.spo2_card.setVisible(show_heart)
        self.gsr_card.setVisible(show_gsr)
        self.status_card.setVisible(show_all)

        self.temperature_chart.setVisible(show_temperature)
        self.heart_chart.setVisible(show_heart)
        self.spo2_chart.setVisible(show_heart)
        self.gsr_chart.setVisible(show_gsr)

    def _update_selected_mode_controls(self) -> None:
        command = self.selected_command
        self.start_button.setText("Start Test")
        self.start_button.setEnabled(True)

        title, body = _test_protocol_text(command)
        self.test_guide_title.setText(title)
        self.test_guide_body.setText(body)
        self.expected_serial_label.setText(
            f"Expected Arduino data\n{_expected_serial_format(command) or '--'}"
        )
        self.last_serial_label.setText(f"Last Arduino line\n{self.last_raw_line}")
        self.last_result_label.setText("Latest valid result\nWaiting for Start Test.")
        self.test_state_label.setText("Test state\nReady. Connect Arduino, then click Start Test.")
        duration = _test_duration_seconds(command)
        self.test_progress_bar.setValue(0)
        self.test_progress_label.setText(
            f"Progress: test duration {duration} seconds."
            if duration
            else "Progress: not available."
        )
        self.test_guide_panel.setVisible(command in {
            ArduinoCommand.TEMP.value,
            ArduinoCommand.GSR.value,
            ArduinoCommand.BPM.value,
        })

    def _is_serial_connected(self) -> bool:
        worker = self.serial_worker
        return bool(worker is not None and worker.isRunning())

    def _connect_serial(self) -> None:
        if self.serial_worker is not None and self.serial_worker.isRunning():
            self.event_log.append_event("Serial connection is already active.", "INFO")
            return

        port = self._current_port()
        if not port:
            self.event_log.append_event("Select a serial port before connecting.", "ERROR")
            return

        self.settings.com_port = port
        self.settings.baud_rate = self.baud_spin.value()
        self.settings_manager.save(self.settings)

        self.serial_worker = ArduinoSerialWorker(port, baud_rate=self.settings.baud_rate)
        self.serial_worker.connected.connect(self._on_serial_connected)
        self.serial_worker.disconnected.connect(self._on_serial_disconnected)
        self.serial_worker.raw_received.connect(self._on_raw_serial_received)
        self.serial_worker.sample_received.connect(self._on_sample_received)
        self.serial_worker.error.connect(self._on_serial_error)
        self.serial_worker.start()
        self.event_log.append_event(f"Connecting to {port} at {self.settings.baud_rate} baud.")

    def _disconnect_serial(self) -> None:
        worker = self.serial_worker
        if worker is None:
            self._set_connected(False)
            return

        if worker.isRunning():
            worker.send_command(ArduinoCommand.STOP.value)
            worker.stop()
            worker.wait(1500)
        self.serial_worker = None
        self._set_connected(False)
        self._update_mode_indicator(ArduinoCommand.STOP.value)
        self.event_log.append_event("Disconnected from Arduino.")

    @Slot(str)
    def _on_serial_connected(self, port: str) -> None:
        self._set_connected(True)
        self.event_log.append_event(f"Connected to Arduino on {port}.")
        self._update_mode_indicator(f"{self.selected_command} READY")

    @Slot()
    def _on_serial_disconnected(self) -> None:
        self._set_connected(False)
        self._update_mode_indicator(ArduinoCommand.STOP.value)
        self.serial_worker = None

    @Slot(str)
    def _on_serial_error(self, message: str) -> None:
        self.event_log.append_event(message, "ERROR")

    @Slot(str)
    def _on_raw_serial_received(self, line: str) -> None:
        self.last_raw_line = line
        if _is_individual_test_command(self.selected_command):
            self.last_serial_label.setText(f"Last Arduino line\n{line}")
            if self.active_test_command is not None:
                fallback_value = _numeric_value_from_raw_line(line, self.active_test_command)
                if fallback_value is not None:
                    self._collect_individual_test_value(fallback_value, line)
                    return
            if not _line_matches_selected_command(line, self.selected_command):
                self.test_state_label.setText(
                    "Test state\nArduino is connected, but this line is not a valid "
                    "result for this test."
                )

    def _set_connected(self, connected: bool) -> None:
        self.connect_button.setEnabled(not connected)
        self.disconnect_button.setEnabled(connected)
        if connected:
            self.connection_indicator.set_status("CONNECTED", COLOR_SUCCESS)
        else:
            self.connection_indicator.set_status("OFFLINE", COLOR_MUTED)

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
        self.current_mode = mode
        self.mode_indicator.setText(f"Mode: {mode}")

    def _start_measurement(self) -> None:
        if _is_individual_test_command(self.selected_command):
            self._start_individual_test()
            return

        if self._send_command(self.selected_command, source=self.start_button.text()):
            self.current_test_sample_count = 0
            expected = _expected_serial_format(self.selected_command)
            if expected:
                self.last_result_label.setText("Latest valid result\nNo valid sample received yet.")
                self.test_state_label.setText(
                    "Test state\nWaiting for the first valid Arduino sample."
                )
                self.event_log.append_event(
                    f"Waiting for Arduino data in format {expected}.",
                    "INFO",
                )

    def _stop_measurement(self) -> None:
        if self.active_test_command is not None:
            self._finish_individual_test(stopped_by_user=True)
            return
        self._send_command(ArduinoCommand.STOP.value, source="Stop")

    def _start_individual_test(self) -> None:
        if self.active_test_command is not None:
            self.event_log.append_event("A test is already running.", "INFO")
            return

        duration = _test_duration_seconds(self.selected_command)
        if duration <= 0:
            self.event_log.append_event("This test is not available yet.", "ERROR")
            return

        if not self._send_command(self.selected_command, source=self.start_button.text()):
            return

        self.active_test_command = self.selected_command
        self.active_test_started_at = datetime.now()
        self.active_test_duration_seconds = duration
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
            f"{self.selected_page_title}: collecting one final result for {duration} seconds.",
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

        if not self.active_test_values:
            expected = _expected_serial_format(command)
            self.test_state_label.setText(
                "Test state\nFinished, but no valid samples were received from Arduino. "
                f"Expected {expected}; last line was: {self.last_raw_line}"
            )
            self.last_result_label.setText("Latest valid result\nNo result saved.")
            self.event_log.append_event(
                f"{self.selected_page_title}: no valid data received. Expected {expected}; "
                f"last Arduino line: {self.last_raw_line}",
                "ERROR",
            )
            return

        final_value = _final_test_value(self.active_test_values)
        sample = self._sample_from_final_value(command, final_value)
        self.session_store.append(sample)
        display_sample = self._latest_metrics_sample(sample.timestamp)
        self._update_live_metrics(display_sample)
        self._update_charts(sample)
        self._refresh_history()

        self.test_progress_bar.setValue(100)
        self.test_progress_label.setText("Progress: completed.")
        result_text = _format_test_value(command, final_value)
        suffix = "stopped early" if stopped_by_user else "completed"
        self.last_result_label.setText(f"Latest valid result\n{result_text}")
        self.test_state_label.setText(
            f"Test state\nTest {suffix}. Final result was saved."
        )
        self.event_log.append_event(
            f"{self.selected_page_title}: final result saved: {result_text}.",
            "USER",
        )

    def _sample_from_final_value(self, command: str, value: float) -> SensorSample:
        sample = SensorSample(timestamp=datetime.now())
        if command == ArduinoCommand.TEMP.value:
            sample.temperature = value
            self.latest_temperature = value
        elif command == ArduinoCommand.GSR.value:
            sample.gsr = value
            self.latest_gsr = value
        elif command == ArduinoCommand.BPM.value:
            sample.heart_rate = value
            self.latest_heart_rate = value
            sample.spo2 = self.latest_spo2
            sample.pulse_valid = self.latest_pulse_valid
            sample.pulse_temperature = self.latest_pulse_temperature

        score = self.score_calculator.calculate_score(sample)
        sample.bioscore = score
        sample.status = status_for_score(score)
        return sample

    @Slot(object, str)
    def _on_sample_received(self, parsed: ParsedMessage, raw: str) -> None:
        if self.active_test_command is not None:
            self._collect_individual_test_sample(parsed, raw)
            return

        if parsed.temperature is not None:
            self.latest_temperature = parsed.temperature
        if parsed.heart_rate is not None:
            self.latest_heart_rate = parsed.heart_rate
        if parsed.spo2 is not None:
            self.latest_spo2 = parsed.spo2
        if parsed.pulse_valid is not None:
            self.latest_pulse_valid = parsed.pulse_valid
        if parsed.pulse_temperature is not None:
            self.latest_pulse_temperature = parsed.pulse_temperature
        if parsed.gsr is not None:
            self.latest_gsr = parsed.gsr

        sample = SensorSample(
            timestamp=datetime.now(),
            temperature=self.latest_temperature
            if self.selected_command in {ArduinoCommand.ALL.value, ArduinoCommand.TEMP.value}
            else None,
            heart_rate=self.latest_heart_rate
            if self.selected_command in {ArduinoCommand.ALL.value, ArduinoCommand.BPM.value}
            else None,
            spo2=self.latest_spo2
            if self.selected_command in {ArduinoCommand.ALL.value, ArduinoCommand.BPM.value}
            else None,
            pulse_valid=self.latest_pulse_valid
            if self.selected_command in {ArduinoCommand.ALL.value, ArduinoCommand.BPM.value}
            else None,
            pulse_temperature=self.latest_pulse_temperature
            if self.selected_command in {ArduinoCommand.ALL.value, ArduinoCommand.BPM.value}
            else None,
            gsr=self.latest_gsr
            if self.selected_command in {ArduinoCommand.ALL.value, ArduinoCommand.GSR.value}
            else None,
        )
        score = self.score_calculator.calculate_score(sample)
        sample.bioscore = score
        sample.status = status_for_score(score)

        self.session_store.append(sample)
        self.current_test_sample_count += 1

        display_sample = self._latest_metrics_sample(sample.timestamp)
        self._update_live_metrics(display_sample)
        self._update_charts(sample)
        self._update_test_result_panel(sample, raw)
        self._refresh_history()

        if display_sample.status != self.last_status:
            self.event_log.append_event(
                f"System status changed to {display_sample.status}.", "SENSOR"
            )
            self.last_status = display_sample.status

    def _collect_individual_test_sample(self, parsed: ParsedMessage, raw: str) -> None:
        command = self.active_test_command
        if command is None:
            return

        if parsed.spo2 is not None:
            self.latest_spo2 = parsed.spo2
        if parsed.pulse_valid is not None:
            self.latest_pulse_valid = parsed.pulse_valid
        if parsed.pulse_temperature is not None:
            self.latest_pulse_temperature = parsed.pulse_temperature

        value = _value_for_command(parsed, command)
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

        self.last_serial_label.setText(f"Last Arduino line\n{raw}")
        self.active_test_values.append(value)
        self.current_test_sample_count += 1
        self.last_result_label.setText(
            f"Latest valid result\nCurrent: {_format_test_value(command, value)} "
            f"({self.current_test_sample_count} samples)"
        )
        self.test_state_label.setText("Test state\nCollecting valid samples for one final result.")

    def _update_test_result_panel(self, sample: SensorSample, raw: str) -> None:
        if not _is_individual_test_command(self.selected_command):
            return

        value_text = "--"
        if self.selected_command == ArduinoCommand.TEMP.value:
            value_text = f"{_format_number(sample.temperature, 1)} °C"
        elif self.selected_command == ArduinoCommand.GSR.value:
            value_text = f"{_format_number(sample.gsr, 0)} ADC"
        elif self.selected_command == ArduinoCommand.BPM.value:
            value_text = (
                f"{_format_number(sample.heart_rate, 0)} BPM, "
                f"SpO2 {_format_number(sample.spo2, 0)}%, "
                f"valid {_format_bool(sample.pulse_valid)}"
            )

        self.last_serial_label.setText(f"Last Arduino line\n{raw}")
        self.last_result_label.setText(
            f"Latest valid result\n{value_text} ({self.current_test_sample_count} samples)"
        )
        self.test_state_label.setText("Test state\nReceiving valid data.")

    def _update_live_metrics(self, sample: SensorSample) -> None:
        deltas = self.score_calculator.calculate_deltas(sample)

        self.temperature_card.set_value(sample.temperature, precision=1)
        self.temperature_card.set_delta(deltas.temperature, precision=1)
        self.temperature_card.set_status(_temperature_status(sample.temperature))

        self.heart_card.set_value(sample.heart_rate, precision=0)
        self.heart_card.set_delta(deltas.heart_rate, precision=0)
        self.heart_card.set_status(_heart_status(sample.heart_rate))

        self.spo2_card.set_value(sample.spo2, precision=0)
        self.spo2_card.set_delta(None)
        self.spo2_card.set_status(_spo2_status(sample.spo2, sample.pulse_valid))

        self.gsr_card.set_value(sample.gsr, precision=0)
        self.gsr_card.set_delta(deltas.gsr, precision=0)
        self.gsr_card.set_status(_gsr_status(deltas))

        self.status_card.value_label.setText(sample.status)
        self.status_card.delta_label.setText("Baseline state active")
        self.status_card.set_status(sample.status)
        self.status_card.value_label.setStyleSheet(f"color: {color_for_status(sample.status)};")

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
                self.latest_temperature = sample.temperature
            if sample.heart_rate is not None:
                self.latest_heart_rate = sample.heart_rate
            if sample.spo2 is not None:
                self.latest_spo2 = sample.spo2
            if sample.pulse_valid is not None:
                self.latest_pulse_valid = sample.pulse_valid
            if sample.pulse_temperature is not None:
                self.latest_pulse_temperature = sample.pulse_temperature
            if sample.gsr is not None:
                self.latest_gsr = sample.gsr
            self.last_status = sample.status

        self._update_live_metrics(self._latest_metrics_sample(samples[-1].timestamp))

    def _latest_metrics_sample(self, timestamp: datetime) -> SensorSample:
        sample = SensorSample(
            timestamp=timestamp,
            temperature=self.latest_temperature,
            heart_rate=self.latest_heart_rate,
            spo2=self.latest_spo2,
            pulse_valid=self.latest_pulse_valid,
            pulse_temperature=self.latest_pulse_temperature,
            gsr=self.latest_gsr,
            status=self.last_status,
        )
        sample.bioscore = self.score_calculator.calculate_score(sample)
        sample.status = status_for_score(sample.bioscore)
        return sample

    def _refresh_history(self) -> None:
        samples = self.session_store.samples
        self.table_model.set_samples(list(reversed(samples[-1000:])))
        self.history_summary.setText(f"{len(samples)} saved samples.")

    def _reset_data(self) -> None:
        self.session_store.clear()
        self.latest_temperature = None
        self.latest_heart_rate = None
        self.latest_spo2 = None
        self.latest_pulse_valid = None
        self.latest_pulse_temperature = None
        self.latest_gsr = None
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
        self.gsr_card.set_delta(None)
        self.gsr_card.set_status("WAITING")
        self.status_card.value_label.setText(STATUS_NORMAL)
        self.status_card.delta_label.setText("Baseline state: --")
        self.status_card.set_status(STATUS_NORMAL)
        self.event_log.append_event("Recorded data reset.", "USER")

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

        path = self.session_store.export_csv(Path(selected))
        self.event_log.append_event(f"CSV exported to {path}.", "USER")

    def _export_report(self) -> None:
        if not self.session_store.samples:
            self.event_log.append_event("Report export skipped: no samples recorded.", "ERROR")
            return

        default_path = timestamped_path(self.settings.data_folder, "biomonitor_report", ".html")
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            str(default_path),
            "HTML Report (*.html)",
        )
        if not selected:
            return

        path = self.session_store.export_report(Path(selected))
        self.event_log.append_event(f"Report exported to {path}.", "USER")

    def _browse_data_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Data Folder",
            self.data_folder_edit.text(),
        )
        if selected:
            self.data_folder_edit.setText(selected)

    def _save_settings(self) -> None:
        selected_port = self.settings_port_combo.currentData() or self._current_port()
        self.settings = AppSettings(
            com_port=str(selected_port or ""),
            baud_rate=self.baud_spin.value(),
            sampling_interval_ms=self.sampling_spin.value(),
            theme=self.theme_combo.currentText(),
            chart_history_seconds=self.history_spin.value(),
            data_folder=Path(self.data_folder_edit.text()).expanduser(),
        )
        self.settings_manager.save(self.settings)
        self.session_store = SessionStore(self.settings.data_folder / "biomonitor.sqlite3")
        self.temperature_chart.set_history_seconds(self.settings.chart_history_seconds)
        self.heart_chart.set_history_seconds(self.settings.chart_history_seconds)
        self.spo2_chart.set_history_seconds(self.settings.chart_history_seconds)
        self.gsr_chart.set_history_seconds(self.settings.chart_history_seconds)
        self._populate_ports(self.settings.com_port)
        self._refresh_history()
        self.event_log.append_event("Settings saved.", "USER")


def _section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def _detail_label(title: str, value: str) -> QLabel:
    label = QLabel(f"{title}\n{value}")
    label.setObjectName("MutedLabel")
    label.setWordWrap(True)
    label.setMinimumHeight(58)
    label.setStyleSheet(
        "background: #111821; border: 1px solid #263341; border-radius: 7px; "
        "padding: 9px 10px; font-size: 12px;"
    )
    return label


def _test_protocol_text(command: str) -> tuple[str, str]:
    if command == ArduinoCommand.TEMP.value:
        return (
            "Temperature Test",
            "1. Podlacz Arduino i upewnij sie, ze status polaczenia to CONNECTED.\n"
            "2. Umiesc czujnik temperatury w wybranym miejscu.\n"
            "3. Utrzymuj czujnik nieruchomo i nie zmieniaj nacisku podczas testu.\n"
            "4. Kliknij Start Test.\n"
            "5. Poczekaj do konca paska postepu.",
        )
    if command == ArduinoCommand.GSR.value:
        return (
            "GSR Test",
            "1. Zaloz elektrody na te same palce przed kazdym pomiarem.\n"
            "2. Nie sciskaj elektrod zbyt mocno.\n"
            "3. Usiadz spokojnie i ogranicz ruch dloni.\n"
            "4. Kliknij Start Test.\n"
            "5. Trzymaj dlon w tej samej pozycji do konca paska postepu.",
        )
    if command == ArduinoCommand.BPM.value:
        return (
            "Heart Rate Test",
            "1. Poloz opuszek palca na sensorze tetna.\n"
            "2. Nie dociskaj palca zbyt mocno.\n"
            "3. Nie przesuwaj palca podczas pomiaru.\n"
            "4. Oddychaj spokojnie i nie rozmawiaj w trakcie testu.\n"
            "5. Kliknij Start Test i poczekaj 30 sekund.",
        )
    if command == ArduinoCommand.ALL.value:
        return ("", "")
    return ("Test Protocol", "")


def _expected_serial_format(command: str) -> str:
    if command == ArduinoCommand.TEMP.value:
        return "TEMP:36.2"
    if command == ArduinoCommand.GSR.value:
        return "GSR:542"
    if command == ArduinoCommand.BPM.value:
        return "BPM:74,SPO2:97,PULSE_VALID:1,PULSE_TEMP:31.50"
    if command == ArduinoCommand.ALL.value:
        return "BPM:74,SPO2:97,PULSE_VALID:1,TEMP:35.82,GSR:542,PULSE_TEMP:31.50"
    return ""


def _test_duration_seconds(command: str) -> int:
    if command == ArduinoCommand.TEMP.value:
        return 10
    if command == ArduinoCommand.GSR.value:
        return 10
    if command == ArduinoCommand.BPM.value:
        return 30
    return 0


def _value_for_command(parsed: ParsedMessage, command: str) -> float | None:
    if command == ArduinoCommand.TEMP.value:
        return parsed.temperature
    if command == ArduinoCommand.GSR.value:
        return parsed.gsr
    if command == ArduinoCommand.BPM.value:
        return parsed.heart_rate
    return None


def _final_test_value(values: list[float]) -> float:
    stable_values = values[-10:] if len(values) >= 10 else values
    return sum(stable_values) / len(stable_values)


def _format_test_value(command: str, value: float) -> str:
    if command == ArduinoCommand.TEMP.value:
        return f"{value:.1f} \N{DEGREE SIGN}C"
    if command == ArduinoCommand.GSR.value:
        return f"{value:.0f} ADC"
    if command == ArduinoCommand.BPM.value:
        return f"{value:.0f} BPM"
    return f"{value:.2f}"


def _numeric_value_from_raw_line(line: str, command: str) -> float | None:
    cleaned = line.strip().replace(",", ".")
    if ":" in cleaned:
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    if command == ArduinoCommand.TEMP.value and -50.0 <= value <= 150.0:
        return value
    if command == ArduinoCommand.GSR.value and 0.0 <= value <= 1023.0:
        return value
    if command == ArduinoCommand.BPM.value and 20.0 <= value <= 240.0:
        return value
    return None


def _line_matches_selected_command(line: str, command: str) -> bool:
    normalized = line.strip().upper()
    if command == ArduinoCommand.TEMP.value:
        return normalized.startswith("TEMP:")
    if command == ArduinoCommand.GSR.value:
        return normalized.startswith("GSR:")
    if command == ArduinoCommand.BPM.value:
        return normalized.startswith("BPM:")
    if command == ArduinoCommand.ALL.value:
        return any(part in normalized for part in ["TEMP:", "GSR:", "BPM:"])
    return False


def _is_individual_test_command(command: str) -> bool:
    return command in {
        ArduinoCommand.TEMP.value,
        ArduinoCommand.GSR.value,
        ArduinoCommand.BPM.value,
    }


def _format_number(value: float | None, precision: int) -> str:
    if value is None:
        return "--"
    if precision <= 0:
        return str(int(round(value)))
    return f"{value:.{precision}f}"


def _format_bool(value: bool | None) -> str:
    if value is None:
        return "--"
    return "YES" if value else "NO"


def _temperature_status(value: float | None) -> str:
    if value is None:
        return "WAITING"
    if 35.5 <= value <= 37.5:
        return STATUS_NORMAL
    if value < 35.5:
        return STATUS_RELAX
    return STATUS_AROUSED


def _heart_status(value: float | None) -> str:
    if value is None:
        return "WAITING"
    if value < 55:
        return STATUS_RELAX
    if value <= 100:
        return STATUS_NORMAL
    return STATUS_AROUSED


def _spo2_status(value: float | None, pulse_valid: bool | None) -> str:
    if pulse_valid is False:
        return "INVALID"
    if value is None:
        return "WAITING"
    if value >= 95:
        return STATUS_NORMAL
    if value >= 90:
        return STATUS_RELAX
    return STATUS_AROUSED


def _gsr_status(deltas: SensorDeltas) -> str:
    if deltas.gsr is None:
        return "WAITING"
    if deltas.gsr < -100:
        return STATUS_RELAX
    if deltas.gsr <= 100:
        return STATUS_NORMAL
    return STATUS_AROUSED
