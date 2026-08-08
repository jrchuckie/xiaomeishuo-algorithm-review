import os
from io import BytesIO
from uuid import uuid4

os.environ["APP_ENV"] = "development"
os.environ["MODEL_MODE"] = "mock"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
headers = {"X-Installation-ID": str(uuid4())}
fake_image = ("reference.jpg", BytesIO(b"not-a-real-jpeg-but-valid-for-mock"), "image/jpeg")


def test_health_reports_no_user_data_store() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["stores_user_data"] is False
    assert response.json()["model_mode"] == "mock"


def test_board_preview_rejects_non_xhs_url() -> None:
    response = client.post(
        "/api/v1/boards/preview",
        headers=headers,
        json={"url": "https://example.com/board/123"},
    )
    assert response.status_code == 400


def test_board_preview_accepts_public_xhs_board() -> None:
    response = client.post(
        "/api/v1/boards/preview",
        headers=headers,
        json={"url": "https://www.xiaohongshu.com/board/abc"},
    )
    assert response.status_code == 200
    assert response.json()["status"] in {"ready", "limited"}
    assert isinstance(response.json()["items"], list)


def test_profile_requires_at_least_three_references() -> None:
    response = client.post(
        "/api/v1/aesthetic/profile",
        headers=headers,
        files=[("references", fake_image)],
    )
    assert response.status_code == 400


def test_profile_plan_and_mock_generation_flow() -> None:
    images = [
        ("references", (f"reference-{index}.jpg", BytesIO(f"image-{index}".encode()), "image/jpeg"))
        for index in range(3)
    ]
    profile_response = client.post(
        "/api/v1/aesthetic/profile",
        headers=headers,
        files=images,
        data={"calibration_json": __import__("json").dumps(["下颌线再清楚一点"])},
    )
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["source_count"] == 3

    plan_response = client.post(
        "/api/v1/edits/plan",
        headers=headers,
        files={"source": ("source.jpg", BytesIO(b"source"), "image/jpeg")},
        data={"profile_json": __import__("json").dumps(profile), "intensity": "visible"},
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert "眼睛" in plan["locked_regions"]

    generation_response = client.post(
        "/api/v1/edits/generate",
        headers=headers,
        files={"source": ("source.jpg", BytesIO(b"source"), "image/jpeg")},
        data={"plan_json": __import__("json").dumps(plan)},
    )
    assert generation_response.status_code == 200
    assert generation_response.json()["result_mode"] == "mock_original"

    medical_response = client.post(
        "/api/v1/medical/plan",
        headers=headers,
        files={
            "front": ("front.jpg", BytesIO(b"front"), "image/jpeg"),
            "side": ("side.jpg", BytesIO(b"side"), "image/jpeg"),
        },
        data={
            "profile_json": __import__("json").dumps(profile),
            "preferences_json": __import__("json").dumps({"budget": "balanced"}),
            "selected_directions_json": __import__("json").dumps(["下颌线", "下巴"]),
            "intensity": "balanced",
        },
    )
    assert medical_response.status_code == 200
    medical_plan = medical_response.json()
    assert len(medical_plan["candidates"]) == 2
    assert "眼睛" in medical_plan["locked_regions"]

    medical_generation_response = client.post(
        "/api/v1/medical/generate",
        headers=headers,
        files={"source": ("front.jpg", BytesIO(b"front"), "image/jpeg")},
        data={
            "plan_json": __import__("json").dumps(medical_plan),
            "intensity": "balanced",
        },
    )
    assert medical_generation_response.status_code == 200
    assert medical_generation_response.json()["result_mode"] == "mock_original"
