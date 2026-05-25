from __future__ import annotations

import sqlite3
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Select

import pjla_contabil_tela_estado as estado
from pjla_contabil_tela_app import run_app
from pjla_contabil_tela_assinaturas_digitais import AssinaturaDigitalListScreen
from pjla_contabil_tela_centro_custos import CentroCustoListScreen
from pjla_contabil_tela_certificados_digitais import CertificadoDigitalListScreen
from pjla_contabil_tela_contas import ContaListScreen
from pjla_contabil_tela_empresa import EmpresaListScreen
from pjla_contabil_tela_livro_diario import LivroDiarioScreen
from pjla_contabil_tela_plano_referencial import PlanoReferencialListScreen
from pjla_contabil_tela_relatorios import RelatoriosScreen
from pjla_contabil_tela_set_empresa import SetEmpresaScreen
from pjla_contabil_tela_tags import TagListScreen
from pjla_contabil_tela_usuarios import UsuarioListScreen


class MainScreen(Screen):
    """Main menu screen."""

    BINDINGS = [
        Binding("q", "quit", "Sair"),
        Binding("a", "livro_diario", "Livro Diário"),
        Binding("c", "cadastro_empresa", "Empresa"),
        Binding("d", "set_empresa", "Definir Empresa"),
    ]

    # Mapeamento de opções do Select para ações
    MENU_OPTIONS = {
        "definir_empresa": ("set_empresa", "Definir Empresa"),
        "empresa": ("cadastro_empresa", "Empresa"),
        "livro_diario": ("livro_diario", "Livro Diário"),
        "assinaturas_digitais": ("assinaturas_digitais", "Assinaturas Digitais"),
        "certificados_digitais": ("certificados_digitais", "Certificados Digitais"),
        "centro_custos": ("centro_custos", "Centro de Custos"),
        "plano_referencial": ("plano_referencial", "Plano Contas Referencial"),
        "plano_contas": ("plano_contas", "Plano Contas"),
        "relatorios": ("relatorios", "Relatórios"),
        "usuarios": ("usuarios", "Usuários"),
        "tags": ("tags", "Tags"),
        "sair": ("quit", "Sair"),
    }

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("PJLA Contabilidade", id="title")
        with Container():
            yield Label(self._empresa_info_text(), id="empresa_info")
            with Vertical(id="menu_container"):
                yield Label("Menu de Opções", id="menu_label")
                yield Select(
                    options=[
                        ("Definir Empresa", "definir_empresa"),
                        ("Empresa", "empresa"),
                        ("Livro Diário", "livro_diario"),
                        ("Assinaturas Digitais", "assinaturas_digitais"),
                        ("Certificados Digitais", "certificados_digitais"),
                        ("Centro de Custos", "centro_custos"),
                        ("Plano Contas Referencial", "plano_referencial"),
                        ("Plano Contas", "plano_contas"),
                        ("Relatórios", "relatorios"),
                        ("Usuários", "usuarios"),
                        ("Tags", "tags"),
                        ("Sair", "sair"),
                    ],
                    id="menu_select"
                )
        yield Footer()

    def _empresa_info_text(self) -> str:
        if estado.EMPRESA_ATUAL is None:
            return "Selecione uma empresa"
        return f"Empresa: {estado.EMPRESA_ATUAL['nome']}"

    def _refresh_empresa_info(self) -> None:
        empresa_info = self.query_one("#empresa_info", Label)
        empresa_info.update(self._empresa_info_text())

    def on_mount(self) -> None:
        self._refresh_empresa_info()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle Select change event."""
        try:
            if event.value is not None and event.control.id == "menu_select":
                selected_value = event.value
                if selected_value in self.MENU_OPTIONS:
                    action_name, _ = self.MENU_OPTIONS[selected_value]
                    action_method = getattr(self, f"action_{action_name}", None)
                    if action_method:
                        action_method()
        except Exception as e:
            self.notify(f"Erro: {str(e)}", timeout=5)

    def action_livro_diario(self) -> None:
        self.app.push_screen(LivroDiarioScreen(self.conn))

    def action_relatorios(self) -> None:
        self.app.push_screen(RelatoriosScreen(self.conn))

    def action_cadastro_empresa(self) -> None:
        self.app.push_screen(EmpresaListScreen(self.conn))

    def action_plano_contas(self) -> None:
        self.app.push_screen(ContaListScreen(self.conn))

    def action_plano_referencial(self) -> None:
        self.app.push_screen(PlanoReferencialListScreen(self.conn))

    def action_usuarios(self) -> None:
        self.app.push_screen(UsuarioListScreen(self.conn))

    def action_centro_custos(self) -> None:
        self.app.push_screen(CentroCustoListScreen(self.conn))

    def action_tags(self) -> None:
        self.app.push_screen(TagListScreen(self.conn))

    def action_certificados_digitais(self) -> None:
        self.app.push_screen(CertificadoDigitalListScreen(self.conn))

    def action_assinaturas_digitais(self) -> None:
        self.app.push_screen(AssinaturaDigitalListScreen(self.conn))

    def action_set_empresa(self) -> None:
        self.app.push_screen(SetEmpresaScreen(self.conn), self._on_set_empresa_closed)

    def _on_set_empresa_closed(self, _result: Optional[sqlite3.Row]) -> None:
        self._refresh_empresa_info()


if __name__ == "__main__":
    run_app(MainScreen)
