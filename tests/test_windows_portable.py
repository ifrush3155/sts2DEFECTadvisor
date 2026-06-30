import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsPortableFilesTests(unittest.TestCase):
    def test_run_panel_bat_uses_project_python_entrypoint(self):
        script = (ROOT / "run-panel.bat").read_text(encoding="utf-8")

        self.assertIn("python.exe", script)
        self.assertIn("PYTHONPATH", script)
        self.assertIn("-m sts2defect.cli run-panel", script)
        self.assertIn("data\\recommendations\\slay-the-spire-2-manual.json", script)

    def test_requirements_install_runtime_extras(self):
        requirements = (ROOT / "requirements-windows.txt").read_text(encoding="utf-8")

        self.assertIn(".[vision,overlay]", requirements)

    def test_windows_portable_docs_exist(self):
        docs = (ROOT / "docs" / "windows-portable.md").read_text(encoding="utf-8")

        self.assertIn("Windows 便携启动", docs)
        self.assertIn("run-panel.bat", docs)
        self.assertIn("常见报错", docs)


if __name__ == "__main__":
    unittest.main()
