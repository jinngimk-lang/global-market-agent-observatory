from app.local_env import load_local_env

# Local developer runs commonly start with `python -m uvicorn app.api.main:app`.
# Load `.env` before app.api.main constructs Settings so local market-data
# credentials/configuration actually reach the runtime. Existing process or
# container environment variables keep precedence.
load_local_env()
