import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from learning_platform.ai_assistant import SYSTEM_PROMPT, AiAssistant, AiSettings, question_message
from learning_platform.models import Question


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


if __name__ == "__main__":
    unittest.main()
