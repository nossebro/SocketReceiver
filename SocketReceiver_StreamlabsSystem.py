#---------------------------------------
#   Import Libraries
#---------------------------------------
import logging
from logging.handlers import TimedRotatingFileHandler
import clr
import re
import os
import codecs
import json
import time
clr.AddReference("websocket-sharp.dll")
from WebSocketSharp import WebSocket

#---------------------------------------
#   [Required] Script Information
#---------------------------------------
ScriptName = "SocketReceiver"
Website = "https://github.com/nossebro/SocketReceiver"
Creator = "nossebro"
Version = "0.0.2"
Description = "Read events from the local SLCB socket"

#---------------------------------------
#   Script Variables
#---------------------------------------
ScriptSettings = None
LocalAPI = None
Logger = None
LastTime = None
LocalSocket = None
LocalSocketIsConnected = False
SettingsFile = os.path.join(os.path.dirname(__file__), "Settings.json")
UIConfigFile = os.path.join(os.path.dirname(__file__), "UI_Config.json")
APIKeyFile = os.path.join(os.path.dirname(__file__), "API_Key.js")

#---------------------------------------
#   Script Classes
#---------------------------------------
class StreamlabsLogHandler(logging.StreamHandler):
	def emit(self, record):
		try:
			message = self.format(record)
			Parent.Log(ScriptName, message)
			self.flush()
		except (KeyboardInterrupt, SystemExit):
			raise
		except:
			self.handleError(record)

class Settings(object):
	def __init__(self, settingsfile=None):
		defaults = self.DefaultSettings(UIConfigFile)
		try:
			with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
				settings = json.load(f, encoding="utf-8")
			self.__dict__ = MergeLists(defaults, settings)
		except:
			self.__dict__ = defaults

	def DefaultSettings(self, settingsfile=None):
		defaults = dict()
		with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
			ui = json.load(f, encoding="utf-8")
		for key in ui:
			try:
				defaults[key] = ui[key]['value']
			except:
				if key != "output_file":
					Parent.Log(ScriptName, "DefaultSettings(): Could not find key {0} in settings".format(key))
		return defaults

	def Reload(self, jsondata):
		self.__dict__ = MergeLists(self.DefaultSettings(UIConfigFile), json.loads(jsondata, encoding="utf-8"))

#---------------------------------------
#   Script Functions
#---------------------------------------
def GetLogger():
	log = logging.getLogger(ScriptName)
	log.setLevel(logging.DEBUG)

	sl = StreamlabsLogHandler()
	sl.setFormatter(logging.Formatter("%(funcName)s(): %(message)s"))
	sl.setLevel(logging.INFO)
	log.addHandler(sl)

	fl = TimedRotatingFileHandler(filename=os.path.join(os.path.dirname(__file__), "info"), when="w0", backupCount=8, encoding="utf-8")
	fl.suffix = "%Y%m%d"
	fl.setFormatter(logging.Formatter("%(asctime)s  %(funcName)s(): %(levelname)s: %(message)s"))
	fl.setLevel(logging.INFO)
	log.addHandler(fl)

	if ScriptSettings.DebugMode:
		dfl = TimedRotatingFileHandler(filename=os.path.join(os.path.dirname(__file__), "debug"), when="h", backupCount=24, encoding="utf-8")
		dfl.suffix = "%Y%m%d%H%M%S"
		dfl.setFormatter(logging.Formatter("%(asctime)s  %(funcName)s(): %(levelname)s: %(message)s"))
		dfl.setLevel(logging.DEBUG)
		log.addHandler(dfl)

	log.debug("Logger initialized")
	return log

def GetAPIKey(apifile=None):
	API = dict()
	try:
		with codecs.open(apifile, encoding="utf-8-sig", mode="r") as f:
			lines = f.readlines()
		matches = re.search(r"\"\s?([0-9a-f]+)\".*\"\s?(ws://[0-9.:]+/\w+)\"", "".join(lines))
		if matches:
			API["Key"] = matches.group(1)
			API["Socket"] = matches.group(2)
			Logger.debug("Got Key ({0}) and Socket ({1}) from API_Key.js".format(matches.group(1), matches.group(2)))
	except:
		Logger.critical("API_Key.js is missing in script folder")
	return API

def MergeLists(x = dict(), y = dict()):
	z = dict()
	for attr in x:
		if attr not in y:
			z[attr] = x[attr]
		else:
			z[attr] = y[attr]
	return z

#---------------------------------------
#   Chatbot Initialize Function
#---------------------------------------
def Init():
	global ScriptSettings
	ScriptSettings = Settings(SettingsFile)
	global Logger
	Logger = GetLogger()

	global LocalSocket
	global LocalAPI
	LocalAPI = GetAPIKey(APIKeyFile)
	LocalSocket = WebSocket(LocalAPI["Socket"])
	LocalSocket.OnOpen += LocalSocketConnected
	LocalSocket.OnClose += LocalSocketDisconnected
	LocalSocket.OnMessage += LocalSocketEvent
	LocalSocket.OnError += LocalSocketError

	if all (keys in LocalAPI for keys in ("Key", "Socket")):
		LocalSocket.Connect()
	else:
		Logger.critical("API_Key.js missing from script folder")
	
	global LastTime
	LastTime = time.time()

#---------------------------------------
#   Chatbot Script Unload Function
#---------------------------------------
def Unload():
	global LocalSocket
	global Logger
	# Disconnect LocalSocket cleanly
	if LocalSocket:
		LocalSocket.Close(1000, "Program exit")
		LocalSocket = None
		Logger.debug("LocalSocket Disconnected")
	if Logger:
		Logger.handlers.Clear()
		Logger = None

#---------------------------------------
#   Chatbot Save Settings Function
#---------------------------------------
def ReloadSettings(jsondata):
	ScriptSettings.Reload(jsondata)
	Logger.debug("Settings reloaded")

	if LocalSocket and not LocalSocket.IsAlive:
		if all (keys in LocalAPI for keys in ("Key", "Socket")):
			LocalSocket.Connect()

	Parent.BroadcastWsEvent('{0}_UPDATE_SETTINGS'.format(ScriptName.upper()), json.dumps(ScriptSettings.__dict__))
	Logger.debug(json.dumps(ScriptSettings.__dict__), True)

#---------------------------------------
#   Chatbot Execute Function
#---------------------------------------
def Execute(data):
	pass

#---------------------------------------
#   Chatbot Tick Function
#---------------------------------------
def Tick():
	global LastTime
	Now = time.time()
	SinceLast = Now - LastTime
	if SinceLast >= 10 and not LocalSocketIsConnected and all (keys in LocalAPI for keys in ("Key", "Socket")):
		Logger.warning("No EVENT_CONNECTED received from LocalSocket, reconnecting")
		try:
			LocalSocket.Close(1006, "No connection confirmation received")
		except:
			Logger.error("Could not close LocalSocket socket gracefully")
		LocalSocket.Connect()
		LastTime = Now
	if SinceLast >= 60:
		if not LocalSocket.IsAlive:
			Logger.warning("LocalSocket seems dead, reconnecting")
			try:
				LocalSocket.Close()
			except:
				Logger.error("Could not close LocalSocket gracefully")
			LocalSocket.Connect()
		LastTime = Now

#---------------------------------------
#   LocalSocket Connect Function
#---------------------------------------
def LocalSocketConnected(ws, data):
	global LocalAPI
	Auth = {
		"author": Creator,
		"website": Website,
		"api_key": LocalAPI["Key"],
		"events": ScriptSettings.Events.split(",")
	}
	ws.Send(json.dumps(Auth))
	Logger.debug("Auth: {0}".format(json.dumps(Auth)))

#---------------------------------------
#   LocalSocket Disconnect Function
#---------------------------------------
def LocalSocketDisconnected(ws, data):
	global LocalSocketIsConnected
	LocalSocketIsConnected = False
	if data.Reason:
		Logger.debug("{0}: {1}".format(data.Code, data.Reason))
	elif data.Code == 1000 or data.Code == 1005:
		Logger.debug("{0}: Normal exit".format(data.Code))
	else:
		Logger.debug("{0}: Unknown reason".format(data.Code))
	if not data.WasClean:
		Logger.warning("Unclean socket disconnect")

#---------------------------------------
#   LocalSocket Error Function
#---------------------------------------
def LocalSocketError(ws, data):
	Logger.error(data.Message)
	if data.Exception:
		Logger.exception(data.Exception)

#---------------------------------------
#   LocalSocket Event Function
#---------------------------------------
def LocalSocketEvent(ws, data):
	if data.IsText:
		event = json.loads(data.Data)
		if "data" in event and isinstance(event["data"], str):
			event["data"] = json.loads(event["data"])
		if event["event"] == "EVENT_CONNECTED":
			global LocalSocketIsConnected
			LocalSocketIsConnected = True
			Logger.info(event["data"]["message"])
		else:
			Logger.warning("Unhandled event: {0}: {1}".format(event["event"], event["data"]))
