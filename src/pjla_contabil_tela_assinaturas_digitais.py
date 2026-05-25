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

class AssinaturaDigitalFormScreen(Screen):
    """Screen for assinaturas digitais form."""

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
        yield Label("PJLA Contabilidade - Assinaturas Digitais", id="title")
        with Container():
            yield Label("ECD File ID*")
            yield Input(value=self.existing["ecd_file_id"] if self.existing else "", id="as_ecd_file_id")
            yield Label("Signed By (Usuário ID)")
            yield Input(value=self.existing["signed_by"] if self.existing and self.existing["signed_by"] else "", id="as_signed_by")
            yield Label("Certificate ID")
            yield Input(value=self.existing["certificate_id"] if self.existing and self.existing["certificate_id"] else "", id="as_certificate_id")
            yield Label("Signature Hash*")
            yield Input(value=self.existing["signature_hash"] if self.existing else "", id="as_hash")
            yield Label("Signed At (YYYY-MM-DD HH:MM:SS)")
            yield Input(value=self.existing["signed_at"] if self.existing and self.existing["signed_at"] else "", id="as_signed_at")
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
        ecd_file_id = self.query_one("#as_ecd_file_id", Input).value.strip()
        signature_hash = self.query_one("#as_hash", Input).value.strip()
        if not ecd_file_id or not signature_hash:
            self.app.notify("ECD File ID e Signature Hash são obrigatórios.", severity="error")
            return

        signed_by = self.query_one("#as_signed_by", Input).value.strip() or None
        certificate_id = self.query_one("#as_certificate_id", Input).value.strip() or None
        signed_at = self.query_one("#as_signed_at", Input).value.strip() or None

        try:
            if self.existing:
                self.conn.execute(
                    """
                    UPDATE assinaturas_digitais
                    SET ecd_file_id = ?, signed_by = ?, certificate_id = ?, signature_hash = ?, signed_at = ?
                    WHERE id = ?
                    """,
                    (ecd_file_id, signed_by, certificate_id, signature_hash, signed_at, self.existing["id"]),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO assinaturas_digitais
                    (id, ecd_file_id, signed_by, certificate_id, signature_hash, signed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), ecd_file_id, signed_by, certificate_id, signature_hash, signed_at),
                )
            self.conn.commit()
            self.app.notify("Assinatura salva com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar assinatura: {exc}", severity="error")


class AssinaturaDigitalListScreen(Screen):
    """Screen for listing assinaturas digitais."""

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
        yield DataTable(id="as_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#as_table", DataTable)
        table.add_columns("ID", "ECD File", "Signed By", "Hash")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#as_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(
            self.conn,
            "SELECT id, ecd_file_id, signed_by, signature_hash FROM assinaturas_digitais ORDER BY signed_at DESC",
        )
        for row in rows:
            table.add_row(str(row["id"]), row["ecd_file_id"], row["signed_by"] or "", row["signature_hash"])
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#as_table", DataTable).get_row(event.row_key)
        self._selected_id = str(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(AssinaturaDigitalFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM assinaturas_digitais WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(AssinaturaDigitalFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM assinaturas_digitais WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Assinatura excluída com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir assinatura: {exc}", severity="error")

        self.app.push_screen(ConfirmDialog("Confirmar exclusão", "Deseja excluir esta assinatura digital?"), handle_confirm)

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


