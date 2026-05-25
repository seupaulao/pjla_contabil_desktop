from __future__ import annotations

import sqlite3

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

import funcoes_relatorios as relatorios
import pjla_contabil_tela_estado as estado

class SetEmpresaScreen(Screen):
    """Screen for setting current empresa."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("ctrl+s", "definir_empresa", "Definir"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Label("Definir Empresa Atual", id="set_empresa_title")
            yield Label("Informe o ID da empresa:")
            yield Input(placeholder="Ex.: 1", id="empresa_id_input")
            with Horizontal():
                yield Button("Definir", id="btn_definir", variant="primary")
                yield Button("Cancelar", id="btn_cancelar")
        yield Footer()            

    def action_definir_empresa(self) -> None:
        self._definir_empresa_atual()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_definir":
            self._definir_empresa_atual()
        elif event.button.id == "btn_cancelar":
            self.app.pop_screen()

    def _definir_empresa_atual(self) -> None:
        empresa_id_text = self.query_one("#empresa_id_input", Input).value.strip()
        if not empresa_id_text:
            self.app.notify("Informe o ID da empresa.", severity="error")
            return

        try:
            empresa_id = int(empresa_id_text)
        except ValueError:
            self.app.notify("ID da empresa deve ser um número inteiro.", severity="error")
            return

        empresa = relatorios.fetch_one(
            self.conn,
            "SELECT id, nome FROM empresa WHERE id = ?",
            (empresa_id,),
        )

        if not empresa:
            self.app.notify("Empresa não encontrada para o ID informado.", severity="error")
            return

        estado.EMPRESA_ATUAL = empresa
        self.app.notify(f"Empresa '{empresa['nome']}' definida com sucesso!")
        self.dismiss(empresa)

