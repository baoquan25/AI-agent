# pyright: basic
# type: ignore
import os
from daytona import Daytona, DaytonaConfig, CreateSnapshotParams, Resources # type: ignore  # pyright: ignore
from dotenv import load_dotenv  # type: ignore # pyright: ignore

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)
load_dotenv()

DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL")


config = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL)
daytona = Daytona(config)

# Dùng image từ local registry
params = CreateSnapshotParams(
    name="sandbox-daytona",
    image="registry:6000/daytona/sandbox-daytona:v1.0",
    resources=Resources(
        cpu=1,
        memory=2,  # GB
        disk=5     # GB
    )
)

snapshot = daytona.snapshot.create(params, on_logs=print)
print(f"✅ Snapshot created: {snapshot.name}")
print(f"   Image: {snapshot.image_name}")