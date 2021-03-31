#!/usr/bin/env python2
# -*- coding: utf-8 -*-

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
clr.AddReference("websocket-sharp.dll")
from WebSocketSharp import WebSocket

#---------------------------------------
#   [Required] Script Information
#---------------------------------------
ScriptName = "SocketReceiver"
Website = "https://github.com/nossebro/SocketReceiver"
Creator = "nossebro"
Version = "0.0.7"
Description = "Read events from the local SLCB socket"

#---------------------------------------
#   Script Variables
#---------------------------------------
ScriptSettings = None
LocalAPI = None
Logger = None
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
			self.__dict__ = self.MergeSettings(defaults, settings)
		except:
			self.__dict__ = defaults

	def MergeSettings(self, x=dict(), y=dict()):
		z = x.copy()
		for attr in x:
			if attr in y:
				z[attr] = y[attr]
		return z

	def DefaultSettings(self, settingsfile=None):
		defaults = dict()
		with codecs.open(settingsfile, encoding="utf-8-sig", mode="r") as f:
			ui = json.load(f, encoding="utf-8")
		for key in ui:
			try:
				defaults[key] = ui[key]["value"]
			except:
				continue
		return defaults

	def Reload(self, jsondata):
		self.__dict__ = self.MergeSettings(self.DefaultSettings(UIConfigFile), json.loads(jsondata, encoding="utf-8"))
		self.SaveSettings(SettingsFile)

	def SaveSettings(self, settingsfile=None):
		defaults = self.DefaultSettings(UIConfigFile)
		self.__dict__ = self.MergeSettings(defaults, self.__dict__)
		try:
			with codecs.open(settingsfile, encoding="utf-8-sig", mode="w") as f:
				json.dump(self.__dict__, f, encoding="utf-8", indent=2)
			with codecs.open(settingsfile.replace("json", "js"), encoding="utf-8-sig", mode="w") as f:
				f.writelines("var settings = {0};".format(json.dumps(self.__dict__, encoding="utf-8", indent=2)))
		except:
			Parent.Log(ScriptName, "SaveSettings(): Could not write settings to file")

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
	API = None
	try:
		with codecs.open(apifile, encoding="utf-8-sig", mode="r") as f:
			lines = f.readlines()
		API = re.search(r"\"\s?(?P<Key>[0-9a-f]+)\".*\"\s?(?P<Socket>ws://[0-9.:a-z]+/\w+)\"", "".join(lines)).groupdict()
		Logger.debug("Got Key ({0}) and Socket ({1}) from API_Key.js".format(API["Key"], API["Socket"]))
	except Exception as e:
		Logger.error(e)
	return API

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
	if all (keys in LocalAPI for keys in ("Key", "Socket")):
		LocalSocket = WebSocket(LocalAPI["Socket"])
		LocalSocket.OnOpen += LocalSocketConnected
		LocalSocket.OnClose += LocalSocketDisconnected
		LocalSocket.OnMessage += LocalSocketEvent
		LocalSocket.OnError += LocalSocketError

#---------------------------------------
#   Chatbot Script Unload Function
#---------------------------------------
def Unload():
	global LocalSocket
	if LocalSocket:
		LocalSocket.Close(1000, "Program exit")
		LocalSocket = None
		Logger.debug("LocalSocket Disconnected")
	global Logger
	if Logger:
		for handler in Logger.handlers[:]:
			Logger.removeHandler(handler)
		Logger = None

#---------------------------------------
#   Chatbot Save Settings Function
#---------------------------------------
def ReloadSettings(jsondata):
	global Logger
	ScriptSettings.Reload(jsondata)
	Parent.BroadcastWsEvent('{0}_UPDATE_SETTINGS'.format(ScriptName.upper()), json.dumps(ScriptSettings.__dict__))
	if Logger:
		Logger.debug("Settings reloaded")
		ScriptToggled(False)
		ScriptToggled(True)

#---------------------------------------
#   Chatbot Toggle Function
#---------------------------------------
def ScriptToggled(state):
	global Logger
	if state:
		if not Logger:
			Init()
		LocalSocket.Connect()
		Parent.AddCooldown(ScriptName, "LocalSocket", 10)
		Logger.debug("Script toggled on")
	else:
		Logger.debug("Script toggled off")
		Unload()

#---------------------------------------
#   Chatbot Execute Function
#---------------------------------------
def Execute(data):
	pass

#---------------------------------------
#   Chatbot Tick Function
#---------------------------------------
def Tick():
	global Logger
	if not Logger:
		return
	global LocalSocketIsConnected
	if not Parent.IsOnCooldown(ScriptName, "LocalSocket") and LocalSocket and not LocalSocketIsConnected and all (keys in LocalAPI for keys in ("Key", "Socket")):
		Logger.warning("No EVENT_CONNECTED received from LocalSocket, reconnecting")
		try:
			LocalSocket.Close(1006, "No connection confirmation received")
		except:
			Logger.error("Could not close LocalSocket gracefully")
		LocalSocket.Connect()
		Parent.AddCooldown(ScriptName, "LocalSocket", 10)
	if not Parent.IsOnCooldown(ScriptName, "LocalSocket") and LocalSocket and not LocalSocket.IsAlive:
		Logger.warning("LocalSocket seems dead, reconnecting")
		try:
			LocalSocket.Close(1006, "No connection")
		except:
			Logger.error("Could not close LocalSocket gracefully")
		LocalSocket.Connect()
		Parent.AddCooldown(ScriptName, "LocalSocket", 10)

#---------------------------------------
#   LocalSocket Connect Function
#---------------------------------------
def LocalSocketConnected(ws, data):
	global Logger
	global LocalAPI
	Auth = {
		"author": Creator,
		"website": Website,
		"api_key": LocalAPI["Key"],
		"events": [x.strip() for x in ScriptSettings.Events.split(',') ]
	}
	ws.Send(json.dumps(Auth))
	Logger.debug("Auth: {0}".format(json.dumps(Auth)))

#---------------------------------------
#   LocalSocket Disconnect Function
#---------------------------------------
def LocalSocketDisconnected(ws, data):
	global Logger
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
	global Logger
	Logger.error(data.Message)
	if data.Exception:
		Logger.debug(data.Exception, exc_info=True)

#---------------------------------------
#   LocalSocket Event Function
#---------------------------------------
def LocalSocketEvent(ws, data):
	global Logger
	if data.IsText:
		event = json.loads(data.Data)
		if "data" in event and isinstance(event["data"], str):
			event["data"] = json.loads(event["data"])
		Logger.info(json.dumps(event))
		if event["event"] == "EVENT_CONNECTED":
			global LocalSocketIsConnected
			LocalSocketIsConnected = True
			Logger.info(event["data"]["message"])
		else:
			Logger.warning("Unhandled event: {0}: {1}".format(event["event"], event["data"]))
