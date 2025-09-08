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
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox, QRadioButton,
    QComboBox, QGroupBox, QFormLayout, QCheckBox, QSizePolicy, QSpacerItem
)

__version__ = "v1.1"
REPO_API_LATEST = "https://api.github.com/repos/Ap4kk/DDNet-Warlist-Editor/releases/latest"
REPO_PAGE = "https://github.com/Ap4kk/DDNet-Warlist-Editor"

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


class WarlistEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.lang = "ru"
        self.theme = "dark"
        self.setWindowTitle(f'{t("title", self.lang)} - {__version__}')
        self.resize(1100, 800)
        self._build_ui()
        threading.Thread(target=self._bg_check_update, daemon=True).start()

    def _build_ui(self):
        self.setStyleSheet("")
        main_layout = QVBoxLayout()

        header = QHBoxLayout()
        self.title_label = QLabel(t("title", self.lang))
        self.title_label.setFont(QFont('Segoe UI', 16, QFont.Bold))
        header.addWidget(self.title_label)
        header.addStretch()

        self.version_label = QLabel(f"{__version__}")
        header.addWidget(self.version_label)

        settings_group = QGroupBox(t("settings", self.lang))
        settings_layout = QHBoxLayout()

        settings_layout.addWidget(QLabel(t("language", self.lang)))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Русский", "English"])
        self.lang_combo.setCurrentIndex(0 if self.lang == "ru" else 1)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        settings_layout.addWidget(self.lang_combo)

        settings_layout.addSpacing(10)
        settings_layout.addWidget(QLabel(t("theme", self.lang)))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems([t("theme_dark", self.lang), t("theme_light", self.lang)])
        self.theme_combo.setCurrentIndex(0 if self.theme == "dark" else 1)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        settings_layout.addWidget(self.theme_combo)
        settings_layout.addStretch()

        settings_group.setLayout(settings_layout)

        main_layout.addLayout(header)
        main_layout.addWidget(settings_group)

        top_group = QGroupBox()
        top_group_layout = QHBoxLayout()
        self.lbl_client = QLabel(t("client", self.lang))
        top_group_layout.addWidget(self.lbl_client)
        self.client_combo = QComboBox()
        self.client_combo.addItems(['Tater Client', 'Cactus Client'])
        self.client_combo.currentIndexChanged.connect(self._on_client_changed)
        top_group_layout.addWidget(self.client_combo)

        top_group_layout.addSpacing(8)
        self.lbl_path = QLabel(t("path", self.lang))
        top_group_layout.addWidget(self.lbl_path)
        self.path_edit = QLineEdit()
        self._set_path_placeholder()
        top_group_layout.addWidget(self.path_edit, stretch=2)

        self.browse_btn = QPushButton(t("choose_file", self.lang))
        self.browse_btn.clicked.connect(self.browse_file)
        top_group_layout.addWidget(self.browse_btn)
        top_group.setLayout(top_group_layout)
        main_layout.addWidget(top_group)

        self.mode_group_box = QGroupBox(t("mode", self.lang))
        mode_layout = QHBoxLayout()
        self.single_radio = QRadioButton(t("single", self.lang))
        self.multi_radio = QRadioButton(t("multi", self.lang))
        self.single_radio.setChecked(True)
        self.single_radio.toggled.connect(self._update_mode)
        mode_layout.addWidget(self.single_radio)
        mode_layout.addWidget(self.multi_radio)
        mode_layout.addStretch()
        self.mode_group_box.setLayout(mode_layout)
        main_layout.addWidget(self.mode_group_box)

        self.single_box = QGroupBox(t("single", self.lang))
        single_form = QFormLayout()
        self.single_nick = QLineEdit()
        self.single_nick.setPlaceholderText(t("nick", self.lang) + " (например: Player123)")
        self.single_clan = QLineEdit()
        self.single_clan.setPlaceholderText(t("clan", self.lang))
        self.single_reason = QLineEdit()
        self.single_reason.setPlaceholderText(t("reason", self.lang))
        self.lbl_single_nick = QLabel(t("nick", self.lang))
        self.lbl_single_clan = QLabel(t("clan", self.lang))
        self.lbl_single_reason = QLabel(t("reason", self.lang))
        single_form.addRow(self.lbl_single_nick, self.single_nick)
        single_form.addRow(self.lbl_single_clan, self.single_clan)
        single_form.addRow(self.lbl_single_reason, self.single_reason)
        self.single_box.setLayout(single_form)
        main_layout.addWidget(self.single_box)

        self.multi_box = QGroupBox(t("multi", self.lang))
        multi_layout = QVBoxLayout()
        multi_top = QHBoxLayout()
        self.multi_text = QTextEdit()
        self.multi_text.setFixedHeight(120)
        self.multi_text.setPlaceholderText(t("multi_hint", self.lang))
        self.multi_text.textChanged.connect(self._on_multi_text_changed)
        multi_top.addWidget(self.multi_text, stretch=3)

        right_col = QVBoxLayout()
        self.multi_reason = QLineEdit()
        self.multi_reason.setPlaceholderText(t("reason", self.lang))
        self.lbl_multi_reason = QLabel(t("multi_reason_label", self.lang))
        right_col.addWidget(self.lbl_multi_reason)
        right_col.addWidget(self.multi_reason)
        right_col.addSpacing(6)
        self.lbl_multi_clan = QLabel(t("multi_clan_label", self.lang))
        right_col.addWidget(self.lbl_multi_clan)
        self.multi_clan = QLineEdit()
        self.multi_clan.setPlaceholderText(t("multi_clan_label", self.lang))
        self.multi_clan.textChanged.connect(self._on_multi_clan_changed)
        right_col.addWidget(self.multi_clan)
        right_col.addStretch()
        multi_top.addLayout(right_col, stretch=1)

        multi_layout.addLayout(multi_top)
        self.multi_box.setLayout(multi_layout)
        main_layout.addWidget(self.multi_box)

        opts_box = QGroupBox()
        opts_layout = QHBoxLayout()
        self.lbl_group = QLabel(t("group", self.lang))
        opts_layout.addWidget(self.lbl_group)
        self.group_box = QComboBox()
        self.group_box.addItems(['enemy', 'team'])
        opts_layout.addWidget(self.group_box)
        self.backup_checkbox = QCheckBox(t("backup", self.lang))
        self.backup_checkbox.setChecked(True)
        opts_layout.addWidget(self.backup_checkbox)
        opts_layout.addStretch()
        opts_box.setLayout(opts_layout)
        main_layout.addWidget(opts_box)

        btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton(t("preview", self.lang))
        self.preview_btn.clicked.connect(self.preview)
        self.add_btn = QPushButton(t("add", self.lang))
        self.add_btn.clicked.connect(self.add_to_file)
        self.undo_btn = QPushButton(t("undo", self.lang))
        self.undo_btn.clicked.connect(self.undo_last)
        self.update_btn = QPushButton(t("check_updates", self.lang))
        self.update_btn.clicked.connect(
            lambda: threading.Thread(target=self._check_update_and_notify, daemon=True).start())

        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.undo_btn)
        btn_layout.addWidget(self.update_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        self.lbl_log = QLabel(t("log_preview", self.lang))
        main_layout.addWidget(self.lbl_log)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(220)
        main_layout.addWidget(self.log)

        footer = QHBoxLayout()
        self.watermark = QLabel(t("byline", self.lang))
        footer.addWidget(self.watermark)
        footer.addStretch()
        self.help_label = QLabel(t("footer_hint", self.lang))
        footer.addWidget(self.help_label)
        main_layout.addLayout(footer)

        self.setLayout(main_layout)

        self._update_mode()
        self._on_client_changed()
        self.apply_theme()

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
            path, _ = QFileDialog.getOpenFileName(self, t("choose_file", self.lang), start,
                                                  "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*)")
        else:
            start = str(Path.home() / "AppData" / "Roaming" / "DDNet")
            path, _ = QFileDialog.getOpenFileName(self, t("choose_file", self.lang), start,
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
                raise ValueError(t("preview_no_nicks_or_clan", self.lang))
            entries.append((nick, clan, reason))
        else:
            raw = self.multi_text.toPlainText().strip()
            if not raw and not (self.multi_clan.text().strip() and not self._is_cactus()):
                raise ValueError(t("preview_no_nicks_or_clan", self.lang))
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
            QMessageBox.critical(self, t("error", self.lang), str(e))
            return

        invalid = [n for n, c, r in entries if n and not safe_nick(n)]
        if invalid:
            QMessageBox.warning(self, t("error", self.lang),
                                t("validation_invalid_nicks", self.lang) + "\n" + "\n".join(invalid))

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
            QMessageBox.warning(self, t("error", self.lang), t("undo_file_missing", self.lang))
            return
        bak = self._read_last_backup_meta(file_path) or getattr(self, '_last_backup', None)
        if not bak or not Path(bak).exists():
            QMessageBox.information(self, t("undo", self.lang), t("undo_no_backup", self.lang))
            return
        reply = QMessageBox.question(self, t("undo", self.lang), f'{t("undo_confirm", self.lang)}?\n{bak}',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy2(bak, file_path)
            self.log.append(f'Откат выполнен: {bak} -> {file_path}')
            QMessageBox.information(self, t("done", self.lang), t("done", self.lang))
        except Exception as e:
            QMessageBox.critical(self, t("error", self.lang), str(e))

    def add_to_file(self):
        reply = QMessageBox.question(self, t("confirm_continue", self.lang), t("confirm_continue", self.lang),
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        file_path_text = self.path_edit.text().strip()
        if not file_path_text:
            QMessageBox.warning(self, t("error", self.lang), t("no_file", self.lang))
            return
        file_path = Path(file_path_text)

        try:
            group, entries = self._gather_entries()
        except Exception as e:
            QMessageBox.critical(self, t("error", self.lang), str(e))
            return

        valid_entries = []
        invalid = []
        for nick, clan, reason in entries:
            if nick and not safe_nick(nick):
                invalid.append(nick)
            else:
                valid_entries.append((nick, clan, reason))
        if invalid:
            QMessageBox.warning(self, t("error", self.lang),
                                t("validation_skipped_invalid", self.lang) + "\n" + "\n".join(invalid))

        if not valid_entries:
            QMessageBox.information(self, t("nothing_to_write", self.lang), t("nothing_to_write", self.lang))
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
                key = (group, nick.casefold(), clan.casefold())
                if key in existing:
                    skipped.append((nick, clan))
                else:
                    to_write.append((nick, clan, reason))

            if not to_write:
                QMessageBox.information(self, t("nothing_to_write", self.lang), t("nothing_to_write", self.lang))
                self.log.append('Новые записи не найдены - ничего не записано.')
                return

            lines = self._format_lines(group, to_write)

            try:
                if self.backup_checkbox.isChecked() and file_path.exists():
                    bak = self.create_backup(file_path)
                    self.log.append(f'Резервная копия создана: {bak}')

                with file_path.open('a', encoding='utf-8', errors='replace') as f:
                    for ln in lines:
                        f.write(ln + '\n')

                msg = f'{t("done", self.lang)}: {len(lines)} записей добавлено.'
                if skipped:
                    msg += f' Пропущено дубликатов: {len(skipped)}.'
                    self.log.append('\n-- Пропущенные дубликаты:')
                    for nick, clan in skipped:
                        self.log.append(f'{nick} ({clan})')

                self.log.append(f'Записано {len(lines)} строк в {file_path}')
                QMessageBox.information(self, t("done", self.lang), msg)
            except Exception as e:
                QMessageBox.critical(self, t("error", self.lang), str(e))

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
                st = state_map.get(group, 1)

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

                msg = f'{t("done", self.lang)}: добавлено {inserted}. Пропущено дубликатов: {skipped}.'
                self.log.append(msg)
                QMessageBox.information(self, t("done", self.lang), msg)
            except Exception as e:
                QMessageBox.critical(self, t("error", self.lang), str(e))

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
            QMessageBox.information(self, t("check_updates", self.lang), f'Не удалось проверить обновления:\n{data}')
            return
        tag = data.get('tag_name')
        url = data.get('html_url') or REPO_PAGE
        if tag:
            latest = _parse_version_tag(tag)
            current = _parse_version_tag(__version__)
            if latest and latest > current:
                resp = QMessageBox.question(self, t("update_available", self.lang),
                                            f'{t("update_available", self.lang)} {tag} (текущая: {__version__}). {t("update_open_repo", self.lang)}',
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if resp == QMessageBox.StandardButton.Yes:
                    webbrowser.open(url)
            else:
                QMessageBox.information(self, t("check_updates", self.lang), 'У вас последняя версия.')
        else:
            QMessageBox.information(self, t("check_updates", self.lang), 'Не удалось получить информацию о релизе.')

    def apply_theme(self):
        if self.theme == "dark":
            stylesheet = """
                QWidget { 
                    background: #1a1a1a; 
                    color: #ffffff; 
                    font-family: "Segoe UI", Arial; 
                    font-size: 9pt;
                }
                QGroupBox { 
                    background: #2d2d2d; 
                    border: 1px solid #404040; 
                    border-radius: 6px; 
                    margin-top: 8px; 
                    padding: 8px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px 0 4px;
                    color: #ffffff;
                }
                QLabel { 
                    color: #ffffff; 
                    background: transparent;
                }
                QLineEdit, QTextEdit, QComboBox { 
                    background: #383838; 
                    border: 1px solid #555555; 
                    color: #ffffff; 
                    padding: 4px; 
                    border-radius: 4px;
                    selection-background-color: #0078d4;
                }
                QTextEdit { 
                    selection-background-color: #0078d4;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox::down-arrow {
                    border: 2px solid #888888;
                    border-top-color: transparent;
                    border-left-color: transparent;
                    border-right-color: transparent;
                    width: 0px;
                    height: 0px;
                }
                QPushButton { 
                    background: #404040; 
                    color: #ffffff; 
                    border: 1px solid #555555; 
                    padding: 6px 12px; 
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { 
                    background: #505050; 
                    border-color: #666666;
                }
                QPushButton:pressed {
                    background: #353535;
                }
                QRadioButton, QCheckBox { 
                    color: #ffffff;
                    spacing: 8px;
                }
                QRadioButton::indicator, QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #555555;
                    border-radius: 8px;
                    background: #2d2d2d;
                }
                QRadioButton::indicator::checked {
                    border: 2px solid #0078d4;
                    border-radius: 8px;
                    background: #0078d4;
                }
                QCheckBox::indicator::unchecked {
                    border: 2px solid #555555;
                    background: #2d2d2d;
                }
                QCheckBox::indicator::checked {
                    border: 2px solid #0078d4;
                    background: #0078d4;
                }
                QScrollBar:vertical {
                    background: #2d2d2d;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background: #555555;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #666666;
                }
            """
        else:
            stylesheet = """
                QWidget { 
                    background: #ffffff; 
                    color: #000000; 
                    font-family: "Segoe UI", Arial;
                    font-size: 9pt;
                }
                QGroupBox { 
                    background: #f8f9fa; 
                    border: 1px solid #dee2e6; 
                    border-radius: 6px; 
                    margin-top: 8px; 
                    padding: 8px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px 0 4px;
                    color: #000000;
                }
                QLabel { 
                    color: #000000;
                    background: transparent;
                }
                QLineEdit, QTextEdit, QComboBox { 
                    background: #ffffff; 
                    border: 1px solid #ced4da; 
                    color: #000000; 
                    padding: 4px; 
                    border-radius: 4px;
                    selection-background-color: #0078d4;
                }
                QTextEdit { 
                    selection-background-color: #b3d7ff;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox::down-arrow {
                    border: 2px solid #666666;
                    border-top-color: transparent;
                    border-left-color: transparent;
                    border-right-color: transparent;
                    width: 0px;
                    height: 0px;
                }
                QPushButton { 
                    background: #e9ecef; 
                    color: #000000; 
                    border: 1px solid #ced4da; 
                    padding: 6px 12px; 
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover { 
                    background: #f8f9fa; 
                    border-color: #adb5bd;
                }
                QPushButton:pressed {
                    background: #dee2e6;
                }
                QRadioButton, QCheckBox { 
                    color: #000000;
                    spacing: 8px;
                }
                QRadioButton::indicator, QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                }
                QRadioButton::indicator::unchecked {
                    border: 2px solid #ced4da;
                    border-radius: 8px;
                    background: #ffffff;
                }
                QRadioButton::indicator::checked {
                    border: 2px solid #0078d4;
                    border-radius: 8px;
                    background: #0078d4;
                }
                QCheckBox::indicator::unchecked {
                    border: 2px solid #ced4da;
                    background: #ffffff;
                }
                QCheckBox::indicator::checked {
                    border: 2px solid #0078d4;
                    background: #0078d4;
                }
                QScrollBar:vertical {
                    background: #f8f9fa;
                    width: 12px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical {
                    background: #ced4da;
                    border-radius: 6px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #adb5bd;
                }
            """
        self.setStyleSheet(stylesheet)

    def _on_theme_changed(self, idx):
        self.theme = "dark" if idx == 0 else "light"
        self.apply_theme()

    def _on_language_changed(self, idx):
        self.lang = "ru" if idx == 0 else "en"
        self._retranslate_ui()

    def _retranslate_ui(self):
        self.setWindowTitle(f'{t("title", self.lang)} - {__version__}')
        self.title_label.setText(t("title", self.lang))

        self.lbl_client.setText(t("client", self.lang))
        self.lbl_path.setText(t("path", self.lang))
        self.browse_btn.setText(t("choose_file", self.lang))

        self.mode_group_box.setTitle(t("mode", self.lang))
        self.single_radio.setText(t("single", self.lang))
        self.multi_radio.setText(t("multi", self.lang))

        self.single_box.setTitle(t("single", self.lang))
        self.lbl_single_nick.setText(t("nick", self.lang))
        self.lbl_single_clan.setText(t("clan", self.lang))
        self.lbl_single_reason.setText(t("reason", self.lang))

        if self.lang == "ru":
            self.single_nick.setPlaceholderText(t("nick", self.lang) + " (например: Player123)")
        else:
            self.single_nick.setPlaceholderText(t("nick", self.lang) + " (e.g. Player123)")
        self.single_clan.setPlaceholderText(t("clan", self.lang))
        self.single_reason.setPlaceholderText(t("reason", self.lang))

        self.multi_box.setTitle(t("multi", self.lang))
        self.multi_text.setPlaceholderText(t("multi_hint", self.lang))
        self.lbl_multi_reason.setText(t("multi_reason_label", self.lang))
        self.lbl_multi_clan.setText(t("multi_clan_label", self.lang))
        self.multi_reason.setPlaceholderText(t("reason", self.lang))
        self.multi_clan.setPlaceholderText(t("multi_clan_label", self.lang))

        self.lbl_group.setText(t("group", self.lang))
        self.backup_checkbox.setText(t("backup", self.lang))

        self.preview_btn.setText(t("preview", self.lang))
        self.add_btn.setText(t("add", self.lang))
        self.undo_btn.setText(t("undo", self.lang))
        self.update_btn.setText(t("check_updates", self.lang))

        self.lbl_log.setText(t("log_preview", self.lang))
        self.help_label.setText(t("footer_hint", self.lang))
        self.watermark.setText(t("byline", self.lang))

        self.theme_combo.setItemText(0, t("theme_dark", self.lang))
        self.theme_combo.setItemText(1, t("theme_light", self.lang))

        self._set_path_placeholder()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = WarlistEditor()
    w.show()
    sys.exit(app.exec())