import sys
import shlex
import shutil
import json
import threading
import urllib.request
import urllib.error
import webbrowser
import sqlite3
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QTextEdit, QPushButton, QMessageBox, QRadioButton,
    QComboBox, QGroupBox, QFormLayout, QCheckBox, QSizePolicy, QSpacerItem, QSplitter
)

__version__ = "v1.1"
REPO_API_LATEST = "https://api.github.com/repos/Ap4kk/DDNet-Warlist-Editor/releases/latest"
REPO_PAGE = "https://github.com/Ap4kk/DDNet-Warlist-Editor"

# TRANSLATIONS kept identical to original for brevity
TRANSLATIONS = {
    "en": {
        "title": "DDNet Warlist Editor",
        "client": "Client:",
        "path": "File path:",
        "choose_file": "Choose file...",
        "mode": "Mode",
        "single": "Single entry",
        "multi": "Multiple entries",
        "nick": "Nick:",
        "clan": "Clan:",
        "reason": "Reason:",
        "multi_hint": 'Split nicks by spaces. Quotes preserved. Example: "King 1 fps?" AKIrA R6 "papa kar"',
        "multi_reason_label": "Reason for all:",
        "multi_clan_label": "Clan (optional for all):",
        "group": "Group:",
        "backup": "Create backup before write",
        "preview": "Preview",
        "add": "Add",
        "undo": "Undo last backup",
        "check_updates": "Check updates",
        "log_preview": "Log / Preview:",
        "footer_hint": "Hint: close DDNet before writing.",
        "byline": "By Ap4k - Tater/Cactus support",
        "ok": "OK",
        "cancel": "Cancel",
        "error": "Error",
        "confirm_continue": "Make sure DDNet (tclient/cactus) is closed. Continue?",
        "no_file": "File not specified",
        "nothing_to_write": "Nothing to write",
        "done": "Done",
        "update_available": "Update available",
        "update_open_repo": "Open repository?",
        "validation_invalid_nicks": "Invalid nicks found (remove or fix):",
        "validation_skipped_invalid": "Invalid nicks - skipped:",
        "create_backup_failed": "Failed to create backup:",
        "undo_no_backup": "Backup not found - nothing to undo.",
        "undo_file_missing": "File not found, cannot undo.",
        "undo_confirm": "Restore from backup",
        "preview_no_nicks_or_clan": "Multiple nicks empty (or provide a clan).",
        "language": "Language:",
        "theme": "Theme:",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "settings": "Settings"
    },
    "ru": {
        "title": "DDNet Warlist Editor",
        "client": "Клиент:",
        "path": "Путь к файлу:",
        "choose_file": "Выбрать файл...",
        "mode": "Режим",
        "single": "Одиночная запись",
        "multi": "Множественная запись",
        "nick": "Ник:",
        "clan": "Клан:",
        "reason": "Причина:",
        "multi_hint": 'Разделяй ники пробелами. Кавычки сохраняются. Например: "King 1 fps?" AKIrA R6 "papa kar"',
        "multi_reason_label": "Причина для всех:",
        "multi_clan_label": "Клан (опционально для всех):",
        "group": "Группа:",
        "backup": "Создавать резервную копию перед записью",
        "preview": "Предпросмотр",
        "add": "Добавить",
        "undo": "Откат последней резервной копии",
        "check_updates": "Проверить обновления",
        "log_preview": "Лог / Предпросмотр:",
        "footer_hint": "Подсказка: закройте DDNet перед записью.",
        "byline": "By Ap4k - поддержка Tater/Cactus",
        "ok": "OK",
        "cancel": "Отмена",
        "error": "Ошибка",
        "confirm_continue": "Убедитесь, что DDNet (tclient/cactus) закрыт. Продолжить запись?",
        "no_file": "Файл не указан",
        "nothing_to_write": "Нечего записывать",
        "done": "Готово",
        "update_available": "Доступно обновление",
        "update_open_repo": "Открыть репозиторий?",
        "validation_invalid_nicks": "Найдены невалидные ники (удалите или исправьте):",
        "validation_skipped_invalid": "Найдены невалидные ники - они будут пропущены:",
        "create_backup_failed": "Не удалось создать резервную копию:",
        "undo_no_backup": "Резервная копия не найдена - нечего не откатывается.",
        "undo_file_missing": "Файл не найден, невозможно откатить.",
        "undo_confirm": "Восстановить из резервной копии",
        "preview_no_nicks_or_clan": "Поле множественных ников пустое (либо заполните ники, либо укажите клан).",
        "language": "Язык:",
        "theme": "Тема:",
        "theme_dark": "Тёмная",
        "theme_light": "Светлая",
        "settings": "Настройки"
    }
}


def t(key: str, lang: str = "en") -> str:
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


# --- utility functions (kept unchanged) ---

def quote_field(s: str) -> str:
    if s is None:
        s = ""
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{s}"'


def parse_existing_entries(text: str):
    existing = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or not line.startswith('add_war_entry'):
            continue
        try:
            parts = shlex.split(line)
            if len(parts) >= 4 and parts[0] == 'add_war_entry':
                group = parts[1]
                nick = parts[2]
                clan = parts[3]
                existing.add((group, nick.casefold(), clan.casefold()))
        except Exception:
            continue
    return existing


def safe_nick(nick: str) -> bool:
    import unicodedata
    if nick is None:
        return False
    s = nick.strip()
    if not s or len(s) > 64:
        return False
    for ch in s:
        cat = unicodedata.category(ch)
        if cat.startswith('C'):
            return False
    return True


def _parse_version_tag(tag: str):
    if not tag:
        return ()
    tag = str(tag).lstrip('vV')
    parts = tag.split('.')
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except Exception:
            nums.append(0)
    return tuple(nums)


def check_github_latest(timeout=6):
    try:
        req = urllib.request.Request(REPO_API_LATEST, headers={
            'User-Agent': 'DDNet-Warlist-Editor-Updater'
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            data = json.loads(raw.decode('utf-8', errors='replace'))
            tag = data.get('tag_name') or data.get('name')
            url = data.get('html_url') or REPO_PAGE
            body = data.get('body') or ''
            return True, {'tag_name': tag, 'html_url': url, 'body': body}
    except urllib.error.HTTPError as e:
        return False, f'HTTP error: {e.code} {e.reason}'
    except urllib.error.URLError as e:
        return False, f'Network error: {e.reason}'
    except Exception as e:
        return False, f'Unexpected error: {e}'


# --- Redesigned UI ---
class WarlistEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.lang = "ru"
        self.theme = "dark"
        self.setWindowTitle(f'{t("title", self.lang)} - {__version__}')
        self.resize(1100, 750)
        self._last_backup = None
        self._build_ui()
        threading.Thread(target=self._bg_check_update, daemon=True).start()

    def _build_ui(self):
        # top-level layout
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # header area: title + quick actions
        header = QHBoxLayout()
        title = QLabel(t('title', self.lang))
        # slightly smaller title for compactness
        title.setFont(QFont('Segoe UI', 16, QFont.Bold))
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header.addWidget(title)

        ver = QLabel(__version__)
        ver.setToolTip('Version')
        ver.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        ver.setFixedWidth(48)
        header.addWidget(ver)

        # compact settings area: smaller height, stacked compact controls
        settings_box = QWidget()
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(4, 4, 4, 4)
        settings_layout.setSpacing(4)
        settings_box.setLayout(settings_layout)
        settings_box.setFixedHeight(56)

        # top row: small labels for context (optional)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.addStretch()
        settings_layout.addLayout(top_row)

        # bottom row: compact combos aligned to the right
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(6)

        lbl_lang = QLabel(t('language', self.lang))
        lbl_lang.setFixedHeight(20)
        bottom_row.addWidget(lbl_lang)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Русский", "English"])
        self.lang_combo.setCurrentIndex(0 if self.lang == 'ru' else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        self.lang_combo.setFixedWidth(120)
        self.lang_combo.setFixedHeight(24)
        bottom_row.addWidget(self.lang_combo)

        lbl_theme = QLabel(t('theme', self.lang))
        lbl_theme.setFixedHeight(20)
        bottom_row.addWidget(lbl_theme)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([t('theme_dark', self.lang), t('theme_light', self.lang)])
        self.theme_combo.setCurrentIndex(0 if self.theme == 'dark' else 1)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.theme_combo.setFixedWidth(120)
        self.theme_combo.setFixedHeight(24)
        bottom_row.addWidget(self.theme_combo)

        bottom_row.addStretch()
        settings_layout.addLayout(bottom_row)

        # give settings a compact visual separation
        header.addWidget(settings_box)

        root.addLayout(header)

        # central area: left form, right log/preview split
        splitter = QSplitter(Qt.Horizontal)

        # left panel - compact form
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(10)

        # file / client row
        file_group = QGroupBox()
        file_layout = QHBoxLayout()
        file_layout.setContentsMargins(6, 6, 6, 6)
        file_layout.setSpacing(8)

        self.lbl_client = QLabel(t('client', self.lang))
        file_layout.addWidget(self.lbl_client)
        self.client_combo = QComboBox()
        self.client_combo.addItems(['Tater Client', 'Cactus Client'])
        self.client_combo.currentIndexChanged.connect(self._on_client_changed)
        file_layout.addWidget(self.client_combo)

        file_layout.addStretch()
        self.lbl_path = QLabel(t('path', self.lang))
        file_layout.addWidget(self.lbl_path)
        self.path_edit = QLineEdit()
        self._set_path_placeholder()
        file_layout.addWidget(self.path_edit, stretch=2)
        self.browse_btn = QPushButton(t('choose_file', self.lang))
        self.browse_btn.clicked.connect(self.browse_file)
        self.browse_btn.setFixedHeight(28)
        file_layout.addWidget(self.browse_btn)
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group)

        # mode selection
        mode_box = QGroupBox(t('mode', self.lang))
        mode_layout = QHBoxLayout()
        self.single_radio = QRadioButton(t('single', self.lang))
        self.multi_radio = QRadioButton(t('multi', self.lang))
        self.single_radio.setChecked(True)
        self.single_radio.toggled.connect(self._update_mode)
        mode_layout.addWidget(self.single_radio)
        mode_layout.addWidget(self.multi_radio)
        mode_layout.addStretch()
        mode_box.setLayout(mode_layout)
        left_layout.addWidget(mode_box)

        # stacked-like area: single / multi
        # single
        single_box = QGroupBox(t('single', self.lang))
        single_form = QFormLayout()
        self.single_nick = QLineEdit()
        self.single_nick.setPlaceholderText(t('nick', self.lang) + ' (например: Player123)')
        self.single_clan = QLineEdit()
        self.single_clan.setPlaceholderText(t('clan', self.lang))
        self.single_reason = QLineEdit()
        self.single_reason.setPlaceholderText(t('reason', self.lang))
        single_form.addRow(QLabel(t('nick', self.lang)), self.single_nick)
        single_form.addRow(QLabel(t('clan', self.lang)), self.single_clan)
        single_form.addRow(QLabel(t('reason', self.lang)), self.single_reason)
        single_box.setLayout(single_form)
        left_layout.addWidget(single_box)

        # multi
        multi_box = QGroupBox(t('multi', self.lang))
        multi_v = QVBoxLayout()
        multi_top = QHBoxLayout()
        self.multi_text = QPlainTextEdit()
        self.multi_text.setPlaceholderText(t('multi_hint', self.lang))
        self.multi_text.setFixedHeight(110)
        self.multi_text.textChanged.connect(self._on_multi_text_changed)
        multi_top.addWidget(self.multi_text, stretch=3)

        right_col = QVBoxLayout()
        self.multi_reason = QLineEdit()
        self.multi_reason.setPlaceholderText(t('reason', self.lang))
        right_col.addWidget(QLabel(t('multi_reason_label', self.lang)))
        right_col.addWidget(self.multi_reason)
        right_col.addSpacing(6)
        right_col.addWidget(QLabel(t('multi_clan_label', self.lang)))
        self.multi_clan = QLineEdit()
        self.multi_clan.setPlaceholderText(t('multi_clan_label', self.lang))
        self.multi_clan.textChanged.connect(self._on_multi_clan_changed)
        right_col.addWidget(self.multi_clan)
        right_col.addStretch()
        multi_top.addLayout(right_col, stretch=1)

        multi_v.addLayout(multi_top)
        multi_box.setLayout(multi_v)
        left_layout.addWidget(multi_box)

        # options + buttons row
        opts = QHBoxLayout()
        self.lbl_group = QLabel(t('group', self.lang))
        opts.addWidget(self.lbl_group)
        self.group_box = QComboBox()
        self.group_box.addItems(['enemy', 'team'])
        opts.addWidget(self.group_box)
        self.backup_checkbox = QCheckBox(t('backup', self.lang))
        self.backup_checkbox.setChecked(True)
        opts.addWidget(self.backup_checkbox)
        opts.addStretch()

        # action buttons with larger sizes
        self.preview_btn = QPushButton(t('preview', self.lang))
        self.preview_btn.clicked.connect(self.preview)
        self.preview_btn.setFixedHeight(34)
        self.add_btn = QPushButton(t('add', self.lang))
        self.add_btn.clicked.connect(self.add_to_file)
        self.add_btn.setFixedHeight(34)
        self.undo_btn = QPushButton(t('undo', self.lang))
        self.undo_btn.clicked.connect(self.undo_last)
        self.update_btn = QPushButton(t('check_updates', self.lang))
        self.update_btn.clicked.connect(lambda: threading.Thread(target=self._check_update_and_notify, daemon=True).start())

        opts.addWidget(self.preview_btn)
        opts.addWidget(self.add_btn)
        opts.addWidget(self.undo_btn)
        opts.addWidget(self.update_btn)
        left_layout.addLayout(opts)

        left_layout.addStretch()
        left_widget.setLayout(left_layout)

        # right panel - log / preview
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(6, 6, 6, 6)
        right_layout.setSpacing(8)
        self.lbl_log = QLabel(t('log_preview', self.lang))
        right_layout.addWidget(self.lbl_log)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QTextEdit.NoWrap)
        right_layout.addWidget(self.log)

        # footer hint at bottom of right panel
        footer = QHBoxLayout()
        self.watermark = QLabel(t('byline', self.lang))
        footer.addWidget(self.watermark)
        footer.addStretch()
        self.help_label = QLabel(t('footer_hint', self.lang))
        footer.addWidget(self.help_label)
        right_layout.addLayout(footer)

        right_widget.setLayout(right_layout)

        # put widgets into splitter
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 640])

        root.addWidget(splitter)

        # keyboard shortcuts for power users
        QShortcut(QKeySequence('Ctrl+P'), self, activated=self.preview)
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.add_to_file)
        QShortcut(QKeySequence('Ctrl+Z'), self, activated=self.undo_last)

        self._update_mode()
        self._on_client_changed()
        self.apply_theme()

    # --- keep existing helper methods mostly unchanged ---
    def _set_path_placeholder(self):
        if self._is_cactus():
            self.path_edit.setPlaceholderText(str(Path.home() / "AppData" / "Roaming" / "DDNet" / "cactus.sqlite3"))
        else:
            self.path_edit.setPlaceholderText(
                str(Path.home() / "AppData" / "Roaming" / "DDNet" / "tclient_warlist.cfg"))

    def _on_client_changed(self, _=None):
        is_cactus = self._is_cactus()
        self.single_clan.setEnabled(not is_cactus)
        self._apply_multi_mutual_exclusion()
        self._set_path_placeholder()

    def _is_cactus(self) -> bool:
        return self.client_combo.currentText().lower().startswith('cactus')

    def _update_mode(self):
        single = self.single_radio.isChecked()
        self.single_nick.setEnabled(single)
        self.single_reason.setEnabled(single)
        self.single_clan.setEnabled(single and not self._is_cactus())
        self.multi_text.setEnabled(not single)
        self.multi_reason.setEnabled(not single)
        self._apply_multi_mutual_exclusion()

    def _apply_multi_mutual_exclusion(self):
        if self._is_cactus() or self.single_radio.isChecked():
            self.multi_clan.setEnabled(False)
            if not self.single_radio.isChecked():
                self.multi_text.setEnabled(True)
            return

        multi_has = bool(self.multi_text.toPlainText().strip())
        clan_has = bool(self.multi_clan.text().strip())

        if multi_has and not clan_has:
            self.multi_clan.setEnabled(False)
            self.multi_text.setEnabled(True)
        elif clan_has and not multi_has:
            self.multi_text.setEnabled(False)
            self.multi_clan.setEnabled(True)
        elif (not multi_has) and (not clan_has):
            self.multi_text.setEnabled(True)
            self.multi_clan.setEnabled(True)
        else:
            self.multi_text.setEnabled(True)
            self.multi_clan.setEnabled(False)

    def _on_multi_text_changed(self):
        if self._is_cactus() or self.single_radio.isChecked():
            return
        self._apply_multi_mutual_exclusion()

    def _on_multi_clan_changed(self):
        if self._is_cactus() or self.single_radio.isChecked():
            return
        self._apply_multi_mutual_exclusion()

    def browse_file(self):
        if self._is_cactus():
            start = str(Path.home() / "AppData" / "Roaming" / "DDNet")
            path, _ = QFileDialog.getOpenFileName(self, t('choose_file', self.lang), start,
                                                  "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*)")
        else:
            start = str(Path.home() / "AppData" / "Roaming" / "DDNet")
            path, _ = QFileDialog.getOpenFileName(self, t('choose_file', self.lang), start,
                                                  "Config Files (*.cfg *.txt);;All Files (*)")
        if path:
            self.path_edit.setText(path)

    def _gather_entries(self):
        group = self.group_box.currentText()
        entries = []
        if self.single_radio.isChecked():
            nick = self.single_nick.text().strip()
            clan = self.single_clan.text().strip() if not self._is_cactus() else ''
            reason = self.single_reason.text().strip()
            if not nick and not clan:
                raise ValueError(t('preview_no_nicks_or_clan', self.lang))
            entries.append((nick, clan, reason))
        else:
            raw = self.multi_text.toPlainText().strip()
            if not raw and not (self.multi_clan.text().strip() and not self._is_cactus()):
                raise ValueError(t('preview_no_nicks_or_clan', self.lang))
            parsed = []
            if raw:
                try:
                    parsed = shlex.split(raw)
                except Exception as e:
                    raise ValueError(f'Failed to parse nicks: {e}')
            reason_all = self.multi_reason.text().strip()
            clan_all = ''
            if not self._is_cactus() and self.multi_clan.isEnabled():
                clan_all = self.multi_clan.text().strip()
            if not parsed:
                entries.append(('', clan_all, reason_all))
            else:
                seen = set()
                for token in parsed:
                    key = token.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append((token, clan_all, reason_all))
        return group, entries

    def _format_lines(self, group: str, entries):
        lines = []
        if self._is_cactus():
            state_map = {'enemy': 1, 'team': 3}
            st = state_map.get(group, 1)
            for nick, clan, reason in entries:
                nick_q = quote_field(nick)
                reason_q = quote_field(reason)
                lines.append(f'INSERT INTO wars (name, state, reason) VALUES ({nick_q}, {st}, {reason_q});')
        else:
            for nick, clan, reason in entries:
                nick_q = quote_field(nick)
                clan_q = quote_field(clan)
                reason_q = quote_field(reason)
                line = f'add_war_entry {quote_field(group)} {nick_q} {clan_q} {reason_q}'
                lines.append(line)
        return lines

    def preview(self):
        try:
            group, entries = self._gather_entries()
        except Exception as e:
            QMessageBox.critical(self, t('error', self.lang), str(e))
            return

        invalid = [n for n, c, r in entries if n and not safe_nick(n)]
        if invalid:
            QMessageBox.warning(self, t('error', self.lang),
                                t('validation_invalid_nicks', self.lang) + "\n" + "\n".join(invalid))

        lines = self._format_lines(group, entries)
        path_text = self.path_edit.text().strip()
        dup_info = []
        if path_text:
            p = Path(path_text)
            if p.exists():
                try:
                    if self._is_cactus():
                        conn = sqlite3.connect(str(p))
                        cur = conn.cursor()
                        state_map = {'enemy': 1, 'team': 3}
                        st = state_map.get(group, 1)
                        for nick, clan, reason in entries:
                            cur.execute("SELECT COUNT(1) FROM sqlite_master WHERE type='table' AND name='wars'")
                            if cur.fetchone()[0] == 0:
                                continue
                            cur.execute("SELECT 1 FROM wars WHERE lower(name)=? AND state=?", (nick.casefold(), st))
                            if cur.fetchone():
                                dup_info.append(f'ПРОПУСК (дубликат): {nick}')
                        conn.close()
                    else:
                        existing = parse_existing_entries(p.read_text(encoding='utf-8', errors='replace'))
                        for ln, (nick, clan, reason) in zip(lines, entries):
                            cmp = (group, nick.casefold(), clan.casefold())
                            if cmp in existing:
                                dup_info.append(f'ПРОПУСК (дубликат): {nick} ({clan})')
                except Exception:
                    pass

        self.log.clear()
        self.log.append('\n'.join(lines))
        if dup_info:
            self.log.append('\n-- Дубликаты (не будут записаны):')
            self.log.append('\n'.join(dup_info))

    def create_backup(self, path: Path) -> Path:
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            bak_name = f"{path.name}.bak_{ts}"
            bak_path = path.with_name(bak_name)
            shutil.copy2(path, bak_path)
            meta = path.with_name(path.name + '.last_backup')
            meta.write_text(str(bak_path), encoding='utf-8')
            self._last_backup = bak_path
            return bak_path
        except Exception as e:
            raise RuntimeError(f'{t("create_backup_failed", self.lang)} {e}')

    def _read_last_backup_meta(self, path: Path):
        meta = path.with_name(path.name + '.last_backup')
        if meta.exists():
            try:
                p = Path(meta.read_text(encoding='utf-8').strip())
                if p.exists():
                    return p
            except Exception:
                return None
        return None

    def undo_last(self):
        file_path = Path(self.path_edit.text().strip())
        if not file_path.exists():
            QMessageBox.warning(self, t('error', self.lang), t('undo_file_missing', self.lang))
            return
        bak = self._read_last_backup_meta(file_path) or getattr(self, '_last_backup', None)
        if not bak or not Path(bak).exists():
            QMessageBox.information(self, t('undo', self.lang), t('undo_no_backup', self.lang))
            return
        msg = f"{t('undo_confirm', self.lang)}?\n{bak}"
        reply = QMessageBox.question(self, t('undo', self.lang), msg,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy2(bak, file_path)
            self.log.append(f'Откат выполнен: {bak} -> {file_path}')
            QMessageBox.information(self, t('done', self.lang), t('done', self.lang))
        except Exception as e:
            QMessageBox.critical(self, t('error', self.lang), str(e))

    def add_to_file(self):
        reply = QMessageBox.question(self, t('confirm_continue', self.lang), t('confirm_continue', self.lang),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        file_path_text = self.path_edit.text().strip()
        if not file_path_text:
            QMessageBox.warning(self, t('error', self.lang), t('no_file', self.lang))
            return
        file_path = Path(file_path_text)

        try:
            group, entries = self._gather_entries()
        except Exception as e:
            QMessageBox.critical(self, t('error', self.lang), str(e))
            return

        valid_entries = []
        invalid = []
        for nick, clan, reason in entries:
            if nick and not safe_nick(nick):
                invalid.append(nick)
            else:
                valid_entries.append((nick, clan, reason))
        if invalid:
            QMessageBox.warning(self, t('error', self.lang),
                                t('validation_skipped_invalid', self.lang) + "\n" + "\n".join(invalid))

        if not valid_entries:
            QMessageBox.information(self, t('nothing_to_write', self.lang), t('nothing_to_write', self.lang))
            return

        if not self._is_cactus():
            existing = set()
            try:
                if file_path.exists():
                    existing = parse_existing_entries(file_path.read_text(encoding='utf-8', errors='replace'))
            except Exception:
                existing = set()

            to_write = []
            skipped = []
            for nick, clan, reason in valid_entries:
                key = (self.group_box.currentText(), nick.casefold(), clan.casefold())
                if key in existing:
                    skipped.append((nick, clan))
                else:
                    to_write.append((nick, clan, reason))

            if not to_write:
                QMessageBox.information(self, t('nothing_to_write', self.lang), t('nothing_to_write', self.lang))
                self.log.append('Новые записи не найдены - ничего не записано.')
                return

            lines = self._format_lines(self.group_box.currentText(), to_write)

            try:
                if self.backup_checkbox.isChecked() and file_path.exists():
                    bak = self.create_backup(file_path)
                    self.log.append(f'Резервная копия создана: {bak}')

                with file_path.open('a', encoding='utf-8', errors='replace') as f:
                    for ln in lines:
                        f.write(ln + '\n')

                msg = f"{t('done', self.lang)}: {len(lines)} записей добавлено."
                if skipped:
                    msg += f" Пропущено дубликатов: {len(skipped)}."

                    self.log.append('\n-- Пропущенные дубликаты:')
                    for nick, clan in skipped:
                        self.log.append(f'{nick} ({clan})')

                self.log.append(f'Записано {len(lines)} строк в {file_path}')
                QMessageBox.information(self, t('done', self.lang), msg)
            except Exception as e:
                QMessageBox.critical(self, t('error', self.lang), str(e))

        else:
            try:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                db_exists = file_path.exists()
                if not db_exists:
                    conn = sqlite3.connect(str(file_path))
                    cur = conn.cursor()
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS wars (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, state INTEGER, reason TEXT)")
                    conn.commit()
                    conn.close()

                if self.backup_checkbox.isChecked() and file_path.exists():
                    bak = self.create_backup(file_path)
                    self.log.append(f'Резервная копия создана: {bak}')

                conn = sqlite3.connect(str(file_path))
                cur = conn.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS wars (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, state INTEGER, reason TEXT)")
                state_map = {'enemy': 1, 'team': 3}
                st = state_map.get(self.group_box.currentText(), 1)

                inserted = 0
                skipped = 0
                for nick, clan, reason in valid_entries:
                    if not nick:
                        continue
                    cur.execute("SELECT 1 FROM wars WHERE lower(name)=? AND state=?", (nick.casefold(), st))
                    if cur.fetchone():
                        skipped += 1
                        continue
                    cur.execute("INSERT INTO wars (name, state, reason) VALUES (?, ?, ?)", (nick, st, reason or ''))
                    inserted += 1

                conn.commit()
                conn.close()

                msg = f"{t('done', self.lang)}: добавлено {inserted}. Пропущено дубликатов: {skipped}."
                self.log.append(msg)
                QMessageBox.information(self, t('done', self.lang), msg)
            except Exception as e:
                QMessageBox.critical(self, t('error', self.lang), str(e))

    def _bg_check_update(self):
        success, data = check_github_latest()
        if success:
            tag = data.get('tag_name')
            if tag:
                latest = _parse_version_tag(tag)
                current = _parse_version_tag(__version__)
                if latest and latest > current:
                    self.log.append(f'Новая версия: {tag} - откройте репозиторий для обновления: {REPO_PAGE}')
                else:
                    self.log.append('Проверка обновлений: у вас последняя версия.')
        else:
            self.log.append(f'Проверка обновлений не удалась: {data}')

    def _check_update_and_notify(self):
        success, data = check_github_latest()
        if not success:
            QMessageBox.information(self, t('check_updates', self.lang), f'Не удалось проверить обновления:\n{data}')
            return
        tag = data.get('tag_name')
        url = data.get('html_url') or REPO_PAGE
        if tag:
            latest = _parse_version_tag(tag)
            current = _parse_version_tag(__version__)
            if latest and latest > current:
                resp = QMessageBox.question(
                    self,
                    t('update_available', self.lang),
                    f"{t('update_available', self.lang)} {tag} (текущая: {__version__}). {t('update_open_repo', self.lang)}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if resp == QMessageBox.StandardButton.Yes:
                    webbrowser.open(url)
            else:
                QMessageBox.information(self, t('check_updates', self.lang), 'У вас последняя версия.')
        else:
            QMessageBox.information(self, t('check_updates', self.lang), 'Не удалось получить информацию о релизе.')

    def apply_theme(self):
        # modernized stylesheet with an accent color and consistent paddings
        accent = '#0078d4'
        if self.theme == 'dark':
            stylesheet = f"""
            QWidget {{ background: #0f1113; color: #e6eef8; font-family: 'Segoe UI', Arial; font-size: 10pt; }}
            QGroupBox {{ background: #151719; border: 1px solid #232629; border-radius: 8px; margin-top: 6px; padding: 8px; font-weight: 600; }}
            QLabel {{ color: #e6eef8 }}
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{ background: #0f1316; border: 1px solid #2b3134; color: #e6eef8; padding: 6px; border-radius: 6px; selection-background-color: {accent}; }}
            QPushButton {{ background: #1b1f22; color: #e6eef8; border: 1px solid #2b3134; padding: 8px 14px; border-radius: 8px; font-weight: 700; }}
            QPushButton:hover {{ background: #22272a }}
            QPushButton:pressed {{ background: #121415 }}
            QComboBox::drop-down {{ border: none }}
            QScrollBar:vertical {{ background: transparent; width: 10px }}
            QScrollBar::handle:vertical {{ background: #2b3134; border-radius: 5px; min-height: 20px }}
            """
        else:
            stylesheet = f"""
            QWidget {{ background: #fbfdff; color: #1a1a1a; font-family: 'Segoe UI', Arial; font-size: 10pt; }}
            QGroupBox {{ background: #ffffff; border: 1px solid #e6ebf0; border-radius: 8px; margin-top: 6px; padding: 8px; font-weight: 600; }}
            QLabel {{ color: #1a1a1a }}
            QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{ background: #ffffff; border: 1px solid #dfe7ee; color: #1a1a1a; padding: 6px; border-radius: 6px; selection-background-color: {accent}; }}
            QPushButton {{ background: #f0f4f8; color: #1a1a1a; border: 1px solid #dfe7ee; padding: 8px 14px; border-radius: 8px; font-weight: 700; }}
            QPushButton:hover {{ background: #e9f1fb }}
            QPushButton:pressed {{ background: #dfeaf7 }}
            QComboBox::drop-down {{ border: none }}
            QScrollBar:vertical {{ background: transparent; width: 10px }}
            QScrollBar::handle:vertical {{ background: #cfdbe6; border-radius: 5px; min-height: 20px }}
            """
        self.setStyleSheet(stylesheet)

    def _on_theme_changed(self, idx):
        self.theme = 'dark' if idx == 0 else 'light'
        self.apply_theme()

    def _on_language_changed(self, idx):
        self.lang = 'ru' if idx == 0 else 'en'
        self._retranslate_ui()

    def _retranslate_ui(self):
        # minimal retranslation - keep layout but update labels
        self.setWindowTitle(f"{t('title', self.lang)} - {__version__}")
        self.lbl_client.setText(t('client', self.lang))
        self.lbl_path.setText(t('path', self.lang))
        self.browse_btn.setText(t('choose_file', self.lang))
        self.mode_group = t('mode', self.lang)
        self.single_radio.setText(t('single', self.lang))
        self.multi_radio.setText(t('multi', self.lang))
        self.single_nick.setPlaceholderText(t('nick', self.lang) + (' (например: Player123)' if self.lang == 'ru' else ' (e.g. Player123)'))
        self.single_clan.setPlaceholderText(t('clan', self.lang))
        self.single_reason.setPlaceholderText(t('reason', self.lang))
        self.multi_text.setPlaceholderText(t('multi_hint', self.lang))
        self.multi_reason.setPlaceholderText(t('reason', self.lang))
        self.multi_clan.setPlaceholderText(t('multi_clan_label', self.lang))
        self.lbl_group.setText(t('group', self.lang))
        self.backup_checkbox.setText(t('backup', self.lang))
        self.preview_btn.setText(t('preview', self.lang))
        self.add_btn.setText(t('add', self.lang))
        self.undo_btn.setText(t('undo', self.lang))
        self.update_btn.setText(t('check_updates', self.lang))
        self.lbl_log.setText(t('log_preview', self.lang))
        self.help_label.setText(t('footer_hint', self.lang))
        self.watermark.setText(t('byline', self.lang))
        self.theme_combo.setItemText(0, t('theme_dark', self.lang))
        self.theme_combo.setItemText(1, t('theme_light', self.lang))
        self._set_path_placeholder()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = WarlistEditor()
    w.show()
    sys.exit(app.exec())
