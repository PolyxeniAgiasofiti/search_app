from shiny import ui, render, reactive

from ai_service import (
    analyze_topic,
    revise_topic_analysis
)

from database import (
    init_database,
    save_research_run,
    save_dataset_candidates,
    update_dataset_review_status,
    update_dataset_retrieval,
    replace_dataset_rows,
    get_dataset_rows
)

from data_service import search_public_datasets
from ingestion_service import retrieve_dataset
from manual_source_service import analyse_user_provided_source


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
# SERVER
# ---------------------------------------------------------

def server(input, output, session):

    revised_result = reactive.Value(None)

    definition_message = reactive.Value(None)
    data_message = reactive.Value(None)
    manual_source_message = reactive.Value(None)
    manual_target_clicks = reactive.Value({})

    definition_approved = reactive.Value(False)
    data_approved = reactive.Value(False)

    research_run_id = reactive.Value(None)
    research_run_save_error = reactive.Value(None)

    discovered_datasets = reactive.Value(None)
    dataset_review_clicks = reactive.Value({})
    dataset_retrieval_clicks = reactive.Value({})
    dataset_preview_rows = reactive.Value({})

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
        manual_source_message.set(None)
        manual_target_clicks.set({})

        definition_approved.set(False)
        data_approved.set(False)

        research_run_id.set(None)
        research_run_save_error.set(None)

        discovered_datasets.set(None)
        dataset_review_clicks.set({})
        dataset_retrieval_clicks.set({})
        dataset_preview_rows.set({})

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

        for index, item in enumerate(result.get("data_needed", [])):

            card_elements = [

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
                )
            ]

            if item.get(
                "origin"
            ) == "user_provided":

                if item.get(
                    "source_title"
                ):

                    card_elements.append(
                        ui.tags.p(
                            ui.tags.strong(
                                "Source: "
                            ),
                            item.get(
                                "source_title"
                            )
                        )
                    )

                if item.get(
                    "publisher"
                ):

                    card_elements.append(
                        ui.tags.p(
                            ui.tags.strong(
                                "Publisher: "
                            ),
                            item.get(
                                "publisher"
                            )
                        )
                    )

                if item.get(
                    "provided_source_url"
                ):

                    card_elements.append(
                        ui.tags.a(
                            "Open provided URL",
                            href=item.get(
                                "provided_source_url"
                            ),
                            target="_blank",
                            class_="dataset-link"
                        )
                    )

                card_elements.append(
                    ui.input_action_button(
                        f"remove_manual_target_{index}",
                        "Remove manual target",
                        class_="btn-secondary confirm-button"
                    )
                )

            data_cards.append(

                ui.div(
                    *card_elements,

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

                ui.tags.hr(),

                ui.tags.h4(
                    "Add Data Target from URL"
                ),

                ui.input_text(
                    "manual_source_url",
                    label="Source URL",
                    placeholder="https://example.org/data.csv",
                    width="100%"
                ),

                ui.input_action_button(
                    "add_manual_source",
                    "Add Data Target",
                    class_="btn-secondary confirm-button"
                ),

                ui.output_ui(
                    "manual_source_status"
                ),

                ui.tags.hr(),

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
            "The definition has been revised. The data "
            "targets have also been reconsidered."
        )

        data_message.set(
            "The data targets must be reviewed again "
            "because the definition was revised."
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
    # MANUAL SOURCE URL
    # -----------------------------------------------------

    @reactive.effect
    @reactive.event(input.add_manual_source)
    def handle_manual_source_addition():

        url = input.manual_source_url()

        if not url or not url.strip():

            manual_source_message.set(
                "Please paste a source URL first."
            )

            return

        current_result = revised_result.get()

        if current_result is None:
            current_result = search_request()

        if not current_result:

            manual_source_message.set(
                "No current analysis is available yet."
            )

            return

        manual_source_message.set(
            "Inspecting source and checking whether it fits the approved topic..."
        )

        try:

            analysis = analyse_user_provided_source(
                definition=current_result.get(
                    "definition",
                    ""
                ),
                existing_data_targets=current_result.get(
                    "data_needed",
                    []
                ),
                url=url.strip()
            )

        except Exception as error:

            manual_source_message.set(
                "The source could not be inspected safely: "
                + str(error)
            )

            return

        if not analysis.get(
            "accepted"
        ):

            manual_source_message.set(
                "Source was not added. "
                + analysis.get(
                    "message",
                    analysis.get(
                        "reason",
                        "It was not validated as a useful data source."
                    )
                )
            )

            return

        manual_target = {
            "name":
                analysis.get(
                    "data_target"
                )
                or
                analysis.get(
                    "source_title",
                    "User-provided data target"
                ),

            "reason":
                analysis.get(
                    "target_description"
                )
                or
                analysis.get(
                    "reason",
                    ""
                ),

            "origin":
                "user_provided",

            "provided_source_url":
                analysis.get(
                    "source_url",
                    url.strip()
                ),

            "source_title":
                analysis.get(
                    "source_title",
                    "unknown"
                ),

            "publisher":
                analysis.get(
                    "publisher",
                    "unknown"
                ),

            "source_description":
                analysis.get(
                    "target_description",
                    ""
                ),

            "description":
                analysis.get(
                    "target_description",
                    ""
                ),

            "available_information":
                analysis.get(
                    "available_information",
                    []
                ),

            "validation_status":
                analysis.get(
                    "validation_status",
                    "validated"
                ),

            "validation_reason":
                analysis.get(
                    "validation_reason",
                    analysis.get(
                        "reason",
                        ""
                    )
                ),

            "link_status":
                analysis.get(
                    "link_status",
                    "reachable"
                ),

            "source_type":
                analysis.get(
                    "source_type",
                    "unknown"
                ),

            "data_access_type":
                analysis.get(
                    "data_access_type",
                    "unknown"
                ),

            "format":
                analysis.get(
                    "data_access_type",
                    "unknown"
                ),

            "geographic_coverage":
                analysis.get(
                    "geographic_coverage",
                    "unknown"
                ),

            "time_coverage":
                analysis.get(
                    "time_coverage",
                    "unknown"
                ),

            "final_url":
                analysis.get(
                    "final_url"
                ),

            "dataset_code":
                analysis.get(
                    "dataset_code"
                ),

            "doi":
                analysis.get(
                    "doi"
                ),

            "source_metadata":
                analysis.get(
                    "source_metadata"
                )
        }

        updated_result = current_result.copy()
        updated_targets = list(
            updated_result.get(
                "data_needed",
                []
            )
        )
        updated_targets.append(
            manual_target
        )
        updated_result["data_needed"] = updated_targets

        revised_result.set(
            updated_result
        )
        data_approved.set(False)
        research_run_id.set(None)
        research_run_save_error.set(None)

        manual_source_message.set(
            "Source added as a user-provided data target. "
            "Please approve the data targets again."
        )


    @reactive.effect
    def handle_manual_target_removal():

        result = revised_result.get()

        if result is None:
            result = search_request()

        if not result:
            return

        previous_clicks = manual_target_clicks.get().copy()
        changed = False

        for index, item in enumerate(
            result.get(
                "data_needed",
                []
            )
        ):

            if item.get(
                "origin"
            ) != "user_provided":
                continue

            input_id = f"remove_manual_target_{index}"

            try:
                clicks = input[input_id]()
            except Exception:
                continue

            previous = previous_clicks.get(
                input_id,
                0
            )

            if clicks and clicks > previous:

                updated_targets = [
                    target
                    for target_index, target
                    in enumerate(
                        result.get(
                            "data_needed",
                            []
                        )
                    )
                    if target_index != index
                ]

                updated_result = result.copy()
                updated_result["data_needed"] = updated_targets

                revised_result.set(
                    updated_result
                )
                data_approved.set(False)
                research_run_id.set(None)
                research_run_save_error.set(None)

                manual_source_message.set(
                    "Manual data target removed. Please approve the data targets again."
                )

                previous_clicks[input_id] = clicks
                changed = True
                break

            previous_clicks[input_id] = clicks or 0

        if changed or previous_clicks != manual_target_clicks.get():
            manual_target_clicks.set(
                previous_clicks
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


    @output
    @render.ui
    def manual_source_status():

        message = manual_source_message.get()

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

            dataset_review_clicks.set(
                {}
            )

            dataset_retrieval_clicks.set(
                {}
            )

            dataset_preview_rows.set(
                {}
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
    # DATASET REVIEW ACTIONS
    # -----------------------------------------------------

    def apply_dataset_review(
        dataset_id,
        review_status
    ):

        update_dataset_review_status(
            dataset_id=dataset_id,
            review_status=review_status
        )


        datasets = discovered_datasets.get()

        if datasets is None:
            return


        updated_datasets = []

        for dataset in datasets:

            updated_dataset = dataset.copy()

            if updated_dataset.get(
                "id"
            ) == dataset_id:

                updated_dataset["review_status"] = review_status


            updated_datasets.append(
                updated_dataset
            )


        discovered_datasets.set(
            updated_datasets
        )

        public_data_status_value.set(
            "Source review status updated."
        )


    @reactive.effect
    def handle_dataset_review_actions():

        datasets = discovered_datasets.get()

        if not datasets:
            return


        previous_clicks = dataset_review_clicks.get().copy()

        next_clicks = previous_clicks.copy()


        for dataset in datasets:

            dataset_id = dataset.get(
                "id"
            )

            if dataset_id is None:
                continue


            for action, review_status in [
                (
                    "approve",
                    "approved"
                ),
                (
                    "reject",
                    "rejected"
                )
            ]:

                input_id = f"{action}_source_{dataset_id}"

                try:

                    click_count = input[input_id]()

                except Exception:

                    click_count = 0


                previous_count = previous_clicks.get(
                    input_id,
                    0
                )

                next_clicks[input_id] = click_count


                if click_count > previous_count:

                    apply_dataset_review(
                        dataset_id=dataset_id,
                        review_status=review_status
                    )

                    dataset_review_clicks.set(
                        next_clicks
                    )

                    return


        if next_clicks != previous_clicks:

            dataset_review_clicks.set(
                next_clicks
            )


    # -----------------------------------------------------
    # DATASET RETRIEVAL ACTIONS
    # -----------------------------------------------------

    def update_dataset_in_state(
        dataset_id,
        updates
    ):

        datasets = discovered_datasets.get()

        if datasets is None:
            return


        updated_datasets = []

        for dataset in datasets:

            updated_dataset = dataset.copy()

            if updated_dataset.get(
                "id"
            ) == dataset_id:

                updated_dataset.update(
                    updates
                )


            updated_datasets.append(
                updated_dataset
            )


        discovered_datasets.set(
            updated_datasets
        )


    def apply_dataset_retrieval(
        dataset
    ):

        dataset_id = dataset.get(
            "id"
        )

        if dataset_id is None:
            return


        if dataset.get(
            "review_status"
        ) != "approved":

            public_data_status_value.set(
                "Only approved sources can be retrieved."
            )

            return


        update_dataset_in_state(
            dataset_id,
            {
                "retrieval_status":
                    "not_started",

                "retrieval_message":
                    "Retrieving data..."
            }
        )

        public_data_status_value.set(
            "Retrieving data..."
        )


        result = retrieve_dataset(
            dataset.get(
                "source_url",
                ""
            )
        )


        if result.get(
            "retrieval_status"
        ) == "retrieved":

            rows = result.get(
                "rows",
                []
            )

            stored_count = replace_dataset_rows(
                dataset_id,
                rows
            )

            update_dataset_retrieval(
                dataset_id=dataset_id,
                retrieval_status="retrieved",
                data_access_url=result.get(
                    "data_access_url"
                ),
                retrieval_message=result.get(
                    "message"
                ),
                retrieved_row_count=result.get(
                    "retrieved_row_count"
                ),
                stored_row_count=stored_count
            )

            preview_rows = get_dataset_rows(
                dataset_id,
                limit=20
            )

            previews = dataset_preview_rows.get().copy()

            previews[dataset_id] = preview_rows

            dataset_preview_rows.set(
                previews
            )

            update_dataset_in_state(
                dataset_id,
                {
                    "retrieval_status":
                        "retrieved",

                    "data_access_url":
                        result.get(
                            "data_access_url"
                        ),

                    "retrieval_message":
                        result.get(
                            "message"
                        ),

                    "retrieved_row_count":
                        result.get(
                            "retrieved_row_count"
                        ),

                    "stored_row_count":
                        stored_count
                }
            )

            public_data_status_value.set(
                "Data retrieval completed."
            )

            return


        update_dataset_retrieval(
            dataset_id=dataset_id,
            retrieval_status=result.get(
                "retrieval_status",
                "failed"
            ),
            data_access_url=result.get(
                "data_access_url"
            ),
            retrieval_message=result.get(
                "message"
            ),
            retrieved_row_count=result.get(
                "retrieved_row_count"
            ),
            stored_row_count=result.get(
                "stored_row_count"
            )
        )

        update_dataset_in_state(
            dataset_id,
            {
                "retrieval_status":
                    result.get(
                        "retrieval_status",
                        "failed"
                    ),

                "data_access_url":
                    result.get(
                        "data_access_url"
                    ),

                "retrieval_message":
                    result.get(
                        "message"
                    ),

                "retrieved_row_count":
                    result.get(
                        "retrieved_row_count"
                    ),

                "stored_row_count":
                    result.get(
                        "stored_row_count"
                    )
            }
        )

        public_data_status_value.set(
            "Data retrieval did not complete: "
            + result.get(
                "message",
                "Unsupported or failed source."
            )
        )


    @reactive.effect
    def handle_dataset_retrieval_actions():

        datasets = discovered_datasets.get()

        if not datasets:
            return


        previous_clicks = dataset_retrieval_clicks.get().copy()

        next_clicks = previous_clicks.copy()


        for dataset in datasets:

            dataset_id = dataset.get(
                "id"
            )

            if dataset_id is None:
                continue


            input_id = f"retrieve_data_{dataset_id}"

            try:

                click_count = input[input_id]()

            except Exception:

                click_count = 0


            previous_count = previous_clicks.get(
                input_id,
                0
            )

            next_clicks[input_id] = click_count


            if click_count > previous_count:

                dataset_retrieval_clicks.set(
                    next_clicks
                )

                apply_dataset_retrieval(
                    dataset
                )

                return


        if next_clicks != previous_clicks:

            dataset_retrieval_clicks.set(
                next_clicks
            )


    # -----------------------------------------------------
    # DISPLAY PUBLIC DATASET RESULTS
    # -----------------------------------------------------

    @output
    @render.ui
    def public_dataset_results():

        datasets = discovered_datasets.get()
        preview_rows_by_dataset = dataset_preview_rows.get()


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

            dataset_id = dataset.get(
                "id"
            )

            retrieval_status = (
                dataset.get(
                    "retrieval_status"
                )
                or
                "not_started"
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
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Source type: "
                    ),

                    (
                        dataset.get(
                            "source_type"
                        )
                        or
                        "unknown"
                    ).replace(
                        "_",
                        " "
                    ).title()
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Origin: "
                    ),

                    (
                        dataset.get(
                            "source_origin"
                        )
                        or
                        "discovered"
                    ).replace(
                        "_",
                        " "
                    ).title()
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Validation: "
                    ),

                    (
                        dataset.get(
                            "validation_status"
                        )
                        or
                        "needs_review"
                    ).replace(
                        "_",
                        " "
                    ).title()
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Link: "
                    ),

                    (
                        dataset.get(
                            "link_status"
                        )
                        or
                        "unknown"
                    ).replace(
                        "_",
                        " "
                    ).title()
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Review status: "
                    ),

                    (
                        dataset.get(
                            "review_status"
                        )
                        or
                        "pending_review"
                    ).replace(
                        "_",
                        " "
                    ).title()
                ),

                ui.tags.p(
                    ui.tags.strong(
                        "Retrieval: "
                    ),

                    retrieval_status.replace(
                        "_",
                        " "
                    ).title()
                )
            ]

            if dataset.get(
                "data_access_url"
            ):

                card_elements.append(
                    ui.tags.p(
                        ui.tags.strong(
                            "Data access URL: "
                        ),

                        dataset.get(
                            "data_access_url"
                        )
                    )
                )

            if dataset.get(
                "retrieved_row_count"
            ) is not None:

                card_elements.append(
                    ui.tags.p(
                        ui.tags.strong(
                            "Retrieved rows: "
                        ),

                        str(
                            dataset.get(
                                "retrieved_row_count"
                            )
                        )
                    )
                )

            if dataset.get(
                "stored_row_count"
            ) is not None:

                card_elements.append(
                    ui.tags.p(
                        ui.tags.strong(
                            "Stored rows: "
                        ),

                        str(
                            dataset.get(
                                "stored_row_count"
                            )
                        )
                    )
                )

            if dataset.get(
                "retrieval_message"
            ):

                card_elements.append(
                    ui.tags.p(
                        dataset.get(
                            "retrieval_message"
                        )
                    )
                )


            if source_url:

                card_elements.append(

                    ui.tags.a(
                        "Open original source",
                        href=source_url,
                        target="_blank",
                        class_="dataset-link"
                    )
                )

            if (
                dataset.get(
                    "review_status"
                ) == "approved"
                and
                dataset_id is not None
                and
                dataset.get(
                    "validation_status"
                ) != "invalid"
            ):

                card_elements.append(

                    ui.input_action_button(
                        f"retrieve_data_{dataset_id}",
                        "Retrieve data",
                        class_="btn-primary confirm-button"
                    )
                )

            if (
                dataset_id is not None
                and
                dataset.get(
                    "validation_status"
                ) != "invalid"
            ):

                card_elements.append(

                    ui.div(

                        ui.input_action_button(
                            f"approve_source_{dataset_id}",
                            "Approve source",
                            class_="btn-success confirm-button"
                        ),

                        ui.input_action_button(
                            f"reject_source_{dataset_id}",
                            "Reject source",
                            class_="btn-secondary confirm-button"
                        )
                    )
                )

            preview_rows = preview_rows_by_dataset.get(
                dataset_id,
                []
            )

            if preview_rows:

                columns = []

                for row in preview_rows:

                    for column in row.keys():

                        if column not in columns:

                            columns.append(
                                column
                            )


                visible_columns = columns[:12]

                table_rows = [
                    ui.tags.tr(
                        *[
                            ui.tags.th(
                                column
                            )
                            for column
                            in visible_columns
                        ]
                    )
                ]

                for row in preview_rows[:20]:

                    table_rows.append(
                        ui.tags.tr(
                            *[
                                ui.tags.td(
                                    "" if row.get(
                                        column
                                    ) is None else str(
                                        row.get(
                                            column
                                        )
                                    )
                                )
                                for column
                                in visible_columns
                            ]
                        )
                    )


                card_elements.append(
                    ui.div(
                        ui.tags.h5(
                            "Preview"
                        ),

                        ui.tags.table(
                            *table_rows,
                            class_="table table-sm"
                        ),

                        (
                            ui.tags.p(
                                "Preview shows the first 12 columns only."
                            )
                            if len(
                                columns
                            ) > len(
                                visible_columns
                            )
                            else
                            None
                        )
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
