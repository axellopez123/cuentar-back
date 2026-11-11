import io
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest_asyncio.fixture
async def test_session(tmp_path, monkeypatch):
    from app.services.storage_service import storage_service
    test_storage_dir = tmp_path / "uploads"
    monkeypatch.setattr(storage_service, "base_dir", test_storage_dir)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test_api.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_full_api_workflow(test_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # 2. Register user
        reg_payload = {
            "email": "arquitecto@cuentar.com",
            "password": "Password123!",
            "full_name": "Axel Lopez",
            "role": "primary",
        }
        res_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 201
        user_data = res_reg.json()
        assert user_data["email"] == "arquitecto@cuentar.com"

        # 3. Login
        login_res = await client.post(
            "/api/v1/auth/login",
            data={"username": "arquitecto@cuentar.com", "password": "Password123!"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Get current user
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["full_name"] == "Axel Lopez"

        # 5. Create category
        cat_res = await client.post(
            "/api/v1/categories",
            headers=headers,
            json={"name": "Hogar & Supermercado", "icon": "shopping-cart", "color_hex": "#10B981"},
        )
        assert cat_res.status_code == 201
        category_id = cat_res.json()["id"]

        # 6. Create credit card
        card_payload = {
            "alias": "BBVA Platino",
            "card_type": "credit",
            "currency": "MXN",
            "credit_limit": "60000.00",
            "current_balance": "60000.00",
            "monthly_budget_limit": "20000.00",
            "statement_closing_day": 15,
            "payment_due_day": 5,
            "color_hex": "#1E40AF",
        }
        card_res = await client.post("/api/v1/cards", headers=headers, json=card_payload)
        assert card_res.status_code == 201
        card_data = card_res.json()
        card_id = card_data["id"]

        # 7. Check card status with live billing cycle
        detail_res = await client.get(f"/api/v1/cards/{card_id}", headers=headers)
        assert detail_res.status_code == 200
        card_detail = detail_res.json()
        assert card_detail["status"]["billing_cycle"] is not None
        assert card_detail["status"]["credit"]["credit_limit"] == "60000.00"

        # 8. Create expense (MSI)
        expense_payload = {
            "card_id": card_id,
            "category_id": category_id,
            "amount": "12000.00",
            "description": "Refrigerador nuevo a 12 MSI",
            "is_shared": True,
            "shared_split_ratio": "50.00",
            "is_installment": True,
            "installment_months": 12,
        }
        exp_res = await client.post("/api/v1/transactions/expense", headers=headers, json=expense_payload)
        assert exp_res.status_code == 201
        tx_data = exp_res.json()
        tx_id = tx_data["id"]
        assert tx_data["card_alias"] == "BBVA Platino"
        assert tx_data["is_installment"] is True
        assert tx_data["installment_plan"]["monthly_amount"] == "1000.00"

        # 9. Upload attachment to transaction
        fake_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        files = {"files": ("ticket_compra.pdf", io.BytesIO(fake_pdf), "application/pdf")}
        upload_res = await client.post(
            f"/api/v1/transactions/{tx_id}/attachments",
            headers=headers,
            files=files,
        )
        assert upload_res.status_code == 200
        attachments_data = upload_res.json()
        assert len(attachments_data) == 1
        att_id = attachments_data[0]["id"]

        # 10. Download attachment
        download_res = await client.get(f"/api/v1/attachments/{att_id}/download", headers=headers)
        assert download_res.status_code == 200
        assert download_res.content == fake_pdf

        # 11. Register payment to card
        payment_payload = {
            "card_id": card_id,
            "amount": "5000.00",
            "description": "Pago anticipado",
        }
        pay_res = await client.post("/api/v1/transactions/payment", headers=headers, json=payment_payload)
        assert pay_res.status_code == 201
        assert pay_res.json()["type"] == "payment"

        # 12. Check Dashboard
        dash_res = await client.get("/api/v1/dashboard", headers=headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        assert len(dash_data["upcoming_payments"]) == 1
        assert dash_data["upcoming_payments"][0]["amount_to_pay"] == "7000.00"  # 12000 - 5000
        assert len(dash_data["participants_breakdown"]) == 1
        assert dash_data["participants_breakdown"][0]["total_spent"] == "12000.00"
