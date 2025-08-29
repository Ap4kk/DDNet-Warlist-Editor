import sys
import shlex
import shutil
import json
import threading
import urllib.request
import urllib.error
import webbrowser
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QMessageBox, QRadioButton,
    QComboBox, QGroupBox, QFormLayout, QCheckBox, QSizePolicy
)

__version__ = "v1.0"
REPO_API_LATEST = "https://api.github.com/repos/Ap4kk/DDNet-Warlist-Editor-For-TaterClient/releases/latest"
REPO_PAGE = "https://github.com/Ap4kk/DDNet-Warlist-Editor-For-TaterClient"


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
    # normalize tag like "v1.2.3" or "1.2" -> tuple of ints for comparison
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
        self.setWindowTitle(f'DDNet Warlist Editor - {__version__}')
        self.resize(900, 700)
        self._build_ui()
        threading.Thread(target=self._bg_check_update, daemon=True).start()

    def _build_ui(self):
        layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r'C:\Users\Ap4k\AppData\Roaming\DDNet\tclient_warlist.cfg')
        browse_btn = QPushButton('Выбрать файл...')
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(QLabel('Путь к файлу:'))
        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(browse_btn)
        layout.addLayout(file_layout)

        # Mode selection
        mode_group_box = QGroupBox('Режим')
        mode_layout = QHBoxLayout()
        self.single_radio = QRadioButton('Одиночная выборка')
        self.multi_radio = QRadioButton('Множественная выборка')
        self.single_radio.setChecked(True)
        mode_layout.addWidget(self.single_radio)
        mode_layout.addWidget(self.multi_radio)
        mode_group_box.setLayout(mode_layout)
        layout.addWidget(mode_group_box)

        # Single mode inputs
        single_box = QGroupBox('Одиночная запись')
        single_form = QFormLayout()
        self.single_nick = QLineEdit()
        self.single_nick.setPlaceholderText('Ник (оставьте пустым если хотите добавить клан)')
        self.single_clan = QLineEdit()
        self.single_clan.setPlaceholderText('Клан (опционально)')
        self.single_reason = QLineEdit()
        self.single_reason.setPlaceholderText('Причина (опционально)')
        single_form.addRow('Ник:', self.single_nick)
        single_form.addRow('Клан:', self.single_clan)
        single_form.addRow('Причина:', self.single_reason)
        single_box.setLayout(single_form)
        layout.addWidget(single_box)

        # Multiple mode inputs
        multi_box = QGroupBox('Множественные ники (через пробел; кавычки сохраняются)')
        multi_layout = QVBoxLayout()
        self.multi_text = QTextEdit()
        self.multi_text.setPlaceholderText('Пример: KIRUSI Questal "I miss her" "King 1 fps?"')
        self.multi_reason = QLineEdit()
        self.multi_reason.setPlaceholderText('Причина (если заполнено — применится ко всем)')
        clan_row = QHBoxLayout()
        clan_row.addWidget(QLabel('Клан (опционально для всех):'))
        self.multi_clan = QLineEdit()
        self.multi_clan.setPlaceholderText('Клан, применимый ко всем никам')
        clan_row.addWidget(self.multi_clan)

        multi_layout.addWidget(self.multi_text)
        multi_layout.addLayout(clan_row)
        multi_layout.addWidget(QLabel('Причина для всех (опционально):'))
        multi_layout.addWidget(self.multi_reason)
        multi_box.setLayout(multi_layout)
        layout.addWidget(multi_box)

        # Group selection and options
        opts_layout = QHBoxLayout()
        self.group_box = QComboBox()
        self.group_box.addItems(['enemy', 'team'])
        opts_layout.addWidget(QLabel('Добавлять в группу:'))
        opts_layout.addWidget(self.group_box)

        self.backup_checkbox = QCheckBox('Создавать резервную копию перед записью')
        self.backup_checkbox.setChecked(True)
        opts_layout.addWidget(self.backup_checkbox)

        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        preview_btn = QPushButton('Предпросмотр')
        preview_btn.clicked.connect(self.preview)
        add_btn = QPushButton('Добавить в файл')
        add_btn.clicked.connect(self.add_to_file)
        update_btn = QPushButton('Проверить обновления')
        update_btn.clicked.connect(lambda: threading.Thread(target=self._check_update_and_notify, daemon=True).start())
        btn_layout.addWidget(preview_btn)
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(update_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Log / preview area
        layout.addWidget(QLabel('Лог / Предпросмотр:'))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        # Bottom row with watermark left and simple help right
        bottom_row = QHBoxLayout()
        self.watermark = QLabel('By Ap4k(AKIrA)')
        self.watermark.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        font = QFont()
        font.setPointSize(9)
        self.watermark.setFont(font)
        self.watermark.setStyleSheet('color: gray;')
        bottom_row.addWidget(self.watermark, alignment=Qt.AlignLeft | Qt.AlignBottom)

        help_label = QLabel('Подсказка: перед записью закройте DDNet (tclient).')
        help_label.setStyleSheet('color: #555555;')
        bottom_row.addStretch()
        bottom_row.addWidget(help_label, alignment=Qt.AlignRight | Qt.AlignBottom)

        layout.addLayout(bottom_row)

        self.setLayout(layout)

        # Connect mode toggles
        self.single_radio.toggled.connect(self._update_mode)
        self._update_mode()

    def _update_mode(self):
        single = self.single_radio.isChecked()
        self.single_nick.setEnabled(single)
        self.single_clan.setEnabled(single)
        self.single_reason.setEnabled(single)
        self.multi_text.setEnabled(not single)
        self.multi_reason.setEnabled(not single)
        self.multi_clan.setEnabled(not single)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Выбрать tclient_warlist.cfg', str(Path.home()))
        if path:
            self.path_edit.setText(path)

    def _gather_entries(self):
        group = self.group_box.currentText()
        entries = []  # tuples of (nick, clan, reason)
        if self.single_radio.isChecked():
            nick = self.single_nick.text().strip()
            clan = self.single_clan.text().strip()
            reason = self.single_reason.text().strip()
            if not nick and not clan:
                raise ValueError('Введите ник или клан для одиночной записи.')
            entries.append((nick, clan, reason))
        else:
            raw = self.multi_text.toPlainText().strip()
            if not raw:
                raise ValueError('Поле множественных ников пустое.')
            try:
                parsed = shlex.split(raw)
            except Exception as e:
                raise ValueError(f'Не удалось распарсить множественные ники: {e}')
            reason_all = self.multi_reason.text().strip()
            clan_all = self.multi_clan.text().strip()
            # deduplicate user input (casefold)
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
            QMessageBox.critical(self, 'Ошибка', str(e))
            return
        # validate nicks
        invalid = [n for n, c, r in entries if n and not safe_nick(n)]
        if invalid:
            QMessageBox.warning(self, 'Валидация', f'Найдены невалидные ники (удалите или исправьте):\n' + '\n'.join(invalid))
        lines = self._format_lines(group, entries)

        path_text = self.path_edit.text().strip()
        dup_info = []
        if path_text:
            p = Path(path_text)
            if p.exists():
                try:
                    existing = parse_existing_entries(p.read_text(encoding='utf-8', errors='replace'))
                    for ln, (nick, clan, reason) in zip(lines, entries):
                        cmp = (group, nick.casefold(), clan.casefold())
                        if cmp in existing:
                            dup_info.append(f'SKIP (duplicate): {nick} ({clan})')
                except Exception:
                    pass

        self.log.clear()
        self.log.append('\n'.join(lines))
        if dup_info:
            self.log.append('\n-- Обнаружены дубликаты (не будут записаны):')
            self.log.append('\n'.join(dup_info))

    def create_backup(self, path: Path) -> Path:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        bak_name = f"{path.name}.bak_{ts}"
        bak_path = path.with_name(bak_name)
        shutil.copy2(path, bak_path)
        meta = path.with_name(path.name + '.last_backup')
        meta.write_text(str(bak_path), encoding='utf-8')
        self._last_backup = bak_path
        return bak_path

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
            QMessageBox.warning(self, 'Undo', 'Файл не найден, невозможно откатить.')
            return
        bak = self._read_last_backup_meta(file_path) or getattr(self, '_last_backup', None)
        if not bak or not Path(bak).exists():
            QMessageBox.information(self, 'Undo', 'Резервная копия не найдена — ничего не откатывается.')
            return
        reply = QMessageBox.question(self, 'Undo', f'Откатить файл до резервной копии?\n{bak}', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.copy2(bak, file_path)
            self.log.append(f'Откат выполнен: {bak} -> {file_path}')
            QMessageBox.information(self, 'Undo', 'Откат выполнен успешно.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка Undo', str(e))

    def add_to_file(self):
        reply = QMessageBox.question(
            self,
            'Внимание',
            'Убедитесь, что DDNet (tclient) закрыт. Продолжить запись в файл?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        file_path = Path(self.path_edit.text().strip())
        if not file_path.exists():
            create_reply = QMessageBox.question(
                self,
                'Файл не найден',
                f'Файл не найден: {file_path}\nСоздать новый файл и продолжить?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if create_reply == QMessageBox.StandardButton.Yes:
                try:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text('# tclient_warlist.cfg (создан автоматически)\n', encoding='utf-8')
                except Exception as e:
                    QMessageBox.critical(self, 'Ошибка', f'Не удалось создать файл: {e}')
                    return
            else:
                return

        try:
            group, entries = self._gather_entries()
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
            return

        valid_entries = []
        invalid = []
        for nick, clan, reason in entries:
            if nick and not safe_nick(nick):
                invalid.append(nick)
            else:
                valid_entries.append((nick, clan, reason))
        if invalid:
            QMessageBox.warning(self, 'Валидация', f'Найдены невалидные ники — они будут пропущены:\n' + '\n'.join(invalid))

        if not valid_entries:
            QMessageBox.information(self, 'Нечего записывать', 'Нет корректных записей для добавления.')
            return

        existing = set()
        try:
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
            QMessageBox.information(self, 'Нечего записывать', 'Новые записи не найдены (все — дубликаты или невалидны).')
            self.log.append('Новые записи не найдены — ничего не записано.')
            return

        lines = self._format_lines(group, to_write)

        try:
            if self.backup_checkbox.isChecked() and file_path.exists():
                bak = self.create_backup(file_path)
                self.log.append(f'Резервная копия создана: {bak}')

            with file_path.open('a', encoding='utf-8', errors='replace') as f:
                for ln in lines:
                    f.write(ln + '\n')

            msg = f'Успешно добавлено {len(lines)} записей.'
            if skipped:
                msg += f' Пропущено дубликатов: {len(skipped)}.'
                self.log.append('\n-- Пропущенные дубликаты:')
                for nick, clan in skipped:
                    self.log.append(f'{nick} ({clan})')

            self.log.append(f'Записано {len(lines)} строк в {file_path}')
            QMessageBox.information(self, 'Готово', msg)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка при записи', str(e))

    def _bg_check_update(self):
        success, data = check_github_latest()
        if success:
            tag = data.get('tag_name')
            if tag:
                latest = _parse_version_tag(tag)
                current = _parse_version_tag(__version__)
                if latest and latest > current:
                    self.log.append(f'Найдена новая версия: {tag} — откройте репозиторий для обновления: {REPO_PAGE}')
                else:
                    self.log.append('Проверка обновлений: у вас последняя версия.')
        else:
            self.log.append(f'Проверка обновлений не удалась: {data}')

    def _check_update_and_notify(self):
        success, data = check_github_latest()
        if not success:
            QMessageBox.information(self, 'Проверка обновлений', f'Не удалось проверить обновления:\n{data}')
            return
        tag = data.get('tag_name')
        url = data.get('html_url') or REPO_PAGE
        if tag:
            latest = _parse_version_tag(tag)
            current = _parse_version_tag(__version__)
            if latest and latest > current:
                resp = QMessageBox.question(self, 'Обновление доступно', f'Доступна версия {tag} (у вас {__version__}). Открыть репозиторий?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if resp == QMessageBox.StandardButton.Yes:
                    webbrowser.open(url)
            else:
                QMessageBox.information(self, 'Проверка обновлений', 'У вас последняя версия.')
        else:
            QMessageBox.information(self, 'Проверка обновлений', 'Не удалось получить информацию о релизе.')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = WarlistEditor()
    w.show()
    sys.exit(app.exec())
