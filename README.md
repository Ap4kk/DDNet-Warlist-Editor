# DDNet Warlist Editor

Lightweight GUI to edit `tclient_warlist.cfg` for TaterClient.

## Requirements

* Python 3.8+
* PySide6

Install dependencies:

```bash
pip install PySide6
```

## Usage

1. Run the GUI:

```bash
python ddnet_warlist_editor_v3.py
```

2. Select the `tclient_warlist.cfg` file (or paste its path).
3. Choose `Одиночная выборка` for a single nick/clan or `Множественная выборка` and paste multiple nicks (use quotes for multi-word nicks).
4. Choose target group (`enemy` or `team`).
5. Optionally enable backups (enabled by default).
6. Click **Предпросмотр** to see what will be added, then **Добавить в файл**.
7. If you need to revert the last change made by the program, click **Отмена / Undo**.

## Notes

* Undo restores the last backup created by this program. Backups are stored next to the target cfg with names like `tclient_warlist.cfg.bak_YYYYMMDD_HHMMSS` and a small meta file `tclient_warlist.cfg.last_backup` points to the latest backup.
* The program intentionally rejects nicknames that contain control/unprintable characters or are longer than 64 characters.

## License

Use as you wish. No warranty.
