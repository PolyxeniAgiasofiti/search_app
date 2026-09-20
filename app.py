from shiny import App, ui, render, reactive

from ai_service import (
    analyze_topic,
    revise_topic_analysis
)

from database import (
    init_database,
    save_research_run,
    save_dataset_candidates
)

from data_service import search_public_datasets


# ---------------------------------------------------------
# DATABASE INITIALISATION
# ---------------------------------------------------------

database_ready = True
database_error_message = ""

try:
    init_database()

except Exception as error:
    database_ready = False
    database_error_message = str(error)


# ---------------------------------------------------------
# UI
# ---------------------------------------------------------

app_ui = ui.page_fluid(

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

        ui.output_ui("search_result"),

        class_="main-container"
    )
)


# ---------------------------------------------------------
# SERVER
# ---------------------------------------------------------

def server(input, output, session):

    revised_result = reactive.Value(None)

    definition_message = reactive.Value(None)
    data_message = reactive.Value(None)

    definition_approved = reactive.Value(False)
    data_approved = reactive.Value(False)

    research_run_id = reactive.Value(None)
    research_run_save_error = reactive.Value(None)

    discovered_datasets = reactive.Value(None)

    public_data_status_value = reactive.Value(None)


    # -----------------------------------------------------
    # INITIAL TOPIC ANALYSIS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # RESET WHEN A NEW SEARCH IS STARTED
    # -----------------------------------------------------

    @reactive.effect
    @reactive.event(input.search_button)
    def reset_review():

        revised_result.set(None)

        definition_message.set(None)
        data_message.set(None)

        definition_approved.set(False)
        data_approved.set(False)

        research_run_id.set(None)
        research_run_save_error.set(None)

        discovered_datasets.set(None)

        public_data_status_value.set(None)


    # -----------------------------------------------------
    # DISPLAY ANALYSIS
    # -----------------------------------------------------

    @output
    @render.ui
    def search_result():

        result = revised_result.get()

        if result is None:
            result = search_request()

        if not result:
            return None


        # OUT OF SCOPE
        if result.get("in_scope") is False:

            return ui.div(

                ui.tags.h3(
                    "Topic outside the scope"
                ),

                ui.tags.p(
                    result.get(
                        "scope_message",
                        "This topic is outside the scope of the Data Observatory."
                    )
                ),

                class_="scope-warning"
            )


        # BUILD DATA TARGET CARDS
        data_cards = []

        for item in result.get("data_needed", []):

            data_cards.append(

                ui.div(

                    ui.tags.h4(
                        item.get(
                            "name",
                            "Data target"
                        )
                    ),

                    ui.tags.p(
                        item.get(
                            "reason",
                            ""
                        )
                    ),

                    class_="data-card"
                )
            )


        return ui.div(

            # ---------------------------------------------
            # DEFINITION
            # ---------------------------------------------

            ui.div(

                ui.tags.h3(
                    "Definition"
                ),

                ui.tags.p(
                    result.get(
                        "definition",
                        ""
                    )
                ),

                ui.tags.hr(),

                ui.tags.p(
                    "Do you accept this definition?"
                ),

                ui.input_radio_buttons(
                    "definition_acceptance",
                    label=None,
                    choices={
                        "yes":
                            "Yes, I accept this definition",

                        "no":
                            "No, I would like to make changes"
                    }
                ),

                ui.input_text_area(
                    "definition_feedback",
                    label="Add your input if necessary",
                    placeholder=(
                        "Describe any corrections or changes "
                        "you would like to make..."
                    ),
                    rows=3,
                    width="100%"
                ),

                ui.input_action_button(
                    "confirm_definition",
                    "Confirm definition",
                    class_="btn-primary confirm-button"
                ),

                ui.output_ui(
                    "definition_status"
                ),

                class_="analysis-section"
            ),


            # ---------------------------------------------
            # DATA TARGETS
            # ---------------------------------------------

            ui.div(

                ui.tags.h3(
                    "Data targets"
                ),

                *data_cards,

                ui.tags.hr(),

                ui.tags.p(
                    "Do you accept these proposed data targets?"
                ),

                ui.input_radio_buttons(
                    "data_acceptance",
                    label=None,
                    choices={
                        "yes":
                            "Yes, I accept these data targets",

                        "no":
                            "No, I would like to make changes"
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

                ui.output_ui(
                    "data_status"
                ),

                class_="analysis-section"
            ),


            # ---------------------------------------------
            # PUBLIC DATA SEARCH
            # ---------------------------------------------

            ui.output_ui(
                "public_data_step"
            )
        )


    # -----------------------------------------------------
    # SAVE APPROVED RESEARCH RUN
    # -----------------------------------------------------

    def try_save_research_run():

        if not definition_approved.get():
            return

        if not data_approved.get():
            return

        if research_run_id.get() is not None:
            return

        research_run_save_error.set(None)

        if not database_ready:

            research_run_save_error.set(
                "Database is not configured, so the approved "
                "research run cannot be saved yet. Set "
                "DATABASE_URL and restart the app. Details: "
                + database_error_message
            )

            return


        result = revised_result.get()

        if result is None:
            result = search_request()

        if not result:
            return


        topic = input.search_query().strip()


        try:

            run_id = save_research_run(
                topic=topic,
                definition=result["definition"],
                data_targets=result["data_needed"]
            )

        except Exception as error:

            research_run_save_error.set(
                "The approved research run could not be saved. "
                "Check the PostgreSQL connection and Render logs. "
                "Details: "
                + str(error)
            )

            return


        research_run_id.set(
            run_id
        )


    # -----------------------------------------------------
    # DEFINITION CONFIRMATION
    # -----------------------------------------------------

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

            definition_approved.set(
                True
            )

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


        revised_result.set(
            new_result
        )

        definition_approved.set(
            False
        )

        data_approved.set(
            False
        )

        definition_message.set(
            "The definition has been revised. "
            "Please review it again."
        )

        data_message.set(
            "The data targets may have changed because "
            "the definition was revised. Please review "
            "them again."
        )


    # -----------------------------------------------------
    # DATA TARGET CONFIRMATION
    # -----------------------------------------------------

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

            data_approved.set(
                True
            )

            data_message.set(
                "Data targets approved."
            )

            try_save_research_run()

            return


        feedback = input.data_feedback()


        if not feedback or not feedback.strip():

            data_message.set(
                "Please describe what you would like "
                "to add, remove, or change."
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


        revised_result.set(
            new_result
        )

        data_approved.set(
            False
        )

        data_message.set(
            "The data targets have been revised. "
            "Please review them again."
        )


    # -----------------------------------------------------
    # DEFINITION STATUS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # DATA STATUS
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # SHOW PUBLIC DATA SEARCH BUTTON
    # -----------------------------------------------------

    @output
    @render.ui
    def public_data_step():

        if not definition_approved.get():
            return None

        if not data_approved.get():
            return None


        if not database_ready:

            return ui.div(

                ui.tags.h3(
                    "Database configuration needed"
                ),

                ui.tags.p(
                    "The definition and data targets are approved, "
                    "but the research run cannot be saved until "
                    "DATABASE_URL is configured."
                ),

                ui.tags.p(
                    database_error_message
                ),

                class_="analysis-section"
            )


        run_id = research_run_id.get()

        if run_id is None:

            save_error = research_run_save_error.get()

            if save_error:

                return ui.div(

                    ui.tags.h3(
                        "Research run was not saved"
                    ),

                    ui.tags.p(
                        save_error
                    ),

                    class_="analysis-section"
                )


            return ui.div(
                "Saving approved research request...",
                class_="review-message"
            )


        return ui.div(

            ui.tags.h3(
                "Ready to search for public data"
            ),

            ui.tags.p(
                "The definition and data targets have been "
                "approved. The application can now search "
                "for real publicly available datasets."
            ),

            ui.input_action_button(
                "search_public_data",
                "Search public data",
                class_="btn-primary search-button"
            ),

            ui.output_ui(
                "public_data_status"
            ),

            ui.output_ui(
                "public_dataset_results"
            ),

            class_="analysis-section"
        )


    # -----------------------------------------------------
    # PUBLIC DATA SEARCH
    # -----------------------------------------------------

    @reactive.effect
    @reactive.event(input.search_public_data)
    def handle_public_data_search():

        try:

            print(
                "PUBLIC DATA SEARCH STARTED"
            )


            public_data_status_value.set(
                "Searching for verified public datasets..."
            )


            run_id = research_run_id.get()


            if run_id is None:

                public_data_status_value.set(
                    "Error: the approved research run "
                    "has not been saved."
                )

                return


            result = revised_result.get()

            if result is None:
                result = search_request()


            if not result:

                public_data_status_value.set(
                    "Error: no approved analysis was found."
                )

                return


            topic = input.search_query().strip()


            print(
                "TOPIC:",
                topic
            )

            print(
                "NUMBER OF DATA TARGETS:",
                len(
                    result.get(
                        "data_needed",
                        []
                    )
                )
            )


            # ---------------------------------------------
            # SEARCH TAVILY + GEMINI FILTERING
            # ---------------------------------------------

            search_result = search_public_datasets(
                topic=topic,
                data_targets=result.get(
                    "data_needed",
                    []
                )
            )


            datasets = search_result.get(
                "datasets",
                []
            )


            print(
                "VERIFIED DATASETS FOUND:",
                len(datasets)
            )


            if not datasets:

                discovered_datasets.set(
                    []
                )

                public_data_status_value.set(
                    "The search completed successfully, "
                    "but no verified public datasets were found."
                )

                return


            # ---------------------------------------------
            # SAVE CANDIDATES TO POSTGRESQL
            # ---------------------------------------------

            saved_datasets = save_dataset_candidates(
                research_run_id=run_id,
                datasets=datasets
            )


            discovered_datasets.set(
                saved_datasets
            )


            public_data_status_value.set(
                f"Search completed. "
                f"Found {len(saved_datasets)} "
                f"verified public datasets."
            )


            print(
                "PUBLIC DATA SEARCH FINISHED"
            )


        except Exception as e:

            print(
                "PUBLIC DATA SEARCH ERROR:",
                repr(e)
            )


            public_data_status_value.set(
                "Public data search failed: "
                + str(e)
            )


    # -----------------------------------------------------
    # PUBLIC DATA STATUS
    # -----------------------------------------------------

    @output
    @render.ui
    def public_data_status():

        message = public_data_status_value.get()

        if not message:
            return None


        return ui.div(
            message,
            class_="review-message"
        )


    # -----------------------------------------------------
    # DISPLAY PUBLIC DATASET RESULTS
    # -----------------------------------------------------

    @output
    @render.ui
    def public_dataset_results():

        datasets = discovered_datasets.get()


        if datasets is None:
            return None


        if len(datasets) == 0:

            return ui.div(
                "No verified dataset candidates were retained.",
                class_="review-message"
            )


        cards = []


        for dataset in datasets:

            source_url = dataset.get(
                "source_url",
                ""
            )


            card_elements = [

                ui.tags.h4(
                    dataset.get(
                        "title",
                        "Untitled dataset"
                    )
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Data target: "
                    ),

                    dataset.get(
                        "data_target",
                        ""
                    )
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Publisher: "
                    ),

                    dataset.get(
                        "publisher",
                        "Unknown"
                    )
                ),

                ui.tags.p(
                    dataset.get(
                        "description",
                        ""
                    )
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Geographic coverage: "
                    ),

                    dataset.get(
                        "geographic_coverage",
                        "Unknown"
                    )
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Time coverage: "
                    ),

                    dataset.get(
                        "time_coverage",
                        "Unknown"
                    )
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Format: "
                    ),

                    dataset.get(
                        "format",
                        "Unknown"
                    )
                )
            ]


            if source_url:

                card_elements.append(

                    ui.tags.a(
                        "Open original source",
                        href=source_url,
                        target="_blank",
                        class_="dataset-link"
                    )
                )


            cards.append(

                ui.div(
                    *card_elements,
                    class_="data-card"
                )
            )


        return ui.div(

            ui.tags.h3(
                "Public datasets found"
            ),

            ui.tags.p(
                "These sources passed the current "
                "automatic verification process. "
                "They should still be reviewed before "
                "the actual data are downloaded."
            ),

            *cards
        )


# ---------------------------------------------------------
# APP
# ---------------------------------------------------------

app = App(
    app_ui,
    server
)
