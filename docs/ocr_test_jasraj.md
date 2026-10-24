# OCR Benchmark Results — Jasraj

**Task:** J2 — Compare EasyOCR and PaddleOCR  
**Test PDF:** `test1.pdf`  
**Test date:** October 2026  
**Machine:** Mac (CPU inference)

## 1. Summary

| Engine | Installed successfully? | Install time | Timed OCR pass (page 1) | Similarity to PDF text | Notes |
|---|---|---:|---:|---:|---|
| EasyOCR | Yes | Not measured | 4.80 s (run 1); 4.63 s (run 2) | 0.986 (both runs) | CPU. First run included model download during initialization. |
| PaddleOCR | Yes | Not measured | 7.03 s (run 1) | 0.997 (run 1) | Paddle check passed on 1 CPU. Non-fatal environment warnings appeared. |

**Preliminary result:** On page 1 of this particular PDF, PaddleOCR had the higher text similarity score. This is only a one-page test on a digital PDF, so it does not establish which engine performs better on scanned or more difficult documents.

## 2. Test setup

- `test1.pdf` contains **17 pages** and has selectable digital text.
- Page 1's PDF text layer contained **298 characters**.
- Page 1 was rendered to `page1.png` at **150 dpi**.
- Both OCR engines were run on CPU.
- Similarity was calculated by comparing OCR output with the PDF's text layer using normalized text and `SequenceMatcher`.
- The installation durations were **not timed**, so they are recorded as “Not measured” rather than estimated.

## 3. EasyOCR results

| Measurement | Run 1 | Run 2 |
|---|---:|---:|
| Initialization/model loading | 100.47 s | 2.88 s |
| First OCR call / warm-up | 5.24 s | 5.58 s |
| Timed OCR pass | 4.80 s | 4.63 s |
| Text similarity | 0.986 | 0.986 |

The first run's initialization included model download/loading, which explains why it took much longer than the second run. PyTorch emitted non-fatal MPS/pinning warnings.

**First five OCR lines:**

1. `Nexbridge Technologies`
2. `PRODUCT REQUIREMENTS DOCUMENT`
3. `Virtual AI Assistant (Mini Alexa)`
4. `AI Internship Program`
5. `Project`

## 4. PaddleOCR results

| Measurement | Run 1 |
|---|---:|
| Paddle installation check | Passed — “PaddlePaddle works well on 1 CPU.” |
| Initialization/model loading | 126.13 s |
| First OCR call / warm-up | 7.07 s |
| Timed OCR pass | 7.03 s |
| Text similarity | 0.997 |

PaddleOCR emitted non-fatal warnings related to `ccache` and the Tensor `place` interface. The OCR run completed successfully.

**First five OCR lines:**

1. `Nexbridge Technologies`
2. `PRODUCT REQUIREMENTS DOCUMENT`
3. `Virtual AI Assistant (Mini Alexa)`
4. `AI Internship Program — Project 1`
5. `Document Type: Internal Project Specification`

## 5. Measurement notes and limitations

- Installation succeeded for both engines, but installation time was not recorded.
- Two EasyOCR runs are confirmed; only one PaddleOCR run is recorded here.
- Initialization/model download, warm-up, and the timed OCR pass are listed separately. The summary's “Timed OCR pass” is the comparison figure.
- These results are from page 1 of one digital PDF. They should not be treated as a general accuracy or speed ranking for all PDFs.
- Warnings noted above did not prevent the runs from completing.

## 6. Required submission

- [ ] Upload this file to the repository at `docs/ocr_test_jasraj.md`.
- [ ] Post a screenshot of the results in the team group chat.
