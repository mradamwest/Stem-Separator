from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget
from stem_separator.engine import run_separation

class SeparationWorker(QThread):
    completed = Signal(dict); failed = Signal(str)
    def __init__(self, source): super().__init__(); self.source = source
    def run(self):
        try: self.completed.emit(run_separation(self.source, allow_model_download=True))
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
        self.start.setEnabled(False); self.status.setText("Separating…"); self.worker=SeparationWorker(self.source); self.worker.completed.connect(self.done); self.worker.failed.connect(self.failed); self.worker.start()
    def done(self, result):
        self.start.setEnabled(True); stems=result.get("stems",{}); self.status.setText(f"Completed: {len(stems)} stems")
        QMessageBox.information(self,"Stem Separator",f"Separation complete.\n\nOutput: {result.get('output_directory','')}")
    def failed(self, message): self.start.setEnabled(True); self.status.setText("Separation failed"); QMessageBox.critical(self,"Stem Separator",message)

def main():
    app=QApplication.instance() or QApplication([]); window=MainWindow(); window.show(); return app.exec()
