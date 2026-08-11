"""文件列表的 QAbstractTableModel。"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QColor

from app.models import FileJob, FileStatus


_COLUMNS = ("文件名", "大小", "状态", "详情")

_STATUS_COLORS = {
    FileStatus.PENDING: None,
    FileStatus.PROCESSING: QColor("#2196F3"),
    FileStatus.SUCCESS: QColor("#4CAF50"),
    FileStatus.FAILED: QColor("#F44336"),
    FileStatus.CANCELED: QColor("#9E9E9E"),
}


def _format_size(n_bytes: int) -> str:
    if n_bytes < 1024:
        return f"{n_bytes} B"
    if n_bytes < 1024 * 1024:
        return f"{n_bytes / 1024:.1f} KB"
    if n_bytes < 1024 * 1024 * 1024:
        return f"{n_bytes / 1024 / 1024:.1f} MB"
    return f"{n_bytes / 1024 / 1024 / 1024:.2f} GB"


class FileListModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: list[FileJob] = []

    # ---- public ----
    def jobs(self) -> list[FileJob]:
        return list(self._jobs)

    def add_jobs(self, jobs: list[FileJob]) -> None:
        if not jobs:
            return
        first = len(self._jobs)
        self.beginInsertRows(self.index(first, 0), first, first + len(jobs) - 1)
        self._jobs.extend(jobs)
        self.endInsertRows()

    def clear(self) -> None:
        if not self._jobs:
            return
        self.beginRemoveRows(self.index(0, 0), 0, len(self._jobs) - 1)
        self._jobs.clear()
        self.endRemoveRows()

    def set_status(self, row: int, status: FileStatus, error: str = "") -> None:
        self._jobs[row].status = status
        if error:
            self._jobs[row].error = error
        self.dataChanged.emit(self.index(row, 2), self.index(row, 3))

    def reset_statuses(self) -> None:
        for j in self._jobs:
            j.status = FileStatus.PENDING
            j.error = ""
            j.progress = 0
        self.dataChanged.emit(self.index(0, 2), self.index(len(self._jobs) - 1, 3))

    # ---- QAbstractTableModel ----
    def rowCount(self, parent=None) -> int:
        return len(self._jobs)

    def columnCount(self, parent=None) -> int:
        return len(_COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        job = self._jobs[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return job.source.name
            if col == 1:
                return _format_size(job.size_bytes)
            if col == 2:
                return job.status.value
            if col == 3:
                return job.error
        elif role == Qt.ForegroundRole:
            color = _STATUS_COLORS.get(job.status)
            if color:
                return color
            return None  # default
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole and section < len(_COLUMNS):
            return _COLUMNS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled
