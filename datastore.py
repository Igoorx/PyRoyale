import os
import hashlib
import argon2
import pickle

accounts = {}

ph = argon2.PasswordHasher()

def loadState():
    global accounts
    try:
        if os.path.exists("server.dat"):
            with open("server.dat", "rb") as f:
                accounts = pickle.load(f)
                #print(str(len(accounts)) + " accounts")
    except Exception as e:
        print(e)

def persistState():
    with open("server.dat", "wb") as f:
        pickle.dump(accounts, f)

def register(username, password):
    if username in accounts:
        return (False, "account already registered")
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = ph.hash(password.encode('utf-8')+salt)
    acc = {"salt" : salt, "pwdhash" : pwdhash, "nickname": username, "skin": 0, "squad": "" }
    accounts[username] = acc
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    persistState()
    return (True, acc2)

def login(username, password):
    invalidMsg = "invalid user name or password"
    if not username in accounts:
        return (False, invalidMsg)
    acc = accounts[username]
    try:
        ph.verify(acc["pwdhash"], password.encode('utf-8')+acc["salt"])
    except:
        return (False, invalidMsg)
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    return (True, acc2)

def updateAccount(username, data):
    if not username in accounts:
        return
    acc = accounts[username]
    if "nickname" in data:
        acc["nickname"] = data["nickname"]
    if "squad" in data:
        acc["squad"] = data["squad"]
    if "skin" in data:
        acc["skin"] = data["skin"]
    persistState()

loadState()
