import csv
import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


class MainWindow(QMainWindow):
    TABLE_COLUMNS = [
        "",
        "Datum",
        "KW",
        "Kunde",
        "Projekt",
        "Mitarbeiter",
        "Status",
        "Automatikstatus",
        "RE",
        "Adresse",
        "Geändert",
        "Notiz",
    ]

    def __init__(self, config_loader, importer, extractor, classifier, builder, grouping, lexware_export_service=None) -> None:
        super().__init__()
        self.setWindowTitle("Rechnungsvorschlag Tool")
        self.resize(2080, 1200)

        self.config_loader = config_loader
        self.importer = importer
        self.extractor = extractor
        self.classifier = classifier
        self.builder = builder
        self.grouping = grouping
        self.lexware_export_service = lexware_export_service

        self.current_file_path: str = ""
        self.groups: list[dict] = []
        self.visible_groups: list[dict] = []
        self.last_action: dict | None = None
        self.change_log: list[str] = []

        self.current_sort_column = 1
        self.current_sort_order = Qt.AscendingOrder

        self.open_button = QPushButton("Datei öffnen")
        self.load_project_button = QPushButton("Projekt laden")
        self.save_project_button = QPushButton("Projekt speichern")
        self.load_session_button = QPushButton("Sitzung laden")
        self.save_session_button = QPushButton("Sitzung speichern")
        self.export_csv_button = QPushButton("CSV exportieren")
        self.export_json_button = QPushButton("JSON exportieren")
        self.lexware_export_button = QPushButton("Lexware Draft exportieren")

        self.mark_approved_button = QPushButton("Freigeben")
        self.mark_review_button = QPushButton("Prüfen")
        self.mark_ignore_button = QPushButton("Ignorieren")
        self.undo_button = QPushButton("Letzte Änderung rückgängig")

        self.selection_approved_button = QPushButton("Auswahl freigeben")
        self.selection_review_button = QPushButton("Auswahl prüfen")
        self.selection_ignore_button = QPushButton("Auswahl ignorieren")
        self.selection_open_button = QPushButton("Auswahl auf offen")

        self.bulk_approved_button = QPushButton("Alle sichtbaren freigeben")
        self.bulk_review_button = QPushButton("Alle sichtbaren prüfen")
        self.bulk_ignore_button = QPushButton("Alle sichtbaren ignorieren")
        self.bulk_open_button = QPushButton("Alle sichtbaren auf offen")

        self.show_open_only_button = QPushButton("Nur offene anzeigen")
        self.show_all_manual_button = QPushButton("Alle manuellen Status anzeigen")

        self.save_note_button = QPushButton("Notiz speichern")

        self.auto_filter_combo = QComboBox()
        self.auto_filter_combo.addItems(["Alle", "Nur Einsätze", "Nur Prüffälle"])
        self.auto_filter_combo.setMinimumWidth(150)

        self.manual_filter_combo = QComboBox()
        self.manual_filter_combo.addItems(["Alle", "Offen", "Freigegeben", "Prüfen", "Ignorieren"])
        self.manual_filter_combo.setMinimumWidth(150)

        self.changed_filter_combo = QComboBox()
        self.changed_filter_combo.addItems(["Alle", "Nur geänderte", "Nur ungeänderte"])
        self.changed_filter_combo.setMinimumWidth(150)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Suche nach Kunde, Projekt, Mitarbeiter, Adresse, Auftrag, Bemerkung ...")
        self.search_input.setMinimumWidth(320)

        self.summary_visible_label = QLabel("Sichtbar: 0")
        self.summary_selected_label = QLabel("Ausgewählt: 0")
        self.summary_open_label = QLabel("Offen: 0")
        self.summary_approved_label = QLabel("Freigegeben: 0")
        self.summary_review_label = QLabel("Prüfen: 0")
        self.summary_ignored_label = QLabel("Ignorieren: 0")
        self.summary_auto_review_label = QLabel("Prüffälle: 0")

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(len(self.TABLE_COLUMNS))
        self.table_widget.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.horizontalHeader().setSectionsClickable(True)
        self.table_widget.horizontalHeader().setSortIndicatorShown(True)
        self.table_widget.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self.open_context_menu)

        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        for i in range(1, 11):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        header.setSectionResizeMode(11, QHeaderView.Stretch)

        header.resizeSection(0, 36)
        header.resizeSection(1, 110)
        header.resizeSection(2, 70)
        header.resizeSection(3, 220)
        header.resizeSection(4, 220)
        header.resizeSection(5, 180)
        header.resizeSection(6, 120)
        header.resizeSection(7, 130)
        header.resizeSection(8, 100)
        header.resizeSection(9, 240)
        header.resizeSection(10, 90)

        self.detail_view = QPlainTextEdit()
        self.detail_view.setReadOnly(True)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Manuelle Notiz zur ausgewählten Gruppe ...")
        self.note_edit.setMinimumHeight(160)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Änderungsverlauf der aktuellen Sitzung ...")
        self.log_view.setMinimumHeight(180)

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.open_button)
        top_bar.addWidget(self.load_project_button)
        top_bar.addWidget(self.save_project_button)
        top_bar.addWidget(self.load_session_button)
        top_bar.addWidget(self.save_session_button)
        top_bar.addWidget(self.export_csv_button)
        top_bar.addWidget(self.export_json_button)
        top_bar.addWidget(self.lexware_export_button)
        top_bar.addStretch()

        filter_bar = QHBoxLayout()
        filter_bar.addWidget(self.auto_filter_combo)
        filter_bar.addWidget(self.manual_filter_combo)
        filter_bar.addWidget(self.changed_filter_combo)
        filter_bar.addWidget(self.show_open_only_button)
        filter_bar.addWidget(self.show_all_manual_button)
        filter_bar.addWidget(self.search_input, 1)

        action_bar = QHBoxLayout()
        action_bar.addWidget(self.mark_approved_button)
        action_bar.addWidget(self.mark_review_button)
        action_bar.addWidget(self.mark_ignore_button)
        action_bar.addWidget(self.undo_button)
        action_bar.addStretch()

        selection_action_bar = QHBoxLayout()
        selection_action_bar.addWidget(self.selection_approved_button)
        selection_action_bar.addWidget(self.selection_review_button)
        selection_action_bar.addWidget(self.selection_ignore_button)
        selection_action_bar.addWidget(self.selection_open_button)
        selection_action_bar.addStretch()

        bulk_action_bar = QHBoxLayout()
        bulk_action_bar.addWidget(self.bulk_approved_button)
        bulk_action_bar.addWidget(self.bulk_review_button)
        bulk_action_bar.addWidget(self.bulk_ignore_button)
        bulk_action_bar.addWidget(self.bulk_open_button)
        bulk_action_bar.addStretch()

        summary_bar = QHBoxLayout()
        summary_bar.addWidget(self.summary_visible_label)
        summary_bar.addWidget(self.summary_selected_label)
        summary_bar.addWidget(self.summary_open_label)
        summary_bar.addWidget(self.summary_approved_label)
        summary_bar.addWidget(self.summary_review_label)
        summary_bar.addWidget(self.summary_ignored_label)
        summary_bar.addWidget(self.summary_auto_review_label)
        summary_bar.addStretch()

        note_bar = QVBoxLayout()
        note_bar.addWidget(QLabel("Manuelle Notiz"))
        note_bar.addWidget(self.note_edit)
        note_bar.addWidget(self.save_note_button)

        log_bar = QVBoxLayout()
        log_bar.addWidget(QLabel("Änderungsverlauf"))
        log_bar.addWidget(self.log_view)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addLayout(top_bar)
        left_layout.addLayout(filter_bar)
        left_layout.addLayout(action_bar)
        left_layout.addLayout(selection_action_bar)
        left_layout.addLayout(bulk_action_bar)
        left_layout.addLayout(summary_bar)
        left_layout.addWidget(self.table_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(self.detail_view, 3)
        right_layout.addLayout(note_bar, 2)
        right_layout.addLayout(log_bar, 2)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([1440, 640])

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.addWidget(splitter)
        self.setCentralWidget(central)

        self.open_button.clicked.connect(self.open_file_dialog)
        self.load_project_button.clicked.connect(self.load_project_file)
        self.save_project_button.clicked.connect(self.save_project_file)
        self.load_session_button.clicked.connect(self.load_session_file)
        self.save_session_button.clicked.connect(self.save_session_file)
        self.export_csv_button.clicked.connect(self.export_visible_groups_to_csv)
        self.export_json_button.clicked.connect(self.export_visible_groups_to_json)
        self.lexware_export_button.clicked.connect(self.export_selected_groups_to_lexware_draft)
        self.save_note_button.clicked.connect(self.save_note_for_selected)
        self.undo_button.clicked.connect(self.undo_last_action)

        self.mark_approved_button.clicked.connect(lambda: self.set_manual_status_for_selected("freigegeben", advance=True))
        self.mark_review_button.clicked.connect(lambda: self.set_manual_status_for_selected("pruefen", advance=True))
        self.mark_ignore_button.clicked.connect(lambda: self.set_manual_status_for_selected("ignorieren", advance=True))

        self.selection_approved_button.clicked.connect(lambda: self.set_manual_status_for_selected_rows("freigegeben"))
        self.selection_review_button.clicked.connect(lambda: self.set_manual_status_for_selected_rows("pruefen"))
        self.selection_ignore_button.clicked.connect(lambda: self.set_manual_status_for_selected_rows("ignorieren"))
        self.selection_open_button.clicked.connect(lambda: self.set_manual_status_for_selected_rows("offen"))

        self.bulk_approved_button.clicked.connect(lambda: self.set_manual_status_for_visible("freigegeben"))
        self.bulk_review_button.clicked.connect(lambda: self.set_manual_status_for_visible("pruefen"))
        self.bulk_ignore_button.clicked.connect(lambda: self.set_manual_status_for_visible("ignorieren"))
        self.bulk_open_button.clicked.connect(lambda: self.set_manual_status_for_visible("offen"))

        self.show_open_only_button.clicked.connect(self.activate_open_only_mode)
        self.show_all_manual_button.clicked.connect(self.activate_show_all_mode)

        self.auto_filter_combo.currentIndexChanged.connect(self.refresh_table)
        self.manual_filter_combo.currentIndexChanged.connect(self.refresh_table)
        self.changed_filter_combo.currentIndexChanged.connect(self.refresh_table)
        self.search_input.textChanged.connect(self.refresh_table)
        self.table_widget.itemSelectionChanged.connect(self.on_table_selection_changed)
        self.table_widget.itemDoubleClicked.connect(self.on_item_double_clicked)

        self.shortcut_approve = QShortcut(QKeySequence("F"), self)
        self.shortcut_review = QShortcut(QKeySequence("P"), self)
        self.shortcut_ignore = QShortcut(QKeySequence("I"), self)
        self.shortcut_open = QShortcut(QKeySequence("O"), self)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)

        self.shortcut_approve.activated.connect(lambda: self.apply_shortcut_status("freigegeben"))
        self.shortcut_review.activated.connect(lambda: self.apply_shortcut_status("pruefen"))
        self.shortcut_ignore.activated.connect(lambda: self.apply_shortcut_status("ignorieren"))
        self.shortcut_open.activated.connect(lambda: self.apply_shortcut_status("offen"))
        self.shortcut_undo.activated.connect(self.undo_last_action)

    def _log_action(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.change_log.insert(0, f"{timestamp} | {text}")
        self.change_log = self.change_log[:500]
        self.log_view.setPlainText("\n".join(self.change_log))

    def _mark_changed(self, groups: list[dict]) -> None:
        changed_at = datetime.now().strftime("%H:%M:%S")
        for group in groups:
            group["_last_changed_at"] = changed_at

    def _status_symbol(self, group: dict) -> str:
        manual = group.get("manueller_status", "offen")
        auto = group.get("gruppenstatus", "")

        if manual == "freigegeben":
            return "✓"
        if manual == "pruefen":
            return "?"
        if manual == "ignorieren":
            return "–"
        if auto == "prueffall":
            return "!"
        return ""

    def _selected_rows(self) -> list[int]:
        model = self.table_widget.selectionModel()
        if model is None:
            return []
        rows = sorted({index.row() for index in model.selectedRows()})
        return [row for row in rows if 0 <= row < len(self.visible_groups)]

    def _selected_groups(self) -> list[dict]:
        return [self.visible_groups[row] for row in self._selected_rows()]

    def open_context_menu(self, position) -> None:
        row = self.table_widget.rowAt(position.y())
        if row < 0 or row >= len(self.visible_groups):
            return

        selected_rows_before = self._selected_rows()
        if row not in selected_rows_before:
            self._set_selected_row(row)

        menu = QMenu(self)

        approve_action = QAction("Freigeben", self)
        review_action = QAction("Prüfen", self)
        ignore_action = QAction("Ignorieren", self)
        open_action = QAction("Auf offen setzen", self)

        approve_selection_action = QAction("Auswahl freigeben", self)
        review_selection_action = QAction("Auswahl prüfen", self)
        ignore_selection_action = QAction("Auswahl ignorieren", self)
        open_selection_action = QAction("Auswahl auf offen setzen", self)

        save_note_action = QAction("Notiz speichern", self)
        copy_details_action = QAction("Details kopieren", self)

        approve_action.triggered.connect(lambda: self.set_manual_status_for_selected("freigegeben", advance=False))
        review_action.triggered.connect(lambda: self.set_manual_status_for_selected("pruefen", advance=False))
        ignore_action.triggered.connect(lambda: self.set_manual_status_for_selected("ignorieren", advance=False))
        open_action.triggered.connect(lambda: self.set_manual_status_for_selected("offen", advance=False))

        approve_selection_action.triggered.connect(lambda: self.set_manual_status_for_selected_rows("freigegeben"))
        review_selection_action.triggered.connect(lambda: self.set_manual_status_for_selected_rows("pruefen"))
        ignore_selection_action.triggered.connect(lambda: self.set_manual_status_for_selected_rows("ignorieren"))
        open_selection_action.triggered.connect(lambda: self.set_manual_status_for_selected_rows("offen"))

        save_note_action.triggered.connect(self.save_note_for_selected)
        copy_details_action.triggered.connect(self.copy_selected_details_to_clipboard)

        menu.addAction(approve_action)
        menu.addAction(review_action)
        menu.addAction(ignore_action)
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(approve_selection_action)
        menu.addAction(review_selection_action)
        menu.addAction(ignore_selection_action)
        menu.addAction(open_selection_action)
        menu.addSeparator()
        menu.addAction(save_note_action)
        menu.addAction(copy_details_action)

        menu.exec(self.table_widget.viewport().mapToGlobal(position))

    def copy_selected_details_to_clipboard(self) -> None:
        groups = self._selected_groups()
        if not groups:
            row = self._current_selected_row()
            if row < 0:
                return
            groups = [self.visible_groups[row]]

        texts = [self._build_detail_text(group) for group in groups]
        QApplication.clipboard().setText(("\n" + ("-" * 80) + "\n").join(texts))
        self._log_action(f"Details kopiert | {len(groups)} Gruppe(n)")

    def on_header_clicked(self, column: int) -> None:
        if self.current_sort_column == column:
            self.current_sort_order = Qt.DescendingOrder if self.current_sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self.current_sort_column = column
            self.current_sort_order = Qt.AscendingOrder

        self.table_widget.horizontalHeader().setSortIndicator(column, self.current_sort_order)
        self.refresh_table()

    def _is_text_input_focused(self) -> bool:
        focused = self.focusWidget()
        return focused in {self.note_edit, self.search_input}

    def _current_selected_row(self) -> int:
        row = self.table_widget.currentRow()
        if row < 0 or row >= len(self.visible_groups):
            return -1
        return row

    def _set_selected_row(self, row: int) -> None:
        if 0 <= row < self.table_widget.rowCount():
            self.table_widget.clearSelection()
            self.table_widget.selectRow(row)
            self.table_widget.setCurrentCell(row, 0)

    def apply_shortcut_status(self, status: str) -> None:
        if self._is_text_input_focused():
            return

        selected_rows = self._selected_rows()
        if len(selected_rows) > 1:
            self.set_manual_status_for_selected_rows(status)
        else:
            self.set_manual_status_for_selected(status, advance=True)

    def _capture_group_state(self, group: dict) -> dict:
        return {
            "key": self._build_group_key(group),
            "manueller_status": group.get("manueller_status", "offen"),
            "manuelle_notiz": group.get("manuelle_notiz", ""),
            "_last_changed_at": group.get("_last_changed_at", ""),
        }

    def _restore_group_states(self, states: list[dict]) -> None:
        state_map = {state["key"]: state for state in states}
        for group in self.groups:
            key = self._build_group_key(group)
            if key in state_map:
                group["manueller_status"] = state_map[key].get("manueller_status", "offen")
                group["manuelle_notiz"] = state_map[key].get("manuelle_notiz", "")
                group["_last_changed_at"] = state_map[key].get("_last_changed_at", "")

    def undo_last_action(self) -> None:
        if not self.last_action:
            return

        previous_states = self.last_action.get("previous_states", [])
        selected_keys = self.last_action.get("selected_keys", [])

        self._restore_group_states(previous_states)
        self._save_manual_data()
        self.refresh_table()

        if selected_keys:
            self._select_groups_by_keys(selected_keys)

        self._log_action("Rückgängig ausgeführt")
        self.last_action = None

    def _confirm_bulk_action(self, title: str, new_status: str, count: int) -> bool:
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText("Soll der manuelle Status wirklich geändert werden?")
        msg.setInformativeText(f"Neuer Status: {new_status}\nBetroffene Gruppen: {count}")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        msg.button(QMessageBox.Yes).setText("Ja")
        msg.button(QMessageBox.No).setText("Nein")
        return msg.exec() == QMessageBox.Yes

    def open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Terminplan-Datei auswählen", "", "Terminplan (*.xlsx *.csv);;Alle Dateien (*.*)")
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str, reset_session_state: bool = True) -> None:
        excel_config = self.config_loader.load_json("excel_import.json")["excel_import"]
        block_configs = excel_config["employee_blocks"]
        sheet_name = excel_config.get("sheet_name")

        rows = self.importer.load_rows(file_path, sheet_name=sheet_name)

        all_candidates = []
        for row_index in range(1, len(rows)):
            blocks = self.extractor.extract_blocks_from_row(rows[row_index], block_configs)
            filled = [b for b in blocks if self.extractor.is_block_meaningfully_filled(b)]
            candidates = self.builder.build_proposal_candidates(filled, self.classifier)
            all_candidates.extend(candidates)

        self.current_file_path = file_path
        self.groups = self.grouping.group_candidates(all_candidates)

        for group in self.groups:
            group.setdefault("manueller_status", "offen")
            group.setdefault("manuelle_notiz", "")
            group.setdefault("_last_changed_at", "")

        self._apply_saved_manual_data()

        if reset_session_state:
            self.last_action = None
            self.change_log.clear()
            self.log_view.clear()

        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        self.refresh_table()
        self.setWindowTitle(f"Rechnungsvorschlag Tool - {file_path}")

        if reset_session_state:
            self._log_action(f"Datei geladen | {file_path}")

    def activate_open_only_mode(self) -> None:
        self.manual_filter_combo.setCurrentText("Offen")

    def activate_show_all_mode(self) -> None:
        self.manual_filter_combo.setCurrentText("Alle")

    def set_manual_status_for_selected(self, status: str, advance: bool = False) -> None:
        row = self._current_selected_row()
        if row < 0:
            return

        selected_group = self.visible_groups[row]
        self.last_action = {
            "type": "single_status",
            "previous_states": [self._capture_group_state(selected_group)],
            "selected_keys": [self._build_group_key(selected_group)],
        }

        selected_group["manueller_status"] = status
        self._mark_changed([selected_group])
        self._save_manual_data()
        self._log_action(
            f"Einzelaktion | {selected_group.get('kunde_roh', '')} | {selected_group.get('projekt_roh', '')} -> {status}"
        )

        next_row = row
        if advance and row < len(self.visible_groups) - 1:
            next_row = row + 1

        self.refresh_table()

        if self.visible_groups:
            if next_row >= len(self.visible_groups):
                next_row = len(self.visible_groups) - 1
            self._set_selected_row(next_row)

    def set_manual_status_for_selected_rows(self, status: str) -> None:
        rows = self._selected_rows()
        if not rows:
            return

        groups = [self.visible_groups[row] for row in rows]

        if not self._confirm_bulk_action("Auswahl bestätigen", status, len(groups)):
            return

        previous_states = [self._capture_group_state(group) for group in groups]
        selected_keys = [self._build_group_key(group) for group in groups]

        self.last_action = {
            "type": "selection_status",
            "previous_states": previous_states,
            "selected_keys": selected_keys,
        }

        for group in groups:
            group["manueller_status"] = status

        self._mark_changed(groups)
        self._save_manual_data()
        self._log_action(f"Auswahl | {len(groups)} Gruppen -> {status}")
        self.refresh_table()
        self._select_groups_by_keys(selected_keys)

    def set_manual_status_for_visible(self, status: str) -> None:
        if not self.visible_groups:
            return

        if not self._confirm_bulk_action("Massenaktion bestätigen", status, len(self.visible_groups)):
            return

        previous_states = [self._capture_group_state(group) for group in self.visible_groups]
        selected_keys = [self._build_group_key(group) for group in self._selected_groups()]

        self.last_action = {
            "type": "bulk_status",
            "previous_states": previous_states,
            "selected_keys": selected_keys,
        }

        for group in self.visible_groups:
            group["manueller_status"] = status

        self._mark_changed(self.visible_groups)
        self._save_manual_data()
        self._log_action(f"Alle sichtbaren | {len(self.visible_groups)} Gruppen -> {status}")
        self.refresh_table()

        if selected_keys:
            self._select_groups_by_keys(selected_keys)

    def on_item_double_clicked(self, item) -> None:
        row = item.row()
        if row < 0 or row >= len(self.visible_groups):
            return

        group = self.visible_groups[row]
        current_status = group.get("manueller_status", "offen")

        if current_status == "offen":
            new_status = "freigegeben"
        elif current_status == "freigegeben":
            new_status = "offen"
        elif current_status == "pruefen":
            new_status = "freigegeben"
        elif current_status == "ignorieren":
            new_status = "offen"
        else:
            new_status = "freigegeben"

        msg = QMessageBox(self)
        msg.setWindowTitle("Status ändern")
        msg.setText("Soll der manuelle Status wirklich geändert werden?")
        msg.setInformativeText(f"Alt: {current_status}\nNeu: {new_status}")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        msg.button(QMessageBox.Yes).setText("Ja")
        msg.button(QMessageBox.No).setText("Nein")

        result = msg.exec()
        if result != QMessageBox.Yes:
            return

        self._set_selected_row(row)
        self.set_manual_status_for_selected(new_status, advance=True)

    def save_note_for_selected(self) -> None:
        row = self._current_selected_row()
        if row < 0:
            return

        selected_group = self.visible_groups[row]
        self.last_action = {
            "type": "note_change",
            "previous_states": [self._capture_group_state(selected_group)],
            "selected_keys": [self._build_group_key(selected_group)],
        }

        selected_group["manuelle_notiz"] = self.note_edit.toPlainText().strip()
        self._mark_changed([selected_group])
        self._save_manual_data()
        selected_key = self._build_group_key(selected_group)
        self._log_action(
            f"Notiz gespeichert | {selected_group.get('kunde_roh', '')} | {selected_group.get('projekt_roh', '')}"
        )
        self.refresh_table()
        self._select_groups_by_keys([selected_key])

    def save_project_file(self) -> None:
        if not self.current_file_path:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "Projektdatei speichern", "bearbeitungsstand.rvt.json", "Projektdateien (*.rvt.json);;JSON-Dateien (*.json)")
        if not file_path:
            return

        project_data = {"source_file": self.current_file_path, "groups": {}}
        for group in self.groups:
            key = self._build_group_key(group)
            project_data["groups"][key] = {
                "manueller_status": group.get("manueller_status", "offen"),
                "manuelle_notiz": group.get("manuelle_notiz", ""),
            }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(project_data, f, ensure_ascii=False, indent=2)

        self._log_action(f"Projekt gespeichert | {file_path}")

    def save_session_file(self) -> None:
        if not self.current_file_path:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Sitzung speichern",
            "bearbeitungssitzung.rvt.session.json",
            "Sitzungsdateien (*.rvt.session.json);;JSON-Dateien (*.json)",
        )
        if not file_path:
            return

        session_data = {
            "source_file": self.current_file_path,
            "groups": {},
            "change_log": self.change_log,
            "saved_at": datetime.now().isoformat(),
        }

        for group in self.groups:
            key = self._build_group_key(group)
            session_data["groups"][key] = {
                "manueller_status": group.get("manueller_status", "offen"),
                "manuelle_notiz": group.get("manuelle_notiz", ""),
                "_last_changed_at": group.get("_last_changed_at", ""),
            }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        self._log_action(f"Sitzung gespeichert | {file_path}")

    def load_session_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sitzung laden",
            "",
            "Sitzungsdateien (*.rvt.session.json);;JSON-Dateien (*.json);;Alle Dateien (*.*)",
        )
        if not file_path:
            return

        with open(file_path, "r", encoding="utf-8") as f:
            session_data = json.load(f)

        source_file = session_data.get("source_file", "")
        group_data = session_data.get("groups", {})
        if not source_file:
            return

        self.load_file(source_file, reset_session_state=False)

        for group in self.groups:
            key = self._build_group_key(group)
            if key in group_data:
                entry = group_data[key]
                if isinstance(entry, dict):
                    group["manueller_status"] = entry.get("manueller_status", "offen")
                    group["manuelle_notiz"] = entry.get("manuelle_notiz", "")
                    group["_last_changed_at"] = entry.get("_last_changed_at", "")

        loaded_change_log = session_data.get("change_log", [])
        if not isinstance(loaded_change_log, list):
            loaded_change_log = []

        self.change_log = [str(x) for x in loaded_change_log]
        self._save_manual_data()
        self.last_action = None
        self.refresh_table()
        self.log_view.setPlainText("\n".join(self.change_log))
        self._log_action(f"Sitzung geladen | {file_path}")

    def load_project_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Projektdatei laden", "", "Projektdateien (*.rvt.json);;JSON-Dateien (*.json);;Alle Dateien (*.*)")
        if not file_path:
            return

        with open(file_path, "r", encoding="utf-8") as f:
            project_data = json.load(f)

        source_file = project_data.get("source_file", "")
        group_data = project_data.get("groups", {})
        if not source_file:
            return

        self.load_file(source_file)

        for group in self.groups:
            key = self._build_group_key(group)
            if key in group_data:
                entry = group_data[key]
                if isinstance(entry, str):
                    group["manueller_status"] = entry
                    group["manuelle_notiz"] = ""
                elif isinstance(entry, dict):
                    group["manueller_status"] = entry.get("manueller_status", "offen")
                    group["manuelle_notiz"] = entry.get("manuelle_notiz", "")

        self._save_manual_data()
        self.last_action = None
        self.refresh_table()
        self._log_action(f"Projekt geladen | {file_path}")

    def export_visible_groups_to_csv(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "CSV-Export speichern", "rechnungsvorschlaege.csv", "CSV-Dateien (*.csv)")
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "ManuellerStatus", "ManuelleNotiz", "Status", "Automatikstatus", "Datum", "KW",
                "Kunde", "Projekt", "Adresse", "Ansprechpartner", "Auftrag", "Bemerkungen",
                "Mitarbeiter", "RE", "Geaendert", "Klassifikationsgruende",
            ])

            for group in self.visible_groups:
                writer.writerow([
                    group.get("manueller_status", "offen"),
                    group.get("manuelle_notiz", ""),
                    self._status_text(group),
                    group.get("gruppenstatus", ""),
                    self._format_date_for_display(group.get("datum", "")),
                    group.get("kw", ""),
                    group.get("kunde_roh", ""),
                    group.get("projekt_roh", ""),
                    group.get("adresse_roh", ""),
                    group.get("ansprechpartner_roh", ""),
                    group.get("auftrag_roh", ""),
                    group.get("bemerkungen_roh", ""),
                    ", ".join(group.get("mitarbeiter_liste", [])),
                    ", ".join(group.get("re_roh_liste", [])),
                    group.get("_last_changed_at", ""),
                    " | ".join(group.get("klassifikationsgruende", [])),
                ])

        self._log_action(f"CSV exportiert | {file_path}")

    def export_visible_groups_to_json(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "JSON-Export speichern", "rechnungsvorschlaege.json", "JSON-Dateien (*.json)")
        if not file_path:
            return

        export_data = []
        for group in self.visible_groups:
            export_data.append({
                "manueller_status": group.get("manueller_status", "offen"),
                "manuelle_notiz": group.get("manuelle_notiz", ""),
                "status": self._status_text(group),
                "gruppenstatus": group.get("gruppenstatus", ""),
                "datum": self._format_date_for_display(group.get("datum", "")),
                "kw": group.get("kw", ""),
                "kunde_roh": group.get("kunde_roh", ""),
                "projekt_roh": group.get("projekt_roh", ""),
                "adresse_roh": group.get("adresse_roh", ""),
                "ansprechpartner_roh": group.get("ansprechpartner_roh", ""),
                "auftrag_roh": group.get("auftrag_roh", ""),
                "bemerkungen_roh": group.get("bemerkungen_roh", ""),
                "mitarbeiter_liste": group.get("mitarbeiter_liste", []),
                "re_roh_liste": group.get("re_roh_liste", []),
                "geaendert": group.get("_last_changed_at", ""),
                "klassifikationsgruende": group.get("klassifikationsgruende", []),
                "eintraege": group.get("eintraege", []),
            })

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        self._log_action(f"JSON exportiert | {file_path}")

    def export_selected_groups_to_lexware_draft(self) -> None:
        selected_groups = self._selected_groups()
        if not selected_groups:
            QMessageBox.information(self, "Lexware Draft Export", "Bitte zuerst mindestens eine Gruppe auswählen.")
            return

        if self.lexware_export_service is None or not self.lexware_export_service.is_configured():
            QMessageBox.warning(
                self,
                "Lexware nicht konfiguriert",
                "Lexware-Zugangsdaten fehlen. Bitte .env prüfen: BASE_URL + ACCESS_TOKEN oder Refresh-Flow (CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/TOKEN_URL).",
            )
            return

        ok_count = 0
        fail_count = 0
        first_error = ""

        for group in selected_groups:
            result = self.lexware_export_service.export_group_as_draft(group)

            if result.get("success"):
                ok_count += 1
                response = result.get("response")
                export_id = ""
                if isinstance(response, dict):
                    export_id = str(
                        response.get("id")
                        or response.get("voucherNumber")
                        or response.get("resourceUri")
                        or ""
                    )
                group["lexware_export_status"] = "exportiert"
                group["lexware_export_id"] = export_id
            else:
                fail_count += 1
                group["lexware_export_status"] = "fehler"
                group["lexware_export_id"] = ""
                if not first_error:
                    status = result.get("status_code")
                    err = result.get("error") or "Unbekannter Fehler"
                    response = result.get("response")
                    first_error = f"Status: {status} | Fehler: {err}"
                    if response:
                        first_error += f" | Antwort: {response}"

        self._mark_changed(selected_groups)
        self.refresh_table()

        self._log_action(f"Lexware Draft Export | erfolgreich: {ok_count} | fehlgeschlagen: {fail_count}")

        if fail_count == 0:
            QMessageBox.information(
                self,
                "Lexware Draft Export",
                f"Export abgeschlossen. Erfolgreich: {ok_count}",
            )
            return

        QMessageBox.warning(
            self,
            "Lexware Draft Export mit Fehlern",
            f"Erfolgreich: {ok_count}\nFehlgeschlagen: {fail_count}\n\nErster Fehler:\n{first_error}",
        )

    def refresh_table(self) -> None:
        auto_filter_text = self.auto_filter_combo.currentText()
        manual_filter_text = self.manual_filter_combo.currentText()
        changed_filter_text = self.changed_filter_combo.currentText()
        search_text = self.search_input.text().strip().lower()

        if auto_filter_text == "Nur Einsätze":
            filtered_groups = [g for g in self.groups if g.get("gruppenstatus") == "einsatz"]
        elif auto_filter_text == "Nur Prüffälle":
            filtered_groups = [g for g in self.groups if g.get("gruppenstatus") == "prueffall"]
        else:
            filtered_groups = list(self.groups)

        if manual_filter_text == "Offen":
            filtered_groups = [g for g in filtered_groups if g.get("manueller_status", "offen") == "offen"]
        elif manual_filter_text == "Freigegeben":
            filtered_groups = [g for g in filtered_groups if g.get("manueller_status", "offen") == "freigegeben"]
        elif manual_filter_text == "Prüfen":
            filtered_groups = [g for g in filtered_groups if g.get("manueller_status", "offen") == "pruefen"]
        elif manual_filter_text == "Ignorieren":
            filtered_groups = [g for g in filtered_groups if g.get("manueller_status", "offen") == "ignorieren"]

        if changed_filter_text == "Nur geänderte":
            filtered_groups = [g for g in filtered_groups if g.get("_last_changed_at", "")]
        elif changed_filter_text == "Nur ungeänderte":
            filtered_groups = [g for g in filtered_groups if not g.get("_last_changed_at", "")]

        if search_text:
            visible_groups = [g for g in filtered_groups if search_text in self._build_search_text(g)]
        else:
            visible_groups = filtered_groups

        selected_keys = [self._build_group_key(group) for group in self._selected_groups()]
        current_row = self._current_selected_row()
        current_key = None
        if current_row >= 0 and current_row < len(self.visible_groups):
            current_key = self._build_group_key(self.visible_groups[current_row])

        self.visible_groups = self._sort_groups(visible_groups)

        self.table_widget.setRowCount(len(self.visible_groups))
        self.table_widget.clearContents()
        self.detail_view.clear()
        self.note_edit.clear()

        for row, group in enumerate(self.visible_groups):
            values = [
                self._status_symbol(group),
                self._format_date_for_display(group.get("datum", "")),
                group.get("kw", ""),
                group.get("kunde_roh", ""),
                group.get("projekt_roh", ""),
                ", ".join(group.get("mitarbeiter_liste", [])),
                self._status_text(group),
                group.get("gruppenstatus", ""),
                ", ".join(group.get("re_roh_liste", [])),
                self._clip_text(group.get("adresse_roh", ""), 60),
                group.get("_last_changed_at", ""),
                self._clip_text(group.get("manuelle_notiz", ""), 50),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

                if col == 0:
                    item.setTextAlignment(Qt.AlignCenter)

                self._apply_item_colors(item, group)
                self.table_widget.setItem(row, col, item)

        self._update_summary_bar()
        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)

        if selected_keys:
            self._select_groups_by_keys(selected_keys)
        elif current_key:
            self._select_groups_by_keys([current_key])
        elif self.visible_groups:
            self._set_selected_row(0)
        else:
            self.summary_selected_label.setText("Ausgewählt: 0")

    def _select_groups_by_keys(self, keys: list[str]) -> None:
        if not keys:
            self.summary_selected_label.setText("Ausgewählt: 0")
            return

        model = self.table_widget.selectionModel()
        if model:
            model.clearSelection()

        first_row = None

        for row, group in enumerate(self.visible_groups):
            if self._build_group_key(group) in keys:
                self.table_widget.selectRow(row)
                if first_row is None:
                    first_row = row

        if first_row is not None:
            self.table_widget.setCurrentCell(first_row, 0)

        self.summary_selected_label.setText(f"Ausgewählt: {len(self._selected_rows())}")

    def _sort_groups(self, groups: list[dict]) -> list[dict]:
        reverse = self.current_sort_order == Qt.DescendingOrder
        column = self.current_sort_column

        def sort_key(g: dict):
            if column == 0:
                return self._status_symbol(g)
            if column == 1:
                return (self._parse_date(g.get("datum", "")), g.get("kunde_roh", "").lower())
            if column == 2:
                return self._safe_int(g.get("kw", ""))
            if column == 3:
                return g.get("kunde_roh", "").lower()
            if column == 4:
                return g.get("projekt_roh", "").lower()
            if column == 5:
                return ", ".join(g.get("mitarbeiter_liste", [])).lower()
            if column == 6:
                order = {"Offen": 0, "Prüfen": 1, "Freigegeben": 2, "Ignorieren": 3, "Prüffall": 4}
                return order.get(self._status_text(g), 99)
            if column == 7:
                order = {"einsatz": 0, "prueffall": 1, "unbekannt": 2}
                return order.get(g.get("gruppenstatus", ""), 99)
            if column == 8:
                return ", ".join(g.get("re_roh_liste", [])).lower()
            if column == 9:
                return g.get("adresse_roh", "").lower()
            if column == 10:
                return g.get("_last_changed_at", "")
            if column == 11:
                return g.get("manuelle_notiz", "").lower()
            return ""

        return sorted(groups, key=sort_key, reverse=reverse)

    def _safe_int(self, value) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return 999999

    def _parse_date(self, value: str):
        text = str(value).strip()
        if not text:
            return datetime.max

        formats = ["%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"]
        for fmt in formats:
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                pass
        return datetime.max

    def _format_date_for_display(self, value: str) -> str:
        parsed = self._parse_date(value)
        if parsed == datetime.max:
            return str(value)
        return parsed.strftime("%d.%m.%Y")

    def _clip_text(self, value: str, length: int) -> str:
        text = str(value or "").replace("\n", " ").strip()
        if len(text) <= length:
            return text
        if length <= 1:
            return text[:length]
        return text[: length - 1] + "…"

    def _status_text(self, group: dict) -> str:
        manual = group.get("manueller_status", "offen")
        auto = group.get("gruppenstatus", "")
        if manual == "freigegeben":
            return "Freigegeben"
        if manual == "pruefen":
            return "Prüfen"
        if manual == "ignorieren":
            return "Ignorieren"
        if auto == "prueffall":
            return "Prüffall"
        return "Offen"

    def _build_detail_text(self, group: dict) -> str:
        detail_lines = [
            f"Manueller Status: {group.get('manueller_status', 'offen')}",
            f"Manuelle Notiz: {group.get('manuelle_notiz', '')}",
            f"Lexware Exportstatus: {group.get('lexware_export_status', '')}",
            f"Lexware Export-ID: {group.get('lexware_export_id', '')}",
            f"Status: {self._status_text(group)}",
            f"Automatischer Status: {group.get('gruppenstatus', '')}",
            f"Datum: {self._format_date_for_display(group.get('datum', ''))}",
            f"KW: {group.get('kw', '')}",
            f"Kunde: {group.get('kunde_roh', '')}",
            f"Projekt: {group.get('projekt_roh', '')}",
            f"Adresse: {group.get('adresse_roh', '')}",
            f"Ansprechpartner: {group.get('ansprechpartner_roh', '')}",
            f"Auftrag: {group.get('auftrag_roh', '')}",
            f"Bemerkungen: {group.get('bemerkungen_roh', '')}",
            f"Mitarbeiter: {', '.join(group.get('mitarbeiter_liste', []))}",
            f"RE: {', '.join(group.get('re_roh_liste', []))}",
            f"Geändert: {group.get('_last_changed_at', '')}",
            "",
            "Klassifikationsgründe:",
        ]

        for grund in group.get("klassifikationsgruende", []):
            detail_lines.append(f"- {grund}")

        detail_lines.append("")
        detail_lines.append("Einträge:")

        for entry in group.get("eintraege", []):
            detail_lines.append(
                f"- {entry.get('mitarbeiter', '')}: "
                f"{entry.get('klassifikation', '')} | "
                f"{entry.get('projekt_roh', '')} | "
                f"{entry.get('bemerkungen_roh', '')}"
            )

        return "\n".join(detail_lines)

    def _update_summary_bar(self) -> None:
        visible_count = len(self.visible_groups)
        selected_count = len(self._selected_rows())
        open_count = approved_count = review_count = ignored_count = auto_review_count = 0

        for group in self.visible_groups:
            manual = group.get("manueller_status", "offen")
            auto_status = group.get("gruppenstatus", "")
            if manual == "offen":
                open_count += 1
            elif manual == "freigegeben":
                approved_count += 1
            elif manual == "pruefen":
                review_count += 1
            elif manual == "ignorieren":
                ignored_count += 1
            if auto_status == "prueffall":
                auto_review_count += 1

        self.summary_visible_label.setText(f"Sichtbar: {visible_count}")
        self.summary_selected_label.setText(f"Ausgewählt: {selected_count}")
        self.summary_open_label.setText(f"Offen: {open_count}")
        self.summary_approved_label.setText(f"Freigegeben: {approved_count}")
        self.summary_review_label.setText(f"Prüfen: {review_count}")
        self.summary_ignored_label.setText(f"Ignorieren: {ignored_count}")
        self.summary_auto_review_label.setText(f"Prüffälle: {auto_review_count}")

    def _apply_item_colors(self, item: QTableWidgetItem, group: dict) -> None:
        status = group.get("gruppenstatus", "")
        manual = group.get("manueller_status", "offen")
        if manual == "freigegeben":
            item.setBackground(QColor("#d9f2d9"))
        elif manual == "pruefen":
            item.setBackground(QColor("#fff3cd"))
        elif manual == "ignorieren":
            item.setBackground(QColor("#e2e3e5"))
            item.setForeground(QColor("#666666"))
        elif status == "prueffall":
            item.setBackground(QColor("#f8d7da"))

    def _build_search_text(self, group: dict) -> str:
        values = [
            self._status_symbol(group),
            self._format_date_for_display(group.get("datum", "")),
            group.get("kw", ""),
            group.get("kunde_roh", ""),
            group.get("projekt_roh", ""),
            group.get("adresse_roh", ""),
            group.get("ansprechpartner_roh", ""),
            group.get("auftrag_roh", ""),
            group.get("bemerkungen_roh", ""),
            " ".join(group.get("mitarbeiter_liste", [])),
            " ".join(group.get("re_roh_liste", [])),
            group.get("gruppenstatus", ""),
            self._status_text(group),
            group.get("manueller_status", "offen"),
            group.get("manuelle_notiz", ""),
            group.get("_last_changed_at", ""),
        ]
        return " | ".join(str(v) for v in values).lower()

    def _build_group_key(self, group: dict) -> str:
        return "||".join([
            str(group.get("datum", "")).strip(),
            group.get("kunde_roh", "").strip().lower(),
            group.get("projekt_roh", "").strip().lower(),
        ])

    def _get_manual_data_file_path(self) -> Path | None:
        if not self.current_file_path:
            return None
        return Path(self.current_file_path + ".status.json")

    def _save_manual_data(self) -> None:
        data_file = self._get_manual_data_file_path()
        if data_file is None:
            return

        manual_data = {}
        for group in self.groups:
            key = self._build_group_key(group)
            manual_status = group.get("manueller_status", "offen")
            manual_note = group.get("manuelle_notiz", "")
            if manual_status != "offen" or manual_note:
                manual_data[key] = {
                    "manueller_status": manual_status,
                    "manuelle_notiz": manual_note,
                }

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(manual_data, f, ensure_ascii=False, indent=2)

    def _apply_saved_manual_data(self) -> None:
        data_file = self._get_manual_data_file_path()
        if data_file is None or not data_file.exists():
            return

        with open(data_file, "r", encoding="utf-8") as f:
            manual_data = json.load(f)

        for group in self.groups:
            key = self._build_group_key(group)
            if key in manual_data:
                entry = manual_data[key]
                if isinstance(entry, str):
                    group["manueller_status"] = entry
                    group["manuelle_notiz"] = ""
                elif isinstance(entry, dict):
                    group["manueller_status"] = entry.get("manueller_status", "offen")
                    group["manuelle_notiz"] = entry.get("manuelle_notiz", "")

    def on_table_selection_changed(self) -> None:
        selected_groups = self._selected_groups()
        self.summary_selected_label.setText(f"Ausgewählt: {len(selected_groups)}")

        if not selected_groups:
            self.detail_view.clear()
            self.note_edit.clear()
            return

        if len(selected_groups) == 1:
            group = selected_groups[0]
            self.detail_view.setPlainText(self._build_detail_text(group))
            self.note_edit.setPlainText(group.get("manuelle_notiz", ""))
            return

        lines = [
            f"Mehrfachauswahl: {len(selected_groups)} Gruppen",
            "",
            "Ausgewählte Gruppen:",
        ]

        for group in selected_groups:
            lines.append(
                f"- {self._format_date_for_display(group.get('datum', ''))} | "
                f"{group.get('kunde_roh', '')} | "
                f"{group.get('projekt_roh', '')} | "
                f"{self._status_text(group)}"
            )

        self.detail_view.setPlainText("\n".join(lines))
        self.note_edit.clear()
