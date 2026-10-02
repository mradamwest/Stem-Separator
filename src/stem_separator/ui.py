from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from stem_separator.engine import create_separation_plan, first_run_status, run_separation


APP_STYLE = """
QWidget { background:#0b1020; color:#e8eefc; font-family:'Segoe UI'; font-size:14px; }
QFrame#sidebar { background:#10182b; border-right:1px solid #202b44; }
QFrame#card { background:#111a2e; border:1px solid #26324c; border-radius:14px; }
QLabel#title { font-size:26px; font-weight:700; }
QLabel#muted { color:#91a0bd; }
QPushButton { background:#17233c; border:1px solid #2a3a5d; border-radius:9px; padding:10px 14px; text-align:left; }
QPushButton:hover { background:#1d2d4d; }
QPushButton#primary { background:#2563eb; border:0; font-weight:700; text-align:center; padding:12px; }
QPushButton#primary:hover { background:#3475f5; }
QPushButton#mode { text-align:center; }
QPushButton#mode:checked { background:#1d4ed8; border-color:#3b82f6; }
"""


class SeparationWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, source, output_root=None, allow_model_download=False):
        super().__init__()
        self.source = source
        self.output_root = output_root
        self.allow_model_download = allow_model_download

    def run(self):
        try:
            self.status.emit("Preparing separation model…")
            self.status.emit("Separating audio…")
            self.completed.emit(run_separation(
                self.source,
                output_root=self.output_root,
                allow_model_download=self.allow_model_download,
            ))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stem Separator")
        self.resize(1180, 760)
        self.setMinimumSize(980, 650)
        self.source = ""
        self.output_root = ""
        self.worker = None
        self.setStyleSheet(APP_STYLE)
        self.setCentralWidget(self.build_ui())

    def card(self):
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    def build_ui(self):
        root = QWidget()
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(20, 26, 20, 20)
        brand = QLabel("STEM\nSEPARATOR")
        brand.setObjectName("title")
        nav.addWidget(brand)
        nav.addSpacing(28)
        for text in ("Separation", "Batch Processing", "History", "Settings"):
            button = QPushButton(text)
            button.setEnabled(text == "Separation")
            nav.addWidget(button)
        nav.addStretch()
        nav.addWidget(QLabel("Working recovery build"))
        outer.addWidget(sidebar)

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 26, 30, 26)
        body.setSpacing(18)

        title = QLabel("Separate Audio")
        title.setObjectName("title")
        subtitle = QLabel("Drop in a song or choose a file, select a mode, then export clean stems.")
        subtitle.setObjectName("muted")
        body.addWidget(title)
        body.addWidget(subtitle)

        top = QHBoxLayout()
        top.setSpacing(18)

        input_card = self.card()
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(24, 24, 24, 24)
        input_layout.addWidget(QLabel("INPUT"))
        self.file_label = QLabel("Drag & drop audio here\n\nor choose a file")
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setMinimumHeight(180)
        self.file_label.setObjectName("muted")
        choose = QPushButton("Choose Audio File")
        choose.setObjectName("primary")
        choose.clicked.connect(self.choose_audio)
        input_layout.addWidget(self.file_label, 1)
        input_layout.addWidget(choose)
        top.addWidget(input_card, 3)

        settings = self.card()
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(22, 22, 22, 22)
        settings_layout.addWidget(QLabel("SEPARATION MODE"))
        modes = QHBoxLayout()
        self.basic = QPushButton("Basic")
        self.advanced = QPushButton("Advanced")
        for button in (self.basic, self.advanced):
            button.setObjectName("mode")
            button.setCheckable(True)
            modes.addWidget(button)
        self.basic.setChecked(True)
        self.basic.clicked.connect(lambda: self.set_mode("basic"))
        self.advanced.clicked.connect(lambda: self.set_mode("advanced"))
        settings_layout.addLayout(modes)

        self.mode_stack = QStackedWidget()
        basic_page = QWidget()
        basic_layout = QVBoxLayout(basic_page)
        basic_layout.setContentsMargins(0, 12, 0, 0)
        basic_layout.addWidget(QLabel("Vocals + Music"))
        basic_note = QLabel("Fast two-part workflow for isolating the vocal from the backing track.")
        basic_note.setWordWrap(True)
        basic_note.setObjectName("muted")
        basic_layout.addWidget(basic_note)
        basic_layout.addStretch()

        advanced_page = QWidget()
        advanced_layout = QVBoxLayout(advanced_page)
        advanced_layout.setContentsMargins(0, 12, 0, 0)
        advanced_layout.addWidget(QLabel("Expanded stem separation"))
        advanced_note = QLabel("Designed for larger instrument sets. Available stems will follow the selected model rather than a fixed six-stem limit.")
        advanced_note.setWordWrap(True)
        advanced_note.setObjectName("muted")
        advanced_layout.addWidget(advanced_note)
        advanced_layout.addStretch()
        self.mode_stack.addWidget(basic_page)
        self.mode_stack.addWidget(advanced_page)
        settings_layout.addWidget(self.mode_stack)

        output = QPushButton("Choose Output Folder")
        output.clicked.connect(self.choose_output)
        self.output_label = QLabel("Output: beside source file")
        self.output_label.setObjectName("muted")
        settings_layout.addWidget(output)
        settings_layout.addWidget(self.output_label)
        top.addWidget(settings, 2)
        body.addLayout(top, 1)

        action_card = self.card()
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(20, 16, 20, 16)
        self.status = QLabel("Ready")
        self.status.setObjectName("muted")
        self.start = QPushButton("Separate")
        self.start.setObjectName("primary")
        self.start.setMinimumWidth(180)
        self.start.setEnabled(False)
        self.start.clicked.connect(self.separate)
        action_layout.addWidget(self.status, 1)
        action_layout.addWidget(self.start)
        body.addWidget(action_card)

        results = self.card()
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(22, 18, 22, 18)
        results_layout.addWidget(QLabel("RESULTS"))
        self.results_label = QLabel("Separated tracks will appear here after processing.")
        self.results_label.setObjectName("muted")
        results_layout.addWidget(self.results_label)
        body.addWidget(results)

        outer.addWidget(content, 1)
        return root

    def set_mode(self, mode):
        advanced = mode == "advanced"
        self.basic.setChecked(not advanced)
        self.advanced.setChecked(advanced)
        self.mode_stack.setCurrentIndex(1 if advanced else 0)

    def choose_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Audio", "", "Audio (*.wav *.mp3 *.flac *.ogg *.m4a)"
        )
        if path:
            self.source = path
            self.file_label.setText(Path(path).name)
            self.status.setText("Ready to separate")
            self.start.setEnabled(True)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Choose Output Folder")
        if path:
            self.output_root = path
            self.output_label.setText(f"Output: {path}")

    def separate(self):
        try:
            status = first_run_status(create_separation_plan(
                self.source, output_root=self.output_root or None
            ))
        except Exception as exc:
            self.failed(str(exc))
            return
        allow_download = False
        if status.get("requires_model_download"):
            answer = QMessageBox.question(
                self, "Model Download Required",
                "The separation model must be downloaded before first use. Continue?"
            )
            if answer != QMessageBox.Yes:
                self.status.setText("Model download cancelled")
                return
            allow_download = True
        self.start.setEnabled(False)
        self.status.setText("Separating…")
        self.worker = SeparationWorker(
            self.source,
            output_root=self.output_root or None,
            allow_model_download=allow_download,
        )
        self.worker.completed.connect(self.done)
        self.worker.failed.connect(self.failed)
        self.worker.status.connect(self.status.setText)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def worker_finished(self):
        self.worker = None

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(
                self, "Stem Separator",
                "Separation is still running. Wait for it to finish before closing."
            )
            event.ignore()
            return
        event.accept()

    def done(self, result):
        self.start.setEnabled(True)
        stems = result.get("stems", {})
        self.status.setText("Complete")
        self.results_label.setText(" • ".join(stems.keys()) or "Separation complete")
        QMessageBox.information(
            self, "Stem Separator",
            f"Separation complete.\n\nOutput: {result.get('output_directory', '')}"
        )

    def failed(self, message):
        self.start.setEnabled(True)
        self.status.setText("Separation failed")
        QMessageBox.critical(self, "Stem Separator", message)


def main():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
