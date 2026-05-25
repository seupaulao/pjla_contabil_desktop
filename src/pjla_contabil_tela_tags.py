from __future__ import annotations

import sqlite3
import uuid
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

import funcoes_relatorios as relatorios
from pjla_contabil_tela_componentes import ConfirmDialog

class TagFormScreen(Screen):
    """Screen for tags form."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cancelar"),
        Binding("ctrl+s", "save", "Salvar"),
    ]

    def __init__(self, conn: sqlite3.Connection, existing: Optional[sqlite3.Row] = None, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self.existing = existing

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("PJLA Contabilidade - Tags", id="title")
        with Container():
            yield Label("Empresa ID")
            yield Input(value=str(self.existing["empresa_id"] or "") if self.existing else "", id="tag_empresa_id")
            yield Label("Nome*")
            yield Input(value=self.existing["name"] if self.existing else "", id="tag_name")
            with Horizontal():
                yield Button("Salvar", id="btn_save", variant="primary")
                yield Button("Cancelar", id="btn_cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            self.action_save()
        elif event.button.id == "btn_cancel":
            self.dismiss(False)

    def action_save(self) -> None:
        empresa_id = self.query_one("#tag_empresa_id", Input).value.strip() or None
        name = self.query_one("#tag_name", Input).value.strip()
        if not name:
            self.app.notify("Nome da tag é obrigatório.", severity="error")
            return

        try:
            if self.existing:
                self.conn.execute("UPDATE tags SET empresa_id = ?, name = ? WHERE id = ?", (empresa_id, name, self.existing["id"]))
            else:
                self.conn.execute("INSERT INTO tags (id, empresa_id, name) VALUES (?, ?, ?)", (str(uuid.uuid4()), empresa_id, name))
            self.conn.commit()
            self.app.notify("Tag salva com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar tag: {exc}", severity="error")


class TagListScreen(Screen):
    """Screen for listing tags."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("n", "novo", "Novo"),
        Binding("e", "editar", "Editar"),
        Binding("d", "excluir", "Excluir"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self._selected_id: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="tag_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tag_table", DataTable)
        table.add_columns("ID", "Empresa", "Nome")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#tag_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(self.conn, "SELECT id, empresa_id, name FROM tags ORDER BY name")
        for row in rows:
            table.add_row(str(row["id"]), str(row["empresa_id"] or ""), row["name"])
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#tag_table", DataTable).get_row(event.row_key)
        self._selected_id = str(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(TagFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM tags WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(TagFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM tags WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Tag excluída com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir tag: {exc}", severity="error")

        self.app.push_screen(ConfirmDialog("Confirmar exclusão", "Deseja excluir esta tag?"), handle_confirm)

    def _on_form_closed(self, saved: bool | None) -> None:
        if saved:
            self.load_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_novo":
            self.action_novo()
        elif event.button.id == "btn_editar":
            self.action_editar()
        elif event.button.id == "btn_excluir":
            self.action_excluir()


