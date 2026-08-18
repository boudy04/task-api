from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_token
from app.config import Settings

app = FastAPI()


@app.get("/protected")
def protected(token: str = Depends(get_current_token)):
    return {"token": token}


client = TestClient(app)


def test_missing_header_401():
    resp = client.get("/protected")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}


def test_wrong_token_401():
    resp = client.get("/protected", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or missing token"}


def test_valid_token_200():
    resp = client.get("/protected", headers={"Authorization": f"Bearer {Settings().auth_token}"})
    assert resp.status_code == 200
    assert resp.json() == {"token": Settings().auth_token}