from fastapi import FastAPI, Request
from .mcp_handlers import handle_mcp_request

app = FastAPI()

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    data = await request.json()
    return await handle_mcp_request(data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
