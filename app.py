from shiny import App

from ui import app_ui
from backend import server


app = App(
    app_ui,
    server
)
