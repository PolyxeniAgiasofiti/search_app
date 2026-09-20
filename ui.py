from shiny import ui


# ---------------------------------------------------------
# APPLICATION UI
# ---------------------------------------------------------

app_ui = ui.page_fluid(

    # -----------------------------------------------------
    # GLOBAL STYLING
    # -----------------------------------------------------

    ui.tags.style(
        """
        body {
            background-color: #f7f7f7;
            font-family: Arial, sans-serif;
        }

        .main-container {
            max-width: 850px;
            margin: 0 auto;
            padding-top: 100px;
            padding-bottom: 100px;
        }

        .main-title {
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .main-question {
            font-size: 22px;
            margin-bottom: 25px;
        }

        .search-button,
        .confirm-button {
            margin-top: 15px;
            margin-bottom: 15px;
        }

        .analysis-section {
            background: white;
            padding: 25px;
            margin-top: 25px;
            border-radius: 12px;
            border: 1px solid #e2e2e2;
        }

        .data-card {
            background: #fafafa;
            padding: 18px;
            margin-top: 14px;
            margin-bottom: 14px;
            border-radius: 8px;
            border: 1px solid #dddddd;
        }

        .review-message {
            margin-top: 15px;
            padding: 12px;
            background: #f1f1f1;
            border-radius: 8px;
        }

        .scope-warning {
            background: #fff4e5;
            border: 1px solid #f0c36d;
            padding: 20px;
            border-radius: 10px;
            margin-top: 25px;
        }

        .dataset-link {
            display: inline-block;
            margin-top: 8px;
        }
        """
    ),

    # -----------------------------------------------------
    # MAIN PAGE
    # -----------------------------------------------------

    ui.div(

        ui.tags.h1(
            "Data Observatory",
            class_="main-title"
        ),

        ui.tags.p(
            "What topic would you like to analyze today?",
            class_="main-question"
        ),

        ui.input_text_area(
            "search_query",
            label=None,
            placeholder="For example: Gerontocracy",
            rows=5,
            width="100%"
        ),

        ui.input_action_button(
            "search_button",
            "Search",
            class_="btn-primary search-button"
        ),

        # Dynamic content is produced by app.py
        ui.output_ui(
            "search_result"
        ),

        class_="main-container"
    )
)