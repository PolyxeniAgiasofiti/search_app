from backend import build_retrieval_success_message, determine_retrieval_scope


def test_unresolved_custom_bookmark_success_message_uses_dataset_scope():

    dataset = {
        "is_custom_view": True,
        "custom_selection_status": "unresolved"
    }

    scope = determine_retrieval_scope(
        dataset
    )
    message = build_retrieval_success_message(
        dataset,
        scope,
        ""
    )

    assert scope == "dataset"
    assert "underlying dataset" in message
    assert "exact bookmarked view" in message


def test_resolved_custom_bookmark_uses_bookmark_selection_scope():

    dataset = {
        "is_custom_view": True,
        "custom_selection_status": "resolved"
    }

    scope = determine_retrieval_scope(
        dataset
    )
    message = build_retrieval_success_message(
        dataset,
        scope,
        "Data retrieval completed."
    )

    assert scope == "bookmark_selection"
    assert message == "Data retrieval completed."


if __name__ == "__main__":
    test_unresolved_custom_bookmark_success_message_uses_dataset_scope()
    test_resolved_custom_bookmark_uses_bookmark_selection_scope()
    print("backend retrieval scope tests passed")
