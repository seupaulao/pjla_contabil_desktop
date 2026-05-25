from __future__ import annotations

import sqlite3
from typing import Any, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

import funcoes_relatorios as relatorios

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
