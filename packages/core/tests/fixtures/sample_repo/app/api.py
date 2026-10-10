from app.auth import decode_token
from app.models import User

def handle(req):
    decode_token(req)
    return User().save()
