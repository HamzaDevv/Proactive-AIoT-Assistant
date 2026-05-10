from fastapi import FastAPI, Depends, HTTPException
from app.models import CommandRequest, CommandResponse, PreferenceUpdate
from app.linker import linker
from app.ha.client import ha_client

app = FastAPI()

@app.post("/command", response_model=CommandResponse)
async def handle_command(req: CommandRequest):
    return await linker.process(req)

@app.get("/state/{device_id}")
async def get_state(device_id: str):
    # return await ha_client.get_state(device_id)
    return {"device_id": device_id, "state": "unknown"}

@app.patch("/preferences/{device_id}")
async def update_preference(device_id: str, body: PreferenceUpdate):
    # await db.spatial_nodes.update_one(
    #     {"_id": device_id},
    #     {"$set": {"preferences_md": body.markdown}}
    # )
    return {"status": "updated", "device_id": device_id}

@app.get("/spatial/tree")
async def get_tree():
    # nodes = await db.spatial_nodes.find({}, {"_id":1,"path":1,"device_type":1}).to_list(500)
    # return build_tree(nodes)
    return {"tree": []}

@app.get("/health")
async def health():
    return {"status": "ok"}
