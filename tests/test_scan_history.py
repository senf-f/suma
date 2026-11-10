import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "scan_history_latin.py"


def load_scanner():
    spec = importlib.util.spec_from_file_location("scan_history_latin", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scanner_does_not_flag_its_own_source():
    scanner = load_scanner()
    assert scanner.suspicious_lines(SCRIPT.read_text(encoding="utf-8")) == []


def test_scanner_flags_a_latin_sentence():
    scanner = load_scanner()
    # Invented, and assembled at runtime so this file's own source never trips the history scan.
    words = [
        "Ad primum ergo",
        "dicendum quod non",
        "est verum, sed",
        "quia videtur esse",
        "sicut unde.",
    ]
    line = " ".join(words)
    assert scanner.suspicious_lines(line) == [line]
