# Auralynq Web UI

Next.js 14 (App Router) + Tailwind UI for Auralynq.

## Features
- Chat with **SSE token streaming** and visible **citations**
- **Push-to-talk** microphone (MediaRecorder → `/voice`) with recording indicator,
  live transcript, and spoken answer playback
- **Retrieval trace panel** (per-node timings) and **evidence-path viewer** (PathRAG)
- **Ingest panel** (upload documents/audio) and **eval report viewer**
- Live **provider badges** from `/health` (shows what's actually running)

## Dev
```bash
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev   # http://localhost:3000
```
The API base defaults to `http://localhost:8000`. In the Podman stack it is wired
automatically (`make stack-up`).
