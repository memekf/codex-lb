from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Account, AccountActiveTimeframe


class AccountActiveTimeframeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[AccountActiveTimeframe]:
        result = await self._session.execute(
            select(AccountActiveTimeframe).order_by(AccountActiveTimeframe.created_at, AccountActiveTimeframe.id)
        )
        return list(result.scalars().all())

    async def get(self, timeframe_id: str) -> AccountActiveTimeframe | None:
        return await self._session.get(AccountActiveTimeframe, timeframe_id)

    async def exists(self, timeframe_id: str) -> bool:
        result = await self._session.execute(
            select(AccountActiveTimeframe.id).where(AccountActiveTimeframe.id == timeframe_id).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def create(self, timeframe: AccountActiveTimeframe) -> AccountActiveTimeframe:
        self._session.add(timeframe)
        await self._session.commit()
        await self._session.refresh(timeframe)
        return timeframe

    async def update(self, timeframe: AccountActiveTimeframe) -> AccountActiveTimeframe:
        await self._session.commit()
        await self._session.refresh(timeframe)
        return timeframe

    async def delete(self, timeframe: AccountActiveTimeframe) -> None:
        await self._session.delete(timeframe)
        await self._session.commit()

    async def count_assignments(self, timeframe_id: str) -> int:
        result = await self._session.execute(
            select(func.count(Account.id)).where(Account.active_timeframe_id == timeframe_id)
        )
        return int(result.scalar_one() or 0)

    async def list_accounts_for_coverage(self) -> Sequence[Account]:
        result = await self._session.execute(
            select(Account)
            .options(selectinload(Account.active_timeframe))
            .order_by(Account.email, Account.id)
        )
        return list(result.scalars().all())
