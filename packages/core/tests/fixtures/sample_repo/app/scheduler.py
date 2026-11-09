from app.jobs import nightly


def tick():
    return nightly()
