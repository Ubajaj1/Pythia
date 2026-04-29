# Presentation assets

Drop these files here — they're wired into `docs/presentation.html` by path.
The page shows a graceful placeholder if a file is missing, so order doesn't matter.

| Section | File | Type | Suggested size |
|---|---|---|---|
| Who am I? | `utkarsh.jpg` | Your photo, circular crop looks best | 400×400 |
| Why Pythia? | `why-pythia.jpg` | Oracle illustration, UI screenshot, or stock boardroom | 800×600 |
| Demo — graphs | `demo-graphs.png` | Screenshot of the stance trajectory / influence graph | 1400×900 |
| Demo — verdict | `demo-verdict.png` | Screenshot of DecisionPanel expanded | 1400×900 |
| Demo — method | `demo-method.png` | Screenshot of OracleMethod component | 1400×900 |
| Demo — agent | `demo-agent.png` | Screenshot of AgentDetail drawer | 1400×900 |
| Meme | `meme.jpg` | Closing humor image | 1000×700 |
| LinkedIn QR | `qr-linkedin.png` | QR code pointing at your LinkedIn | 500×500 |
| GitHub QR | `qr-github.png` | QR code for https://github.com/Ubajaj1/Pythia | 500×500 |

## Quick QR code generation

```bash
# Python one-liner — requires `pip install qrcode[pil]`
python -c "import qrcode; qrcode.make('https://github.com/Ubajaj1/Pythia').save('qr-github.png')"
python -c "import qrcode; qrcode.make('https://www.linkedin.com/in/YOUR-HANDLE/').save('qr-linkedin.png')"
```

Or use any generator — Google "QR code generator" and pick one.

## Running the slide deck

```bash
python3 -m http.server -d docs 8080
# open http://localhost:8080/presentation.html
```
