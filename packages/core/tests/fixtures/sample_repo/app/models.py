class Base:
    def save(self):
        return 1

class User(Base):
    def save(self):          # overrides Base.save
        return super().save()

class Admin(User):
    pass
