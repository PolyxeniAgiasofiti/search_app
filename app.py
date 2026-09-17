from shiny import App, ui, render, reactive


app_ui = ui.page_fluid(

    ui.tags.style("""
        body {
            background-color: #f7f7f7;
            font-family: Arial, sans-serif;
        }

        .main-container {
            max-width: 850px;
            margin: 0 auto;
            padding-top: 140px;
            text-align: center;
        }

        .app-title {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 2px;
            margin-bottom: 35px;
            color: #555;
        }

        .question-title {
            font-size: 36px;
            font-weight: 600;
            margin-bottom: 30px;
            color: #222;
        }

        .search-button {
            margin-top: 15px;
            padding: 12px 35px;
            font-size: 17px;
            border-radius: 8px;
        }

        .result-box {
            margin-top: 40px;
            font-size: 18px;
            text-align: left;
        }

        input.form-control {
            height: 60px;
            font-size: 18px;
            padding: 15px 20px;
            border-radius: 12px;
        }
    """),

    ui.div(

        ui.div(
            "Data Observatory",
            class_="app-title"
        ),

        ui.div(
            "What would you like to search today?",
            class_="question-title"
        ),

        ui.input_text(
            "search_query",
            label=None,
            placeholder="Describe what you would like to explore..."
        ),

        ui.input_action_button(
            "search_button",
            "Search",
            class_="btn-primary search-button"
        ),

        ui.div(
            ui.output_ui("search_result"),
            class_="result-box"
        ),

        class_="main-container"
    )
)


def server(input, output, session):

    @reactive.calc
    @reactive.event(input.search_button)
    def search_request():
        query = input.search_query()

        if not query:
            return None

        return query.strip()


    @output
    @render.ui
    def search_result():

        query = search_request()

        if not query:
            return None

        return ui.div(
            ui.tags.strong("You searched for:"),
            ui.tags.p(query)
        )


app = App(app_ui, server)