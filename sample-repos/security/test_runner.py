from pathlib import Path


def test_source_has_no_shell_execution():
    source = Path("runner.py").read_text()
    assert "os.system(" not in source
    assert "shell=True" not in source
