#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Screens.HelpMenu import HelpableScreen
from Components.Network import iNetwork
from Components.Sources.StaticText import StaticText
from Components.Sources.Boolean import Boolean
from Components.Sources.List import List
from Components.Label import Label, MultiColorLabel
from Components.Pixmap import Pixmap, MultiPixmap
from Components.MenuList import MenuList
from Components.config import config, ConfigYesNo, ConfigIP, NoSave, ConfigText, ConfigPassword, ConfigSelection, getConfigListEntry, ConfigMacText, ConfigSubsection, ConfigNumber, ConfigLocations
from Components.ConfigList import ConfigListScreen
from Components.PluginComponent import plugins
from Components.ActionMap import ActionMap, NumberActionMap, HelpableActionMap
from Tools.Directories import resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN, fileExists
from Tools.LoadPixmap import LoadPixmap
from Plugins.Plugin import PluginDescriptor
from enigma import eTimer, eConsoleAppContainer
try:
	import commands
except:
	import subprocess as commands
from Components.Console import Console
from Screens.Standby import TryQuitMainloop
from random import Random
import time
from Components.FileList import MultiFileSelectList
from Screens.VirtualKeyBoard import VirtualKeyBoard
import string
import glob
import fnmatch
from Components.ScrollLabel import ScrollLabel
from os import remove, unlink, rename
from six import PY2
from Components.SystemInfo import BoxInfo

model = BoxInfo.getItem("model")

# Define a function to determine whether a service is configured to start at boot time.
# This checks for a start file in rc2.d (rc4.d might be more appropriate, but historically it's been rc2.d, so...).


def ServiceIsEnabled(service_name):
	starter_list = glob.glob("/etc/rc2.d/S*" + service_name)
	return len(starter_list) > 0

# Lets have some global functions to reduce python code


class NSCommon:
	def StartStopCallback(self, result=None, retval=None, extra_args=None):
		time.sleep(3)
		self.updateService()

	def removeComplete(self, result=None, retval=None, extra_args=None):
		if self.reboot_at_end:
			self.session.open(TryQuitMainloop, 2)
		self.message.close()
		self.close()

	def installComplete(self, result=None, retval=None, extra_args=None):
		self.feedscheck.close()
		if self.reboot_at_end:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.updateService()
		self.message.close()
		self.close()

	def doRemove(self, callback, pkgname):
		self.message = self.session.open(MessageBox, _("Please wait..."), MessageBox.TYPE_INFO, enable_input=False)
		self.message.setTitle(_('Removing service'))
		self.Console.ePopen('opkg remove ' + pkgname + ' --force-remove --autoremove', callback)

	def doInstall(self, callback, pkgname):
		self.message = self.session.open(MessageBox, _("Please wait..."), MessageBox.TYPE_INFO, enable_input=False)
		self.message.setTitle(_('Installing service'))
		self.Console.ePopen('opkg install ' + pkgname + ' >/dev/null 2>&1', callback)

	def checkNetworkState(self, str, retval, extra_args):
		if 'Collected errors' in str:
			self.session.openWithCallback(self.close, MessageBox, _("Seems a background update check is in progress, please wait a few minutes and then try again."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
		elif not str:
			self.feedscheck = self.session.open(MessageBox, _('Please wait while feeds state is being checked.'), MessageBox.TYPE_INFO, enable_input=False)
			self.feedscheck.setTitle(_('Checking feeds'))
			cmd1 = "opkg update"
			self.CheckConsole = Console()
			self.CheckConsole.ePopen(cmd1, self.checkNetworkStateFinished)
		else:
			self.updateService()

	def checkNetworkStateFinished(self, result, retval, extra_args=None):
		if 'bad address' in result:
			self.session.openWithCallback(self.InstallPackageFailed, MessageBox, _("Your receiver is not connected to the internet, please check your network settings and try again."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)
		if self.reboot_at_end:
			mtext = _('Your receiver will be restarted after the installation of the service\nAre you ready to install "%s" ?') % self.service_name
		else:
			mtext = _('Are you ready to install "%s" ?') % self.service_name
		self.session.openWithCallback(self.InstallPackage, MessageBox, mtext, MessageBox.TYPE_YESNO)
		if ('wget returned 1' or 'wget returned 255' or '404 Not Found') in result:
			self.session.openWithCallback(self.InstallPackageFailed, MessageBox, _("Please wait while feeds state is being checked."), type=MessageBox.TYPE_INFO, timeout=10, close_on_any_key=True)

	def UninstallCheck(self):
		self.Console.ePopen('opkg list_installed ' + self.service_name, self.RemovedataAvail)

	def RemovedataAvail(self, str, retval, extra_args):
		if str:
			if self.reboot_at_end:
				restartbox = self.session.openWithCallback(self.RemovePackage, MessageBox, _('Your receiver will be restarted after the removal of the service\nDo you want to remove the service now ?'), MessageBox.TYPE_YESNO)
				restartbox.setTitle(_('Are you ready to remove "%s" ?') % self.service_name)
			else:
				self.session.openWithCallback(self.RemovePackage, MessageBox, _('Ready to remove "%s" ?') % self.service_name, MessageBox.TYPE_YESNO)
		else:
			self.updateService()

	def RemovePackage(self, val):
		if val:
			self.doRemove(self.removeComplete, self.service_name)

	def InstallPackage(self, val):
		if val:
			self.doInstall(self.installComplete, self.service_name)
		else:
			self.feedscheck.close()
			self.close()

	def InstallPackageFailed(self, val):
		self.feedscheck.close()
		self.close()

	def InstallCheck(self):
		self.Console.ePopen('opkg list_installed ' + self.service_name, self.checkNetworkState)
# Now global functions will help us to reduce code


class NetworkAdapterSelection(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setTitle(_("Select a network adapter"))
		self.wlan_errortext = _("No working wireless network adapter found.\nPlease verify that you have attached a compatible WLAN device and your network is configured correctly.")
		self.lan_errortext = _("No working local network adapter found.\nPlease verify that you have attached a network cable and your network is configured correctly.")
		self.oktext = _("Press OK on your remote control to continue.")
		self.edittext = _("Press OK to edit the settings.")
		self.defaulttext = _("Press yellow to set this interface as default interface.")
		self.restartLanRef = None

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Select"))
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")
		self["introduction"] = StaticText(self.edittext)

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.close, _("Exit network interface list")),
			"ok": (self.okbuttonClick, _("Select interface")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.close, _("Exit network interface list")),
			"green": (self.okbuttonClick, _("Select interface")),
			"blue": (self.openNetworkWizard, _("Use the network wizard to configure selected network adapter")),
			})

		self["DefaultInterfaceAction"] = HelpableActionMap(self, ["ColorActions"],
			{
			"yellow": (self.setDefaultInterface, [_("Set interface as default Interface"), _("* Only available if more than one interface is active.")]),
			})

		self.adapters = [(iNetwork.getFriendlyAdapterName(x), x) for x in iNetwork.getAdapterList()]

		if not self.adapters:
			self.adapters = [(iNetwork.getFriendlyAdapterName(x), x) for x in iNetwork.getConfiguredAdapters()]

		if len(self.adapters) == 0:
			self.adapters = [(iNetwork.getFriendlyAdapterName(x), x) for x in iNetwork.getInstalledAdapters()]

		self.list = []
		self["list"] = List(self.list)
		self.updateList()

		if len(self.adapters) == 1:
			self.onFirstExecBegin.append(self.okbuttonClick)
		self.onClose.append(self.cleanup)

	def buildInterfaceList(self, iface, name, default, active):
		divpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "div-h.png"))
		defaultpng = None
		activepng = None
		description = None
		interfacepng = None

		if not iNetwork.isWirelessInterface(iface):
			if active is True:
				interfacepng = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/network_wired-active.png"))
			elif active is False:
				interfacepng = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/network_wired-inactive.png"))
			else:
				interfacepng = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/network_wired.png"))
		elif iNetwork.isWirelessInterface(iface):
			if active is True:
				interfacepng = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/network_wireless-active.png"))
			elif active is False:
				interfacepng = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/network_wireless-inactive.png"))
			else:
				interfacepng = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/network_wireless.png"))

		num_configured_if = len(iNetwork.getConfiguredAdapters())
		if num_configured_if >= 2:
			if active is True:
				defaultpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "buttons/button_green.png"))
			elif active is False:
				defaultpng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "buttons/button_green_off.png"))
		if active is True:
			activepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/lock_on.png"))
		elif active is False:
			activepng = LoadPixmap(cached=True, path=resolveFilename(SCOPE_CURRENT_SKIN, "icons/lock_error.png"))

		description = iNetwork.getFriendlyAdapterDescription(iface)

		return((iface, name, description, interfacepng, defaultpng, activepng, divpng))

	def updateList(self):
		self.list = []
		default_gw = None
		iNetwork.getInterfaces()
		num_configured_if = len(iNetwork.getConfiguredAdapters())
		if num_configured_if >= 2:
			self["key_yellow"].setText(_("Default"))
			self["introduction"].setText(self.defaulttext)
			self["DefaultInterfaceAction"].setEnabled(True)
		else:
			self["key_yellow"].setText("")
			self["introduction"].setText(self.edittext)
			self["DefaultInterfaceAction"].setEnabled(False)

		if num_configured_if < 2 and os.path.exists("/etc/default_gw"):
			os.unlink("/etc/default_gw")

		if os.path.exists("/etc/default_gw"):
			fp = open('/etc/default_gw', 'r')
			result = fp.read()
			fp.close()
			default_gw = result

		for x in self.adapters:
			if x[1] == default_gw:
				default_int = True
			else:
				default_int = False
			if iNetwork.getAdapterAttribute(x[1], 'up') is True:
				active_int = True
			else:
				active_int = False
			self.list.append(self.buildInterfaceList(x[1], _(x[0]), default_int, active_int))

		if os.path.exists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/NetworkWizard/networkwizard.xml")):
			self["key_blue"].setText(_("Network wizard"))
		self["list"].setList(self.list)

	def setDefaultInterface(self):
		selection = self["list"].getCurrent()
		num_if = len(self.list)
		old_default_gw = None
		num_configured_if = len(iNetwork.getConfiguredAdapters())
		if os.path.exists("/etc/default_gw"):
			fp = open('/etc/default_gw', 'r')
			old_default_gw = fp.read()
			fp.close()
		if num_configured_if > 1 and (not old_default_gw or old_default_gw != selection[0]):
			fp = open('/etc/default_gw', 'w+')
			fp.write(selection[0])
			fp.close()
			self.restartLan()
		elif old_default_gw and num_configured_if < 2:
			os.unlink("/etc/default_gw")
			self.restartLan()

	def okbuttonClick(self):
		selection = self["list"].getCurrent()
		if selection is not None:
			self.session.openWithCallback(self.AdapterSetupClosed, AdapterSetupConfiguration, selection[0])

	def AdapterSetupClosed(self, *ret):
		if len(self.adapters) == 1:
			self.close()
		else:
			self.updateList()

	def cleanup(self):
		iNetwork.stopLinkStateConsole()
		iNetwork.stopRestartConsole()
		iNetwork.stopGetInterfacesConsole()

	def restartLan(self):
		iNetwork.restartNetwork(self.restartLanDataAvail)
		self.restartLanRef = self.session.openWithCallback(self.restartfinishedCB, MessageBox, _("Please wait while we configure your network..."), type=MessageBox.TYPE_INFO, enable_input=False)

	def restartLanDataAvail(self, data):
		if data is True:
			iNetwork.getInterfaces(self.getInterfacesDataAvail)

	def getInterfacesDataAvail(self, data):
		if data is True:
			self.restartLanRef.close(True)

	def restartfinishedCB(self, data):
		if data is True:
			self.updateList()
			self.session.open(MessageBox, _("Finished configuring your network"), type=MessageBox.TYPE_INFO, timeout=10, default=False)

	def openNetworkWizard(self):
		if os.path.exists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/NetworkWizard/networkwizard.xml")):
			try:
				from Plugins.SystemPlugins.NetworkWizard.NetworkWizard import NetworkWizard
			except ImportError as e:
				self.session.open(MessageBox, _("The network wizard extension is not installed!\nPlease install it."), type=MessageBox.TYPE_INFO, timeout=10)
			else:
				selection = self["list"].getCurrent()
				if selection is not None:
					self.session.openWithCallback(self.AdapterSetupClosed, NetworkWizard, selection[0])


class NameserverSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setTitle(_("Configure nameservers"))
		self.backupNameserverList = iNetwork.getNameserverList()[:]
		print("[NetworkSetup] backup-list:", self.backupNameserverList)

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Add"))
		self["key_yellow"] = StaticText(_("Delete"))

		self["introduction"] = StaticText(_("Press OK to activate the settings."))
		self.createConfig()

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.cancel, _("Exit nameserver configuration")),
			"ok": (self.ok, _("Activate current configuration")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.cancel, _("Exit nameserver configuration")),
			"green": (self.add, _("Add a nameserver entry")),
			"yellow": (self.remove, _("Remove a nameserver entry")),
			})

		self["actions"] = NumberActionMap(["SetupActions"],
		{
			"ok": self.ok,
		}, -2)

		self.list = []
		ConfigListScreen.__init__(self, self.list)
		self.createSetup()

	def createConfig(self):
		self.nameservers = iNetwork.getNameserverList()
		if config.usage.dns.value == 'google':
			self.nameserverEntries = [NoSave(ConfigIP(default=[8, 8, 8, 8])), NoSave(ConfigIP(default=[8, 8, 4, 4]))]
		elif config.usage.dns.value == 'cloudflare':
			self.nameserverEntries = [NoSave(ConfigIP(default=[1, 1, 1, 1])), NoSave(ConfigIP(default=[1, 0, 0, 1]))]
		elif config.usage.dns.value == 'opendns-familyshield':
			self.nameserverEntries = [NoSave(ConfigIP(default=[208, 67, 222, 123])), NoSave(ConfigIP(default=[208, 67, 220, 123]))]
		elif config.usage.dns.value == 'opendns-home':
			self.nameserverEntries = [NoSave(ConfigIP(default=[208, 67, 222, 222])), NoSave(ConfigIP(default=[208, 67, 220, 220]))]
		elif config.usage.dns.value == 'custom' or config.usage.dns.value == 'dhcp-router':
			self.nameserverEntries = [NoSave(ConfigIP(default=nameserver)) for nameserver in self.nameservers]

	def createSetup(self):
		self.list = []
		self.DNSEntry = getConfigListEntry(_("Nameserver configuration"), config.usage.dns)
		self.list.append(self.DNSEntry)

		i = 1
		for x in self.nameserverEntries:
			self.list.append(getConfigListEntry(_("Nameserver %d") % (i), x))
			i += 1

		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def ok(self):
		self.RefreshNameServerUsed()
		iNetwork.clearNameservers()
		for nameserver in self.nameserverEntries:
			iNetwork.addNameserver(nameserver.value)
		iNetwork.writeNameserverConfig()
		config.usage.dns.save()
		self.close()

	def run(self):
		self.ok()

	def cancel(self):
		self.close()

	def add(self):
		iNetwork.addNameserver([0, 0, 0, 0])
		self.createConfig()
		self.createSetup()

	def remove(self):
		print("[NetworkSetup] currentIndex:", self["config"].getCurrentIndex())
		index = self["config"].getCurrentIndex()
		if index < len(self.nameservers):
			iNetwork.removeNameserver(self.nameservers[index])
			self.createConfig()
			self.createSetup()

	def RefreshNameServerUsed(self):
		print("[NetworkSetup] currentIndex:", self["config"].getCurrentIndex())
		index = self["config"].getCurrentIndex()
		if index < len(self.nameservers):
			self.createConfig()
			self.createSetup()


class NetworkMacSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		Screen.setTitle(self, _("MAC address settings"))
		self.curMac = self.getmac('eth0')
		self.getConfigMac = NoSave(ConfigMacText(default=self.curMac))

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))

		self["introduction"] = StaticText(_("Press OK to set the MAC address."))

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.cancel, _("Exit nameserver configuration")),
			"ok": (self.ok, _("Activate current configuration")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.cancel, _("Exit MAC address configuration")),
			"green": (self.ok, _("Activate MAC address configuration")),
			})

		self["actions"] = NumberActionMap(["SetupActions"],
		{
			"ok": self.ok,
		}, -2)

		self.list = []
		ConfigListScreen.__init__(self, self.list)
		self.createSetup()

	def getmac(self, iface):
		mac = (0, 0, 0, 0, 0, 0)
		ifconfig = commands.getoutput("ifconfig " + iface + "| grep HWaddr | awk '{ print($5) }'").strip()
		if len(ifconfig) == 0:
			mac = "00:00:00:00:00:00"
		else:
			mac = ifconfig[:17]
		return mac

	def createSetup(self):
		self.list = []
		self.list.append(getConfigListEntry(_("MAC address"), self.getConfigMac))
		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def ok(self):
		MAC = self.getConfigMac.value
		open("/etc/enigma2/hwmac", "w").write(MAC)
		route = commands.getoutput("route -n |grep UG | awk '{print($2) }'")
		self.restartLan()

	def run(self):
		self.ok()

	def cancel(self):
		self.close()

	def restartLan(self, ret=False):
		if ret:
			iNetwork.restartNetwork(self.restartLanDataAvail)
			self.restartLanRef = self.session.openWithCallback(self.restartfinishedCB, MessageBox, _("Please wait while your network is restarting..."), type=MessageBox.TYPE_INFO, enable_input=False)

	def restartLanDataAvail(self, data):
		if data is True:
			iNetwork.getInterfaces(self.getInterfacesDataAvail)

	def getInterfacesDataAvail(self, data):
		if data is True:
			self.restartLanRef.close(True)

	def restartfinishedCB(self, data):
		if data is True:
			self.updateStatusbar()
			self.session.open(MessageBox, _("Finished restarting your network"), type=MessageBox.TYPE_INFO, timeout=10, default=False)


class IPv6Setup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		Screen.setTitle(self, _("IPv6 support"))

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_blue"] = StaticText(_("Restore inetd"))

		self["introduction"] = StaticText(_("Enable or disable IPv6"))

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.cancel, _("Exit IPv6 configuration")),
			"ok": (self.ok, _("Activate IPv6 configuration")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.cancel, _("Exit IPv6 configuration")),
			"green": (self.ok, _("Activate IPv6 configuration")),
			"blue": (self.restoreinetdData2, _("Restore inetd.conf")),
			})

		self["actions"] = NumberActionMap(["SetupActions"],
		{
			"ok": self.ok,
		}, -2)

		self.list = []
		ConfigListScreen.__init__(self, self.list)

		print("[NetworkSetup] Read /proc/sys/net/ipv6/conf/all/disable_ipv6")
		old_ipv6 = open("/proc/sys/net/ipv6/conf/all/disable_ipv6", "r").read()
		if int(old_ipv6) == 1:
			self.ipv6 = False
		else:
			self.ipv6 = True
		self.IPv6ConfigEntry = NoSave(ConfigYesNo(default=self.ipv6 or False))
		self.createSetup()

	def createSetup(self):
		self.list = []
		self.IPv6Entry = getConfigListEntry(_("IPv6 support"), self.IPv6ConfigEntry)
		self.list.append(self.IPv6Entry)
		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def restoreinetdData2(self):
		sockTypetcp = "tcp"
		sockTypeudp = "udp"
		if self.IPv6ConfigEntry.value == True:
			sockTypetcp = "tcp6"
			sockTypeudp = "udp6"

		inetdData = "# /etc/inetd.conf:  see inetd(8) for further informations.\n"
		inetdData += "#\n"
		inetdData += "# Internet server configuration database\n"
		inetdData += "#\n"
		inetdData += "# If you want to disable an entry so it isn't touched during\n"
		inetdData += "# package updates just comment it out with a single '#' character.\n"
		inetdData += "#\n"
		inetdData += "# <service_name> <sock_type> <proto> <flags> <user> <server_path> <args>\n"
		inetdData += "#\n"
		inetdData += "#:INTERNAL: Internal services\n"
		inetdData += "#echo	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#echo	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#chargen	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#chargen	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#discard	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#discard	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#daytime	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#daytime	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#time	stream	tcp	nowait	root	internal\n"
		inetdData += "#time	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "ftp	stream	" + sockTypetcp + "	nowait	root	/usr/sbin/vsftpd	vsftpd\n"
		inetdData += "#ftp	stream	" + sockTypetcp + "	nowait	root	ftpd	ftpd -w /\n"
		inetdData += "telnet	stream	" + sockTypetcp + "	nowait	root	/usr/sbin/telnetd	telnetd\n"
		if fileExists("/usr/sbin/smbd"):
			inetdData += "#microsoft-ds	stream	" + sockTypetcp + "	nowait	root	/usr/sbin/smbd	smbd\n"
		if fileExists("/usr/sbin/nmbd"):
			inetdData += "#netbios-ns	dgram	" + sockTypeudp + "	wait	root	/usr/sbin/nmbd	nmbd\n"
		if fileExists("/usr/bin/streamproxy"):
			inetdData += "8001	stream	" + sockTypetcp + "	nowait	root	/usr/bin/streamproxy	streamproxy\n"

		if fileExists("/usr/bin/transtreamproxy"):
			inetdData += "8002	stream	" + sockTypetcp + "	nowait	root	/usr/bin/transtreamproxy	transtreamproxy\n"

		open("/etc/inetd.conf", "w").write(inetdData)

		self.session.open(MessageBox, _("Successfully restored /etc/inetd.conf!"), type=MessageBox.TYPE_INFO, timeout=10)

	def ok(self):
		ipv6 = '/etc/enigma2/ipv6'
		print("[NetworkSetup] Write to /proc/sys/net/ipv6/conf/all/disable_ipv6")
		if self.IPv6ConfigEntry.value == False:
			open("/proc/sys/net/ipv6/conf/all/disable_ipv6", "w").write("1")
			print("[NetworkSetup] Write to /etc/enigma2/ipv6")
			open("/etc/enigma2/ipv6", "w").write("1")
		else:
			open("/proc/sys/net/ipv6/conf/all/disable_ipv6", "w").write("0")
			Console().ePopen('rm -R %s' % ipv6)
		self.restoreinetdData2()
		self.close()

	def run(self):
		self.ok()

	def cancel(self):
		self.close()


class InetdRecovery(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Inetd recovery"))

		self["key_red"] = Label(_("Cancel"))
		self["key_blue"] = Label(_("Recover"))

		self.list = []

		self.ipv6 = NoSave(ConfigYesNo(default=False))
		self.list.append(getConfigListEntry(_("IPv6"), self.ipv6))

		ConfigListScreen.__init__(self, self.list)

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"], {
			"cancel": (self.close, _("Exit inetd recovery"))
		})
		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"], {
			"red": (self.close, _("Exit inetd recovery")),
			"blue": (self.keyBlue, _("Recover inetd")),
		})

	def keyBlue(self):
		sockTypetcp = "tcp"
		sockTypeudp = "udp"
		if self.ipv6.value:
			sockTypetcp = "tcp6"
			sockTypeudp = "udp6"

		inetdData = "# /etc/inetd.conf:  see inetd(8) for further informations.\n"
		inetdData += "#\n"
		inetdData += "# Internet server configuration database\n"
		inetdData += "#\n"
		inetdData += "# If you want to disable an entry so it isn't touched during\n"
		inetdData += "# package updates just comment it out with a single '#' character.\n"
		inetdData += "#\n"
		inetdData += "# <service_name> <sock_type> <proto> <flags> <user> <server_path> <args>\n"
		inetdData += "#\n"
		inetdData += "#:INTERNAL: Internal services\n"
		inetdData += "#echo	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#echo	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#chargen	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#chargen	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#discard	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#discard	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#daytime	stream	" + sockTypetcp + "	nowait	root	internal\n"
		inetdData += "#daytime	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "#time	stream	tcp	nowait	root	internal\n"
		inetdData += "#time	dgram	" + sockTypeudp + "	wait	root	internal\n"
		inetdData += "ftp	stream	" + sockTypetcp + "	nowait	root	/usr/sbin/vsftpd	vsftpd\n"
		inetdData += "#ftp	stream	" + sockTypetcp + "	nowait	root	ftpd	ftpd -w /\n"
		inetdData += "telnet	stream	" + sockTypetcp + "	nowait	root	/usr/sbin/telnetd	telnetd\n"
		if fileExists("/usr/sbin/smbd"):
			inetdData += "#microsoft-ds	stream	" + sockTypetcp + "	nowait	root	/usr/sbin/smbd	smbd\n"
		if fileExists("/usr/sbin/nmbd"):
			inetdData += "#netbios-ns	dgram	" + sockTypeudp + "	wait	root	/usr/sbin/nmbd	nmbd\n"
		if fileExists("/usr/bin/streamproxy"):
			inetdData += "8001	stream	" + sockTypetcp + "	nowait	root	/usr/bin/streamproxy	streamproxy\n"

		if fileExists("/usr/bin/transtreamproxy"):
			inetdData += "8002	stream	" + sockTypetcp + "	nowait	root	/usr/bin/transtreamproxy	transtreamproxy\n"

		open("/etc/inetd.conf", "w").write(inetdData)

		self.inetdRestart()

		self.session.open(MessageBox, _("Successfully restored /etc/inetd.conf!"), type=MessageBox.TYPE_INFO, timeout=10)
		self.close()

	def inetdRestart(self):
		commands = []
		if fileExists("/etc/init.d/inetd.busybox"):
			commands.append('/etc/init.d/inetd.busybox restart')


class AdapterSetup(Screen, ConfigListScreen, HelpableScreen):
	def __init__(self, session, networkinfo, essid=None):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setTitle(_("Network Setup"))
		self.session = session
		if isinstance(networkinfo, (list, tuple)):
			self.iface = networkinfo[0]
			self.essid = networkinfo[1]
		else:
			self.iface = networkinfo
			self.essid = essid

		self.extended = None
		self.applyConfigRef = None
		self.finished_cb = None
		self.oktext = _("Press OK on your remote control to continue.")
		self.oldInterfaceState = iNetwork.getAdapterAttribute(self.iface, "up")

		self.createConfig()

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.keyCancel, _("exit network adapter configuration")),
			"ok": (self.keySave, _("activate network adapter configuration")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.keyCancel, _("exit network adapter configuration")),
			"green": (self.keySave, _("activate network adapter configuration")),
			"blue": (self.KeyBlue, _("open nameserver configuration")),
			})

		self["actions"] = NumberActionMap(["SetupActions"],
		{
			"ok": self.keySave,
		}, -2)

		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session)
		self.createSetup()
		self.onLayoutFinish.append(self.layoutFinished)
		self.onClose.append(self.cleanup)

		self["DNS1text"] = StaticText(_("Primary DNS"))
		self["DNS2text"] = StaticText(_("Secondary DNS"))
		self["DNS1"] = StaticText()
		self["DNS2"] = StaticText()
		self["introduction"] = StaticText(_("Current settings:"))

		self["IPtext"] = StaticText(_("IP address"))
		self["Netmasktext"] = StaticText(_("Netmask"))
		self["Gatewaytext"] = StaticText(_("Gateway"))

		self["IP"] = StaticText()
		self["Mask"] = StaticText()
		self["Gateway"] = StaticText()

		self["Adaptertext"] = StaticText(_("Network:"))
		self["Adapter"] = StaticText()
		self["introduction2"] = StaticText(_("Press OK to activate the settings."))
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_blue"] = StaticText(_("Edit DNS"))

		self["VKeyIcon"] = Boolean(False)
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

	def layoutFinished(self):
		self["DNS1"].setText(self.primaryDNS.getText())
		self["DNS2"].setText(self.secondaryDNS.getText())
		if self.ipConfigEntry.getText() is not None:
			if self.ipConfigEntry.getText() == "0.0.0.0":
				self["IP"].setText(_("N/A"))
			else:
				self["IP"].setText(self.ipConfigEntry.getText())
		else:
			self["IP"].setText(_("N/A"))
		if self.netmaskConfigEntry.getText() is not None:
			if self.netmaskConfigEntry.getText() == "0.0.0.0":
				self["Mask"].setText(_("N/A"))
			else:
				self["Mask"].setText(self.netmaskConfigEntry.getText())
		else:
			self["IP"].setText(_("N/A"))
		if iNetwork.getAdapterAttribute(self.iface, "gateway"):
			if self.gatewayConfigEntry.getText() == "0.0.0.0":
				self["Gatewaytext"].setText(_("Gateway"))
				self["Gateway"].setText(_("N/A"))
			else:
				self["Gatewaytext"].setText(_("Gateway"))
				self["Gateway"].setText(self.gatewayConfigEntry.getText())
		else:
			self["Gateway"].setText("")
			self["Gatewaytext"].setText("")
		self["Adapter"].setText(iNetwork.getFriendlyAdapterName(self.iface))

	def createConfig(self):
		self.InterfaceEntry = None
		self.dhcpEntry = None
		self.gatewayEntry = None
		self.hiddenSSID = None
		self.wlanSSID = None
		self.encryption = None
		self.encryptionType = None
		self.encryptionKey = None
		self.encryptionlist = None
		self.weplist = None
		self.wsconfig = None
		self.default = None

		if iNetwork.isWirelessInterface(self.iface):
			from Plugins.SystemPlugins.WirelessLan.Wlan import wpaSupplicant
			self.ws = wpaSupplicant()
			self.encryptionlist = []
			self.encryptionlist.append(("Unencrypted", _("Unencrypted")))
			self.encryptionlist.append(("WEP", _("WEP")))
			self.encryptionlist.append(("WPA", _("WPA")))
			if not os.path.exists("/tmp/bcm/" + self.iface):
				self.encryptionlist.append(("WPA/WPA2", _("WPA or WPA2")))
			self.encryptionlist.append(("WPA2", _("WPA2")))
			self.weplist = []
			self.weplist.append("ASCII")
			self.weplist.append("HEX")

			self.wsconfig = self.ws.loadConfig(self.iface)
			if self.essid is None:
				self.essid = self.wsconfig['ssid']

			config.plugins.wlan.hiddenessid = NoSave(ConfigYesNo(default=self.wsconfig['hiddenessid']))
			config.plugins.wlan.essid = NoSave(ConfigText(default=self.essid, visible_width=50, fixed_size=False))
			config.plugins.wlan.encryption = NoSave(ConfigSelection(self.encryptionlist, default=self.wsconfig['encryption']))
			config.plugins.wlan.wepkeytype = NoSave(ConfigSelection(self.weplist, default=self.wsconfig['wepkeytype']))
			config.plugins.wlan.psk = NoSave(ConfigPassword(default=self.wsconfig['key'], visible_width=50, fixed_size=False))

		self.activateInterfaceEntry = NoSave(ConfigYesNo(default=iNetwork.getAdapterAttribute(self.iface, "up") or False))
		self.dhcpConfigEntry = NoSave(ConfigYesNo(default=iNetwork.getAdapterAttribute(self.iface, "dhcp") or False))
		self.ipConfigEntry = NoSave(ConfigIP(default=iNetwork.getAdapterAttribute(self.iface, "ip")) or [0, 0, 0, 0])
		self.netmaskConfigEntry = NoSave(ConfigIP(default=iNetwork.getAdapterAttribute(self.iface, "netmask") or [255, 0, 0, 0]))
		if iNetwork.getAdapterAttribute(self.iface, "gateway"):
			self.dhcpdefault = True
		else:
			self.dhcpdefault = False
		self.hasGatewayConfigEntry = NoSave(ConfigYesNo(default=self.dhcpdefault or False))
		self.gatewayConfigEntry = NoSave(ConfigIP(default=iNetwork.getAdapterAttribute(self.iface, "gateway") or [0, 0, 0, 0]))
		nameserver = (iNetwork.getNameserverList() + [[0, 0, 0, 0]] * 2)[0:2]
		self.primaryDNS = NoSave(ConfigIP(default=nameserver[0]))
		self.secondaryDNS = NoSave(ConfigIP(default=nameserver[1]))

	def createSetup(self):
		self.list = []
		self.InterfaceEntry = getConfigListEntry(_("Use interface"), self.activateInterfaceEntry)

		self.list.append(self.InterfaceEntry)
		if self.activateInterfaceEntry.value:
			self.dhcpEntry = getConfigListEntry(_("Use DHCP"), self.dhcpConfigEntry)
			self.list.append(self.dhcpEntry)
			if not self.dhcpConfigEntry.value:
				self.list.append(getConfigListEntry(_('IP address'), self.ipConfigEntry))
				self.list.append(getConfigListEntry(_('Netmask'), self.netmaskConfigEntry))
				self.gatewayEntry = getConfigListEntry(_('Use a gateway'), self.hasGatewayConfigEntry)
				self.list.append(self.gatewayEntry)
				if self.hasGatewayConfigEntry.value:
					self.list.append(getConfigListEntry(_('Gateway'), self.gatewayConfigEntry))

			self.extended = None
			self.configStrings = None
			for p in plugins.getPlugins(PluginDescriptor.WHERE_NETWORKSETUP):
				callFnc = p.__call__["ifaceSupported"](self.iface)
				if callFnc is not None:
					if "WlanPluginEntry" in p.__call__: # internally used only for WLAN Plugin
						self.extended = callFnc
						if "configStrings" in p.__call__:
							self.configStrings = p.__call__["configStrings"]
						isExistBcmWifi = os.path.exists("/tmp/bcm/" + self.iface)
						if not isExistBcmWifi:
							self.hiddenSSID = getConfigListEntry(_("Hidden network"), config.plugins.wlan.hiddenessid)
							self.list.append(self.hiddenSSID)
						self.wlanSSID = getConfigListEntry(_("Network name (SSID)"), config.plugins.wlan.essid)
						self.list.append(self.wlanSSID)
						self.encryption = getConfigListEntry(_("Encryption"), config.plugins.wlan.encryption)
						self.list.append(self.encryption)
						if not isExistBcmWifi:
							self.encryptionType = getConfigListEntry(_("Encryption key type"), config.plugins.wlan.wepkeytype)
						self.encryptionKey = getConfigListEntry(_("Encryption key"), config.plugins.wlan.psk)

						if config.plugins.wlan.encryption.value != "Unencrypted":
							if config.plugins.wlan.encryption.value == 'WEP':
								if not isExistBcmWifi:
									self.list.append(self.encryptionType)
							self.list.append(self.encryptionKey)
		self["config"].list = self.list
		self["config"].l.setList(self.list)

	def KeyBlue(self):
		self.session.openWithCallback(self.NameserverSetupClosed, NameserverSetup)

	def newConfig(self):
		if self["config"].getCurrent() == self.InterfaceEntry:
			self.createSetup()
		if self["config"].getCurrent() == self.dhcpEntry:
			self.createSetup()
		if self["config"].getCurrent() == self.gatewayEntry:
			self.createSetup()
		if iNetwork.isWirelessInterface(self.iface):
			if self["config"].getCurrent() == self.encryption:
				self.createSetup()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.newConfig()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.newConfig()

	def keySave(self):
		self.hideInputHelp()
		if self["config"].isChanged():
			self.session.openWithCallback(self.keySaveConfirm, MessageBox, (_("Are you sure you want to activate this network configuration?\n\n") + self.oktext))
		else:
			if self.finished_cb:
				self.finished_cb()
			else:
				self.close('cancel')

	def keySaveConfirm(self, ret=False):
		if ret:
			num_configured_if = len(iNetwork.getConfiguredAdapters())
			if num_configured_if >= 1:
				if self.iface in iNetwork.getConfiguredAdapters():
					self.applyConfig(True)
				else:
					self.session.openWithCallback(self.secondIfaceFoundCB, MessageBox, _("A second configured interface has been found.\n\nDo you want to disable the second network interface?"), default=True)
			else:
				self.applyConfig(True)
		else:
			self.keyCancel()

	def secondIfaceFoundCB(self, data):
		if data is False:
			self.applyConfig(True)
		else:
			configuredInterfaces = iNetwork.getConfiguredAdapters()
			for interface in configuredInterfaces:
				if interface == self.iface:
					continue
				iNetwork.setAdapterAttribute(interface, "up", False)
			iNetwork.deactivateInterface(configuredInterfaces, self.deactivateSecondInterfaceCB)

	def deactivateSecondInterfaceCB(self, data):
		if data is True:
			self.applyConfig(True)

	def applyConfig(self, ret=False):
		if ret:
			self.applyConfigRef = None
			iNetwork.setAdapterAttribute(self.iface, "up", self.activateInterfaceEntry.value)
			iNetwork.setAdapterAttribute(self.iface, "dhcp", self.dhcpConfigEntry.value)
			iNetwork.setAdapterAttribute(self.iface, "ip", self.ipConfigEntry.value)
			iNetwork.setAdapterAttribute(self.iface, "netmask", self.netmaskConfigEntry.value)
			if self.hasGatewayConfigEntry.value:
				iNetwork.setAdapterAttribute(self.iface, "gateway", self.gatewayConfigEntry.value)
			else:
				iNetwork.removeAdapterAttribute(self.iface, "gateway")

			if self.extended is not None and self.configStrings is not None:
				iNetwork.setAdapterAttribute(self.iface, "configStrings", self.configStrings(self.iface))
				self.ws.writeConfig(self.iface)

			if self.activateInterfaceEntry.value is False:
				iNetwork.deactivateInterface(self.iface, self.deactivateInterfaceCB)
				iNetwork.writeNetworkConfig()
				self.applyConfigRef = self.session.openWithCallback(self.applyConfigfinishedCB, MessageBox, _("Please wait for activation of your network configuration..."), type=MessageBox.TYPE_INFO, enable_input=False)
			else:
				if self.oldInterfaceState is False:
					iNetwork.activateInterface(self.iface, self.deactivateInterfaceCB)
				else:
					iNetwork.deactivateInterface(self.iface, self.activateInterfaceCB)
				iNetwork.writeNetworkConfig()
				self.applyConfigRef = self.session.openWithCallback(self.applyConfigfinishedCB, MessageBox, _("Please wait for activation of your network configuration..."), type=MessageBox.TYPE_INFO, enable_input=False)
		else:
			self.keyCancel()

	def deactivateInterfaceCB(self, data):
		if data is True:
			self.applyConfigDataAvail(True)

	def activateInterfaceCB(self, data):
		if data is True:
			iNetwork.activateInterface(self.iface, self.applyConfigDataAvail)

	def applyConfigDataAvail(self, data):
		if data is True:
			iNetwork.getInterfaces(self.getInterfacesDataAvail)

	def getInterfacesDataAvail(self, data):
		if data is True:
			self.applyConfigRef.close(True)

	def applyConfigfinishedCB(self, data):
		if data is True:
			if self.finished_cb:
				self.session.openWithCallback(lambda x: self.finished_cb(), MessageBox, _("Your network configuration has been activated."), type=MessageBox.TYPE_INFO, timeout=10)
			else:
				self.session.openWithCallback(self.ConfigfinishedCB, MessageBox, _("Your network configuration has been activated."), type=MessageBox.TYPE_INFO, timeout=10)

	def ConfigfinishedCB(self, data):
		if data is not None:
			if data is True:
				self.close('ok')

	def keyCancelConfirm(self, result):
		if not result:
			return
		if self.oldInterfaceState is False:
			iNetwork.deactivateInterface(self.iface, self.keyCancelCB)
		else:
			self.close('cancel')

	def keyCancel(self):
		self.hideInputHelp()
		if self["config"].isChanged():
			self.session.openWithCallback(self.keyCancelConfirm, MessageBox, _("Really close without saving settings?"))
		else:
			self.close('cancel')

	def keyCancelCB(self, data):
		if data is not None:
			if data is True:
				self.close('cancel')

	def runAsync(self, finished_cb):
		self.finished_cb = finished_cb
		self.keySave()

	def NameserverSetupClosed(self, *ret):
		iNetwork.loadNameserverConfig()
		nameserver = (iNetwork.getNameserverList() + [[0, 0, 0, 0]] * 2)[0:2]
		self.primaryDNS = NoSave(ConfigIP(default=nameserver[0]))
		self.secondaryDNS = NoSave(ConfigIP(default=nameserver[1]))
		self.createSetup()
		self.layoutFinished()

	def cleanup(self):
		iNetwork.stopLinkStateConsole()

	def hideInputHelp(self):
		current = self["config"].getCurrent()
		if current == self.wlanSSID:
			if current[1].help_window.instance is not None:
				current[1].help_window.instance.hide()
		elif current == self.encryptionKey and config.plugins.wlan.encryption.value is not "Unencrypted":
			if current[1].help_window.instance is not None:
				current[1].help_window.instance.hide()


class AdapterSetupConfiguration(Screen, HelpableScreen):
	def __init__(self, session, iface):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.setTitle(_("Network configuration"))
		self.session = session
		self.iface = iface
		self.restartLanRef = None
		self.LinkState = None
		self.mainmenu = self.genMainMenu()
		self["menulist"] = MenuList(self.mainmenu)
		self["key_red"] = StaticText(_("Close"))
		self["description"] = StaticText()
		self["IFtext"] = StaticText()
		self["IF"] = StaticText()
		self["Statustext"] = StaticText()
		self["statuspic"] = MultiPixmap()
		self["statuspic"].hide()
		self["devicepic"] = MultiPixmap()

		self.oktext = _("Press OK on your remote control to continue.")
		self.reboottext = _("Your receiver will restart after pressing OK on your remote control.")
		self.errortext = _("No working wireless network interface found.\n Please verify that you have attached a compatible WLAN device or enable your local network interface.")
		self.missingwlanplugintxt = _("The wireless LAN plugin is not installed!\nPlease install it.")

		self["WizardActions"] = HelpableActionMap(self, ["WizardActions"],
			{
			"up": (self.up, _("move up to previous entry")),
			"down": (self.down, _("move down to next entry")),
			"left": (self.left, _("move up to first entry")),
			"right": (self.right, _("move down to last entry")),
			})

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.close, _("exit networkadapter setup menu")),
			"ok": (self.ok, _("select menu entry")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.close, _("exit networkadapter setup menu")),
			})

		self["actions"] = NumberActionMap(["WizardActions", "ShortcutActions"],
		{
			"ok": self.ok,
			"back": self.close,
			"up": self.up,
			"down": self.down,
			"red": self.close,
			"left": self.left,
			"right": self.right,
		}, -2)

		self.updateStatusbar()
		self.onLayoutFinish.append(self.layoutFinished)
		self.onClose.append(self.cleanup)

	def queryWirelessDevice(self, iface):
		try:
			from pythonwifi.iwlibs import Wireless
			import errno
		except ImportError as e:
			return False
		else:
			try:
				ifobj = Wireless(iface) # a Wireless NIC Object
				wlanresponse = ifobj.getAPaddr()
			except IOError as error_no_error_str:
				(error_no, error_str) = error_no_error_str
				if error_no in (errno.EOPNOTSUPP, errno.ENODEV, errno.EPERM):
					return False
				else:
					print("[NetworkSetup] error: ", error_no, error_str)
					return True
			else:
				return True

	def ok(self):
		self.cleanup()
		if self["menulist"].getCurrent()[1] == 'edit':
			if iNetwork.isWirelessInterface(self.iface):
				try:
					from Plugins.SystemPlugins.WirelessLan.plugin import WlanScan
				except ImportError as e:
					self.session.open(MessageBox, self.missingwlanplugintxt, type=MessageBox.TYPE_INFO, timeout=10)
				else:
					if self.queryWirelessDevice(self.iface):
						self.session.openWithCallback(self.AdapterSetupClosed, AdapterSetup, self.iface)
					else:
						self.showErrorMessage()	# Display Wlan not available Message
			else:
				self.session.openWithCallback(self.AdapterSetupClosed, AdapterSetup, self.iface)
		if self["menulist"].getCurrent()[1] == 'test':
			self.session.open(NetworkAdapterTest, self.iface)
		if self["menulist"].getCurrent()[1] == 'dns':
			self.session.open(NameserverSetup)
		if self["menulist"].getCurrent()[1] == 'mac':
			self.session.open(NetworkMacSetup)
		if self["menulist"].getCurrent()[1] == 'ipv6':
			self.session.open(IPv6Setup)
		if self["menulist"].getCurrent()[1] == 'scanwlan':
			try:
				from Plugins.SystemPlugins.WirelessLan.plugin import WlanScan
			except ImportError as e:
				self.session.open(MessageBox, self.missingwlanplugintxt, type=MessageBox.TYPE_INFO, timeout=10)
			else:
				if self.queryWirelessDevice(self.iface):
					self.session.openWithCallback(self.WlanScanClosed, WlanScan, self.iface)
				else:
					self.showErrorMessage()	# Display Wlan not available Message
		if self["menulist"].getCurrent()[1] == 'wlanstatus':
			try:
				from Plugins.SystemPlugins.WirelessLan.plugin import WlanStatus
			except ImportError as e:
				self.session.open(MessageBox, self.missingwlanplugintxt, type=MessageBox.TYPE_INFO, timeout=10)
			else:
				if self.queryWirelessDevice(self.iface):
					self.session.openWithCallback(self.WlanStatusClosed, WlanStatus, self.iface)
				else:
					self.showErrorMessage()	# Display Wlan not available Message
		if self["menulist"].getCurrent()[1] == 'lanrestart':
			self.session.openWithCallback(self.restartLan, MessageBox, (_("Are you sure you want to restart your network interfaces?\n\n") + self.oktext))
		if self["menulist"].getCurrent()[1] == 'openwizard':
			from Plugins.SystemPlugins.NetworkWizard.NetworkWizard import NetworkWizard
			self.session.openWithCallback(self.AdapterSetupClosed, NetworkWizard, self.iface)
		if self["menulist"].getCurrent()[1][0] == 'extendedSetup':
			self.extended = self["menulist"].getCurrent()[1][2]
			self.extended(self.session, self.iface)

	def up(self):
		self["menulist"].up()
		self.loadDescription()

	def down(self):
		self["menulist"].down()
		self.loadDescription()

	def left(self):
		self["menulist"].pageUp()
		self.loadDescription()

	def right(self):
		self["menulist"].pageDown()
		self.loadDescription()

	def layoutFinished(self):
		idx = 0
		self["menulist"].moveToIndex(idx)
		self.loadDescription()

	def loadDescription(self):
		if self["menulist"].getCurrent()[1] == 'edit':
			self["description"].setText(_("Edit the network configuration of your receiver.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'test':
			self["description"].setText(_("Test the network configuration of your receiver.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'dns':
			self["description"].setText(_("Edit the nameserver configuration of your receiver.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'scanwlan':
			self["description"].setText(_("Scan your network for wireless access points and connect to them using your selected wireless device.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'wlanstatus':
			self["description"].setText(_("Shows the state of your wireless LAN connection.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'lanrestart':
			self["description"].setText(_("Restart your network connection and interfaces.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'openwizard':
			self["description"].setText(_("Use the network wizard to configure your network\n") + self.oktext)
		if self["menulist"].getCurrent()[1][0] == 'extendedSetup':
			self["description"].setText(_(self["menulist"].getCurrent()[1][1]) + self.oktext)
		if self["menulist"].getCurrent()[1] == 'mac':
			self["description"].setText(_("Set the MAC address of your receiver.\n") + self.oktext)
		if self["menulist"].getCurrent()[1] == 'ipv6':
			self["description"].setText(_("Enable/Disable IPv6 support of your receiver.\n") + self.oktext)

	def updateStatusbar(self, data=None):
		self.mainmenu = self.genMainMenu()
		self["menulist"].l.setList(self.mainmenu)
		self["IFtext"].setText(_("Network:"))
		self["IF"].setText(iNetwork.getFriendlyAdapterName(self.iface))
		self["Statustext"].setText(_("Link:"))

		if iNetwork.isWirelessInterface(self.iface):
			self["devicepic"].setPixmapNum(1)
			try:
				from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus
			except:
				self["statuspic"].setPixmapNum(1)
				self["statuspic"].show()
			else:
				iStatus.getDataForInterface(self.iface, self.getInfoCB)
		else:
			iNetwork.getLinkState(self.iface, self.dataAvail)
			self["devicepic"].setPixmapNum(0)
		self["devicepic"].show()

	def doNothing(self):
		pass

	def genMainMenu(self):
		menu = []
		menu.append((_("Adapter settings"), "edit"))
		menu.append((_("Nameserver settings"), "dns"))
		menu.append((_("Network test"), "test"))
		menu.append((_("Restart network"), "lanrestart"))

		self.extended = None
		self.extendedSetup = None
		for p in plugins.getPlugins(PluginDescriptor.WHERE_NETWORKSETUP):
			callFnc = p.__call__["ifaceSupported"](self.iface)
			if callFnc is not None:
				self.extended = callFnc
				if "WlanPluginEntry" in p.__call__: # internally used only for WLAN Plugin
					menu.append((_("Scan wireless networks"), "scanwlan"))
					if iNetwork.getAdapterAttribute(self.iface, "up"):
						menu.append((_("Show WLAN status"), "wlanstatus"))
				else:
					if "menuEntryName" in p.__call__:
						menuEntryName = p.__call__["menuEntryName"](self.iface)
					else:
						menuEntryName = _('Extended setup...')
					if "menuEntryDescription" in p.__call__:
						menuEntryDescription = p.__call__["menuEntryDescription"](self.iface)
					else:
						menuEntryDescription = _('Extended network setup plugin...')
					self.extendedSetup = ('extendedSetup', menuEntryDescription, self.extended)
					menu.append((menuEntryName, self.extendedSetup))

		if os.path.exists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/NetworkWizard/networkwizard.xml")):
			menu.append((_("Network wizard"), "openwizard"))
		if self.iface == 'eth0':
			menu.append((_("Network MAC settings"), "mac"))
			menu.append((_("Enable/Disable IPv6"), "ipv6"))

		return menu

	def AdapterSetupClosed(self, *ret):
		if ret is not None and len(ret):
			if ret[0] == 'ok' and (iNetwork.isWirelessInterface(self.iface) and iNetwork.getAdapterAttribute(self.iface, "up") is True):
				try:
					from Plugins.SystemPlugins.WirelessLan.plugin import WlanStatus
				except ImportError as e:
					self.session.open(MessageBox, self.missingwlanplugintxt, type=MessageBox.TYPE_INFO, timeout=10)
				else:
					if self.queryWirelessDevice(self.iface):
						self.session.openWithCallback(self.WlanStatusClosed, WlanStatus, self.iface)
					else:
						self.showErrorMessage()	# Display Wlan not available Message
			else:
				self.updateStatusbar()
		else:
			self.updateStatusbar()

	def WlanStatusClosed(self, *ret):
		if ret is not None and len(ret):
			from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus
			iStatus.stopWlanConsole()
			self.updateStatusbar()

	def WlanScanClosed(self, *ret):
		if ret[0] is not None:
			self.session.openWithCallback(self.AdapterSetupClosed, AdapterSetup, self.iface, ret[0])
		else:
			from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus
			iStatus.stopWlanConsole()
			self.updateStatusbar()

	def restartLan(self, ret=False):
		if ret:
			iNetwork.restartNetwork(self.restartLanDataAvail)
			self.restartLanRef = self.session.openWithCallback(self.restartfinishedCB, MessageBox, _("Please wait while your network is restarting..."), type=MessageBox.TYPE_INFO, enable_input=False)

	def restartLanDataAvail(self, data):
		if data is True:
			iNetwork.getInterfaces(self.getInterfacesDataAvail)

	def getInterfacesDataAvail(self, data):
		if data is True:
			self.restartLanRef.close(True)

	def restartfinishedCB(self, data):
		if data is True:
			self.updateStatusbar()
			self.session.open(MessageBox, _("Finished restarting your network"), type=MessageBox.TYPE_INFO, timeout=10, default=False)

	def dataAvail(self, data):
		self.LinkState = None
		for line in data.splitlines():
			if PY2:
				line = line.strip()
			else:
				line = line.strip().decode()
			if 'Link detected:' in line:
				if "yes" in line:
					self.LinkState = True
				else:
					self.LinkState = False
		if self.LinkState:
			iNetwork.checkNetworkState(self.checkNetworkCB)
		else:
			self["statuspic"].setPixmapNum(1)
			self["statuspic"].show()

	def showErrorMessage(self):
		self.session.open(MessageBox, self.errortext, type=MessageBox.TYPE_INFO, timeout=10)

	def cleanup(self):
		iNetwork.stopLinkStateConsole()
		iNetwork.stopDeactivateInterfaceConsole()
		iNetwork.stopActivateInterfaceConsole()
		iNetwork.stopPingConsole()
		try:
			from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus
		except ImportError as e:
			pass
		else:
			iStatus.stopWlanConsole()

	def getInfoCB(self, data, status):
		self.LinkState = None
		if data is not None:
			if data is True:
				if status is not None:
					if status[self.iface]["essid"] == "off" or status[self.iface]["accesspoint"] == "Not-Associated" or status[self.iface]["accesspoint"] == False:
						self.LinkState = False
						self["statuspic"].setPixmapNum(1)
						self["statuspic"].show()
					else:
						self.LinkState = True
						iNetwork.checkNetworkState(self.checkNetworkCB)

	def checkNetworkCB(self, data):
		if iNetwork.getAdapterAttribute(self.iface, "up") is True:
			if self.LinkState is True:
				if data <= 2:
					self["statuspic"].setPixmapNum(0)
				else:
					self["statuspic"].setPixmapNum(1)
				self["statuspic"].show()
			else:
				self["statuspic"].setPixmapNum(1)
				self["statuspic"].show()
		else:
			self["statuspic"].setPixmapNum(1)
			self["statuspic"].show()


class NetworkAdapterTest(Screen):
	def __init__(self, session, iface):
		Screen.__init__(self, session)
		self.iface = iface
		self.setTitle(_("Network test: ") + iNetwork.getFriendlyAdapterName(self.iface))
		self.oldInterfaceState = iNetwork.getAdapterAttribute(self.iface, "up")
		self.setLabels()
		self.onClose.append(self.cleanup)
		self.onHide.append(self.cleanup)

		self["updown_actions"] = NumberActionMap(["WizardActions", "ShortcutActions"],
		{
			"ok": self.KeyOK,
			"blue": self.KeyOK,
			"up": lambda: self.updownhandler('up'),
			"down": lambda: self.updownhandler('down'),

		}, -2)

		self["shortcuts"] = ActionMap(["ShortcutActions", "WizardActions"],
		{
			"red": self.cancel,
			"back": self.cancel,
		}, -2)
		self["infoshortcuts"] = ActionMap(["ShortcutActions", "WizardActions"],
		{
			"red": self.closeInfo,
			"back": self.closeInfo,
		}, -2)
		self["shortcutsgreen"] = ActionMap(["ShortcutActions"],
		{
			"green": self.KeyGreen,
		}, -2)
		self["shortcutsgreen_restart"] = ActionMap(["ShortcutActions"],
		{
			"green": self.KeyGreenRestart,
		}, -2)
		self["shortcutsyellow"] = ActionMap(["ShortcutActions"],
		{
			"yellow": self.KeyYellow,
		}, -2)

		self["shortcutsgreen_restart"].setEnabled(False)
		self["updown_actions"].setEnabled(False)
		self["infoshortcuts"].setEnabled(False)
		self.onClose.append(self.delTimer)
		self.onLayoutFinish.append(self.layoutFinished)
		self.steptimer = False
		self.nextstep = 0
		self.activebutton = 0
		self.nextStepTimer = eTimer()
		self.nextStepTimer.callback.append(self.nextStepTimerFire)

	def cancel(self):
		if self.oldInterfaceState is False:
			iNetwork.setAdapterAttribute(self.iface, "up", self.oldInterfaceState)
			iNetwork.deactivateInterface(self.iface)
		self.close()

	def closeInfo(self):
		self["shortcuts"].setEnabled(True)
		self["infoshortcuts"].setEnabled(False)
		self["InfoText"].hide()
		self["InfoTextBorder"].hide()
		self["key_red"].setText(_("Close"))

	def delTimer(self):
		del self.steptimer
		del self.nextStepTimer

	def nextStepTimerFire(self):
		self.nextStepTimer.stop()
		self.steptimer = False
		self.runTest()

	def updownhandler(self, direction):
		if direction == 'up':
			if self.activebutton >= 2:
				self.activebutton -= 1
			else:
				self.activebutton = 6
			self.setActiveButton(self.activebutton)
		if direction == 'down':
			if self.activebutton <= 5:
				self.activebutton += 1
			else:
				self.activebutton = 1
			self.setActiveButton(self.activebutton)

	def setActiveButton(self, button):
		if button == 1:
			self["EditSettingsButton"].setPixmapNum(0)
			self["EditSettings_Text"].setForegroundColorNum(0)
			self["NetworkInfo"].setPixmapNum(0)
			self["NetworkInfo_Text"].setForegroundColorNum(1)
			self["AdapterInfo"].setPixmapNum(1) 		  # active
			self["AdapterInfo_Text"].setForegroundColorNum(2) # active
		if button == 2:
			self["AdapterInfo_Text"].setForegroundColorNum(1)
			self["AdapterInfo"].setPixmapNum(0)
			self["DhcpInfo"].setPixmapNum(0)
			self["DhcpInfo_Text"].setForegroundColorNum(1)
			self["NetworkInfo"].setPixmapNum(1) 		  # active
			self["NetworkInfo_Text"].setForegroundColorNum(2) # active
		if button == 3:
			self["NetworkInfo"].setPixmapNum(0)
			self["NetworkInfo_Text"].setForegroundColorNum(1)
			self["IPInfo"].setPixmapNum(0)
			self["IPInfo_Text"].setForegroundColorNum(1)
			self["DhcpInfo"].setPixmapNum(1) 		  # active
			self["DhcpInfo_Text"].setForegroundColorNum(2) 	  # active
		if button == 4:
			self["DhcpInfo"].setPixmapNum(0)
			self["DhcpInfo_Text"].setForegroundColorNum(1)
			self["DNSInfo"].setPixmapNum(0)
			self["DNSInfo_Text"].setForegroundColorNum(1)
			self["IPInfo"].setPixmapNum(1)			# active
			self["IPInfo_Text"].setForegroundColorNum(2)	# active
		if button == 5:
			self["IPInfo"].setPixmapNum(0)
			self["IPInfo_Text"].setForegroundColorNum(1)
			self["EditSettingsButton"].setPixmapNum(0)
			self["EditSettings_Text"].setForegroundColorNum(0)
			self["DNSInfo"].setPixmapNum(1)			# active
			self["DNSInfo_Text"].setForegroundColorNum(2)	# active
		if button == 6:
			self["DNSInfo"].setPixmapNum(0)
			self["DNSInfo_Text"].setForegroundColorNum(1)
			self["EditSettingsButton"].setPixmapNum(1) 	   # active
			self["EditSettings_Text"].setForegroundColorNum(2) # active
			self["AdapterInfo"].setPixmapNum(0)
			self["AdapterInfo_Text"].setForegroundColorNum(1)

	def runTest(self):
		next = self.nextstep
		if next == 0:
			self.doStep1()
		elif next == 1:
			self.doStep2()
		elif next == 2:
			self.doStep3()
		elif next == 3:
			self.doStep4()
		elif next == 4:
			self.doStep5()
		elif next == 5:
			self.doStep6()
		self.nextstep += 1

	def doStep1(self):
		self.steptimer = True
		self.nextStepTimer.start(300)
		self["key_yellow"].setText(_("Stop test"))

	def doStep2(self):
		self["Adapter"].setText(iNetwork.getFriendlyAdapterName(self.iface))
		self["Adapter"].setForegroundColorNum(2)
		self["Adaptertext"].setForegroundColorNum(1)
		self["AdapterInfo_Text"].setForegroundColorNum(1)
		self["AdapterInfo_OK"].show()
		self.steptimer = True
		self.nextStepTimer.start(300)

	def doStep3(self):
		self["Networktext"].setForegroundColorNum(1)
		self["Network"].setText(_("Please wait..."))
		self.getLinkState(self.iface)
		self["NetworkInfo_Text"].setForegroundColorNum(1)
		self.steptimer = True
		self.nextStepTimer.start(1000)

	def doStep4(self):
		self["Dhcptext"].setForegroundColorNum(1)
		if iNetwork.getAdapterAttribute(self.iface, 'dhcp') is True:
			self["Dhcp"].setForegroundColorNum(2)
			self["Dhcp"].setText(_("enabled"))
			self["DhcpInfo_Check"].setPixmapNum(0)
		else:
			self["Dhcp"].setForegroundColorNum(1)
			self["Dhcp"].setText(_("disabled"))
			self["DhcpInfo_Check"].setPixmapNum(1)
		self["DhcpInfo_Check"].show()
		self["DhcpInfo_Text"].setForegroundColorNum(1)
		self.steptimer = True
		self.nextStepTimer.start(1000)

	def doStep5(self):
		self["IPtext"].setForegroundColorNum(1)
		self["IP"].setText(_("Please wait..."))
		iNetwork.checkNetworkState(self.NetworkStatedataAvail)

	def doStep6(self):
		self.steptimer = False
		self.nextStepTimer.stop()
		self["DNStext"].setForegroundColorNum(1)
		self["DNS"].setText(_("Please wait..."))
		iNetwork.checkDNSLookup(self.DNSLookupdataAvail)

	def KeyGreen(self):
		self["shortcutsgreen"].setEnabled(False)
		self["shortcutsyellow"].setEnabled(True)
		self["updown_actions"].setEnabled(False)
		self["key_yellow"].setText("")
		self["key_green"].setText("")
		self.steptimer = True
		self.nextStepTimer.start(1000)

	def KeyGreenRestart(self):
		self.nextstep = 0
		self.layoutFinished()
		self["Adapter"].setText("")
		self["Network"].setText("")
		self["Dhcp"].setText("")
		self["IP"].setText("")
		self["DNS"].setText("")
		self["AdapterInfo_Text"].setForegroundColorNum(0)
		self["NetworkInfo_Text"].setForegroundColorNum(0)
		self["DhcpInfo_Text"].setForegroundColorNum(0)
		self["IPInfo_Text"].setForegroundColorNum(0)
		self["DNSInfo_Text"].setForegroundColorNum(0)
		self["shortcutsgreen_restart"].setEnabled(False)
		self["shortcutsgreen"].setEnabled(False)
		self["shortcutsyellow"].setEnabled(True)
		self["updown_actions"].setEnabled(False)
		self["key_yellow"].setText("")
		self["key_green"].setText("")
		self.steptimer = True
		self.nextStepTimer.start(1000)

	def KeyOK(self):
		self["infoshortcuts"].setEnabled(True)
		self["shortcuts"].setEnabled(False)
		if self.activebutton == 1: # Adapter Check
			self["InfoText"].setText(_("This test detects your configured LAN adapter."))
			self["InfoTextBorder"].show()
			self["InfoText"].show()
			self["key_red"].setText(_("Back"))
		if self.activebutton == 2: #LAN Check
			self["InfoText"].setText(_("This test checks whether a network cable is connected to your LAN adapter.\nIf you get a \"disconnected\" message:\n- verify that a network cable is attached\n- verify that the cable is not broken"))
			self["InfoTextBorder"].show()
			self["InfoText"].show()
			self["key_red"].setText(_("Back"))
		if self.activebutton == 3: #DHCP Check
			self["InfoText"].setText(_("This test checks whether your LAN adapter is set up for automatic IP address configuration with DHCP.\nIf you get a \"disabled\" message:\n - then your LAN adapter is configured for manual IP setup\n- verify thay you have entered the correct IP information in the adapter setup dialog.\nIf you get an \"enabeld\" message:\n-verify that you have a configured and working DHCP server in your network."))
			self["InfoTextBorder"].show()
			self["InfoText"].show()
			self["key_red"].setText(_("Back"))
		if self.activebutton == 4: # IP Check
			self["InfoText"].setText(_("This test checks whether a valid IP address is found for your LAN adapter.\nIf you get a \"unconfirmed\" message:\n- no valid IP address was found\n- please check your DHCP, cabling and adapter setup"))
			self["InfoTextBorder"].show()
			self["InfoText"].show()
			self["key_red"].setText(_("Back"))
		if self.activebutton == 5: # DNS Check
			self["InfoText"].setText(_("This test checks for configured nameservers.\nIf you get a \"unconfirmed\" message:\n- please check your DHCP, cabling and adapter setup\n- if you configured your nameservers manually please verify your entries in the \"Nameserver\" configuration"))
			self["InfoTextBorder"].show()
			self["InfoText"].show()
			self["key_red"].setText(_("Back"))
		if self.activebutton == 6: # Edit Settings
			self.session.open(AdapterSetup, self.iface)

	def KeyYellow(self):
		self.nextstep = 0
		self["shortcutsgreen_restart"].setEnabled(True)
		self["shortcutsgreen"].setEnabled(False)
		self["shortcutsyellow"].setEnabled(False)
		self["key_green"].setText(_("Restart test"))
		self["key_yellow"].setText("")
		self.steptimer = False
		self.nextStepTimer.stop()

	def layoutFinished(self):
		self["shortcutsyellow"].setEnabled(False)
		self["AdapterInfo_OK"].hide()
		self["NetworkInfo_Check"].hide()
		self["DhcpInfo_Check"].hide()
		self["IPInfo_Check"].hide()
		self["DNSInfo_Check"].hide()
		self["EditSettings_Text"].hide()
		self["EditSettingsButton"].hide()
		self["InfoText"].hide()
		self["InfoTextBorder"].hide()
		self["key_yellow"].setText("")

	def setLabels(self):
		self["Adaptertext"] = MultiColorLabel(_("LAN adapter"))
		self["Adapter"] = MultiColorLabel()
		self["AdapterInfo"] = MultiPixmap()
		self["AdapterInfo_Text"] = MultiColorLabel(_("Show info"))
		self["AdapterInfo_OK"] = Pixmap()

		if self.iface in iNetwork.wlan_interfaces:
			self["Networktext"] = MultiColorLabel(_("Wireless network"))
		else:
			self["Networktext"] = MultiColorLabel(_("Local network"))

		self["Network"] = MultiColorLabel()
		self["NetworkInfo"] = MultiPixmap()
		self["NetworkInfo_Text"] = MultiColorLabel(_("Show info"))
		self["NetworkInfo_Check"] = MultiPixmap()

		self["Dhcptext"] = MultiColorLabel(_("DHCP"))
		self["Dhcp"] = MultiColorLabel()
		self["DhcpInfo"] = MultiPixmap()
		self["DhcpInfo_Text"] = MultiColorLabel(_("Show info"))
		self["DhcpInfo_Check"] = MultiPixmap()

		self["IPtext"] = MultiColorLabel(_("IP address"))
		self["IP"] = MultiColorLabel()
		self["IPInfo"] = MultiPixmap()
		self["IPInfo_Text"] = MultiColorLabel(_("Show info"))
		self["IPInfo_Check"] = MultiPixmap()

		self["DNStext"] = MultiColorLabel(_("Nameserver"))
		self["DNS"] = MultiColorLabel()
		self["DNSInfo"] = MultiPixmap()
		self["DNSInfo_Text"] = MultiColorLabel(_("Show info"))
		self["DNSInfo_Check"] = MultiPixmap()

		self["EditSettings_Text"] = MultiColorLabel(_("Edit settings"))
		self["EditSettingsButton"] = MultiPixmap()

		self["key_red"] = StaticText(_("Close"))
		self["key_green"] = StaticText(_("Start test"))
		self["key_yellow"] = StaticText(_("Stop test"))

		self["InfoTextBorder"] = Pixmap()
		self["InfoText"] = Label()

	def getLinkState(self, iface):
		if iface in iNetwork.wlan_interfaces:
			try:
				from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus
			except:
				self["Network"].setForegroundColorNum(1)
				self["Network"].setText(_("disconnected"))
				self["NetworkInfo_Check"].setPixmapNum(1)
				self["NetworkInfo_Check"].show()
			else:
				iStatus.getDataForInterface(self.iface, self.getInfoCB)
		else:
			iNetwork.getLinkState(iface, self.LinkStatedataAvail)

	def LinkStatedataAvail(self, data):
		for item in data.splitlines():
			if "Link detected:" in item:
				if "yes" in item:
					self["Network"].setForegroundColorNum(2)
					self["Network"].setText(_("connected"))
					self["NetworkInfo_Check"].setPixmapNum(0)
				else:
					self["Network"].setForegroundColorNum(1)
					self["Network"].setText(_("disconnected"))
					self["NetworkInfo_Check"].setPixmapNum(1)
				break
		else:
			self["Network"].setText(_("unknown"))
		self["NetworkInfo_Check"].show()

	def NetworkStatedataAvail(self, data):
		if data <= 2:
			self["IP"].setForegroundColorNum(2)
			self["IP"].setText(_("confirmed"))
			self["IPInfo_Check"].setPixmapNum(0)
		else:
			self["IP"].setForegroundColorNum(1)
			self["IP"].setText(_("unconfirmed"))
			self["IPInfo_Check"].setPixmapNum(1)
		self["IPInfo_Check"].show()
		self["IPInfo_Text"].setForegroundColorNum(1)
		self.steptimer = True
		self.nextStepTimer.start(300)

	def DNSLookupdataAvail(self, data):
		if data <= 2:
			self["DNS"].setForegroundColorNum(2)
			self["DNS"].setText(_("confirmed"))
			self["DNSInfo_Check"].setPixmapNum(0)
		else:
			self["DNS"].setForegroundColorNum(1)
			self["DNS"].setText(_("unconfirmed"))
			self["DNSInfo_Check"].setPixmapNum(1)
		self["DNSInfo_Check"].show()
		self["DNSInfo_Text"].setForegroundColorNum(1)
		self["EditSettings_Text"].show()
		self["EditSettingsButton"].setPixmapNum(1)
		self["EditSettings_Text"].setForegroundColorNum(2) # active
		self["EditSettingsButton"].show()
		self["key_yellow"].setText("")
		self["key_green"].setText(_("Restart test"))
		self["shortcutsgreen"].setEnabled(False)
		self["shortcutsgreen_restart"].setEnabled(True)
		self["shortcutsyellow"].setEnabled(False)
		self["updown_actions"].setEnabled(True)
		self.activebutton = 6

	def getInfoCB(self, data, status):
		if data is not None:
			if data is True:
				if status is not None:
					if status[self.iface]["essid"] == "off" or status[self.iface]["accesspoint"] == "Not-Associated" or status[self.iface]["accesspoint"] == False:
						self["Network"].setForegroundColorNum(1)
						self["Network"].setText(_("disconnected"))
						self["NetworkInfo_Check"].setPixmapNum(1)
						self["NetworkInfo_Check"].show()
					else:
						self["Network"].setForegroundColorNum(2)
						self["Network"].setText(_("connected"))
						self["NetworkInfo_Check"].setPixmapNum(0)
						self["NetworkInfo_Check"].show()

	def cleanup(self):
		iNetwork.stopLinkStateConsole()
		iNetwork.stopDNSConsole()
		try:
			from Plugins.SystemPlugins.WirelessLan.Wlan import iStatus
		except ImportError as e:
			pass
		else:
			iStatus.stopWlanConsole()


class NetworkMountsMenu(Screen, HelpableScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		Screen.setTitle(self, _("Mounts setup"))
		self.session = session
		self.onChangedEntry = []
		self.mainmenu = self.genMainMenu()
		self["menulist"] = MenuList(self.mainmenu)
		self["key_red"] = StaticText(_("Close"))
		self["introduction"] = StaticText()

		self["WizardActions"] = HelpableActionMap(self, ["WizardActions"],
			{
			"up": (self.up, _("Move up to previous entry")),
			"down": (self.down, _("Move down to next entry")),
			"left": (self.left, _("Move up to first entry")),
			"right": (self.right, _("Move down to last entry")),
			})

		self["OkCancelActions"] = HelpableActionMap(self, ["OkCancelActions"],
			{
			"cancel": (self.close, _("Exit mounts setup menu")),
			"ok": (self.ok, _("Select menu entry")),
			})

		self["ColorActions"] = HelpableActionMap(self, ["ColorActions"],
			{
			"red": (self.close, _("Exit networkadapter setup menu")),
			})

		self["actions"] = NumberActionMap(["WizardActions", "ShortcutActions"],
		{
			"ok": self.ok,
			"back": self.close,
			"up": self.up,
			"down": self.down,
			"red": self.close,
			"left": self.left,
			"right": self.right,
		}, -2)

		if not self.selectionChanged in self["menulist"].onSelectionChanged:
			self["menulist"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["menulist"].getCurrent()
		if item:
			if item[1][0] == 'extendedSetup':
				self["introduction"].setText(_(item[1][1]))
			name = str(self["menulist"].getCurrent()[0])
			desc = self["introduction"].text
		else:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def ok(self):
		if self["menulist"].getCurrent()[1][0] == 'extendedSetup':
			self.extended = self["menulist"].getCurrent()[1][2]
			self.extended(self.session)

	def up(self):
		self["menulist"].up()

	def down(self):
		self["menulist"].down()

	def left(self):
		self["menulist"].pageUp()

	def right(self):
		self["menulist"].pageDown()

	def genMainMenu(self):
		menu = []
		self.extended = None
		self.extendedSetup = None
		for p in plugins.getPlugins(PluginDescriptor.WHERE_NETWORKMOUNTS):
			callFnc = p.__call__["ifaceSupported"](self)
			if callFnc is not None:
				self.extended = callFnc
				if 'menuEntryName' in p.__call__:
					menuEntryName = p.__call__["menuEntryName"](self)
				else:
					menuEntryName = _('Extended setup...')
				if 'menuEntryDescription' in p.__call__:
					menuEntryDescription = p.__call__["menuEntryDescription"](self)
				else:
					menuEntryDescription = _('Extended network setup plugin...')
				self.extendedSetup = ('extendedSetup', menuEntryDescription, self.extended)
				menu.append((menuEntryName, self.extendedSetup))
		return menu


class NetworkAfp(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("AFP setup"))
		self.skinName = "NetworkAfp"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_red'] = Label(_("Remove service"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self['status_summary'] = StaticText()
		self['autostartstatus_summary'] = StaticText()
		self.Console = Console()
		self.my_afp_active = False
		self.my_afp_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.AfpStartStop, 'yellow': self.activateAfp})
		self.service_name = 'netatalk kernel-module-appletalk kernel-module-llc kernel-module-psnap'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = True

	def createSummary(self):
		return NetworkServicesSummary

	def AfpStartStop(self):
		if not self.my_afp_run:
			self.Console.ePopen('/etc/init.d/atalk start', self.StartStopCallback)
		elif self.my_afp_run:
			self.Console.ePopen('/etc/init.d/atalk stop', self.StartStopCallback)

	def activateAfp(self):
		if ServiceIsEnabled('atalk'):
			self.Console.ePopen('update-rc.d -f atalk remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f atalk defaults', self.StartStopCallback)

	def updateService(self, result=None, retval=None, extra_args=None):
		import process
		p = process.ProcessList()
		afp_process = str(p.named('afpd')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_afp_active = False
		self.my_afp_run = False
		if ServiceIsEnabled('atalk'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_afp_active = True
		if afp_process:
			self.my_afp_run = True
		if self.my_afp_run:
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("AFP setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkSABnzbd(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("SABnzbd setup"))
		self.skinName = "NetworkSABnzbd"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_red'] = Label(_("Remove service"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self['status_summary'] = StaticText()
		self['autostartstatus_summary'] = StaticText()
		self.Console = Console()
		self.my_sabnzbd_active = False
		self.my_sabnzbd_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.SABnzbStartStop, 'yellow': self.activateSABnzbd})
		self.service_name = 'sabnzbd'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def SABnzbStartStop(self):
		if not self.my_sabnzbd_run:
			self.Console.ePopen('/etc/init.d/sabnzbd start')
			time.sleep(3)
			self.updateService()
		elif self.my_sabnzbd_run:
			self.Console.ePopen('/etc/init.d/sabnzbd stop')
			time.sleep(3)
			self.updateService()

	def activateSABnzbd(self):
		if ServiceIsEnabled('sabnzbd'):
			self.Console.ePopen('update-rc.d -f sabnzbd remove')
		else:
			self.Console.ePopen('update-rc.d -f sabnzbd defaults')
		time.sleep(3)
		self.updateService()

	def updateService(self, result=None, retval=None, extra_args=None):
		import process
		p = process.ProcessList()
		sabnzbd_process = str(p.named('SABnzbd.py')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_sabnzbd_active = False
		self.my_sabnzbd_run = False
		if ServiceIsEnabled('sabnzbd'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_sabnzbd_active = True
		if sabnzbd_process:
			self.my_sabnzbd_run = True
		if self.my_sabnzbd_run:
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("SABnzbd setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkFtp(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("FTP setup"))
		self.skinName = "NetworkServiceSetup"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self.Console = Console()
		self.my_ftp_active = False
		self.my_ftp_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'green': self.FtpStartStop, 'yellow': self.activateFtp})
		self.Console = Console()
		self.onLayoutFinish.append(self.updateService)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def FtpStartStop(self):
		commands = []
		if not fileExists('/etc/pam.d/vsftpd'):
			commands.append('mv /etc/pam.d/vsftpdd /etc/pam.d/vsftpd')
		if fileExists('/etc/pam.d/vsftpd'):
			commands.append('killall vsftpd ; mv /etc/pam.d/vsftpd /etc/pam.d/vsftpdd')
		self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def activateFtp(self):
		commands = []
		if fileExists('/etc/pam.d/vsftpd'):
			commands.append('mv /etc/pam.d/vsftpd /etc/pam.d/vsftpdd')
		else:
			commands.append('mv /etc/pam.d/vsftpdd /etc/pam.d/vsftpd')
		self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def updateService(self):
		import process
		p = process.ProcessList()
		ftp_process = str(p.named('vsftpd')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_ftp_active = False
		if fileExists('/etc/pam.d/vsftpd'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_ftp_active = True

		self.my_ftp_run = False
		if ftp_process:
			self.my_ftp_run = True
		if fileExists('/etc/pam.d/vsftpd'):
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("FTP setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkNfs(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("NFS setup"))
		self.skinName = "NetworkNfs"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_green'] = Label(_("Start"))
		self['key_red'] = Label(_("Remove service"))
		self['key_yellow'] = Label(_("Autostart"))
		self.Console = Console()
		self.my_nfs_active = False
		self.my_nfs_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.NfsStartStop, 'yellow': self.Nfsset})
		self.service_name = 'nfs-utils nfs-utils-client'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = True

	def createSummary(self):
		return NetworkServicesSummary

	def NfsStartStop(self):
		if not self.my_nfs_run:
			self.Console.ePopen('/etc/init.d/nfsserver start', self.StartStopCallback)
		elif self.my_nfs_run:
			self.Console.ePopen('/etc/init.d/nfsserver stop', self.StartStopCallback)

	def Nfsset(self):
		if ServiceIsEnabled('nfsserver'):
			self.Console.ePopen('update-rc.d -f nfsserver remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f nfsserver defaults 13', self.StartStopCallback)

	def updateService(self):
		import process
		p = process.ProcessList()
		nfs_process = str(p.named('nfsd')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_nfs_active = False
		self.my_nfs_run = False
		if ServiceIsEnabled('nfsserver'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_nfs_active = True
		if nfs_process:
			self.my_nfs_run = True
		if self.my_nfs_run:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("NFS setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkOpenvpn(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("OpenVPN setup"))
		self.skinName = "NetworkOpenvpn"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_green'] = Label(_("Start"))
		self['key_red'] = Label(_("Remove service"))
		self['key_yellow'] = Label(_("Autostart"))
		self['key_blue'] = Label(_("Show log"))
		self.Console = Console()
		self.my_vpn_active = False
		self.my_vpn_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.VpnStartStop, 'yellow': self.activateVpn, 'blue': self.Vpnshowlog})
		self.service_name = 'openvpn'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def Vpnshowlog(self):
		self.session.open(NetworkVpnLog)

	def VpnStartStop(self):
		if not self.my_vpn_run:
			self.Console.ePopen('/etc/init.d/openvpn start', self.StartStopCallback)
		elif self.my_vpn_run:
			self.Console.ePopen('/etc/init.d/openvpn stop', self.StartStopCallback)

	def StartStopCallback(self, result=None, retval=None, extra_args=None):
		openvpnfile = '0'
		if not os.path.exists('/etc/openvpn'):
			os.makedirs('/etc/openvpn')
		for file in os.listdir('/etc/openvpn'):
			if fnmatch.fnmatch(file, '*.conf'):
				print(file)
				openvpnfile = '1'

		if openvpnfile == '0':
			self.message = self.session.open(MessageBox, _("No config to start, please check /etc/openvpn/ and try again."), type=MessageBox.TYPE_INFO, close_on_any_key=True)
		else:
			print("[NetworkSetup] config in /etc/openvpn")

		time.sleep(3)
		self.updateService()

	def activateVpn(self):
		if ServiceIsEnabled('openvpn'):
			self.Console.ePopen('update-rc.d -f openvpn remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f openvpn defaults', self.StartStopCallback)

	def updateService(self):
		import process
		p = process.ProcessList()
		openvpn_process = str(p.named('openvpn')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_Vpn_active = False
		self.my_vpn_run = False
		if ServiceIsEnabled('openvpn'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_Vpn_active = True
		if openvpn_process:
			self.my_vpn_run = True
		if self.my_vpn_run:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("OpenVPN setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkVpnLog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("OpenVPN log"))
		self.skinName = "NetworkServiceLog"
		self['infotext'] = ScrollLabel('')
		self.Console = Console()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'up': self['infotext'].pageUp, 'down': self['infotext'].pageDown})
		strview = ''
		self.Console.ePopen('tail /var/log/messages > /var/log/openvpn.log')
		time.sleep(1)
		if fileExists('/var/log/openvpn.log'):
			f = open('/var/log/openvpn.log', 'r')
			for line in f.readlines():
				strview += line
			f.close()
			remove('/var/log/openvpn.log')
		self['infotext'].setText(strview)


class NetworkZeroTier(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("ZeroTier Setup"))
		self.skinName = "NetworkOpenvpn"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_green'] = Label(_("Start"))
		self['key_red'] = Label(_("Remove service"))
		self['key_yellow'] = Label(_("Autostart"))
		self['key_blue'] = Label(_("Show log"))
		self.Console = Console()
		self.my_zerotier_active = False
		self.my_zerotier_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.ZeroTierStartStop, 'yellow': self.activateZeroTier, 'blue': self.ZeroTiershowlog})
		self.service_name = 'zerotier'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def ZeroTiershowlog(self):
		self.session.open(NetworkZeroTierLog)

	def ZeroTierStartStop(self):
		commands = []
		if fileExists('/etc/init.d/zerotier'):
			if self.my_zerotier_run:
				commands.append('/etc/init.d/zerotier stop')
			else:
				commands.append('/etc/init.d/zerotier start')
			self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def activateZeroTier(self):
		if ServiceIsEnabled('zerotier'):
			self.Console.ePopen('update-rc.d -f zerotier remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f zerotier defaults', self.StartStopCallback)

	def updateService(self):
		import process
		p = process.ProcessList()
		zerotier_process = str(p.named('zerotier-one')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_zerotier_active = False
		if ServiceIsEnabled('zerotier'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_zerotier_active = True

		self.my_zerotier_run = False
		if zerotier_process:
			self.my_zerotier_run = True
		if self.my_zerotier_run:
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("ZeroTier setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkZeroTierLog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("ZeroTier log"))
		self.skinName = "NetworkServiceLog"
		self['infotext'] = ScrollLabel('')
		self.Console = Console()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'up': self['infotext'].pageUp, 'down': self['infotext'].pageDown})
		strview = ''
		self.Console.ePopen('tail /var/log/messages > /var/log/zerotier.log')
		time.sleep(1)
		if fileExists('/var/log/zerotier.log'):
			f = open('/var/log/zerotier.log', 'r')
			for line in f.readlines():
				strview += line
			f.close()
			remove('/var/log/zerotier.log')
		self['infotext'].setText(strview)


class NetworkSamba(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Samba setup"))
		self.skinName = "NetworkSamba"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_green'] = Label(_("Start"))
		self['key_red'] = Label(_("Remove service"))
		self['key_yellow'] = Label(_("Autostart"))
		self['key_blue'] = Label(_("Show log"))
		self.Console = Console()
		self.my_Samba_active = False
		self.my_Samba_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.SambaStartStop, 'yellow': self.activateSamba, 'blue': self.Sambashowlog})
		self.service_name = 'samba-base'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = True

	def createSummary(self):
		return NetworkServicesSummary

	def Sambashowlog(self):
		self.session.open(NetworkSambaLog)

	def SambaStartStop(self):
		commands = []
		if not self.my_Samba_run:
			commands.append('/etc/init.d/samba.sh start')
		elif self.my_Samba_run:
			commands.append('/etc/init.d/samba.sh stop')
			commands.append('killall nmbd')
			commands.append('killall smbd')
		self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def activateSamba(self):
		commands = []
		if fileExists('/etc/rc2.d/S20samba.sh'):
			commands.append('update-rc.d -f samba.sh remove')
		else:
			commands.append('update-rc.d -f samba.sh defaults')
		self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def updateService(self):
		import process
		p = process.ProcessList()
		samba_process = str(p.named('smbd')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_Samba_active = False
		if fileExists('/etc/rc2.d/S20samba.sh'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_Samba_active = True

		self.my_Samba_run = False
		if samba_process:
			self.my_Samba_run = True
		if self.my_Samba_run:
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("Samba setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkSambaLog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Samba log"))
		self.skinName = "NetworkServiceLog"
		self['infotext'] = ScrollLabel('')
		self.Console = Console()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'up': self['infotext'].pageUp, 'down': self['infotext'].pageDown})
		strview = ''
		self.Console.ePopen('tail /var/lib/samba/browse.dat* > /var/lib/samba/samba.log')
		time.sleep(1)
		if fileExists('/var/lib/samba/samba.log'):
			f = open('/var/lib/samba/samba.log', 'r')
			for line in f.readlines():
				strview += line
			f.close()
			remove('/var/lib/samba/samba.log')
		self['infotext'].setText(strview)


class NetworkTelnet(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Telnet setup"))
		self.skinName = "NetworkServiceSetup"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self.Console = Console()
		self.my_telnet_active = False
		self.my_telnet_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'green': self.TelnetStartStop, 'yellow': self.activateTelnet})
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def TelnetStartStop(self):
		commands = []
		if fileExists('/bin/busybox.nosuid'):
			if self.my_telnet_run:
				commands.append('killall telnetd ; rm -f /usr/sbin/telnetd')
			else:
				commands.append('ln -s /bin/busybox.nosuid /usr/sbin/telnetd')
			self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def activateTelnet(self):
		commands = []
		if fileExists('/usr/sbin/telnetd'):
			commands.append('rm -f /usr/sbin/telnetd')
		else:
			commands.append('ln -s /bin/busybox.nosuid /usr/sbin/telnetd')
		self.Console.eBatch(commands, self.StartStopCallback, debug=True)

	def updateService(self):
		import process
		p = process.ProcessList()
		telnet_process = str(p.named('telnetd')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_telnet_active = False
		self.my_telnet_run = False
		if fileExists('/usr/sbin/telnetd'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_telnet_active = True

		if fileExists('/usr/sbin/telnetd'):
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			self.my_telnet_run = True
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_green'].setText(_("Start"))
			self.my_telnet_run = False
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("Telnet setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)


class NetworkInadyn(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Inadyn setup"))
		self.onChangedEntry = []
		self['autostart'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Active")))
		self['labdisabled'] = Label(_(_("Disabled")))
		self['status'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['time'] = Label(_("Time update in minutes:"))
		self['labtime'] = Label()
		self['username'] = Label(_("Username") + ":")
		self['labuser'] = Label()
		self['password'] = Label(_("Password") + ":")
		self['labpass'] = Label()
		self['alias'] = Label(_("Alias") + ":")
		self['labalias'] = Label()
		self['sactive'] = Pixmap()
		self['sinactive'] = Pixmap()
		self['system'] = Label(_("System") + ":")
		self['labsys'] = Label()
		self['key_red'] = Label(_("Remove service"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self['key_blue'] = Label(_("Show log"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'SetupActions'], {'ok': self.setupinadyn, 'back': self.close, 'menu': self.setupinadyn, 'red': self.UninstallCheck, 'green': self.InadynStartStop, 'yellow': self.autostart, 'blue': self.inaLog})
		self.Console = Console()
		self.service_name = 'inadyn-mt'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def InadynStartStop(self):
		if not self.my_inadyn_run:
			self.Console.ePopen('/etc/init.d/inadyn-mt start', self.StartStopCallback)
		elif self.my_inadyn_run:
			self.Console.ePopen('/etc/init.d/inadyn-mt stop', self.StartStopCallback)

	def autostart(self):
		if ServiceIsEnabled('inadyn-mt'):
			self.Console.ePopen('update-rc.d -f inadyn-mt remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f inadyn-mt defaults', self.StartStopCallback)

	def updateService(self):
		import process
		p = process.ProcessList()
		inadyn_process = str(p.named('inadyn-mt')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].hide()
		self['labdisabled'].hide()
		self['sactive'].hide()
		self.my_inadyn_active = False
		self.my_inadyn_run = False
		if ServiceIsEnabled('inadyn-mt'):
			self['labdisabled'].hide()
			self['labactive'].show()
			self.my_inadyn_active = True
			autostartstatus_summary = self['autostart'].text + ' ' + self['labactive'].text
		else:
			self['labactive'].hide()
			self['labdisabled'].show()
			autostartstatus_summary = self['autostart'].text + ' ' + self['labdisabled'].text
		if inadyn_process:
			self.my_inadyn_run = True
		if self.my_inadyn_run:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['status'].text + ' ' + self['labrun'].text
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_green'].setText(_("Start"))
			status_summary = self['status'].text + ' ' + self['labstop'].text

		if fileExists('/etc/inadyn.conf'):
			f = open('/etc/inadyn.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('username '):
					line = line[9:]
					self['labuser'].setText(line)
				elif line.startswith('password '):
					line = line[9:]
					self['labpass'].setText(line)
				elif line.startswith('alias '):
					line = line[6:]
					self['labalias'].setText(line)
				elif line.startswith('update_period_sec '):
					line = line[18:]
					line = (int(line) / 60)
					self['labtime'].setText(str(line))
				elif line.startswith('dyndns_system ') or line.startswith('#dyndns_system '):
					if line.startswith('#'):
						line = line[15:]
						self['sactive'].hide()
					else:
						line = line[14:]
						self['sactive'].show()
					self['labsys'].setText(line)
			f.close()
		title = _("Inadyn setup")

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)

	def setupinadyn(self):
		self.session.openWithCallback(self.updateService, NetworkInadynSetup)

	def inaLog(self):
		self.session.open(NetworkInadynLog)


class NetworkInadynSetup(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.selectionChanged)
		Screen.setTitle(self, _("Inadyn setup"))
		self['key_red'] = Label(_("Save"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'VirtualKeyboardActions'], {'red': self.saveIna, 'back': self.close, 'showVirtualKeyboard': self.KeyText})
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self.updateList()
		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["config"].getCurrent()
		if item:
			name = str(item[0])
			desc = str(item[1].value)
		else:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def updateList(self):
		self.ina_user = NoSave(ConfigText(fixed_size=False))
		self.ina_pass = NoSave(ConfigText(fixed_size=False))
		self.ina_alias = NoSave(ConfigText(fixed_size=False))
		self.ina_period = NoSave(ConfigNumber())
		self.ina_sysactive = NoSave(ConfigYesNo(default='False'))
		self.ina_system = NoSave(ConfigSelection(default="dyndns@dyndns.org", choices=[("dyndns@dyndns.org", "dyndns@dyndns.org"), ("statdns@dyndns.org", "statdns@dyndns.org"), ("custom@dyndns.org", "custom@dyndns.org"), ("default@no-ip.com", "default@no-ip.com")]))

		if fileExists('/etc/inadyn.conf'):
			f = open('/etc/inadyn.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('username '):
					line = line[9:]
					self.ina_user.value = line
					ina_user1 = getConfigListEntry(_("Username") + ":", self.ina_user)
					self.list.append(ina_user1)
				elif line.startswith('password '):
					line = line[9:]
					self.ina_pass.value = line
					ina_pass1 = getConfigListEntry(_("Password") + ":", self.ina_pass)
					self.list.append(ina_pass1)
				elif line.startswith('alias '):
					line = line[6:]
					self.ina_alias.value = line
					ina_alias1 = getConfigListEntry(_("Alias") + ":", self.ina_alias)
					self.list.append(ina_alias1)
				elif line.startswith('update_period_sec '):
					line = line[18:]
					line = (int(line) / 60)
					self.ina_period.value = line
					ina_period1 = getConfigListEntry(_("Time update in minutes") + ":", self.ina_period)
					self.list.append(ina_period1)
				elif line.startswith('dyndns_system ') or line.startswith('#dyndns_system '):
					if not line.startswith('#'):
						self.ina_sysactive.value = True
						line = line[14:]
					else:
						self.ina_sysactive.value = False
						line = line[15:]
					ina_sysactive1 = getConfigListEntry(_("Set system") + ":", self.ina_sysactive)
					self.list.append(ina_sysactive1)
					self.ina_value = line
					ina_system1 = getConfigListEntry(_("System") + ":", self.ina_system)
					self.list.append(ina_system1)

			f.close()
		self['config'].list = self.list
		self['config'].l.setList(self.list)

	def KeyText(self):
		sel = self['config'].getCurrent()
		if sel:
			if isinstance(self["config"].getCurrent()[1], ConfigText) or isinstance(self["config"].getCurrent()[1], ConfigPassword):
				if self["config"].getCurrent()[1].help_window.instance is not None:
					self["config"].getCurrent()[1].help_window.hide()
			self.vkvar = sel[0]
			if self.vkvar == _("Username") + ':' or self.vkvar == _("Password") + ':' or self.vkvar == _("Alias") + ':' or self.vkvar == _("System") + ':':
				from Screens.VirtualKeyBoard import VirtualKeyBoard
				self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title=self["config"].getCurrent()[0], text=self["config"].getCurrent()[1].value)

	def VirtualKeyBoardCallback(self, callback=None):
		if callback is not None and len(callback):
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

	def saveIna(self):
		if fileExists('/etc/inadyn.conf'):
			inme = open('/etc/inadyn.conf', 'r')
			out = open('/etc/inadyn.conf.tmp', 'w')
			for line in inme.readlines():
				line = line.replace('\n', '')
				if line.startswith('username '):
					line = ('username ' + self.ina_user.value.strip())
				elif line.startswith('password '):
					line = ('password ' + self.ina_pass.value.strip())
				elif line.startswith('alias '):
					line = ('alias ' + self.ina_alias.value.strip())
				elif line.startswith('update_period_sec '):
					strview = (self.ina_period.value * 60)
					strview = str(strview)
					line = ('update_period_sec ' + strview)
				elif line.startswith('dyndns_system ') or line.startswith('#dyndns_system '):
					if self.ina_sysactive.value:
						line = ('dyndns_system ' + self.ina_system.value.strip())
					else:
						line = ('#dyndns_system ' + self.ina_system.value.strip())
				out.write((line + '\n'))
			out.close()
			inme.close()
		else:
			self.session.open(MessageBox, _("Inadyn config is missing!"), MessageBox.TYPE_INFO)
			self.close()
		if fileExists('/etc/inadyn.conf.tmp'):
			rename('/etc/inadyn.conf.tmp', '/etc/inadyn.conf')
		self.myStop()

	def myStop(self):
		self.close()


class NetworkInadynLog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Inadyn log"))
		self.skinName = "NetworkServiceLog"
		self['infotext'] = ScrollLabel('')
		self['actions'] = ActionMap(['WizardActions', 'DirectionActions', 'ColorActions'], {'ok': self.close,
		 'back': self.close,
		 'up': self['infotext'].pageUp,
		 'down': self['infotext'].pageDown})
		strview = ''
		if fileExists('/tmp/inadyn_ip.cache'):
			f = open('/tmp/inadyn_ip.cache', 'r')
			for line in f.readlines():
				strview += line
			else:
				if fileExists('/tmp/inadyn.log'):
					f = open('/tmp/inadyn.log', 'r')
					for line in f.readlines():
						strview += line
			f.close()
		self['infotext'].setText(strview)


config.networkushare = ConfigSubsection()
config.networkushare.mediafolders = NoSave(ConfigLocations(default=""))


class NetworkuShare(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("uShare setup"))
		self.onChangedEntry = []
		self['autostart'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Active")))
		self['labdisabled'] = Label(_(_("Disabled")))
		self['status'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['username'] = Label(_("uShare name") + ":")
		self['labuser'] = Label()
		self['iface'] = Label(_("Interface") + ":")
		self['labiface'] = Label()
		self['port'] = Label(_("uShare port") + ":")
		self['labport'] = Label()
		self['telnetport'] = Label(_("Telnet port") + ":")
		self['labtelnetport'] = Label()
		self['sharedir'] = Label(_("Share folder") + ":")
		self['labsharedir'] = Label()
		self['web'] = Label(_("Web interface") + ":")
		self['webactive'] = Pixmap()
		self['webinactive'] = Pixmap()
		self['telnet'] = Label(_("Telnet interface") + ":")
		self['telnetactive'] = Pixmap()
		self['telnetinactive'] = Pixmap()
		self['xbox'] = Label(_("XBox support") + ":")
		self['xboxactive'] = Pixmap()
		self['xboxinactive'] = Pixmap()
		self['dlna'] = Label(_("DLNA support") + ":")
		self['dlnaactive'] = Pixmap()
		self['dlnainactive'] = Pixmap()

		self['key_red'] = Label(_("Remove service"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self['key_blue'] = Label(_("Show log"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'SetupActions'], {'ok': self.setupushare, 'back': self.close, 'menu': self.setupushare, 'red': self.UninstallCheck, 'green': self.uShareStartStop, 'yellow': self.autostart, 'blue': self.ushareLog})
		self.Console = Console()
		self.service_name = 'ushare'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def uShareStartStop(self):
		if not self.my_ushare_run:
			self.Console.ePopen('/etc/init.d/ushare start >> /tmp/uShare.log', self.StartStopCallback)
		elif self.my_ushare_run:
			self.Console.ePopen('/etc/init.d/ushare stop >> /tmp/uShare.log', self.StartStopCallback)

	def autostart(self):
		if ServiceIsEnabled('ushare'):
			self.Console.ePopen('update-rc.d -f ushare remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f ushare defaults', self.StartStopCallback)

	def updateService(self):
		import process
		p = process.ProcessList()
		ushare_process = str(p.named('ushare')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].hide()
		self['labdisabled'].hide()
		self.my_ushare_active = False
		self.my_ushare_run = False
		if not fileExists('/tmp/uShare.log'):
			open("/tmp/uShare.log", "w").write("")
		if ServiceIsEnabled('ushare'):
			self['labdisabled'].hide()
			self['labactive'].show()
			self.my_ushare_active = True
			autostartstatus_summary = self['autostart'].text + ' ' + self['labactive'].text
		else:
			self['labactive'].hide()
			self['labdisabled'].show()
			autostartstatus_summary = self['autostart'].text + ' ' + self['labdisabled'].text
		if ushare_process:
			self.my_ushare_run = True
		if self.my_ushare_run:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['status'].text + ' ' + self['labstop'].text
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_green'].setText(_("Start"))
			status_summary = self['status'].text + ' ' + self['labstop'].text

		if fileExists('/etc/ushare.conf'):
			f = open('/etc/ushare.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('USHARE_NAME='):
					line = line[12:]
					self['labuser'].setText(line)
				elif line.startswith('USHARE_IFACE='):
					line = line[13:]
					self['labiface'].setText(line)
				elif line.startswith('USHARE_PORT='):
					line = line[12:]
					self['labport'].setText(line)
				elif line.startswith('USHARE_TELNET_PORT='):
					line = line[19:]
					self['labtelnetport'].setText(line)
				elif line.startswith('USHARE_DIR='):
					line = line[11:]
					self.mediafolders = line
					self['labsharedir'].setText(line)
				elif line.startswith('ENABLE_WEB='):
					if line[11:] == 'no':
						self['webactive'].hide()
						self['webinactive'].show()
					else:
						self['webactive'].show()
						self['webinactive'].hide()
				elif line.startswith('ENABLE_TELNET='):
					if line[14:] == 'no':
						self['telnetactive'].hide()
						self['telnetinactive'].show()
					else:
						self['telnetactive'].show()
						self['telnetinactive'].hide()
				elif line.startswith('ENABLE_XBOX='):
					if line[12:] == 'no':
						self['xboxactive'].hide()
						self['xboxinactive'].show()
					else:
						self['xboxactive'].show()
						self['xboxinactive'].hide()
				elif line.startswith('ENABLE_DLNA='):
					if line[12:] == 'no':
						self['dlnaactive'].hide()
						self['dlnainactive'].show()
					else:
						self['dlnaactive'].show()
						self['dlnainactive'].hide()
			f.close()
		title = _("uShare setup")

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)

	def setupushare(self):
		self.session.openWithCallback(self.updateService, NetworkuShareSetup)

	def ushareLog(self):
		self.session.open(NetworkuShareLog)


class NetworkuShareSetup(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("uShare setup"))
		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.selectionChanged)
		Screen.setTitle(self, _("uShare setup"))
		self['key_red'] = Label(_("Save"))
		self['key_green'] = Label(_("Shares"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'VirtualKeyboardActions'], {'red': self.saveuShare, 'green': self.selectfolders, 'back': self.close, 'showVirtualKeyboard': self.KeyText})
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self.updateList()
		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["config"].getCurrent()
		if item:
			name = str(item[0])
			desc = str(item[1].value)
		else:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def updateList(self, ret=None):
		self.list = []
		self.ushare_user = NoSave(ConfigText(default=model, fixed_size=False))
		self.ushare_iface = NoSave(ConfigText(fixed_size=False))
		self.ushare_port = NoSave(ConfigNumber())
		self.ushare_telnetport = NoSave(ConfigNumber())
		self.ushare_web = NoSave(ConfigYesNo(default='True'))
		self.ushare_telnet = NoSave(ConfigYesNo(default='True'))
		self.ushare_xbox = NoSave(ConfigYesNo(default='True'))
		self.ushare_ps3 = NoSave(ConfigYesNo(default='True'))
		self.ushare_system = NoSave(ConfigSelection(default="dyndns@dyndns.org", choices=[("dyndns@dyndns.org", "dyndns@dyndns.org"), ("statdns@dyndns.org", "statdns@dyndns.org"), ("custom@dyndns.org", "custom@dyndns.org")]))

		if fileExists('/etc/ushare.conf'):
			f = open('/etc/ushare.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('USHARE_NAME='):
					line = line[12:]
					self.ushare_user.value = line
					ushare_user1 = getConfigListEntry(_("uShare name") + ":", self.ushare_user)
					self.list.append(ushare_user1)
				elif line.startswith('USHARE_IFACE='):
					line = line[13:]
					self.ushare_iface.value = line
					ushare_iface1 = getConfigListEntry(_("Interface") + ":", self.ushare_iface)
					self.list.append(ushare_iface1)
				elif line.startswith('USHARE_PORT='):
					line = line[12:]
					self.ushare_port.value = line
					ushare_port1 = getConfigListEntry(_("uShare port") + ":", self.ushare_port)
					self.list.append(ushare_port1)
				elif line.startswith('USHARE_TELNET_PORT='):
					line = line[19:]
					self.ushare_telnetport.value = line
					ushare_telnetport1 = getConfigListEntry(_("Telnet port") + ":", self.ushare_telnetport)
					self.list.append(ushare_telnetport1)
				elif line.startswith('ENABLE_WEB='):
					if line[11:] == 'no':
						self.ushare_web.value = False
					else:
						self.ushare_web.value = True
					ushare_web1 = getConfigListEntry(_("Web interface") + ":", self.ushare_web)
					self.list.append(ushare_web1)
				elif line.startswith('ENABLE_TELNET='):
					if line[14:] == 'no':
						self.ushare_telnet.value = False
					else:
						self.ushare_telnet.value = True
					ushare_telnet1 = getConfigListEntry(_("Telnet interface") + ":", self.ushare_telnet)
					self.list.append(ushare_telnet1)
				elif line.startswith('ENABLE_XBOX='):
					if line[12:] == 'no':
						self.ushare_xbox.value = False
					else:
						self.ushare_xbox.value = True
					ushare_xbox1 = getConfigListEntry(_("XBox support") + ":", self.ushare_xbox)
					self.list.append(ushare_xbox1)
				elif line.startswith('ENABLE_DLNA='):
					if line[12:] == 'no':
						self.ushare_ps3.value = False
					else:
						self.ushare_ps3.value = True
					ushare_ps31 = getConfigListEntry(_("DLNA support") + ":", self.ushare_ps3)
					self.list.append(ushare_ps31)
			f.close()
		self['config'].list = self.list
		self['config'].l.setList(self.list)

	def KeyText(self):
		sel = self['config'].getCurrent()
		if sel:
			if isinstance(self["config"].getCurrent()[1], ConfigText) or isinstance(self["config"].getCurrent()[1], ConfigPassword):
				if self["config"].getCurrent()[1].help_window.instance is not None:
					self["config"].getCurrent()[1].help_window.hide()
			self.vkvar = sel[0]
			if self.vkvar == _("uShare name") + ":" or self.vkvar == _("Share folder") + ":":
				from Screens.VirtualKeyBoard import VirtualKeyBoard
				self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title=self["config"].getCurrent()[0], text=self["config"].getCurrent()[1].value)

	def VirtualKeyBoardCallback(self, callback=None):
		if callback is not None and len(callback):
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

	def saveuShare(self):
		if fileExists('/etc/ushare.conf'):
			inme = open('/etc/ushare.conf', 'r')
			out = open('/etc/ushare.conf.tmp', 'w')
			for line in inme.readlines():
				line = line.replace('\n', '')
				if line.startswith('USHARE_NAME='):
					line = ('USHARE_NAME=' + self.ushare_user.value.strip())
				elif line.startswith('USHARE_IFACE='):
					line = ('USHARE_IFACE=' + self.ushare_iface.value.strip())
				elif line.startswith('USHARE_PORT='):
					line = ('USHARE_PORT=' + str(self.ushare_port.value))
				elif line.startswith('USHARE_TELNET_PORT='):
					line = ('USHARE_TELNET_PORT=' + str(self.ushare_telnetport.value))
				elif line.startswith('USHARE_DIR='):
					line = ('USHARE_DIR=' + ', '.join(config.networkushare.mediafolders.value))
				elif line.startswith('ENABLE_WEB='):
					if not self.ushare_web.value:
						line = 'ENABLE_WEB=no'
					else:
						line = 'ENABLE_WEB=yes'
				elif line.startswith('ENABLE_TELNET='):
					if not self.ushare_telnet.value:
						line = 'ENABLE_TELNET=no'
					else:
						line = 'ENABLE_TELNET=yes'
				elif line.startswith('ENABLE_XBOX='):
					if not self.ushare_xbox.value:
						line = 'ENABLE_XBOX=no'
					else:
						line = 'ENABLE_XBOX=yes'
				elif line.startswith('ENABLE_DLNA='):
					if not self.ushare_ps3.value:
						line = 'ENABLE_DLNA=no'
					else:
						line = 'ENABLE_DLNA=yes'
				out.write((line + '\n'))
			out.close()
			inme.close()
		else:
			open('/tmp/uShare.log', "a").write(_("uShare config is missing!") + '\n')
			self.session.open(MessageBox, _("uShare config is missing!"), MessageBox.TYPE_INFO)
			self.close()
		if fileExists('/etc/ushare.conf.tmp'):
			rename('/etc/ushare.conf.tmp', '/etc/ushare.conf')
		self.myStop()

	def myStop(self):
		self.close()

	def selectfolders(self):
		try:
			self["config"].getCurrent()[1].help_window.hide()
		except:
			pass
		self.session.openWithCallback(self.updateList, uShareSelection)


class uShareSelection(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Select folders"))
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText()

		if fileExists('/etc/ushare.conf'):
			f = open('/etc/ushare.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('USHARE_DIR='):
					line = line[11:]
					self.mediafolders = line
		self.selectedFiles = [str(n) for n in self.mediafolders.split(', ')]
		defaultDir = '/media/'
		self.filelist = MultiFileSelectList(self.selectedFiles, defaultDir, showFiles=False)
		self["checkList"] = self.filelist

		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ShortcutActions"],
		{
			"cancel": self.exit,
			"red": self.exit,
			"yellow": self.changeSelectionState,
			"green": self.saveSelection,
			"ok": self.okClicked,
			"left": self.left,
			"right": self.right,
			"down": self.down,
			"up": self.up
		}, -1)
		if not self.selectionChanged in self["checkList"].onSelectionChanged:
			self["checkList"].onSelectionChanged.append(self.selectionChanged)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		idx = 0
		self["checkList"].moveToIndex(idx)
		self.selectionChanged()

	def selectionChanged(self):
		current = self["checkList"].getCurrent()[0]
		if current[2] is True:
			self["key_yellow"].setText(_("Deselect"))
		else:
			self["key_yellow"].setText(_("Select"))

	def up(self):
		self["checkList"].up()

	def down(self):
		self["checkList"].down()

	def left(self):
		self["checkList"].pageUp()

	def right(self):
		self["checkList"].pageDown()

	def changeSelectionState(self):
		self["checkList"].changeSelectionState()
		self.selectedFiles = self["checkList"].getSelectedList()

	def saveSelection(self):
		self.selectedFiles = self["checkList"].getSelectedList()
		config.networkushare.mediafolders.value = self.selectedFiles
		self.close(None)

	def exit(self):
		self.close(None)

	def okClicked(self):
		if self.filelist.canDescent():
			self.filelist.descent()


class NetworkuShareLog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NetworkServiceLog"
		Screen.setTitle(self, _("uShare log"))
		self['infotext'] = ScrollLabel('')
		self.Console = Console()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'up': self['infotext'].pageUp, 'down': self['infotext'].pageDown})
		strview = ''
		self.Console.ePopen('tail /tmp/uShare.log > /tmp/tmp.log')
		time.sleep(1)
		if fileExists('/tmp/tmp.log'):
			f = open('/tmp/tmp.log', 'r')
			for line in f.readlines():
				strview += line
			f.close()
			remove('/tmp/tmp.log')
		self['infotext'].setText(strview)


config.networkminidlna = ConfigSubsection()
config.networkminidlna.mediafolders = NoSave(ConfigLocations(default=""))


class NetworkMiniDLNA(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("MiniDLNA setup"))
		self.onChangedEntry = []
		self['autostart'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Active")))
		self['labdisabled'] = Label(_(_("Disabled")))
		self['status'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['username'] = Label(_("Name") + ":")
		self['labuser'] = Label()
		self['iface'] = Label(_("Interface") + ":")
		self['labiface'] = Label()
		self['port'] = Label(_("Port") + ":")
		self['labport'] = Label()
		self['serialno'] = Label(_("Serial") + ":")
		self['labserialno'] = Label()
		self['sharedir'] = Label(_("Share folder") + ":")
		self['labsharedir'] = Label()
		self['inotify'] = Label(_("Inotify monitoring") + ":")
		self['inotifyactive'] = Pixmap()
		self['inotifyinactive'] = Pixmap()
		self['tivo'] = Label(_("TiVo support") + ":")
		self['tivoactive'] = Pixmap()
		self['tivoinactive'] = Pixmap()
		self['dlna'] = Label(_("Strict DLNA") + ":")
		self['dlnaactive'] = Pixmap()
		self['dlnainactive'] = Pixmap()

		self['key_red'] = Label(_("Remove service"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Autostart"))
		self['key_blue'] = Label(_("Show log"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'SetupActions'], {'ok': self.setupminidlna, 'back': self.close, 'menu': self.setupminidlna, 'red': self.UninstallCheck, 'green': self.MiniDLNAStartStop, 'yellow': self.autostart, 'blue': self.minidlnaLog})
		self.Console = Console()
		self.service_name = 'minidlna'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = False

	def createSummary(self):
		return NetworkServicesSummary

	def MiniDLNAStartStop(self):
		if not self.my_minidlna_run:
			self.Console.ePopen('/etc/init.d/minidlna.sh start', self.StartStopCallback)
		elif self.my_minidlna_run:
			self.Console.ePopen('/etc/init.d/minidlna.sh stop', self.StartStopCallback)

	def autostart(self):
		if self.my_minidlna_active:
			self.Console.ePopen('update-rc.d -f minidlna.sh remove', self.StartStopCallback)
		else:
			self.Console.ePopen('update-rc.d -f minidlna.sh remove ; update-rc.d -f minidlna.sh defaults', self.StartStopCallback)

	def updateService(self):
		import process
		p = process.ProcessList()
		minidlna_process = str(p.named('minidlnad')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].hide()
		self['labdisabled'].hide()
		self.my_minidlna_active = False
		self.my_minidlna_run = False
		if fileExists('/etc/rc2.d/S20minidlna.sh'):
			self['labdisabled'].hide()
			self['labactive'].show()
			self.my_minidlna_active = True
			autostartstatus_summary = self['autostart'].text + ' ' + self['labactive'].text
		else:
			self['labactive'].hide()
			self['labdisabled'].show()
			autostartstatus_summary = self['autostart'].text + ' ' + self['labdisabled'].text
		if minidlna_process:
			self.my_minidlna_run = True
		if self.my_minidlna_run:
			self['labstop'].hide()
			self['labrun'].show()
			self['key_green'].setText(_("Stop"))
			status_summary = self['status'].text + ' ' + self['labstop'].text
		else:
			self['labstop'].show()
			self['labrun'].hide()
			self['key_green'].setText(_("Start"))
			status_summary = self['status'].text + ' ' + self['labstop'].text

		if fileExists('/etc/minidlna.conf'):
			f = open('/etc/minidlna.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('friendly_name='):
					line = line[14:]
					self['labuser'].setText(line)
				elif line.startswith('network_interface='):
					line = line[18:]
					self['labiface'].setText(line)
				elif line.startswith('port='):
					line = line[5:]
					self['labport'].setText(line)
				elif line.startswith('serial='):
					line = line[7:]
					self['labserialno'].setText(line)
				elif line.startswith('media_dir='):
					line = line[10:]
					self.mediafolders = line
					self['labsharedir'].setText(line)
				elif line.startswith('inotify='):
					if line[8:] == 'no':
						self['inotifyactive'].hide()
						self['inotifyinactive'].show()
					else:
						self['inotifyactive'].show()
						self['inotifyinactive'].hide()
				elif line.startswith('enable_tivo='):
					if line[12:] == 'no':
						self['tivoactive'].hide()
						self['tivoinactive'].show()
					else:
						self['tivoactive'].show()
						self['tivoinactive'].hide()
				elif line.startswith('strict_dlna='):
					if line[12:] == 'no':
						self['dlnaactive'].hide()
						self['dlnainactive'].show()
					else:
						self['dlnaactive'].show()
						self['dlnainactive'].hide()
			f.close()
		title = _("MiniDLNA setup")

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)

	def setupminidlna(self):
		self.session.openWithCallback(self.updateService, NetworkMiniDLNASetup)

	def minidlnaLog(self):
		self.session.open(NetworkMiniDLNALog)


class NetworkMiniDLNASetup(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("MiniDLNA setup"))
		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.selectionChanged)
		Screen.setTitle(self, _("MiniDLNA setup"))
		self.skinName = "NetworkuShareSetup"
		self['key_red'] = Label(_("Save"))
		self['key_green'] = Label(_("Shares"))
		self['actions'] = ActionMap(['WizardActions', 'ColorActions', 'VirtualKeyboardActions'], {'red': self.saveMinidlna, 'green': self.selectfolders, 'back': self.close, 'showVirtualKeyboard': self.KeyText})
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self.updateList()
		if not self.selectionChanged in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)

	def createSummary(self):
		from Screens.PluginBrowser import PluginBrowserSummary
		return PluginBrowserSummary

	def selectionChanged(self):
		item = self["config"].getCurrent()
		if item:
			name = str(item[0])
			desc = str(item[1].value)
		else:
			name = ""
			desc = ""
		for cb in self.onChangedEntry:
			cb(name, desc)

	def updateList(self, ret=None):
		self.list = []
		self.minidlna_name = NoSave(ConfigText(default=model, fixed_size=False))
		self.minidlna_iface = NoSave(ConfigText(fixed_size=False))
		self.minidlna_port = NoSave(ConfigNumber())
		self.minidlna_serialno = NoSave(ConfigNumber())
		self.minidlna_web = NoSave(ConfigYesNo(default='True'))
		self.minidlna_inotify = NoSave(ConfigYesNo(default='True'))
		self.minidlna_tivo = NoSave(ConfigYesNo(default='True'))
		self.minidlna_strictdlna = NoSave(ConfigYesNo(default='True'))

		if fileExists('/etc/minidlna.conf'):
			f = open('/etc/minidlna.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('friendly_name='):
					line = line[14:]
					self.minidlna_name.value = line
					minidlna_name1 = getConfigListEntry(_("Name") + ":", self.minidlna_name)
					self.list.append(minidlna_name1)
				elif line.startswith('network_interface='):
					line = line[18:]
					self.minidlna_iface.value = line
					minidlna_iface1 = getConfigListEntry(_("Interface") + ":", self.minidlna_iface)
					self.list.append(minidlna_iface1)
				elif line.startswith('port='):
					line = line[5:]
					self.minidlna_port.value = line
					minidlna_port1 = getConfigListEntry(_("Port") + ":", self.minidlna_port)
					self.list.append(minidlna_port1)
				elif line.startswith('serial='):
					line = line[7:]
					self.minidlna_serialno.value = line
					minidlna_serialno1 = getConfigListEntry(_("Serial") + ":", self.minidlna_serialno)
					self.list.append(minidlna_serialno1)
				elif line.startswith('inotify='):
					if line[8:] == 'no':
						self.minidlna_inotify.value = False
					else:
						self.minidlna_inotify.value = True
					minidlna_inotify1 = getConfigListEntry(_("Inotify monitoring") + ":", self.minidlna_inotify)
					self.list.append(minidlna_inotify1)
				elif line.startswith('enable_tivo='):
					if line[12:] == 'no':
						self.minidlna_tivo.value = False
					else:
						self.minidlna_tivo.value = True
					minidlna_tivo1 = getConfigListEntry(_("TiVo support") + ":", self.minidlna_tivo)
					self.list.append(minidlna_tivo1)
				elif line.startswith('strict_dlna='):
					if line[12:] == 'no':
						self.minidlna_strictdlna.value = False
					else:
						self.minidlna_strictdlna.value = True
					minidlna_strictdlna1 = getConfigListEntry(_("Strict DLNA") + ":", self.minidlna_strictdlna)
					self.list.append(minidlna_strictdlna1)
			f.close()
		self['config'].list = self.list
		self['config'].l.setList(self.list)

	def KeyText(self):
		sel = self['config'].getCurrent()
		if sel:
			if isinstance(self["config"].getCurrent()[1], ConfigText) or isinstance(self["config"].getCurrent()[1], ConfigPassword):
				if self["config"].getCurrent()[1].help_window.instance is not None:
					self["config"].getCurrent()[1].help_window.hide()
			self.vkvar = sel[0]
			if self.vkvar == _("Name") + ":" or self.vkvar == _("Share folder") + ":":
				from Screens.VirtualKeyBoard import VirtualKeyBoard
				self.session.openWithCallback(self.VirtualKeyBoardCallback, VirtualKeyBoard, title=self["config"].getCurrent()[0], text=self["config"].getCurrent()[1].value)

	def VirtualKeyBoardCallback(self, callback=None):
		if callback is not None and len(callback):
			self["config"].getCurrent()[1].setValue(callback)
			self["config"].invalidate(self["config"].getCurrent())

	def saveMinidlna(self):
		if fileExists('/etc/minidlna.conf'):
			inme = open('/etc/minidlna.conf', 'r')
			out = open('/etc/minidlna.conf.tmp', 'w')
			for line in inme.readlines():
				line = line.replace('\n', '')
				if line.startswith('friendly_name='):
					line = ('friendly_name=' + self.minidlna_name.value.strip())
				elif line.startswith('network_interface='):
					line = ('network_interface=' + self.minidlna_iface.value.strip())
				elif line.startswith('port='):
					line = ('port=' + str(self.minidlna_port.value))
				elif line.startswith('serial='):
					line = ('serial=' + str(self.minidlna_serialno.value))
				elif line.startswith('media_dir='):
					line = ('media_dir=' + ', '.join(config.networkminidlna.mediafolders.value))
				elif line.startswith('inotify='):
					if not self.minidlna_inotify.value:
						line = 'inotify=no'
					else:
						line = 'inotify=yes'
				elif line.startswith('enable_tivo='):
					if not self.minidlna_tivo.value:
						line = 'enable_tivo=no'
					else:
						line = 'enable_tivo=yes'
				elif line.startswith('strict_dlna='):
					if not self.minidlna_strictdlna.value:
						line = 'strict_dlna=no'
					else:
						line = 'strict_dlna=yes'
				out.write((line + '\n'))
			out.close()
			inme.close()
		else:
			self.session.open(MessageBox, _("MiniDLNA config is missing!"), MessageBox.TYPE_INFO)
			self.close()
		if fileExists('/etc/minidlna.conf.tmp'):
			rename('/etc/minidlna.conf.tmp', '/etc/minidlna.conf')
		self.myStop()

	def myStop(self):
		self.close()

	def selectfolders(self):
		try:
			self["config"].getCurrent()[1].help_window.hide()
		except:
			pass
		self.session.openWithCallback(self.updateList, MiniDLNASelection)


class MiniDLNASelection(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("Select folders"))
		self.skinName = "uShareSelection"
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText()

		if fileExists('/etc/minidlna.conf'):
			f = open('/etc/minidlna.conf', 'r')
			for line in f.readlines():
				line = line.strip()
				if line.startswith('media_dir='):
					line = line[11:]
					self.mediafolders = line
		self.selectedFiles = [str(n) for n in self.mediafolders.split(', ')]
		defaultDir = '/media/'
		self.filelist = MultiFileSelectList(self.selectedFiles, defaultDir, showFiles=False)
		self["checkList"] = self.filelist

		self["actions"] = ActionMap(["DirectionActions", "OkCancelActions", "ShortcutActions"],
		{
			"cancel": self.exit,
			"red": self.exit,
			"yellow": self.changeSelectionState,
			"green": self.saveSelection,
			"ok": self.okClicked,
			"left": self.left,
			"right": self.right,
			"down": self.down,
			"up": self.up
		}, -1)
		if not self.selectionChanged in self["checkList"].onSelectionChanged:
			self["checkList"].onSelectionChanged.append(self.selectionChanged)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		idx = 0
		self["checkList"].moveToIndex(idx)
		self.selectionChanged()

	def selectionChanged(self):
		current = self["checkList"].getCurrent()[0]
		if current[2] is True:
			self["key_yellow"].setText(_("Deselect"))
		else:
			self["key_yellow"].setText(_("Select"))

	def up(self):
		self["checkList"].up()

	def down(self):
		self["checkList"].down()

	def left(self):
		self["checkList"].pageUp()

	def right(self):
		self["checkList"].pageDown()

	def changeSelectionState(self):
		self["checkList"].changeSelectionState()
		self.selectedFiles = self["checkList"].getSelectedList()

	def saveSelection(self):
		self.selectedFiles = self["checkList"].getSelectedList()
		config.networkminidlna.mediafolders.value = self.selectedFiles
		self.close(None)

	def exit(self):
		self.close(None)

	def okClicked(self):
		if self.filelist.canDescent():
			self.filelist.descent()


class NetworkMiniDLNALog(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NetworkServiceLog"
		Screen.setTitle(self, _("MiniDLNA log"))
		self['infotext'] = ScrollLabel('')
		self.Console = Console()
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'up': self['infotext'].pageUp, 'down': self['infotext'].pageDown})
		strview = ''
		self.Console.ePopen('tail /var/volatile/tmp/minidlna.log > /tmp/tmp.log')
		time.sleep(1)
		if fileExists('/tmp/tmp.log'):
			f = open('/tmp/tmp.log', 'r')
			for line in f.readlines():
				strview += line
			f.close()
			remove('/tmp/tmp.log')
		self['infotext'].setText(strview)


class NetworkServicesSummary(Screen):
	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["title"] = StaticText("")
		self["status_summary"] = StaticText("")
		self["autostartstatus_summary"] = StaticText("")
		self.onShow.append(self.addWatcher)
		self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		self.parent.onChangedEntry.append(self.selectionChanged)
		self.parent.updateService()

	def removeWatcher(self):
		self.parent.onChangedEntry.remove(self.selectionChanged)

	def selectionChanged(self, title, status_summary, autostartstatus_summary):
		self["title"].text = title
		self["status_summary"].text = status_summary
		self["autostartstatus_summary"].text = autostartstatus_summary


class NetworkPassword(ConfigListScreen, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NetworkPassword"
		self.onChangedEntry = []
		self.list = []
		ConfigListScreen.__init__(self, self.list, session=self.session, on_change=self.selectionChanged)
		Screen.setTitle(self, _("Password setup"))

		self["key_red"] = StaticText(_("Exit"))
		self["key_green"] = StaticText(_("Save"))
		self["key_yellow"] = StaticText(_("Random password"))
		self["key_blue"] = StaticText("")

		self["actions"] = ActionMap(["SetupActions", "ColorActions"], {
			"red": self.close,
			"cancel": self.close,
			"green": self.SetPasswd,
			"save": self.SetPasswd,
			"yellow": self.newRandom,
		})

		self["description"] = Label()
		self['footnote'] = Label()
		self["VKeyIcon"] = Boolean(False)
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()

		self.user = "root"
		self.output_line = ""

		self.updateList()
		if self.selectionChanged not in self["config"].onSelectionChanged:
			self["config"].onSelectionChanged.append(self.selectionChanged)
		self.selectionChanged()

	def selectionChanged(self):
		item = self["config"].getCurrent()
		self["description"].setText(item[2])

	def newRandom(self):
		self.password.value = self.GeneratePassword()
		self["config"].invalidateCurrent()

	def updateList(self):
		self.password = NoSave(ConfigPassword(default=""))
		instructions = _("You must set a root password in order to be able to use network services,"
						" such as FTP, telnet or ssh.")
		self.list.append(getConfigListEntry(_('New password'), self.password, instructions))
		self['config'].list = self.list
		self['config'].l.setList(self.list)

	def GeneratePassword(self):
		passwdChars = string.letters + string.digits
		passwdLength = 10
		return ''.join(Random().sample(passwdChars, passwdLength))

	def SetPasswd(self):
		password = self.password.value
		if not password:
			self.session.open(MessageBox, _("The password can not be blank!"), MessageBox.TYPE_ERROR)
			return
		self.container = eConsoleAppContainer()
		self.container.appClosed.append(self.runFinished)
		self.container.dataAvail.append(self.dataAvail)
		retval = self.container.execute("echo -e '%s\n%s' | (passwd %s)" % (password, password, self.user))
		if retval:
			message = _("Unable to change password!")
			self.session.open(MessageBox, message, MessageBox.TYPE_ERROR)
		else:
			message = _("Password changed.")
			self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=5)
			self["HelpWindow"].hide()
			self.close()

	def dataAvail(self, data):
		self.output_line += data
		while True:
			i = self.output_line.find('\n')
			if i == -1:
				break
			self.processOutputLine(self.output_line[:i + 1])
			self.output_line = self.output_line[i + 1:]

	def processOutputLine(self, line):
		if line.find('password: '):
			self.container.write("%s\n" % self.password.value)

	def runFinished(self, retval):
		del self.container.dataAvail[:]
		del self.container.appClosed[:]
		del self.container
		self.close()


class NetworkSATPI(NSCommon, Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		Screen.setTitle(self, _("SATPI Setup"))
		self.skinName = "NetworkSATPI"
		self.onChangedEntry = []
		self['lab1'] = Label(_("Autostart:"))
		self['labactive'] = Label(_(_("Disabled")))
		self['lab2'] = Label(_("Current status:"))
		self['labstop'] = Label(_("Stopped"))
		self['labrun'] = Label(_("Running"))
		self['key_red'] = Label(_("Remove service"))
		self['key_green'] = Label(_("Start"))
		self['key_yellow'] = Label(_("Enable Autostart"))
		self['key_blue'] = Label(_("Stop|Disable Autostart"))
		self['status_summary'] = StaticText()
		self['autostartstatus_summary'] = StaticText()
		self.Console = Console()
		self.my_satpi_active = False
		self.my_satpi_run = False
		self['actions'] = ActionMap(['WizardActions', 'ColorActions'], {'ok': self.close, 'back': self.close, 'red': self.UninstallCheck, 'green': self.SatPIStart, 'yellow': self.activateSatPI, 'blue': self.SatPIStop})
		self.service_name = 'satpi'
		self.onLayoutFinish.append(self.InstallCheck)
		self.reboot_at_end = True

	def createSummary(self):
		return NetworkServicesSummary

	def SatPIStart(self):
		if not self.my_satpi_run:
			self.Console.ePopen('/etc/init.d/satpi start', self.StartStopCallback)

	def SatPIStop(self):
		if self.my_satpi_run or ServiceIsEnabled('satpi'):
			self.Console.ePopen('/etc/init.d/satpi stop ; update-rc.d -f satpi remove', self.StartStopCallback)

	def activateSatPI(self):
		if not ServiceIsEnabled('satpi'):
			self.Console.ePopen('update-rc.d -f satpi defaults', self.StartStopCallback)

	def updateService(self, result=None, retval=None, extra_args=None):
		import process
		p = process.ProcessList()
		satpi_process = str(p.named('satpi')).strip('[]')
		self['labrun'].hide()
		self['labstop'].hide()
		self['labactive'].setText(_("Disabled"))
		self.my_satpi_active = False
		self.my_satpi_run = False
		if ServiceIsEnabled('satpi'):
			self['labactive'].setText(_("Enabled"))
			self['labactive'].show()
			self.my_satpi_active = True
		if satpi_process:
			self.my_satpi_run = True
		if self.my_satpi_run:
			self['labstop'].hide()
			self['labactive'].show()
			self['labrun'].show()
			self['key_green'].setText(_("Start"))
			status_summary = self['lab2'].text + ' ' + self['labrun'].text
		else:
			self['labrun'].hide()
			self['labstop'].show()
			self['labactive'].show()
			self['key_blue'].setText(_("Stop|Disable Autostart"))
			status_summary = self['lab2'].text + ' ' + self['labstop'].text
		title = _("SatPI setup")
		autostartstatus_summary = self['lab1'].text + ' ' + self['labactive'].text

		for cb in self.onChangedEntry:
			cb(title, status_summary, autostartstatus_summary)
