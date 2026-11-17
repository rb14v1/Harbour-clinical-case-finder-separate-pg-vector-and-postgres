from decouple import Csv, config

from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", cast=Csv())

# Azure Container Apps (and any TLS-terminating ingress) terminates HTTPS at the edge and
# forwards to the container over plain internal HTTP, naming the real scheme in
# X-Forwarded-Proto. Without this setting Django never sees a secure request, so the
# HTTPS redirect below sends every request back to the URL it was just asked for — an
# infinite 301 loop that makes the whole component unreachable.
#
# Azure sets X-Forwarded-Proto itself and overwrites any value a client sends, so this
# header cannot be spoofed to fake a secure request.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
