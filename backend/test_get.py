from fastapi.testclient import TestClient

from auth import create_session_jwt
from main import app

# Generate an admin token for testing
token = create_session_jwt("00000000-0000-0000-0000-000000000000", "admin")

client = TestClient(app)
response = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {token}"})
print("STATUS:", response.status_code)
print("BODY:", response.text[:500])
