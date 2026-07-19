# ReVoice — Multimodal Memory Agent

> Built for the MemoryAgent track of the Global AI Hackathon Series with Qwen Cloud.

ReVoice helps a person who knows what they mean but cannot retrieve the exact word. Instead of storing facts, it stores the **recovery path** — the specific sequence of personal cues that helped this person communicate this concept before — and replays a smaller, more targeted version of that path the next time the concept comes up.

See [docs/architecture.md](docs/architecture.md) for the full architecture and [docs/demo_script.md](docs/demo_script.md) for the demo narration.

---

## Setup

```bash
# Clone and enter
git clone https://github.com/MunadEAli/ReVoice_Agent.git
cd ReVoice_Agent

# Backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Copy env and fill in your keys
cp .env.example .env
# Edit .env — at minimum set DASHSCOPE_API_KEY when available

# Run backend
uvicorn services.api.main:app --reload

# Frontend
cd apps/web
npm install
npm run dev
```

Full documentation and architecture diagrams in [docs/](docs/).
