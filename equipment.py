"""Учёт оборудования. Запуск: python equipment.py."""
import csv
import sqlite3
import tkinter as tk
from contextlib import closing
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

STATUSES = ("В эксплуатации", "На складе", "В ремонте", "Списано")
FIELDS = ("inventory", "name", "category", "room", "responsible", "status")
LABELS = ("Инв. номер", "Наименование", "Категория", "Кабинет", "Ответственный", "Статус")
SCHEMA = """
CREATE TABLE IF NOT EXISTS equipment (
    id INTEGER PRIMARY KEY,
    inventory TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    room TEXT NOT NULL,
    responsible TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('В эксплуатации','На складе','В ремонте','Списано'))
);
"""


class Registry:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(SCHEMA)

    def save(self, values, item_id=None):
        inventory, name, category, room, responsible, status = (v.strip() for v in values)
        if not inventory or not name or status not in STATUSES:
            raise ValueError("Заполните инвентарный номер, название и выберите статус.")
        if max(map(len, (inventory, name, category, room, responsible))) > 120:
            raise ValueError("Максимальная длина каждого поля — 120 символов.")
        clean = (inventory.upper(), name, category, room, responsible, status)
        with closing(sqlite3.connect(self.path)) as db, db:
            if item_id is None:
                return db.execute(
                    "INSERT INTO equipment (inventory,name,category,room,responsible,status) "
                    "VALUES (?,?,?,?,?,?)", clean
                ).lastrowid
            db.execute(
                "UPDATE equipment SET inventory=?,name=?,category=?,room=?,responsible=?,status=? "
                "WHERE id=?", (*clean, item_id)
            )
            return item_id

    def delete(self, item_id):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM equipment WHERE id=?", (item_id,))

    def list(self, search="", status=""):
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute(
                "SELECT id,inventory,name,category,room,responsible,status FROM equipment "
                "WHERE (?='' OR status=?) ORDER BY inventory", (status, status)
            ).fetchall()
        term = search.strip().casefold()
        return [row for row in rows if any(term in value.casefold() for value in row[1:])]

    def export(self, path, search="", status=""):
        def cell(value):
            # CSV может открываться в табличном редакторе.
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value

        with open(path, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(LABELS)
            writer.writerows([cell(value) for value in row[1:]] for row in self.list(search, status))


class EquipmentWindow:
    def __init__(self, root, registry):
        self.root, self.registry = root, registry
        self.item_id = None
        self.values = [tk.StringVar() for _ in FIELDS]
        self.values[-1].set(STATUSES[0])
        self.search = tk.StringVar()
        self.status = tk.StringVar(value="Все статусы")
        self.notice = tk.StringVar()
        root.title("Учёт оборудования")
        root.geometry("980x560")
        root.minsize(780, 470)
        frame = ttk.Frame(root, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Учёт оборудования", font=("TkDefaultFont", 19, "bold")).pack(anchor="w")
        filters = ttk.Frame(frame, padding=(0, 12))
        filters.pack(fill="x")
        ttk.Label(filters, text="Поиск").pack(side="left")
        ttk.Entry(filters, textvariable=self.search, width=26).pack(side="left", padx=8)
        ttk.Combobox(filters, textvariable=self.status, values=("Все статусы", *STATUSES),
                     state="readonly", width=20).pack(side="left")
        ttk.Button(filters, text="Экспорт CSV", command=self.export).pack(side="right")
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=FIELDS, show="headings", selectmode="browse")
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for field, label, width in zip(FIELDS, LABELS, (95, 200, 125, 85, 155, 128)):
            self.tree.heading(field, text=label)
            self.tree.column(field, width=width, minwidth=60)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        form = ttk.LabelFrame(frame, text="Карточка оборудования", padding=12)
        form.pack(fill="x", pady=(12, 0))
        for index, (label, variable) in enumerate(zip(LABELS, self.values)):
            row, column = divmod(index, 3)
            ttk.Label(form, text=label).grid(row=row * 2, column=column, sticky="w", padx=4)
            widget = (ttk.Combobox(form, textvariable=variable, values=STATUSES, state="readonly")
                      if index == 5 else ttk.Entry(form, textvariable=variable))
            widget.grid(row=row * 2 + 1, column=column, sticky="ew", padx=4, pady=(0, 6))
            form.columnconfigure(column, weight=1)
        ttk.Button(form, text="Новая карточка", command=self.clear).grid(row=4, column=0, sticky="w")
        ttk.Button(form, text="Сохранить", command=self.save).grid(row=4, column=1, sticky="w")
        ttk.Button(form, text="Удалить", command=self.delete).grid(row=4, column=2, sticky="w")
        ttk.Label(frame, textvariable=self.notice).pack(anchor="w", pady=(6, 0))
        self.search.trace_add("write", self.refresh)
        self.status.trace_add("write", self.refresh)
        self.refresh()

    def filter_values(self):
        status = self.status.get()
        return self.search.get(), "" if status == "Все статусы" else status

    def refresh(self, *_):
        if self.item_id is not None:
            self.clear()
        rows = self.registry.list(*self.filter_values())
        self.tree.delete(*self.tree.get_children())
        for item_id, *values in rows:
            self.tree.insert("", "end", iid=str(item_id), values=values)
        self.notice.set(f"Записей в выборке: {len(rows)}")

    def select(self, _event):
        selection = self.tree.selection()
        if selection:
            self.item_id = int(selection[0])
            for variable, value in zip(self.values, self.tree.item(selection[0], "values")):
                variable.set(value)

    def clear(self):
        self.tree.selection_remove(*self.tree.selection())
        self.item_id = None
        for variable in self.values[:-1]:
            variable.set("")
        self.values[-1].set(STATUSES[0])

    def save(self):
        try:
            self.registry.save([v.get() for v in self.values], self.item_id)
        except ValueError as error:
            messagebox.showwarning("Проверьте данные", str(error))
            return
        except sqlite3.IntegrityError:
            messagebox.showwarning("Проверьте данные", "Этот инвентарный номер уже занят.")
            return
        self.clear()
        self.refresh()
        self.notice.set("Карточка сохранена. " + self.notice.get())

    def delete(self):
        selection = self.tree.selection()
        if selection and messagebox.askyesno("Удаление карточки", "Удалить выбранную карточку из реестра?"):
            self.registry.delete(int(selection[0]))
            self.clear()
            self.refresh()
            self.notice.set("Карточка удалена. " + self.notice.get())

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="equipment.csv",
                                            filetypes=[("CSV", "*.csv")])
        if path:
            try:
                self.registry.export(path, *self.filter_values())
            except OSError as error:
                messagebox.showerror("Ошибка экспорта", str(error))
            else:
                self.notice.set("Текущая выборка экспортирована.")


if __name__ == "__main__":
    root = tk.Tk()
    EquipmentWindow(root, Registry(Path(__file__).with_name("equipment.sqlite3")))
    root.mainloop()
