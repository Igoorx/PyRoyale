import os
import sys

if sys.version_info.major != 3:
    sys.stderr.write("You need python 3.7 or later to run this script\n")
    if os.name == 'nt': # Enforce that the window opens in windows
        print("Press ENTER to exit")
        input()
    exit(1)

from twisted.python import log
log.startLogging(sys.stdout)

from autobahn.twisted import install_reactor
# we use an Autobahn utility to import the "best" available Twisted reactor
reactor = install_reactor(verbose=False,
                          require_optimal_reactor=False)

from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from twisted.internet.protocol import Factory
import json
import random
import hashlib
import traceback
import configparser
from buffer import Buffer
from player import Player
from match import Match

class MyServerProtocol(WebSocketServerProtocol):
    def __init__(self, server):
        WebSocketServerProtocol.__init__(self)

        self.server = server
        self.address = str()
        self.recv = bytes()

        self.pendingStat = None
        self.stat = str()
        self.player = None
        self.trustCount = int()
        self.blocked = bool()

        self.lastX = int()
        self.lastXOk = True

        self.dcTimer = None

    def onConnect(self, request):
        #print("Client connecting: {0}".format(request.peer))

        if "x-real-ip" in request.headers:
            self.address = request.headers["x-real-ip"]

    def onOpen(self):
        #print("WebSocket connection open.")

        if not self.address:
            self.address = self.transport.getPeer().host
 
        self.dcTimer = reactor.callLater(25, self.transport.loseConnection)
        self.setState("l")

    def onClose(self, wasClean, code, reason):
        #print("WebSocket connection closed: {0}".format(reason))
        
        try:
            self.dcTimer.cancel()
        except:
            pass

        if self.stat == "g" and self.player != None:
            self.server.players.remove(self.player)
            self.player.match.removePlayer(self.player)
            self.player.match = None
            self.player = None
            self.pendingStat = None
            self.stat = str()

    def onMessage(self, payload, isBinary):
        if len(payload) == 0:
            return

        self.server.messages += 1

        try:
            if isBinary:
                self.recv += payload
                while len(self.recv) > 0:
                    self.onBinaryMessage()
            else:
                self.onTextMessage(payload.decode('utf8'))
        except Exception as e:
            traceback.print_exc()
            self.transport.loseConnection()
            self.recv = bytes()
            return

    def sendJSON(self, j):
        self.sendMessage(json.dumps(j).encode('utf-8'), False)

    def sendBin(self, code, buff):
        msg=Buffer().writeInt8(code).write(buff.toBytes() if isinstance(buff, Buffer) else buff).toBytes()
        self.sendMessage(msg, True)

    def loginSuccess(self):
        self.sendJSON({"packets": [
            {"name": self.player.name, "team": self.player.team, "sid": "i-dont-know-for-what-this-is-used", "type": "l01"}
        ], "type": "s01"})
    
    def setState(self, state):
        self.stat = self.pendingStat = state
        self.sendJSON({"packets": [
            {"state": state, "type": "s00"}
        ], "type": "s01"})

    def exception(self, message):
        self.sendJSON({"packets": [
            {"message": message, "type": "x00"}
        ], "type": "s01"})

    def block(self, reason):
        if self.blocked:
            return
        print("Player blocked: {0}".format(self.player.name))
        self.blocked = True
        if not self.player.dead:
            self.player.match.broadBin(0x11, Buffer().writeInt16(self.player.id), self.player.id) # KILL_PLAYER_OBJECT
        self.server.blockAddress(self.address, self.player.name, reason)

    def onTextMessage(self, payload):
        #print("Text message received: {0}".format(payload))
        packet = json.loads(payload)
        type = packet["type"]

        if self.stat == "l":
            if type == "l00": # Input state ready
                if self.pendingStat is None:
                    self.transport.loseConnection()
                    return
                self.pendingStat = None
                
                try:
                    self.dcTimer.cancel()
                except:
                    pass

                if self.address != "127.0.0.1" and self.server.getPlayerCountByAddress(self.address) >= self.server.maxSimulIP:
                    self.exception("Too many connections")
                    self.transport.loseConnection()
                    return

                for b in self.server.blocked:
                    if b[0] == self.address:
                        self.blocked = True

                team = packet["team"][:3].strip().upper()
                if len(team) == 0:
                    team = self.server.defaultTeam
                
                self.player = Player(self,
                                     packet["name"],
                                     team,
                                     self.server.getMatch(team, packet["private"] if "private" in packet else False))
                self.loginSuccess()
                self.server.players.append(self.player)
                
                self.setState("g") # Ingame

        elif self.stat == "g":
            if type == "g00": # Ingame state ready
                if self.player is None or self.pendingStat is None:
                    self.transport.loseConnection()
                    return
                self.pendingStat = None
                
                self.player.onEnterIngame()

            elif type == "g03": # World load completed
                if self.player is None:
                    self.transport.loseConnection()
                    return
                self.lastXOk = True
                self.player.onLoadComplete()

            elif type == "g50": # Vote to start
                if self.player is None or self.player.voted or self.player.match.playing:
                    return
                
                self.player.voted = True
                self.player.match.voteStart()

            elif type == "g51": # (SPECIAL) Force start
                if self.server.mcode and self.server.mcode in packet["code"]:
                    self.player.match.start(True)

    def onBinaryMessage(self):
        pktLenDict = { 0x10: 6, 0x11: 0, 0x12: 12, 0x13: 1, 0x17: 2, 0x18: 4, 0x19: 0, 0x20: 7, 0x30: 7 }
        
        code = self.recv[0]
        if code not in pktLenDict:
            #print("Unknown binary message received: {1} = {0}".format(repr(self.recv[1:]), hex(code)))
            self.recv = bytes()
            return False
            
        pktLen = pktLenDict[code] + 1
        if len(self.recv) < pktLen:
            return False
        
        pktData = self.recv[1:pktLen]
        self.recv = self.recv[pktLen:]
        b = Buffer(pktData)
        
        if not self.player.loaded or self.blocked or (not self.player.match.closed and self.player.match.playing):
            self.recv = bytes()
            return False
        
        if code == 0x10: # CREATE_PLAYER_OBJECT
            level, zone, pos = b.readInt8(), b.readInt8(), b.readShor2()
            self.player.level = level
            self.player.zone = zone
            
            wasDead = self.player.dead
            self.player.dead = False
            if wasDead:
                self.player.match.broadPlayerList()
            
            try:
                self.dcTimer.cancel()
            except:
                pass
            
            self.player.match.broadBin(0x10, Buffer().writeInt16(self.player.id).write(pktData))

        elif code == 0x11: # KILL_PLAYER_OBJECT
            if self.player.dead:
                return
            
            self.player.dead = True
            self.dcTimer = reactor.callLater(15, self.transport.loseConnection)
            
            self.player.match.broadBin(0x11, Buffer().writeInt16(self.player.id))
            
        elif code == 0x12: # UPDATE_PLAYER_OBJECT
            if self.player.dead:
                return

            level, zone, pos, sprite, reverse = b.readInt8(), b.readInt8(), b.readVec2(), b.readInt8(), b.readBool()
            self.player.level = level
            self.player.zone = zone
            self.player.posX = pos[0]
            self.player.posY = pos[1]

            if ((#self.player.posX < 23 or
                 self.player.posY >= 58.5) or sprite > 5) and self.player.match.world == "lobby" and zone == 0:
                self.block(0x1)
                return
            
            self.player.match.broadBin(0x12, Buffer().writeInt16(self.player.id).write(pktData))
            
        elif code == 0x13: # PLAYER_OBJECT_EVENT
            if self.player.dead:
                return

            type = b.readInt8()

            if self.player.match.world == "lobby":
                self.block(0x2)
                return
            
            self.player.match.broadBin(0x13, Buffer().writeInt16(self.player.id).write(pktData))

        elif code == 0x17:
            killer = b.readInt16()
            if self.player.id == killer:
                return
            
            killer = self.player.match.getPlayer(killer)
            if killer is None:
                return

            killer.sendBin(0x17, Buffer().writeInt16(self.player.id).write(pktData))

        elif code == 0x18: # PLAYER_RESULT_REQUEST
            if self.player.dead or self.player.win:
                return

            self.player.win = True
            self.dcTimer = reactor.callLater(120, self.transport.loseConnection)
            
            self.player.match.broadBin(0x18, Buffer().writeInt16(self.player.id).writeInt8(self.player.match.getWinners()).writeInt8(0))
            
        elif code == 0x19:
            self.trustCount += 1
            if self.trustCount > 8:
                self.block(0x3)

        elif code == 0x20: # OBJECT_EVENT_TRIGGER
            if self.player.dead:
                return

            level, zone, oid, type = b.readInt8(), b.readInt8(), b.readInt32(), b.readInt8()

            self.player.match.broadBin(0x20, Buffer().writeInt16(self.player.id).write(pktData))
            
        elif code == 0x30: # TILE_EVENT_TRIGGER
            if self.player.dead:
                return

            level, zone, pos, type = b.readInt8(), b.readInt8(), b.readShor2(), b.readInt8()

            self.player.match.broadBin(0x30, Buffer().writeInt16(self.player.id).write(pktData))
            
        else:
            print("Unknown binary message received: {1} = {0}".format(repr(self.recv[1:]), hex(code)))
            self.recv = bytes()
            return False

        return True

class MyServerFactory(WebSocketServerFactory):
    def __init__(self, url):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "server.cfg"), "r") as f:
            self.configHash = hashlib.md5(f.read().encode('utf-8')).hexdigest()
        self.readConfig(self.configHash)
        
        WebSocketServerFactory.__init__(self, url.format(self.listenPort))

        self.players = list()
        self.matches = list()
        
        self.curse = list()
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "words.json"), "r") as f:
                self.curse = json.loads(f.read())
        except:
            pass

        self.blocked = list()
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "blocked.json"), "r") as f:
                self.blocked = json.loads(f.read())
        except:
            pass

        self.messages = 0

        reactor.callLater(5, self.generalUpdate)

    def readConfig(self, cfgHash):
        self.configHash = cfgHash
            
        config = configparser.ConfigParser()
        config.read('server.cfg')

        self.listenPort = config.getint('Server', 'ListenPort')
        self.mcode = config.get('Server', 'MCode').strip()
        self.statusPath = config.get('Server', 'StatusPath').strip()
        self.defaultName = config.get('Server', 'DefaultName').strip()
        self.defaultTeam = config.get('Server', 'DefaultTeam').strip()
        self.maxSimulIP = config.getint('Server', 'MaxSimulIP')
        self.playerMin = config.getint('Match', 'PlayerMin')
        self.playerCap = config.getint('Match', 'PlayerCap')
        self.startTimer = config.getint('Match', 'StartTimer')
        self.enableVoteStart = config.getboolean('Match', 'EnableVoteStart')
        self.voteRateToStart = config.getfloat('Match', 'VoteRateToStart')
        self.allowLateEnter = config.getboolean('Match', 'AllowLateEnter')
        self.worlds = config.get('Match', 'Worlds').strip().split(',')

    def generalUpdate(self):
        playerCount = len(self.players)

        print("pc: {0}, mc: {1}, mp5s: {2}".format(playerCount, len(self.matches), self.messages))
        self.messages = 0

        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "server.cfg"), "r") as f:
                cfgHash = hashlib.md5(f.read().encode('utf-8')).hexdigest()
                if cfgHash != self.configHash:
                    self.readConfig(cfgHash)
                    print("Configuration reloaded.")
        except:
            print("Failed to reload configuration.")
        
        if self.statusPath:
            try:
                with open(self.statusPath, "w") as f:
                    f.write('{"active":' + str(playerCount) + '}')
            except:
                pass
            
        reactor.callLater(5, self.generalUpdate)

    def checkCurse(self, str):
        if len(str) <= 3:
            return False
        str = str.lower()
        for w in self.curse:
            if len(w) <= 3:
                continue
            if w in str:
                return True
        return False

    def blockAddress(self, address, playerName, reason):
        if not address in self.blocked:
            self.blocked.append([address, playerName, reason])
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "blocked.json"), "w") as f:
                    f.write(json.dumps(self.blocked))
            except:
                pass

    def getPlayerCountByAddress(self, address):
        count = 0
        for player in self.players:
            if player.client.address == address:
                count += 1
        return count

    def buildProtocol(self, addr):
        protocol = MyServerProtocol(self)
        protocol.factory = self
        return protocol

    def getMatch(self, roomName, private):
        if roomName == "":
            private = False
        
        fmatch = None
        for match in self.matches:
            if not match.closed and len(match.players) < self.playerCap and private == match.private and (not private or match.roomName == roomName):
                if not self.allowLateEnter and match.playing:
                    continue
                fmatch = match
                break

        if fmatch == None:
            fmatch = Match(self, roomName, private)
            self.matches.append(fmatch)

        return fmatch

    def removeMatch(self, match):
        if match in self.matches:
            self.matches.remove(match)
                

if __name__ == '__main__':
    factory = MyServerFactory(u"ws://127.0.0.1:{0}/royale/ws")
    # factory.setProtocolOptions(maxConnections=2)

    reactor.listenTCP(factory.listenPort, factory)
    reactor.run()
