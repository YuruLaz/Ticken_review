from fastapi import FastAPI

app = FastAPI(title="SupportDesk AI")


@app.get("/health")
async def health():
    return {"status": "ok"}
