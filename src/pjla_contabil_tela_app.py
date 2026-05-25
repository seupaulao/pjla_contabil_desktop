from __future__ import annotations

import sqlite3
from typing import Type

from textual.app import App
from textual.screen import Screen

import funcoes_relatorios as relatorios


class ContabilidadeApp(App):
    """Main application bootstrap."""

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

    #empresa_info {
        width: 100%;
        height: 1;
        content-align: center middle;
        background: $surface;
    }

    #menu_container {
        align: center middle;
        height: 1fr;
        width: 100%;
    }

    #menu_label {
        width: 100%;
        height: 1;
        content-align: center middle;
        margin-bottom: 1;
    }

    #menu_select {
        width: 50;
        height: auto;
        border: solid $accent;
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

    def __init__(self, main_screen_class: Type[Screen]):
        super().__init__()
        self.conn: sqlite3.Connection = relatorios.connect_db()
        self._main_screen_class = main_screen_class

    def on_mount(self) -> None:
        self.push_screen(self._main_screen_class(self.conn))

    def on_unmount(self) -> None:
        self.conn.close()


def run_app(main_screen_class: Type[Screen]) -> None:
    app = ContabilidadeApp(main_screen_class)
    app.run()
