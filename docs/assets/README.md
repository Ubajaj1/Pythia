# Presentation assets

Drop these files here, keep the exact filenames. The page shows a graceful placeholder if a file is missing, so order does not matter.

## Where each image appears in the deck

| # | File | Section | What it is | Suggested size |
|---|---|---|---|---|
| 1 | `utkarsh.jpg` | Who am I (**below the text** `UB` monogram + tagline) | Your photo, landscape or square works | 1200×800 |
| 2 | `why-pythia.jpg` | Why Pythia (right column, beside the 4 numbered cards) | Oracle illustration, boardroom/meeting photo, or UI screenshot | 800×900 |
| 3 | `demo-graphs.png` | Demo gallery, top-left tile | Screenshot of the stance trajectory / influence graph | 1400×900 |
| 4 | `demo-verdict.png` | Demo gallery, top-right tile | Screenshot of `DecisionPanel` expanded | 1400×900 |
| 5 | `demo-method.png` | Demo gallery, bottom-left tile | Screenshot of `OracleMethod` report | 1400×900 |
| 6 | `demo-agent.png` | Demo gallery, bottom-right tile | Screenshot of `AgentDetail` drawer | 1400×900 |
| 7 | `meme.jpg` | Connect row, left tile | Closing humour image (landscape) | 1000×700 |
| 8 | `qr-linkedin.png` | Connect row, middle tile | QR pointing at your LinkedIn | 500×500 |
| 9 | `qr-github.png` | Connect row, right tile | QR for https://github.com/Ubajaj1/Pythia | 500×500 |

## Quick QR generation

```bash
# one-time: pip install 'qrcode[pil]'
python -c "import qrcode; qrcode.make('https://github.com/Ubajaj1/Pythia').save('docs/assets/qr-github.png')"
python -c "import qrcode; qrcode.make('https://www.linkedin.com/in/YOUR-HANDLE/').save('docs/assets/qr-linkedin.png')"
```

## Running the deck locally

```bash
python3 -m http.server -d docs 8080
# then open http://localhost:8080/presentation.html
```
