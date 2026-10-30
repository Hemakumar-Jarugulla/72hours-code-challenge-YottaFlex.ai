"""
Application Server Runner.
Starts the FastAPI application and serves the web interface.
"""

import os
import sys
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"\n=======================================================")
    print(f"Starting FairCollect AI Server on http://{host}:{port}")
    print(f"=======================================================\n")
    uvicorn.run("api.server:app", host=host, port=port, reload=False)
