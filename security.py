import os,secrets,time
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

ph=PasswordHasher()
def hash_password(p): return ph.hash(p)
def verify_password(h,p):
    try: return ph.verify(h,p)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError): return False
def csrf_token(request):
    if "csrf" not in request.session: request.session["csrf"]=secrets.token_urlsafe(32)
    return request.session["csrf"]
def check_csrf(request,token):
    if not token or not secrets.compare_digest(str(request.session.get("csrf","")),str(token)):
        raise HTTPException(403,"CSRF validation failed")
def signed_serializer():
    key=os.getenv("SECRET_KEY","")
    if len(key)<32: raise RuntimeError("SECRET_KEY must be at least 32 characters")
    return URLSafeTimedSerializer(key,salt="elephant-private-file")
def safe_gstin(value):
    import re
    return bool(re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]",(value or "").upper()))


class LazySessionMiddleware:
    """Read session security settings when ASGI starts, not when app.main is imported.

    This avoids freezing an empty/test secret or insecure cookie setting merely
    because a test plugin imported the application before fixtures ran.
    """
    def __init__(self, app, **options):
        self.app = app
        self.options = options
        self._middleware = None

    async def __call__(self, scope, receive, send):
        if self._middleware is None:
            from starlette.middleware.sessions import SessionMiddleware
            self._middleware = SessionMiddleware(
                self.app,
                secret_key=os.getenv("SECRET_KEY", ""),
                session_cookie=self.options.get("session_cookie", "et_session"),
                max_age=self.options.get("max_age", 8 * 3600),
                same_site=self.options.get("same_site", "lax"),
                https_only=os.getenv("COOKIE_SECURE", "true").lower() == "true",
            )
        await self._middleware(scope, receive, send)
