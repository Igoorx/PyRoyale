from twisted.internet import reactor
from buffer import Buffer
import random

class Match(object):
    def __init__(self, server):
        self.server = server

        self.closed = False
        self.startTimer = int()
        self.playing = False
        self.world = "lobby"
        self.votes = int()
        self.lastId = -1
        self.players = list()
        self.winners = int()

        self.autoStartTimer = None

    def getNextPlayerId(self):
        self.lastId += 1
        return self.lastId

    def addPlayer(self, player):
        self.players.append(player)
        return self.getNextPlayerId()

    def removePlayer(self, player):
        if player not in self.players:
            return
        self.players.remove(player)
        
        if len(self.players) == 0:
            self.server.removeMatch(self)
            return
        
        if not player.dead:
            self.broadBin(0x11, Buffer().writeInt16(player.id)) # KILL_PLAYER_OBJECT

        self.broadPlayerList()

        if not self.playing and self.votes >= len(self.players) * 0.60:
            self.start()
            
    def getWinners(self):
        self.winners += 1
        return self.winners

    def broadJSON(self, j):
        for player in self.players:
            if not player.loaded:
                continue
            player.sendJSON(j)

    def broadBin(self, code, buff):
        buff = buff.toString() if isinstance(buff, Buffer) else buff
        for player in self.players:
            if not player.loaded:
                continue
            player.sendBin(code, buff)

    def broadLoadWorld(self):
        for player in self.players:
            player.dead = True
            player.loaded = False
            player.loadWorld(self.world)

    def broadStartTimer(self, time):
        self.startTimer = time * 30
        for player in self.players:
            if not player.loaded:
                continue
            player.setStartTimer(self.startTimer)
        
        if time > 0:
            reactor.callLater(1, self.broadStartTimer, time - 1)
        else:
            self.closed = True

    def broadPlayerList(self):
        self.broadJSON({"packets": [
            {"players": self.getPlayersData(),
             "type": "g12"}
        ], "type": "s01"})

    def getPlayersData(self):
        playersData = []
        for player in self.players:
            if not player.loaded or player.dead:
                continue
            playersData.append(player.getSimpleData())
        return playersData

    def onPlayerReady(self, player):
        if not self.playing: # Ensure that the game starts even with fewer players
            try:
                self.autoStartTimer.cancel()
            except:
                pass
            self.autoStartTimer = reactor.callLater(60, self.start, True)
            
        if self.world == "lobby" or not player.lobbier:
            for p in self.players:
                if not p.loaded:
                    continue
                player.sendBin(0x10, p.serializePlayerObject())
            if self.startTimer != 0 or self.closed:
                player.setStartTimer(self.startTimer)
        self.broadPlayerList()

        if not self.playing and len(self.getPlayersData()) >= 75:
            reactor.callLater(5, self.start)

    def voteStart(self):
        self.votes += 1
        if not self.playing and self.votes >= len(self.players) * 0.60:
            self.start()

    def start(self, forced = False):
        if self.playing or (not forced and len(self.players) < 15): # We need at-least 15 players to start
            return
        self.playing = True
        try:
            self.autoStartTimer.cancel()
        except:
            pass
        
        self.world = random.choice(["world-1", "world-2", "world-3", "world-5", "world-6", "world-l1", "world-p"])
        self.broadLoadWorld()

        reactor.callLater(1, self.broadStartTimer, 5)
        
