import os
import sys

NUM_SKINS = 6   #temporary until shop is implemented

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

try:
    from discord_webhook import DiscordWebhook
    DWH_IMPORT = True
except Exception as e:
    print("Can't import discord_webhook, discord functioning will be disabled.")
    DWH_IMPORT = False

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
        self.recv = bytearray()

        self.pendingStat = None
        self.stat = str()
        self.player = None
        self.blocked = bool()

        self.dcTimer = None
        self.maxConLifeTimer = None

    def startDCTimer(self, time):
        self.stopDCTimer()
        self.dcTimer = reactor.callLater(time, self.sendClose)

    def stopDCTimer(self):
        try:
            self.dcTimer.cancel()
        except:
            pass

    def onConnect(self, request):
        #print("Client connecting: {0}".format(request.peer))

        if "x-real-ip" in request.headers:
            self.address = request.headers["x-real-ip"]

    def onOpen(self):
        #print("WebSocket connection open.")

        if not self.address:
            self.address = self.transport.getPeer().host

        # A connection can only be alive for 30 minutes
        self.maxConLifeTimer = reactor.callLater(30 * 60, self.sendClose)
 
        self.startDCTimer(25)
        self.setState("l")

    def onClose(self, wasClean, code, reason):
        #print("WebSocket connection closed: {0}".format(reason))

        try:
            self.maxConLifeTimer.cancel()
        except:
            pass
        self.stopDCTimer()

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

        self.server.in_messages += 1

        try:
            if isBinary:
                self.recv += payload
                while len(self.recv) > 0:
                    if not self.onBinaryMessage():
                        break
            else:
                self.onTextMessage(payload.decode('utf8'))
        except Exception as e:
            traceback.print_exc()
            self.sendClose()
            self.recv.clear()
            return

    def sendJSON(self, j):
        self.server.out_messages += 1
        #print("sendJSON: "+str(j))
        self.sendMessage(json.dumps(j).encode('utf-8'), False)

    def sendBin(self, code, buff):
        self.server.out_messages += 1
        msg=Buffer().writeInt8(code).write(buff.toBytes() if isinstance(buff, Buffer) else buff).toBytes()
        #print("sendBin: "+str(code)+" "+str(msg))
        self.sendMessage(msg, True)

    def loginSuccess(self):
        self.sendJSON({"packets": [
            {"name": self.player.name, "team": self.player.team, "sid": "i-dont-know-for-what-this-is-used", "type": "l01", "skin": self.player.skin}
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
        if self.blocked or len(self.player.match.players) == 1:
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
                    self.sendClose()
                    return
                self.pendingStat = None
                
                self.stopDCTimer()

                if self.address != "127.0.0.1" and self.server.getPlayerCountByAddress(self.address) >= self.server.maxSimulIP:
                    self.exception("Too many connections")
                    self.sendClose()
                    return

                for b in self.server.blocked:
                    if b[0] == self.address:
                        self.blocked = True
                        self.setState("g") # Ingame
                        return

                team = packet["team"][:3].strip().upper()
                if len(team) == 0:
                    team = self.server.defaultTeam
                skin = packet["skin"] if "skin" in packet else 0
                if skin<0 or skin>NUM_SKINS-1:  #once shop is implemented this check should be "does player own this skin"
                    skin = 0
                self.player = Player(self,
                                     packet["name"],
                                     team,
                                     self.server.getMatch(team, packet["private"] if "private" in packet else False),
                                     skin)
                self.loginSuccess()
                self.server.players.append(self.player)
                
                self.setState("g") # Ingame

        elif self.stat == "g":
            if type == "g00": # Ingame state ready
                if self.player is None or self.pendingStat is None:
                    if self.blocked:
                        self.sendJSON({"packets": [{"game": "jail", "type": "g01"}], "type": "s01"})
                        return
                    self.sendClose()
                    return
                self.pendingStat = None
                
                self.player.onEnterIngame()

            elif type == "g03": # World load completed
                if self.player is None:
                    if self.blocked:
                        self.sendBin(0x02, Buffer().writeInt16(0).writeInt16(0))
                        self.startDCTimer(15)
                        return
                    self.sendClose()
                    return
                self.player.onLoadComplete()

            elif type == "g50": # Vote to start
                if self.player is None or self.player.voted or self.player.match.playing:
                    return
                
                self.player.voted = True
                self.player.match.voteStart()

            elif type == "g51": # (SPECIAL) Force start
                if self.server.mcode and self.server.mcode in packet["code"]:
                    self.player.match.start(True)
            
            elif type == "gsl":  # Level select
                if self.player is None or self.player.team != "" or not self.player.match.private:
                    return
                
                levelName = packet["name"]
                if levelName == "custom":
                    try:
                        self.player.match.selectCustomLevel(packet["data"])
                    except Exception as e:
                        estr = str(e)
                        estr = "\n".join(estr.split("\n")[:10])
                        self.sendJSON({"type":"gsl","name":levelName,"status":"error","message":estr})
                        return
                    
                    self.sendJSON({"type":"gsl","name":levelName,"status":"success","message":""})
                else:
                    self.player.match.selectLevel(levelName)

    def onBinaryMessage(self):
        pktLenDict = { 0x10: 6, 0x11: 0, 0x12: 12, 0x13: 1, 0x17: 2, 0x18: 4, 0x19: 0, 0x20: 7, 0x30: 7 }

        code = self.recv[0]
        if code not in pktLenDict:
            #print("Unknown binary message received: {1} = {0}".format(repr(self.recv[1:]), hex(code)))
            self.recv.clear()
            return False
            
        pktLen = pktLenDict[code] + 1
        if len(self.recv) < pktLen:
            return False
        
        b = Buffer(self.recv[1:pktLen])
        del self.recv[:pktLen]
        
        if not self.player.loaded or self.blocked or (not self.player.match.closed and self.player.match.playing):
            self.recv.clear()
            return False
        
        self.player.handlePkt(code, b, b.toBytes())
        return True

class MyServerFactory(WebSocketServerFactory):
    def __init__(self, url):
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "server.cfg"), "r") as f:
                self.configHash = hashlib.md5(f.read().encode('utf-8')).hexdigest()
            self.readConfig(self.configHash)
        except Exception as e:
            sys.stderr.write("The file \"server.cfg\" does not exist or is invalid, consider renaming \"server.cfg.example\" to \"server.cfg\".\n")
            if os.name == 'nt': # Enforce that the window opens in windows
                print("Press ENTER to exit")
                input()
            exit(1)
        
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

        if DWH_IMPORT:
            self.discordWebhook = DiscordWebhook(url=self.discordWebhookUrl)
        else:
            self.discordWebhook = None

        self.randomWorldList = list()

        self.in_messages = 0
        self.out_messages = 0

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
        self.discordWebhookUrl = config.get('Server', 'DiscordWebhookUrl').strip()
        self.playerMin = config.getint('Match', 'PlayerMin')
        self.playerCap = config.getint('Match', 'PlayerCap')
        self.autoStartTime = config.getint('Match', 'AutoStartTime')
        self.startTimer = config.getint('Match', 'StartTimer')
        self.enableVoteStart = config.getboolean('Match', 'EnableVoteStart')
        self.voteRateToStart = config.getfloat('Match', 'VoteRateToStart')
        self.allowLateEnter = config.getboolean('Match', 'AllowLateEnter')
        self.worlds = config.get('Match', 'Worlds').strip().split(',')

    def generalUpdate(self):
        playerCount = len(self.players)

        print("pc: {0}, mc: {1}, in: {2}, out: {3}".format(playerCount, len(self.matches), self.in_messages, self.out_messages))
        self.in_messages = 0
        self.out_messages = 0

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

    def getRandomWorld(self):
        if len(self.worlds) == 0:
            return None
        
        if len(self.randomWorldList) > 0:
            selected = random.choice(self.randomWorldList)
            self.randomWorldList.remove(selected)
            return selected
        
        self.randomWorldList = list(self.worlds) # Make a copy
        return self.getRandomWorld()

    # Maybe this should be in a util class?
    def leet2(self, word):
        REPLACE = { str(index): str(letter) for index, letter in enumerate('oizeasgtb') }
        letters = [ REPLACE.get(l, l) for l in word.lower() ]
        return ''.join(letters)

    def checkCurse(self, str):
        if self.checkCheckCurse(str):
            return True
        str = self.leet2(str)
        if self.checkCheckCurse(str):
            return True
        str = ''.join(e for e in str if e.isalnum())
        if self.checkCheckCurse(str):
            return True
        return False

    def checkCheckCurse(self, str):
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
        if private and roomName == "":
            return Match(self, roomName, private)
        
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
