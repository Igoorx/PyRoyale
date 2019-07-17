import os
import hashlib
try:
    import argon2
    A2_IMPORT = True
except:
    # Maybe we can switch to a built-in passwordHasher?
    print("Can't import argon2-cffi, accounts functioning will be disabled.")
    A2_IMPORT = False
import pickle
import secrets

accounts = {}
session = {}

if A2_IMPORT:
    ph = argon2.PasswordHasher()
else:
    ph = None

def loadState():
    global accounts
    try:
        if os.path.exists("server.dat"):
            with open("server.dat", "rb") as f:
                accounts = pickle.load(f)
    except Exception as e:
        print(e)

def persistState():
    with open("server.dat", "wb") as f:
        pickle.dump(accounts, f)

def register(username, password):
    if ph is None:
        return False, "account system disabled"
    if len(username) < 3:
        return False, "username too short"
    if len(username) > 20:
        return False, "username too long"
    if len(password) < 8:
        return False, "password too short"
    if len(password) > 120:
        return False, "password too long"
    if username in accounts:
        return False, "account already registered"
    
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = ph.hash(password.encode('utf-8')+salt)
    
    acc = { "salt": salt,
            "pwdhash": pwdhash,
            "nickname": username,
            "skin": 0,
            "squad": "" }
    accounts[username] = acc
    persistState()
    
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    
    token = secrets.token_urlsafe(32)
    session[token] = username
    acc2["session"] = token
    return True, acc2

def login(username, password):
    if ph is None:
        return False, "account system disabled"
    
    invalidMsg = "invalid user name or password"
    if len(username) < 3:
        return False, invalidMsg
    if len(username) > 20:
        return False, invalidMsg
    if len(password) < 8:
        return False, invalidMsg
    if len(password) > 120:
        return False, invalidMsg
    if username not in accounts:
        return False, invalidMsg
    acc = accounts[username]
    
    try:
        ph.verify(acc["pwdhash"], password.encode('utf-8')+acc["salt"])
    except:
        return False, invalidMsg
    
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    
    token = secrets.token_urlsafe(32)
    session[token] = username
    acc2["session"] = token
    return True, acc2

def resumeSession(token):
    if token not in session:
        return False, "session expired, please log in"
    
    username = session[token]
    if username not in accounts:
        return False, "invalid user name or password"
    acc = accounts[username]
    
    acc2 = acc.copy()
    del acc2["salt"]
    del acc2["pwdhash"]
    
    acc2["username"] = username
    acc2["session"] = token
    return True, acc2

def updateAccount(username, data):
    if username not in accounts:
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
