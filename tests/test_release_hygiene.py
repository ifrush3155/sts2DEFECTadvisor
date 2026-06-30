import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneTests(unittest.TestCase):
    def test_gitignore_excludes_private_and_generated_runtime_data(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in [
            "data/samples/profile1/",
            "data/samples/**/*.save",
            "data/samples/**/*.run",
            "data/samples/**/*.mcr",
            "data/samples/**/debug*/",
            "data/samples/**/live*/",
            "data/samples/**/ocr-crops/",
            "data/samples/ui-*.png",
            ".venv/",
            ".cache/",
        ]:
            self.assertIn(pattern, gitignore)

    def test_readme_covers_release_usage_and_safety_boundaries(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for text in [
            "Windows",
            "run-panel.bat",
            "OCR",
            "STS2MCP",
            "牌组统计",
            "只读",
            "不会点击游戏",
            "不会修改存档",
        ]:
            self.assertIn(text, readme)


if __name__ == "__main__":
    unittest.main()
