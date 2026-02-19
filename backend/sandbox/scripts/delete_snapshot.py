# pyright: basic
# type: ignore

import os
from daytona import Daytona, DaytonaConfig # type: ignore  # pyright: ignore
from dotenv import load_dotenv  # type: ignore # pyright: ignore

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(env_path)
load_dotenv()

DAYTONA_API_KEY = os.getenv("DAYTONA_API_KEY")
DAYTONA_API_URL = os.getenv("DAYTONA_API_URL")

# Khởi tạo Daytona client
config = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL)
daytona = Daytona(config)

# Tên snapshot cần xóa
SNAPSHOT_NAME = os.getenv("SNAPSHOT_NAME", "sandbox-daytona")

# Kiểm tra và xóa snapshot
try:
    snapshots = daytona.snapshot.list()
    found = False
    for s in snapshots.items:
        print(f"\n📋 Snapshot info:")
        print(f"   Name: '{s.name}'")
        print(f"   ID: {s.id}")
        print(f"   Image: {s.image_name}")
        print(f"   State: {s.state}")
        
        if s.name == SNAPSHOT_NAME:
            found = True
            print(f"\n🗑️ Attempting to delete...")
            try:
                daytona.snapshot.delete(s)
                print(f"✅ Deleted snapshot: {SNAPSHOT_NAME}")
            except Exception as del_err:
                print(f"❌ Delete failed: {del_err}")
            break
    
    if not found:
        print(f"❌ Snapshot '{SNAPSHOT_NAME}' not found")
except Exception as e:
    print(f"❌ Error: {e}")

# List snapshots còn lại
print("\n📋 Remaining snapshots:")
try:
    snapshots = daytona.snapshot.list()
    for s in snapshots.items:
        print(f"  - {s.name} ({s.image_name})")
except Exception as e:
    print(f"❌ Error listing snapshots: {e}")
