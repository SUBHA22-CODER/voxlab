import asyncio
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import Agent, User

async def main():
    async with SessionLocal() as db:
        users = (await db.scalars(select(User))).all()
        for u in users:
            existing = (await db.scalars(select(Agent).where(Agent.user_id == u.id))).all()
            if not existing:
                a1 = Agent(
                    user_id=u.id,
                    name="Customer Support Agent (Demo)",
                    description="Support desk agent for tracking, modifying, and troubleshooting orders.",
                    endpoint="http://localhost:8100/conversation",
                    agent_type="http",
                    config={"timeout_s": 15},
                )
                a2 = Agent(
                    user_id=u.id,
                    name="Wispr Flow Dictation Agent (Demo)",
                    description="Voice dictation and natural speech cleaning pipeline for Wispr Flow.",
                    endpoint="http://localhost:8200/conversation",
                    agent_type="http",
                    config={"timeout_s": 15},
                )
                db.add_all([a1, a2])
                print(f"Provisioned starter agents for user {u.id} ({u.email})")
        await db.commit()
        
        all_agents = (await db.scalars(select(Agent))).all()
        print(f"Total agents now in DB: {len(all_agents)}")
        for a in all_agents:
            print(f"  Agent {a.id}: user_id={a.user_id}, name='{a.name}', endpoint='{a.endpoint}'")

if __name__ == "__main__":
    asyncio.run(main())
