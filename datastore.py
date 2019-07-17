import os
import hashlib
import argon2
import pickle
import secrets

accounts = {}
session = {}

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
    if len(username) < 5:
        return (False, "username too short")
    if len(password) < 8:
        return (False, "password too short")
    if username in accounts:
        return (False, "account already registered")
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = ph.hash(password.encode('utf-8')+salt)
    acc = {"salt" : salt, "pwdhash" : pwdhash, "nickname": username, "skin": 0, "squad": "" }
    accounts[username] = acc
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    token = secrets.token_urlsafe(32)
    acc2["session"] = token
    session[token] = username
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
    token = secrets.token_urlsafe(32)
    acc2["session"] = token
    session[token] = username
    return (True, acc2)

def resumeSession(token):
    if not token in session:
        return (False, "session expired, please log in")
    username = session[token]
    if not username in accounts:
        return (False, "invalid user name or password")
    acc = accounts[username]
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    acc2["username"] = username
    acc2["session"] = token
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

def logout(token):
    if token in session:
        del session[token]

loadState()
