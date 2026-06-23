odpalanie: 
docker compose up --build
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/warszawskieceny
flask --app backend.manage db upgrade
