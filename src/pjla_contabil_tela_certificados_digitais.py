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

class CertificadoDigitalFormScreen(Screen):
    """Screen for certificados digitais form."""

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
        yield Label("PJLA Contabilidade - Certificados Digitais", id="title")
        with Container():
            yield Label("Empresa ID*")
            yield Input(value=str(self.existing["empresa_id"] or "") if self.existing else "", id="cert_empresa_id")
            yield Label("Nome do Certificado")
            yield Input(value=self.existing["certificate_name"] if self.existing and self.existing["certificate_name"] else "", id="cert_name")
            yield Label("Número de Série")
            yield Input(value=self.existing["serial_number"] if self.existing and self.existing["serial_number"] else "", id="cert_serial")
            yield Label("Válido de (YYYY-MM-DD)")
            yield Input(value=self.existing["valid_from"] if self.existing and self.existing["valid_from"] else "", id="cert_valid_from")
            yield Label("Válido até (YYYY-MM-DD)")
            yield Input(value=self.existing["valid_until"] if self.existing and self.existing["valid_until"] else "", id="cert_valid_until")
            yield Label("Emissor")
            yield Input(value=self.existing["issuer"] if self.existing and self.existing["issuer"] else "", id="cert_issuer")
            yield Label("PFX (texto/base64)")
            yield Input(value=self.existing["encrypted_pfx"] if self.existing and self.existing["encrypted_pfx"] else "", id="cert_pfx")
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
        empresa_id = self.query_one("#cert_empresa_id", Input).value.strip()
        if not empresa_id:
            self.app.notify("Empresa ID é obrigatório.", severity="error")
            return

        cert_name = self.query_one("#cert_name", Input).value.strip() or None
        serial = self.query_one("#cert_serial", Input).value.strip() or None
        valid_from = self.query_one("#cert_valid_from", Input).value.strip() or None
        valid_until = self.query_one("#cert_valid_until", Input).value.strip() or None
        issuer = self.query_one("#cert_issuer", Input).value.strip() or None
        pfx = self.query_one("#cert_pfx", Input).value.strip() or None

        try:
            if self.existing:
                self.conn.execute(
                    """
                    UPDATE certificados_digitais
                    SET empresa_id = ?, certificate_name = ?, serial_number = ?, valid_from = ?,
                        valid_until = ?, issuer = ?, encrypted_pfx = ?
                    WHERE id = ?
                    """,
                    (empresa_id, cert_name, serial, valid_from, valid_until, issuer, pfx, self.existing["id"]),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO certificados_digitais
                    (id, empresa_id, certificate_name, serial_number, valid_from, valid_until, issuer, encrypted_pfx)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid.uuid4()), empresa_id, cert_name, serial, valid_from, valid_until, issuer, pfx),
                )
            self.conn.commit()
            self.app.notify("Certificado salvo com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar certificado: {exc}", severity="error")


class CertificadoDigitalListScreen(Screen):
    """Screen for listing certificados digitais."""

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
        yield DataTable(id="cert_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#cert_table", DataTable)
        table.add_columns("ID", "Empresa", "Certificado", "Série", "Válido Até")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#cert_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(
            self.conn,
            "SELECT id, empresa_id, certificate_name, serial_number, valid_until FROM certificados_digitais ORDER BY created_at DESC",
        )
        for row in rows:
            table.add_row(
                str(row["id"]),
                str(row["empresa_id"]),
                row["certificate_name"] or "",
                row["serial_number"] or "",
                row["valid_until"] or "",
            )
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#cert_table", DataTable).get_row(event.row_key)
        self._selected_id = str(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(CertificadoDigitalFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM certificados_digitais WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(CertificadoDigitalFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM certificados_digitais WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Certificado excluído com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir certificado: {exc}", severity="error")

        self.app.push_screen(ConfirmDialog("Confirmar exclusão", "Deseja excluir este certificado digital?"), handle_confirm)

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


