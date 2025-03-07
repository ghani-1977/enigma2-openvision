from fcntl import ioctl
from os import O_NONBLOCK, O_RDWR, close as osclose, listdir, open as osopen, write as oswrite
from os.path import isdir, isfile
from platform import machine
from struct import pack

from enigma import eRCInput

from keyids import KEYIDS, KEYIDNAMES
from Components.config import ConfigInteger, ConfigSelection, ConfigSelectionNumber, ConfigSlider, ConfigSubsection, ConfigText, ConfigYesNo, NoSave, config, configfile
from Components.Console import Console
from Components.Language import language
from Components.SystemInfo import BoxInfo
from Tools.Directories import SCOPE_KEYMAPS, SCOPE_SKIN, fileReadLine, fileWriteLine, fileReadLines, fileReadXML, resolveFilename

MODULE_NAME = __name__.split(".")[-1]

# BLACKLIST = ("dreambox front panel", "cec_input")  # Why was this being done?

REMOTE_MODEL = 0
REMOTE_RCTYPE = 1
REMOTE_NAME = 2
REMOTE_DISPLAY_NAME = 3

config.inputDevices = ConfigSubsection()


class InputDevices:
	def __init__(self):
		self.devices = {}
		self.currentDevice = None
		for device in sorted(listdir("/dev/input/")):
			if isdir("/dev/input/%s" % device):
				continue
			try:
				buffer = b"\0" * 512
				self.fd = osopen("/dev/input/%s" % device, O_RDWR | O_NONBLOCK)
				self.name = ioctl(self.fd, self.EVIOCGNAME(256), buffer)
				osclose(self.fd)
				self.name = str(self.name[:self.name.find(b"\0")])
			except (IOError, OSError) as err:
				print("[InputDevice] Error: device='%s' getInputDevices <ERROR: ioctl(EVIOCGNAME): '%s'>" % (device, str(err)))
				self.name = None
			if self.name:
				devType = self.getInputDeviceType(self.name.lower())
				print("[InputDevice] Found device '%s' with name '%s' of type '%s'." % (device, self.name, "Unknown" if devType is None else devType.capitalize()))
				# What was this for?
				# if self.name == "aml_keypad":
				# 	print("[InputDevice] ALERT: Old code flag for 'aml_keypad'.")
				# 	self.name = "dreambox advanced remote control (native)"
				# if self.name in BLACKLIST:
				# 	print("[InputDevice] ALERT: Old code flag for device in blacklist.")
				# 	continue
				self.devices[device] = {
					"name": self.name,
					"type": devType,
					"enabled": False,
					"configuredName": None
				}
				# What was this for?
				# if model.startswith("et"):
				# 	print("[InputDevice] ALERT: Old code flag for device starting with 'et'.")
				# 	self.setDeviceDefaults(device)

	def EVIOCGNAME(self, length):
		# From include/uapi/asm-generic/ioctl.h and asm-generic/ioctl.h for HAVE_OLDE2_API
		IOC_NRBITS = 8L
		IOC_TYPEBITS = 8L
		if BoxInfo.getItem("OLDE2API"):
			IOC_SIZEBITS = 13L
		else:
			IOC_SIZEBITS = 13L if "mips" in machine() else 14L
		IOC_NRSHIFT = 0L
		IOC_TYPESHIFT = IOC_NRSHIFT + IOC_NRBITS
		IOC_SIZESHIFT = IOC_TYPESHIFT + IOC_TYPEBITS
		IOC_DIRSHIFT = IOC_SIZESHIFT + IOC_SIZEBITS
		IOC_READ = 2L
		return (IOC_READ << IOC_DIRSHIFT) | (length << IOC_SIZESHIFT) | (0x45 << IOC_TYPESHIFT) | (0x06 << IOC_NRSHIFT)

	def getInputDeviceType(self, name):
		if "remote control" in name:
			return "remote"
		elif "keyboard" in name:
			return "keyboard"
		elif "mouse" in name:
			return "mouse"
		elif "front panel" in name:
			return "panel"
		else:
			# print("[InputDevice] Warning: Unknown device type: '%s'!" % name)
			return None

	def getDeviceList(self):
		return sorted(list(self.devices.keys()))

	# struct input_event {
	# 	struct timeval time;    -> ignored
	# 	__u16 type;             -> EV_REP (0x14)
	# 	__u16 code;             -> REP_DELAY (0x00) or REP_PERIOD (0x01)
	# 	__s32 value;            -> DEFAULTS: 700(REP_DELAY) or 100(REP_PERIOD)
	# }; -> size = 16
	#
	def setDeviceDefaults(self, device):
		# print("[InputDevice] setDeviceDefaults DEBUG: Device '%s'." % device)
		self.setDeviceAttribute(device, "configuredName", None)
		eventRepeat = pack("LLHHi", 0, 0, 0x14, 0x01, 100)
		eventDelay = pack("LLHHi", 0, 0, 0x14, 0x00, 700)
		fd = osopen("/dev/input/%s" % device, O_RDWR)
		oswrite(fd, eventRepeat)
		oswrite(fd, eventDelay)
		osclose(fd)

	def setDeviceEnabled(self, device, value):
		oldVal = self.getDeviceAttribute(device, "enabled")
		# print("[InputDevice] setDeviceEnabled DEBUG: Set device '%s' to '%s' from '%s'." % (device, value, oldVal))
		self.setDeviceAttribute(device, "enabled", value)
		if oldVal is True and value is False:
			self.setDeviceDefaults(device)

	def getDeviceName(self, device):
		if device in list(self.devices.keys()):
			return self.devices[device].get("name", device)
		return "Unknown device name"

	def setDeviceName(self, device, value):
		# print("[InputDevice] setDeviceName DEBUG: Set device name from '%s' to '%s'." % (device, value))
		self.setDeviceAttribute(device, "configuredName", value)

	def setDeviceDelay(self, device, value):  # REP_DELAY
		if self.getDeviceAttribute(device, "enabled"):
			# print("[InputDevice] setDeviceDelay DEBUG: Set device '%s' to %s ms." % (device, value))
			event = pack("LLHHi", 0, 0, 0x14, 0x00, int(value))
			fd = osopen("/dev/input/%s" % device, O_RDWR)
			oswrite(fd, event)
			osclose(fd)

	def setDeviceRepeat(self, device, value):  # REP_PERIOD
		if self.getDeviceAttribute(device, "enabled"):
			# print("[InputDevice] setDeviceRepeat DEBUG: Set device '%s' to %s ms." % (device, value))
			event = pack("LLHHi", 0, 0, 0x14, 0x01, int(value))
			fd = osopen("/dev/input/%s" % device, O_RDWR)
			oswrite(fd, event)
			osclose(fd)

	def getDeviceAttribute(self, device, attribute):
		if device in self.devices and attribute in self.devices[device]:
			return self.devices[device][attribute]
		return None

	def setDeviceAttribute(self, device, attribute, value):
		# print("[InputDevice] setDeviceAttribute DEBUG: Set attribute '%s' for device '%s' to value '%s'." % (attribute, device, value))
		if device in self.devices:
			self.devices[device][attribute] = value


class Keyboard:
	def __init__(self):
		self.keyboardMaps = []
		for keyboardMapInfo in sorted(listdir(resolveFilename(SCOPE_KEYMAPS))):
			if keyboardMapInfo.endswith(".info"):
				lines = []
				lines = fileReadLines(resolveFilename(SCOPE_KEYMAPS, keyboardMapInfo), lines, source=MODULE_NAME)
				keyboardMapFile = None
				keyboardMapName = None
				for line in lines:
					key, val = [x.strip() for x in line.split("=", 1)]
					if key == "kmap":
						keyboardMapFile = val
					elif key == "name":
						keyboardMapName = val
				if keyboardMapFile and keyboardMapName:
					keyboardMapPath = resolveFilename(SCOPE_KEYMAPS, keyboardMapFile)
					if isfile(keyboardMapPath):
						print("[InputDevice] Adding keyboard keymap '%s' in '%s'." % (keyboardMapName, keyboardMapFile))
						self.keyboardMaps.append((keyboardMapFile, keyboardMapName))
					else:
						print("[InputDevice] Error: Keyboard keymap file '%s' doesn't exist!" % keyboardMapPath)
				else:
					print("[InputDevice] Error: Invalid keyboard keymap information file '%s'!" % keyboardMapInfo)
		config.inputDevices.keyboardMap = ConfigSelection(choices=self.keyboardMaps, default=self.getDefaultKeyboardMap())

	def getDefaultKeyboardMap(self):
		# locale = international.getLocale()
		locale = "en_US"  # language.getLanguage()
		if locale:
			for keyboardMap in self.keyboardMaps:  # See if there is a keyboard keymap specific to the current locale.
				if keyboardMap[0].startswith(locale):
					return keyboardMap[0]
		# language = international.getLanguage()
		language = locale.split("_")[0]
		if language:
			for keyboardMap in self.keyboardMaps:  # See if there is a keyboard keymap specific to the current language.
				if keyboardMap[0].startswith(language):
					return keyboardMap[0]
		return "default.kmap"


class RemoteControl:
	knownCompatibleRemotes = [
		("gb0", "gb1", "gb2", "gb3", "gb4"),
		("ini0", "ini1", "ini2", "ini3", "ini4", "ini5", "ini6", "ini7", "ini8"),
		("wetek", "wetek2", "wetek3"),
		("zgemma1", "zgemma2", "zgemma3", "zgemma4", "zgemma5", "zgemma6", "zgemma7", "evo6", "evo7")
	]

	def __init__(self):
		self.model = BoxInfo.getItem("model")
		self.rcName = BoxInfo.getItem("rcname")
		self.rcType = self.readRemoteControlType()
		print("[InputDevice] RemoteControl DEBUG: model='%s', rcName='%s', rcType='%s'." % (self.model, self.rcName, self.rcType))
		remotes = fileReadXML(resolveFilename(SCOPE_SKIN, "remotes.xml"), source=MODULE_NAME)
		self.remotes = []
		if remotes:
			for remote in sorted(remotes.findall("remote"), key=lambda remote: (remote.tag, remote.get("displayName"))):
				model = remote.attrib.get("model")
				rcType = remote.attrib.get("rcType")
				codeName = remote.attrib.get("codeName")
				displayName = remote.attrib.get("displayName")
				if codeName and displayName:
					print("[InputDevice] Adding remote control for '%s'." % displayName)
					self.remotes.append((model, rcType, codeName, displayName))
		self.remotes.insert(0, ("", "", "", _("Default")))
		if BoxInfo.getItem("RemoteTypeZeroAllowed", False):
			self.remotes.insert(1, ("", "0", "", _("All supported")))
		rcChoices = []
		default = "0"
		for index, remote in enumerate(self.remotes):
			index = str(index)
			rcChoices.append((index, remote[REMOTE_DISPLAY_NAME]))
			if self.model == remote[REMOTE_MODEL] and self.rcType == remote[REMOTE_RCTYPE] and self.rcName in [x.strip() for x in remote[REMOTE_NAME].split(",")]:
				default = index
		config.inputDevices.remotesIndex = ConfigSelection(choices=rcChoices, default=default)
		self.remote = self.loadRemoteControl(BoxInfo.getItem("RCMapping"))

	def loadRemoteControl(self, filename):
		print("[InputDevice] Loading remote control '%s'." % filename)
		rcs = fileReadXML(filename, source=MODULE_NAME)
		if rcs:
			rc = rcs.find("rc")
			if rc:
				rcButtons = {}
				logRemaps = []
				remapButtons = {}
				placeHolder = 0
				rcButtons["keyIds"] = []
				rcButtons["image"] = rc.attrib.get("image")
				print("[InputDevice] loadRemoteControl DEBUG: image='%s'." % rcButtons["image"])
				for button in rc.findall("button"):
					id = button.attrib.get("id", "KEY_RESERVED")
					remap = button.attrib.get("remap")
					keyId = KEYIDS.get(id)
					remapId = KEYIDS.get(remap)
					if keyId is not None and remapId is not None:
						logRemaps.append((id, remap))
						remapButtons[keyId] = remapId
						keyId = remapId
					if keyId == 0:
						placeHolder -= 1
						keyId = placeHolder
					rcButtons["keyIds"].append(keyId)
					rcButtons[keyId] = {}
					rcButtons[keyId]["id"] = id
					rcButtons[keyId]["label"] = button.attrib.get("label")
					rcButtons[keyId]["pos"] = [int(x.strip()) for x in button.attrib.get("pos", "0").split(",")]
					rcButtons[keyId]["title"] = button.attrib.get("title")
					rcButtons[keyId]["shape"] = button.attrib.get("shape")
					rcButtons[keyId]["coords"] = [int(x.strip()) for x in button.attrib.get("coords", "0").split(",")]
					print("[InputDevice] loadRemoteControl DEBUG: id='%s', keyId='%s', label='%s', pos='%s', title='%s', shape='%s', coords='%s'." % (id, keyId, rcButtons[keyId]["label"], rcButtons[keyId]["pos"], rcButtons[keyId]["title"], rcButtons[keyId]["shape"], rcButtons[keyId]["coords"]))
				if logRemaps:
					for remap in logRemaps:
						print("[InputDevice] Remapping '%s' to '%s'." % (remap[0], remap[1]))
					for evdev, evdevinfo in sorted(inputDevices.devices.items()):
						if evdevinfo["type"] == "remote":
							result = eRCInput.getInstance().setKeyMapping(evdevinfo["name"], remapButtons)
							resStr = {
								eRCInput.remapOk: "Remap completed okay.",
								eRCInput.remapUnsupported: "Error: Remapping not supported on device!",
								eRCInput.remapFormatErr: "Error: Remap map in incorrect format!",
								eRCInput.remapNoSuchDevice: "Error: Unknown device!",
							}.get(result, "Error: Unknown error!")
							print("[InputDevice] Remote remap evdev='%s', name='%s': %s" % (evdev, evdevinfo["name"], resStr))
		return rcButtons

	def getRemoteControlKeyList(self):
		return self.remote["keyIds"]

	def getRemoteControlKeyLabel(self, keyId):
		if keyId in self.remote:
			return self.remote[keyId]["label"]
		print("[InputDevice] Button '%s' (%d) is not available on the current remote control." % (KEYIDNAMES.get(keyId), keyId))
		return None

	def getRemoteControlKeyPos(self, keyId):
		if keyId in self.remote:
			return self.remote[keyId]["pos"]
		print("[InputDevice] Button '%s' (%d) is not available on the current remote control." % (KEYIDNAMES.get(keyId), keyId))
		return None

	def readRemoteControlType(self):
		return fileReadLine("/proc/stb/ir/rc/type", "-1", source=MODULE_NAME)

	def writeRemoteControlType(self, rcType):
		if rcType > 0:
			fileWriteLine("/proc/stb/ir/rc/type", rcType, source=MODULE_NAME)

	def getOpenWebifHTML(self):
		html = []
		error = False
		image = self.remote["image"]
		if image:
			html.append("<img border=\"0\" src=\"%s\" usemap=\"#map\" />" % image)
			html.append("<map name=\"map\">")
			for keyId in self.remote["keyIds"]:
				attribs = []
				title = self.remote[keyId]["title"]
				if title:
					attribs.append("title=\"%s\"" % title)
				else:
					error = True
				shape = self.remote[keyId]["shape"]
				if shape:
					attribs.append("shape=\"%s\"" % shape)
				else:
					error = True
				coords = ",".join([str(x) for x in self.remote[keyId]["coords"]])
				if coords:
					attribs.append("coords=\"%s\"" % coords)
				else:
					error = True
				if keyId > 0:
					attribs.append("onclick=\"pressMenuRemote('%d');\"" % keyId)
				html.append("\t<area %s />" % " ".join(attribs))
			html.append("</map>")
		else:
			error = True
		return None if error else "\n".join(html)


class InitInputDevices:
	def __init__(self):
		self.currentDevice = None
		for device in sorted(list(inputDevices.devices.keys())):
			print("[InputDevice] InitInputDevices DEBUG: Creating config entry for device: '%s' -> '%s'." % (device, inputDevices.devices[device]["name"]))
			self.currentDevice = device
			self.setupConfigEntries(self.currentDevice)
			self.currentDevice = None

	def setupConfigEntries(self, device):
		setattr(config.inputDevices, device, ConfigSubsection())
		configItem = getattr(config.inputDevices, device)
		configItem.enabled = ConfigYesNo(default=BoxInfo.getItem("RemoteEnable", False))
		configItem.enabled.addNotifier(self.inputDevicesEnabledChanged)
		configItem.name = ConfigText(default=inputDevices.devices[device]["name"])
		configItem.name.addNotifier(self.inputDevicesNameChanged)
		configItem.repeat = ConfigSelectionNumber(default=BoxInfo.getItem("RemoteRepeat", 100), min=0, max=500, stepwidth=10)
		configItem.repeat.addNotifier(self.inputDevicesRepeatChanged)
		configItem.delay = ConfigSelectionNumber(default=BoxInfo.getItem("RemoteDelay", 700), min=0, max=5000, stepwidth=100)
		configItem.delay.addNotifier(self.inputDevicesDelayChanged)

	def inputDevicesEnabledChanged(self, configElement):
		if self.currentDevice and inputDevices.currentDevice is None:
			inputDevices.setDeviceEnabled(self.currentDevice, configElement.value)
		elif inputDevices.currentDevice:
			inputDevices.setDeviceEnabled(inputDevices.currentDevice, configElement.value)

	def inputDevicesNameChanged(self, configElement):
		if self.currentDevice and inputDevices.currentDevice is None:
			inputDevices.setDeviceName(self.currentDevice, configElement.value)
			if configElement.value:
				devName = inputDevices.getDeviceAttribute(self.currentDevice, "name")
				if devName != configElement.value:
					configItem = getattr(config.inputDevices, "%s.enabled" % self.currentDevice)
					configItem.value = False
					configItem.save()
		elif inputDevices.currentDevice:
			inputDevices.setDeviceName(inputDevices.currentDevice, configElement.value)

	def inputDevicesDelayChanged(self, configElement):
		if self.currentDevice and inputDevices.currentDevice is None:
			inputDevices.setDeviceDelay(self.currentDevice, configElement.value)
		elif inputDevices.currentDevice:
			inputDevices.setDeviceDelay(inputDevices.currentDevice, configElement.value)

	def inputDevicesRepeatChanged(self, configElement):
		if self.currentDevice and inputDevices.currentDevice is None:
			inputDevices.setDeviceRepeat(self.currentDevice, configElement.value)
		elif inputDevices.currentDevice:
			inputDevices.setDeviceRepeat(inputDevices.currentDevice, configElement.value)


inputDevices = InputDevices()
keyboard = Keyboard()
remoteControl = RemoteControl()
