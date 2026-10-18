import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Configure it in your environment or .env file."
    )

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is missing. Configure it in your environment or .env file."
    )

JWT_ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

RELATIONSHIP_REQUEST_COOLDOWN_HOURS = int(
    os.getenv("RELATIONSHIP_REQUEST_COOLDOWN_HOURS", "24")
)


RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
PASSWORD_RESET_FROM_EMAIL = os.getenv(
    "RESEND_FROM_EMAIL",
    "LoveChat <onboarding@resend.dev>",
).strip()
PASSWORD_RESET_REDIRECT_URL = os.getenv(
    "PASSWORD_RESET_REDIRECT_URL",
    "lovechat://auth/reset-password",
).strip()
PASSWORD_RESET_EXPIRE_MINUTES = int(
    os.getenv("PASSWORD_RESET_EXPIRE_MINUTES", "30")
)
