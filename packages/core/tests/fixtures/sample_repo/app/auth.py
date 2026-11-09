import json

def decode_token(raw):
    return parse(raw)

def parse(raw):
    return json.dumps(raw)

def lookup(obj, name):
    return getattr(obj, name)()   # unresolvable
