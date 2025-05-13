import json

# Создаем словарь с cookies
cookies = [
    {
        "name": "X-MID",
        "value": "Zv0qTQABAAGUX0pTd4oHqXdLUEXn",
        "domain": ".instagram.com",
        "path": "/"
    },
    {
        "name": "IG-U-DS-USER-ID",
        "value": "69867164430",
        "domain": ".instagram.com",
        "path": "/"
    },
    {
        "name": "IG-INTENDED-USER-ID",
        "value": "69867164430",
        "domain": ".instagram.com",
        "path": "/"
    },
    {
        "name": "Authorization",
        "value": "Bearer IGT:2:eyJkc191c2VyX2lkIjoiNjk4NjcxNjQ0MzAiLCJzZXNzaW9uaWQiOiI2OTg2NzE2NDQzMCUzQXZPalZJWU5UWUJjeHZ6JTNBMiUzQUFZY0dveExkaEVNYU41RUN1d0ZDRjNMMTl1MjFIUDdYWW96NHNuQm9QQSJ9",
        "domain": ".instagram.com",
        "path": "/"
    },
    {
        "name": "X-IG-WWW-Claim",
        "value": "hmac.AR3X5LJ9wp_fxv8wVye04MOR7qNTrWl9frpMUoNV9GHeNmPf",
        "domain": ".instagram.com",
        "path": "/"
    },
    {
        "name": "IG-U-RUR",
        "value": "RVA,69867164430,1771699092:01f7885ad5ca0de1a9644934bf4863f8b95c314e1fd32c696eb88dde7dd5208ef244edf1",
        "domain": ".instagram.com",
        "path": "/"
    },
    {
        "name": "IG-U-IG-DIRECT-REGION-HINT",
        "value": "CLN,69867164430,1771699091:01f78ca9c3560e4de2974d123a6ed5dd26bb8026d7fbb57a18a3562e104875f7bc1cc62f",
        "domain": ".instagram.com",
        "path": "/"
    }
]

# Сохраняем в файл
with open("Anna5272c1999_cookies.json", "w") as f:
    json.dump(cookies, f, indent=4)

print("Файл cookies.json успешно создан!")