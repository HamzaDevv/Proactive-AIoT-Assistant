from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from .sense_aggregator import SenseAggregator

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize aggregator (with error handling)
try:
    aggregator = SenseAggregator()
except Exception as e:
    print(f"Warning: Failed to initialize aggregator: {e}")
    aggregator = None


@app.get("/")
async def read_root():
    return {"status": "ok"}


@app.get("/sense")
async def sense():
    return await aggregator.collect()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
