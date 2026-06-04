import uuid

class Object:
    token = ""
    id = ""

    def __init__(self, token):
        self.token = token
    

    def getToken(self):
        return self.token

    def getID(self):
        return self.id

    def setToken(self, token):
        self.token = token

    def __str__(self):
        return f"{self.id} : {self.token}"