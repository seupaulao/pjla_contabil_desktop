from __future__ import annotations

import sqlite3
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label

import funcoes_relatorios as relatorios
from pjla_contabil_tela_componentes import ConfirmDialog

class PlanoReferencialFormScreen(Screen):
    """Screen for plano de contas referencial form."""

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
        yield Label("PJLA Contabilidade - Plano de Contas Referencial", id="title")
        with Container():
            yield Label("Código*")
            yield Input(value=self.existing["codigo"] if self.existing else "", id="pr_codigo")
            yield Label("Nome*")
            yield Input(value=self.existing["nome"] if self.existing else "", id="pr_nome")
            yield Label("Tipo")
            yield Input(value=self.existing["tipo"] if self.existing else "", id="pr_tipo")
            yield Label("Natureza")
            yield Input(value=self.existing["natureza"] if self.existing else "", id="pr_natureza")
            yield Label("Nível")
            yield Input(value=str(self.existing["nivel"] or "") if self.existing else "", id="pr_nivel")
            yield Label("Parent ID")
            yield Input(value=str(self.existing["parent_id"] or "") if self.existing else "", id="pr_parent_id")
            yield Label("Grupo")
            yield Input(value=self.existing["grupo"] if self.existing else "", id="pr_grupo")
            yield Label("Grupo DRE")
            yield Input(value=self.existing["dre_grupo"] if self.existing else "", id="pr_dre_grupo")
            yield Label("Fluxo Caixa Tipo")
            yield Input(value=self.existing["fluxo_caixa_tipo"] if self.existing else "", id="pr_fluxo")
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
        codigo = self.query_one("#pr_codigo", Input).value.strip()
        nome = self.query_one("#pr_nome", Input).value.strip()
        if not codigo or not nome:
            self.app.notify("Código e Nome são obrigatórios.", severity="error")
            return

        tipo = self.query_one("#pr_tipo", Input).value.strip() or None
        natureza = self.query_one("#pr_natureza", Input).value.strip() or None
        nivel_raw = self.query_one("#pr_nivel", Input).value.strip()
        parent_raw = self.query_one("#pr_parent_id", Input).value.strip()
        grupo = self.query_one("#pr_grupo", Input).value.strip() or None
        dre_grupo = self.query_one("#pr_dre_grupo", Input).value.strip() or None
        fluxo = self.query_one("#pr_fluxo", Input).value.strip() or None

        try:
            nivel = int(nivel_raw) if nivel_raw else None
            parent_id = int(parent_raw) if parent_raw else None
        except ValueError:
            self.app.notify("Nível e Parent ID devem ser números inteiros.", severity="error")
            return

        try:
            if self.existing:
                self.conn.execute(
                    """
                    UPDATE plano_contas_referencial
                    SET codigo = ?, nome = ?, tipo = ?, natureza = ?, nivel = ?,
                        parent_id = ?, grupo = ?, dre_grupo = ?, fluxo_caixa_tipo = ?
                    WHERE id = ?
                    """,
                    (codigo, nome, tipo, natureza, nivel, parent_id, grupo, dre_grupo, fluxo, self.existing["id"]),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO plano_contas_referencial
                    (codigo, nome, tipo, natureza, nivel, parent_id, grupo, dre_grupo, fluxo_caixa_tipo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (codigo, nome, tipo, natureza, nivel, parent_id, grupo, dre_grupo, fluxo),
                )
            self.conn.commit()
            self.app.notify("Registro salvo com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar: {exc}", severity="error")


class PlanoReferencialListScreen(Screen):
    """Screen for listing plano de contas referencial."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("n", "novo", "Novo"),
        Binding("e", "editar", "Editar"),
        Binding("d", "excluir", "Excluir"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self._selected_id: Optional[int] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="pr_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#pr_table", DataTable)
        table.add_columns("ID", "Código", "Nome", "Tipo", "Natureza")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#pr_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(
            self.conn,
            "SELECT id, codigo, nome, tipo, natureza FROM plano_contas_referencial ORDER BY codigo",
        )
        for row in rows:
            table.add_row(str(row["id"]), row["codigo"], row["nome"], row["tipo"] or "", row["natureza"] or "")
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#pr_table", DataTable).get_row(event.row_key)
        self._selected_id = int(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(PlanoReferencialFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM plano_contas_referencial WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(PlanoReferencialFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM plano_contas_referencial WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Registro excluído com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir: {exc}", severity="error")

        self.app.push_screen(
            ConfirmDialog("Confirmar exclusão", "Deseja excluir este registro referencial?"),
            handle_confirm,
        )

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


