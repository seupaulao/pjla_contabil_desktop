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

class CentroCustoFormScreen(Screen):
    """Screen for centro de custo form."""

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
        yield Label("PJLA Contabilidade - Centro de Custos", id="title")
        with Container():
            yield Label("Empresa ID*")
            yield Input(value=str(self.existing["empresa_id"] or "") if self.existing else "", id="cc_empresa_id")
            yield Label("Código")
            yield Input(value=self.existing["codigo"] if self.existing else "", id="cc_codigo")
            yield Label("Nome*")
            yield Input(value=self.existing["nome"] if self.existing else "", id="cc_nome")
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
        empresa_id = self.query_one("#cc_empresa_id", Input).value.strip()
        codigo = self.query_one("#cc_codigo", Input).value.strip() or None
        nome = self.query_one("#cc_nome", Input).value.strip()
        if not empresa_id or not nome:
            self.app.notify("Empresa ID e Nome são obrigatórios.", severity="error")
            return

        try:
            if self.existing:
                self.conn.execute(
                    "UPDATE centro_custo SET empresa_id = ?, codigo = ?, nome = ? WHERE id = ?",
                    (empresa_id, codigo, nome, self.existing["id"]),
                )
            else:
                self.conn.execute(
                    "INSERT INTO centro_custo (id, empresa_id, codigo, nome) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), empresa_id, codigo, nome),
                )
            self.conn.commit()
            self.app.notify("Centro de custo salvo com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar centro de custo: {exc}", severity="error")


class CentroCustoListScreen(Screen):
    """Screen for listing centro de custos."""

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
        yield DataTable(id="cc_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#cc_table", DataTable)
        table.add_columns("ID", "Empresa", "Código", "Nome")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#cc_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(self.conn, "SELECT id, empresa_id, codigo, nome FROM centro_custo ORDER BY nome")
        for row in rows:
            table.add_row(str(row["id"]), str(row["empresa_id"]), row["codigo"] or "", row["nome"])
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#cc_table", DataTable).get_row(event.row_key)
        self._selected_id = str(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(CentroCustoFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM centro_custo WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(CentroCustoFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM centro_custo WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Centro de custo excluído com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir centro de custo: {exc}", severity="error")

        self.app.push_screen(ConfirmDialog("Confirmar exclusão", "Deseja excluir este centro de custo?"), handle_confirm)

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


