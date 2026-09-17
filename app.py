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

        .search-box {
            width: 100%;
            max-width: 760px;
            margin: 0 auto;
        }

        .search-box textarea {
            width: 100%;
            min-height: 130px;
            padding: 18px 20px;
            font-size: 17px;
            line-height: 1.5;
            border: 1px solid #c8c8c8;
            border-radius: 16px;
            resize: vertical;
            box-sizing: border-box;
            background-color: white;
        }

        .search-box textarea:focus {
            border-color: #777;
            outline: none;
            box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.05);
        }

        .search-button {
            margin-top: 22px;
            padding: 12px 35px;
            font-size: 17px;
            border-radius: 8px;
        }

        .result-box {
            max-width: 760px;
            margin: 40px auto 0 auto;
            font-size: 18px;
            text-align: left;
        }
    """),

    ui.div(

        ui.div(
            "Data Observatory",
            class_="app-title"
        ),

        ui.div(
            "What topic would you like to analyze today?",
            class_="question-title"
        ),

        ui.div(
            ui.input_text_area(
                "search_query",
                label=None,
                placeholder="Describe the topic you would like to analyze...",
                rows=5,
                width="100%"
            ),
            class_="search-box"
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