"""Create local-only credentials once; never overwrite existing configuration."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
env = root / ".env"
if env.exists():
    raise SystemExit(".env already exists; keeping existing credentials.")
admin, product, company, password = [secrets.token_urlsafe(24) for _ in range(4)]
email = "founder@ventureforge.local"
(root / ".local").mkdir(exist_ok=True)
env.write_text(
    f"POSTGRES_PASSWORD={admin}\nPRODUCT_DB_PASSWORD={product}\nCOMPANY_DB_PASSWORD={company}\n"
    f"DATABASE_URL=postgresql+psycopg://vf_product:{product}@127.0.0.1:55432/vf_product\n"
    f"TEST_DATABASE_URL=postgresql+psycopg://vf_product:{product}@127.0.0.1:55432/vf_product_test\n"
    "APP_ORIGIN=http://127.0.0.1:3000\nCOOKIE_SECURE=false\n"
    f"BOOTSTRAP_EMAIL={email}\nBOOTSTRAP_PASSWORD={password}\n",
    encoding="utf-8",
)
(root / ".local" / "sign-in.txt").write_text(
    f"Local Venture Forge sign-in\nURL: http://127.0.0.1:3000\nEmail: {email}\nPassword: {password}\n",
    encoding="utf-8",
)
print("Created .env and .local/sign-in.txt. Credentials are excluded from git.")
