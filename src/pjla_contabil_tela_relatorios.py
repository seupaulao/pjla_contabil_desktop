from __future__ import annotations

import sqlite3

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

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
        yield Label("PJLA Contabilidade - Relatórios - Em construção...")
        yield Footer()    

