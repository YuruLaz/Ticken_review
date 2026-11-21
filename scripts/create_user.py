"""Create a user with any role, since /auth/register only makes customers. Run from the project root:

    python -m scripts.create_user agent@example.com secret123 --role agent
"""

import argparse
import asyncio

from app.core.security import hash_password
from app.database.db import SessionLocal
from app.models import User


async def main(email: str, password: str, role: str, name: str):
    async with SessionLocal() as session:
        session.add(User(email=email, full_name=name, hashed_password=hash_password(password), role=role))
        await session.commit()
    print(f"Created {role} {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--role", choices=["customer", "agent", "admin"], default="agent")
    parser.add_argument("--name", default="Support Agent")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.password, args.role, args.name))
