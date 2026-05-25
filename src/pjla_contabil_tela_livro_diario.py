from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select

import funcoes_relatorios as relatorios
import pjla_contabil_tela_estado as estado
from pjla_contabil_tela_componentes import ConfirmDialog

class LivroDiarioScreen(Screen):
    """Screen for displaying Livro Diário."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("n", "novo_lancamento", "Novo"),
        Binding("e", "editar_lancamento", "Editar"),
        Binding("d", "excluir_lancamento", "Excluir"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("PJLA Contabilidade - Livro Diário", id="title")
        yield DataTable(id="lancamento_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar")
            yield Button("Excluir", id="btn_excluir", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self.load_lancamentos()

    def load_lancamentos(self) -> None:
        table = self.query_one("#lancamento_table", DataTable)
        table.clear()
        table.add_columns("ID", "Data", "Histórico")
        table.cursor_type = "row"

        if estado.EMPRESA_ATUAL is None:
            return

        rows = relatorios.fetch_all(
            self.conn,
            """
            SELECT id, data, historico
            FROM lancamento
            WHERE empresa_id = ?
            ORDER BY data, id
            """,
            (estado.EMPRESA_ATUAL["id"],),
        )

        for row in rows:
            table.add_row(str(row["id"]), relatorios.display_date(row["data"]), row["historico"] or "")

    def get_selected_lancamento_id(self) -> Optional[int]:
        table = self.query_one("#lancamento_table", DataTable)
        if table.cursor_row is None:
            return None
        selected_id = table.get_cell(table.cursor_row, 0)
        try:
            return int(selected_id)
        except (TypeError, ValueError):
            return None

    def action_novo_lancamento(self) -> None:
        if estado.EMPRESA_ATUAL is None:
            self.app.notify("Selecione uma empresa antes de lançar.", severity="error")
            return
        self.app.push_screen(LancamentoEditScreen(self.conn), self._on_edit_closed)

    def action_editar_lancamento(self) -> None:
        if estado.EMPRESA_ATUAL is None:
            self.app.notify("Selecione uma empresa antes de editar.", severity="error")
            return

        lancamento_id = self.get_selected_lancamento_id()
        if lancamento_id is None:
            self.app.notify("Selecione um lançamento para editar.", severity="error")
            return

        self.app.push_screen(LancamentoEditScreen(self.conn, lancamento_id=lancamento_id), self._on_edit_closed)

    def action_excluir_lancamento(self) -> None:
        lancamento_id = self.get_selected_lancamento_id()
        if lancamento_id is None:
            self.app.notify("Selecione um lançamento para excluir.", severity="error")
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM lancamento WHERE id = ?", (lancamento_id,))
                self.conn.commit()
                self.load_lancamentos()
                self.app.notify("Lançamento excluído com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir lançamento: {exc}", severity="error")

        self.app.push_screen(
            ConfirmDialog(
                title="Confirmar exclusão",
                message="Deseja realmente excluir este lançamento?",
            ),
            handle_confirm,
        )

    def _on_edit_closed(self, saved: Optional[bool]) -> None:
        if saved:
            self.load_lancamentos()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_novo":
            self.action_novo_lancamento()
        elif event.button.id == "btn_editar":
            self.action_editar_lancamento()
        elif event.button.id == "btn_excluir":
            self.action_excluir_lancamento()


class LancamentoEditScreen(Screen):
    """Screen for creating or editing lançamento and its items."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
        Binding("ctrl+s", "salvar_lancamento", "Salvar"),
    ]

    def __init__(self, conn: sqlite3.Connection, lancamento_id: Optional[int] = None, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self.lancamento_id = lancamento_id
        self.items: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("PJLA Contabilidade - Lançamentos", id="title")
        with Container():
            yield Label("Data do Lançamento")
            yield Input(value=datetime.now().strftime("%d/%m/%Y"), id="lanc_data", placeholder="DD/MM/AAAA")
            yield Label("Histórico")
            yield Input(id="lanc_historico", placeholder="Histórico do lançamento")

            yield Label("Conta (ID, código ou nome)")
            yield Input(id="item_conta", placeholder="Ex.: 10, 1.1.1 ou Caixa")

            yield Label("Tipo de Lançamento")
            yield Select(
                [("Débito", "D"), ("Crédito", "C")],
                value="D",
                id="item_tipo",
            )

            yield Label("Valor")
            yield Input(id="item_valor", placeholder="0,00")

            with Horizontal(id="lancamento_item_actions"):
                yield Button("Incluir", id="btn_item_incluir", variant="primary")
                yield Button("Excluir", id="btn_item_excluir", variant="error")
                yield Button("Salvar Lançamento", id="btn_lanc_salvar", variant="success")

            yield DataTable(id="lancamento_item_table")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#lancamento_item_table", DataTable)
        table.add_columns("Código", "Nome Conta", "Tipo", "Valor")
        table.cursor_type = "row"

        if self.lancamento_id is not None:
            self._load_existing_lancamento()

    def _load_existing_lancamento(self) -> None:
        if estado.EMPRESA_ATUAL is None:
            return

        lanc = relatorios.fetch_one(
            self.conn,
            """
            SELECT id, data, historico
            FROM lancamento
            WHERE id = ? AND empresa_id = ?
            """,
            (self.lancamento_id, estado.EMPRESA_ATUAL["id"]),
        )
        if not lanc:
            self.app.notify("Lançamento não encontrado para a empresa selecionada.", severity="error")
            self.app.pop_screen()
            return

        self.query_one("#lanc_data", Input).value = relatorios.display_date(lanc["data"])
        self.query_one("#lanc_historico", Input).value = lanc["historico"] or ""

        rows = relatorios.fetch_all(
            self.conn,
            """
            SELECT li.conta_id, li.tipo, li.valor, c.codigo, c.descricao
            FROM lancamento_item li
            JOIN plano_contas c ON c.id = li.conta_id
            WHERE li.lancamento_id = ?
            ORDER BY li.id
            """,
            (self.lancamento_id,),
        )

        self.items = [
            {
                "conta_id": row["conta_id"],
                "codigo": row["codigo"],
                "descricao": row["descricao"],
                "tipo": row["tipo"],
                "valor": float(row["valor"]),
            }
            for row in rows
        ]
        self._refresh_items_table()

    def _find_account(self, raw_search: str) -> Optional[sqlite3.Row]:
        if estado.EMPRESA_ATUAL is None:
            return None

        text = raw_search.strip()
        if not text:
            return None

        if text.isdigit():
            account = relatorios.fetch_one(
                self.conn,
                """
                SELECT id, codigo, descricao
                FROM plano_contas
                WHERE empresa_id = ? AND aceita_lancamento = 1 AND id = ?
                """,
                (estado.EMPRESA_ATUAL["id"], int(text)),
            )
            if account:
                return account

        return relatorios.fetch_one(
            self.conn,
            """
            SELECT id, codigo, descricao
            FROM plano_contas
            WHERE empresa_id = ?
              AND aceita_lancamento = 1
              AND (codigo = ? OR UPPER(descricao) = UPPER(?) OR UPPER(descricao) LIKE UPPER(?))
            ORDER BY CASE
                WHEN codigo = ? THEN 0
                WHEN UPPER(descricao) = UPPER(?) THEN 1
                ELSE 2
            END,
            codigo
            LIMIT 1
            """,
            (estado.EMPRESA_ATUAL["id"], text, text, f"%{text}%", text, text),
        )

    def _refresh_items_table(self) -> None:
        table = self.query_one("#lancamento_item_table", DataTable)
        table.clear()
        for item in self.items:
            table.add_row(
                item["codigo"],
                item["descricao"],
                item["tipo"],
                relatorios.format_currency(item["valor"]),
            )

    def _incluir_item(self) -> None:
        if estado.EMPRESA_ATUAL is None:
            self.app.notify("Selecione uma empresa antes de incluir itens.", severity="error")
            return

        conta_raw = self.query_one("#item_conta", Input).value.strip()
        if not conta_raw:
            self.app.notify("Informe ID, código ou nome da conta.", severity="error")
            return

        conta = self._find_account(conta_raw)
        if not conta:
            self.app.notify("Conta não encontrada para a empresa atual.", severity="error")
            return

        tipo = self.query_one("#item_tipo", Select).value
        if tipo not in ("D", "C"):
            self.app.notify("Selecione Débito ou Crédito.", severity="error")
            return

        valor_raw = self.query_one("#item_valor", Input).value
        try:
            valor = relatorios.parse_decimal(valor_raw)
        except ValueError as exc:
            self.app.notify(str(exc), severity="error")
            return

        self.items.append(
            {
                "conta_id": int(conta["id"]),
                "codigo": conta["codigo"],
                "descricao": conta["descricao"],
                "tipo": tipo,
                "valor": valor,
            }
        )
        self._refresh_items_table()

        self.query_one("#item_conta", Input).value = ""
        self.query_one("#item_valor", Input).value = ""
        self.app.notify("Item incluído com sucesso!")

    def _excluir_item(self) -> None:
        table = self.query_one("#lancamento_item_table", DataTable)
        if table.cursor_row is None:
            self.app.notify("Selecione um item para excluir.", severity="error")
            return

        index = table.cursor_row
        if index < 0 or index >= len(self.items):
            self.app.notify("Item selecionado é inválido.", severity="error")
            return

        self.items.pop(index)
        self._refresh_items_table()
        self.app.notify("Item excluído.")

    def action_salvar_lancamento(self) -> None:
        self._salvar_lancamento()

    def _salvar_lancamento(self) -> None:
        if estado.EMPRESA_ATUAL is None:
            self.app.notify("Selecione uma empresa antes de salvar.", severity="error")
            return

        if not self.items:
            self.app.notify("Inclua pelo menos um item no lançamento.", severity="error")
            return

        data_input = self.query_one("#lanc_data", Input).value.strip()
        historico = self.query_one("#lanc_historico", Input).value.strip()
        if not historico:
            self.app.notify("Informe o histórico do lançamento.", severity="error")
            return

        try:
            data_norm = relatorios.normalize_date(data_input)
        except ValueError as exc:
            self.app.notify(str(exc), severity="error")
            return

        try:
            if self.lancamento_id is None:
                cursor = self.conn.execute(
                    """
                    INSERT INTO lancamento (empresa_id, data, historico)
                    VALUES (?, ?, ?)
                    """,
                    (estado.EMPRESA_ATUAL["id"], data_norm, historico),
                )
                lancamento_id = cursor.lastrowid
            else:
                lancamento_id = self.lancamento_id
                self.conn.execute(
                    """
                    UPDATE lancamento
                    SET data = ?, historico = ?, empresa_id = ?
                    WHERE id = ?
                    """,
                    (data_norm, historico, estado.EMPRESA_ATUAL["id"], lancamento_id),
                )
                self.conn.execute("DELETE FROM lancamento_item WHERE lancamento_id = ?", (lancamento_id,))

            for item in self.items:
                self.conn.execute(
                    """
                    INSERT INTO lancamento_item (lancamento_id, conta_id, tipo, valor)
                    VALUES (?, ?, ?, ?)
                    """,
                    (lancamento_id, item["conta_id"], item["tipo"], item["valor"]),
                )

            self.conn.commit()
            self.app.notify("Lançamento salvo com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar lançamento: {exc}", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_item_incluir":
            self._incluir_item()
        elif event.button.id == "btn_item_excluir":
            self._excluir_item()
        elif event.button.id == "btn_lanc_salvar":
            self._salvar_lancamento()

