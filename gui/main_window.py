import csv
import json
import math
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib import parse, request, error

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QDoubleSpinBox,
    QSpinBox,
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
        "Kundenmatch",
        "Projekt",
        "Mitarbeiter",
        "Status",
        "Automatikstatus",
        "Validierung",
        "RE",
        "Adresse",
        "Geändert",
        "Notiz",
    ]

    def __init__(
        self,
        config_loader,
        importer,
        contacts_importer,
        extractor,
        classifier,
        builder,
        grouping,
        articles_importer=None,
        invoice_mapper=None,
        lexware_export_service=None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Rechnungsvorschlag Tool")
        self.resize(2080, 1200)

        self.config_loader = config_loader
        self.importer = importer
        self.contacts_importer = contacts_importer
        self.articles_importer = articles_importer
        self.extractor = extractor
        self.classifier = classifier
        self.builder = builder
        self.grouping = grouping
        self.invoice_mapper = invoice_mapper
        self.lexware_export_service = lexware_export_service

        self.current_file_path: str = ""
        self.groups: list[dict] = []
        self.visible_groups: list[dict] = []
        self.last_action: dict | None = None
        self.change_log: list[str] = []
        self.current_articles: list[dict] = []
        self.customer_article_templates: dict[str, list[dict]] = {}
        
        self.mandants: list[dict] = self._load_mandants()
        self.active_mandant_id: str = self.mandants[0]["id"] if self.mandants else ""

        self.current_sort_column = 1
        self.current_sort_order = Qt.AscendingOrder
        self._geo_cache: dict[str, tuple[float, float]] = {}
        self._lexware_customers_cache: list[dict] = []
        self._lexware_templates_cache: dict[str, list[dict]] = {}
        self._lexware_service_defaults: dict[str, str] | None = None

        self.open_button = QPushButton("Datei öffnen")
        self.load_project_button = QPushButton("Projekt laden")
        self.save_project_button = QPushButton("Projekt speichern")
        self.load_session_button = QPushButton("Sitzung laden")
        self.save_session_button = QPushButton("Sitzung speichern")
        self.export_csv_button = QPushButton("CSV exportieren")
        self.export_json_button = QPushButton("JSON exportieren")
        self.lexware_export_button = QPushButton("Lexware Draft exportieren")
        self.offer_editor_button = QPushButton("Angebot/Rechnung bearbeiten")
        
        self.mandant_combo = QComboBox()
        self.mandant_combo.setMinimumWidth(250)
        for mandant in self.mandants:
            self.mandant_combo.addItem(mandant.get("display_name", ""), mandant.get("id", ""))
        if self.active_mandant_id:
            index = self.mandant_combo.findData(self.active_mandant_id)
            if index >= 0:
                self.mandant_combo.setCurrentIndex(index)
        self.mandant_combo.currentIndexChanged.connect(self._on_mandant_changed_combo)

        self.article_combo = QComboBox()
        self.article_combo.setMinimumWidth(320)
        self.article_combo.currentIndexChanged.connect(self._on_article_changed_combo)

        self.article_add_button = QPushButton("Artikel hinzufügen")
        self.article_remove_button = QPushButton("Artikel entfernen")
        self.article_clear_button = QPushButton("Artikel leeren")
        self.article_template_combo = QComboBox()
        self.article_template_combo.setMinimumWidth(320)
        self.article_template_save_button = QPushButton("Artikelsatz speichern")
        self.article_template_apply_button = QPushButton("Vorlage anwenden")
        self.article_quick_select_input = QLineEdit()
        self.article_quick_select_input.setPlaceholderText("Schnellreferenz: z.B. 1,4,7")
        self.article_quick_select_apply_button = QPushButton("Referenz anwenden")
        self.article_add_button.clicked.connect(self.add_selected_article_to_group)
        self.article_remove_button.clicked.connect(self.remove_selected_article_from_group)
        self.article_clear_button.clicked.connect(self.clear_selected_articles_for_group)
        self.article_template_save_button.clicked.connect(self.save_article_template_for_group)
        self.article_template_apply_button.clicked.connect(self.apply_selected_article_template_to_group)
        self.article_quick_select_apply_button.clicked.connect(self.apply_quick_article_reference_for_group)
        self.article_quick_select_input.returnPressed.connect(self.apply_quick_article_reference_for_group)

        self.article_list_widget = QListWidget()
        self.article_list_widget.setMinimumHeight(140)
        self.article_list_widget.itemSelectionChanged.connect(self._on_article_list_selection_changed)

        self.article_summary_label = QLabel("Artikel: kein Artikel gewählt")
        self.article_summary_label.setWordWrap(True)

        self.article_price_spin = QDoubleSpinBox()
        self.article_price_spin.setRange(0.0, 1000000.0)
        self.article_price_spin.setDecimals(2)
        self.article_price_spin.setSingleStep(10.0)
        self.article_price_spin.setPrefix("EUR ")
        self.article_price_spin.valueChanged.connect(self._on_article_price_changed)

        self.draft_title_edit = QLineEdit()
        self.draft_title_edit.setPlaceholderText("Belegtitel für Lexware-Draft")
        self.draft_title_edit.setText("Angebot")
        self.draft_title_edit.textChanged.connect(self._update_draft_preview)

        self.draft_introduction_edit = QPlainTextEdit()
        self.draft_introduction_edit.setPlaceholderText("Einleitungstext für das Angebot ...")
        self.draft_introduction_edit.setPlainText("Automatisch erzeugter Entwurf für das Angebot.")
        self.draft_introduction_edit.setMinimumHeight(70)
        self.draft_introduction_edit.textChanged.connect(self._update_draft_preview)

        self.draft_remark_edit = QPlainTextEdit()
        self.draft_remark_edit.setPlaceholderText("Nachbemerkung / Fußtext ...")
        self.draft_remark_edit.setPlainText("Erzeugt durch Rechnungsautomatismus")
        self.draft_remark_edit.setMinimumHeight(60)
        self.draft_remark_edit.textChanged.connect(self._update_draft_preview)

        self.draft_payment_term_days_spin = QSpinBox()
        self.draft_payment_term_days_spin.setRange(0, 365)
        self.draft_payment_term_days_spin.setValue(getattr(self.lexware_export_service, "default_payment_term_days", 14))
        self.draft_payment_term_days_spin.setSuffix(" Tage netto")
        self.draft_payment_term_days_spin.valueChanged.connect(self._update_draft_preview)

        self.travel_mode_combo = QComboBox()
        self.travel_mode_combo.addItem("Fahrtkosten als extra Artikel", "extra_article")
        self.travel_mode_combo.addItem("Fahrtkosten im 1. Artikel enthalten", "included_in_first_article")

        self.travel_hours_spin = QDoubleSpinBox()
        self.travel_hours_spin.setRange(0.0, 1000.0)
        self.travel_hours_spin.setDecimals(2)
        self.travel_hours_spin.setSingleStep(0.25)
        self.travel_hours_spin.setSuffix(" h")

        self.travel_km_spin = QDoubleSpinBox()
        self.travel_km_spin.setRange(0.0, 100000.0)
        self.travel_km_spin.setDecimals(0)
        self.travel_km_spin.setSingleStep(10.0)
        self.travel_km_spin.setSuffix(" km")

        self.travel_hour_rate_spin = QDoubleSpinBox()
        self.travel_hour_rate_spin.setRange(0.0, 10000.0)
        self.travel_hour_rate_spin.setDecimals(2)
        self.travel_hour_rate_spin.setValue(150.0)
        self.travel_hour_rate_spin.setSingleStep(10.0)
        self.travel_hour_rate_spin.setPrefix("EUR ")

        self.travel_km_rate_spin = QDoubleSpinBox()
        self.travel_km_rate_spin.setRange(0.0, 100.0)
        self.travel_km_rate_spin.setDecimals(2)
        self.travel_km_rate_spin.setValue(0.7)
        self.travel_km_rate_spin.setSingleStep(0.1)
        self.travel_km_rate_spin.setPrefix("EUR ")

        self.travel_recalc_button = QPushButton("KM automatisch berechnen")

        self.travel_mode_combo.currentIndexChanged.connect(self._on_travel_settings_changed)
        self.travel_hours_spin.valueChanged.connect(self._on_travel_settings_changed)
        self.travel_km_spin.valueChanged.connect(self._on_travel_settings_changed)
        self.travel_hour_rate_spin.valueChanged.connect(self._on_travel_settings_changed)
        self.travel_km_rate_spin.valueChanged.connect(self._on_travel_settings_changed)
        self.travel_recalc_button.clicked.connect(self._calculate_travel_km_for_selected)

        self.draft_preview_view = QPlainTextEdit()
        self.draft_preview_view.setReadOnly(True)
        self.draft_preview_view.setPlaceholderText("Vorschau des Lexware-Drafts ...")
        self.draft_preview_view.setMinimumHeight(150)
        self.draft_preview_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.draft_preview_view.setStyleSheet(
            "QPlainTextEdit {"
            " background: #fbf7ef;"
            " border: 1px solid #d7cab2;"
            " border-radius: 8px;"
            " padding: 8px;"
            " font-family: 'DejaVu Sans Mono', monospace;"
            " }"
        )

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
        self.table_widget.setStyleSheet(
            "QTableWidget {"
            " font-size: 12px;"
            " gridline-color: #d9dfe7;"
            " }"
            "QHeaderView::section {"
            " font-size: 12px;"
            " font-weight: 600;"
            " background: #eef2f7;"
            " border: 1px solid #d9dfe7;"
            " padding: 6px 4px;"
            " }"
        )

        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        for i in range(1, 13):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
        header.setSectionResizeMode(13, QHeaderView.Stretch)
        header.setMinimumSectionSize(48)
        header.setDefaultSectionSize(120)
        self.table_widget.verticalHeader().setDefaultSectionSize(30)

        header.resizeSection(0, 36)
        header.resizeSection(1, 110)
        header.resizeSection(2, 70)
        header.resizeSection(3, 220)
        header.resizeSection(4, 140)
        header.resizeSection(5, 220)
        header.resizeSection(6, 180)
        header.resizeSection(7, 120)
        header.resizeSection(8, 130)
        header.resizeSection(9, 120)
        header.resizeSection(10, 100)
        header.resizeSection(11, 240)
        header.resizeSection(12, 90)

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
        top_bar.addWidget(self.offer_editor_button)
        top_bar.addWidget(self.lexware_export_button)
        top_bar.addWidget(QLabel("Mandant:"))
        top_bar.addWidget(self.mandant_combo)
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

        draft_title = QLabel("Angebot / Draft")
        draft_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        draft_bar = QVBoxLayout()
        draft_bar.setContentsMargins(10, 10, 10, 10)
        draft_bar.setSpacing(8)
        draft_bar.addWidget(draft_title)
        compact_hint = QLabel(
            "Vorschau direkt hier. Erweiterte Bearbeitung (Belegtitel, Texte, Zahlungsziel, Lexware-Filter, Fahrtkosten)"
            " im Fenster: Angebot/Rechnung bearbeiten"
        )
        compact_hint.setWordWrap(True)
        compact_hint.setStyleSheet("color: #5f6368;")
        draft_bar.addWidget(compact_hint)
        draft_bar.addWidget(self.draft_preview_view)

        article_title = QLabel("Artikel")
        article_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        article_bar = QVBoxLayout()
        article_bar.setContentsMargins(10, 10, 10, 10)
        article_bar.setSpacing(8)
        article_bar.addWidget(article_title)
        article_bar.addWidget(self.article_combo)
        article_button_bar = QHBoxLayout()
        article_button_bar.setSpacing(6)
        article_button_bar.addWidget(self.article_add_button)
        article_button_bar.addWidget(self.article_remove_button)
        article_button_bar.addWidget(self.article_clear_button)
        article_bar.addLayout(article_button_bar)
        article_template_bar = QHBoxLayout()
        article_template_bar.setSpacing(6)
        article_template_bar.addWidget(self.article_template_combo)
        article_template_bar.addWidget(self.article_template_save_button)
        article_template_bar.addWidget(self.article_template_apply_button)
        article_bar.addLayout(article_template_bar)
        article_quick_select_bar = QHBoxLayout()
        article_quick_select_bar.setSpacing(6)
        article_quick_select_bar.addWidget(self.article_quick_select_input)
        article_quick_select_bar.addWidget(self.article_quick_select_apply_button)
        article_bar.addLayout(article_quick_select_bar)
        article_bar.addWidget(self.article_list_widget)
        article_bar.addWidget(self.article_summary_label)
        article_price_row = QHBoxLayout()
        article_price_row.addWidget(QLabel("Preis (ausgewählter Artikel)"))
        article_price_row.addWidget(self.article_price_spin)
        article_bar.addLayout(article_price_row)
        article_bar.addWidget(QLabel("Manuelle Notiz"))
        article_bar.addWidget(self.note_edit)
        article_bar.addWidget(self.save_note_button)

        log_title = QLabel("Änderungsverlauf")
        log_title.setStyleSheet("font-weight: 700; font-size: 13px;")
        log_bar = QVBoxLayout()
        log_bar.setContentsMargins(10, 10, 10, 10)
        log_bar.setSpacing(8)
        log_bar.addWidget(log_title)
        log_bar.addWidget(self.log_view)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addLayout(top_bar)
        left_layout.addLayout(filter_bar)
        left_layout.addLayout(action_bar)
        left_layout.addLayout(selection_action_bar)
        left_layout.addLayout(bulk_action_bar)
        left_layout.addLayout(summary_bar)
        left_layout.addWidget(self.table_widget, 4)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(10)

        detail_section = QFrame()
        detail_section.setObjectName("rightSection")
        detail_layout = QVBoxLayout(detail_section)
        detail_layout.setContentsMargins(10, 10, 10, 10)
        detail_layout.addWidget(self.detail_view)

        draft_section = QFrame()
        draft_section.setObjectName("rightSection")
        draft_section.setLayout(draft_bar)

        article_section = QFrame()
        article_section.setObjectName("rightSection")
        article_section.setLayout(article_bar)

        log_section = QFrame()
        log_section.setObjectName("rightSection")
        log_section.setLayout(log_bar)

        lower_editor_splitter = QSplitter(Qt.Horizontal)
        lower_editor_splitter.addWidget(draft_section)
        lower_editor_splitter.addWidget(article_section)
        lower_editor_splitter.setChildrenCollapsible(False)
        lower_editor_splitter.setStretchFactor(0, 1)
        lower_editor_splitter.setStretchFactor(1, 1)
        lower_editor_splitter.setSizes([620, 620])

        left_layout.addWidget(lower_editor_splitter, 2)

        right_widget.setStyleSheet(
            "QFrame#rightSection {"
            " border: 1px solid #d9dfe7;"
            " border-radius: 8px;"
            " background: #f8fafc;"
            " }"
        )

        right_layout.addWidget(detail_section, 4)
        right_layout.addWidget(log_section, 2)

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
        self.offer_editor_button.clicked.connect(self.open_offer_editor_dialog)
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

        self._refresh_articles_for_mandant(self.active_mandant_id)
        self._apply_draft_defaults_for_mandant(self.active_mandant_id)
        self._refresh_article_template_combo_for_group(None)

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
        table_widget = getattr(self, "table_widget", None)
        if table_widget is None:
            return []

        model = table_widget.selectionModel()
        if model is None:
            return []
        rows = sorted({index.row() for index in model.selectedRows()})
        return [row for row in rows if 0 <= row < len(self.visible_groups)]

    def _selected_groups(self) -> list[dict]:
        return [self.visible_groups[row] for row in self._selected_rows()]

    def _load_mandants(self) -> list[dict]:
        """Lädt alle Mandanten aus der Konfiguration."""
        try:
            config = self.config_loader.load_json("mandants.json")
            return config.get("mandants", [])
        except Exception:
            return []

    def _get_mandant_by_id(self, mandant_id: str) -> dict | None:
        """Gibt den Mandanten mit der gegebenen ID zurück."""
        for mandant in self.mandants:
            if mandant.get("id", "") == mandant_id:
                return mandant
        return None

    def _load_contacts_for_mandant(self, mandant_id: str) -> list[dict]:
        """Lädt Kontakte nur für den angegebenen Mandanten."""
        if self.contacts_importer is None:
            return []

        mandant = self._get_mandant_by_id(mandant_id)
        if not mandant:
            return []

        contacts_path = mandant.get("contacts_csv", "")
        if not contacts_path:
            return []

        try:
            return self.contacts_importer.load(contacts_path)
        except Exception:
            return []

    def _load_articles_for_mandant(self, mandant_id: str) -> list[dict]:
        """Lädt Artikel nur für den angegebenen Mandanten."""
        articles_importer = getattr(self, "articles_importer", None)
        if articles_importer is None:
            return []

        mandant = self._get_mandant_by_id(mandant_id)
        if not mandant:
            return []

        articles_path = mandant.get("products_csv", "")
        if not articles_path:
            return []

        try:
            rows = articles_importer.load(articles_path)
            if hasattr(self, "change_log") and hasattr(self, "log_view"):
                self._log_action(f"Artikel geladen | Mandant={mandant_id} | Datei={articles_path} | Anzahl={len(rows)}")
            return rows
        except Exception as exc:
            if hasattr(self, "change_log") and hasattr(self, "log_view"):
                self._log_action(f"Artikel laden fehlgeschlagen | Mandant={mandant_id} | Datei={articles_path} | Fehler={exc}")
            return []

    def _mandant_full_address(self, mandant_id: str) -> str:
        mandant = self._get_mandant_by_id(mandant_id)
        if not mandant:
            return ""

        parts = [
            str(mandant.get("strasse", "") or "").strip(),
            " ".join(
                p for p in [
                    str(mandant.get("plz", "") or "").strip(),
                    str(mandant.get("ort", "") or "").strip(),
                ]
                if p
            ).strip(),
        ]
        return ", ".join(part for part in parts if part)

    def _normalize_address_for_geocoding(self, address: str) -> str:
        text = str(address or "").strip()
        if not text:
            return ""

        # Entfernt Zusatzteile wie Google-Code/Koordinaten, damit Nominatim den Ort besser findet.
        text = re.sub(r"Google-?Code\s*:[^,;\n]*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"Koordinaten\s*:[^,;\n]*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" ,;")
        return text

    def _extract_coordinates_from_text(self, address: str) -> tuple[float, float] | None:
        text = str(address or "").strip()
        if not text:
            return None

        decimal_match = re.search(
            r"(-?\d{1,2}(?:[\.,]\d+)?)\s*[,;/ ]\s*(-?\d{1,3}(?:[\.,]\d+)?)",
            text,
        )
        if decimal_match:
            try:
                first = float(decimal_match.group(1).replace(",", "."))
                second = float(decimal_match.group(2).replace(",", "."))
                if abs(first) <= 90 and abs(second) <= 180:
                    return (first, second)
            except Exception:
                pass

        dms_matches = re.findall(
            r"(\d{1,3})\s*[°º]\s*(\d{1,2})\s*['′]\s*(\d{1,2}(?:[\.,]\d+)?)\s*[\"”″]?\s*([NSEW])",
            text,
            flags=re.IGNORECASE,
        )
        if len(dms_matches) >= 2:
            coords = []
            for deg, minutes, seconds, direction in dms_matches[:2]:
                try:
                    value = float(deg) + (float(minutes) / 60.0) + (float(str(seconds).replace(",", ".")) / 3600.0)
                    if direction.upper() in {"S", "W"}:
                        value = -value
                    coords.append((direction.upper(), value))
                except Exception:
                    continue

            if len(coords) == 2:
                lat = None
                lon = None
                for direction, value in coords:
                    if direction in {"N", "S"}:
                        lat = value
                    if direction in {"E", "W"}:
                        lon = value
                if lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180:
                    return (lat, lon)

        return None

    def _geocode_address(self, address: str) -> tuple[float, float] | None:
        key = str(address or "").strip()
        if not key:
            return None
        if key in self._geo_cache:
            return self._geo_cache[key]

        extracted = self._extract_coordinates_from_text(key)
        if extracted is not None:
            self._geo_cache[key] = extracted
            return extracted

        query_text = self._normalize_address_for_geocoding(key)
        if not query_text:
            return None
        if query_text in self._geo_cache:
            return self._geo_cache[query_text]

        url = "https://nominatim.openstreetmap.org/search?" + parse.urlencode({
            "q": query_text,
            "format": "json",
            "limit": 1,
        })
        req = request.Request(
            url,
            headers={"User-Agent": "Rechnungsautomatismus/1.0 (travel-km-calc)"},
            method="GET",
        )

        try:
            with request.urlopen(req, timeout=4) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not isinstance(payload, list) or not payload:
                return None

            item = payload[0]
            lat = float(item.get("lat"))
            lon = float(item.get("lon"))
            self._geo_cache[key] = (lat, lon)
            self._geo_cache[query_text] = (lat, lon)
            return (lat, lon)
        except (error.URLError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _route_distance_km(self, start: tuple[float, float], end: tuple[float, float]) -> float | None:
        metrics = self._route_metrics(start, end)
        if metrics is None:
            return None
        return metrics[0]

    def _route_metrics(self, start: tuple[float, float], end: tuple[float, float]) -> tuple[float, float] | None:
        lat1, lon1 = start
        lat2, lon2 = end
        base_url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        url = base_url + "?" + parse.urlencode({"overview": "false", "alternatives": "false", "steps": "false"})
        req = request.Request(
            url,
            headers={"User-Agent": "Rechnungsautomatismus/1.0 (travel-route-calc)"},
            method="GET",
        )

        try:
            with request.urlopen(req, timeout=6) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))

            routes = payload.get("routes", []) if isinstance(payload, dict) else []
            if not routes:
                return None

            meters = float(routes[0].get("distance", 0.0) or 0.0)
            if meters <= 0:
                return None

            duration_seconds = float(routes[0].get("duration", 0.0) or 0.0)
            distance_raw_km = max(meters, 0.0) / 1000.0
            distance_km = self._round_up_km_to_tens(distance_raw_km)

            duration_raw_hours = max(duration_seconds, 0.0) / 3600.0
            duration_hours = self._round_up_to_quarter_hour(duration_raw_hours)

            return distance_km, duration_hours

        except (error.URLError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _round_up_to_quarter_hour(self, hours: float) -> float:
        value = float(hours or 0.0)
        if value <= 0:
            return 0.0
        return round(math.ceil(value * 4.0) / 4.0, 2)

    def _round_up_km_to_tens(self, distance_km: float) -> float:
        value = float(distance_km or 0.0)
        if value <= 0:
            return 0.0
        return float(int(math.ceil(value / 10.0) * 10))

    def _calculate_travel_km_for_selected(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        if not self._calculate_travel_km_for_group(group, show_messages=True):
            return

        self._sync_travel_editor_from_group(group)
        self._mark_changed([group])
        self._save_manual_data()
        self.detail_view.setPlainText(self._build_detail_text(group))
        self._update_draft_preview()

    def _calculate_travel_km_for_group(self, group: dict, show_messages: bool = False) -> bool:
        origin = self._mandant_full_address(self.active_mandant_id)
        destination = str(group.get("adresse_roh", "") or "").strip()
        if not origin or not destination:
            if show_messages:
                QMessageBox.information(self, "KM-Berechnung", "Start- oder Zieladresse fehlt.")
            return False

        start_coords = self._geocode_address(origin)
        end_coords = self._geocode_address(destination)
        if start_coords is None or end_coords is None:
            if show_messages:
                QMessageBox.warning(
                    self,
                    "KM-Berechnung",
                    "Adressen konnten nicht geocodiert werden. "
                    "Bitte Adresse prüfen oder Koordinaten im Feld hinterlegen (z.B. 50.123, 11.456).",
                )
            return False

        metrics = self._route_metrics(start_coords, end_coords)
        if metrics is None:
            if show_messages:
                QMessageBox.warning(self, "KM-Berechnung", "Auto-Fahrstrecke konnte nicht berechnet werden.")
            return False

        distance_km, duration_hours = metrics
        distance_km = self._round_up_km_to_tens(distance_km * 2.0)
        duration_hours = self._round_up_to_quarter_hour(duration_hours * 2.0)

        if duration_hours <= 0:
            if show_messages:
                QMessageBox.warning(
                    self,
                    "KM-Berechnung",
                    "Route konnte ohne verlässliche Fahrzeit nicht übernommen werden. "
                    "Bitte Fahrtzeit manuell setzen oder Route erneut berechnen.",
                )
            return False

        if distance_km <= 0:
            return False

        group["travel_km"] = distance_km
        group["travel_hours"] = duration_hours
        group["travel_route_origin"] = origin
        group["travel_route_destination"] = destination
        group["travel_values_source"] = "auto_single"

        if show_messages:
            QMessageBox.information(
                self,
                "KM-Berechnung",
                "Route berechnet.\n"
                f"Start: {origin}\n"
                f"Ziel: {destination}\n"
                f"Strecke (Hin- und Rückfahrt): {int(round(distance_km))} km\n"
                f"Fahrzeit: {duration_hours:.2f} h",
            )
        return True

    def _tour_customer_key(self, group: dict) -> str:
        customer_number = str(group.get("customer_match_number", "") or "").strip().lower()
        if customer_number:
            return f"nr:{customer_number}"

        customer_name = str(group.get("customer_match_name", "") or group.get("kunde_roh", "")).strip().lower()
        return f"name:{customer_name}"

    def _tour_day_key(self, group: dict) -> str:
        parsed = self._parse_date(str(group.get("datum", "") or ""))
        if parsed == datetime.max:
            return str(group.get("datum", "") or "").strip()
        return parsed.date().isoformat()

    def _tour_employee_key(self, group: dict) -> str:
        employees = group.get("mitarbeiter_liste", [])
        if isinstance(employees, list) and employees:
            normalized = sorted(
                str(employee or "").strip().lower()
                for employee in employees
                if str(employee or "").strip()
            )
            if normalized:
                return "|".join(normalized)

        return str(group.get("mitarbeiter", "") or "").strip().lower()

    def _split_groups_into_consecutive_day_clusters(self, groups: list[dict], order_map: dict[int, int]) -> list[list[dict]]:
        if not groups:
            return []

        ordered_groups = sorted(
            groups,
            key=lambda group: (
                self._parse_date(str(group.get("datum", "") or "")),
                order_map.get(id(group), 999999),
                str(group.get("projekt_roh", "") or "").strip().lower(),
            ),
        )

        clusters: list[list[dict]] = []
        current_cluster: list[dict] = []
        last_date = None

        for group in ordered_groups:
            parsed = self._parse_date(str(group.get("datum", "") or ""))
            current_date = None if parsed == datetime.max else parsed.date()

            if not current_cluster:
                current_cluster = [group]
                last_date = current_date
                continue

            if current_date is None or last_date is None:
                same_cluster = str(group.get("datum", "") or "").strip() == str(current_cluster[-1].get("datum", "") or "").strip()
            else:
                same_cluster = current_date <= (last_date + timedelta(days=1))

            if same_cluster:
                current_cluster.append(group)
            else:
                clusters.append(current_cluster)
                current_cluster = [group]

            last_date = current_date

        if current_cluster:
            clusters.append(current_cluster)
        return clusters

    def _apply_roundtrip_distribution_for_groups(self, groups: list[dict]) -> int:
        """Verteilt Fahrten bei gleichem Kundentag auf mehrere Projektgruppen.

        Regel: Firma -> 1. Adresse -> ... -> letzte Adresse -> Firma.
        Die Hinfahrt liegt damit auf der ersten Rechnung, die Rueckfahrt auf der letzten.
        """
        if not groups:
            return 0

        groups_by_tour_key: dict[tuple[str, str, str], list[dict]] = {}
        order_map = {id(group): idx for idx, group in enumerate(groups)}

        for group in groups:
            mandant_id = str(group.get("mandant_id", self.active_mandant_id) or self.active_mandant_id)
            tour_key = (mandant_id, self._tour_customer_key(group), self._tour_employee_key(group))
            groups_by_tour_key.setdefault(tour_key, []).append(group)

        applied_tours = 0
        for (mandant_id, _customer_key, _employee_key), raw_cluster in groups_by_tour_key.items():
            for cluster in self._split_groups_into_consecutive_day_clusters(raw_cluster, order_map):
                if len(cluster) < 2:
                    continue

                distinct_projects = {
                    str(group.get("projekt_roh", "") or "").strip().lower()
                    for group in cluster
                    if str(group.get("projekt_roh", "") or "").strip()
                }
                if len(distinct_projects) < 2:
                    continue

                if any(
                    str(group.get("travel_values_source", "") or "").strip().lower() == "manual"
                    and (
                        float(group.get("travel_km", 0.0) or 0.0) > 0.0
                        or float(group.get("travel_hours", 0.0) or 0.0) > 0.0
                    )
                    for group in cluster
                ):
                    continue

                ordered_cluster = sorted(
                    cluster,
                    key=lambda group: (
                        self._parse_date(str(group.get("datum", "") or "")),
                        order_map.get(id(group), 999999),
                        str(group.get("projekt_roh", "") or "").strip().lower(),
                    ),
                )

                if self._apply_roundtrip_distribution_for_ordered_groups(ordered_cluster, mandant_id):
                    applied_tours += 1

        return applied_tours

    def _apply_roundtrip_distribution_for_ordered_groups(self, ordered_groups: list[dict], mandant_id: str) -> bool:
        if not ordered_groups:
            return False

        origin = self._mandant_full_address(mandant_id)
        if not origin:
            return False

        origin_coords = self._geocode_address(origin)
        if origin_coords is None:
            return False

        destinations: list[tuple[dict, str, tuple[float, float]]] = []
        for group in ordered_groups:
            destination = str(group.get("adresse_roh", "") or "").strip()
            if not destination:
                return False
            destination_coords = self._geocode_address(destination)
            if destination_coords is None:
                return False
            destinations.append((group, destination, destination_coords))

        last_index = len(destinations) - 1

        leg_infos: list[dict] = []
        # Outbound: Firma -> erstes Projekt
        first_destination = destinations[0]
        outbound_metrics = self._route_metrics(origin_coords, first_destination[2])
        if outbound_metrics is None:
            return False
        outbound_km, outbound_hours = outbound_metrics
        if outbound_km <= 0 or outbound_hours <= 0:
            return False
        leg_infos.append({
            "type": "outbound",
            "from": origin,
            "to": first_destination[1],
            "km": float(outbound_km),
            "hours": float(outbound_hours),
        })

        # Zwischenfahrten: Projekt i -> Projekt i+1
        for idx in range(len(destinations) - 1):
            from_destination = destinations[idx]
            to_destination = destinations[idx + 1]
            forward_metrics = self._route_metrics(from_destination[2], to_destination[2])
            if forward_metrics is None:
                return False
            forward_km, forward_hours = forward_metrics
            if forward_km <= 0 or forward_hours <= 0:
                return False
            leg_infos.append({
                "type": "forward",
                "from": from_destination[1],
                "to": to_destination[1],
                "km": float(forward_km),
                "hours": float(forward_hours),
            })

        # Return: letztes Projekt -> Firma
        last_destination = destinations[last_index]
        return_metrics = self._route_metrics(last_destination[2], origin_coords)
        if return_metrics is None:
            return False
        return_km, return_hours = return_metrics
        if return_km <= 0 or return_hours <= 0:
            return False
        leg_infos.append({
            "type": "return",
            "from": last_destination[1],
            "to": f"{origin} (inkl. Rueckfahrt zur Firma)",
            "km": float(return_km),
            "hours": float(return_hours),
        })

        # Verteilregel: Zwischenfahrten auf Tag 1 oder Tag 2 buchen.
        forward_rule = str(
            ordered_groups[0].get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
            or self._default_travel_forward_assignment_rule()
        ).strip().lower()
        if forward_rule not in {"tag_1", "tag_2"}:
            forward_rule = self._default_travel_forward_assignment_rule()

        per_invoice_segments: list[list[dict]] = [[] for _ in destinations]

        # Outbound immer auf erste Rechnung.
        per_invoice_segments[0].append(leg_infos[0])

        # Zwischenfahrten je nach Regel verteilen.
        forward_legs = [leg for leg in leg_infos if leg.get("type") == "forward"]
        if forward_rule == "tag_1":
            for idx, leg in enumerate(forward_legs):
                per_invoice_segments[idx].append(leg)
        else:
            for idx, leg in enumerate(forward_legs, start=1):
                per_invoice_segments[idx].append(leg)

        # Rueckfahrt immer auf letzte Rechnung.
        per_invoice_segments[last_index].append(leg_infos[-1])

        for idx, (group, destination, _destination_coords) in enumerate(destinations):
            self._ensure_travel_fields_for_group(group)
            segments = per_invoice_segments[idx]
            if not segments:
                return False

            total_km = sum(float(segment.get("km", 0.0) or 0.0) for segment in segments)
            total_hours = sum(float(segment.get("hours", 0.0) or 0.0) for segment in segments)
            if total_km <= 0 or total_hours <= 0:
                return False

            group["travel_km"] = float(total_km)
            group["travel_hours"] = round(float(total_hours), 2)
            group["travel_route_origin"] = str(segments[0].get("from", "") or origin)
            group["travel_route_destination"] = str(segments[-1].get("to", "") or destination)
            group["travel_values_source"] = "auto_roundtrip"
            group["travel_route_segments"] = [
                f"{str(seg.get('from', '') or '-')} -> {str(seg.get('to', '') or '-')}"
                for seg in segments
            ]

            if idx == 0:
                group["travel_segment_role"] = "first_invoice_outbound"
            elif idx == last_index:
                group["travel_segment_role"] = "last_invoice_with_return"
            else:
                group["travel_segment_role"] = "middle_invoice"

        return True

    def _travel_segment_preview_text(self, group: dict) -> str:
        origin = str(group.get("travel_route_origin", "") or "").strip()
        destination = str(group.get("travel_route_destination", "") or "").strip()
        if not origin and not destination:
            return ""

        route_segments = group.get("travel_route_segments", [])
        route_text = ""
        if isinstance(route_segments, list) and route_segments:
            cleaned_segments = [str(segment).strip() for segment in route_segments if str(segment).strip()]
            if cleaned_segments:
                route_text = " | ".join(cleaned_segments)
        if not route_text:
            route_text = f"{origin or '-'} -> {destination or '-'}"

        km = float(group.get("travel_km", 0.0) or 0.0)
        hours = float(group.get("travel_hours", 0.0) or 0.0)
        role = str(group.get("travel_segment_role", "") or "").strip().lower()
        role_prefix = ""
        if role == "first_invoice_outbound":
            role_prefix = "Erste Rechnung (Anfahrt): "
        elif role == "last_invoice_with_return":
            role_prefix = "Letzte Rechnung (inkl. Rueckfahrt): "
        elif role == "middle_invoice":
            role_prefix = "Zwischenrechnung: "
        return (
            f"{role_prefix}Route: {route_text}"
            f" | {int(round(km))} km | {hours:.2f} h"
        )

    def _default_travel_forward_assignment_rule(self) -> str:
        return "tag_2"

    def _default_multi_day_allowance_assignment_rule(self) -> str:
        return "tag_1"

    def _article_key(self, article: dict) -> str:
        article_number = str((article or {}).get("Artikelnummer", "") or (article or {}).get("Artikelnummer ", "")).strip()
        if article_number:
            return article_number

        name = str((article or {}).get("Bezeichnung", "") or "").strip().lower()
        unit = str((article or {}).get("Einheit", "") or "").strip().lower()
        tax = str((article or {}).get("Steuerart", "") or "").strip().lower()
        price = str((article or {}).get("VK (Netto)", "") or "").strip().lower()
        return "|".join([name, unit, tax, price])

    def _article_display_text(self, article: dict, reference_index: int | None = None) -> str:
        article_number = str((article or {}).get("Artikelnummer", "") or "").strip()
        name = str((article or {}).get("Bezeichnung", "") or "").strip() or "Unbenannter Artikel"
        unit = str((article or {}).get("Einheit", "") or "").strip()
        tax = str((article or {}).get("Steuerart", "") or "").strip()
        price = str((article or {}).get("VK (Netto)", "") or "").strip()

        parts = [name]
        if article_number:
            parts.insert(0, article_number)
        suffix_parts = [part for part in [unit, tax, price] if part]
        if suffix_parts:
            parts.append(f"({', '.join(suffix_parts)})")
        base_text = " - ".join(parts)
        if reference_index is not None and reference_index > 0:
            return f"{reference_index}. {base_text}"
        return base_text

    def _parse_price_value(self, value, fallback: float = 0.0) -> float:
        text = str(value or "").strip()
        if not text:
            return fallback

        normalized = text.replace(" ", "").replace("EUR", "").replace("eur", "")
        normalized = normalized.replace(".", "").replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", normalized)
        if not match:
            return fallback
        try:
            return float(match.group(0))
        except Exception:
            return fallback

    def _format_price_value(self, value: float) -> str:
        return f"{float(value):.2f}".replace(".", ",")

    def _sync_article_price_editor_from_group(self, group: dict | None) -> None:
        widget = getattr(self, "article_price_spin", None)
        if widget is None:
            return

        widget.blockSignals(True)
        if group is None:
            widget.setValue(0.0)
            widget.setEnabled(False)
            widget.blockSignals(False)
            return

        articles = self._selected_articles_for_group(group)
        if not articles:
            widget.setValue(0.0)
            widget.setEnabled(False)
            widget.blockSignals(False)
            return

        article_list_widget = getattr(self, "article_list_widget", None)
        selected_index = article_list_widget.currentRow() if article_list_widget is not None else 0
        if selected_index < 0 or selected_index >= len(articles):
            selected_index = 0
        price = self._parse_price_value(articles[selected_index].get("VK (Netto)", ""), 0.0)
        widget.setValue(price)
        widget.setEnabled(True)
        widget.blockSignals(False)

    def _on_article_price_changed(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        articles = self._selected_articles_for_group(group)
        if not articles:
            return

        article_list_widget = getattr(self, "article_list_widget", None)
        selected_index = article_list_widget.currentRow() if article_list_widget is not None else 0
        if selected_index < 0 or selected_index >= len(articles):
            selected_index = 0

        updated_article = dict(articles[selected_index])
        updated_article["VK (Netto)"] = self._format_price_value(self.article_price_spin.value())
        articles[selected_index] = updated_article
        self._set_selected_articles_for_group(group, articles)

        self._mark_changed([group])
        self._save_manual_data()
        self._refresh_article_editor_for_group(group)
        self._refresh_group_view_after_article_change(group)
        self._update_draft_preview()

    def _selected_articles_for_group(self, group: dict) -> list[dict]:
        articles = group.get("selected_articles", [])
        if isinstance(articles, list) and articles:
            return [dict(article) for article in articles if isinstance(article, dict)]

        single_article = group.get("selected_article", {})
        if isinstance(single_article, dict) and single_article:
            return [dict(single_article)]

        return []

    def _current_customer_template_key(self, group: dict | None) -> str:
        if not isinstance(group, dict):
            return ""

        customer_number = str(group.get("customer_match_number", "") or "").strip().lower()
        if customer_number:
            return f"nr:{customer_number}"

        customer_name = str(group.get("customer_match_name", "") or group.get("kunde_roh", "") or "").strip().lower()
        customer_name = re.sub(r"\s+", " ", customer_name)
        if customer_name:
            return f"name:{customer_name}"
        return ""

    def _customer_templates_for_mandant(self, mandant_id: str) -> list[dict]:
        if not isinstance(getattr(self, "customer_article_templates", None), dict):
            self.customer_article_templates = {}

        templates = self.customer_article_templates.get(mandant_id)
        if isinstance(templates, list):
            return templates
        self.customer_article_templates[mandant_id] = []
        return self.customer_article_templates[mandant_id]

    def _label_for_template_key(self, group: dict | None) -> str:
        if not isinstance(group, dict):
            return "Unbekannter Kunde"

        customer_number = str(group.get("customer_match_number", "") or "").strip()
        customer_name = str(group.get("customer_match_name", "") or group.get("kunde_roh", "") or "").strip() or "Unbekannter Kunde"
        if customer_number:
            return f"{customer_name} (Nr. {customer_number})"
        return customer_name

    def _refresh_article_template_combo_for_group(self, group: dict | None) -> None:
        combo = getattr(self, "article_template_combo", None)
        apply_button = getattr(self, "article_template_apply_button", None)
        save_button = getattr(self, "article_template_save_button", None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        if group is None:
            combo.addItem("Keine Vorlage (Gruppe wählen)", -1)
            combo.blockSignals(False)
            if apply_button is not None:
                apply_button.setEnabled(False)
            if save_button is not None:
                save_button.setEnabled(False)
            return

        customer_key = self._current_customer_template_key(group)
        templates = self._customer_templates_for_mandant(self.active_mandant_id)
        matching_templates = [
            tpl for tpl in templates
            if str((tpl or {}).get("customer_key", "") or "").strip() == customer_key
        ]

        if not matching_templates:
            combo.addItem("Keine Artikelsatz-Vorlage für diesen Kunden", -1)
        else:
            for idx, template in enumerate(matching_templates):
                template_name = str((template or {}).get("name", "") or "").strip() or f"Vorlage {idx + 1}"
                articles = (template or {}).get("articles", [])
                count = len(articles) if isinstance(articles, list) else 0
                combo.addItem(f"{template_name} ({count} Artikel)", idx)

        combo.blockSignals(False)
        if apply_button is not None:
            apply_button.setEnabled(bool(matching_templates))
        if save_button is not None:
            save_button.setEnabled(True)

    def _resolve_articles_from_reference(self, reference_text: str) -> tuple[list[dict], list[str]]:
        text = str(reference_text or "").strip()
        if not text:
            return [], []

        tokens = [token.strip() for token in re.split(r"[,;\s]+", text) if token.strip()]
        if not tokens:
            return [], []

        resolved: list[dict] = []
        invalid: list[str] = []
        seen_indexes: set[int] = set()

        for token in tokens:
            if not token.isdigit():
                invalid.append(token)
                continue

            number = int(token)
            if number <= 0:
                invalid.append(token)
                continue

            index = number - 1
            if index >= len(self.current_articles):
                invalid.append(token)
                continue

            if index in seen_indexes:
                continue

            seen_indexes.add(index)
            resolved.append(dict(self.current_articles[index]))

        return resolved, invalid

    def save_article_template_for_group(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        articles = self._selected_articles_for_group(group)
        if not articles:
            QMessageBox.information(self, "Artikelsatz", "Für diese Gruppe sind keine Artikel ausgewählt.")
            return

        customer_key = self._current_customer_template_key(group)
        if not customer_key:
            QMessageBox.warning(self, "Artikelsatz", "Kunde konnte nicht eindeutig bestimmt werden.")
            return

        suggested_name = f"{str(group.get('projekt_roh', '') or '').strip() or 'Standard'}"
        template_name, ok = QInputDialog.getText(self, "Artikelsatz speichern", "Vorlagenname", text=suggested_name)
        if not ok:
            return

        template_name = str(template_name or "").strip()
        if not template_name:
            QMessageBox.warning(self, "Artikelsatz", "Bitte einen Vorlagennamen eingeben.")
            return

        templates = self._customer_templates_for_mandant(self.active_mandant_id)
        customer_label = self._label_for_template_key(group)

        existing = None
        for template in templates:
            if (
                str(template.get("customer_key", "") or "").strip() == customer_key
                and str(template.get("name", "") or "").strip().lower() == template_name.lower()
            ):
                existing = template
                break

        if existing is not None:
            existing["articles"] = [dict(article) for article in articles if isinstance(article, dict)]
            existing["customer_label"] = customer_label
            self._log_action(f"Artikelsatz aktualisiert | {customer_label} | {template_name}")
        else:
            templates.append({
                "name": template_name,
                "customer_key": customer_key,
                "customer_label": customer_label,
                "articles": [dict(article) for article in articles if isinstance(article, dict)],
            })
            self._log_action(f"Artikelsatz gespeichert | {customer_label} | {template_name}")

        self._save_manual_data()
        self._refresh_article_template_combo_for_group(group)

    def apply_selected_article_template_to_group(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        combo = getattr(self, "article_template_combo", None)
        if combo is None:
            return

        selected_data = combo.currentData()
        try:
            selected_index = int(selected_data)
        except Exception:
            selected_index = -1
        if selected_index < 0:
            return

        customer_key = self._current_customer_template_key(group)
        templates = self._customer_templates_for_mandant(self.active_mandant_id)
        matching_templates = [
            tpl for tpl in templates
            if str((tpl or {}).get("customer_key", "") or "").strip() == customer_key
        ]

        if not (0 <= selected_index < len(matching_templates)):
            return

        template = matching_templates[selected_index]
        articles = template.get("articles", [])
        if not isinstance(articles, list) or not articles:
            return

        self._set_selected_articles_for_group(group, [dict(article) for article in articles if isinstance(article, dict)])
        self._mark_changed([group])
        self._save_manual_data()
        self._refresh_article_editor_for_group(group)
        self._refresh_group_view_after_article_change(group)
        self._log_action(
            f"Artikelsatz angewendet | {self._label_for_template_key(group)} | {str(template.get('name', '') or '').strip()}"
        )

    def apply_quick_article_reference_for_group(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        input_widget = getattr(self, "article_quick_select_input", None)
        if input_widget is None:
            return

        reference_text = str(input_widget.text() or "").strip()
        if not reference_text:
            QMessageBox.information(self, "Schnellreferenz", "Bitte Referenz eingeben (z.B. 1,4,7).")
            return

        resolved_articles, invalid_tokens = self._resolve_articles_from_reference(reference_text)
        if not resolved_articles:
            max_index = len(self.current_articles)
            QMessageBox.warning(
                self,
                "Schnellreferenz",
                f"Keine gültigen Referenzen gefunden. Verfügbar: 1 bis {max_index}.",
            )
            return

        self._set_selected_articles_for_group(group, resolved_articles)
        self._mark_changed([group])
        self._save_manual_data()
        self._refresh_article_editor_for_group(group)
        self._refresh_group_view_after_article_change(group)

        if invalid_tokens:
            QMessageBox.information(
                self,
                "Schnellreferenz",
                "Gültige Referenzen wurden übernommen. "
                f"Ignoriert: {', '.join(invalid_tokens)}",
            )

        self._log_action(
            f"Schnellreferenz angewendet | {self._label_for_template_key(group)} | {reference_text}"
        )

    def _set_selected_articles_for_group(self, group: dict, articles: list[dict]) -> None:
        normalized_articles = [dict(article) for article in articles if isinstance(article, dict)]
        group["selected_articles"] = normalized_articles

        if normalized_articles:
            self._apply_article_to_group(group, normalized_articles[0])
        else:
            group["selected_article"] = {}
            group["selected_article_key"] = ""
            group["selected_article_name"] = ""
            group["selected_article_unit"] = ""
            group["selected_article_price_net"] = ""
            group["selected_article_tax_rate"] = ""

    def _append_article_to_group(self, group: dict, article: dict) -> None:
        articles = self._selected_articles_for_group(group)
        articles.append(dict(article))
        self._set_selected_articles_for_group(group, articles)

    def _remove_article_from_group(self, group: dict, index: int) -> None:
        articles = self._selected_articles_for_group(group)
        if 0 <= index < len(articles):
            del articles[index]
            self._set_selected_articles_for_group(group, articles)

    def _clear_articles_for_group(self, group: dict) -> None:
        self._set_selected_articles_for_group(group, [])

    def _resolve_article_by_key(self, article_key: str) -> dict | None:
        key = str(article_key or "").strip()
        if not key:
            return None
        for article in self.current_articles:
            if self._article_key(article) == key:
                return article
        return None

    def _selected_article_for_group(self, group: dict) -> dict | None:
        articles = self._selected_articles_for_group(group)
        if articles:
            article = articles[0]
            key = self._article_key(article)
            resolved = self._resolve_article_by_key(key)
            return resolved or article

        article = group.get("selected_article")
        if isinstance(article, dict) and article:
            key = self._article_key(article)
            resolved = self._resolve_article_by_key(key)
            return resolved or article

        key = str(group.get("selected_article_key", "") or "").strip()
        return self._resolve_article_by_key(key)

    def _apply_article_to_group(self, group: dict, article: dict | None) -> None:
        if not article:
            group["selected_article"] = {}
            group["selected_article_key"] = ""
            group["selected_article_name"] = ""
            group["selected_article_unit"] = ""
            group["selected_article_price_net"] = ""
            group["selected_article_tax_rate"] = ""
            return

        group["selected_article"] = dict(article)
        group["selected_article_key"] = self._article_key(article)
        group["selected_article_name"] = str(article.get("Bezeichnung", "") or "").strip()
        group["selected_article_unit"] = str(article.get("Einheit", "") or "").strip()
        group["selected_article_price_net"] = str(article.get("VK (Netto)", "") or "").strip()
        group["selected_article_tax_rate"] = str(article.get("Steuerart", "") or "").strip()

    def _refresh_articles_for_mandant(self, mandant_id: str) -> None:
        self.current_articles = self._load_articles_for_mandant(mandant_id)

        article_combo = getattr(self, "article_combo", None)
        article_summary_label = getattr(self, "article_summary_label", None)
        article_list_widget = getattr(self, "article_list_widget", None)
        if article_combo is None or article_summary_label is None:
            return

        current_selected_key = ""
        current_group = self._selected_groups()[0] if len(self._selected_groups()) == 1 else None
        if current_group:
            current_selected_key = str(current_group.get("selected_article_key", "") or "").strip()

        article_combo.blockSignals(True)
        article_combo.clear()
        article_combo.addItem("Kein Artikel gewählt", "")

        for index, article in enumerate(self.current_articles, start=1):
            article_combo.addItem(self._article_display_text(article, reference_index=index), self._article_key(article))

        index = article_combo.findData(current_selected_key)
        if index >= 0:
            article_combo.setCurrentIndex(index)
        else:
            article_combo.setCurrentIndex(0)
        article_combo.blockSignals(False)

        self._update_article_summary(current_group)
        if not self.current_articles:
            mandant = self._get_mandant_by_id(mandant_id) or {}
            products_csv = str(mandant.get("products_csv", "") or "")
            article_summary_label.setText(f"Artikel: keine Daten geladen (Datei: {products_csv})")
        if article_list_widget is not None and current_group is not None:
            self._sync_article_list_widget(current_group)

    def _update_article_summary(self, group: dict | None) -> None:
        if not group:
            self.article_summary_label.setText("Artikel: kein Artikel gewählt")
            return

        articles = self._selected_articles_for_group(group)
        if not articles:
            article = self._selected_article_for_group(group)
            if not article:
                self.article_summary_label.setText("Artikel: kein Artikel gewählt")
                return

            parts = [str(article.get("Bezeichnung", "") or "").strip()]
            if article.get("Artikelnummer", ""):
                parts.insert(0, str(article.get("Artikelnummer", "") or "").strip())
            self.article_summary_label.setText(f"Artikel: {' - '.join(part for part in parts if part)}")
            return

        first_article = articles[0]
        parts = [str(first_article.get("Bezeichnung", "") or "").strip()]
        if first_article.get("Artikelnummer", ""):
            parts.insert(0, str(first_article.get("Artikelnummer", "") or "").strip())
        summary = f"Artikel: {len(articles)} ausgewählt"
        if any(parts):
            summary += f" | {' - '.join(part for part in parts if part)}"
        self.article_summary_label.setText(summary)

    def _sync_article_list_widget(self, group: dict | None) -> None:
        article_list_widget = getattr(self, "article_list_widget", None)
        if article_list_widget is None:
            return

        article_list_widget.blockSignals(True)
        article_list_widget.clear()

        articles = self._selected_articles_for_group(group or {}) if group else []
        for article in articles:
            item = QListWidgetItem(self._article_display_text(article))
            item.setData(Qt.UserRole, self._article_key(article))
            article_list_widget.addItem(item)

        article_list_widget.blockSignals(False)

    def _current_group_for_article_editing(self) -> dict | None:
        row = self._current_selected_row()
        if row < 0:
            return None
        return self.visible_groups[row]

    def _on_article_changed_combo(self) -> None:
        row = self._current_selected_row()
        if row < 0:
            self._update_article_summary(None)
            return

        group = self.visible_groups[row]
        article_key = str(self.article_combo.currentData() or "").strip()
        article = self._resolve_article_by_key(article_key)
        if article:
            self.article_summary_label.setText(self._article_display_text(article))
        else:
            self._update_article_summary(group)

    def add_selected_article_to_group(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        article_key = str(self.article_combo.currentData() or "").strip()
        article = self._resolve_article_by_key(article_key)
        if not article:
            return

        self._append_article_to_group(group, article)
        self._mark_changed([group])
        self._save_manual_data()
        self._refresh_article_editor_for_group(group)
        self._refresh_group_view_after_article_change(group)

    def remove_selected_article_from_group(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        article_list_widget = getattr(self, "article_list_widget", None)
        if article_list_widget is None:
            return

        row = article_list_widget.currentRow()
        if row < 0:
            return

        self._remove_article_from_group(group, row)
        self._mark_changed([group])
        self._save_manual_data()
        self._refresh_article_editor_for_group(group)
        self._refresh_group_view_after_article_change(group)

    def clear_selected_articles_for_group(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        self._clear_articles_for_group(group)
        self._mark_changed([group])
        self._save_manual_data()
        self._refresh_article_editor_for_group(group)
        self._refresh_group_view_after_article_change(group)

    def _on_article_list_selection_changed(self) -> None:
        group = self._current_group_for_article_editing()
        if group is not None:
            self._update_article_summary(group)
        self._sync_article_price_editor_from_group(group)

    def _refresh_article_editor_for_group(self, group: dict | None) -> None:
        quick_input = getattr(self, "article_quick_select_input", None)
        quick_button = getattr(self, "article_quick_select_apply_button", None)
        if group is None:
            self.article_combo.blockSignals(True)
            self.article_combo.setCurrentIndex(0)
            self.article_combo.blockSignals(False)
            article_list_widget = getattr(self, "article_list_widget", None)
            if article_list_widget is not None:
                article_list_widget.blockSignals(True)
                article_list_widget.clear()
                article_list_widget.blockSignals(False)
            self._update_article_summary(None)
            self._sync_article_price_editor_from_group(None)
            self._refresh_article_template_combo_for_group(None)
            if quick_input is not None:
                quick_input.clear()
                quick_input.setEnabled(False)
            if quick_button is not None:
                quick_button.setEnabled(False)
            return

        self._sync_article_list_widget(group)
        articles = self._selected_articles_for_group(group)
        if articles:
            article_key = self._article_key(articles[0])
            index = self.article_combo.findData(article_key)
            self.article_combo.blockSignals(True)
            self.article_combo.setCurrentIndex(index if index >= 0 else 0)
            self.article_combo.blockSignals(False)
        else:
            self.article_combo.blockSignals(True)
            self.article_combo.setCurrentIndex(0)
            self.article_combo.blockSignals(False)
        self._update_article_summary(group)
        self._sync_article_price_editor_from_group(group)
        self._refresh_article_template_combo_for_group(group)
        if quick_input is not None:
            quick_input.setEnabled(True)
            max_index = max(len(self.current_articles), 1)
            quick_input.setPlaceholderText(f"Schnellreferenz: 1-{max_index} (z.B. 1,4,7)")
        if quick_button is not None:
            quick_button.setEnabled(bool(self.current_articles))

    def _refresh_group_view_after_article_change(self, group: dict) -> None:
        self._refresh_group_invoice_proposal(group)
        self._update_article_summary(group)
        self.detail_view.setPlainText(self._build_detail_text(group))
        self.refresh_table()
        self._select_groups_by_keys([self._build_group_key(group)])

    def _get_lexware_company_id_for_mandant(self, mandant_id: str) -> str:
        mandant = self._get_mandant_by_id(mandant_id)
        env_value = self._mandant_specific_lexware_env_value(mandant_id, "LEXWARE_COMPANY_ID")
        if env_value:
            return env_value

        if mandant:
            mandant_value = str(mandant.get("lexware_company_id", "") or "").strip()
            if mandant_value:
                return mandant_value

        self._ensure_lexware_service_defaults()
        if isinstance(self._lexware_service_defaults, dict):
            return str(self._lexware_service_defaults.get("company_id", "") or "").strip()
        return ""

    def _mandant_specific_lexware_env_value(self, mandant_id: str, base_key: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9]+", "_", str(mandant_id or "").strip()).strip("_").upper()
        if not normalized:
            return ""
        return str(os.getenv(f"{base_key}__{normalized}", "") or "").strip()

    def _ensure_lexware_service_defaults(self) -> None:
        if getattr(self, "_lexware_service_defaults", None) is not None:
            return

        service = getattr(self, "lexware_export_service", None)
        if service is None:
            self._lexware_service_defaults = {}
            return

        keys = [
            "base_url",
            "access_token",
            "client_id",
            "client_secret",
            "refresh_token",
            "token_url",
            "company_id",
            "draft_endpoint",
            "templates_endpoint",
            "customers_endpoint",
        ]
        self._lexware_service_defaults = {
            key: str(getattr(service, key, "") or "").strip()
            for key in keys
        }

    def _configure_lexware_service_for_mandant(self, mandant_id: str) -> None:
        service = getattr(self, "lexware_export_service", None)
        if service is None:
            return

        self._ensure_lexware_service_defaults()
        defaults = self._lexware_service_defaults or {}
        mandant = self._get_mandant_by_id(mandant_id) or {}

        mappings = {
            "base_url": "LEXWARE_BASE_URL",
            "access_token": "LEXWARE_ACCESS_TOKEN",
            "client_id": "LEXWARE_CLIENT_ID",
            "client_secret": "LEXWARE_CLIENT_SECRET",
            "refresh_token": "LEXWARE_REFRESH_TOKEN",
            "token_url": "LEXWARE_TOKEN_URL",
            "company_id": "LEXWARE_COMPANY_ID",
            "draft_endpoint": "LEXWARE_DRAFT_ENDPOINT",
            "templates_endpoint": "LEXWARE_TEMPLATES_ENDPOINT",
            "customers_endpoint": "LEXWARE_CUSTOMERS_ENDPOINT",
        }

        for attr_name, env_key in mappings.items():
            env_override = self._mandant_specific_lexware_env_value(mandant_id, env_key)
            cfg_override = str(mandant.get(f"lexware_{attr_name}", "") or "").strip()
            fallback = str(defaults.get(attr_name, "") or "").strip()
            effective = env_override or cfg_override or fallback
            setattr(service, attr_name, effective)

        token_url = str(getattr(service, "token_url", "") or "").strip()
        base_url = str(getattr(service, "base_url", "") or "").strip()
        if not token_url and base_url:
            service.token_url = f"{base_url.rstrip('/')}/oauth/token"

    def _lexware_context_for_mandant(self, mandant_id: str) -> dict:
        self._configure_lexware_service_for_mandant(mandant_id)
        service = getattr(self, "lexware_export_service", None)
        mandant = self._get_mandant_by_id(mandant_id) or {}

        return {
            "mandant_id": str(mandant_id or "").strip(),
            "mandant_name": str(mandant.get("display_name", "") or mandant_id or "").strip(),
            "base_url": str(getattr(service, "base_url", "") or "").strip(),
            "draft_endpoint": str(getattr(service, "draft_endpoint", "") or "").strip(),
            "company_id": self._get_lexware_company_id_for_mandant(mandant_id),
        }

    def _lexware_context_lines_for_groups(self, groups: list[dict]) -> list[str]:
        mandant_ids: list[str] = []
        for group in groups:
            mandant_id = str(group.get("mandant_id", self.active_mandant_id) or self.active_mandant_id)
            if mandant_id and mandant_id not in mandant_ids:
                mandant_ids.append(mandant_id)

        lines: list[str] = []
        for mandant_id in mandant_ids:
            context = self._lexware_context_for_mandant(mandant_id)
            base_url = context.get("base_url") or "-"
            endpoint = context.get("draft_endpoint") or "-"
            company_id = context.get("company_id") or "-"
            lines.append(
                f"- {context.get('mandant_name', mandant_id)} | Base URL: {base_url} | Endpoint: {endpoint} | Company-ID: {company_id}"
            )
        return lines

    def _apply_customer_matching_for_mandant(self, mandant_id: str) -> None:
        """Wendet Customer-Matching auf alle Gruppen für den aktiven Mandanten an."""
        contacts = self._load_contacts_for_mandant(mandant_id)

        for group in self.groups:
            group["mandant_id"] = mandant_id
            group["customer_match_state"] = "nicht_zugeordnet"
            group["customer_match_name"] = ""
            group["customer_match_number"] = ""
            group["customer_match_street"] = ""
            group["customer_match_zip"] = ""
            group["customer_match_city"] = ""
            group["customer_match_country"] = "DE"
            group["invoice_validation_errors"] = 0
            group["invoice_validation_warnings"] = 0
            group["invoice_validation_infos"] = 0
            group["invoice_validation_messages"] = []
            group["invoice_validation_state"] = "Unbekannt"
            group["invoice_export_ready"] = False
            group["invoice_positions_count"] = 0
            group["invoice_positions_preview"] = []

        if self.invoice_mapper is None:
            return

        for group in self.groups:
            proposal = self.invoice_mapper.map_group(group, contacts=contacts)
            self._apply_proposal_to_group(group, proposal)

    def _refresh_group_invoice_proposal(self, group: dict) -> None:
        if self.invoice_mapper is None:
            return

        mandant_id = str(group.get("mandant_id", self.active_mandant_id) or self.active_mandant_id)
        group["mandant_id"] = mandant_id
        contacts = self._load_contacts_for_mandant(mandant_id)
        proposal = self.invoice_mapper.map_group(group, contacts=contacts)
        self._apply_proposal_to_group(group, proposal)

    def _apply_proposal_to_group(self, group: dict, proposal) -> None:
        match = proposal.customer_match
        group["customer_match_state"] = str(match.state or "nicht_zugeordnet")
        group["customer_match_name"] = str(match.customer_name or "")
        group["customer_match_number"] = str(match.customer_number or "")

        street = getattr(match, "address_street", "")
        zip_code = getattr(match, "address_zip", "")
        city = getattr(match, "address_city", "")
        country = getattr(match, "address_country", "DE")
        group["customer_match_street"] = street.strip() if isinstance(street, str) else ""
        group["customer_match_zip"] = zip_code.strip() if isinstance(zip_code, str) else ""
        group["customer_match_city"] = city.strip() if isinstance(city, str) else ""
        group["customer_match_country"] = country.strip() if isinstance(country, str) and country.strip() else "DE"

        raw_messages = getattr(proposal, "validation_messages", [])
        messages = raw_messages if isinstance(raw_messages, list) else []
        errors = sum(1 for msg in messages if str(getattr(msg, "level", "")).lower() == "error")
        warnings = sum(1 for msg in messages if str(getattr(msg, "level", "")).lower() == "warning")
        infos = sum(1 for msg in messages if str(getattr(msg, "level", "")).lower() == "info")

        group["invoice_validation_errors"] = errors
        group["invoice_validation_warnings"] = warnings
        group["invoice_validation_infos"] = infos
        group["invoice_validation_messages"] = [
            f"{str(getattr(msg, 'level', '')).upper()}: {str(getattr(msg, 'message', '')).strip()}".strip()
            for msg in messages
        ]
        group["invoice_export_ready"] = bool(getattr(proposal, "is_export_ready", False))

        if errors > 0:
            state = f"Blockiert ({errors})"
        elif warnings > 0:
            state = f"Warnung ({warnings})"
        elif infos > 0:
            state = f"Info ({infos})"
        else:
            state = "OK"
        group["invoice_validation_state"] = state

        raw_positions = getattr(proposal, "positions", [])
        positions = raw_positions if isinstance(raw_positions, list) else []
        group["invoice_positions_count"] = len(positions)
        preview_lines = []
        for position in positions[:8]:
            title = str(getattr(position, "title", "") or "Position").strip()
            quantity = float(getattr(position, "quantity", 0.0) or 0.0)
            unit = str(getattr(position, "unit", "") or "").strip()
            unit_price = float(getattr(position, "unit_price_net", 0.0) or 0.0)
            total_net = float(getattr(position, "total_net", quantity * unit_price) or 0.0)
            preview_lines.append(
                f"{title} | {quantity:g} {unit} x {unit_price:.2f} EUR = {total_net:.2f} EUR"
            )

        remaining_count = len(positions) - len(preview_lines)
        if remaining_count > 0:
            preview_lines.append(f"... +{remaining_count} weitere Position(en)")
        group["invoice_positions_preview"] = preview_lines

    def _on_mandant_changed_combo(self) -> None:
        """Handler für Mandantenwechsel im Dropdown."""
        mandant_id = self.mandant_combo.currentData()
        if mandant_id and mandant_id != self.active_mandant_id:
            self._on_mandant_changed(mandant_id)

    def _on_mandant_changed(self, mandant_id: str) -> None:
        """Wechselt zum neuen Mandanten und führt Re-Matching durch."""
        if not mandant_id or mandant_id == self.active_mandant_id:
            return

        self.active_mandant_id = mandant_id
        self._configure_lexware_service_for_mandant(mandant_id)
        self._lexware_customers_cache = []
        self._lexware_templates_cache = {}
        self._apply_customer_matching_for_mandant(mandant_id)
        self._refresh_articles_for_mandant(mandant_id)
        self._apply_draft_defaults_for_mandant(mandant_id)
        self._refresh_article_template_combo_for_group(self._current_group_for_article_editing())
        self._save_manual_data()
        self._log_action(f"Mandant gewechselt | {self._get_mandant_by_id(mandant_id).get('display_name', mandant_id)}")
        self.refresh_table()

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
        return focused in {
            getattr(self, "note_edit", None),
            getattr(self, "search_input", None),
            getattr(self, "draft_title_edit", None),
            getattr(self, "draft_introduction_edit", None),
            getattr(self, "draft_remark_edit", None),
            getattr(self, "travel_hours_spin", None),
            getattr(self, "travel_km_spin", None),
            getattr(self, "travel_hour_rate_spin", None),
            getattr(self, "travel_km_rate_spin", None),
            getattr(self, "travel_mode_combo", None),
        }

    def _draft_export_settings(self) -> dict:
        title_widget = getattr(self, "draft_title_edit", None)
        introduction_widget = getattr(self, "draft_introduction_edit", None)
        remark_widget = getattr(self, "draft_remark_edit", None)
        payment_term_widget = getattr(self, "draft_payment_term_days_spin", None)

        return {
            "title": title_widget.text().strip() if title_widget is not None else "Angebot",
            "introduction": introduction_widget.toPlainText().strip() if introduction_widget is not None else "Automatisch erzeugter Entwurf für das Angebot.",
            "remark": remark_widget.toPlainText().strip() if remark_widget is not None else "Erzeugt durch Rechnungsautomatismus",
            "payment_term_days": payment_term_widget.value() if payment_term_widget is not None else 14,
        }

    def _draft_templates_for_mandant(self) -> tuple[list[str], list[str]]:
        mandant = self._get_mandant_by_id(self.active_mandant_id)
        intro_templates = []
        remark_templates = []

        if mandant:
            intro_templates = [
                str(x).strip()
                for x in mandant.get("draft_introduction_templates", [])
                if str(x).strip()
            ]
            remark_templates = [
                str(x).strip()
                for x in mandant.get("draft_remark_templates", [])
                if str(x).strip()
            ]

        intro_widget = getattr(self, "draft_introduction_edit", None)
        remark_widget = getattr(self, "draft_remark_edit", None)
        current_intro = str(intro_widget.toPlainText() if intro_widget is not None else "").strip()
        current_remark = str(remark_widget.toPlainText() if remark_widget is not None else "").strip()

        if current_intro and current_intro not in intro_templates:
            intro_templates.insert(0, current_intro)
        if current_remark and current_remark not in remark_templates:
            remark_templates.insert(0, current_remark)

        if not intro_templates:
            intro_templates = ["Automatisch erzeugter Entwurf für das Angebot."]
        if not remark_templates:
            remark_templates = ["Erzeugt durch Rechnungsautomatismus"]

        return intro_templates, remark_templates

    def _current_voucher_type(self) -> str:
        service = getattr(self, "lexware_export_service", None)
        endpoint = str(getattr(service, "draft_endpoint", "") or "").lower()
        if "invoice" in endpoint:
            return "invoice"
        return "quotation"

    def _load_lexware_customers(self) -> tuple[list[dict], str]:
        service = getattr(self, "lexware_export_service", None)
        if service is None or not hasattr(service, "fetch_customers"):
            return [], "Lexware Kunden-API nicht verfügbar."
        self._configure_lexware_service_for_mandant(self.active_mandant_id)
        if not service.is_configured():
            return [], "Lexware nicht konfiguriert."

        company_id = self._get_lexware_company_id_for_mandant(self.active_mandant_id)
        result = service.fetch_customers(company_id=company_id)
        if not result.get("success"):
            return [], str(result.get("error", "Unbekannter API-Fehler"))

        customers = result.get("customers", [])
        if isinstance(customers, list):
            self._lexware_customers_cache = [x for x in customers if isinstance(x, dict)]
        return list(self._lexware_customers_cache), ""

    def _load_lexware_templates(self, customer_number: str = "", customer_name: str = "") -> tuple[list[dict], str]:
        service = getattr(self, "lexware_export_service", None)
        if service is None or not hasattr(service, "fetch_text_templates"):
            return [], "Lexware Vorlagen-API nicht verfügbar."
        self._configure_lexware_service_for_mandant(self.active_mandant_id)
        if not service.is_configured():
            return [], "Lexware nicht konfiguriert."

        voucher_type = self._current_voucher_type()
        cache_key = "|".join([
            voucher_type,
            str(customer_number or "").strip().lower(),
            str(customer_name or "").strip().lower(),
        ])
        if cache_key in self._lexware_templates_cache:
            return list(self._lexware_templates_cache.get(cache_key, [])), ""

        company_id = self._get_lexware_company_id_for_mandant(self.active_mandant_id)
        result = service.fetch_text_templates(
            voucher_type=voucher_type,
            customer_number=customer_number,
            customer_name=customer_name,
            company_id=company_id,
        )
        if not result.get("success"):
            return [], str(result.get("error", "Unbekannter API-Fehler"))

        templates = result.get("templates", [])
        normalized = [x for x in templates if isinstance(x, dict)] if isinstance(templates, list) else []
        self._lexware_templates_cache[cache_key] = normalized
        return list(normalized), ""

    def _lexware_template_display_text(self, template: dict) -> str:
        name = str(template.get("name", "") or "Vorlage").strip()
        customer = str(template.get("customer_name", "") or "").strip()
        customer_no = str(template.get("customer_number", "") or "").strip()

        suffix_parts = []
        if customer:
            suffix_parts.append(customer)
        if customer_no:
            suffix_parts.append(f"Nr. {customer_no}")

        if suffix_parts:
            return f"{name} ({' | '.join(suffix_parts)})"
        return name

    def _normalize_customer_lookup_text(self, value: str) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        tokens = [t for t in text.split() if t and t not in {"gmbh", "ag", "kg", "co", "mbh", "und"}]
        return " ".join(tokens)

    def _humanize_lexware_error(self, error_text: str, endpoint: str) -> str:
        text = str(error_text or "").strip()
        if "404" in text:
            return (
                f"HTTP 404: Endpoint nicht gefunden ({endpoint}). "
                "Bitte Lexware-Endpunkt in .env prüfen oder lokale Vorlagen verwenden."
            )
        return text or "Unbekannter API-Fehler"

    def open_offer_editor_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Angebot / Rechnung bearbeiten")
        dialog.resize(860, 760)

        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        current_title = self.draft_title_edit.text().strip()
        title_type_combo = QComboBox()
        title_type_combo.addItem("Angebot", "Angebot")
        title_type_combo.addItem("Rechnung", "Rechnung")
        intro_templates, remark_templates = self._draft_templates_for_mandant()

        intro_template_combo = QComboBox()
        intro_template_combo.addItems(intro_templates)
        intro_edit = QPlainTextEdit(self.draft_introduction_edit.toPlainText().strip())
        intro_edit.setMinimumHeight(90)

        remark_template_combo = QComboBox()
        remark_template_combo.addItems(remark_templates)
        remark_edit = QPlainTextEdit(self.draft_remark_edit.toPlainText().strip())
        remark_edit.setMinimumHeight(90)

        lexware_customer_combo = QComboBox()
        lexware_customer_combo.setMinimumWidth(380)
        lexware_customer_combo.addItem("Aktueller Kunde (aus Auswahl)", "")

        lexware_template_combo = QComboBox()
        lexware_template_combo.setMinimumWidth(380)
        lexware_template_combo.addItem("Keine Lexware-Vorlage geladen", -1)

        lexware_status_label = QLabel("Lexware: noch nicht geladen")
        lexware_load_button = QPushButton("Lexware Vorlagen laden")
        customer_only_templates_check = QCheckBox("Nur kundenspezifische Vorlagen anzeigen")
        customer_only_templates_check.setChecked(True)

        def _apply_intro_template(index: int) -> None:
            if 0 <= index < len(intro_templates):
                intro_edit.setPlainText(intro_templates[index])

        def _apply_remark_template(index: int) -> None:
            if 0 <= index < len(remark_templates):
                remark_edit.setPlainText(remark_templates[index])

        intro_template_combo.currentIndexChanged.connect(_apply_intro_template)
        remark_template_combo.currentIndexChanged.connect(_apply_remark_template)

        group = self._current_group_for_article_editing()

        project_name = ""
        if group is not None:
            project_name = str(group.get("projekt_roh", "") or "").strip()

        initial_title_type = "Angebot"
        if current_title.lower().startswith("rechnung"):
            initial_title_type = "Rechnung"
        title_type_index = title_type_combo.findData(initial_title_type)
        title_type_combo.setCurrentIndex(title_type_index if title_type_index >= 0 else 0)

        title_preview_label = QLabel()
        title_preview_label.setWordWrap(True)

        def _refresh_title_preview() -> None:
            title_type = str(title_type_combo.currentData() or "Angebot").strip()
            suffix = f" - {project_name}" if project_name else ""
            title_preview_label.setText(f"{title_type}{suffix}")

        title_type_combo.currentIndexChanged.connect(_refresh_title_preview)
        _refresh_title_preview()

        current_customer_name = ""
        current_customer_number = ""
        if group is not None:
            current_customer_name = str(group.get("customer_match_name", "") or group.get("kunde_roh", "") or "").strip()
            current_customer_number = str(group.get("customer_match_number", "") or "").strip()

        loaded_templates: list[dict] = []
        all_templates: list[dict] = []

        def _selected_customer_filter() -> tuple[str, str]:
            selected_customer = lexware_customer_combo.currentData()
            if isinstance(selected_customer, dict):
                number = str(selected_customer.get("customer_number", "") or "").strip()
                name = str(selected_customer.get("name", "") or "").strip()
                return number, name
            return current_customer_number, current_customer_name

        def _populate_lexware_template_combo(templates: list[dict]) -> None:
            lexware_template_combo.blockSignals(True)
            lexware_template_combo.clear()
            if not templates:
                lexware_template_combo.addItem("Keine passende Lexware-Vorlage gefunden", -1)
            else:
                for idx, template in enumerate(templates):
                    lexware_template_combo.addItem(self._lexware_template_display_text(template), idx)
            lexware_template_combo.blockSignals(False)

        def _filter_templates_for_ui(templates: list[dict]) -> list[dict]:
            selected_customer = lexware_customer_combo.currentData()
            selected_number = ""
            selected_name = ""
            if isinstance(selected_customer, dict):
                selected_number = str(selected_customer.get("customer_number", "") or "").strip().lower()
                selected_name = str(selected_customer.get("name", "") or "").strip().lower()
            elif current_customer_number or current_customer_name:
                selected_number = str(current_customer_number or "").strip().lower()
                selected_name = str(current_customer_name or "").strip().lower()

            if not customer_only_templates_check.isChecked():
                return list(templates)

            filtered = []
            for template in templates:
                t_number = str(template.get("customer_number", "") or "").strip().lower()
                t_name = str(template.get("customer_name", "") or "").strip().lower()
                if not (t_number or t_name):
                    continue
                if selected_number and t_number and selected_number in t_number:
                    filtered.append(template)
                    continue
                if selected_name and t_name and selected_name in t_name:
                    filtered.append(template)
                    continue
                if not selected_number and not selected_name:
                    filtered.append(template)
            return filtered

        def _apply_lexware_template(index: int) -> None:
            if not (0 <= index < len(loaded_templates)):
                return
            template = loaded_templates[index]
            intro = str(template.get("introduction", "") or "").strip()
            remark = str(template.get("remark", "") or "").strip()
            if intro:
                intro_edit.setPlainText(intro)
            if remark:
                remark_edit.setPlainText(remark)

        def _load_lexware_templates_for_selected_customer() -> None:
            customer_number, customer_name = _selected_customer_filter()
            templates, error_text = self._load_lexware_templates(
                customer_number=customer_number,
                customer_name=customer_name,
            )
            all_templates.clear()
            all_templates.extend(templates)
            loaded_templates.clear()
            filtered_templates = _filter_templates_for_ui(all_templates)
            fallback_to_all = False
            if not filtered_templates and all_templates and customer_only_templates_check.isChecked():
                # UX-Fallback: lieber globale Vorlagen zeigen als leere Liste.
                fallback_to_all = True
                filtered_templates = list(all_templates)

            loaded_templates.extend(filtered_templates)
            _populate_lexware_template_combo(loaded_templates)

            if error_text:
                service = getattr(self, "lexware_export_service", None)
                endpoint = str(getattr(service, "templates_endpoint", "/v1/text-modules") or "/v1/text-modules")
                lexware_status_label.setText(f"Lexware: {self._humanize_lexware_error(error_text, endpoint)}")
            else:
                status = f"Lexware: {len(all_templates)} geladen, {len(loaded_templates)} angezeigt"
                if fallback_to_all:
                    status += " (kundenbezogen 0 Treffer -> globale Vorlagen gezeigt)"
                lexware_status_label.setText(status)

        def _load_lexware_data() -> None:
            customers, customer_error = self._load_lexware_customers()
            lexware_customer_combo.blockSignals(True)
            lexware_customer_combo.clear()
            current_text = current_customer_name or "Unbekannt"
            if current_customer_number:
                current_text += f" (Nr. {current_customer_number})"
            lexware_customer_combo.addItem(f"Aktueller Kunde (aus Termin): {current_text}", "")

            preselect_index = 0
            lookup_name = self._normalize_customer_lookup_text(current_customer_name)
            for customer in customers:
                name = str(customer.get("name", "") or "").strip()
                number = str(customer.get("customer_number", "") or "").strip()
                city = str(customer.get("city", "") or "").strip()
                if not name:
                    continue
                text = f"{name}"
                if number:
                    text += f" (Nr. {number})"
                if city:
                    text += f" - {city}"
                lexware_customer_combo.addItem(text, customer)

                if current_customer_number and number and current_customer_number == number:
                    preselect_index = lexware_customer_combo.count() - 1
                    continue

                if lookup_name:
                    candidate = self._normalize_customer_lookup_text(name)
                    if candidate and (lookup_name in candidate or candidate in lookup_name):
                        preselect_index = lexware_customer_combo.count() - 1

            lexware_customer_combo.setCurrentIndex(preselect_index)
            lexware_customer_combo.blockSignals(False)

            _load_lexware_templates_for_selected_customer()
            if customer_error and not loaded_templates:
                service = getattr(self, "lexware_export_service", None)
                endpoint = str(getattr(service, "customers_endpoint", "/v1/contacts") or "/v1/contacts")
                lexware_status_label.setText(f"Lexware: {self._humanize_lexware_error(customer_error, endpoint)}")

        lexware_load_button.clicked.connect(_load_lexware_data)
        lexware_customer_combo.currentIndexChanged.connect(lambda _: _load_lexware_templates_for_selected_customer())
        lexware_template_combo.currentIndexChanged.connect(_apply_lexware_template)
        customer_only_templates_check.stateChanged.connect(lambda _: _load_lexware_templates_for_selected_customer())

        payment_days = QSpinBox()
        payment_days.setRange(0, 365)
        payment_days.setValue(int(self.draft_payment_term_days_spin.value()))
        payment_days.setSuffix(" Tage netto")

        form.addRow("Belegtyp", title_type_combo)
        form.addRow("Belegtitel", title_preview_label)
        form.addRow("Einleitung Vorlage", intro_template_combo)
        form.addRow("Einleitung", intro_edit)
        form.addRow("Nachbemerkung Vorlage", remark_template_combo)
        form.addRow("Nachbemerkung", remark_edit)
        form.addRow("Lexware Kunde", lexware_customer_combo)
        form.addRow("Lexware Vorlage", lexware_template_combo)
        form.addRow("Filter", customer_only_templates_check)
        form.addRow("Lexware", lexware_load_button)
        form.addRow("Status", lexware_status_label)
        form.addRow("Zahlungsziel", payment_days)

        travel_mode_combo = QComboBox()
        travel_mode_combo.addItem("Fahrtkosten als extra Artikel", "extra_article")
        travel_mode_combo.addItem("Fahrtkosten im 1. Artikel enthalten", "included_in_first_article")
        travel_hours = QDoubleSpinBox()
        travel_hours.setRange(0.0, 1000.0)
        travel_hours.setDecimals(2)
        travel_hours.setSuffix(" h")
        travel_km = QDoubleSpinBox()
        travel_km.setRange(0.0, 100000.0)
        travel_km.setDecimals(0)
        travel_km.setSingleStep(10.0)
        travel_km.setSuffix(" km")
        travel_hour_rate = QDoubleSpinBox()
        travel_hour_rate.setRange(0.0, 10000.0)
        travel_hour_rate.setDecimals(2)
        travel_hour_rate.setPrefix("EUR ")
        travel_km_rate = QDoubleSpinBox()
        travel_km_rate.setRange(0.0, 100.0)
        travel_km_rate.setDecimals(2)
        travel_km_rate.setPrefix("EUR ")

        if group is not None:
            self._ensure_travel_fields_for_group(group)
            mode_index = travel_mode_combo.findData(group.get("travel_mode", self._default_travel_mode_for_group(group)))
            travel_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
            travel_hours.setValue(float(group.get("travel_hours", 0.0) or 0.0))
            travel_km.setValue(float(group.get("travel_km", 0.0) or 0.0))
            travel_hour_rate.setValue(float(group.get("travel_hour_rate", 150.0) or 150.0))
            travel_km_rate.setValue(float(group.get("travel_km_rate", 0.7) or 0.7))
        else:
            travel_mode_combo.setCurrentIndex(0)
            travel_hours.setValue(0.0)
            travel_km.setValue(0.0)
            travel_hour_rate.setValue(150.0)
            travel_km_rate.setValue(0.7)
            for w in [travel_mode_combo, travel_hours, travel_km, travel_hour_rate, travel_km_rate]:
                w.setEnabled(False)

        form.addRow("Fahrtkostenmodus", travel_mode_combo)
        travel_forward_assignment_combo = QComboBox()
        travel_forward_assignment_combo.addItem("Weiterfahrt auf Tag 1", "tag_1")
        travel_forward_assignment_combo.addItem("Weiterfahrt auf Tag 2", "tag_2")

        multi_day_allowance_assignment_combo = QComboBox()
        multi_day_allowance_assignment_combo.addItem("Mehrtagespauschale auf Tag 1", "tag_1")
        multi_day_allowance_assignment_combo.addItem("Mehrtagespauschale auf Tag 2", "tag_2")

        if group is not None:
            forward_rule = str(group.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule()) or self._default_travel_forward_assignment_rule())
            forward_index = travel_forward_assignment_combo.findData(forward_rule)
            travel_forward_assignment_combo.setCurrentIndex(forward_index if forward_index >= 0 else 1)

            allowance_rule = str(group.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule()) or self._default_multi_day_allowance_assignment_rule())
            allowance_index = multi_day_allowance_assignment_combo.findData(allowance_rule)
            multi_day_allowance_assignment_combo.setCurrentIndex(allowance_index if allowance_index >= 0 else 0)
        else:
            travel_forward_assignment_combo.setCurrentIndex(1)
            multi_day_allowance_assignment_combo.setCurrentIndex(0)
            travel_forward_assignment_combo.setEnabled(False)
            multi_day_allowance_assignment_combo.setEnabled(False)

        form.addRow("Weiterfahrt-Zuordnung", travel_forward_assignment_combo)
        form.addRow("Mehrtagespauschale-Zuordnung", multi_day_allowance_assignment_combo)
        form.addRow("Fahrtstunden", travel_hours)
        form.addRow("Kilometer", travel_km)
        form.addRow("Stundensatz", travel_hour_rate)
        form.addRow("KM-Satz", travel_km_rate)

        route_origin = str((group or {}).get("travel_route_origin", "") or self._mandant_full_address(self.active_mandant_id) or "-")
        route_destination = str((group or {}).get("travel_route_destination", "") or (group or {}).get("adresse_roh", "") or "-")
        route_label = QLabel(f"Start: {route_origin}\nZiel: {route_destination}")
        route_label.setWordWrap(True)
        form.addRow("Angenommene Route", route_label)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        # Initialer Versuch, echte Lexware-Daten nachzuladen.
        _load_lexware_data()

        if dialog.exec() != QDialog.Accepted:
            return

        self.draft_title_edit.setText(title_preview_label.text().strip())
        self.draft_introduction_edit.setPlainText(intro_edit.toPlainText().strip())
        self.draft_remark_edit.setPlainText(remark_edit.toPlainText().strip())
        self.draft_payment_term_days_spin.setValue(int(payment_days.value()))

        if group is not None:
            group["travel_mode"] = str(travel_mode_combo.currentData() or self._default_travel_mode_for_group(group))
            group["travel_forward_assignment_rule"] = str(
                travel_forward_assignment_combo.currentData() or self._default_travel_forward_assignment_rule()
            )
            group["multi_day_allowance_assignment_rule"] = str(
                multi_day_allowance_assignment_combo.currentData() or self._default_multi_day_allowance_assignment_rule()
            )
            group["travel_hours"] = float(travel_hours.value())
            group["travel_km"] = float(travel_km.value())
            group["travel_hour_rate"] = float(travel_hour_rate.value())
            group["travel_km_rate"] = float(travel_km_rate.value())
            group["travel_values_source"] = "manual"
            self._sync_travel_editor_from_group(group)
            self._mark_changed([group])
            self._save_manual_data()
            self.detail_view.setPlainText(self._build_detail_text(group))

        self._update_draft_preview()

    def _default_travel_mode_for_group(self, group: dict) -> str:
        customer = str((group or {}).get("kunde_roh", "") or "").strip().lower()
        if "faber etec" in customer:
            return "included_in_first_article"
        return "extra_article"

    def _ensure_travel_fields_for_group(self, group: dict) -> None:
        default_mode = self._default_travel_mode_for_group(group)
        group.setdefault("travel_mode", default_mode)
        group.setdefault("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
        group.setdefault("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule())
        group.setdefault("travel_hours", 0.0)
        group.setdefault("travel_km", 0.0)
        group.setdefault("travel_hour_rate", 150.0)
        group.setdefault("travel_km_rate", 0.7)
        group.setdefault("travel_values_source", "")

    def _travel_amount_for_group(self, group: dict) -> float:
        self._ensure_travel_fields_for_group(group)
        hours = float(group.get("travel_hours", 0.0) or 0.0)
        km = float(group.get("travel_km", 0.0) or 0.0)
        hour_rate = float(group.get("travel_hour_rate", 150.0) or 0.0)
        km_rate = float(group.get("travel_km_rate", 0.7) or 0.0)
        return round((hours * hour_rate) + (km * km_rate), 2)

    def _sync_travel_editor_from_group(self, group: dict | None) -> None:
        widgets = [
            self.travel_mode_combo,
            self.travel_hours_spin,
            self.travel_km_spin,
            self.travel_hour_rate_spin,
            self.travel_km_rate_spin,
        ]
        for widget in widgets:
            widget.blockSignals(True)

        if group is None:
            self.travel_mode_combo.setCurrentIndex(0)
            self.travel_hours_spin.setValue(0.0)
            self.travel_km_spin.setValue(0.0)
            self.travel_hour_rate_spin.setValue(150.0)
            self.travel_km_rate_spin.setValue(0.7)
        else:
            self._ensure_travel_fields_for_group(group)
            mode = str(group.get("travel_mode", "") or self._default_travel_mode_for_group(group))
            idx = self.travel_mode_combo.findData(mode)
            self.travel_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.travel_hours_spin.setValue(float(group.get("travel_hours", 0.0) or 0.0))
            self.travel_km_spin.setValue(float(group.get("travel_km", 0.0) or 0.0))
            self.travel_hour_rate_spin.setValue(float(group.get("travel_hour_rate", 150.0) or 150.0))
            self.travel_km_rate_spin.setValue(float(group.get("travel_km_rate", 0.7) or 0.7))

        for widget in widgets:
            widget.blockSignals(False)

    def _apply_travel_editor_to_group(self, group: dict) -> None:
        self._ensure_travel_fields_for_group(group)
        group["travel_mode"] = str(self.travel_mode_combo.currentData() or self._default_travel_mode_for_group(group))
        group["travel_hours"] = float(self.travel_hours_spin.value())
        group["travel_km"] = float(self.travel_km_spin.value())
        group["travel_hour_rate"] = float(self.travel_hour_rate_spin.value())
        group["travel_km_rate"] = float(self.travel_km_rate_spin.value())
        group["travel_values_source"] = "manual"

    def _on_travel_settings_changed(self) -> None:
        group = self._current_group_for_article_editing()
        if group is None:
            return

        self._apply_travel_editor_to_group(group)
        self._mark_changed([group])
        self._save_manual_data()
        self.detail_view.setPlainText(self._build_detail_text(group))
        self._update_draft_preview()

    def _update_draft_preview(self) -> None:
        preview_widget = getattr(self, "draft_preview_view", None)
        if preview_widget is None:
            return

        settings = self._draft_export_settings()
        selected_groups = self._selected_groups()
        group = selected_groups[0] if len(selected_groups) == 1 else None

        lines = [
            f"{settings['title']}",
            "=" * max(len(settings["title"]), 9),
            f"Einleitung: {settings['introduction']}",
            f"Nachbemerkung: {settings['remark']}",
            f"Zahlungsziel: {settings['payment_term_days']} Tage netto",
        ]

        if group is not None:
            selected_articles = self._selected_articles_for_group(group)
            if not selected_articles:
                selected_article = self._selected_article_for_group(group)
                selected_articles = [selected_article] if selected_article else []

            article_count = len(selected_articles)
            lines.extend([
                "",
                "Belegdaten",
                "----------",
                f"Kunde  : {group.get('kunde_roh', '')}",
                f"Projekt: {group.get('projekt_roh', '')}",
                f"Positionen: {article_count if article_count else 1}",
                f"Fahrtkostenmodus: {group.get('travel_mode', self._default_travel_mode_for_group(group))}",
                f"Weiterfahrt-Zuordnung: {group.get('travel_forward_assignment_rule', self._default_travel_forward_assignment_rule())}",
                f"Mehrtagespauschale-Zuordnung: {group.get('multi_day_allowance_assignment_rule', self._default_multi_day_allowance_assignment_rule())}",
                f"Fahrtstunden: {group.get('travel_hours', 0.0)}",
                f"Fahrtkilometer: {group.get('travel_km', 0.0)}",
                f"Stundensatz: {group.get('travel_hour_rate', 150.0)} EUR",
                f"KM-Satz: {group.get('travel_km_rate', 0.7)} EUR",
                f"Fahrtkosten gesamt: {self._travel_amount_for_group(group)} EUR",
            ])

            if selected_articles:
                lines.append("")
                lines.append("Positionen")
                lines.append("----------")
                for index, article in enumerate(selected_articles, start=1):
                    if not isinstance(article, dict):
                        continue

                    article_number = str(article.get("Artikelnummer", "") or "").strip()
                    article_name = str(article.get("Bezeichnung", "") or "").strip() or f"Artikel {index}"
                    article_unit = str(article.get("Einheit", "") or "").strip() or "Stk"
                    article_price = str(article.get("VK (Netto)", "") or "").strip() or "0,00"
                    article_tax = str(article.get("Steuerart", "") or "").strip() or "19%"

                    title_parts = [part for part in [article_number, article_name] if part]
                    lines.append(f"{index:>2}. {' - '.join(title_parts)}")
                    lines.append(f"    Einheit: {article_unit} | Netto: {article_price} | Steuer: {article_tax}")

        preview_widget.setPlainText("\n".join(lines))

    def _set_default_draft_export_settings(self) -> None:
        title_widget = getattr(self, "draft_title_edit", None)
        introduction_widget = getattr(self, "draft_introduction_edit", None)
        remark_widget = getattr(self, "draft_remark_edit", None)
        payment_term_widget = getattr(self, "draft_payment_term_days_spin", None)

        if title_widget is not None:
            title_widget.setText("Angebot")
        if introduction_widget is not None:
            introduction_widget.setPlainText("Automatisch erzeugter Entwurf für das Angebot.")
        if remark_widget is not None:
            remark_widget.setPlainText("Erzeugt durch Rechnungsautomatismus")
        if payment_term_widget is not None:
            payment_term_widget.setValue(14)

    def _apply_draft_export_settings(self, settings: dict | None) -> None:
        if not isinstance(settings, dict):
            return

        title_widget = getattr(self, "draft_title_edit", None)
        introduction_widget = getattr(self, "draft_introduction_edit", None)
        remark_widget = getattr(self, "draft_remark_edit", None)
        payment_term_widget = getattr(self, "draft_payment_term_days_spin", None)

        if title_widget is not None:
            title = str(settings.get("title", "") or "").strip()
            if title:
                title_widget.setText(title)

        if introduction_widget is not None:
            introduction = str(settings.get("introduction", "") or "").strip()
            if introduction:
                introduction_widget.setPlainText(introduction)

        if remark_widget is not None:
            remark = str(settings.get("remark", "") or "").strip()
            if remark:
                remark_widget.setPlainText(remark)

        if payment_term_widget is not None:
            raw_days = settings.get("payment_term_days", None)
            try:
                payment_term_widget.setValue(max(int(raw_days), 0))
            except Exception:
                pass

    def _apply_draft_defaults_for_mandant(self, mandant_id: str) -> None:
        mandant = self._get_mandant_by_id(mandant_id)
        if not mandant:
            return

        payment_terms = str(mandant.get("default_payment_terms", "") or "").strip()
        payment_term_widget = getattr(self, "draft_payment_term_days_spin", None)
        if payment_term_widget is None or not payment_terms:
            return

        match = re.search(r"\d+", payment_terms)
        if match:
            try:
                payment_term_widget.setValue(max(int(match.group(0)), 0))
            except Exception:
                pass

        title_widget = getattr(self, "draft_title_edit", None)
        introduction_widget = getattr(self, "draft_introduction_edit", None)
        remark_widget = getattr(self, "draft_remark_edit", None)

        title_default = str(mandant.get("default_draft_title", "") or "").strip()
        if title_widget is not None and title_default:
            title_widget.setText(title_default)

        introduction_default = str(mandant.get("default_draft_introduction", "") or "").strip()
        if introduction_widget is not None and introduction_default:
            introduction_widget.setPlainText(introduction_default)

        remark_default = str(mandant.get("default_draft_remark", "") or "").strip()
        if remark_widget is not None and remark_default:
            remark_widget.setPlainText(remark_default)

        self._update_draft_preview()

    def _current_selected_row(self) -> int:
        table_widget = getattr(self, "table_widget", None)
        if table_widget is None:
            return -1

        row = table_widget.currentRow()
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
            "selected_article_key": group.get("selected_article_key", ""),
            "selected_article": group.get("selected_article", {}),
            "_last_changed_at": group.get("_last_changed_at", ""),
            "lexware_export_status": group.get("lexware_export_status", ""),
            "lexware_export_id": group.get("lexware_export_id", ""),
            "lexware_export_resource_uri": group.get("lexware_export_resource_uri", ""),
            "lexware_exported_at": group.get("lexware_exported_at", ""),
            "travel_mode": group.get("travel_mode", ""),
            "travel_forward_assignment_rule": group.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule()),
            "multi_day_allowance_assignment_rule": group.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule()),
            "travel_values_source": group.get("travel_values_source", ""),
            "travel_hours": group.get("travel_hours", 0.0),
            "travel_km": group.get("travel_km", 0.0),
            "travel_hour_rate": group.get("travel_hour_rate", 150.0),
            "travel_km_rate": group.get("travel_km_rate", 0.7),
        }

    def _restore_group_states(self, states: list[dict]) -> None:
        state_map = {state["key"]: state for state in states}
        for group in self.groups:
            key = self._build_group_key(group)
            if key in state_map:
                group["manueller_status"] = state_map[key].get("manueller_status", "offen")
                group["manuelle_notiz"] = state_map[key].get("manuelle_notiz", "")
                article = state_map[key].get("selected_article", {})
                if isinstance(article, dict) and article:
                    self._apply_article_to_group(group, article)
                else:
                    group["selected_article"] = {}
                    group["selected_article_key"] = state_map[key].get("selected_article_key", "")
                group["_last_changed_at"] = state_map[key].get("_last_changed_at", "")
                group["lexware_export_status"] = state_map[key].get("lexware_export_status", "")
                group["lexware_export_id"] = state_map[key].get("lexware_export_id", "")
                group["lexware_export_resource_uri"] = state_map[key].get("lexware_export_resource_uri", "")
                group["lexware_exported_at"] = state_map[key].get("lexware_exported_at", "")
                group["travel_mode"] = state_map[key].get("travel_mode", self._default_travel_mode_for_group(group))
                group["travel_forward_assignment_rule"] = state_map[key].get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
                group["multi_day_allowance_assignment_rule"] = state_map[key].get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule())
                group["travel_values_source"] = state_map[key].get("travel_values_source", "")
                group["travel_hours"] = float(state_map[key].get("travel_hours", 0.0) or 0.0)
                group["travel_km"] = float(state_map[key].get("travel_km", 0.0) or 0.0)
                group["travel_hour_rate"] = float(state_map[key].get("travel_hour_rate", 150.0) or 150.0)
                group["travel_km_rate"] = float(state_map[key].get("travel_km_rate", 0.7) or 0.7)

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
            group.setdefault("selected_articles", [])
            group.setdefault("selected_article_key", "")
            group.setdefault("selected_article", {})
            group.setdefault("_last_changed_at", "")
            group.setdefault("lexware_export_status", "")
            group.setdefault("lexware_export_id", "")
            group.setdefault("lexware_export_resource_uri", "")
            group.setdefault("lexware_exported_at", "")
            group.setdefault("customer_match_state", "nicht_zugeordnet")
            group.setdefault("customer_match_name", "")
            group.setdefault("customer_match_number", "")
            group.setdefault("customer_match_street", "")
            group.setdefault("customer_match_zip", "")
            group.setdefault("customer_match_city", "")
            group.setdefault("customer_match_country", "DE")
            group.setdefault("invoice_validation_errors", 0)
            group.setdefault("invoice_validation_warnings", 0)
            group.setdefault("invoice_validation_infos", 0)
            group.setdefault("invoice_validation_messages", [])
            group.setdefault("invoice_validation_state", "Unbekannt")
            group.setdefault("invoice_export_ready", False)
            group.setdefault("invoice_positions_count", 0)
            group.setdefault("invoice_positions_preview", [])
            self._ensure_travel_fields_for_group(group)

        # Setze active_mandant_id auf den Standard-Mandanten (oder bewahre ihn)
        if not self.active_mandant_id or self.active_mandant_id not in [m.get("id") for m in self.mandants]:
            self.active_mandant_id = self.mandants[0]["id"] if self.mandants else ""

        self._refresh_articles_for_mandant(self.active_mandant_id)
        self._apply_customer_matching_for_mandant(self.active_mandant_id)

        self._apply_saved_manual_data()
        self._apply_customer_matching_for_mandant(self.active_mandant_id)

        if reset_session_state:
            self.last_action = None
            self.change_log.clear()
            self.log_view.clear()

        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        self.refresh_table()
        self.setWindowTitle(f"Rechnungsvorschlag Tool - {file_path}")

        if reset_session_state:
            self._log_action(f"Datei geladen | {file_path}")

    def _load_contacts_for_matching(self) -> list[dict]:
        if self.contacts_importer is None:
            return []

        paths: list[Path] = []
        try:
            mandants = self.config_loader.load_json("mandants.json").get("mandants", [])
        except Exception:
            mandants = []

        for entry in mandants:
            path_text = str((entry or {}).get("contacts_csv", "")).strip()
            if not path_text:
                continue
            path_obj = Path(path_text)
            if path_obj.exists():
                paths.append(path_obj)

        unique_paths: list[Path] = []
        seen: set[str] = set()
        for path_obj in paths:
            key = str(path_obj.resolve())
            if key in seen:
                continue
            seen.add(key)
            unique_paths.append(path_obj)

        contacts: list[dict] = []
        for path_obj in unique_paths:
            try:
                contacts.extend(self.contacts_importer.load(str(path_obj)))
            except Exception:
                continue

        return contacts

    def _apply_customer_matching(self) -> None:
        """Deprecated: Verwende stattdessen _apply_customer_matching_for_mandant."""
        self._apply_customer_matching_for_mandant(self.active_mandant_id)

    def _customer_match_text(self, group: dict) -> str:
        state = str(group.get("customer_match_state", "nicht_zugeordnet")).strip().lower()
        if state == "eindeutig":
            number = str(group.get("customer_match_number", "")).strip()
            return f"Eindeutig ({number})" if number else "Eindeutig"
        if state == "mehrdeutig":
            return "Mehrdeutig"
        if state == "nicht_gefunden":
            return "Nicht gefunden"
        if state == "nicht_zugeordnet":
            return "Nicht zugeordnet"
        return state

    def _validation_status_text(self, group: dict) -> str:
        state = str(group.get("invoice_validation_state", "")).strip()
        if state:
            return state

        errors = int(group.get("invoice_validation_errors", 0) or 0)
        warnings = int(group.get("invoice_validation_warnings", 0) or 0)
        infos = int(group.get("invoice_validation_infos", 0) or 0)
        if errors > 0:
            return f"Blockiert ({errors})"
        if warnings > 0:
            return f"Warnung ({warnings})"
        if infos > 0:
            return f"Info ({infos})"
        return "OK"

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

        project_data = {
            "source_file": self.current_file_path,
            "groups": {},
            "draft_settings": self._draft_export_settings(),
            "customer_article_templates": getattr(self, "customer_article_templates", {}),
        }
        for group in self.groups:
            key = self._build_group_key(group)
            project_data["groups"][key] = {
                "manueller_status": group.get("manueller_status", "offen"),
                "manuelle_notiz": group.get("manuelle_notiz", ""),
                "selected_articles": group.get("selected_articles", []),
                "selected_article_key": group.get("selected_article_key", ""),
                "selected_article": group.get("selected_article", {}),
                "travel_mode": group.get("travel_mode", self._default_travel_mode_for_group(group)),
                "travel_forward_assignment_rule": group.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule()),
                "multi_day_allowance_assignment_rule": group.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule()),
                "travel_values_source": group.get("travel_values_source", ""),
                "travel_hours": group.get("travel_hours", 0.0),
                "travel_km": group.get("travel_km", 0.0),
                "travel_hour_rate": group.get("travel_hour_rate", 150.0),
                "travel_km_rate": group.get("travel_km_rate", 0.7),
                "lexware_export_status": group.get("lexware_export_status", ""),
                "lexware_export_id": group.get("lexware_export_id", ""),
                "lexware_export_resource_uri": group.get("lexware_export_resource_uri", ""),
                "lexware_exported_at": group.get("lexware_exported_at", ""),
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
            "active_mandant_id": self.active_mandant_id,
            "draft_settings": self._draft_export_settings(),
            "customer_article_templates": getattr(self, "customer_article_templates", {}),
            "groups": {},
            "change_log": self.change_log,
            "saved_at": datetime.now().isoformat(),
        }

        for group in self.groups:
            key = self._build_group_key(group)
            session_data["groups"][key] = {
                "manueller_status": group.get("manueller_status", "offen"),
                "manuelle_notiz": group.get("manuelle_notiz", ""),
                "selected_articles": group.get("selected_articles", []),
                "selected_article_key": group.get("selected_article_key", ""),
                "selected_article": group.get("selected_article", {}),
                "travel_mode": group.get("travel_mode", self._default_travel_mode_for_group(group)),
                "travel_forward_assignment_rule": group.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule()),
                "multi_day_allowance_assignment_rule": group.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule()),
                "travel_values_source": group.get("travel_values_source", ""),
                "travel_hours": group.get("travel_hours", 0.0),
                "travel_km": group.get("travel_km", 0.0),
                "travel_hour_rate": group.get("travel_hour_rate", 150.0),
                "travel_km_rate": group.get("travel_km_rate", 0.7),
                "_last_changed_at": group.get("_last_changed_at", ""),
                "lexware_export_status": group.get("lexware_export_status", ""),
                "lexware_export_id": group.get("lexware_export_id", ""),
                "lexware_export_resource_uri": group.get("lexware_export_resource_uri", ""),
                "lexware_exported_at": group.get("lexware_exported_at", ""),
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
        draft_settings = session_data.get("draft_settings", {})
        loaded_templates = session_data.get("customer_article_templates", {})
        saved_mandant_id = session_data.get("active_mandant_id", "")
        
        if not source_file:
            return

        self.load_file(source_file, reset_session_state=False)

        # Wechsle zum gespeicherten Mandanten, falls vorhanden
        if saved_mandant_id and saved_mandant_id != self.active_mandant_id:
            # Deaktiviere Signal temporär
            self.mandant_combo.blockSignals(True)
            index = self.mandant_combo.findData(saved_mandant_id)
            if index >= 0:
                self.mandant_combo.setCurrentIndex(index)
                self._on_mandant_changed(saved_mandant_id)
            self.mandant_combo.blockSignals(False)

        self._set_default_draft_export_settings()
        self._apply_draft_defaults_for_mandant(self.active_mandant_id)
        self._apply_draft_export_settings(draft_settings)
        self._set_customer_article_templates(loaded_templates)
        self._update_draft_preview()

        for group in self.groups:
            key = self._build_group_key(group)
            if key in group_data:
                entry = group_data[key]
                if isinstance(entry, dict):
                    group["manueller_status"] = entry.get("manueller_status", "offen")
                    group["manuelle_notiz"] = entry.get("manuelle_notiz", "")
                    article = entry.get("selected_article", {})
                    if isinstance(article, dict) and article:
                        self._apply_article_to_group(group, article)
                    else:
                        group["selected_article"] = {}
                        group["selected_article_key"] = entry.get("selected_article_key", "")
                    group["_last_changed_at"] = entry.get("_last_changed_at", "")
                    group["travel_mode"] = entry.get("travel_mode", self._default_travel_mode_for_group(group))
                    group["travel_forward_assignment_rule"] = entry.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
                    group["multi_day_allowance_assignment_rule"] = entry.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule())
                    group["travel_values_source"] = entry.get("travel_values_source", "")
                    group["travel_hours"] = float(entry.get("travel_hours", 0.0) or 0.0)
                    group["travel_km"] = float(entry.get("travel_km", 0.0) or 0.0)
                    group["travel_hour_rate"] = float(entry.get("travel_hour_rate", 150.0) or 150.0)
                    group["travel_km_rate"] = float(entry.get("travel_km_rate", 0.7) or 0.7)
                    group["lexware_export_status"] = entry.get("lexware_export_status", "")
                    group["lexware_export_id"] = entry.get("lexware_export_id", "")
                    group["lexware_export_resource_uri"] = entry.get("lexware_export_resource_uri", "")
                    group["lexware_exported_at"] = entry.get("lexware_exported_at", "")

        loaded_change_log = session_data.get("change_log", [])
        if not isinstance(loaded_change_log, list):
            loaded_change_log = []

        self.change_log = [str(x) for x in loaded_change_log]
        self._save_manual_data()
        self.last_action = None
        self.refresh_table()
        self._refresh_article_template_combo_for_group(self._current_group_for_article_editing())
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
        draft_settings = project_data.get("draft_settings", {})
        loaded_templates = project_data.get("customer_article_templates", {})
        if not source_file:
            return

        self.load_file(source_file)
        self._set_default_draft_export_settings()
        self._apply_draft_defaults_for_mandant(self.active_mandant_id)
        self._apply_draft_export_settings(draft_settings)
        self._set_customer_article_templates(loaded_templates)
        self._update_draft_preview()

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
                    selected_articles = entry.get("selected_articles", [])
                    if isinstance(selected_articles, list) and selected_articles:
                        self._set_selected_articles_for_group(group, selected_articles)
                    else:
                        article = entry.get("selected_article", {})
                        if isinstance(article, dict) and article:
                            self._set_selected_articles_for_group(group, [article])
                        else:
                            group["selected_articles"] = []
                            group["selected_article"] = {}
                            group["selected_article_key"] = entry.get("selected_article_key", "")
                    group["lexware_export_status"] = entry.get("lexware_export_status", "")
                    group["lexware_export_id"] = entry.get("lexware_export_id", "")
                    group["lexware_export_resource_uri"] = entry.get("lexware_export_resource_uri", "")
                    group["lexware_exported_at"] = entry.get("lexware_exported_at", "")
                    group["travel_mode"] = entry.get("travel_mode", self._default_travel_mode_for_group(group))
                    group["travel_forward_assignment_rule"] = entry.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
                    group["multi_day_allowance_assignment_rule"] = entry.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule())
                    group["travel_values_source"] = entry.get("travel_values_source", "")
                    group["travel_hours"] = float(entry.get("travel_hours", 0.0) or 0.0)
                    group["travel_km"] = float(entry.get("travel_km", 0.0) or 0.0)
                    group["travel_hour_rate"] = float(entry.get("travel_hour_rate", 150.0) or 150.0)
                    group["travel_km_rate"] = float(entry.get("travel_km_rate", 0.7) or 0.7)

        self._save_manual_data()
        self.last_action = None
        self.refresh_table()
        self._refresh_article_template_combo_for_group(self._current_group_for_article_editing())
        self._log_action(f"Projekt geladen | {file_path}")

    def export_visible_groups_to_csv(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(self, "CSV-Export speichern", "rechnungsvorschlaege.csv", "CSV-Dateien (*.csv)")
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "ManuellerStatus", "ManuelleNotiz", "Status", "Automatikstatus", "Datum", "KW",
                "Kunde", "Kundenmatch", "Kundennummer", "Validierung", "Projekt", "Adresse", "Ansprechpartner", "Auftrag", "Bemerkungen",
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
                    self._customer_match_text(group),
                    group.get("customer_match_number", ""),
                    self._validation_status_text(group),
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
                "customer_match_state": group.get("customer_match_state", ""),
                "customer_match_name": group.get("customer_match_name", ""),
                "customer_match_number": group.get("customer_match_number", ""),
                "invoice_validation_state": self._validation_status_text(group),
                "invoice_validation_errors": int(group.get("invoice_validation_errors", 0) or 0),
                "invoice_validation_warnings": int(group.get("invoice_validation_warnings", 0) or 0),
                "invoice_validation_infos": int(group.get("invoice_validation_infos", 0) or 0),
                "invoice_export_ready": bool(group.get("invoice_export_ready", False)),
                "invoice_validation_messages": group.get("invoice_validation_messages", []),
                "invoice_positions_count": int(group.get("invoice_positions_count", 0) or 0),
                "invoice_positions_preview": group.get("invoice_positions_preview", []),
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

        blocked_groups = [
            group for group in selected_groups
            if int(group.get("invoice_validation_errors", 0) or 0) > 0
        ]
        if blocked_groups:
            preview = []
            for index, group in enumerate(blocked_groups[:10], start=1):
                preview.append(
                    f"{index}. {self._format_date_for_display(group.get('datum', ''))} | "
                    f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')} | "
                    f"Fehler: {int(group.get('invoice_validation_errors', 0) or 0)}"
                )
            if len(blocked_groups) > 10:
                preview.append(f"... +{len(blocked_groups) - 10} weitere")

            QMessageBox.warning(
                self,
                "Lexware Draft Export blockiert",
                "Export abgebrochen, weil ausgewählte Gruppen harte Validierungsfehler enthalten.\n\n"
                f"Blockiert: {len(blocked_groups)} Gruppe(n)\n\n"
                + "\n".join(preview),
            )
            return

        warning_groups = [
            group for group in selected_groups
            if int(group.get("invoice_validation_warnings", 0) or 0) > 0
        ]
        if warning_groups:
            warning_preview = []
            for index, group in enumerate(warning_groups[:10], start=1):
                warning_preview.append(
                    f"{index}. {self._format_date_for_display(group.get('datum', ''))} | "
                    f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')} | "
                    f"Warnungen: {int(group.get('invoice_validation_warnings', 0) or 0)}"
                )
            if len(warning_groups) > 10:
                warning_preview.append(f"... +{len(warning_groups) - 10} weitere")

            warning_decision = QMessageBox.question(
                self,
                "Export mit Warnungen bestätigen",
                "Die Auswahl enthält Gruppen mit Warnungen.\n"
                "Der Export ist möglich, sollte aber fachlich geprüft werden.\n\n"
                f"Mit Warnungen: {len(warning_groups)} Gruppe(n)\n\n"
                + "\n".join(warning_preview)
                + "\n\nTrotzdem exportieren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if warning_decision != QMessageBox.Yes:
                return

        self._configure_lexware_service_for_mandant(self.active_mandant_id)

        if self.lexware_export_service is None or not self.lexware_export_service.is_configured():
            QMessageBox.warning(
                self,
                "Lexware nicht konfiguriert",
                "Lexware-Zugangsdaten fehlen. Bitte .env prüfen: BASE_URL + ACCESS_TOKEN oder Refresh-Flow (CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/TOKEN_URL).",
            )
            return

        is_quotation_mode = bool(getattr(self.lexware_export_service, "is_quotation_mode", lambda: False)())
        already_exported = [g for g in selected_groups if self._is_already_exported(g)]

        export_mode = "create_new"
        export_candidates: list[dict] = []
        skipped_exported_groups: list[dict] = []
        skipped_count = 0

        if is_quotation_mode:
            if already_exported:
                mode_box = QMessageBox(self)
                mode_box.setIcon(QMessageBox.Question)
                mode_box.setWindowTitle("Angebotsexport: Vorgehen wählen")
                mode_box.setText(
                    f"{len(already_exported)} ausgewählte Gruppe(n) wurden bereits als Angebot exportiert."
                )
                mode_box.setInformativeText(
                    "Ja = bestehende Angebote in Lexware überschreiben\n"
                    "Nein = zusätzliche neue Angebote anlegen\n"
                    "Abbrechen = Export abbrechen"
                )
                mode_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                mode_box.setDefaultButton(QMessageBox.Yes)
                mode_box.button(QMessageBox.Yes).setText("Überschreiben")
                mode_box.button(QMessageBox.No).setText("Neu anlegen")
                mode_box.button(QMessageBox.Cancel).setText("Abbrechen")

                mode_result = mode_box.exec()
                if mode_result == QMessageBox.Cancel:
                    return
                export_mode = "overwrite" if mode_result == QMessageBox.Yes else "create_new"

            export_candidates = list(selected_groups)
            skipped_count = 0
        else:
            skipped_exported_groups = [g for g in selected_groups if self._is_already_exported(g)]
            export_candidates = [g for g in selected_groups if not self._is_already_exported(g)]
            skipped_count = len(selected_groups) - len(export_candidates)
            if not export_candidates:
                skipped_preview = []
                for idx, group in enumerate(skipped_exported_groups[:10], start=1):
                    skipped_preview.append(
                        f"{idx}. {self._format_date_for_display(group.get('datum', ''))} | "
                        f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')}"
                    )
                if len(skipped_exported_groups) > 10:
                    skipped_preview.append(f"... +{len(skipped_exported_groups) - 10} weitere")

                QMessageBox.information(
                    self,
                    "Lexware Draft Export",
                    "Alle ausgewählten Gruppen wurden bereits exportiert und werden nicht erneut erstellt.\n\n"
                    f"Übersprungen: {len(skipped_exported_groups)} Gruppe(n)\n\n"
                    + "\n".join(skipped_preview),
                )
                return

        roundtrip_tours_applied = self._apply_roundtrip_distribution_for_groups(export_candidates)

        geocode_unresolved_groups: list[dict] = []
        for group in export_candidates:
            if float(group.get("travel_km", 0.0) or 0.0) > 0:
                continue
            if self._calculate_travel_km_for_group(group, show_messages=False):
                continue
            geocode_unresolved_groups.append(group)

        if geocode_unresolved_groups:
            geocode_preview = []
            for idx, group in enumerate(geocode_unresolved_groups[:10], start=1):
                geocode_preview.append(
                    f"{idx}. {self._format_date_for_display(group.get('datum', ''))} | "
                    f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')} | "
                    f"Adresse: {str(group.get('adresse_roh', '') or '').strip() or '-'}"
                )
            if len(geocode_unresolved_groups) > 10:
                geocode_preview.append(f"... +{len(geocode_unresolved_groups) - 10} weitere")

            geocode_decision = QMessageBox.question(
                self,
                "Export mit fehlender Geokodierung bestätigen",
                "Bei einigen Gruppen konnte die Strecke nicht automatisch geokodiert werden.\n"
                "Diese Gruppen werden mit den aktuell gesetzten Fahrtwerten exportiert (oft 0 km / 0 h).\n\n"
                f"Betroffen: {len(geocode_unresolved_groups)} Gruppe(n)\n\n"
                + "\n".join(geocode_preview)
                + "\n\nTrotzdem exportieren?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if geocode_decision != QMessageBox.Yes:
                return

        account_context_lines = self._lexware_context_lines_for_groups(export_candidates)

        preview_lines = []
        for idx, group in enumerate(export_candidates[:12], start=1):
            line = (
                f"{idx}. {self._format_date_for_display(group.get('datum', ''))} | "
                f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')}"
            )
            segment_text = self._travel_segment_preview_text(group)
            if segment_text:
                line += f"\n   {segment_text}"
            preview_lines.append(line)
        if len(export_candidates) > 12:
            preview_lines.append(f"... +{len(export_candidates) - 12} weitere")

        skipped_preview_lines = []
        for idx, group in enumerate(skipped_exported_groups[:8], start=1):
            skipped_preview_lines.append(
                f"{idx}. {self._format_date_for_display(group.get('datum', ''))} | "
                f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')}"
            )
        if len(skipped_exported_groups) > 8:
            skipped_preview_lines.append(f"... +{len(skipped_exported_groups) - 8} weitere")

        confirm_text = (
            f"Ausgewählt: {len(selected_groups)} Gruppe(n)\n"
            f"Wird exportiert: {len(export_candidates)} Gruppe(n)\n"
            f"Übersprungen (bereits exportiert): {skipped_count}\n\n"
            f"Mit Warnungen (Auswahl): {len(warning_groups)}\n"
            f"Ohne automatische Geokodierung: {len(geocode_unresolved_groups)}\n"
            f"Rundreisen automatisch verteilt: {roundtrip_tours_applied}\n"
            f"Modus: {'Überschreiben bestehender Angebote' if export_mode == 'overwrite' else 'Neue Entwürfe anlegen'}\n\n"
            + ("Lexware Konto-Kontext:\n" + "\n".join(account_context_lines) + "\n\n" if account_context_lines else "")
            + f"Zu exportierende Gruppen:\n" + "\n".join(preview_lines) + "\n\n"
            + ("Bereits exportiert (Auszug):\n" + "\n".join(skipped_preview_lines) + "\n\n" if skipped_preview_lines else "")
            + "Jetzt exportieren?"
        )
        decision = QMessageBox.question(
            self,
            "Lexware Draft Export bestätigen",
            confirm_text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if decision != QMessageBox.Yes:
            return

        ok_count = 0
        fail_count = 0
        created_count = 0
        overwritten_count = 0
        first_error = ""
        failed_previews: list[str] = []
        export_settings = self._draft_export_settings()

        for group in export_candidates:
            mandant_id = str(group.get("mandant_id", self.active_mandant_id) or self.active_mandant_id)
            self._configure_lexware_service_for_mandant(mandant_id)
            company_id = self._get_lexware_company_id_for_mandant(mandant_id)
            should_overwrite = is_quotation_mode and export_mode == "overwrite" and self._is_already_exported(group)
            export_reference = self._export_reference_for_group(group) if should_overwrite else ""
            result = self.lexware_export_service.export_group_as_draft(
                group,
                company_id=company_id,
                title=export_settings["title"],
                introduction=export_settings["introduction"],
                remark=export_settings["remark"],
                payment_term_days=export_settings["payment_term_days"],
                update_existing=should_overwrite,
                export_reference=export_reference,
            )

            if result.get("success"):
                ok_count += 1
                if should_overwrite:
                    overwritten_count += 1
                else:
                    created_count += 1
                response = result.get("response")
                export_id = ""
                export_resource_uri = ""
                if isinstance(response, dict):
                    export_id = str(response.get("id") or response.get("voucherNumber") or "")
                    export_resource_uri = str(response.get("resourceUri") or response.get("resourceURI") or "")
                if not export_id:
                    export_id = str(export_reference or "")
                if not export_resource_uri and export_reference and "/" in export_reference:
                    export_resource_uri = str(export_reference)
                group["lexware_export_status"] = "exportiert"
                group["lexware_export_id"] = export_id
                group["lexware_export_resource_uri"] = export_resource_uri
                group["lexware_exported_at"] = datetime.now().isoformat(timespec="seconds")
            else:
                fail_count += 1
                group["lexware_export_status"] = "fehler"
                if not self._is_already_exported(group):
                    group["lexware_export_id"] = ""
                    group["lexware_export_resource_uri"] = ""
                group["lexware_exported_at"] = ""
                if not first_error:
                    status = result.get("status_code")
                    err = result.get("error") or "Unbekannter Fehler"
                    response = result.get("response")
                    first_error = f"Status: {status} | Fehler: {err}"
                    if response:
                        first_error += f" | Antwort: {response}"
                if len(failed_previews) < 8:
                    failed_previews.append(
                        f"- {self._format_date_for_display(group.get('datum', ''))} | "
                        f"{group.get('kunde_roh', '')} | {group.get('projekt_roh', '')} | "
                        f"{result.get('error') or 'Unbekannter Fehler'}"
                    )

        warning_export_count = sum(
            1 for group in export_candidates
            if int(group.get("invoice_validation_warnings", 0) or 0) > 0
        )

        self._mark_changed(export_candidates)
        self._save_manual_data()
        self.refresh_table()

        self._log_action(
            "Lexware Draft Export | "
            f"erfolgreich: {ok_count} (neu: {created_count}, ueberschrieben: {overwritten_count}) | "
            f"fehlgeschlagen: {fail_count} | uebersprungen: {skipped_count} | "
            f"mit_warnungen: {warning_export_count}"
        )

        if fail_count == 0:
            QMessageBox.information(
                self,
                "Lexware Draft Export",
                "Export abgeschlossen.\n"
                f"Erfolgreich: {ok_count}\n"
                f"Neu erstellt: {created_count}\n"
                f"Überschrieben: {overwritten_count}\n"
                f"Mit Warnungen (exportiert): {warning_export_count}\n"
                f"Uebersprungen (bereits exportiert): {skipped_count}",
            )
            return

        failed_text = "\n".join(failed_previews)
        if fail_count > len(failed_previews):
            failed_text += f"\n... +{fail_count - len(failed_previews)} weitere Fehler"

        QMessageBox.warning(
            self,
            "Lexware Draft Export mit Fehlern",
            "Export abgeschlossen mit Fehlern.\n"
            f"Erfolgreich: {ok_count}\n"
            f"Neu erstellt: {created_count}\n"
            f"Überschrieben: {overwritten_count}\n"
            f"Fehlgeschlagen: {fail_count}\n"
            f"Mit Warnungen (exportiert): {warning_export_count}\n"
            f"Uebersprungen (bereits exportiert): {skipped_count}\n\n"
            f"Erster Fehler:\n{first_error}\n\n"
            f"Fehlerliste:\n{failed_text}",
        )

    def _is_already_exported(self, group: dict) -> bool:
        if str(group.get("lexware_export_status", "")).strip().lower() != "exportiert":
            return False
        export_id = str(group.get("lexware_export_id", "")).strip()
        export_uri = str(group.get("lexware_export_resource_uri", "")).strip()
        return bool(export_id or export_uri)

    def _export_reference_for_group(self, group: dict) -> str:
        export_uri = str(group.get("lexware_export_resource_uri", "")).strip()
        if export_uri:
            return export_uri
        return str(group.get("lexware_export_id", "")).strip()

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
                self._customer_match_text(group),
                group.get("projekt_roh", ""),
                ", ".join(group.get("mitarbeiter_liste", [])),
                self._status_text(group),
                group.get("gruppenstatus", ""),
                self._validation_status_text(group),
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
                return self._customer_match_text(g).lower()
            if column == 5:
                return g.get("projekt_roh", "").lower()
            if column == 6:
                return ", ".join(g.get("mitarbeiter_liste", [])).lower()
            if column == 7:
                order = {"Offen": 0, "Prüfen": 1, "Freigegeben": 2, "Ignorieren": 3, "Prüffall": 4}
                return order.get(self._status_text(g), 99)
            if column == 8:
                order = {"einsatz": 0, "prueffall": 1, "unbekannt": 2}
                return order.get(g.get("gruppenstatus", ""), 99)
            if column == 9:
                text = self._validation_status_text(g).lower()
                if text.startswith("blockiert"):
                    return (0, text)
                if text.startswith("warnung"):
                    return (1, text)
                if text.startswith("info"):
                    return (2, text)
                return (3, text)
            if column == 10:
                return ", ".join(g.get("re_roh_liste", [])).lower()
            if column == 11:
                return g.get("adresse_roh", "").lower()
            if column == 12:
                return g.get("_last_changed_at", "")
            if column == 13:
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
        selected_articles = self._selected_articles_for_group(group)
        if selected_articles:
            article_lines = [self._article_display_text(article) for article in selected_articles]
            article_text = f"{len(selected_articles)} Artikel\n- " + "\n- ".join(article_lines)
        else:
            article_text = self._article_display_text(group.get('selected_article', {})) if group.get('selected_article') else 'Kein Artikel gewählt'

        detail_lines = [
            f"Manueller Status: {group.get('manueller_status', 'offen')}",
            f"Manuelle Notiz: {group.get('manuelle_notiz', '')}",
            f"Artikel: {article_text}",
            f"Fahrtkostenmodus: {group.get('travel_mode', self._default_travel_mode_for_group(group))}",
            f"Fahrtstunden: {group.get('travel_hours', 0.0)}",
            f"Fahrtkilometer: {int(round(float(group.get('travel_km', 0.0) or 0.0)))}",
            f"Routen-Start: {group.get('travel_route_origin', self._mandant_full_address(self.active_mandant_id))}",
            f"Routen-Ziel: {group.get('travel_route_destination', group.get('adresse_roh', ''))}",
            f"Rundtour-Rolle: {group.get('travel_segment_role', '')}",
            f"Fahrtstundensatz: {group.get('travel_hour_rate', 150.0)} EUR",
            f"Fahrt-KM-Satz: {group.get('travel_km_rate', 0.7)} EUR",
            f"Fahrtkosten gesamt: {self._travel_amount_for_group(group)} EUR",
            f"Lexware Exportstatus: {group.get('lexware_export_status', '')}",
            f"Lexware Export-ID: {group.get('lexware_export_id', '')}",
            f"Lexware Resource-URI: {group.get('lexware_export_resource_uri', '')}",
            f"Lexware Exportzeit: {group.get('lexware_exported_at', '')}",
            f"Status: {self._status_text(group)}",
            f"Automatischer Status: {group.get('gruppenstatus', '')}",
            f"Datum: {self._format_date_for_display(group.get('datum', ''))}",
            f"KW: {group.get('kw', '')}",
            f"Kunde: {group.get('kunde_roh', '')}",
            f"Kundenmatch: {self._customer_match_text(group)}",
            f"Zugeordneter Kunde: {group.get('customer_match_name', '')}",
            f"Kundennummer: {group.get('customer_match_number', '')}",
            f"Validierung: {self._validation_status_text(group)}",
            f"Export bereit: {'Ja' if bool(group.get('invoice_export_ready', False)) else 'Nein'}",
            f"Positionen gesamt: {group.get('invoice_positions_count', 0)}",
            f"Projekt: {group.get('projekt_roh', '')}",
            f"Adresse: {group.get('adresse_roh', '')}",
            f"Ansprechpartner: {group.get('ansprechpartner_roh', '')}",
            f"Auftrag: {group.get('auftrag_roh', '')}",
            f"Bemerkungen: {group.get('bemerkungen_roh', '')}",
            f"Mitarbeiter: {', '.join(group.get('mitarbeiter_liste', []))}",
            f"RE: {', '.join(group.get('re_roh_liste', []))}",
            f"Geändert: {group.get('_last_changed_at', '')}",
            "",
            "Rundtour-Segmente:",
        ]

        route_segments = group.get("travel_route_segments", [])
        if isinstance(route_segments, list) and route_segments:
            for segment in route_segments:
                detail_lines.append(f"- {segment}")
        else:
            segment_preview = self._travel_segment_preview_text(group)
            detail_lines.append(f"- {segment_preview}" if segment_preview else "- Keine")

        detail_lines.extend([
            "",
            "Validierungsmeldungen:",
        ])

        validation_messages = group.get("invoice_validation_messages", [])
        if validation_messages:
            for message in validation_messages:
                detail_lines.append(f"- {message}")
        else:
            detail_lines.append("- Keine")

        detail_lines.append("")
        detail_lines.append("Rechnungspositionen:")
        position_lines = group.get("invoice_positions_preview", [])
        if position_lines:
            for line in position_lines:
                detail_lines.append(f"- {line}")
        else:
            detail_lines.append("- Keine Positionen")

        detail_lines.extend([
            "",
            "Klassifikationsgründe:",
        ])

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
            self._customer_match_text(group),
            self._validation_status_text(group),
            " ".join(group.get("invoice_validation_messages", [])),
            group.get("customer_match_name", ""),
            group.get("customer_match_number", ""),
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
            " ".join(group.get("invoice_positions_preview", [])),
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
            selected_articles = group.get("selected_articles", [])
            selected_article_key = group.get("selected_article_key", "")
            selected_article = group.get("selected_article", {})
            travel_mode = group.get("travel_mode", self._default_travel_mode_for_group(group))
            travel_forward_assignment_rule = group.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
            multi_day_allowance_assignment_rule = group.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule())
            travel_values_source = group.get("travel_values_source", "")
            travel_hours = float(group.get("travel_hours", 0.0) or 0.0)
            travel_km = float(group.get("travel_km", 0.0) or 0.0)
            travel_hour_rate = float(group.get("travel_hour_rate", 150.0) or 150.0)
            travel_km_rate = float(group.get("travel_km_rate", 0.7) or 0.7)
            export_status = group.get("lexware_export_status", "")
            export_id = group.get("lexware_export_id", "")
            export_resource_uri = group.get("lexware_export_resource_uri", "")
            exported_at = group.get("lexware_exported_at", "")
            if manual_status != "offen" or manual_note or selected_articles or selected_article_key or selected_article or export_status or export_id or export_resource_uri or exported_at or travel_hours or travel_km:
                manual_data[key] = {
                    "manueller_status": manual_status,
                    "manuelle_notiz": manual_note,
                    "selected_articles": selected_articles,
                    "selected_article_key": selected_article_key,
                    "selected_article": selected_article,
                    "travel_mode": travel_mode,
                    "travel_forward_assignment_rule": travel_forward_assignment_rule,
                    "multi_day_allowance_assignment_rule": multi_day_allowance_assignment_rule,
                    "travel_values_source": travel_values_source,
                    "travel_hours": travel_hours,
                    "travel_km": travel_km,
                    "travel_hour_rate": travel_hour_rate,
                    "travel_km_rate": travel_km_rate,
                    "lexware_export_status": export_status,
                    "lexware_export_id": export_id,
                    "lexware_export_resource_uri": export_resource_uri,
                    "lexware_exported_at": exported_at,
                }

        manual_data["__meta__"] = {
            "customer_article_templates": getattr(self, "customer_article_templates", {}),
        }

        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(manual_data, f, ensure_ascii=False, indent=2)

    def _apply_saved_manual_data(self) -> None:
        data_file = self._get_manual_data_file_path()
        if data_file is None or not data_file.exists():
            return

        with open(data_file, "r", encoding="utf-8") as f:
            manual_data = json.load(f)

        meta_entry = manual_data.get("__meta__", {}) if isinstance(manual_data, dict) else {}
        if isinstance(meta_entry, dict):
            self._set_customer_article_templates(meta_entry.get("customer_article_templates", {}))

        for group in self.groups:
            key = self._build_group_key(group)
            if key in manual_data:
                entry = manual_data[key]
                if isinstance(entry, str):
                    group["manueller_status"] = entry
                    group["manuelle_notiz"] = ""
                    continue

                if not isinstance(entry, dict):
                    continue

                group["manueller_status"] = entry.get("manueller_status", "offen")
                group["manuelle_notiz"] = entry.get("manuelle_notiz", "")
                selected_articles = entry.get("selected_articles", [])
                if isinstance(selected_articles, list) and selected_articles:
                    self._set_selected_articles_for_group(group, selected_articles)
                else:
                    article = entry.get("selected_article", {})
                    if isinstance(article, dict) and article:
                        self._set_selected_articles_for_group(group, [article])
                    else:
                        group["selected_articles"] = []
                        group["selected_article"] = {}
                        group["selected_article_key"] = entry.get("selected_article_key", "")

                group["travel_mode"] = entry.get("travel_mode", self._default_travel_mode_for_group(group))
                group["travel_forward_assignment_rule"] = entry.get("travel_forward_assignment_rule", self._default_travel_forward_assignment_rule())
                group["multi_day_allowance_assignment_rule"] = entry.get("multi_day_allowance_assignment_rule", self._default_multi_day_allowance_assignment_rule())
                group["travel_values_source"] = entry.get("travel_values_source", "")
                group["travel_hours"] = float(entry.get("travel_hours", 0.0) or 0.0)
                group["travel_km"] = float(entry.get("travel_km", 0.0) or 0.0)
                group["travel_hour_rate"] = float(entry.get("travel_hour_rate", 150.0) or 150.0)
                group["travel_km_rate"] = float(entry.get("travel_km_rate", 0.7) or 0.7)
                group["lexware_export_status"] = entry.get("lexware_export_status", "")
                group["lexware_export_id"] = entry.get("lexware_export_id", "")
                group["lexware_export_resource_uri"] = entry.get("lexware_export_resource_uri", "")
                group["lexware_exported_at"] = entry.get("lexware_exported_at", "")

    def _set_customer_article_templates(self, raw_templates) -> None:
        parsed: dict[str, list[dict]] = {}
        if isinstance(raw_templates, dict):
            for mandant_id, templates in raw_templates.items():
                if not isinstance(templates, list):
                    continue
                normalized_templates = []
                for template in templates:
                    if not isinstance(template, dict):
                        continue
                    articles = template.get("articles", [])
                    if not isinstance(articles, list) or not articles:
                        continue
                    normalized_templates.append({
                        "name": str(template.get("name", "") or "").strip() or "Vorlage",
                        "customer_key": str(template.get("customer_key", "") or "").strip(),
                        "customer_label": str(template.get("customer_label", "") or "").strip(),
                        "articles": [dict(article) for article in articles if isinstance(article, dict)],
                    })
                parsed[str(mandant_id)] = normalized_templates
        self.customer_article_templates = parsed

    def on_table_selection_changed(self) -> None:
        selected_groups = self._selected_groups()
        self.summary_selected_label.setText(f"Ausgewählt: {len(selected_groups)}")

        if not selected_groups:
            self.detail_view.clear()
            self.note_edit.clear()
            self._refresh_article_editor_for_group(None)
            self._sync_travel_editor_from_group(None)
            self._update_draft_preview()
            return

        if len(selected_groups) == 1:
            group = selected_groups[0]
            if float(group.get("travel_km", 0.0) or 0.0) <= 0:
                self._calculate_travel_km_for_group(group, show_messages=False)
            self._refresh_article_editor_for_group(group)
            self._sync_travel_editor_from_group(group)
            self.detail_view.setPlainText(self._build_detail_text(group))
            self.note_edit.setPlainText(group.get("manuelle_notiz", ""))
            self._update_draft_preview()
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
        self._refresh_article_editor_for_group(None)
        self._sync_travel_editor_from_group(None)
        self._update_draft_preview()
