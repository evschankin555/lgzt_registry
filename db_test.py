from db import SessionLocal
from models import Company, User
from sqlalchemy import select
import asyncio

async def main():

    async with SessionLocal() as session:

        stmt = select(User).where(User.tg_id == 995863310)

        query = await session.execute(stmt)

        result = query.scalars().all()

        if len(result) > 0:

            for user in result:

                user.tg_id = None


        await session.commit()





asyncio.run(main())