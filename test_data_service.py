from data_service import search_public_datasets


targets = [
    {
        "name": "Population age structure",
        "reason": (
            "Needed to understand the age distribution "
            "of the population."
        )
    }
]


result = search_public_datasets(
    topic="Gerontocracy in Europe",
    data_targets=targets
)


print("\n\nFINAL DATASET CANDIDATES\n")

for dataset in result["datasets"]:

    print("TITLE:")
    print(dataset.get("title"))

    print("\nPUBLISHER:")
    print(dataset.get("publisher"))

    print("\nURL:")
    print(dataset.get("source_url"))

    print("\nDESCRIPTION:")
    print(dataset.get("description"))

    print("\nFORMAT:")
    print(dataset.get("format"))

    print("\n" + "=" * 70)