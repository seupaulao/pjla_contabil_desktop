from __future__ import annotations

import sqlite3
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label

import funcoes_relatorios as relatorios
from pjla_contabil_tela_componentes import ContaForm

class ContaFormScreen(Screen):
    """Screen for conta form."""
    
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
        yield Label("PJLA Contabilidade - Contas", id="title")
        with Container():
            yield ContaForm(existing=self.existing, id="conta_form")
            with Horizontal():
                yield Button("Salvar", id="btn_save", variant="primary")
                yield Button("Cancelar", id="btn_cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_save":
            self.action_save()
        elif event.button.id == "btn_cancel":
            self.app.pop_screen()

    def action_save(self) -> None:
        try:
            form = self.query_one(ContaForm)
            data = form.get_data()
            data["aceita_lancamento"] = 1
            
            if self.existing:
                data["id"] = self.existing["id"]
                self.conn.execute(
                    """
                    UPDATE plano_contas
                    SET empresa_id = ?, codigo = ?, descricao = ?, tipo = ?, natureza = ?,
                        grupo = ?, dre_grupo = ?, subgrupo = ?, fluxo_caixa_tipo = ?,
                        nivel = ?, conta_pai_id = ?, codigo_referencial = ?
                    WHERE id = ?
                    """,
                    (data.get("empresa_id"), data.get("codigo"), data.get("descricao"),
                     data.get("tipo"), data.get("natureza"), data.get("grupo"),
                     data.get("dre_grupo"), data.get("subgrupo"), data.get("fluxo_caixa_tipo"),
                     data.get("nivel"), data.get("conta_pai_id"), data.get("codigo_referencial"),
                     data.get("id")),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO plano_contas
                    (empresa_id, codigo, descricao, tipo, natureza, grupo, dre_grupo,
                     subgrupo, fluxo_caixa_tipo, nivel, conta_pai_id, codigo_referencial, aceita_lancamento)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (data.get("empresa_id"), data.get("codigo"), data.get("descricao"),
                     data.get("tipo"), data.get("natureza"), data.get("grupo"),
                     data.get("dre_grupo"), data.get("subgrupo"), data.get("fluxo_caixa_tipo"),
                     data.get("nivel"), data.get("conta_pai_id"), data.get("codigo_referencial"),
                     data.get("aceita_lancamento")),
                )
            
            self.conn.commit()
            self.app.notify("Conta salva com sucesso!")
            self.app.pop_screen()
        except ValueError as e:
            self.app.notify(f"Erro: {str(e)}", severity="error")
        except sqlite3.DatabaseError as e:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar: {str(e)}", severity="error")


class ContaListScreen(Screen):
    """Screen for listing contas."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("n", "nova_conta", "Nova"),
        Binding("e", "editar", "Editar"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="conta_table")
        yield Footer()

    def on_mount(self) -> None:
        self.load_contas()

    def load_contas(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        table.add_columns("Código", "Descrição", "Tipo", "Natureza")
        
        rows = relatorios.fetch_all(self.conn, "SELECT codigo, descricao, tipo, natureza FROM plano_contas ORDER BY codigo")
        for row in rows:
            table.add_row(row["codigo"], row["descricao"], row["tipo"], row["natureza"])

    def action_nova_conta(self) -> None:
        self.app.push_screen(ContaFormScreen(self.conn))

    def action_editar(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            codigo = table.get_cell(table.cursor_row, 0)
            conta = relatorios.fetch_one(self.conn, "SELECT * FROM plano_contas WHERE codigo = ?", (codigo,))
            if conta:
                self.app.push_screen(ContaFormScreen(self.conn, existing=conta))

