"""设置对话框。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import Config, default_output_dir


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self._cfg = config
        self._setup_ui()
        self._load()

    # ---- UI ----
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)

        # 识别服务
        svc = QGroupBox("识别服务")
        svc_ly = QFormLayout(svc)
        self._cmb_provider = QComboBox()
        self._cmb_provider.addItem("阿里云百炼 (Paraformer)", "dashscope")
        self._cmb_provider.addItem("OpenAI 兼容", "openai_compat")
        self._cmb_provider.currentIndexChanged.connect(self._on_provider_changed)
        svc_ly.addRow("服务商:", self._cmb_provider)
        root.addWidget(svc)

        # 百炼
        self._grp_ds = QGroupBox("阿里云百炼")
        ds_ly = QFormLayout(self._grp_ds)
        self._edt_ds_key = QLineEdit()
        self._edt_ds_key.setEchoMode(QLineEdit.Password)
        self._edt_ds_key.setPlaceholderText("sk-xxxxxxxx")
        ds_ly.addRow("API Key:", self._edt_ds_key)
        root.addWidget(self._grp_ds)

        # OpenAI 兼容
        self._grp_oa = QGroupBox("OpenAI 兼容")
        oa_ly = QFormLayout(self._grp_oa)
        self._edt_oa_url = QLineEdit()
        self._edt_oa_url.setPlaceholderText("https://api.openai.com")
        oa_ly.addRow("Base URL:", self._edt_oa_url)
        self._edt_oa_key = QLineEdit()
        self._edt_oa_key.setEchoMode(QLineEdit.Password)
        self._edt_oa_key.setPlaceholderText("sk-xxxxxxxx")
        oa_ly.addRow("API Key:", self._edt_oa_key)
        self._edt_oa_model = QLineEdit()
        self._edt_oa_model.setPlaceholderText("whisper-1")
        oa_ly.addRow("模型:", self._edt_oa_model)
        root.addWidget(self._grp_oa)

        # 通用
        common = QGroupBox("通用")
        com_ly = QFormLayout(common)
        self._cmb_lang = QComboBox()
        self._cmb_lang.addItem("中文", "zh")
        self._cmb_lang.addItem("English", "en")
        self._cmb_lang.addItem("自动", "auto")
        com_ly.addRow("识别语言:", self._cmb_lang)

        out_row = QHBoxLayout()
        self._edt_out = QLineEdit()
        self._edt_out.setPlaceholderText(str(default_output_dir()))
        out_row.addWidget(self._edt_out)
        btn = QPushButton("浏览…")
        btn.clicked.connect(self._browse_output)
        out_row.addWidget(btn)
        com_ly.addRow("输出目录:", out_row)
        root.addWidget(common)

        # 高级
        adv = QGroupBox("高级")
        adv_ly = QFormLayout(adv)
        self._spn_chunk = QSpinBox()
        self._spn_chunk.setRange(60, 3600)
        self._spn_chunk.setSuffix(" 秒")
        self._spn_chunk.setToolTip("OpenAI 兼容下音频超过 24MB 时的切块时长")
        adv_ly.addRow("切块时长:", self._spn_chunk)
        self._spn_gap = QSpinBox()
        self._spn_gap.setRange(0, 2000)
        self._spn_gap.setSuffix(" ms")
        self._spn_gap.setToolTip("相邻两句间隔小于此值时合并为一条字幕")
        adv_ly.addRow("合并阈值:", self._spn_gap)
        self._spn_parallel = QSpinBox()
        self._spn_parallel.setRange(1, 8)
        self._spn_parallel.setSuffix(" 个")
        self._spn_parallel.setToolTip("同时提取多少个文件的音频（API 识别始终按顺序逐个进行）")
        adv_ly.addRow("并行提取数:", self._spn_parallel)
        root.addWidget(adv)

        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _load(self) -> None:
        c = self._cfg
        idx = self._cmb_provider.findData(c.provider)
        if idx >= 0:
            self._cmb_provider.setCurrentIndex(idx)
        self._edt_ds_key.setText(c.dashscope_api_key)
        self._edt_oa_url.setText(c.openai_base_url)
        self._edt_oa_key.setText(c.openai_api_key)
        self._edt_oa_model.setText(c.openai_model)
        idx = self._cmb_lang.findData(c.language)
        if idx >= 0:
            self._cmb_lang.setCurrentIndex(idx)
        self._edt_out.setText(c.output_dir)
        self._spn_chunk.setValue(c.chunk_seconds)
        self._spn_gap.setValue(c.merge_gap_ms)
        self._spn_parallel.setValue(c.parallel_extractions)
        self._on_provider_changed()

    # ---- slots ----
    def _on_provider_changed(self) -> None:
        is_ds = self._cmb_provider.currentData() == "dashscope"
        self._grp_ds.setVisible(is_ds)
        self._grp_oa.setVisible(not is_ds)

    def _browse_output(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "选择字幕输出目录")
        if d:
            self._edt_out.setText(d)

    def _on_ok(self) -> None:
        c = self._cfg
        c.provider = self._cmb_provider.currentData()
        c.dashscope_api_key = self._edt_ds_key.text().strip()
        c.openai_base_url = self._edt_oa_url.text().strip()
        c.openai_api_key = self._edt_oa_key.text().strip()
        c.openai_model = self._edt_oa_model.text().strip() or "whisper-1"
        c.language = self._cmb_lang.currentData()
        c.output_dir = self._edt_out.text().strip()
        c.chunk_seconds = self._spn_chunk.value()
        c.merge_gap_ms = self._spn_gap.value()
        c.parallel_extractions = self._spn_parallel.value()
        self.accept()
