from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from typing import Any, Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, Label, Input, Static, DataTable, Select
from textual.screen import Screen
from textual.app import App
from textual.binding import Binding

import funcoes_relatorios as relatorios


APP_TITLE = "PJLA Contabilidade OFFLINE"
EMPRESA_ATUAL: Optional[sqlite3.Row] = None


# ============= TEXTUAL UI COMPONENTS =============

class FormField(Container):
    """Form field component with label and input."""
    
    def __init__(self, label: str, field_type: str = "text", required: bool = False, value: str = "", **kwargs):
        super().__init__(**kwargs)
        self.label = label
        self.field_type = field_type
        self.required = required
        self.value = value
        self.input_widget: Optional[Input] = None

    def compose(self) -> ComposeResult:
        yield Label(f"{self.label}{'*' if self.required else ''}")
        if self.field_type == "text":
            self.input_widget = Input(value=self.value, id=self.label.lower().replace(" ", "_"))
            yield self.input_widget
        elif self.field_type == "date":
            self.input_widget = Input(value=self.value, placeholder="DD/MM/AAAA", id=self.label.lower().replace(" ", "_"))
            yield self.input_widget

    def get_value(self) -> str:
        return self.input_widget.value if self.input_widget else ""

class MessageBox(Screen):
    """Simple message display screen."""
    
    def __init__(self, title: str, message: str, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.message_text = message

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self.title_text)
            yield Label(self.message_text)
            with Horizontal():
                yield Button("OK", id="btn_ok")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_ok":
            self.app.pop_screen()


class ConfirmDialog(Screen):
    """Confirmation dialog screen that returns boolean result."""

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        background: $surface;
        border: thick $error;
        padding: 1 2;
        width: 60;
        height: auto;
    }
    ConfirmDialog #msg {
        text-align: center;
        margin-bottom: 1;
    }
    ConfirmDialog Horizontal {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    ConfirmDialog Button {
        margin: 0 1;
    }
    """

    def __init__(self, title: str, message: str, **kwargs):
        super().__init__(**kwargs)
        self.title_text = title
        self.message_text = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.title_text, id="title")
            yield Static(self.message_text, id="msg")
            with Horizontal():
                yield Button("Sim", id="btn_yes", variant="primary")
                yield Button("Não", id="btn_no", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_yes":
            self.dismiss(True)
        elif event.button.id == "btn_no":
            self.dismiss(False)


# ============= FORMS =============

class EmpresaForm(Static):
    """Form for empresa data entry."""
    
    def __init__(self, existing: Optional[sqlite3.Row] = None, **kwargs):
        super().__init__(**kwargs)
        self.existing = existing
        self.form_fields: dict[str, FormField] = {}

    def compose(self) -> ComposeResult:
        yield Label("Informações da Empresa")
        with ScrollableContainer():
            for field_name, label, required, field_type in relatorios.EMPRESA_FIELDS:
                value = ""
                if self.existing:
                    val = self.existing[field_name]
                    if field_type == "date" and val:
                        value = relatorios.display_date(val)
                    elif val:
                        value = str(val)
                
                form_field = FormField(label, field_type=field_type, required=required, value=value)
                self.form_fields[field_name] = form_field
                yield form_field

    def get_data(self) -> dict[str, Any]:
        data = {}
        for field_name, label, required, field_type in relatorios.EMPRESA_FIELDS:
            form_field = self.form_fields[field_name]
            value = form_field.get_value().strip()
            
            if not value and required:
                raise ValueError(f"Campo '{label}' é obrigatório.")
            
            if field_type == "date" and value:
                value = relatorios.normalize_date(value)
            
            data[field_name] = value or None
        
        return data


class ContaForm(Static):
    """Form for conta data entry."""
    
    def __init__(self, existing: Optional[sqlite3.Row] = None, **kwargs):
        super().__init__(**kwargs)
        self.existing = existing
        self.fields: dict[str, Input] = {}

    def compose(self) -> ComposeResult:
        yield Label("Dados da Conta")
        with ScrollableContainer():
            field_configs = [
                ("empresa_id", "Código da Empresa", True),
                ("codigo", "Código da Conta (01.01.01)", True),
                ("descricao", "Descrição", True),
                ("tipo", "Tipo [A/S]", True),
                ("natureza", "Natureza [D/C]", True),
                ("grupo", "Grupo", False),
                ("dre_grupo", "Grupo DRE", False),
                ("subgrupo", "Subgrupo", False),
                ("fluxo_caixa_tipo", "Tipo Fluxo Caixa", False),
                ("nivel", "Nível", False),
                ("conta_pai_id", "Conta PAI", False),
                ("codigo_referencial", "Código Referencial", False),
            ]
            
            for field_id, label, required in field_configs:
                value = ""
                if self.existing and field_id in self.existing.keys():
                    val = self.existing[field_id]
                    value = str(val) if val else ""
                
                with Horizontal():
                    yield Label(f"{label}{'*' if required else ''}", classes="label")
                    input_field = Input(value=value, id=field_id)
                    self.fields[field_id] = input_field
                    yield input_field

    def get_data(self) -> dict[str, Any]:
        data = {}
        required_fields = ["empresa_id", "codigo", "descricao", "tipo", "natureza"]
        
        for field_id, input_widget in self.fields.items():
            value = input_widget.value.strip()
            if not value and field_id in required_fields:
                raise ValueError(f"Campo {field_id} é obrigatório.")
            data[field_id] = value or None
        
        return data


# ============= SCREENS =============

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


class TagFormScreen(Screen):
    """Screen for tags form."""

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
        with Container():
            yield Label("Empresa ID")
            yield Input(value=str(self.existing["empresa_id"] or "") if self.existing else "", id="tag_empresa_id")
            yield Label("Nome*")
            yield Input(value=self.existing["name"] if self.existing else "", id="tag_name")
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
        empresa_id = self.query_one("#tag_empresa_id", Input).value.strip() or None
        name = self.query_one("#tag_name", Input).value.strip()
        if not name:
            self.app.notify("Nome da tag é obrigatório.", severity="error")
            return

        try:
            if self.existing:
                self.conn.execute("UPDATE tags SET empresa_id = ?, name = ? WHERE id = ?", (empresa_id, name, self.existing["id"]))
            else:
                self.conn.execute("INSERT INTO tags (id, empresa_id, name) VALUES (?, ?, ?)", (str(uuid.uuid4()), empresa_id, name))
            self.conn.commit()
            self.app.notify("Tag salva com sucesso!")
            self.dismiss(True)
        except sqlite3.DatabaseError as exc:
            self.conn.rollback()
            self.app.notify(f"Erro ao salvar tag: {exc}", severity="error")


class TagListScreen(Screen):
    """Screen for listing tags."""

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
        yield DataTable(id="tag_table")
        with Horizontal():
            yield Button("Novo", id="btn_novo", variant="primary")
            yield Button("Editar", id="btn_editar", disabled=True)
            yield Button("Excluir", id="btn_excluir", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tag_table", DataTable)
        table.add_columns("ID", "Empresa", "Nome")
        table.cursor_type = "row"
        self.load_data()

    def load_data(self) -> None:
        table = self.query_one("#tag_table", DataTable)
        table.clear()
        rows = relatorios.fetch_all(self.conn, "SELECT id, empresa_id, name FROM tags ORDER BY name")
        for row in rows:
            table.add_row(str(row["id"]), str(row["empresa_id"] or ""), row["name"])
        self._selected_id = None
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self._selected_id is not None
        self.query_one("#btn_editar", Button).disabled = not has_selection
        self.query_one("#btn_excluir", Button).disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row = self.query_one("#tag_table", DataTable).get_row(event.row_key)
        self._selected_id = str(row[0])
        self._update_buttons()

    def action_novo(self) -> None:
        self.app.push_screen(TagFormScreen(self.conn), self._on_form_closed)

    def action_editar(self) -> None:
        if self._selected_id is None:
            return
        row = relatorios.fetch_one(self.conn, "SELECT * FROM tags WHERE id = ?", (self._selected_id,))
        if row:
            self.app.push_screen(TagFormScreen(self.conn, existing=row), self._on_form_closed)

    def action_excluir(self) -> None:
        if self._selected_id is None:
            return

        def handle_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.conn.execute("DELETE FROM tags WHERE id = ?", (self._selected_id,))
                self.conn.commit()
                self.load_data()
                self.app.notify("Tag excluída com sucesso!")
            except sqlite3.DatabaseError as exc:
                self.conn.rollback()
                self.app.notify(f"Erro ao excluir tag: {exc}", severity="error")

        self.app.push_screen(ConfirmDialog("Confirmar exclusão", "Deseja excluir esta tag?"), handle_confirm)

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

        if EMPRESA_ATUAL is None:
            return

        rows = relatorios.fetch_all(
            self.conn,
            """
            SELECT id, data, historico
            FROM lancamento
            WHERE empresa_id = ?
            ORDER BY data, id
            """,
            (EMPRESA_ATUAL["id"],),
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
        if EMPRESA_ATUAL is None:
            self.app.notify("Selecione uma empresa antes de lançar.", severity="error")
            return
        self.app.push_screen(LancamentoEditScreen(self.conn), self._on_edit_closed)

    def action_editar_lancamento(self) -> None:
        if EMPRESA_ATUAL is None:
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
        if EMPRESA_ATUAL is None:
            return

        lanc = relatorios.fetch_one(
            self.conn,
            """
            SELECT id, data, historico
            FROM lancamento
            WHERE id = ? AND empresa_id = ?
            """,
            (self.lancamento_id, EMPRESA_ATUAL["id"]),
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
        if EMPRESA_ATUAL is None:
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
                (EMPRESA_ATUAL["id"], int(text)),
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
            (EMPRESA_ATUAL["id"], text, text, f"%{text}%", text, text),
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
        if EMPRESA_ATUAL is None:
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
        if EMPRESA_ATUAL is None:
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
                    (EMPRESA_ATUAL["id"], data_norm, historico),
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
                    (data_norm, historico, EMPRESA_ATUAL["id"], lancamento_id),
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

class RelatoriosScreen(Screen):
    """Screen for displaying Relatórios."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Voltar"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Relatórios - Em construção...")
        yield Footer()    

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
        global EMPRESA_ATUAL

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

        EMPRESA_ATUAL = empresa
        self.app.notify(f"Empresa '{empresa['nome']}' definida com sucesso!")
        self.dismiss(empresa)

class MainScreen(Screen):
    """Main menu screen."""
    
    BINDINGS = [
        Binding("q", "quit", "Sair"),
        Binding("a", "livro_diario", "Livro Diário"),
        Binding("b", "relatorios", "Relatórios"),
        Binding("c", "cadastro_empresa", "Empresa"),
        Binding("d", "set_empresa", "Definir Empresa"),
        Binding("e", "plano_contas", "Contas"),
        Binding("f", "plano_referencial", "Plano Referencial"),
        Binding("g", "usuarios", "Usuários"),
        Binding("h", "centro_custos", "Centro de Custos"),
        Binding("i", "tags", "Tags"),
        Binding("j", "certificados_digitais", "Certificados Digitais"),
        Binding("k", "assinaturas_digitais", "Assinaturas Digitais"),
    ]

    def __init__(self, conn: sqlite3.Connection, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield Label("PJLA Contabilidade OFFLINE", id="title")
            yield Label(self._empresa_info_text(), id="empresa_info")
        yield Footer()

    def _empresa_info_text(self) -> str:
        if EMPRESA_ATUAL is None:
            return "Selecione uma empresa"
        return f"Empresa: {EMPRESA_ATUAL['nome']}"

    def _refresh_empresa_info(self) -> None:
        empresa_info = self.query_one("#empresa_info", Label)
        empresa_info.update(self._empresa_info_text())

    def on_mount(self) -> None:
        self._refresh_empresa_info()

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


# ============= MAIN APP =============

class ContabilidadeApp(App):
    """Main application."""
    
    TITLE = "PJLA Contabilidade OFFLINE"
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #title {
        width: 100%;
        height: 3;
        content-align: center middle;
        background: $accent;
        color: $text;
    }
    
    .menu {
        align: center middle;
        width: 40;
        height: auto;
    }
    
    .menu Button {
        width: 100%;
        margin: 1 0;
    }
    
    Label {
        width: 100%;
    }
    
    FormField {
        height: auto;
        margin: 1 0;
    }
    
    FormField Label {
        width: 20;
        margin-right: 1;
    }
    
    Input {
        width: 60;
    }
    
    DataTable {
        height: 1fr;
    }
    
    .label {
        width: 25;
        text-align: right;
        margin-right: 1;
    }

    #lancamento_item_actions {
        width: 100%;
        align: center middle;
        margin: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.conn = relatorios.connect_db()

    def on_mount(self) -> None:
        self.push_screen(MainScreen(self.conn))

    def on_unmount(self) -> None:
        self.conn.close()


if __name__ == "__main__":
    app = ContabilidadeApp()
    app.run()
