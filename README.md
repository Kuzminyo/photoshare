# PhotoShare — REST API

Командний проєкт курсу Python Web (GoIT). REST API для обміну світлинами на **FastAPI**,
**PostgreSQL** + **SQLAlchemy**, сховище зображень — **Cloudinary**.

## Можливості

**Аутентифікація**
- JWT: access + refresh токени, ротація refresh-токена.
- Вхід за email **або** юзернеймом.
- Три ролі: `user`, `moderator`, `admin`. Перший зареєстрований користувач — завжди адміністратор.
- Доступ за ролями — залежність `RoleAccess` (`src/services/roles.py`).
- `logout`: access-токен (і refresh, якщо передати) потрапляє в чорний список до кінця терміну дії.
- Заблоковані (неактивні) користувачі не можуть увійти, а їхні токени перестають працювати.

**Світлини**
- Завантаження з описом і до 5 тегів (`POST /api/photos`, multipart).
- Теги унікальні для всього застосунку: існуючий тег перевикористовується, новий створюється.
- Отримання (`GET`), редагування опису/тегів (`PUT`), видалення (`DELETE`) — власник або адміністратор.
- Трансформації Cloudinary: розмір, обрізка, gravity, ефекти (sepia, grayscale, cartoonify, blur, …),
  поворот, заокруглення кутів, формат. Кожна трансформація зберігається як окреме посилання в БД.
- QR-код для кожного посилання (`GET /api/links/{token}/qr`, публічний PNG) — скануєте телефоном і бачите зображення.

**Коментарі**
- Користувачі коментують будь-які світлини, редагують лише свої коментарі.
- Видаляти коментарі можуть модератори та адміністратори.
- У БД зберігаються `created_at` і `updated_at`.

**Профілі та адміністрування**
- Публічний профіль за юзернеймом: ім'я, дата реєстрації, кількість світлин і коментарів.
- `GET/PATCH /api/users/me` — власні дані (email, юзернейм, ім'я, біо, пароль).
- Адміністратор: список користувачів, бан/розбан, зміна ролі.

**Додатково**
- Рейтинг 1–5 зірок: один раз на світлину, не для власних світлин; середнє значення у відповіді.
  Модератори й адміністратори переглядають і видаляють оцінки.
- Пошук за ключовим словом (опис і теги) або тегом, фільтри за рейтингом і датою, сортування за рейтингом або датою.
  Фільтр за автором (`username`) — лише для модераторів і адміністраторів.

## Структура

```
main.py                  # FastAPI app, підключення роутерів
src/conf/config.py       # налаштування з .env
src/database/            # engine, сесії, ORM-моделі
src/repository/          # робота з БД
src/routes/              # auth, users, photos (+links), comments, ratings
src/services/            # JWT і паролі, ролі, Cloudinary, QR, побудова відповідей
migrations/              # Alembic
tests/                   # pytest + unittest
```

## Запуск через Docker Compose (рекомендовано)

1. Скопіюйте налаштування й заповніть їх:
   ```bash
   cp .env.example .env
   ```
   - `JWT_SECRET_KEY` — довгий випадковий рядок:
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `CLOUDINARY_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — з
     [консолі Cloudinary](https://console.cloudinary.com) (без них завантаження світлин повертає 503).
2. Запустіть усе однією командою:
   ```bash
   docker compose up -d --build
   ```
   Міграції застосовуються автоматично під час старту контейнера.
3. Відкрийте Swagger: <http://localhost:8080/docs> (ReDoc: `/redoc`).

Порти змінюються в `.env`: `APP_PORT` (API, за замовчуванням 8080) і `POSTGRES_PORT` (5440).

## Локальний запуск без Docker для API

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d postgres   # або власний PostgreSQL, вкажіть DATABASE_URL у .env
alembic upgrade head
uvicorn main:app --reload
```

Swagger: <http://localhost:8000/docs>. Для локального запуску поставте `BASE_URL=http://localhost:8000`.

## Як користуватися

1. `POST /api/auth/signup` — реєстрація (перший користувач стає адміністратором).
2. `POST /api/auth/login` — у Swagger натисніть **Authorize** і введіть email або юзернейм та пароль.
3. `POST /api/photos` — завантажте світлину з описом і тегами.
4. `POST /api/photos/{id}/transform` — наприклад
   `{"width": 400, "height": 400, "crop": "fill", "effect": "sepia", "radius": "max"}`.
   У відповіді є `url` трансформованого зображення та `qr_code_url`.
5. `GET /api/photos?keyword=sea&sort_by=rating` — пошук і сортування.
6. `POST /api/photos/{id}/comments`, `POST /api/photos/{id}/ratings` — коментарі та оцінки.
7. `POST /api/auth/logout` — вихід (тіло `{"refresh_token": "..."}` необов'язкове).

### Основні маршрути

| Метод | Шлях | Доступ |
|---|---|---|
| POST | `/api/auth/signup`, `/api/auth/login` | усі |
| GET | `/api/auth/refresh_token` | refresh-токен |
| POST | `/api/auth/logout` | авторизовані |
| GET, PATCH | `/api/users/me` | авторизовані |
| GET | `/api/users/{username}` | усі |
| GET | `/api/users` | admin |
| PATCH | `/api/users/{id}/ban`, `/unban`, `/role` | admin |
| POST, GET | `/api/photos` | авторизовані (фільтр `username` — moderator/admin) |
| GET, PUT, DELETE | `/api/photos/{id}` | GET — авторизовані; PUT/DELETE — власник або admin |
| POST | `/api/photos/{id}/transform` | власник або admin |
| GET | `/api/photos/{id}/links` | власник або admin |
| GET | `/api/links/{token}`, `/api/links/{token}/qr` | усі (публічні) |
| POST, GET | `/api/photos/{id}/comments` | авторизовані |
| PUT | `/api/comments/{id}` | автор коментаря |
| DELETE | `/api/comments/{id}` | moderator, admin |
| POST | `/api/photos/{id}/ratings` | авторизовані (не власник) |
| GET | `/api/photos/{id}/ratings` | moderator, admin |
| DELETE | `/api/ratings/{id}` | moderator, admin |

## Тести

```bash
pip install -r requirements-dev.txt
pytest --cov
```

За замовчуванням тести працюють на SQLite в пам'яті, Cloudinary замокано. Ті самі тести можна запустити
на PostgreSQL:

```bash
# Windows PowerShell: $env:TEST_DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5440/photoshare_test"
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5440/photoshare_test pytest
```

Поточне покриття — 100% (поріг у `.coveragerc` — 90%).

## Деплой (Koyeb або Fly.io)

Застосунку потрібні PostgreSQL і змінні оточення з `.env.example`. `Dockerfile` сам застосовує міграції
й слухає порт зі змінної `PORT`.

**Koyeb**
1. Створіть базу: *Databases → Create PostgreSQL* і скопіюйте connection string.
2. *Create Service → GitHub*, оберіть репозиторій, builder — **Dockerfile**, порт `8000`.
3. Змінні: `DATABASE_URL` (рядок підключення з Koyeb, наприклад `postgres://user:pass@host/db?sslmode=require`),
   `JWT_SECRET_KEY`, `CLOUDINARY_*`, `BASE_URL=https://<ваш-сервіс>.koyeb.app`.

**Fly.io**
```bash
fly launch --no-deploy                    # створить fly.toml з Dockerfile
fly postgres create && fly postgres attach <db-app-name>
fly secrets set JWT_SECRET_KEY=... CLOUDINARY_NAME=... CLOUDINARY_API_KEY=... CLOUDINARY_API_SECRET=... BASE_URL=https://<app>.fly.dev
fly deploy
```
`fly postgres attach` сам задає `DATABASE_URL`. Префікси `postgres://` і `postgresql://` застосунок
перетворює на `postgresql+psycopg2://` автоматично.
