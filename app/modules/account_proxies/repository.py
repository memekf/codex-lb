from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, AccountProxy


class AccountProxyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[AccountProxy]:
        result = await self._session.execute(select(AccountProxy).order_by(AccountProxy.created_at, AccountProxy.id))
        return list(result.scalars().all())

    async def get(self, proxy_id: str) -> AccountProxy | None:
        return await self._session.get(AccountProxy, proxy_id)

    async def exists(self, proxy_id: str) -> bool:
        result = await self._session.execute(select(AccountProxy.id).where(AccountProxy.id == proxy_id).limit(1))
        return result.scalar_one_or_none() is not None

    async def create(self, proxy: AccountProxy) -> AccountProxy:
        self._session.add(proxy)
        await self._session.commit()
        await self._session.refresh(proxy)
        return proxy

    async def update(self, proxy: AccountProxy) -> AccountProxy:
        await self._session.commit()
        await self._session.refresh(proxy)
        return proxy

    async def delete(self, proxy: AccountProxy) -> None:
        await self._session.delete(proxy)
        await self._session.commit()

    async def count_assignments(self, proxy_id: str) -> int:
        result = await self._session.execute(select(func.count(Account.id)).where(Account.proxy_id == proxy_id))
        return int(result.scalar_one() or 0)
