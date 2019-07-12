import re
import emoji
from twisted.internet import reactor
from buffer import Buffer

try:
    from discord_webhook import DiscordEmbed
except Exception as e:
    pass

class Player(object):
    def __init__(self, client, name, team, match, skin):
        self.client = client
        self.server = client.server
        self.match = match
        self.skin = skin
        
        self.name = ' '.join(emoji.emojize(re.sub(r"[^\x00-\x7F]+", "", emoji.demojize(name)).strip())[:20].split()).upper()
        self.team = team
        if len(self.team) > 0 and self.server.checkCurse(self.name):
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

        self.trustCount = int()
        self.lastX = int()
        self.lastXOk = True
        
        self.id = match.addPlayer(self)

    def sendJSON(self, j):
        self.client.sendJSON(j)

    def sendBin(self, code, b):
        self.client.sendBin(code, b)

    def getSimpleData(self):
        return {"id": self.id, "name": self.name, "team": self.team}

    def serializePlayerObject(self):
        return Buffer().writeInt16(self.id).writeInt8(self.level).writeInt8(self.zone).writeShor2(self.posX, self.posY).writeInt16(self.skin).toBytes()

    def loadWorld(self, worldName, levelData):
        self.dead = True
        self.loaded = False
        self.pendingWorld = worldName
        msg = {"game": worldName, "type": "g01"}
        if worldName == "custom":
            msg["levelData"] = levelData
        self.sendJSON({"packets": [msg], "type": "s01"})
        self.client.startDCTimer(15)

    def setStartTimer(self, time):
        self.sendJSON({"packets": [
            {"time": time, "type": "g13"}
        ], "type": "s01"})

    def onEnterIngame(self):
        if not self.dead:
            return
        
        if self.match.world == "lobby":
            self.lobbier = True

        self.match.onPlayerEnter(self)
        self.loadWorld(self.match.world, self.match.customLevelData)

    def onLoadComplete(self):
        if self.loaded or self.pendingWorld is None:
            return

        self.client.stopDCTimer()
        
        self.level = 0
        self.zone = 0
        self.posX = 35
        self.posY = 3
        self.win = False
        self.dead = False
        self.loaded = True
        self.pendingWorld = None
        self.lastXOk = True
        
        self.sendBin(0x02, Buffer().writeInt16(self.id).writeInt16(self.skin)) # ASSIGN_PID

        self.match.onPlayerReady(self)

    def handlePkt(self, code, b, pktData):
        if code == 0x10: # CREATE_PLAYER_OBJECT
            level, zone, pos = b.readInt8(), b.readInt8(), b.readShor2()
            self.level = level
            self.zone = zone
            
            self.dead = False
            self.client.stopDCTimer()
            
            self.match.broadBin(0x10, Buffer().writeInt16(self.id).write(pktData).writeInt16(self.skin))

        elif code == 0x11: # KILL_PLAYER_OBJECT
            if self.dead:
                return
            
            self.dead = True
            self.client.startDCTimer(60)
            
            self.match.broadBin(0x11, Buffer().writeInt16(self.id))
            
        elif code == 0x12: # UPDATE_PLAYER_OBJECT
            if self.dead:
                return

            level, zone, pos, sprite, reverse = b.readInt8(), b.readInt8(), b.readVec2(), b.readInt8(), b.readBool()
            self.level = level
            self.zone = zone
            self.posX = pos[0]
            self.posY = pos[1]

            if sprite > 5 and self.match.world == "lobby" and zone == 0:
                self.client.block(0x1)
                return
            
            self.match.broadBin(0x12, Buffer().writeInt16(self.id).write(pktData))
            
        elif code == 0x13: # PLAYER_OBJECT_EVENT
            if self.dead:
                return

            type = b.readInt8()

            if self.match.world == "lobby":
                self.client.block(0x2)
                return
            
            self.match.broadBin(0x13, Buffer().writeInt16(self.id).write(pktData))

        elif code == 0x17:
            killer = b.readInt16()
            if self.id == killer:
                return
            
            killer = self.match.getPlayer(killer)
            if killer is None:
                return

            killer.sendBin(0x17, Buffer().writeInt16(self.id).write(pktData))

        elif code == 0x18: # PLAYER_RESULT_REQUEST
            if self.dead or self.win:
                return

            self.win = True
            self.client.startDCTimer(120)

            pos = self.match.getWinners()
            if self.server.discordWebhook is not None and pos == 1 and not self.match.private:
                name = self.name
                # We already filter players that have a squad so...
                if len(self.team) == 0 and self.server.checkCurse(self.name):
                    name = "[ censored ]"
                embed = DiscordEmbed(description='**%s** has achieved **#1** victory royale!' % name, color=0xffff00)
                self.server.discordWebhook.add_embed(embed)
                self.server.discordWebhook.execute()
                self.server.discordWebhook.remove_embed(0)
            
            self.match.broadBin(0x18, Buffer().writeInt16(self.id).writeInt8(pos).writeInt8(0))
            
        elif code == 0x19:
            self.trustCount += 1
            if self.trustCount > 8:
                self.client.block(0x3)

        elif code == 0x20: # OBJECT_EVENT_TRIGGER
            if self.dead:
                return

            level, zone, oid, type = b.readInt8(), b.readInt8(), b.readInt32(), b.readInt8()

            if self.match.world == "lobby" and oid == 458761:
                self.match.goldFlowerTaken = True

            self.match.broadBin(0x20, Buffer().writeInt16(self.id).write(pktData))
            
        elif code == 0x30: # TILE_EVENT_TRIGGER
            if self.dead:
                return

            level, zone, pos, type = b.readInt8(), b.readInt8(), b.readShor2(), b.readInt8()

            self.match.broadBin(0x30, Buffer().writeInt16(self.id).write(pktData))

