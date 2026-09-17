from shiny import App, ui, render, reactive
from ai_service import analyze_topic , revise_topic_analysis

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

        .analysis-section {
    margin-top: 35px;
    text-align: left;
}

.analysis-section h3 {
    font-size: 24px;
    margin-bottom: 18px;
}

.data-card {
    background-color: white;
    border: 1px solid #dddddd;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
}

.data-card h4 {
    margin-top: 0;
    margin-bottom: 8px;
    font-size: 18px;
}

.data-card p {
    margin-bottom: 0;
    color: #555;
    line-height: 1.5;
}
.verification-section {
    margin-top: 45px;
    padding: 25px;
    background-color: white;
    border: 1px solid #dddddd;
    border-radius: 14px;
    text-align: left;
}

.verification-section h3 {
    margin-top: 0;
    margin-bottom: 12px;
}

.verification-section textarea {
    margin-top: 10px;
    border-radius: 10px;
}

.confirm-button {
    margin-top: 15px;
    padding: 10px 28px;
    border-radius: 8px;
}

.review-message {
    margin-top: 20px;
    padding: 14px 18px;
    background-color: #f1f3f5;
    border-radius: 10px;
    font-weight: 500;
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

    revised_result = reactive.Value(None)
    review_message = reactive.Value(None)


    # -----------------------------------
    # FIRST ANALYSIS
    # -----------------------------------

    @reactive.calc
    @reactive.event(input.search_button)
    def search_request():

        topic = input.search_query()

        if not topic:
            return None

        topic = topic.strip()

        if not topic:
            return None

        result = analyze_topic(topic)

        return result


    # -----------------------------------
    # RESET WHEN USER MAKES A NEW SEARCH
    # -----------------------------------

    @reactive.effect
    @reactive.event(input.search_button)
    def reset_review():

        revised_result.set(None)
        review_message.set(None)


    # -----------------------------------
    # DISPLAY ANALYSIS
    # -----------------------------------

    @output
    @render.ui
    def search_result():

        result = revised_result.get()

        if result is None:
            result = search_request()

        if not result:
            return None

        data_cards = []

        for item in result["data_needed"]:

            data_cards.append(
                ui.div(
                    ui.tags.h4(item["name"]),
                    ui.tags.p(item["reason"]),
                    class_="data-card"
                )
            )

        return ui.div(

            # Definition
            ui.div(
                ui.tags.h3("Definition"),
                ui.tags.p(result["definition"]),
                class_="analysis-section"
            ),

            # Data requirements
            ui.div(
                ui.tags.h3("Data needed for the study"),
                *data_cards,
                class_="analysis-section"
            ),

            # User verification
            ui.div(

                ui.tags.h3("Review the analysis"),

                ui.tags.p(
                    "Do you accept the definition and the proposed data requirements?"
                ),

                ui.input_radio_buttons(
                    "analysis_acceptance",
                    label=None,
                    choices={
                        "yes": "Yes, I accept them",
                        "no": "No, I would like to make changes"
                    }
                ),

                ui.input_text_area(
                    "user_feedback",
                    label="Add your input if necessary",
                    placeholder=(
                        "Add any corrections, comments, "
                        "or additional data requirements here..."
                    ),
                    rows=4,
                    width="100%"
                ),

                ui.input_action_button(
                    "confirm_analysis",
                    "Confirm",
                    class_="btn-primary confirm-button"
                ),

                ui.output_ui("review_status"),

                class_="verification-section"
            )
        )


    # -----------------------------------
    # HANDLE USER CONFIRMATION
    # -----------------------------------

    @reactive.effect
    @reactive.event(input.confirm_analysis)
    def handle_confirmation():

        choice = input.analysis_acceptance()

        if not choice:
            review_message.set(
                "Please select whether you accept the analysis."
            )
            return

        # User accepts the analysis
        if choice == "yes":

            review_message.set(
                "Analysis confirmed."
            )

            return

        # User wants changes
        feedback = input.user_feedback()

        if not feedback or not feedback.strip():

            review_message.set(
                "Please describe what you would like to change."
            )

            return

        feedback = feedback.strip()

        current_result = revised_result.get()

        if current_result is None:
            current_result = search_request()

        topic = input.search_query().strip()

        new_result = revise_topic_analysis(
            topic,
            current_result,
            feedback
        )

        revised_result.set(new_result)

        review_message.set(
            "The analysis has been revised. Please review it again."
        )


    # -----------------------------------
    # DISPLAY REVIEW MESSAGE
    # -----------------------------------

    @output
    @render.ui
    def review_status():

        message = review_message.get()

        if not message:
            return None

        return ui.div(
            message,
            class_="review-message"
        )


    app = App(app_ui, server)