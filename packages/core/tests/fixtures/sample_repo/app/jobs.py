from app.auth import decode_token

def nightly():
    return decode_token("y")

def run():                   # same bare name as cli.run → ambiguity
    return nightly()
