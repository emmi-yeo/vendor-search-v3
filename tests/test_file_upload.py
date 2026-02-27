import io
import base64
import sys
import os

# ensure project root is on path so `import src` works
root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root not in sys.path:
    sys.path.append(root)

import pytest
import pandas as pd
from PyPDF2 import PdfWriter
import docx

from src import file_handler


class DummyFile:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content
        self.size = len(content)

    def read(self):
        return self._content

    def seek(self, pos):
        # not used in tests but keep signature
        pass


def make_pdf_bytes(text="hello") -> bytes:
    writer = PdfWriter()
    # PyPDF2 blank page has no text; instead create a page and add text via annotations?
    # simpler: create PDF from scratch using reportlab? reportlab isn't in requirements but exists maybe.
    # Instead we can create from bytes by writing simple PDF code.
    # For testing, we just need extract_text to not crash; blank page is OK.
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def make_docx_bytes(text="hello") -> bytes:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_xlsx_bytes() -> bytes:
    df1 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df1.to_excel(writer, sheet_name="Sheet1", index=False)
    return buf.getvalue()


def test_validate_file_good():
    f = DummyFile("foo.pdf", b"abc")
    assert file_handler.validate_file(f) is True


def test_validate_file_bad_ext():
    f = DummyFile("foo.exe", b"abc")
    with pytest.raises(ValueError):
        file_handler.validate_file(f)


def test_validate_file_too_large():
    f = DummyFile("foo.pdf", b"0" * (file_handler.MAX_FILE_SIZE + 1))
    with pytest.raises(ValueError):
        file_handler.validate_file(f)


def test_extract_text_pdf():
    data = make_pdf_bytes()
    text = file_handler.extract_text_from_file(data, "test.pdf")
    assert isinstance(text, str)


def test_extract_text_docx():
    data = make_docx_bytes("some words")
    text = file_handler.extract_text_from_file(data, "test.docx")
    assert "some words" in text


def test_extract_text_xlsx():
    data = make_xlsx_bytes()
    text = file_handler.extract_text_from_file(data, "test.xlsx")
    assert "Sheet" in text


def test_extract_text_image():
    # minimal PNG header
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 10
    text = file_handler.extract_text_from_file(png, "pic.png")
    assert "data:image/png;base64" in text


def test_interpret_files_search(monkeypatch):
    def fake_chat(messages, temperature, max_tokens):
        return '{"action":"search","search_query":"foo"}'

    monkeypatch.setattr("src.azure_llm.azure_chat", fake_chat)
    result = file_handler.interpret_files(["x"], ["a.txt"], "bar")
    assert result["action"] == "search"
    assert result["search_query"] == "foo"


def test_interpret_files_malformed(monkeypatch):
    monkeypatch.setattr(
        "src.azure_llm.azure_chat",
        lambda *args, **kwargs: "not json",
    )
    result = file_handler.interpret_files(["x"], ["a.txt"], None)
    assert result["action"] == "respond"
    assert "not json" in result["text"]


def test_handle_uploaded_files_search(monkeypatch):
    # simulate a pair of files
    def fake_interpret(texts, names, query):
        return {"action": "search", "search_query": "bar"}

    monkeypatch.setattr(file_handler, "interpret_files", fake_interpret)
    # prevent actual extraction (dummy bytes would otherwise fail)
    monkeypatch.setattr(file_handler, "extract_text_from_file", lambda b, n: "dummy")
    f = DummyFile("foo.pdf", b"abc")
    res = file_handler.handle_uploaded_files([f], "baz")
    assert res["action"] == "search"
    assert res["search_query"] == "bar"


def test_handle_uploaded_files_summary(monkeypatch):
    def fake_interpret(texts, names, query):
        return {"action": "summary", "text": "ok"}

    monkeypatch.setattr(file_handler, "interpret_files", fake_interpret)
    monkeypatch.setattr(file_handler, "extract_text_from_file", lambda b, n: "dummy")
    f = DummyFile("foo.pdf", b"abc")
    res = file_handler.handle_uploaded_files([f], None)
    assert res["action"] == "summary"
    assert res["text"] == "ok"
