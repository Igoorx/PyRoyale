import sys

from twisted.python import log
log.startLogging(sys.stdout)

from autobahn.twisted import install_reactor
# we use an Autobahn utility to import the "best" available Twisted reactor
reactor = install_reactor(verbose=False,
                          require_optimal_reactor=False)

from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory
from twisted.internet.protocol import Factory
import json
import traceback
from buffer import Buffer
from player import Player
from match import Match

class MyServerProtocol(WebSocketServerProtocol):
    def __init__(self, server):
        WebSocketServerProtocol.__init__(self)

        self.server = server
        self.recv = str()

        self.stat = str()
        self.player = None

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open.")
        self.setState("l")

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))

        if self.stat == "g" and self.player != None:
            self.player.match.removePlayer(self.player)
            self.player.match = None
            self.stat = str()

    def onMessage(self, payload, isBinary):
        if len(payload) == 0:
            return

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
            self.recv = str()
            return

    def sendJSON(self, j):
        self.sendMessage(json.dumps(j), False)

    def sendBin(self, code, buff):
        self.sendMessage(Buffer().writeInt8(code).write(buff.toString() if isinstance(buff, Buffer) else buff).toString(), True)
    
    def setState(self, state):
        self.stat = state
        self.sendJSON({"packets": [
            {"state": state, "type": "s00"}
        ], "type": "s01"})

    def onTextMessage(self, payload):
        #print("Text message received: {0}".format(payload))
        packet = json.loads(payload)
        type = packet["type"]

        if self.stat == "l":
            if type == "l00": # Input state ready
                self.player = Player(self,
                                     packet["name"] if len(packet["name"].strip()) > 0 else "Mario",
                                     packet["team"],
                                     self.server.getMatch())
                self.setState("g") # Ingame

        elif self.stat == "g":
            if type == "g00": # Ingame state ready
                self.player.onEnterIngame()

            elif type == "g03": # World load completed
                self.player.onLoadComplete()

            elif type == "g50": # Vote to start
                if self.player.voted:
                    return
                self.player.voted = True
                self.player.match.voteStart()

    def onBinaryMessage(self):
        pktLenDict = { 0x10: 6, 0x11: 0, 0x12: 12, 0x13: 1, 0x18: 4, 0x20: 7, 0x30: 7 }
        
        code = ord(self.recv[0])
        if code not in pktLenDict:
            print("Unknown binary message received: {1} = {0}".format(repr(self.recv[1:]), hex(code)))
            self.recv = self.recv[len(self.recv):]
            return False
        
        pktLen = pktLenDict[code] + 1
        if len(self.recv) < pktLen:
            return False
        
        pktData = self.recv[1:pktLen]
        self.recv = self.recv[pktLen:]
        b = Buffer(pktData)
        
        if not self.player.loaded:
            return True
        
        if code == 0x10: # CREATE_PLAYER_OBJECT
            level, zone, pos = b.readInt8(), b.readInt8(), b.readShor2()
            self.player.level = level
            self.player.zone = zone
            
            self.player.match.broadBin(0x10, Buffer().writeInt16(self.player.id).write(pktData))

        elif code == 0x11: # KILL_PLAYER_OBJECT
            self.player.dead = True
            
            self.player.match.broadBin(0x11, Buffer().writeInt16(self.player.id))
            
        elif code == 0x12: # UPDATE_PLAYER_OBJECT
            level, zone, pos, sprite, reverse = b.readInt8(), b.readInt8(), b.readVec2(), b.readInt8(), b.readBool()
            self.player.level = level
            self.player.zone = zone
            self.player.posX = pos[0]
            self.player.posY = pos[1]
            
            self.player.match.broadBin(0x12, Buffer().writeInt16(self.player.id).write(pktData))
            
        elif code == 0x13: # PLAYER_OBJECT_EVENT
            type = b.readInt8()
            
            self.player.match.broadBin(0x13, Buffer().writeInt16(self.player.id).write(pktData))

        elif code == 0x18: # PLAYER_RESULT_REQUEST
            self.player.match.broadBin(0x18, Buffer().writeInt16(self.player.id).writeInt8(self.player.match.getWinners()).writeInt8(0))
            
        elif code == 0x20: # OBJECT_EVENT_TRIGGER
            level, zone, oid, type = b.readInt8(), b.readInt8(), b.readInt32(), b.readInt8()

            self.player.match.broadBin(0x20, Buffer().writeInt16(self.player.id).write(pktData))
            
        elif code == 0x30: # TILE_EVENT_TRIGGER
            level, zone, pos, type = b.readInt8(), b.readInt8(), b.readShor2(), b.readInt8()

            self.player.match.broadBin(0x30, Buffer().writeInt16(self.player.id).write(pktData))
            
        else:
            print("Unknown binary message received: {1} = {0}".format(repr(self.recv[1:]), hex(code)))
            self.recv = self.recv[len(self.recv):]
            return False

        return True
            


class MyServerFactory(WebSocketServerFactory):
    def __init__(self, url):
        WebSocketServerFactory.__init__(self, url)

        self.matches = []

    def buildProtocol(self, addr):
        protocol = MyServerProtocol(self)
        protocol.factory = self
        return protocol

    def getMatch(self):
        fmatch = None
        for match in self.matches:
            if len(match.players) < 75 and not match.closed:
                fmatch = match
                break

        if fmatch == None:
            fmatch = Match(self)
            self.matches.append(fmatch)

        return fmatch

    def removeMatch(self, match):
        if match in self.matches:
            self.matches.remove(match)
                

if __name__ == '__main__':
    factory = MyServerFactory(u"ws://127.0.0.1:9000/royale/ws")
    # factory.setProtocolOptions(maxConnections=2)

    reactor.listenTCP(9000, factory)
    reactor.run()
