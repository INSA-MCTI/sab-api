from hashlib import md5
from flask import request

def hash_all(*args):
    strings = list(map(str, args))
    hashed = md5(':'.join(strings).encode('utf-8'))
    return hashed.hexdigest()

def digest(hA1, hA2, qop, realm):
    auth = request.authorization
    return hash_all(hA1, qop, realm, hA2)
