import re
import emoji
from twisted.internet import reactor
from buffer import Buffer

class Player(object):
    def __init__(self, client, name, team, match):
        self.client = client
        self.server = client.server
        self.match = match
        
        self.name = ' '.join(emoji.emojize(re.sub(r"[^\x00-\x7F]+", "", emoji.demojize(name)).strip())[:20].split()).upper()
        self.team = team
        if len(self.team) > 0 and self.server.checkCurse(self.name): # Don't filter players out of squads
            self.name = str()
        if len(self.name) == 0:
            self.name = self.server.defaultName
        self.pendingWorld = None
        self.level = int()
        self.zone = int()
        self.posX = int()
        self.posY = int()
        self.dead = True
        self.win = bool()
        self.voted = bool()
        self.loaded = bool()
        self.lobbier = bool()
        
        self.id = match.addPlayer(self)

    def sendJSON(self, j):
        self.client.sendJSON(j)

    def sendBin(self, code, b):
        self.client.sendBin(code, b)

    def getSimpleData(self):
        return {"id": self.id, "name": self.name, "team": self.team}

    def serializePlayerObject(self):
        return Buffer().writeInt16(self.id).writeInt8(self.level).writeInt8(self.zone).writeShor2(self.posX, self.posY).toBytes()

    def loadWorld(self, worldName):
        self.dead = True
        self.loaded = False
        self.pendingWorld = worldName
        self.sendJSON({"packets": [
            {"game": worldName, "type": "g01"}
        ], "type": "s01"})
        self.client.dcTimer = reactor.callLater(15, self.client.transport.loseConnection)

    def setStartTimer(self, time):
        self.sendJSON({"packets": [
            {"time": time, "type": "g13"}
        ], "type": "s01"})

    def onEnterIngame(self):
        if not self.dead:
            return
        
        if self.match.world == "lobby":
            self.lobbier = True
            
        self.loadWorld(self.match.world)

    def onLoadComplete(self):
        if self.loaded or self.pendingWorld is None:
            return

        try:
            self.client.dcTimer.cancel()
        except:
            pass
        
        self.level = 0
        self.zone = 0
        self.posX = 35
        self.posY = 3
        self.win = False
        self.dead = False
        self.loaded = True
        self.pendingWorld = None
        
        self.sendBin(0x02, Buffer().writeInt16(self.id)) # ASSIGN_PID

        self.match.onPlayerReady(self)
        
