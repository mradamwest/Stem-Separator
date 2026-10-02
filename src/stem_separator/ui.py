from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
from stem_separator.engine import create_separation_plan, first_run_status, run_separation

class SeparationWorker(QThread):
    completed = Signal(dict); failed = Signal(str); status = Signal(str)
    def __init__(self, source, allow_model_download=False): super().__init__(); self.source = source; self.allow_model_download = allow_model_download
    def run(self):
        try:
            self.status.emit("Preparing separation model…")
            self.status.emit("Separating audio…")
            self.completed.emit(run_separation(self.source, allow_model_download=self.allow_model_download))
        except Exception as exc: self.failed.emit(str(exc))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Stem Separator"); self.resize(760, 420); self.source = ""; self.worker = None
        root=QWidget(); layout=QVBoxLayout(root); self.status=QLabel("Choose an audio file to separate into the stems supported by the selected model.")
        choose=QPushButton("Choose Audio…"); choose.clicked.connect(self.choose_audio); self.start=QPushButton("Separate Stems"); self.start.setEnabled(False); self.start.clicked.connect(self.separate)
        layout.addWidget(self.status); layout.addWidget(choose); layout.addWidget(self.start); layout.addStretch(); self.setCentralWidget(root)
    def choose_audio(self):
        path,_=QFileDialog.getOpenFileName(self,"Choose Audio","","Audio (*.wav *.mp3 *.flac *.ogg *.m4a)")
        if path: self.source=path; self.status.setText(Path(path).name); self.start.setEnabled(True)
    def separate(self):
        try:
            status = first_run_status(create_separation_plan(self.source))
        except Exception as exc:
            self.failed(str(exc)); return
        allow_download = False
        if status.get("requires_model_download"):
            answer = QMessageBox.question(self, "Model Download Required", "The separation model is not cached yet and must be downloaded before first use. Continue?")
            if answer != QMessageBox.Yes:
                self.start.setEnabled(True); self.status.setText("Model download cancelled"); return
            allow_download = True
        self.start.setEnabled(False); self.status.setText("Separating…"); self.worker=SeparationWorker(self.source, allow_model_download=allow_download); self.worker.completed.connect(self.done); self.worker.failed.connect(self.failed); self.worker.status.connect(self.status.setText); self.worker.finished.connect(self.worker_finished); self.worker.start()
    def worker_finished(self): self.worker = None
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "Stem Separator", "Separation is still running. Wait for it to finish before closing.")
            event.ignore(); return
        event.accept()
    def done(self, result):
        self.start.setEnabled(True); stems=result.get("stems",{}); self.status.setText(f"Completed: {len(stems)} stems")
        QMessageBox.information(self,"Stem Separator",f"Separation complete.\n\nOutput: {result.get('output_directory','')}")
    def failed(self, message): self.start.setEnabled(True); self.status.setText("Separation failed"); QMessageBox.critical(self,"Stem Separator",message)

def main():
    app=QApplication.instance() or QApplication([]); window=MainWindow(); window.show(); return app.exec()
