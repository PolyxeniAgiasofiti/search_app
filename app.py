from database import (
    init_database,
    save_research_run,
    save_dataset_candidates
)
from shiny import App, ui, render, reactive
from ai_service import analyze_topic, revise_topic_analysis
from data_service import search_public_datasets

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
            background-color: white;
            border: 1px solid #dddddd;
            border-radius: 14px;
            padding: 25px;
        }

        .analysis-section h3 {
            font-size: 24px;
            margin-top: 0;
            margin-bottom: 18px;
        }

        .data-card {
            background-color: #fafafa;
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

        .scope-warning {
            margin-top: 35px;
            padding: 25px;
            background-color: white;
            border: 1px solid #dddddd;
            border-radius: 14px;
            text-align: left;
        }

        hr {
            margin-top: 25px;
            margin-bottom: 20px;
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

    definition_message = reactive.Value(None)
    data_message = reactive.Value(None)

    definition_approved = reactive.Value(False)
    data_approved = reactive.Value(False)

    research_run_id = reactive.Value(None)
    discovered_datasets = reactive.Value(None)

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

        return analyze_topic(topic)


    # -----------------------------------
    # RESET WHEN USER MAKES A NEW SEARCH
    # -----------------------------------

    @reactive.effect
    @reactive.event(input.search_button)
    def reset_review():

        revised_result.set(None)

        definition_message.set(None)
        data_message.set(None)

        definition_approved.set(False)
        data_approved.set(False)

        research_run_id.set(None)
        discovered_datasets.set(None)

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


        # Guardrail result
        if result.get("in_scope") is False:

            return ui.div(
                ui.tags.h3("Topic outside the scope"),
                ui.tags.p(
                    result.get(
                        "scope_message",
                        "This topic is outside the scope of the Data Observatory."
                    )
                ),
                class_="scope-warning"
            )


        # Create cards for data targets
        data_cards = []

        for item in result.get("data_needed", []):

            data_cards.append(
                ui.div(
                    ui.tags.h4(item["name"]),
                    ui.tags.p(item["reason"]),
                    class_="data-card"
                )
            )


        return ui.div(

            # ===================================
            # DEFINITION REVIEW
            # ===================================

            ui.div(

                ui.tags.h3("Definition"),

                ui.tags.p(
                    result["definition"]
                ),

                ui.tags.hr(),

                ui.tags.p(
                    "Do you accept this definition?"
                ),

                ui.input_radio_buttons(
                    "definition_acceptance",
                    label=None,
                    choices={
                        "yes": "Yes, I accept this definition",
                        "no": "No, I would like to make changes"
                    }
                ),

                ui.input_text_area(
                    "definition_feedback",
                    label="Add your input if necessary",
                    placeholder=(
                        "Describe any corrections or changes "
                        "you would like to make to the definition..."
                    ),
                    rows=3,
                    width="100%"
                ),

                ui.input_action_button(
                    "confirm_definition",
                    "Confirm definition",
                    class_="btn-primary confirm-button"
                ),

                ui.output_ui("definition_status"),

                class_="analysis-section"
            ),


            # ===================================
            # DATA TARGETS REVIEW
            # ===================================

            ui.div(

                ui.tags.h3("Data targets"),

                *data_cards,

                ui.tags.hr(),

                ui.tags.p(
                    "Do you accept these proposed data targets?"
                ),

                ui.input_radio_buttons(
                    "data_acceptance",
                    label=None,
                    choices={
                        "yes": "Yes, I accept these data targets",
                        "no": "No, I would like to make changes"
                    }
                ),

                ui.input_text_area(
                    "data_feedback",
                    label="Add your input if necessary",
                    placeholder=(
                        "Add, remove, or modify data targets. "
                        "For example: Add housing affordability "
                        "and wealth distribution by age."
                    ),
                    rows=4,
                    width="100%"
                ),

                ui.input_action_button(
                    "confirm_data",
                    "Confirm data targets",
                    class_="btn-primary confirm-button"
                ),

                ui.output_ui("data_status"),

                class_="analysis-section"
            ),
            ui.output_ui("public_data_step")
        )


    # -----------------------------------
    # SAVE APPROVED RESEARCH RUN
    # -----------------------------------

    def try_save_research_run():

        if not definition_approved.get():
            return

        if not data_approved.get():
            return

        # Prevent saving the same run twice
        if research_run_id.get() is not None:
            return

        result = revised_result.get()

        if result is None:
            result = search_request()

        if not result:
            return

        topic = input.search_query().strip()

        run_id = save_research_run(
            topic=topic,
            definition=result["definition"],
            data_targets=result["data_needed"]
        )

        research_run_id.set(run_id)


    # -----------------------------------
    # HANDLE DEFINITION CONFIRMATION
    # -----------------------------------

    @reactive.effect
    @reactive.event(input.confirm_definition)
    def handle_definition_confirmation():

        choice = input.definition_acceptance()

        if not choice:
            definition_message.set(
                "Please select whether you accept the definition."
            )
            return


        if choice == "yes":

            definition_approved.set(True)

            definition_message.set(
                "Definition approved."
            )

            try_save_research_run()

            return


        feedback = input.definition_feedback()

        if not feedback or not feedback.strip():

            definition_message.set(
                "Please describe what you would like to change."
            )

            return


        current_result = revised_result.get()

        if current_result is None:
            current_result = search_request()


        topic = input.search_query().strip()


        new_result = revise_topic_analysis(
            topic,
            current_result,
            feedback.strip(),
            target="definition"
        )


        revised_result.set(new_result)

        definition_approved.set(False)

        definition_message.set(
            "The definition has been revised. Please review it again."
        )


    # -----------------------------------
    # HANDLE DATA TARGET CONFIRMATION
    # -----------------------------------

    @reactive.effect
    @reactive.event(input.confirm_data)
    def handle_data_confirmation():

        choice = input.data_acceptance()

        if not choice:
            data_message.set(
                "Please select whether you accept the data targets."
            )
            return


        if choice == "yes":

            data_approved.set(True)

            data_message.set(
                "Data targets approved."
            )

            try_save_research_run()

            return


        feedback = input.data_feedback()

        if not feedback or not feedback.strip():

            data_message.set(
                "Please describe what you would like to add, remove, or change."
            )

            return


        current_result = revised_result.get()

        if current_result is None:
            current_result = search_request()


        topic = input.search_query().strip()


        new_result = revise_topic_analysis(
            topic,
            current_result,
            feedback.strip(),
            target="data"
        )


        revised_result.set(new_result)

        data_approved.set(False)

        data_message.set(
            "The data targets have been revised. Please review them again."
        )


    # -----------------------------------
    # DISPLAY DEFINITION STATUS
    # -----------------------------------

    @output
    @render.ui
    def definition_status():

        message = definition_message.get()

        if not message:
            return None

        return ui.div(
            message,
            class_="review-message"
        )


    # -----------------------------------
    # DISPLAY DATA STATUS
    # -----------------------------------

    @output
    @render.ui
    def data_status():

        message = data_message.get()

        if not message:
            return None

        return ui.div(
            message,
            class_="review-message"
        )
        # -----------------------------------
    # PUBLIC DATA SEARCH STEP
    # -----------------------------------

    @output
    @render.ui
    def public_data_step():

        if not definition_approved.get():
            return None

        if not data_approved.get():
            return None

        run_id = research_run_id.get()

        if run_id is None:
            return None

        return ui.div(

            ui.tags.h3(
                "Ready to search for public data"
            ),

            ui.tags.p(
                "The definition and data targets have been approved "
                "and the research run has been saved."
            ),

            ui.input_action_button(
                "search_public_data",
                "Search public data",
                class_="btn-primary search-button"
            ),
            ui.output_ui("public_dataset_results"),
            class_="analysis-section"
        )    # -----------------------------------
    # PUBLIC DATA SEARCH STEP
    # -----------------------------------


    @output
    @render.ui
    def public_dataset_results():

        datasets = discovered_datasets.get()

        if not datasets:
            return None

        cards = []

        for dataset in datasets:

            cards.append(
                ui.div(

                    ui.tags.h4(
                        dataset["title"]
                    ),

                    ui.tags.p(
                        ui.tags.strong("Data target: "),
                        dataset.get("data_target", "")
                    ),

                    ui.tags.p(
                        ui.tags.strong("Publisher: "),
                        dataset.get("publisher", "")
                    ),

                    ui.tags.p(
                        dataset.get("description", "")
                    ),

                    ui.tags.p(
                        ui.tags.strong("Geographic coverage: "),
                        dataset.get(
                            "geographic_coverage",
                            "Unknown"
                        )
                    ),

                    ui.tags.p(
                        ui.tags.strong("Time coverage: "),
                        dataset.get(
                            "time_coverage",
                            "Unknown"
                        )
                    ),

                    ui.tags.p(
                        ui.tags.strong("Format: "),
                        dataset.get(
                            "format",
                            "Unknown"
                        )
                    ),

                    ui.tags.a(
                        "Open original source",
                        href=dataset["source_url"],
                        target="_blank"
                    ),

                    class_="data-card"
                )
            )

        return ui.div(

            ui.tags.h3(
                "Public datasets found"
            ),

            *cards,

            class_="analysis-section"
        )   

init_database()
app = App(app_ui, server)
