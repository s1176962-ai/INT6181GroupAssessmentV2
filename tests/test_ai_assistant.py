import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from learning_platform.ai_assistant import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_EN,
    AiAssistant,
    AiSettings,
    question_message,
    system_prompt,
)
from learning_platform.models import Question


def has_chinese(text):
    return any("\u4e00" <= char <= "\u9fff" for char in text)


class AiAssistantTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)

    def question(self):
        return Question.from_dict(
            {
                "id": "AI001",
                "subject": "Science",
                "topic": "Plants",
                "difficulty": "easy",
                "type": "single_choice",
                "question": "Which part absorbs water?",
                "options": ["Root", "Flower", "Fruit"],
                "answer": "Root",
                "explanation": "Roots absorb water.",
                "question_image": "assets/secret.png",
                "option_images": [None, None, None],
            }
        )

    def test_question_message_excludes_answer_explanation_and_images(self):
        message = question_message(self.question())
        self.assertIn("Which part absorbs water?", message)
        self.assertIn("A. Root", message)
        self.assertNotIn("Roots absorb water", message)
        self.assertNotIn("assets/secret.png", message)

    def test_english_mode_uses_an_english_prompt_and_question(self):
        """Switching the UI to English must not leak Chinese into AI output."""
        self.assertEqual(system_prompt("en"), SYSTEM_PROMPT_EN)
        self.assertEqual(system_prompt("zh"), SYSTEM_PROMPT)
        self.assertFalse(has_chinese(SYSTEM_PROMPT_EN))
        message = question_message(self.question(), "en")
        self.assertIn("Which part absorbs water?", message)
        self.assertIn("A. Root", message)
        self.assertNotIn("Roots absorb water", message)
        self.assertNotIn("assets/secret.png", message)
        self.assertFalse(has_chinese(message))

        settings = MagicMock()
        settings.load.return_value = {
            "endpoint": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-chat",
            "api_key": "secret",
        }
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Start with the subject."}}]}
        ).encode()
        response.__enter__.return_value = response
        with patch(
            "learning_platform.ai_assistant.urllib.request.urlopen", return_value=response
        ) as call:
            AiAssistant(settings).ask("Help me solve it", language="en")
        payload = json.loads(call.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["messages"][0]["content"], SYSTEM_PROMPT_EN)
        self.assertEqual(payload["messages"][1]["content"], "Help me solve it")

    def test_english_validation_errors_are_english(self):
        assistant = AiAssistant(MagicMock())
        for message in ("", "x" * (AiAssistant.MAX_INPUT_CHARS + 1)):
            with self.subTest(message_length=len(message)):
                with self.assertRaises(ValueError) as caught:
                    assistant.ask(message, language="en")
                self.assertFalse(has_chinese(str(caught.exception)))
        assistant.settings.load.return_value = {
            "endpoint": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-chat",
            "api_key": "",
        }
        with self.assertRaises(ValueError) as caught:
            assistant.ask("Explain this", language="en")
        self.assertFalse(has_chinese(str(caught.exception)))

    def test_key_is_not_stored_as_plain_text(self):
        settings = AiSettings(self.folder)
        with (
            patch("learning_platform.ai_assistant._protect", return_value="encrypted"),
            patch("learning_platform.ai_assistant._unprotect", return_value="secret-key"),
        ):
            settings.save(
                "https://api.deepseek.com/chat/completions", "deepseek-chat", "secret-key"
            )
            self.assertEqual(settings.load()["api_key"], "secret-key")
        self.assertNotIn("secret-key", settings.store.path.read_text(encoding="utf-8"))

    def test_request_uses_system_prompt_and_token_limit(self):
        settings = MagicMock()
        settings.load.return_value = {
            "endpoint": "https://api.deepseek.com/chat/completions",
            "model": "deepseek-chat",
            "api_key": "secret",
        }
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "先判断植物器官的功能。"}}]}
        ).encode()
        response.__enter__.return_value = response
        with patch(
            "learning_platform.ai_assistant.urllib.request.urlopen", return_value=response
        ) as call:
            answer = AiAssistant(settings).ask("How should I solve it?")
        self.assertEqual(answer, "先判断植物器官的功能。")
        request = call.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["max_tokens"], 320)
        self.assertEqual(payload["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(call.call_args.kwargs["timeout"], 30)

    def test_input_and_configuration_validation_happen_before_network_request(self):
        settings = MagicMock()
        assistant = AiAssistant(settings)
        with patch("learning_platform.ai_assistant.urllib.request.urlopen") as urlopen:
            for message in ("  ", "x" * (AiAssistant.MAX_INPUT_CHARS + 1)):
                with self.subTest(message_length=len(message)), self.assertRaises(ValueError):
                    assistant.ask(message)
            settings.load.assert_not_called()
            urlopen.assert_not_called()

            settings.load.return_value = {
                "endpoint": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
                "api_key": "",
            }
            with self.assertRaisesRegex(ValueError, "API Key"):
                assistant.ask("Please explain this question.")
            urlopen.assert_not_called()

    def test_settings_reject_insecure_endpoint_and_empty_model(self):
        settings = AiSettings(self.folder)
        with self.assertRaises(ValueError):
            settings.save("http://example.test", "model", "secret")
        with self.assertRaises(ValueError):
            settings.save("https://example.test", "  ", "secret")


if __name__ == "__main__":
    unittest.main()
