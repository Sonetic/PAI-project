odpalanie: 

```bash
docker compose up --build
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/warszawskieceny
flask --app backend.manage db upgrade
```


baza danych:

```bash
docker exec -it pai-project-postgres-1 psql -U postgres -d warszawskieceny
```
