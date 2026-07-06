"""服務單例的組裝與存取：routers 透過 request.app.state.container 取得服務"""

from dataclasses import dataclass

from fastapi import Request

from ..infra.event_bus import EventBus
from ..repositories.auth_state_repository import AuthStateRepository
from ..repositories.checkout_repository import CheckoutRecordRepository
from ..repositories.product_repository import ProductRepository
from ..repositories.settings_repository import SettingsRepository
from ..services.auth_service import AuthService
from ..services.job_service import JobService


@dataclass
class Container:
    product_repository: ProductRepository
    checkout_repository: CheckoutRecordRepository
    bus: EventBus
    jobs: JobService
    auth: AuthService
    settings_repository: SettingsRepository

    def state(self) -> dict:
        """完整狀態快照：所有變更狀態的路由都回傳這個形狀"""
        snapshot = self.jobs.state()
        return {
            "auth": self.auth.status(),
            "products": snapshot["products"],
            "groups": snapshot["groups"],
            "checkouts": self.checkout_repository.list(),
        }


def build_container() -> Container:
    product_repository = ProductRepository()
    checkout_repository = CheckoutRecordRepository()
    bus = EventBus()
    settings_repository = SettingsRepository()
    auth_state_repository = AuthStateRepository()
    jobs = JobService(
        product_repository,
        checkout_repository,
        bus,
        settings_repository,
        auth_state_repository,
    )
    auth = AuthService(auth_state_repository)
    return Container(
        product_repository, checkout_repository, bus, jobs, auth, settings_repository
    )


def get_container(request: Request) -> Container:
    return request.app.state.container
