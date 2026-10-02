from pathlib import Path
import os
from PySide6.QtCore import QElapsedTimer, QSettings, QThread, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget)
from stem_separator.engine import create_separation_plan, first_run_status, run_separation

class SeparationWorker(QThread):
    completed = Signal(dict); failed = Signal(str); status = Signal(str); progress = Signal(int, str)
    def __init__(self, source, output_root, mode, allow_model_download=False):
        super().__init__(); self.source=source; self.output_root=output_root; self.mode=mode; self.allow_model_download=allow_model_download
    def run(self):
        try:
            self.status.emit("Preparing separation model…")
            result=run_separation(self.source, output_root=self.output_root, mode=self.mode,
                allow_model_download=self.allow_model_download,
                progress_callback=lambda value,text: self.progress.emit(value,text))
            self.completed.emit(result)
        except Exception as exc: self.failed.emit(str(exc))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Stem Separator"); self.resize(820,520)
        self.source=""; self.worker=None; self.settings=QSettings("Stem Separator","Stem Separator")
        self.output_root=self.settings.value("output_root","")
        root=QWidget(); layout=QVBoxLayout(root); layout.setSpacing(14)
        title=QLabel("Stem Separator"); title.setStyleSheet("font-size: 26px; font-weight: 700;")
        subtitle=QLabel("Separate audio or video into clean music stems."); subtitle.setStyleSheet("color:#666;")
        layout.addWidget(title); layout.addWidget(subtitle)
        self.source_label=QLabel("No file selected")
        choose=QPushButton("Choose Audio or Video…"); choose.clicked.connect(self.choose_media)
        row=QHBoxLayout(); row.addWidget(choose); row.addWidget(self.source_label,1); layout.addLayout(row)
        form=QFormLayout()
        self.mode=QComboBox(); self.mode.addItem("Vocals + Music (2 stems)","2"); self.mode.addItem("4 Stems — Vocals, Drums, Bass, Other","4"); self.mode.addItem("6 Stems — Vocals, Drums, Bass, Guitar, Piano, Other","6"); self.mode.setCurrentIndex(1)
        form.addRow("Separation mode:",self.mode)
        self.output_label=QLabel(self.output_root or "Same folder as source")
        browse=QPushButton("Browse…"); browse.clicked.connect(self.choose_output)
        outrow=QHBoxLayout(); outrow.addWidget(self.output_label,1); outrow.addWidget(browse)
        outwidget=QWidget(); outwidget.setLayout(outrow); form.addRow("Output location:",outwidget); layout.addLayout(form)
        self.start=QPushButton("Separate Stems"); self.start.setMinimumHeight(44); self.start.setEnabled(False); self.start.clicked.connect(self.separate); layout.addWidget(self.start)
        self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.hide(); layout.addWidget(self.progress)
        self.status=QLabel("Choose a file to begin."); layout.addWidget(self.status)
        self.details=QLabel(""); self.details.setWordWrap(True); layout.addWidget(self.details)
        self.open_output=QPushButton("Open Output Folder"); self.open_output.setEnabled(False); self.open_output.clicked.connect(self.open_output_folder); layout.addWidget(self.open_output)
        layout.addStretch(); self.setCentralWidget(root)
        self.timer=QTimer(self); self.timer.timeout.connect(self.update_elapsed); self.elapsed=QElapsedTimer(); self.last_stage=""; self.last_output=""

    def choose_media(self):
        filt="Media (*.wav *.mp3 *.flac *.ogg *.m4a *.mp4 *.mov *.mkv *.avi *.webm *.m4v *.mpeg *.mpg)"
        path,_=QFileDialog.getOpenFileName(self,"Choose Audio or Video","",filt)
        if path: self.source=path; self.source_label.setText(Path(path).name); self.status.setText("Ready"); self.start.setEnabled(True)

    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,"Choose Output Folder",self.output_root or str(Path.home()))
        if path: self.output_root=path; self.settings.setValue("output_root",path); self.output_label.setText(path)

    def separate(self):
        model="htdemucs_6s" if self.mode.currentData()=="6" else "htdemucs"
        try: status=first_run_status(create_separation_plan(self.source,output_root=self.output_root or None,model_name=model))
        except Exception as exc: self.failed(str(exc)); return
        allow=False
        if status.get("requires_model_download"):
            answer=QMessageBox.question(self,"Model Download Required","The selected separation model must be downloaded before first use. Continue?")
            if answer!=QMessageBox.Yes: return
            allow=True
        self.start.setEnabled(False); self.mode.setEnabled(False); self.progress.setValue(0); self.progress.show(); self.elapsed.start(); self.timer.start(1000)
        self.last_stage="Preparing separation…"; self.status.setText(self.last_stage)
        self.worker=SeparationWorker(self.source,self.output_root or None,self.mode.currentData(),allow)
        self.worker.completed.connect(self.done); self.worker.failed.connect(self.failed); self.worker.status.connect(self.set_stage); self.worker.progress.connect(self.set_progress); self.worker.finished.connect(self.worker_finished); self.worker.start()

    def set_stage(self,text): self.last_stage=text; self.status.setText(text)
    def set_progress(self,value,text): self.progress.setValue(max(0,min(100,value))); self.set_stage(text)
    def update_elapsed(self):
        if self.elapsed.isValid(): self.details.setText(f"{self.last_stage}   •   Elapsed: {self.elapsed.elapsed()//1000}s")

    def worker_finished(self): self.timer.stop(); self.worker=None
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning(): QMessageBox.information(self,"Stem Separator","Separation is still running. Wait for it to finish before closing."); event.ignore(); return
        event.accept()

    def done(self,result):
        self.start.setEnabled(True); self.mode.setEnabled(True); self.progress.setValue(100); self.last_output=result.get("output_directory",""); stems=result.get("stems",{})
        self.status.setText(f"Complete — {len(stems)} stems exported"); self.details.setText("\n".join(f"{name}: {path}" for name,path in stems.items())); self.open_output.setEnabled(bool(self.last_output))
        QMessageBox.information(self,"Stem Separator",f"Separation complete.\n\nSaved to:\n{self.last_output}")

    def failed(self,message):
        self.timer.stop(); self.start.setEnabled(bool(self.source)); self.mode.setEnabled(True); self.progress.hide(); self.status.setText("Separation failed"); QMessageBox.critical(self,"Stem Separator",message)

    def open_output_folder(self):
        if self.last_output and Path(self.last_output).is_dir(): os.startfile(self.last_output)

def main():
    app=QApplication.instance() or QApplication([]); window=MainWindow(); window.show(); return app.exec()
