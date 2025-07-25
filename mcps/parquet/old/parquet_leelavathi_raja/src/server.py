from fastapi import FastAPI
from fastapi.responses import JSONResponse
from src.mcp_handlers import handle_mcp_request

app = FastAPI()

@app.post("/mcp")
async def mcp_handler(request: dict):
    return await handle_mcp_request(request)