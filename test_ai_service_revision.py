import json
import unittest

import ai_service


class FakeInteractions:

    def create(
        self,
        model,
        input
    ):

        class Response:
            output_text = json.dumps(
                {
                    "in_scope": True,
                    "scope_message": "",
                    "definition": (
                        "Gerontocracy is political power "
                        "held disproportionately by older people."
                    ),
                    "data_needed": [
                        {
                            "name": "Age distribution of elected officials",
                            "reason": (
                                "Needed to compare institutional power "
                                "across age groups."
                            )
                        }
                    ]
                }
            )

        return Response()


class FakeClient:

    interactions = FakeInteractions()


class AiServiceRevisionTest(unittest.TestCase):

    def assert_result_structure(self, result):

        for key in [
            "in_scope",
            "scope_message",
            "definition",
            "data_needed"
        ]:

            self.assertIn(
                key,
                result
            )

        self.assertIsInstance(
            result["data_needed"],
            list
        )

    def test_definition_revision_can_update_data_targets(self):

        original_client = ai_service.client
        ai_service.client = FakeClient()

        current_analysis = {
            "in_scope": True,
            "scope_message": "",
            "definition": (
                "Gerontocracy means rule by older people."
            ),
            "data_needed": [
                {
                    "name": "Population age structure",
                    "reason": (
                        "Needed to understand the age distribution "
                        "of the population."
                    )
                }
            ]
        }

        try:
            result = ai_service.revise_topic_analysis(
                topic="Gerontocracy",
                current_analysis=current_analysis,
                user_feedback=(
                    "Focus the definition on political power "
                    "and representation."
                ),
                target="definition"
            )

        finally:
            ai_service.client = original_client

        self.assertNotEqual(
            result["definition"],
            current_analysis["definition"]
        )

        self.assertNotEqual(
            result["data_needed"],
            current_analysis["data_needed"]
        )

        self.assertEqual(
            result["data_needed"][0]["name"],
            "Age distribution of elected officials"
        )

        self.assert_result_structure(
            result
        )

    def test_data_revision_preserves_definition(self):

        original_client = ai_service.client
        ai_service.client = FakeClient()

        current_analysis = {
            "in_scope": True,
            "scope_message": "",
            "definition": (
                "Gerontocracy means rule by older people."
            ),
            "data_needed": [
                {
                    "name": "Population age structure",
                    "reason": (
                        "Needed to understand the age distribution "
                        "of the population."
                    )
                }
            ]
        }

        try:
            result = ai_service.revise_topic_analysis(
                topic="Gerontocracy",
                current_analysis=current_analysis,
                user_feedback="Add age distribution of elected officials.",
                target="data"
            )

        finally:
            ai_service.client = original_client

        self.assertEqual(
            result["definition"],
            current_analysis["definition"]
        )

        self.assertNotEqual(
            result["data_needed"],
            current_analysis["data_needed"]
        )

        self.assert_result_structure(
            result
        )


if __name__ == "__main__":
    unittest.main()
