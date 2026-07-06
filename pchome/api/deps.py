"""服務單例的組裝與存取：routers 透過 request.app.state.container 取得服務"""

from dataclasses import dataclass

from fastapi import Request

from ..core.config import CHECKOUTS_FILE, PRODUCTS_FILE
from ..services.auth_service import AuthService
from ..services.checkout_store import CheckoutRecordStore
from ..services.event_bus import EventBus
from ..services.job_service import JobService
from ..services.product_store import ProductStore
from ..services.settings_store import SettingsStore


@dataclass
class Container:
    store: ProductStore
    checkout_store: CheckoutRecordStore
    bus: EventBus
    jobs: JobService
    auth: AuthService
    settings: SettingsStore

    def state(self) -> dict:
        """完整狀態快照：所有變更狀態的路由都回傳這個形狀"""
        snapshot = self.jobs.state()
        return {
            "auth": self.auth.status(),
            "products": snapshot["products"],
            "groups": snapshot["groups"],
            "checkouts": self.checkout_store.list(),
        }


def build_container() -> Container:
    store = ProductStore(PRODUCTS_FILE)
    checkout_store = CheckoutRecordStore(CHECKOUTS_FILE)
    bus = EventBus()
    settings = SettingsStore()
    jobs = JobService(store, checkout_store, bus, settings)
    auth = AuthService()
    return Container(store, checkout_store, bus, jobs, auth, settings)


def get_container(request: Request) -> Container:
    return request.app.state.container
