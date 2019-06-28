from buffer import Buffer

class Player(object):
    def __init__(self, client, name, team, match):
        self.client = client
        self.server = client.server
        self.match = match
        
        self.name = name[:20].upper()
        self.team = team[:3].upper()
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
        return Buffer().writeInt16(self.id).writeInt8(self.level).writeInt8(self.zone).writeShor2(self.posX, self.posY).toString()

    def loadWorld(self, worldName):
        self.dead = True
        self.loaded = False
        self.sendJSON({"packets": [
            {"game": worldName, "type": "g01"}
        ], "type": "s01"})

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
        if self.loaded:
            return
        
        self.level = 0
        self.zone = 0
        self.posX = 35
        self.posY = 3
        self.win = False
        self.dead = False
        self.loaded = True
        
        self.sendBin(0x02, Buffer().writeInt16(self.id)) # ASSIGN_PID

        self.match.onPlayerReady(self)
        
