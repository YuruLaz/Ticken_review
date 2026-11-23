# SupportDesk AI

Customers submit support tickets. An AI pipeline classifies each ticket, looks up the knowledge base and drafts a reply. Simple tickets are answered automatically, the rest wait for an agent to approve, edit or reject the reply.

## What you need

- Docker
- An Anthropic API key (writes the replies)
- A Gemini API key (searches the knowledge base)

## Start up

1. Create a file called `.env` in the project folder:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/supportdesk
JWT_SECRET_KEY=any-long-random-text
ANTHROPIC_API_KEY=your-anthropic-key
GEMINI_API_KEY=your-gemini-key
```

2. Build and start everything:

```
docker compose up -d --build
```

3. Load the knowledge base and create staff accounts (only the first time):

```
docker compose exec app python -m scripts.seed_kb
docker compose exec app python -m scripts.create_user agent@example.com secret123 --role agent
docker compose exec app python -m scripts.create_user admin@example.com secret123 --role admin --name Admin
```

4. Open the app:

- Web app: http://localhost:8001
- API docs: http://localhost:8000/docs

Customers create their own account on the web app's register page. Agents and admins log in with the accounts from step 3.

## Stop

```
docker compose down
```

Your data is kept. To delete it too, run `docker compose down -v`.

## Run the tests

The tests use a fake AI, so they need no API keys and cost nothing. They do need the database container and a separate test database:

```
docker compose up -d db
docker compose exec db createdb -U postgres supportdesk_test
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```
