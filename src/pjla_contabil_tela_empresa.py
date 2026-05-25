from __future__ import annotations

import sqlite3
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static, Label

import funcoes_relatorios as relatorios
from pjla_contabil_tela_componentes import ConfirmDialog, EmpresaForm

class EmpresaListScreen(Screen):
    """Screen for listing empresas."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("n", "nova_empresa", "Novo"),
        Binding("e", "editar_empresa", "Editar"),
        Binding("d", "excluir_empresa", "Excluir"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self._selected_empresa: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("PJLA Contabilidade - Empresas", id="title")

        yield DataTable(id="empresa_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", variant="primary", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#empresa_table", DataTable)
        table.add_columns("ID", "Nome", "CNPJ", "UF", "Município")
        table.cursor_type = "row"
        self.load_empresas()

    def load_empresas(self) -> None:
        table = self.query_one("#empresa_table", DataTable)
        table.clear()
        
        rows = relatorios.fetch_all(
            self.conn, 
            "SELECT id, nome, cnpj, uf, municipio FROM empresa ORDER BY id"
        )
        for row in rows:
            table.add_row(
                str(row["id"]), 
                row["nome"], 
                row["cnpj"],
                row["uf"] or "",
                row["municipio"] or ""
            )
        
        # Limpa seleção ao atualizar
        self._selected_empresa = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Habilita/desabilita botões baseado na seleção."""
        has_selection = self._selected_empresa is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Trata seleção de linha na tabela."""
        table = self.query_one("#empresa_table", DataTable)
        row_data = table.get_row(event.row_key)
        self._selected_empresa = {
            "id": int(row_data[0]),
            "nome": row_data[1],
            "cnpj": row_data[2],
            "uf": row_data[3],
            "municipio": row_data[4],
        }
        self._update_buttons()

    def action_nova_empresa(self) -> None:
        self.app.push_screen(EmpresaFormScreen(self.conn), self._on_form_closed)

    def action_editar_empresa(self) -> None:
        if not self._selected_empresa:
            self.app.notify("Selecione uma empresa para editar.", severity="error")
            return
        
        empresa = relatorios.fetch_one(
            self.conn, 
            "SELECT * FROM empresa WHERE id = ?", 
            (self._selected_empresa["id"],)
        )
        if empresa:
            self.app.push_screen(
                EmpresaFormScreen(self.conn, existing=empresa),
                self._on_form_closed
            )

    def action_excluir_empresa(self) -> None:
        if not self._selected_empresa:
            self.app.notify("Selecione uma empresa para excluir.", severity="error")
            return

        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                try:
                    self.conn.execute(
                        "DELETE FROM empresa WHERE id = ?", 
                        (self._selected_empresa["id"],)
                    )
                    self.conn.commit()
                    self.app.notify("Empresa excluída com sucesso!")
                    self.load_empresas()
                except sqlite3.DatabaseError as exc:
                    self.conn.rollback()
                    self.app.notify(f"Erro ao excluir: {exc}", severity="error")

        self.app.push_screen(
            ConfirmDialog(
                title="Confirmar exclusão",
                message=f"Deseja excluir a empresa?\n\nNome: {self._selected_empresa['nome']}\nCNPJ: {self._selected_empresa['cnpj']}",
            ),
            handle_confirm,
        )

    def _on_form_closed(self, saved: bool | None) -> None:
        """Callback quando tela de formulário é fechada."""
        if saved:
            self.load_empresas()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_novo":
            self.action_nova_empresa()
        elif event.button.id == "btn_editar":
            self.action_editar_empresa()
        elif event.button.id == "btn_excluir":
            self.action_excluir_empresa()


class EmpresaFormScreen(Screen):
    """Screen for empresa form."""
    
    DEFAULT_CSS = """
    EmpresaFormScreen {
        align: center middle;
    }
    EmpresaFormScreen > Container {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 80;
        height: auto;
    }
    EmpresaFormScreen #error-msg {
        color: $error;
        margin-top: 1;
        height: 1;
    }
    EmpresaFormScreen Horizontal {
        align: center middle;
        height: auto;
        margin-top: 2;
    }
    EmpresaFormScreen Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cancelar"),
        Binding("ctrl+s", "save", "Salvar"),
    ]

    def __init__(self, conn: sqlite3.Connection, existing: Optional[sqlite3.Row] = None, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self.existing = existing
        self._is_edit = existing is not None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            titulo = "Editar Empresa" if self._is_edit else "Nova Empresa"
            yield Static(titulo, id="form-title")
            yield EmpresaForm(existing=self.existing, id="empresa_form")
            yield Static("", id="error-msg")
            with Horizontal():
                yield Button("Salvar", id="btn_save", variant="primary")
                yield Button("Cancelar", id="btn_cancel", variant="default")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            self.action_save()
        elif event.button.id == "btn_cancel":
            self.dismiss(False)

    def action_save(self) -> None:
        try:
            form = self.query_one("#empresa_form", EmpresaForm)
            data = form.get_data()
            
            if self.existing:
                data["id"] = self.existing["id"]
                self.conn.execute(
                    """
                    UPDATE empresa
                    SET cnpj = :cnpj, nome = :nome, uf = :uf, municipio = :municipio,
                        data_inicio = :data_inicio, data_fim = :data_fim
                    WHERE id = :id
                    """,
                    data,
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO empresa (cnpj, nome, uf, municipio, data_inicio, data_fim)
                    VALUES (:cnpj, :nome, :uf, :municipio, :data_inicio, :data_fim)
                    """,
                    data,
                )
            
            self.conn.commit()
            self.app.notify("Empresa salva com sucesso!")
            self.dismiss(True)
        except ValueError as e:
            error_label = self.query_one("#error-msg", Static)
            error_label.update(f"Erro: {str(e)}")
        except sqlite3.DatabaseError as e:
            self.conn.rollback()
            error_label = self.query_one("#error-msg", Static)
            error_label.update(f"Erro ao salvar: {str(e)}")


