# n8n glue (optional — never core logic)

Start (no restart policy, so it never comes back at boot):
    docker start n8n || docker run -d --name n8n -p 127.0.0.1:5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n:1.123.100
Stop: `docker stop n8n`. UI: http://localhost:5678

Pattern: FastAPI -> POST $N8N_WEBHOOK_URL (3 s timeout, fire-and-forget) -> Telegram/Gmail/Sheets.
Cloud callers need a public URL: `bash scripts/tunnel.sh` with PORT=5678.
Design workflows with the n8n-mcp tools (prompt E in the master doc); export JSON into this folder.
