"""主窗口。"""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QAction, QBrush, QColor

from app.config import Config, default_output_dir, load_config, save_config
from app.core.pipeline import cache_dir
from app.models import FileJob, FileStatus
from app.ui.file_list_model import FileListModel
from app.ui.settings_dialog import SettingsDialog
from app.ui.worker import QueueWorker

from PySide6.QtCore import QThread

MEDIA_EXTS = {
    ".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm",
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".m4v", ".mpg", ".mpeg",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg = load_config()
        self._model = FileListModel(self)
        self._thread: QThread | None = None
        self._worker: QueueWorker | None = None
        self._queue_phase: str = ""  # "extract" | "recognize"
        self._setup_ui()
        self.setWindowTitle("Scrybe —— 批量媒体转字幕")
        self.resize(900, 650)

    # ---- UI ----
    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 工具栏
        tb = QToolBar()
        tb.setMovable(False)
        self._act_add = QAction("添加文件", self)
        self._act_add.triggered.connect(self._on_add_files)
        tb.addAction(self._act_add)
        self._act_folder = QAction("添加文件夹", self)
        self._act_folder.triggered.connect(self._on_add_folder)
        tb.addAction(self._act_folder)
        tb.addSeparator()
        self._act_output = QAction("选择输出目录", self)
        self._act_output.triggered.connect(self._on_choose_output)
        tb.addAction(self._act_output)
        self._act_settings = QAction("设置", self)
        self._act_settings.triggered.connect(self._on_settings)
        tb.addAction(self._act_settings)
        tb.addSeparator()
        self._act_start = QAction("▶ 开始转换", self)
        self._act_start.triggered.connect(self._on_start)
        tb.addAction(self._act_start)
        self._act_stop = QAction("■ 停止", self)
        self._act_stop.setEnabled(False)
        self._act_stop.triggered.connect(self._on_stop)
        tb.addAction(self._act_stop)
        self._act_retry = QAction("↻ 重试失败", self)
        self._act_retry.setEnabled(False)
        self._act_retry.setToolTip("重新识别失败的任务（音频已缓存，无需重新提取）")
        self._act_retry.triggered.connect(self._on_retry)
        tb.addAction(self._act_retry)
        self.addToolBar(tb)

        # 文件表
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.setAcceptDrops(True)
        self._table.setDragDropMode(QTableView.DropOnly)
        self._table.dragEnterEvent = self._dragEnterEvent
        self._table.dropEvent = self._dropEvent

        # 底部区域
        bottom = QVBoxLayout()

        # 进度条
        pbar_row = QHBoxLayout()
        self._lbl_file = QLabel("就绪")
        pbar_row.addWidget(self._lbl_file)
        self._pbar_file = QProgressBar()
        self._pbar_file.setMaximum(100)
        self._pbar_file.setMinimum(0)
        self._pbar_file.setMaximumWidth(300)
        pbar_row.addWidget(self._pbar_file)
        pbar_row.addStretch()
        self._lbl_queue = QLabel("0 / 0")
        pbar_row.addWidget(self._lbl_queue)
        self._pbar_queue = QProgressBar()
        self._pbar_queue.setMaximum(100)
        self._pbar_queue.setMinimum(0)
        self._pbar_queue.setMaximumWidth(300)
        pbar_row.addWidget(self._pbar_queue)
        bottom.addLayout(pbar_row)

        # 日志
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        bottom.addWidget(self._log)

        # 组装
        splitter = QSplitter(Qt.Vertical)
        top_w = QWidget()
        top_ly = QVBoxLayout(top_w)
        top_ly.setContentsMargins(0, 0, 0, 0)
        top_ly.addWidget(self._table)
        splitter.addWidget(top_w)
        bottom_w = QWidget()
        bottom_w.setLayout(bottom)
        splitter.addWidget(bottom_w)
        splitter.setSizes([350, 250])
        root.addWidget(splitter)

    # ---- 文件操作 ----
    def _add_paths(self, paths: list[Path]) -> None:
        existing = {j.source.resolve() for j in self._model.jobs()}
        new: list[FileJob] = []
        for p in paths:
            if not p.is_file():
                continue
            if p.suffix.lower() not in MEDIA_EXTS:
                continue
            ap = p.resolve()
            if ap in existing:
                continue
            existing.add(ap)
            od = Path(self._cfg.output_dir) if self._cfg.output_dir else default_output_dir()
            new.append(FileJob(source=ap, output_dir=od, size_bytes=ap.stat().st_size))
        if new:
            self._model.add_jobs(new)
            self._log_msg("info", f"已添加 {len(new)} 个文件")

    def _on_add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择媒体文件", "",
            "媒体文件 (*.mp4 *.mkv *.mov *.avi *.wmv *.flv *.webm *.mp3 *.wav *.m4a *.flac *.aac *.ogg);;所有文件 (*.*)",
        )
        if files:
            self._add_paths([Path(f) for f in files])

    def _on_add_folder(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if d:
            paths = [p for p in Path(d).rglob("*") if p.suffix.lower() in MEDIA_EXTS]
            self._add_paths(paths)

    def _on_choose_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择字幕输出目录")
        if d:
            self._cfg.output_dir = d
            save_config(self._cfg)
            od = Path(d)
            for j in self._model._jobs:
                j.output_dir = od
            self._log_msg("info", f"输出目录: {d}")

    # ---- 设置 ----
    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._cfg, self)
        if dlg.exec() == SettingsDialog.Accepted:
            save_config(self._cfg)
            od = Path(self._cfg.output_dir) if self._cfg.output_dir else default_output_dir()
            for j in self._model._jobs:
                j.output_dir = od
            self._log_msg("info", "设置已保存")

    # ---- 队列 ----
    def _on_start(self) -> None:
        jobs = self._model.jobs()
        if not jobs:
            QMessageBox.information(self, "提示", "请先添加至少一个文件。")
            return
        if all(j.status == FileStatus.SUCCESS for j in jobs):
            QMessageBox.information(self, "提示", "列表中的文件都已成功转换，请先添加新文件。")
            return
        self._model.reset_statuses()
        self._log.clear()
        self._run_queue()

    def _on_retry(self) -> None:
        """重试失败项：音频已缓存，直接走识别，不重新提取。"""
        self._model.reset_failed()
        self._log.clear()
        self._log_msg("info", "重试失败项…")
        self._run_queue()

    def _run_queue(self) -> None:
        jobs = self._model.jobs()
        self._act_start.setEnabled(False)
        self._act_stop.setEnabled(True)
        self._act_retry.setEnabled(False)
        self._act_add.setEnabled(False)
        self._act_folder.setEnabled(False)
        self._act_settings.setEnabled(False)

        self._thread = QThread(self)
        self._worker = QueueWorker(jobs, self._cfg)
        self._worker.moveToThread(self._thread)

        ws = self._worker.signals
        ws.log.connect(self._log_msg)
        ws.queue_phase.connect(self._on_queue_phase)
        ws.file_started.connect(self._on_file_started)
        ws.file_progress.connect(self._on_file_progress)
        ws.file_done.connect(self._on_file_done)
        ws.queue_progress.connect(self._on_queue_progress)
        ws.queue_finished.connect(self._on_queue_finished)
        ws.queue_finished.connect(self._worker.deleteLater)
        ws.queue_finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, "_thread", None))
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def _on_stop(self) -> None:
        if self._worker:
            self._worker.stop()
            self._act_stop.setEnabled(False)
            self._log_msg("info", "正在停止（当前任务完成后生效）…")

    def _on_file_started(self, idx: int) -> None:
        job = self._model._jobs[idx]
        self._lbl_file.setText(job.source.name)
        self._pbar_file.setValue(0)

    def _on_file_progress(self, idx: int, pct: int) -> None:
        self._pbar_file.setValue(pct)

    def _on_file_done(self, idx: int, result: str, detail: str) -> None:
        status = {"success": FileStatus.SUCCESS, "failed": FileStatus.FAILED, "canceled": FileStatus.CANCELED}.get(result, FileStatus.FAILED)
        self._model.set_status(idx, status, "" if result == "success" else detail)

    def _on_queue_phase(self, phase: str) -> None:
        self._queue_phase = phase
        self._lbl_file.setText("正在提取音频…" if phase == "extract" else "正在识别字幕…")

    def _on_queue_progress(self, done: int, total: int) -> None:
        pct = int(done / total * 100) if total else 0
        self._pbar_queue.setValue(pct)
        prefix = "提取" if self._queue_phase == "extract" else "识别"
        self._lbl_queue.setText(f"{prefix} {done} / {total}")

    def _on_queue_finished(self) -> None:
        self._act_start.setEnabled(True)
        self._act_stop.setEnabled(False)
        self._act_add.setEnabled(True)
        self._act_folder.setEnabled(True)
        self._act_settings.setEnabled(True)
        self._lbl_file.setText("完成")
        has_failed = any(j.status == FileStatus.FAILED for j in self._model._jobs)
        self._act_retry.setEnabled(has_failed)

        # 汇总
        jobs = self._model._jobs
        ok = sum(1 for j in jobs if j.status == FileStatus.SUCCESS)
        ng = sum(1 for j in jobs if j.status == FileStatus.FAILED)
        self._log_msg("info", f"====== 转换完成：成功 {ok} 个，失败 {ng} 个 ======")
        if ng > 0:
            QMessageBox.information(self, "处理完成", f"成功 {ok} 个\n失败 {ng} 个\n\n失败的详情请查看下方日志。")

    def _log_msg(self, level: str, msg: str) -> None:
        self._log.appendPlainText(f"[{level}] {msg}")

    # ---- 拖拽 ----
    def _dragEnterEvent(self, event) -> None:  # type: ignore[override]
        mime: QMimeData = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()

    def _dropEvent(self, event) -> None:  # type: ignore[override]
        mime: QMimeData = event.mimeData()
        if mime.hasUrls():
            paths = [Path(u.toLocalFile()) for u in mime.urls()]
            self._add_paths(paths)

    # ---- 关闭 ----
    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            r = QMessageBox.question(self, "确认", "任务正在运行，确定要退出吗？\n（正在处理的文件完成后才会退出）",
                                     QMessageBox.Yes | QMessageBox.No)
            if r == QMessageBox.No:
                event.ignore()
                return
            if self._worker:
                self._worker.stop()
            self._thread.quit()
            self._thread.wait(10000)
        shutil.rmtree(cache_dir(), ignore_errors=True)
        event.accept()
