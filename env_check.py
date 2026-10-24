"""SIH26261 environment check. Synthetic data only."""
import importlib
from importlib import metadata

TEXT = "SYNTHETIC TEST 12345"
PDF_NAME = "env_test.pdf"

# (name shown, import name, install name)
PACKAGES = [
    ("fitz", "fitz", "PyMuPDF"),
    ("pdfplumber", "pdfplumber", "pdfplumber"),
    ("PIL", "PIL", "pillow"),
    ("numpy", "numpy", "numpy"),
    ("yaml", "yaml", "PyYAML"),
    ("pydantic", "pydantic", "pydantic"),
    ("fastapi", "fastapi", "fastapi"),
    ("streamlit", "streamlit", "streamlit"),
    ("pyhanko", "pyhanko", "pyhanko"),
]


def check(label, module, dist):
    """Try to import one package and print OK or FAIL."""
    try:
        importlib.import_module(module)
    except Exception as exc:
        print(f"FAIL {label} {exc}")
        return False
    try:
        version = metadata.version(dist)
    except Exception:
        version = "unknown"
    print(f"OK {label} {version}")
    return True


def make_pdf():
    """Create a one-page PDF with PyMuPDF."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), TEXT, fontsize=14)
    doc.save(PDF_NAME)
    doc.close()


def read_pdf():
    """Read the PDF back with pdfplumber and look for the text."""
    import pdfplumber
    with pdfplumber.open(PDF_NAME) as pdf:
        text = pdf.pages[0].extract_text() or ""
    return TEXT in text


def main():
    results = [check(*pkg) for pkg in PACKAGES]
    try:
        make_pdf()
        found = read_pdf()
        if found:
            print("OK pdf-roundtrip text found")
        else:
            print("FAIL pdf-roundtrip text not found")
        results.append(found)
    except Exception as exc:
        print(f"FAIL pdf-roundtrip {exc}")
        results.append(False)
    print("ALL OK" if all(results) else "SOME FAILED")


if __name__ == "__main__":
    main()

    