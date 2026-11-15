import threading
import uvicorn
from fastapi import FastAPI, HTTPException

from cache import StateStore
from hitl_ui import HITLManager
from schemas import InvokeRequest
from workflows import run_ide_code, run_inline_text, run_os_powershell, run_web_qa

app = FastAPI(title="Local-First Edge AI Desktop Assistant")
hitl = HITLManager()
store = StateStore()


@app.get("/health")
def health():
    return {"status": "ok", "model": "llama3.1:8b"}


@app.post("/invoke")
def invoke(req: InvokeRequest):
    try:
        if req.workflow == "inline_text":
            return run_inline_text(req.prompt, req.selected_text, store)
        if req.workflow == "ide_code":
            return run_ide_code(req.prompt, req.selected_text, store)
        if req.workflow == "web_qa":
            return run_web_qa(req.prompt, req.selected_text, store)
        if req.workflow == "os_powershell":
            return run_os_powershell(req.prompt, hitl, store)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    server_thread = threading.Thread(
        target=lambda: uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info"),
        daemon=True,
    )
    server_thread.start()
    hitl.run_mainloop()