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

class UsuarioFormScreen(Screen):
    """Screen for usuário form."""

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
        yield Label("PJLA Contabilidade - Usuários", id="title")
        with Container():
            yield Label("Nome*")
            yield Input(value=self.existing["nome"] if self.existing else "", id="u_nome")
            yield Label("Email*")
            yield Input(value=self.existing["email"] if self.existing else "", id="u_email")
            yield Label("Password Hash*")
            yield Input(value=self.existing["password_hash"] if self.existing else "", id="u_password_hash")
            yield Label("Ativo (1/0)")
            yield Input(value=str(self.existing["is_active"] if self.existing else 1), id="u_is_active")
            yield Label("Último Login (YYYY-MM-DD HH:MM:SS)")
            yield Input(value=self.existing["last_login_at"] if self.existing and self.existing["last_login_at"] else "", id="u_last_login")
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
        nome = self.query_one("#u_nome", Input).value.strip()
        email = self.query_one("#u_email", Input).value.strip()
        password_hash = self.query_one("#u_password_hash", Input).value.strip()
        is_active_raw = self.query_one("#u_is_active", Input).value.strip() or "1"
        last_login_at = self.query_one("#u_last_login", Input).value.strip() or None

        if not nome or not email or not password_hash:
            self.app.notify("Nome, Email e Password Hash são obrigatórios.", severity="error")
            return

        try:
            is_active = 1 if int(is_active_raw) else 0
        except ValueError:
            self.app.notify("Ativo deve ser 1 ou 0.", severity="error")
            return

        try:
            if self.existing:
                self.conn.execute(
                    """
                    UPDATE usuarios
                    SET nome = ?, email = ?, password_hash = ?, is_active = ?, last_login_at = ?
                    WHERE id = ?
                    """,
                    (nome, email, password_hash, is_active, last_login_at, self.existing["id"]),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO usuarios (id, nome, email, password_hash, is_active, last_login_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), nome, email, password_hash, is_active, last_login_at),
                )
            self.conn.commit()
            self.app.notify("Usuário salvo com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar usuário: {exc}", severity="error")


class UsuarioListScreen(Screen):
    """Screen for listing usuários."""

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
        yield DataTable(id="usuarios_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#usuarios_table", DataTable)
        table.add_columns("ID", "Nome", "Email", "Ativo")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#usuarios_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(self.conn, "SELECT id, nome, email, is_active FROM usuarios ORDER BY nome")
        for row in rows:
            table.add_row(str(row["id"]), row["nome"], row["email"], str(row["is_active"]))
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#usuarios_table", DataTable).get_row(event.row_key)
        self._selected_id = str(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(UsuarioFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM usuarios WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(UsuarioFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM usuarios WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Usuário excluído com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir usuário: {exc}", severity="error")

        self.app.push_screen(ConfirmDialog("Confirmar exclusão", "Deseja excluir este usuário?"), handle_confirm)

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


