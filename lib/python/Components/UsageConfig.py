from locale import AM_STR, PM_STR, nl_langinfo
from os import mkdir, remove
from os.path import exists, isfile, islink, join as pathjoin, normpath
from time import mktime

from enigma import eBackgroundFileEraser, eDVBDB, eEnv, setEnableTtCachingOnOff, setPreferredTuner, setSpinnerOnOff, setTunerTypePriorityOrder, Misc_Options, eServiceEvent, eDVBLocalTimeHandler, eEPGCache

from keyids import KEYIDS
from skin import parameters
from Components.About import GetIPsFromNetworkInterfaces
from Components.config import ConfigBoolean, ConfigClock, ConfigDictionarySet, ConfigEnableDisable, ConfigInteger, ConfigIP, ConfigLocations, ConfigNumber, ConfigPassword, ConfigSelection, ConfigSelectionNumber, ConfigSet, ConfigSlider, ConfigSubDict, ConfigSubsection, ConfigText, ConfigYesNo, NoSave, config
from Components.Console import Console
from Components.Harddisk import harddiskmanager
from Components.NimManager import nimmanager
from Components.ServiceList import refreshServiceList
from Components.SystemInfo import BoxInfo
from Tools.Directories import SCOPE_HDD, SCOPE_TIMESHIFT, defaultRecordingLocation, fileContains, resolveFilename

model = BoxInfo.getItem("model")
displaytype = BoxInfo.getItem("displaytype")


def InitUsageConfig():
	config.usage = ConfigSubsection()
	if fileContains("/etc/network/interfaces", "iface eth0 inet static") and not fileContains("/etc/network/interfaces", "iface wlan0 inet dhcp") or fileContains("/etc/network/interfaces", "iface wlan0 inet static") and fileContains("/run/ifstate", "wlan0=wlan0"):
		config.usage.dns = ConfigSelection(default="custom", choices=[
			("custom", _("Static IP or Custom")),
			("google", _("Google DNS")),
			("cloudflare", _("Cloudflare")),
			("opendns-familyshield", _("OpenDNS FamilyShield")),
			("opendns-home", _("OpenDNS Home"))
		])
	else:
		config.usage.dns = ConfigSelection(default="dhcp-router", choices=[
			("dhcp-router", _("DHCP Router")),
			("custom", _("Static IP or Custom")),
			("google", _("Google DNS")),
			("cloudflare", _("Cloudflare")),
			("opendns-familyshield", _("OpenDNS FamilyShield")),
			("opendns-home", _("OpenDNS Home"))
		])
	config.usage.subnetwork = ConfigYesNo(default=True)
	config.usage.subnetwork_cable = ConfigYesNo(default=True)
	config.usage.subnetwork_terrestrial = ConfigYesNo(default=True)
	config.usage.showdish = ConfigYesNo(default=True)
	config.usage.multibouquet = ConfigYesNo(default=True)

	showrotorpositionChoicesUpdate()

	config.usage.maxchannelnumlen = ConfigSelection(default="4", choices=[
		("3", _("3")),
		("4", _("4")),
		("5", _("5")),
		("6", _("6"))
	])
	config.misc.OVupdatecheck = ConfigYesNo(default=False)
	config.misc.extraopkgpackages = ConfigYesNo(default=False)
	config.misc.opkgcleanmode = ConfigYesNo(default=False)

	config.usage.alternative_number_mode = ConfigYesNo(default=False)

	def alternativeNumberModeChange(configElement):
		eDVBDB.getInstance().setNumberingMode(configElement.value)
		refreshServiceList()
	config.usage.alternative_number_mode.addNotifier(alternativeNumberModeChange)

	config.usage.servicelist_twolines = ConfigSelection(default="0", choices=[
		("0", _("Single line mode")),
		("1", _("Two lines")),
		("2", _("Two lines and next event"))
	])
	config.usage.servicelist_twolines.addNotifier(refreshServiceList)

	config.usage.hide_number_markers = ConfigYesNo(default=True)
	config.usage.hide_number_markers.addNotifier(refreshServiceList)

	config.usage.servicetype_icon_mode = ConfigSelection(default="1", choices=[
		("0", _("None")),
		("1", _("Left from servicename")),
		("2", _("Right from servicename"))
	])
	config.usage.servicetype_icon_mode.addNotifier(refreshServiceList)
	config.usage.crypto_icon_mode = ConfigSelection(default="2", choices=[
		("0", _("None")),
		("1", _("Left from servicename")),
		("2", _("Right from servicename"))
	])
	config.usage.crypto_icon_mode.addNotifier(refreshServiceList)
	config.usage.record_indicator_mode = ConfigSelection(default="3", choices=[
		("0", _("None")),
		("1", _("Left from servicename")),
		("2", _("Right from servicename")),
		("3", _("Red colored"))
	])
	config.usage.record_indicator_mode.addNotifier(refreshServiceList)

	config.usage.virtualkeyBoard_style = ConfigSelection(default="OV", choices=[
		("OV", _("Open Vision")),
		("e2", _("Enigma2 default"))
	])

	choicelist = [("-1", _("Disable"))]
	for i in range(0, 1300, 100):
		choicelist.append((str(i), ngettext("%d pixel wide", "%d pixels wide", i) % i))
	config.usage.servicelist_column = ConfigSelection(default="-1", choices=choicelist)
	config.usage.servicelist_column.addNotifier(refreshServiceList)

	config.usage.service_icon_enable = ConfigYesNo(default=True)
	config.usage.service_icon_enable.addNotifier(refreshServiceList)
	config.usage.servicelist_cursor_behavior = ConfigSelection(default="keep", choices=[
		("standard", _("Standard")),
		("keep", _("Keep service")),
		("reverseB", _("Reverse bouquet buttons")),
		("keep reverseB", "%s + %s" % (_("Keep service"), _("Reverse bouquet buttons")))
	])

	choicelist = [("by skin", _("As defined by the skin"))]
	for i in range(5, 41):
		choicelist.append((str(i)))
	config.usage.servicelist_number_of_services = ConfigSelection(default="by skin", choices=choicelist)
	config.usage.servicelist_number_of_services.addNotifier(refreshServiceList)

	config.usage.multiepg_ask_bouquet = ConfigYesNo(default=False)

	config.usage.quickzap_bouquet_change = ConfigYesNo(default=False)
	config.usage.e1like_radio_mode = ConfigYesNo(default=False)
	config.usage.e1like_radio_mode_last_play = ConfigYesNo(default=True)
	choicelist = [("0", _("No timeout"))]
	for i in range(1, 12):
		choicelist.append((str(i), ngettext("%d second", "%d seconds", i) % i))
	config.usage.infobar_timeout = ConfigSelection(default="5", choices=choicelist)
	if BoxInfo.getItem("socfamily").startswith("bcm"):
		config.usage.fadeout = ConfigYesNo(default=True)
	else:
		config.usage.fadeout = ConfigYesNo(default=False)
	config.usage.show_infobar_do_dimming = ConfigYesNo(default=False)
	config.usage.show_infobar_dimming_speed = ConfigSelectionNumber(min=1, max=40, stepwidth=1, default=40, wraparound=True)
	config.usage.show_infobar_on_zap = ConfigYesNo(default=True)
	config.usage.show_infobar_on_skip = ConfigYesNo(default=True)
	config.usage.show_infobar_on_event_change = ConfigYesNo(default=False)
	config.usage.show_second_infobar = ConfigSelection(default="0", choices=[("", _("None"))] + choicelist + [("EPG", _("EPG"))])
	config.usage.show_simple_second_infobar = ConfigYesNo(default=False)
	config.usage.infobar_frontend_source = ConfigSelection(default="settings", choices=[
		("settings", _("Settings")),
		("tuner", _("Tuner"))
	])
	config.usage.oldstyle_zap_controls = ConfigYesNo(default=False)
	config.usage.oldstyle_channel_select_controls = ConfigYesNo(default=False)
	config.usage.zap_with_ch_buttons = ConfigYesNo(default=False)
	config.usage.ok_is_channelselection = ConfigYesNo(default=False)
	config.usage.volume_instead_of_channelselection = ConfigYesNo(default=False)
	config.usage.channelselection_preview = ConfigYesNo(default=False)
	config.usage.show_spinner = ConfigYesNo(default=True)
	config.usage.menu_sort_weight = ConfigDictionarySet(default={"mainmenu": {"submenu": {}}})
	config.usage.menu_sort_mode = ConfigSelection(default="default", choices=[
		("a_z", _("Alphabetical")),
		("default", _("Default")),
		("user", _("User defined")),
		("user_hidden", _("User defined hidden"))
	])
	if model.startswith("bey"):
		config.usage.show_genre_info = ConfigYesNo(default=True)
	else:
		config.usage.show_genre_info = ConfigYesNo(default=False)
	config.usage.menu_show_numbers = ConfigSelection(default="no", choices=[
		("no", _("No")),
		("menu&plugins", _("In menu and plugins")),
		("menu", _("In menu only")),
		("plugins", _("In plugins only"))
	])
	config.usage.showScreenPath = ConfigSelection(default="small", choices=[
		("off", _("Disabled")),
		("small", _("Small")),
		("large", _("Large"))
	])
	config.usage.enable_tt_caching = ConfigYesNo(default=False)

	config.usage.tuxtxt_font_and_res = ConfigSelection(default="TTF_SD", choices=[
		("X11_SD", _("Fixed X11 font (SD)")),
		("TTF_SD", _("TrueType font (SD)")),
		("TTF_HD", _("TrueType font (HD)")),
		("TTF_FHD", _("TrueType font (Full-HD)")),
		("expert_mode", _("Expert mode"))
	])
	config.usage.tuxtxt_UseTTF = ConfigSelection(default="1", choices=[
		("0", _("0")),
		("1", _("1"))
	])
	config.usage.tuxtxt_TTFBold = ConfigSelection(default="1", choices=[
		("0", _("0")),
		("1", _("1"))
	])
	config.usage.tuxtxt_TTFScreenResX = ConfigSelection(default="720", choices=[
		("720", _("720")),
		("1280", _("1280")),
		("1920", _("1920"))
	])
	config.usage.tuxtxt_StartX = ConfigInteger(default=50, limits=(0, 200))
	config.usage.tuxtxt_EndX = ConfigInteger(default=670, limits=(500, 1920))
	config.usage.tuxtxt_StartY = ConfigInteger(default=30, limits=(0, 200))
	config.usage.tuxtxt_EndY = ConfigInteger(default=555, limits=(400, 1080))
	config.usage.tuxtxt_TTFShiftY = ConfigSelection(default="2", choices=[
		("-9", _("-9")),
		("-8", _("-8")),
		("-7", _("-7")),
		("-6", _("-6")),
		("-5", _("-5")),
		("-4", _("-4")),
		("-3", _("-3")),
		("-2", _("-2")),
		("-1", _("-1")),
		("0", _("0")),
		("1", _("1")),
		("2", _("2")),
		("3", _("3")),
		("4", _("4")),
		("5", _("5")),
		("6", _("6")),
		("7", _("7")),
		("8", _("8")),
		("9", _("9"))
	])
	config.usage.tuxtxt_TTFShiftX = ConfigSelection(default="0", choices=[
		("-9", _("-9")),
		("-8", _("-8")),
		("-7", _("-7")),
		("-6", _("-6")),
		("-5", _("-5")),
		("-4", _("-4")),
		("-3", _("-3")),
		("-2", _("-2")),
		("-1", _("-1")),
		("0", _("0")),
		("1", _("1")),
		("2", _("2")),
		("3", _("3")),
		("4", _("4")),
		("5", _("5")),
		("6", _("6")),
		("7", _("7")),
		("8", _("8")),
		("9", _("9"))
	])
	config.usage.tuxtxt_TTFWidthFactor16 = ConfigInteger(default=29, limits=(8, 31))
	config.usage.tuxtxt_TTFHeightFactor16 = ConfigInteger(default=14, limits=(8, 31))
	config.usage.tuxtxt_CleanAlgo = ConfigInteger(default=0, limits=(0, 9))
	config.usage.tuxtxt_ConfFileHasBeenPatched = NoSave(ConfigYesNo(default=False))

	config.usage.tuxtxt_font_and_res.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_UseTTF.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_TTFBold.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_TTFScreenResX.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_StartX.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_EndX.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_StartY.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_EndY.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_TTFShiftY.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_TTFShiftX.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_TTFWidthFactor16.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_TTFHeightFactor16.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)
	config.usage.tuxtxt_CleanAlgo.addNotifier(patchTuxtxtConfFile, initial_call=False, immediate_feedback=False)

	config.usage.sort_settings = ConfigYesNo(default=False)
	choicelist = []
	for i in (10, 30):
		choicelist.append((str(i), ngettext("%d second", "%d seconds", i) % i))
	for i in (60, 120, 300, 600, 1200, 1800):
		m = i / 60
		choicelist.append((str(i), ngettext("%d minute", "%d minutes", m) % m))
	for i in (3600, 7200, 14400):
		h = i / 3600
		choicelist.append((str(i), ngettext("%d hour", "%d hours", h) % h))
	config.usage.hdd_standby = ConfigSelection(default="300", choices=[("0", _("No standby"))] + choicelist)
	config.usage.output_12V = ConfigSelection(default="do not change", choices=[
		("do not change", _("Do not change")),
		("off", _("Off")),
		("on", _("On"))
	])

	config.usage.pip_zero_button = ConfigSelection(default="standard", choices=[
		("standard", _("Standard")),
		("swap", _("Swap PiP and main picture")),
		("swapstop", _("Move PiP to main picture")),
		("stop", _("Stop PiP"))
	])
	config.usage.pip_hideOnExit = ConfigSelection(default="without popup", choices=[
		("no", _("No")),
		("popup", _("With popup")),
		("without popup", _("Without popup"))
	])
	choicelist = [
		("-1", _("Disabled")),
		("0", _("No timeout"))
	]
	for i in [60, 300, 600, 900, 1800, 2700, 3600]:
		m = i / 60
		choicelist.append((str(i), ngettext("%d minute", "%d minutes", m) % m))
	config.usage.pip_last_service_timeout = ConfigSelection(default="0", choices=choicelist)

	if not exists(resolveFilename(SCOPE_HDD)):
		try:
			mkdir(resolveFilename(SCOPE_HDD), 0755)
		except (IOError, OSError):
			pass
	defaultValue = resolveFilename(SCOPE_HDD)
	config.usage.default_path = ConfigSelection(default=defaultValue, choices=[(defaultValue, defaultValue)])
	config.usage.default_path.load()
	if config.usage.default_path.saved_value:
		savedValue = pathjoin(config.usage.default_path.saved_value, "")
		if savedValue and savedValue != defaultValue:
			config.usage.default_path.setChoices([(defaultValue, defaultValue), (savedValue, savedValue)], default=defaultValue)
			config.usage.default_path.value = savedValue
	config.usage.default_path.save()
	choiceList = [("<default>", "<default>"), ("<current>", "<current>"), ("<timer>", "<timer>")]
	config.usage.timer_path = ConfigSelection(default="<default>", choices=choiceList)
	config.usage.timer_path.load()
	if config.usage.timer_path.saved_value:
		savedValue = config.usage.timer_path.saved_value if config.usage.timer_path.saved_value.startswith("<") else pathjoin(config.usage.timer_path.saved_value, "")
		if savedValue and savedValue not in choiceList:
			config.usage.timer_path.setChoices(choiceList + [(savedValue, savedValue)], default="<default>")
			config.usage.timer_path.value = savedValue
	config.usage.timer_path.save()
	config.usage.instantrec_path = ConfigSelection(default="<default>", choices=choiceList)
	config.usage.instantrec_path.load()
	if config.usage.instantrec_path.saved_value:
		savedValue = config.usage.instantrec_path.saved_value if config.usage.instantrec_path.saved_value.startswith("<") else pathjoin(config.usage.instantrec_path.saved_value, "")
		if savedValue and savedValue not in choiceList:
			config.usage.instantrec_path.setChoices(choiceList + [(savedValue, savedValue)], default="<default>")
			config.usage.instantrec_path.value = savedValue
	config.usage.instantrec_path.save()
	if not exists(resolveFilename(SCOPE_TIMESHIFT)):
		try:
			mkdir(resolveFilename(SCOPE_TIMESHIFT), 0755)
		except:
			pass
	defaultValue = resolveFilename(SCOPE_TIMESHIFT)
	config.usage.timeshift_path = ConfigSelection(default=defaultValue, choices=[(defaultValue, defaultValue)])
	config.usage.timeshift_path.load()
	if config.usage.timeshift_path.saved_value:
		savedValue = pathjoin(config.usage.timeshift_path.saved_value, "")
		if savedValue and savedValue != defaultValue:
			config.usage.timeshift_path.setChoices([(defaultValue, defaultValue), (savedValue, savedValue)], default=defaultValue)
			config.usage.timeshift_path.value = savedValue
	config.usage.timeshift_path.save()
	config.usage.allowed_timeshift_paths = ConfigLocations(default=[resolveFilename(SCOPE_TIMESHIFT)])

	config.usage.trashsort_deltime = ConfigSelection(default="no", choices=[
		("no", _("No")),
		("show record time", _("Yes, show record time")),
		("show delete time", _("Yes, show delete time"))])
	config.usage.movielist_trashcan = ConfigYesNo(default=True)
	config.usage.movielist_trashcan_network_clean = ConfigYesNo(default=False)

	config.usage.movielist_trashcan_days = ConfigSelectionNumber(min=0, max=31, stepwidth=1, default=8, wraparound=True)
	config.usage.movielist_trashcan_reserve = ConfigNumber(default=40)
	config.usage.on_movie_start = ConfigSelection(default="ask yes", choices=[
		("ask yes", _("Ask user (with default as 'Yes')")),
		("ask no", _("Ask user (with default as 'No')")),
		("resume", _("Resume from last position")),
		("beginning", _("Start from the beginning"))
	])
	config.usage.on_movie_stop = ConfigSelection(default="movielist", choices=[
		("ask", _("Ask user")),
		("movielist", _("Return to movie list")),
		("quit", _("Return to previous service"))
	])
	config.usage.on_movie_eof = ConfigSelection(default="movielist", choices=[
		("ask", _("Ask user")),
		("movielist", _("Return to movie list")),
		("quit", _("Return to previous service")),
		("pause", _("Pause movie at end")),
		("playlist", _("Play next (return to movie list)")),
		("playlistquit", _("Play next (return to previous service)")),
		("loop", _("Continues play (loop)")),
		("repeatcurrent", _("Repeat"))
	])
	config.usage.next_movie_msg = ConfigYesNo(default=True)
	config.usage.last_movie_played = ConfigText()
	config.usage.leave_movieplayer_onExit = ConfigSelection(default="popup", choices=[
		("no", _("No")),
		("popup", _("With popup")),
		("without popup", _("Without popup"))
	])

	config.usage.setup_level = ConfigSelection(default="expert", choices=[
		("simple", _("Normal")),
		("intermediate", _("Advanced")),
		("expert", _("Expert"))
	])

	config.usage.setupShowDefault = ConfigSelection(default="newline", choices=[
		("", _("Don't show default")),
		("spaces", _("Show default after description")),
		("newline", _("Show default on new line"))
	])

	config.usage.helpSortOrder = ConfigSelection(default="headings+alphabetic", choices=[
		("headings+alphabetic", _("Alphabetical under headings")),
		("flat+alphabetic", _("Flat alphabetical")),
		("flat+remotepos", _("Flat by position on remote")),
		("flat+remotegroups", _("Flat by key group on remote"))
	])

	config.usage.helpAnimationSpeed = ConfigSelection(default="10", choices=[
		("1", _("Very fast")),
		("5", _("Fast")),
		("10", _("Default")),
		("20", _("Slow")),
		("50", _("Very slow"))
	])

	config.usage.startup_to_standby = ConfigSelection(default="no", choices=[
		("no", _("No")),
		("yes", _("Yes")),
		("except", _("No, except Wakeup timer"))
	])

	config.usage.wakeup_enabled = ConfigSelection(default="no", choices=[
		("no", _("No")),
		("yes", _("Yes")),
		("standby", _("Yes, only from standby")),
		("deepstandby", _("Yes, only from deep standby"))
	])
	config.usage.wakeup_day = ConfigSubDict()
	config.usage.wakeup_time = ConfigSubDict()
	for i in range(7):
		config.usage.wakeup_day[i] = ConfigEnableDisable(default=False)
		config.usage.wakeup_time[i] = ConfigClock(default=((6 * 60 + 0) * 60))

	choicelist = [("0", _("Do nothing"))]
	for i in range(3600, 21601, 3600):
		h = abs(i / 3600)
		choicelist.append((str(i), _("Standby in %s") % (ngettext("%d hour", "%d hours", h) % h)))
	config.usage.inactivity_timer = ConfigSelection(default="0", choices=choicelist)
	config.usage.inactivity_timer_blocktime = ConfigYesNo(default=True)
	config.usage.inactivity_timer_blocktime_begin = ConfigClock(default=mktime((1970, 1, 1, 18, 0, 0, 0, 0, 0)))
	config.usage.inactivity_timer_blocktime_end = ConfigClock(default=mktime((1970, 1, 1, 23, 0, 0, 0, 0, 0)))
	config.usage.inactivity_timer_blocktime_extra = ConfigYesNo(default=False)
	config.usage.inactivity_timer_blocktime_extra_begin = ConfigClock(default=mktime((1970, 1, 1, 6, 0, 0, 0, 0, 0)))
	config.usage.inactivity_timer_blocktime_extra_end = ConfigClock(default=mktime((1970, 1, 1, 9, 0, 0, 0, 0, 0)))
	config.usage.inactivity_timer_blocktime_by_weekdays = ConfigYesNo(default=False)
	config.usage.inactivity_timer_blocktime_day = ConfigSubDict()
	config.usage.inactivity_timer_blocktime_begin_day = ConfigSubDict()
	config.usage.inactivity_timer_blocktime_end_day = ConfigSubDict()
	config.usage.inactivity_timer_blocktime_extra_day = ConfigSubDict()
	config.usage.inactivity_timer_blocktime_extra_begin_day = ConfigSubDict()
	config.usage.inactivity_timer_blocktime_extra_end_day = ConfigSubDict()
	for i in range(7):
		config.usage.inactivity_timer_blocktime_day[i] = ConfigYesNo(default=False)
		config.usage.inactivity_timer_blocktime_begin_day[i] = ConfigClock(default=mktime((1970, 1, 1, 18, 0, 0, 0, 0, 0)))
		config.usage.inactivity_timer_blocktime_end_day[i] = ConfigClock(default=mktime((1970, 1, 1, 23, 0, 0, 0, 0, 0)))
		config.usage.inactivity_timer_blocktime_extra_day[i] = ConfigYesNo(default=False)
		config.usage.inactivity_timer_blocktime_extra_begin_day[i] = ConfigClock(default=mktime((1970, 1, 1, 6, 0, 0, 0, 0, 0)))
		config.usage.inactivity_timer_blocktime_extra_end_day[i] = ConfigClock(default=mktime((1970, 1, 1, 9, 0, 0, 0, 0, 0)))

	choicelist = [
		("0", _("Disabled")),
		("event_standby", _("Standby after current event"))
	]
	for i in range(900, 7201, 900):
		m = abs(i / 60)
		choicelist.append((str(i), _("Standby in %s") % (ngettext("%d minute", "%d minutes", m) % m)))
	config.usage.sleep_timer = ConfigSelection(default="0", choices=choicelist)

	choicelist = [("0", _("Disabled"))]
	for i in [300, 600] + list(range(900, 14401, 900)):
		m = abs(i / 60)
		choicelist.append((str(i), _("After %s") % (ngettext("%d minute", "%d minutes", m) % m)))
	config.usage.standby_to_shutdown_timer = ConfigSelection(default="0", choices=choicelist)
	config.usage.standby_to_shutdown_timer_blocktime = ConfigYesNo(default=False)
	config.usage.standby_to_shutdown_timer_blocktime_begin = ConfigClock(default=mktime((1970, 1, 1, 6, 0, 0, 0, 0, 0)))
	config.usage.standby_to_shutdown_timer_blocktime_end = ConfigClock(default=mktime((1970, 1, 1, 23, 0, 0, 0, 0, 0)))

	config.usage.long_press_emulation_key = ConfigSelection(default="0", choices=[
		("0", _("None")),
		(str(KEYIDS["KEY_TV"]), _("TV")),
		(str(KEYIDS["KEY_RADIO"]), _("Radio")),
		(str(KEYIDS["KEY_AUDIO"]), _("Audio")),
		(str(KEYIDS["KEY_VIDEO"]), _("List/Fav")),
		(str(KEYIDS["KEY_HOME"]), _("Home")),
		(str(KEYIDS["KEY_END"]), _("End")),
		(str(KEYIDS["KEY_HELP"]), _("Help")),
		(str(KEYIDS["KEY_INFO"]), _("Info (EPG)")),
		(str(KEYIDS["KEY_TEXT"]), _("Teletext")),
		(str(KEYIDS["KEY_SUBTITLE"]), _("Subtitle")),
		(str(KEYIDS["KEY_FAVORITES"]), _("Favorites"))
	])

	choicelist = [("0", _("Disabled"))]
	for m in (1, 5, 10, 15, 30, 60):
		choicelist.append((str(m * 60), ngettext("%d minute", "%d minutes", m) % m))
	config.usage.screen_saver = ConfigSelection(default="300", choices=choicelist)

	config.usage.check_timeshift = ConfigYesNo(default=True)

	choicelist = [("0", _("Disabled"))]
	for i in (2, 3, 4, 5, 10, 20, 30):
		choicelist.append((str(i), ngettext("%d second", "%d seconds", i) % i))
	for i in (60, 120, 300):
		m = i / 60
		choicelist.append((str(i), ngettext("%d minute", "%d minutes", m) % m))
	config.usage.timeshift_start_delay = ConfigSelection(default="0", choices=choicelist)

	config.usage.alternatives_priority = ConfigSelection(default="1", choices=[
		("0", _("DVB-S/-C/-T")),
		("1", _("DVB-S/-T/-C")),
		("2", _("DVB-C/-S/-T")),
		("3", _("DVB-C/-T/-S")),
		("4", _("DVB-T/-C/-S")),
		("5", _("DVB-T/-S/-C")),
		("127", _("No priority"))
	])

	def remote_fallback_changed(configElement):
		if configElement.value:
			configElement.value = "%s%s" % (not configElement.value.startswith("http://") and "http://" or "", configElement.value)
			configElement.value = "%s%s" % (configElement.value, configElement.value.count(":") == 1 and ":8001" or "")
	config.usage.remote_fallback_enabled = ConfigYesNo(default=False)
	config.usage.remote_fallback = ConfigText(default="", fixed_size=False)
	config.usage.remote_fallback.addNotifier(remote_fallback_changed, immediate_feedback=False)
	config.usage.remote_fallback_import_url = ConfigText(default="", fixed_size=False)
	config.usage.remote_fallback_import_url.addNotifier(remote_fallback_changed, immediate_feedback=False)
	config.usage.remote_fallback_alternative = ConfigYesNo(default=False)
	config.usage.remote_fallback_dvb_t = ConfigText(default="", fixed_size=False)
	config.usage.remote_fallback_dvb_t.addNotifier(remote_fallback_changed, immediate_feedback=False)
	config.usage.remote_fallback_dvb_c = ConfigText(default="", fixed_size=False)
	config.usage.remote_fallback_dvb_c.addNotifier(remote_fallback_changed, immediate_feedback=False)
	config.usage.remote_fallback_atsc = ConfigText(default="", fixed_size=False)
	config.usage.remote_fallback_atsc.addNotifier(remote_fallback_changed, immediate_feedback=False)
	config.usage.remote_fallback_import = ConfigSelection(default="", choices=[
		("", _("No")),
		("channels", _("Channels only")),
		("channels_epg", _("Channels and EPG")),
		("epg", _("EPG only"))
	])
	config.usage.remote_fallback_import_restart = ConfigYesNo(default=False)
	config.usage.remote_fallback_import_standby = ConfigYesNo(default=False)
	config.usage.remote_fallback_ok = ConfigYesNo(default=False)
	config.usage.remote_fallback_nok = ConfigYesNo(default=False)
	config.usage.remote_fallback_extension_menu = ConfigYesNo(default=False)
	config.usage.remote_fallback_external_timer = ConfigYesNo(default=False)
	config.usage.remote_fallback_openwebif_customize = ConfigYesNo(default=False)
	config.usage.remote_fallback_openwebif_userid = ConfigText(default="root")
	config.usage.remote_fallback_openwebif_password = ConfigPassword(default="default")
	config.usage.remote_fallback_openwebif_port = ConfigInteger(default=80, limits=(0, 65535))
	config.usage.remote_fallback_dvbt_region = ConfigText(default="fallback DVB-T/T2 Europe")

	config.usage.show_timer_conflict_warning = ConfigYesNo(default=True)

	dvbs_nims = [("-2", _("Disabled"))]
	dvbt_nims = [("-2", _("Disabled"))]
	dvbc_nims = [("-2", _("Disabled"))]
	atsc_nims = [("-2", _("Disabled"))]

	nims = [("-1", _("Auto"))]
	for x in nimmanager.nim_slots:
		if x.isCompatible("DVB-S"):
			dvbs_nims.append((str(x.slot), x.getSlotName()))
		elif x.isCompatible("DVB-T"):
			dvbt_nims.append((str(x.slot), x.getSlotName()))
		elif x.isCompatible("DVB-C"):
			dvbc_nims.append((str(x.slot), x.getSlotName()))
		elif x.isCompatible("ATSC"):
			atsc_nims.append((str(x.slot), x.getSlotName()))
		nims.append((str(x.slot), x.getSlotName()))

	config.usage.menutype = ConfigSelection(default="standard", choices=[
		("horzanim", _("Horizontal menu")),
		("horzicon", _("Horizontal icons")),
		("standard", _("Standard menu"))
	])

	config.usage.frontend_priority = ConfigSelection(default="-1", choices=list(nims))
	nims.insert(0, ("-2", _("Disabled")))
	config.usage.recording_frontend_priority = ConfigSelection(default="-2", choices=nims)
	config.usage.frontend_priority_dvbs = ConfigSelection(default="-2", choices=list(dvbs_nims))
	dvbs_nims.insert(1, ("-1", _("Auto")))
	config.usage.recording_frontend_priority_dvbs = ConfigSelection(default="-2", choices=dvbs_nims)
	config.usage.frontend_priority_dvbt = ConfigSelection(default="-2", choices=list(dvbt_nims))
	dvbt_nims.insert(1, ("-1", _("Auto")))
	config.usage.recording_frontend_priority_dvbt = ConfigSelection(default="-2", choices=dvbt_nims)
	config.usage.frontend_priority_dvbc = ConfigSelection(default="-2", choices=list(dvbc_nims))
	dvbc_nims.insert(1, ("-1", _("Auto")))
	config.usage.recording_frontend_priority_dvbc = ConfigSelection(default="-2", choices=dvbc_nims)
	config.usage.frontend_priority_atsc = ConfigSelection(default="-2", choices=list(atsc_nims))
	atsc_nims.insert(1, ("-1", _("Auto")))
	config.usage.recording_frontend_priority_atsc = ConfigSelection(default="-2", choices=atsc_nims)

	BoxInfo.setItem("DVB-S_priority_tuner_available", len(dvbs_nims) > 3 and any(len(i) > 2 for i in (dvbt_nims, dvbc_nims, atsc_nims)))
	BoxInfo.setItem("DVB-T_priority_tuner_available", len(dvbt_nims) > 3 and any(len(i) > 2 for i in (dvbs_nims, dvbc_nims, atsc_nims)))
	BoxInfo.setItem("DVB-C_priority_tuner_available", len(dvbc_nims) > 3 and any(len(i) > 2 for i in (dvbs_nims, dvbt_nims, atsc_nims)))
	BoxInfo.setItem("ATSC_priority_tuner_available", len(atsc_nims) > 3 and any(len(i) > 2 for i in (dvbs_nims, dvbc_nims, dvbt_nims)))

	config.misc.disable_background_scan = ConfigYesNo(default=False)
	config.misc.use_ci_assignment = ConfigYesNo(default=False)
	config.usage.show_event_progress_in_servicelist = ConfigSelection(default="percright", choices=[
		("barleft", _("Progress bar left")),
		("barright", _("Progress bar right")),
		("percleft", _("Percentage left")),
		("percright", _("Percentage right")),
		("no", _("No"))
	])
	config.usage.show_channel_numbers_in_servicelist = ConfigYesNo(default=True)
	config.usage.show_event_progress_in_servicelist.addNotifier(refreshServiceList)
	config.usage.show_channel_numbers_in_servicelist.addNotifier(refreshServiceList)

	if displaytype == "7segment" or "7seg" in displaytype:
		config.usage.blinking_display_clock_during_recording = ConfigSelection(default="Rec", choices=[
			("Rec", _("REC")),
			("RecBlink", _("Blinking REC")),
			("Time", _("Time")),
			("Nothing", _("Nothing"))
		])
	else:
		config.usage.blinking_display_clock_during_recording = ConfigYesNo(default=False)

	if displaytype == "textlcd" or "text" in displaytype:
		config.usage.blinking_rec_symbol_during_recording = ConfigSelection(default="Channel", choices=[
			("Rec", _("REC symbol")),
			("RecBlink", _("Blinking REC symbol")),
			("Channel", _("Channel name"))
		])
	if displaytype == "7segment" or "7seg" in displaytype:
		config.usage.blinking_rec_symbol_during_recording = ConfigSelection(default="Rec", choices=[
			("Rec", _("REC")),
			("RecBlink", _("Blinking REC")),
			("Time", _("Time"))
		])
	else:
		config.usage.blinking_rec_symbol_during_recording = ConfigYesNo(default=True)

	config.usage.show_in_standby = ConfigSelection(default="time", choices=[
		("time", _("Time")),
		("nothing", _("Nothing"))
	])

	config.usage.show_message_when_recording_starts = ConfigYesNo(default=True)

	config.usage.load_length_of_movies_in_moviellist = ConfigYesNo(default=True)
	config.usage.show_icons_in_movielist = ConfigSelection(default="i", choices=[
		("o", _("Off")),
		("p", _("Progress")),
		("s", _("Small progress")),
		("i", _("Icons"))
	])
	config.usage.movielist_unseen = ConfigYesNo(default=True)
	config.usage.movielist_servicename_mode = ConfigSelection(default="", choices=[
		("", _("None")),
		("picon", _("Picon"))
	])
	config.usage.movielist_piconwidth = ConfigSelectionNumber(default=100, stepwidth=1, min=50, max=500, wraparound=True)

	config.usage.swap_snr_on_osd = ConfigYesNo(default=False)
	config.usage.swap_time_display_on_osd = ConfigSelection(default="0", choices=[
		("0", _("Skin setting")),
		("1", _("Mins")),
		("2", _("Mins Secs")),
		("3", _("Hours Mins")),
		("4", _("Hours Mins Secs")),
		("5", _("Percentage"))
	])
	config.usage.swap_media_time_display_on_osd = ConfigSelection(default="0", choices=[
		("0", _("Skin setting")),
		("1", _("Mins")),
		("2", _("Mins Secs")),
		("3", _("Hours Mins")),
		("4", _("Hours Mins Secs")),
		("5", _("Percentage"))
	])
	config.usage.swap_time_remaining_on_osd = ConfigSelection(default="0", choices=[
		("0", _("Remaining")),
		("1", _("Elapsed")),
		("2", _("Elapsed & Remaining")),
		("3", _("Remaining & Elapsed"))
	])
	config.usage.elapsed_time_positive_osd = ConfigYesNo(default=False)
	config.usage.swap_time_display_on_vfd = ConfigSelection(default="0", choices=[
		("0", _("Skin setting")),
		("1", _("Mins")),
		("2", _("Mins Secs")),
		("3", _("Hours Mins")),
		("4", _("Hours Mins Secs")),
		("5", _("Percentage"))
	])
	config.usage.swap_media_time_display_on_vfd = ConfigSelection(default="0", choices=[
		("0", _("Skin setting")),
		("1", _("Mins")),
		("2", _("Mins Secs")),
		("3", _("Hours Mins")),
		("4", _("Hours Mins Secs")),
		("5", _("Percentage"))
	])
	config.usage.swap_time_remaining_on_vfd = ConfigSelection(default="0", choices=[
		("0", _("Remaining")),
		("1", _("Elapsed")),
		("2", _("Elapsed & Remaining")),
		("3", _("Remaining & Elapsed"))
	])
	config.usage.elapsed_time_positive_vfd = ConfigYesNo(default=False)

	config.usage.frontled_color = ConfigSelection(default="2", choices=[
		("0", _("Off")),
		("1", _("Blue")),
		("2", _("Red")),
		("3", _("Blinking blue")),
		("4", _("Blinking red"))
	])
	config.usage.frontledrec_color = ConfigSelection(default="3", choices=[
		("0", _("Off")),
		("1", _("Blue")),
		("2", _("Red")),
		("3", _("Blinking blue")),
		("4", _("Blinking red"))
	])
	config.usage.frontledstdby_color = ConfigSelection(default="0", choices=[
		("0", _("Off")),
		("1", _("Blue")),
		("2", _("Red")),
		("3", _("Blinking blue")),
		("4", _("Blinking red"))
	])
	config.usage.frontledrecstdby_color = ConfigSelection(default="3", choices=[
		("0", _("Off")),
		("1", _("Blue")),
		("2", _("Red")),
		("3", _("Blinking blue")),
		("4", _("Blinking red"))
	])

	config.usage.lcd_scroll_delay = ConfigSelection(default="10000", choices=[
		("10000", _("%d seconds") % 10),
		("20000", _("%d seconds") % 20),
		("30000", _("%d seconds") % 30),
		("60000", _("%d minute") % 1),
		("300000", _("%d minutes") % 5),
		("noscrolling", _("Off"))
	])
	config.usage.lcd_scroll_speed = ConfigSelection(default="300", choices=[
		("500", _("Slow")),
		("300", _("Normal")),
		("100", _("Fast"))
	])

	def SpinnerOnOffChanged(configElement):
		setSpinnerOnOff(int(configElement.value))
	config.usage.show_spinner.addNotifier(SpinnerOnOffChanged)

	def EnableTtCachingChanged(configElement):
		setEnableTtCachingOnOff(int(configElement.value))
	config.usage.enable_tt_caching.addNotifier(EnableTtCachingChanged)

	def TunerTypePriorityOrderChanged(configElement):
		setTunerTypePriorityOrder(int(configElement.value))
	config.usage.alternatives_priority.addNotifier(TunerTypePriorityOrderChanged, immediate_feedback=False)

	def PreferredTunerChanged(configElement):
		setPreferredTuner(int(configElement.value))
	config.usage.frontend_priority.addNotifier(PreferredTunerChanged)

	config.skin.onlyicon = NoSave(ConfigBoolean(default=False))

	try:
		onlyIcon = parameters.get("AllowUseOnlyIcon", (0))
	except Exception as error:
		print("[UsageConfig] Error loading 'AllowUseOnlyIcon' skin parameter! (%s)" % error)
		onlyIcon = (0)
	if onlyIcon:
		config.skin.onlyicon.value = True
	else:
		config.skin.onlyicon.value = False

	config.usage.show_picon_in_display = ConfigYesNo(default=True)
	config.usage.hide_zap_errors = ConfigYesNo(default=False)
	config.usage.show_cryptoinfo = ConfigYesNo(default=True)
	config.usage.show_eit_nownext = ConfigYesNo(default=True)
	config.usage.show_vcr_scart = ConfigYesNo(default=False)
	config.usage.show_update_disclaimer = ConfigYesNo(default=True)
	config.usage.pic_resolution = ConfigSelection(default=None, choices=[
		(None, _("Same resolution as skin")),
		("(720, 576)", _("720x576")),
		("(1280, 720)", _("1280x720")),
		("(1920, 1080)", _("1920x1080"))
	][:BoxInfo.getItem("HasFullHDSkinSupport") and 4 or 3])

	config.usage.date = ConfigSubsection()
	config.usage.date.enabled = NoSave(ConfigBoolean(default=False))
	config.usage.date.enabled_display = NoSave(ConfigBoolean(default=False))
	config.usage.time = ConfigSubsection()
	config.usage.time.enabled = NoSave(ConfigBoolean(default=False))
	config.usage.time.disabled = NoSave(ConfigBoolean(default=True))
	config.usage.time.enabled_display = NoSave(ConfigBoolean(default=False))
	config.usage.time.wide = NoSave(ConfigBoolean(default=False))
	config.usage.time.wide_display = NoSave(ConfigBoolean(default=False))

	# TRANSLATORS: full date representation dayname daynum monthname year in strftime() format! See "man strftime"
	config.usage.date.dayfull = ConfigSelection(default=_("%A %-d %B %Y"), choices=[
		(_("%A %d %B %Y"), _("Dayname DD Month Year")),
		(_("%A %d. %B %Y"), _("Dayname DD. Month Year")),
		(_("%A %-d %B %Y"), _("Dayname D Month Year")),
		(_("%A %-d. %B %Y"), _("Dayname D. Month Year")),
		(_("%A %d-%B-%Y"), _("Dayname DD-Month-Year")),
		(_("%A %-d-%B-%Y"), _("Dayname D-Month-Year")),
		(_("%A %d/%m/%Y"), _("Dayname DD/MM/Year")),
		(_("%A %d.%m.%Y"), _("Dayname DD.MM.Year")),
		(_("%A %-d/%m/%Y"), _("Dayname D/MM/Year")),
		(_("%A %-d.%m.%Y"), _("Dayname D.MM.Year")),
		(_("%A %d/%-m/%Y"), _("Dayname DD/M/Year")),
		(_("%A %d.%-m.%Y"), _("Dayname DD.M.Year")),
		(_("%A %-d/%-m/%Y"), _("Dayname D/M/Year")),
		(_("%A %-d.%-m.%Y"), _("Dayname D.M.Year")),
		(_("%A %B %d %Y"), _("Dayname Month DD Year")),
		(_("%A %B %-d %Y"), _("Dayname Month D Year")),
		(_("%A %B-%d-%Y"), _("Dayname Month-DD-Year")),
		(_("%A %B-%-d-%Y"), _("Dayname Month-D-Year")),
		(_("%A %m/%d/%Y"), _("Dayname MM/DD/Year")),
		(_("%A %-m/%d/%Y"), _("Dayname M/DD/Year")),
		(_("%A %m/%-d/%Y"), _("Dayname MM/D/Year")),
		(_("%A %-m/%-d/%Y"), _("Dayname M/D/Year")),
		(_("%A %Y %B %d"), _("Dayname Year Month DD")),
		(_("%A %Y %B %-d"), _("Dayname Year Month D")),
		(_("%A %Y-%B-%d"), _("Dayname Year-Month-DD")),
		(_("%A %Y-%B-%-d"), _("Dayname Year-Month-D")),
		(_("%A %Y/%m/%d"), _("Dayname Year/MM/DD")),
		(_("%A %Y/%m/%-d"), _("Dayname Year/MM/D")),
		(_("%A %Y/%-m/%d"), _("Dayname Year/M/DD")),
		(_("%A %Y/%-m/%-d"), _("Dayname Year/M/D"))
	])

	# TRANSLATORS: long date representation short dayname daynum monthname year in strftime() format! See "man strftime"
	config.usage.date.shortdayfull = ConfigText(default=_("%a %-d %B %Y"))

	# TRANSLATORS: long date representation short dayname daynum short monthname year in strftime() format! See "man strftime"
	config.usage.date.daylong = ConfigText(default=_("%a %-d %b %Y"))

	# TRANSLATORS: short date representation dayname daynum short monthname in strftime() format! See "man strftime"
	config.usage.date.dayshortfull = ConfigText(default=_("%A %-d %B"))

	# TRANSLATORS: short date representation short dayname daynum short monthname in strftime() format! See "man strftime"
	config.usage.date.dayshort = ConfigText(default=_("%a %-d %b"))

	# TRANSLATORS: small date representation short dayname daynum in strftime() format! See "man strftime"
	config.usage.date.daysmall = ConfigText(default=_("%a %-d"))

	# TRANSLATORS: full date representation daynum monthname year in strftime() format! See "man strftime"
	config.usage.date.full = ConfigText(default=_("%-d %B %Y"))

	# TRANSLATORS: long date representation daynum short monthname year in strftime() format! See "man strftime"
	config.usage.date.long = ConfigText(default=_("%-d %b %Y"))

	# TRANSLATORS: small date representation daynum short monthname in strftime() format! See "man strftime"
	config.usage.date.short = ConfigText(default=_("%-d %b"))

	def setDateStyles(configElement):
		dateStyles = {
			# dayfull: (shortdayfull, daylong, dayshortfull, dayshort, daysmall, full, long, short)
			_("%A %d %B %Y"): (_("%a %d %B %Y"), _("%a %d %b %Y"), _("%A %d %B"), _("%a %d %b"), _("%a %d"), _("%d %B %Y"), _("%d %b %Y"), _("%d %b")),
			_("%A %d. %B %Y"): (_("%a %d. %B %Y"), _("%a %d. %b %Y"), _("%A %d. %B"), _("%a %d. %b"), _("%a %d"), _("%d. %B %Y"), _("%d. %b %Y"), _("%d. %b")),
			_("%A %-d %B %Y"): (_("%a %-d %B %Y"), _("%a %-d %b %Y"), _("%A %-d %B"), _("%a %-d %b"), _("%a %-d"), _("%-d %B %Y"), _("%-d %b %Y"), _("%-d %b")),
			_("%A %-d. %B %Y"): (_("%a %-d. %B %Y"), _("%a %-d. %b %Y"), _("%A %-d. %B"), _("%a %-d. %b"), _("%a %-d"), _("%-d. %B %Y"), _("%-d. %b %Y"), _("%-d. %b")),
			_("%A %d-%B-%Y"): (_("%a %d-%B-%Y"), _("%a %d-%b-%Y"), _("%A %d-%B"), _("%a %d-%b"), _("%a %d"), _("%d-%B-%Y"), _("%d-%b-%Y"), _("%d-%b")),
			_("%A %-d-%B-%Y"): (_("%a %-d-%B-%Y"), _("%a %-d-%b-%Y"), _("%A %-d-%B"), _("%a %-d-%b"), _("%a %-d"), _("%-d-%B-%Y"), _("%-d-%b-%Y"), _("%-d-%b")),
			_("%A %d/%m/%Y"): (_("%a %d/%m/%Y"), _("%a %d/%m/%Y"), _("%A %d/%m"), _("%a %d/%m"), _("%a %d"), _("%d/%m/%Y"), _("%d/%m/%Y"), _("%d/%m")),
			_("%A %d.%m.%Y"): (_("%a %d.%m.%Y"), _("%a %d.%m.%Y"), _("%A %d.%m"), _("%a %d.%m"), _("%a %d"), _("%d.%m.%Y"), _("%d.%m.%Y"), _("%d.%m")),
			_("%A %-d/%m/%Y"): (_("%a %-d/%m/%Y"), _("%a %-d/%m/%Y"), _("%A %-d/%m"), _("%a %-d/%m"), _("%a %-d"), _("%-d/%m/%Y"), _("%-d/%m/%Y"), _("%-d/%m")),
			_("%A %-d.%m.%Y"): (_("%a %-d.%m.%Y"), _("%a %-d.%m.%Y"), _("%A %-d.%m"), _("%a %-d.%m"), _("%a %-d"), _("%-d.%m.%Y"), _("%-d.%m.%Y"), _("%-d.%m")),
			_("%A %d/%-m/%Y"): (_("%a %d/%-m/%Y"), _("%a %d/%-m/%Y"), _("%A %d/%-m"), _("%a %d/%-m"), _("%a %d"), _("%d/%-m/%Y"), _("%d/%-m/%Y"), _("%d/%-m")),
			_("%A %d.%-m.%Y"): (_("%a %d.%-m.%Y"), _("%a %d.%-m.%Y"), _("%A %d.%-m"), _("%a %d.%-m"), _("%a %d"), _("%d.%-m.%Y"), _("%d.%-m.%Y"), _("%d.%-m")),
			_("%A %-d/%-m/%Y"): (_("%a %-d/%-m/%Y"), _("%a %-d/%-m/%Y"), _("%A %-d/%-m"), _("%a %-d/%-m"), _("%a %-d"), _("%-d/%-m/%Y"), _("%-d/%-m/%Y"), _("%-d/%-m")),
			_("%A %-d.%-m.%Y"): (_("%a %-d.%-m.%Y"), _("%a %-d.%-m.%Y"), _("%A %-d.%-m"), _("%a %-d.%-m"), _("%a %-d"), _("%-d.%-m.%Y"), _("%-d.%-m.%Y"), _("%-d.%-m")),
			_("%A %B %d %Y"): (_("%a %B %d %Y"), _("%a %b %d %Y"), _("%A %B %d"), _("%a %b %d"), _("%a %d"), _("%B %d %Y"), _("%b %d %Y"), _("%b %d")),
			_("%A %B %-d %Y"): (_("%a %B %-d %Y"), _("%a %b %-d %Y"), _("%A %B %-d"), _("%a %b %-d"), _("%a %-d"), _("%B %-d %Y"), _("%b %-d %Y"), _("%b %-d")),
			_("%A %B-%d-%Y"): (_("%a %B-%d-%Y"), _("%a %b-%d-%Y"), _("%A %B-%d"), _("%a %b-%d"), _("%a %d"), _("%B-%d-%Y"), _("%b-%d-%Y"), _("%b-%d")),
			_("%A %B-%-d-%Y"): (_("%a %B-%-d-%Y"), _("%a %b-%-d-%Y"), _("%A %B-%-d"), _("%a %b-%-d"), _("%a %-d"), _("%B-%-d-%Y"), _("%b-%-d-%Y"), _("%b-%-d")),
			_("%A %m/%d/%Y"): (_("%a %m/%d/%Y"), _("%a %m/%d/%Y"), _("%A %m/%d"), _("%a %m/%d"), _("%a %d"), _("%m/%d/%Y"), _("%m/%d/%Y"), _("%m/%d")),
			_("%A %-m/%d/%Y"): (_("%a %-m/%d/%Y"), _("%a %-m/%d/%Y"), _("%A %-m/%d"), _("%a %-m/%d"), _("%a %d"), _("%-m/%d/%Y"), _("%-m/%d/%Y"), _("%-m/%d")),
			_("%A %m/%-d/%Y"): (_("%a %m/%-d/%Y"), _("%a %m/%-d/%Y"), _("%A %m/%-d"), _("%a %m/%-d"), _("%a %-d"), _("%m/%-d/%Y"), _("%m/%-d/%Y"), _("%m/%-d")),
			_("%A %-m/%-d/%Y"): (_("%a %-m/%-d/%Y"), _("%a %-m/%-d/%Y"), _("%A %-m/%-d"), _("%a %-m/%-d"), _("%a %-d"), _("%-m/%-d/%Y"), _("%-m/%-d/%Y"), _("%-m/%-d")),
			_("%A %Y %B %d"): (_("%a %Y %B %d"), _("%a %Y %b %d"), _("%A %B %d"), _("%a %b %d"), _("%a %d"), _("%Y %B %d"), _("%Y %b %d"), _("%b %d")),
			_("%A %Y %B %-d"): (_("%a %Y %B %-d"), _("%a %Y %b %-d"), _("%A %B %-d"), _("%a %b %-d"), _("%a %-d"), _("%Y %B %-d"), _("%Y %b %-d"), _("%b %-d")),
			_("%A %Y-%B-%d"): (_("%a %Y-%B-%d"), _("%a %Y-%b-%d"), _("%A %B-%d"), _("%a %b-%d"), _("%a %d"), _("%Y-%B-%d"), _("%Y-%b-%d"), _("%b-%d")),
			_("%A %Y-%B-%-d"): (_("%a %Y-%B-%-d"), _("%a %Y-%b-%-d"), _("%A %B-%-d"), _("%a %b-%-d"), _("%a %-d"), _("%Y-%B-%-d"), _("%Y-%b-%-d"), _("%b-%-d")),
			_("%A %Y/%m/%d"): (_("%a %Y/%m/%d"), _("%a %Y/%m/%d"), _("%A %m/%d"), _("%a %m/%d"), _("%a %d"), _("%Y/%m/%d"), _("%Y/%m/%d"), _("%m/%d")),
			_("%A %Y/%m/%-d"): (_("%a %Y/%m/%-d"), _("%a %Y/%m/%-d"), _("%A %m/%-d"), _("%a %m/%-d"), _("%a %-d"), _("%Y/%m/%-d"), _("%Y/%m/%-d"), _("%m/%-d")),
			_("%A %Y/%-m/%d"): (_("%a %Y/%-m/%d"), _("%a %Y/%-m/%d"), _("%A %-m/%d"), _("%a %-m/%d"), _("%a %d"), _("%Y/%-m/%d"), _("%Y/%-m/%d"), _("%-m/%d")),
			_("%A %Y/%-m/%-d"): (_("%a %Y/%-m/%-d"), _("%a %Y/%-m/%-d"), _("%A %-m/%-d"), _("%a %-m/%-d"), _("%a %-d"), _("%Y/%-m/%-d"), _("%Y/%-m/%-d"), _("%-m/%-d"))
		}
		style = dateStyles.get(configElement.value, ((_("Invalid")) * 8))
		config.usage.date.shortdayfull.value = style[0]
		config.usage.date.shortdayfull.save()
		config.usage.date.daylong.value = style[1]
		config.usage.date.daylong.save()
		config.usage.date.dayshortfull.value = style[2]
		config.usage.date.dayshortfull.save()
		config.usage.date.dayshort.value = style[3]
		config.usage.date.dayshort.save()
		config.usage.date.daysmall.value = style[4]
		config.usage.date.daysmall.save()
		config.usage.date.full.value = style[5]
		config.usage.date.full.save()
		config.usage.date.long.value = style[6]
		config.usage.date.long.save()
		config.usage.date.short.value = style[7]
		config.usage.date.short.save()

	config.usage.date.dayfull.addNotifier(setDateStyles)

	# TRANSLATORS: full time representation hour:minute:seconds
	if nl_langinfo(AM_STR) and nl_langinfo(PM_STR):
		config.usage.time.long = ConfigSelection(default=_("%T"), choices=[
			(_("%T"), _("HH:mm:ss")),
			(_("%-H:%M:%S"), _("H:mm:ss")),
			(_("%I:%M:%S%^p"), _("hh:mm:ssAM/PM")),
			(_("%-I:%M:%S%^p"), _("h:mm:ssAM/PM")),
			(_("%I:%M:%S%P"), _("hh:mm:ssam/pm")),
			(_("%-I:%M:%S%P"), _("h:mm:ssam/pm")),
			(_("%I:%M:%S"), _("hh:mm:ss")),
			(_("%-I:%M:%S"), _("h:mm:ss"))
		])
	else:
		config.usage.time.long = ConfigSelection(default=_("%T"), choices=[
			(_("%T"), _("HH:mm:ss")),
			(_("%-H:%M:%S"), _("H:mm:ss")),
			(_("%I:%M:%S"), _("hh:mm:ss")),
			(_("%-I:%M:%S"), _("h:mm:ss"))
		])

	# TRANSLATORS: time representation hour:minute:seconds for 24 hour clock or 12 hour clock without AM/PM and hour:minute for 12 hour clocks with AM/PM
	config.usage.time.mixed = ConfigText(default=_("%T"))

	# TRANSLATORS: short time representation hour:minute (Same as "Default")
	config.usage.time.short = ConfigText(default=_("%R"))

	def setTimeStyles(configElement):
		timeStyles = {
			# long: (mixed, short)
			_("%T"): (_("%T"), _("%R")),
			_("%-H:%M:%S"): (_("%-H:%M:%S"), _("%-H:%M")),
			_("%I:%M:%S%^p"): (_("%I:%M%^p"), _("%I:%M%^p")),
			_("%-I:%M:%S%^p"): (_("%-I:%M%^p"), _("%-I:%M%^p")),
			_("%I:%M:%S%P"): (_("%I:%M%P"), _("%I:%M%P")),
			_("%-I:%M:%S%P"): (_("%-I:%M%P"), _("%-I:%M%P")),
			_("%I:%M:%S"): (_("%I:%M:%S"), _("%I:%M")),
			_("%-I:%M:%S"): (_("%-I:%M:%S"), _("%-I:%M"))
		}
		style = timeStyles.get(configElement.value, ((_("Invalid")) * 2))
		config.usage.time.mixed.value = style[0]
		config.usage.time.mixed.save()
		config.usage.time.short.value = style[1]
		config.usage.time.short.save()
		config.usage.time.wide.value = style[1].endswith(("P", "p"))

	config.usage.time.long.addNotifier(setTimeStyles)

	try:
		dateEnabled, timeEnabled = parameters.get("AllowUserDatesAndTimes", (0, 0))
	except Exception as error:
		print("[UsageConfig] Error loading 'AllowUserDatesAndTimes' skin parameter! (%s)" % error)
		dateEnabled, timeEnabled = (0, 0)
	if dateEnabled:
		config.usage.date.enabled.value = True
	else:
		config.usage.date.enabled.value = False
		config.usage.date.dayfull.value = config.usage.date.dayfull.default
	if timeEnabled:
		config.usage.time.enabled.value = True
		config.usage.time.disabled.value = not config.usage.time.enabled.value
	else:
		config.usage.time.enabled.value = False
		config.usage.time.disabled.value = not config.usage.time.enabled.value
		config.usage.time.long.value = config.usage.time.long.default

	# TRANSLATORS: compact date representation (for VFD) daynum short monthname in strftime() format! See "man strftime"
	config.usage.date.display = ConfigSelection(default=_("%-d %b"), choices=[
		("", _("Hidden / Blank")),
		(_("%d %b"), _("Day DD Mon")),
		(_("%-d %b"), _("Day D Mon")),
		(_("%d-%b"), _("Day DD-Mon")),
		(_("%-d-%b"), _("Day D-Mon")),
		(_("%d/%m"), _("Day DD/MM")),
		(_("%-d/%m"), _("Day D/MM")),
		(_("%d/%-m"), _("Day DD/M")),
		(_("%-d/%-m"), _("Day D/M")),
		(_("%b %d"), _("Day Mon DD")),
		(_("%b %-d"), _("Day Mon D")),
		(_("%b-%d"), _("Day Mon-DD")),
		(_("%b-%-d"), _("Day Mon-D")),
		(_("%m/%d"), _("Day MM/DD")),
		(_("%m/%-d"), _("Day MM/D")),
		(_("%-m/%d"), _("Day M/DD")),
		(_("%-m/%-d"), _("Day M/D"))
	])

	config.usage.date.displayday = ConfigText(default=_("%a %-d+%b_"))
	config.usage.date.display_template = ConfigText(default=_("%-d+%b_"))
	config.usage.date.compact = ConfigText(default=_("%-d+%b_"))
	config.usage.date.compressed = ConfigText(default=_("%-d+%b_"))

	timeDisplayValue = [_("%R")]

	def adjustDisplayDates():
		if timeDisplayValue[0] == "":
			if config.usage.date.display.value == "":  # If the date and time are both hidden output a space to blank the VFD display.
				config.usage.date.compact.value = " "
				config.usage.date.compressed.value = " "
			else:
				config.usage.date.compact.value = config.usage.date.displayday.value
				config.usage.date.compressed.value = config.usage.date.displayday.value
		else:
			if config.usage.time.wide_display.value:
				config.usage.date.compact.value = config.usage.date.display_template.value.replace("_", "").replace("=", "").replace("+", "")
				config.usage.date.compressed.value = config.usage.date.display_template.value.replace("_", "").replace("=", "").replace("+", "")
			else:
				config.usage.date.compact.value = config.usage.date.display_template.value.replace("_", " ").replace("=", "-").replace("+", " ")
				config.usage.date.compressed.value = config.usage.date.display_template.value.replace("_", " ").replace("=", "").replace("+", "")
		config.usage.date.compact.save()
		config.usage.date.compressed.save()

	def setDateDisplayStyles(configElement):
		dateDisplayStyles = {
			# display: (displayday, template)
			"": ("", ""),
			_("%d %b"): (_("%a %d %b"), _("%d+%b_")),
			_("%-d %b"): (_("%a %-d %b"), _("%-d+%b_")),
			_("%d-%b"): (_("%a %d-%b"), _("%d=%b_")),
			_("%-d-%b"): (_("%a %-d-%b"), _("%-d=%b_")),
			_("%d/%m"): (_("%a %d/%m"), _("%d/%m ")),
			_("%-d/%m"): (_("%a %-d/%m"), _("%-d/%m ")),
			_("%d/%-m"): (_("%a %d/%-m"), _("%d/%-m ")),
			_("%-d/%-m"): (_("%a %-d/%-m"), _("%-d/%-m ")),
			_("%b %d"): (_("%a %b %d"), _("%b+%d ")),
			_("%b %-d"): (_("%a %b %-d"), _("%b+%-d ")),
			_("%b-%d"): (_("%a %b-%d"), _("%b=%d ")),
			_("%b-%-d"): (_("%a %b-%-d"), _("%b=%-d ")),
			_("%m/%d"): (_("%a %m/%d"), _("%m/%d ")),
			_("%m/%-d"): (_("%a %m/%-d"), _("%m/%-d ")),
			_("%-m/%d"): (_("%a %-m/%d"), _("%-m/%d ")),
			_("%-m/%-d"): (_("%a %-m/%-d"), _("%-m/%-d "))
		}
		style = dateDisplayStyles.get(configElement.value, ((_("Invalid")) * 2))
		config.usage.date.displayday.value = style[0]
		config.usage.date.displayday.save()
		config.usage.date.display_template.value = style[1]
		config.usage.date.display_template.save()
		adjustDisplayDates()

	config.usage.date.display.addNotifier(setDateDisplayStyles)

	# TRANSLATORS: short time representation hour:minute (Same as "Default")
	if nl_langinfo(AM_STR) and nl_langinfo(PM_STR):
		config.usage.time.display = ConfigSelection(default=_("%R"), choices=[
			("", _("Hidden / Blank")),
			(_("%R"), _("HH:mm")),
			(_("%-H:%M"), _("H:mm")),
			(_("%I:%M%^p"), _("hh:mmAM/PM")),
			(_("%-I:%M%^p"), _("h:mmAM/PM")),
			(_("%I:%M%P"), _("hh:mmam/pm")),
			(_("%-I:%M%P"), _("h:mmam/pm")),
			(_("%I:%M"), _("hh:mm")),
			(_("%-I:%M"), _("h:mm"))
		])
	else:
		config.usage.time.display = ConfigSelection(default=_("%R"), choices=[
			("", _("Hidden / Blank")),
			(_("%R"), _("HH:mm")),
			(_("%-H:%M"), _("H:mm")),
			(_("%I:%M"), _("hh:mm")),
			(_("%-I:%M"), _("h:mm"))
		])

	def setTimeDisplayStyles(configElement):
		timeDisplayValue[0] = config.usage.time.display.value
		config.usage.time.wide_display.value = configElement.value.endswith(("P", "p"))
		adjustDisplayDates()

	config.usage.time.display.addNotifier(setTimeDisplayStyles)

	try:
		dateDisplayEnabled, timeDisplayEnabled = parameters.get("AllowUserDatesAndTimesDisplay", (0, 0))
	except Exception as error:
		print("[UsageConfig] Error loading 'AllowUserDatesAndTimesDisplay' display skin parameter! (%s)" % error)
		dateDisplayEnabled, timeDisplayEnabled = (0, 0)
	if dateDisplayEnabled:
		config.usage.date.enabled_display.value = True
	else:
		config.usage.date.enabled_display.value = False
		config.usage.date.display.value = config.usage.date.display.default
	if timeDisplayEnabled:
		config.usage.time.enabled_display.value = True
	else:
		config.usage.time.enabled_display.value = False
		config.usage.time.display.value = config.usage.time.display.default

	if BoxInfo.getItem("Fan"):
		choicelist = [
			("off", _("Off")),
			("on", _("On")),
			("auto", _("Auto"))
		]
		if exists("/proc/stb/fp/fan_choices"):
			print("[UsageConfig] Read /proc/stb/fp/fan_choices")
			choicelist = [x for x in choicelist if x[0] in open("/proc/stb/fp/fan_choices", "r").read().strip().split(" ")]
		config.usage.fan = ConfigSelection(choicelist)

		def fanChanged(configElement):
			open(BoxInfo.getItem("Fan"), "w").write(configElement.value)
		config.usage.fan.addNotifier(fanChanged)

	if BoxInfo.getItem("FanPWM"):
		def fanSpeedChanged(configElement):
			open(BoxInfo.getItem("FanPWM"), "w").write(hex(configElement.value)[2:])
		config.usage.fanspeed = ConfigSlider(default=127, increment=8, limits=(0, 255))
		config.usage.fanspeed.addNotifier(fanSpeedChanged)

	if BoxInfo.getItem("WakeOnLAN") or BoxInfo.getItem("wol"):
		def wakeOnLANChanged(configElement):
			if "fp" in BoxInfo.getItem("WakeOnLAN"):
				open(BoxInfo.getItem("WakeOnLAN"), "w").write(configElement.value and "enable" or "disable")
			else:
				open(BoxInfo.getItem("WakeOnLAN"), "w").write(configElement.value and "on" or "off")
		config.usage.wakeOnLAN = ConfigYesNo(default=False)
		config.usage.wakeOnLAN.addNotifier(wakeOnLANChanged)

	config.usage.boolean_graphic = ConfigSelection(default="true", choices={
		"false": _("No"),
		"true": _("Yes"),
		"only_bool": _("Yes, but not in multi selections")
	})

	config.osd.alpha_teletext = ConfigSelectionNumber(default=255, stepwidth=1, min=0, max=255, wraparound=False)

	config.epg = ConfigSubsection()
	config.epg.eit = ConfigYesNo(default=True)
	config.epg.mhw = ConfigYesNo(default=False)
	config.epg.freesat = ConfigYesNo(default=False)
	config.epg.viasat = ConfigYesNo(default=False)
	config.epg.netmed = ConfigYesNo(default=False)
	config.epg.virgin = ConfigYesNo(default=False)
	config.epg.opentv = ConfigYesNo(default=False)
	config.epg.saveepg = ConfigYesNo(default=True)

	config.epg.maxdays = ConfigSelectionNumber(min=1, max=365, stepwidth=1, default=7, wraparound=True)

	def EpgmaxdaysChanged(configElement):
		from enigma import eEPGCache
		eEPGCache.getInstance().setEpgmaxdays(config.epg.maxdays.getValue())
	config.epg.maxdays.addNotifier(EpgmaxdaysChanged)

	if model.startswith("bey"):
		config.misc.epgratingcountry = ConfigSelection(default="AUS", choices=[
			("", _("Auto detect")),
			("ETSI", _("Generic")),
			("AUS", _("Australia"))
		])
		config.misc.epggenrecountry = ConfigSelection(default="AUS", choices=[
			("", _("Auto detect")),
			("ETSI", _("Generic")),
			("AUS", _("Australia"))
		])
	else:
		config.misc.epgratingcountry = ConfigSelection(default="", choices=[
			("", _("Auto detect")),
			("ETSI", _("Generic")),
			("AUS", _("Australia"))
		])
		config.misc.epggenrecountry = ConfigSelection(default="", choices=[
			("", _("Auto detect")),
			("ETSI", _("Generic")),
			("AUS", _("Australia"))
		])

	def EpgSettingsChanged(configElement):
		mask = 0xffffffff
		if not config.epg.eit.value:
			mask &= ~(eEPGCache.NOWNEXT | eEPGCache.SCHEDULE | eEPGCache.SCHEDULE_OTHER)
		if not config.epg.mhw.value:
			mask &= ~eEPGCache.MHW
		if not config.epg.freesat.value:
			mask &= ~(eEPGCache.FREESAT_NOWNEXT | eEPGCache.FREESAT_SCHEDULE | eEPGCache.FREESAT_SCHEDULE_OTHER)
		if not config.epg.viasat.value:
			mask &= ~eEPGCache.VIASAT
		if not config.epg.netmed.value:
			mask &= ~(eEPGCache.NETMED_SCHEDULE | eEPGCache.NETMED_SCHEDULE_OTHER)
		if not config.epg.virgin.value:
			mask &= ~(eEPGCache.VIRGIN_NOWNEXT | eEPGCache.VIRGIN_SCHEDULE)
		if not config.epg.opentv.value:
			mask &= ~eEPGCache.OPENTV
		eEPGCache.getInstance().setEpgSources(mask)
	config.epg.eit.addNotifier(EpgSettingsChanged)
	config.epg.mhw.addNotifier(EpgSettingsChanged)
	config.epg.freesat.addNotifier(EpgSettingsChanged)
	config.epg.viasat.addNotifier(EpgSettingsChanged)
	config.epg.netmed.addNotifier(EpgSettingsChanged)
	config.epg.virgin.addNotifier(EpgSettingsChanged)
	config.epg.opentv.addNotifier(EpgSettingsChanged)

	config.epg.histminutes = ConfigSelectionNumber(min=0, max=120, stepwidth=15, default=0, wraparound=True)

	def EpgHistorySecondsChanged(configElement):
		from enigma import eEPGCache
		eEPGCache.getInstance().setEpgHistorySeconds(config.epg.histminutes.getValue() * 60)
	config.epg.histminutes.addNotifier(EpgHistorySecondsChanged)

	config.epg.cacheloadsched = ConfigYesNo(default=False)
	config.epg.cachesavesched = ConfigYesNo(default=False)

	def EpgCacheLoadSchedChanged(configElement):
		from Components import EpgLoadSave
		EpgLoadSave.EpgCacheLoadCheck()

	def EpgCacheSaveSchedChanged(configElement):
		from Components import EpgLoadSave
		EpgLoadSave.EpgCacheSaveCheck()
	config.epg.cacheloadsched.addNotifier(EpgCacheLoadSchedChanged, immediate_feedback=False)
	config.epg.cachesavesched.addNotifier(EpgCacheSaveSchedChanged, immediate_feedback=False)
	config.epg.cacheloadtimer = ConfigSelectionNumber(default=24, stepwidth=1, min=1, max=24, wraparound=True)
	config.epg.cachesavetimer = ConfigSelectionNumber(default=24, stepwidth=1, min=1, max=24, wraparound=True)

	hddchoises = [("/etc/enigma2/", "Internal Flash")]
	for p in harddiskmanager.getMountedPartitions():
		if exists(p.mountpoint):
			d = normpath(p.mountpoint)
			if p.mountpoint != "/":
				hddchoises.append((p.mountpoint, d))
	config.misc.epgcachepath = ConfigSelection(default="/etc/enigma2/", choices=hddchoises)
	config.misc.epgcachefilename = ConfigText(default="epg", fixed_size=False)
	config.misc.epgcache_filename = ConfigText(default=pathjoin(config.misc.epgcachepath.value, "%s.dat" % config.misc.epgcachefilename.value.replace(".dat", "")))

	def EpgCacheChanged(configElement):
		config.misc.epgcache_filename.setValue(pathjoin(config.misc.epgcachepath.value, "%s.dat" % config.misc.epgcachefilename.value.replace(".dat", "")))
		config.misc.epgcache_filename.save()
		eEPGCache.getInstance().setCacheFile(config.misc.epgcache_filename.value)
		epgcache = eEPGCache.getInstance()
		epgcache.save()
		if not config.misc.epgcache_filename.value.startswith("/etc/enigma2/"):
			if exists(pathjoin("/etc/enigma2", "%s.dat" % config.misc.epgcachefilename.value.replace(".dat", ""))):
				remove(pathjoin("/etc/enigma2", "%s.dat" % config.misc.epgcachefilename.value.replace(".dat", "")))
	config.misc.epgcachepath.addNotifier(EpgCacheChanged, immediate_feedback=False)
	config.misc.epgcachefilename.addNotifier(EpgCacheChanged, immediate_feedback=False)

	config.misc.epgratingcountry = ConfigSelection(default="", choices=[
		("", _("Auto detect")),
		("ETSI", _("Generic")),
		("AUS", _("Australia"))
	])
	config.misc.epggenrecountry = ConfigSelection(default="", choices=[
		("", _("Auto detect")),
		("ETSI", _("Generic")),
		("AUS", _("Australia"))
	])

	config.misc.showradiopic = ConfigYesNo(default=True)

	def setHDDStandby(configElement):
		for hdd in harddiskmanager.HDDList():
			hdd[1].setIdleTime(int(configElement.value))
	config.usage.hdd_standby.addNotifier(setHDDStandby, immediate_feedback=False)

	if BoxInfo.getItem("12V_Output"):
		def set12VOutput(configElement):
			Misc_Options.getInstance().set_12V_output(configElement.value == "on" and 1 or 0)
		config.usage.output_12V.addNotifier(set12VOutput, immediate_feedback=False)

	config.usage.keymap = ConfigText(default=eEnv.resolve("${datadir}/enigma2/keymap.xml"))
	config.usage.keytrans = ConfigText(default=eEnv.resolve("${datadir}/enigma2/keytranslation.xml"))
	config.usage.alternative_imagefeed = ConfigText(default="", fixed_size=False)

	config.crash = ConfigSubsection()

	def updateStackTracePrinter(configElement):
		from Components.StackTrace import StackTracePrinter
		if configElement.value:
			if (isfile("/tmp/doPythonStackTrace")):
				remove("/tmp/doPythonStackTrace")
			from threading import current_thread
			StackTracePrinter.getInstance().activate(current_thread().ident)
		else:
			StackTracePrinter.getInstance().deactivate()

	config.crash.pythonStackOnSpinner = ConfigYesNo(default=False)
	config.crash.pythonStackOnSpinner.addNotifier(updateStackTracePrinter, immediate_feedback=False, initial_call=True)
	config.crash.debugLevel = ConfigSelection(choices=[
		("3", _("No")),
		("4", _("Yes"))
	], default="3")
	config.crash.debugLevel.save_forced = True
	# The config.crash.debugTimeFormat item is used to set ENIGMA_DEBUG_TIME environmental variable on enigma2 start from enigma2.sh.
	config.crash.debugTimeFormat = ConfigSelection(choices=[
		("0", _("None")),
		("1", _("Boot time")),
		("2", _("Local time")),
		("3", _("Boot time and local time")),
		("6", _("Local date/time")),
		("7", _("Boot time and local data/time"))
	], default="1")
	config.crash.debugTimeFormat.save_forced = True
	debugPath = [
		("/home/root/logs/", "/home/root/")
	]
	for partition in harddiskmanager.getMountedPartitions():
		if exists(partition.mountpoint):
			path = normpath(partition.mountpoint)
			if partition.mountpoint != "/":
				debugPath.append((pathjoin(partition.mountpoint, "logs", ""), path))
	config.crash.debugPath = ConfigSelection(default="/home/root/logs/", choices=debugPath)

	def updateDebugPath(configElement):
		if not exists(config.crash.debugPath.value):
			mkdir(config.crash.debugPath.value, 0o755)

	config.crash.debugPath.addNotifier(updateDebugPath, immediate_feedback=False)
	config.crash.debugFileCount = ConfigSelectionNumber(min=2, max=20, stepwidth=1, default=5, wraparound=True)
	config.crash.debugFileCount.save_forced = True

	config.seek = ConfigSubsection()
	config.seek.selfdefined_13 = ConfigNumber(default=15)
	config.seek.selfdefined_46 = ConfigNumber(default=60)
	config.seek.selfdefined_79 = ConfigNumber(default=300)

	config.seek.speeds_forward = ConfigSet(default=[2, 4, 8, 16, 32, 64, 128], choices=[2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128])
	config.seek.speeds_backward = ConfigSet(default=[2, 4, 8, 16, 32, 64, 128], choices=[1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128])
	config.seek.speeds_slowmotion = ConfigSet(default=[2, 4, 8], choices=[2, 4, 6, 8, 12, 16, 25])

	config.seek.enter_forward = ConfigSelection(default=2, choices=[2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128])
	config.seek.enter_backward = ConfigSelection(default=1, choices=[1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128])

	config.seek.on_pause = ConfigSelection(default="play", choices=[
		("play", _("Play")),
		("step", _("Single step (GOP)")),
		("last", _("Last speed"))])

	config.usage.timerlist_finished_timer_position = ConfigSelection(default="end", choices=[
		("beginning", _("At beginning")),
		("end", _("At end"))
	])

	def updateEnterForward(configElement):
		if not configElement.value:
			configElement.value = [2]
		updateChoices(config.seek.enter_forward, configElement.value)

	config.seek.speeds_forward.addNotifier(updateEnterForward, immediate_feedback=False)

	def updateEnterBackward(configElement):
		if not configElement.value:
			configElement.value = [2]
		updateChoices(config.seek.enter_backward, configElement.value)

	config.seek.speeds_backward.addNotifier(updateEnterBackward, immediate_feedback=False)

	def updateEraseSpeed(el):
		eBackgroundFileEraser.getInstance().setEraseSpeed(int(el.value))

	def updateEraseFlags(el):
		eBackgroundFileEraser.getInstance().setEraseFlags(int(el.value))
	config.misc.erase_speed = ConfigSelection(default="20", choices=[
		("10", _("10 MB/s")),
		("20", _("20 MB/s")),
		("50", _("50 MB/s")),
		("100", _("100 MB/s"))])
	config.misc.erase_speed.addNotifier(updateEraseSpeed, immediate_feedback=False)
	config.misc.erase_flags = ConfigSelection(default="1", choices=[
		("0", _("Disable")),
		("1", _("Internal hdd only")),
		("3", _("Everywhere"))])
	config.misc.erase_flags.addNotifier(updateEraseFlags, immediate_feedback=False)

	config.misc.zapkey_delay = ConfigSelectionNumber(default=5, stepwidth=1, min=0, max=20, wraparound=True)
	config.misc.numzap_picon = ConfigYesNo(default=False)

	if BoxInfo.getItem("ZapMode"):
		def setZapmode(el):
			open(BoxInfo.getItem("ZapMode"), "w").write(el.value)
		config.misc.zapmode = ConfigSelection(default="mute", choices=[
			("mute", _("Black screen")),
			("hold", _("Hold screen")),
			("mutetilllock", _("Black screen till locked")),
			("holdtilllock", _("Hold till locked"))
		])
		config.misc.zapmode.addNotifier(setZapmode, immediate_feedback=False)

	if BoxInfo.getItem("HasBypassEdidChecking"):
		def setHasBypassEdidChecking(configElement):
			open(BoxInfo.getItem("HasBypassEdidChecking"), "w").write("00000001" if configElement.value else "00000000")
		config.av.bypassEdidChecking = ConfigYesNo(default=False)
		config.av.bypassEdidChecking.addNotifier(setHasBypassEdidChecking)

	if BoxInfo.getItem("HasColorspace"):
		def setHaveColorspace(configElement):
			open(BoxInfo.getItem("HasColorspace"), "w").write(configElement.value)
		if BoxInfo.getItem("HasColorspaceSimple"):
			config.av.hdmicolorspace = ConfigSelection(default="Edid(Auto)", choices={
				"Edid(Auto)": _("Auto"),
				"Hdmi_Rgb": _("RGB"),
				"444": _("YCbCr444"),
				"422": _("YCbCr422"),
				"420": _("YCbCr420")
			})
		else:
			if model == "vuzero4k" or BoxInfo.getItem("platform") == "dm4kgen":
				config.av.hdmicolorspace = ConfigSelection(default="Edid(Auto)", choices={
					"Edid(Auto)": _("Auto"),
					"Hdmi_Rgb": _("RGB"),
					"Itu_R_BT_709": _("BT709"),
					"DVI_Full_Range_RGB": _("Full Range RGB"),
					"FCC": _("FCC 1953"),
					"Itu_R_BT_470_2_BG": _("BT470 BG"),
					"Smpte_170M": _("Smpte 170M"),
					"Smpte_240M": _("Smpte 240M"),
					"Itu_R_BT_2020_NCL": _("BT2020 NCL"),
					"Itu_R_BT_2020_CL": _("BT2020 CL"),
					"XvYCC_709": _("BT709 XvYCC"),
					"XvYCC_601": _("BT601 XvYCC")
				})
			else:
				config.av.hdmicolorspace = ConfigSelection(default="auto", choices={
					"auto": _("Auto"),
					"rgb": _("RGB"),
					"420": _("420"),
					"422": _("422"),
					"444": _("444")
				})
		config.av.hdmicolorspace.addNotifier(setHaveColorspace)

	if BoxInfo.getItem("HasColordepth"):
		def setHaveColordepth(configElement):
			open(BoxInfo.getItem("HasColordepth"), "w").write(configElement.value)
		config.av.hdmicolordepth = ConfigSelection(default="auto", choices={
			"auto": _("Auto"),
			"8bit": _("8 bit"),
			"10bit": _("10 bit"),
			"12bit": _("12 bit")
		})
		config.av.hdmicolordepth.addNotifier(setHaveColordepth)

	if BoxInfo.getItem("HasHDMIpreemphasis"):
		def setHDMIpreemphasis(configElement):
			open(BoxInfo.getItem("HasHDMIpreemphasis"), "w").write("on" if configElement.value else "off")
		config.av.hdmipreemphasis = ConfigYesNo(default=False)
		config.av.hdmipreemphasis.addNotifier(setHDMIpreemphasis)

	if BoxInfo.getItem("HasColorimetry"):
		def setColorimetry(configElement):
			open(BoxInfo.getItem("HasColorimetry"), "w").write(configElement.value)
		config.av.hdmicolorimetry = ConfigSelection(default="auto", choices=[
			("auto", _("Auto")),
			("bt2020ncl", _("BT 2020 NCL")),
			("bt2020cl", _("BT 2020 CL")),
			("bt709", _("BT 709"))
		])
		config.av.hdmicolorimetry.addNotifier(setColorimetry)

	if BoxInfo.getItem("HasHdrType"):
		def setHdmiHdrType(configElement):
			open(BoxInfo.getItem("HasHdrType"), "w").write(configElement.value)
		config.av.hdmihdrtype = ConfigSelection(default="auto", choices={
			"auto": _("Auto"),
			"none": _("SDR"),
			"hdr10": _("HDR10"),
			"hlg": _("HLG"),
			"dolby": _("Dolby")
		})
		config.av.hdmihdrtype.addNotifier(setHdmiHdrType)

	if BoxInfo.getItem("HDRSupport"):
		def setHlgSupport(configElement):
			print("[UsageConfig] Read /proc/stb/hdmi/hlg_support")
			open("/proc/stb/hdmi/hlg_support", "w").write(configElement.value)
		config.av.hlg_support = ConfigSelection(default="auto(EDID)", choices=[
			("auto(EDID)", _("Controlled by HDMI")),
			("yes", _("Force enabled")),
			("no", _("Force disabled"))
		])
		config.av.hlg_support.addNotifier(setHlgSupport)

		def setHdr10Support(configElement):
			print("[UsageConfig] Read /proc/stb/hdmi/hdr10_support")
			open("/proc/stb/hdmi/hdr10_support", "w").write(configElement.value)
		config.av.hdr10_support = ConfigSelection(default="auto(EDID)", choices=[
			("auto(EDID)", _("Controlled by HDMI")),
			("yes", _("Force enabled")),
			("no", _("Force disabled"))
		])
		config.av.hdr10_support.addNotifier(setHdr10Support)

		def setDisable12Bit(configElement):
			print("[UsageConfig] Read /proc/stb/video/disable_12bit")
			open("/proc/stb/video/disable_12bit", "w").write("on" if configElement.value else "off")
		config.av.allow_12bit = ConfigYesNo(default=False)
		config.av.allow_12bit.addNotifier(setDisable12Bit)

		def setDisable10Bit(configElement):
			print("[UsageConfig] Read /proc/stb/video/disable_10bit")
			open("/proc/stb/video/disable_10bit", "w").write("on" if configElement.value else "off")
		config.av.allow_10bit = ConfigYesNo(default=False)
		config.av.allow_10bit.addNotifier(setDisable10Bit)

	if BoxInfo.getItem("CanSyncMode"):
		def setSyncMode(configElement):
			print("[UsageConfig] Read /proc/stb/video/sync_mode")
			open("/proc/stb/video/sync_mode", "w").write(configElement.value)
		config.av.sync_mode = ConfigSelection(default="slow", choices={
			"slow": _("Slow motion"),
			"hold": _("Hold first frame"),
			"black": _("Black screen")
		})
		config.av.sync_mode.addNotifier(setSyncMode)

	config.subtitles = ConfigSubsection()
	config.subtitles.show = ConfigYesNo(default=True)
	config.subtitles.ttx_subtitle_colors = ConfigSelection(default="1", choices=[
		("0", _("Original")),
		("1", _("White")),
		("2", _("Yellow"))
	])
	config.subtitles.ttx_subtitle_original_position = ConfigYesNo(default=False)
	config.subtitles.ttx_subtitle_position = ConfigSelection(default="50", choices=[
		"0",
		"10",
		"20",
		"30",
		"40",
		"50",
		"60",
		"70",
		"80",
		"90",
		"100",
		"150",
		"200",
		"250",
		"300",
		"350",
		"400",
		"450"
	])
	config.subtitles.subtitle_alignment = ConfigSelection(default="center", choices=[
		("left", _("Left")),
		("center", _("Center")),
		("right", _("Right"))
	])
	config.subtitles.subtitle_rewrap = ConfigYesNo(default=False)
	config.subtitles.colourise_dialogs = ConfigYesNo(default=False)
	config.subtitles.subtitle_borderwidth = ConfigSelection(default="3", choices=["%d" % x for x in range(1, 6)])
	config.subtitles.subtitle_fontsize = ConfigSelection(default="40", choices=["%d" % x for x in range(16, 101) if not x % 2])
	config.subtitles.showbackground = ConfigYesNo(default=False)

	subtitle_delay_choicelist = []
	for i in range(-900000, 1845000, 45000):
		if i == 0:
			subtitle_delay_choicelist.append(("0", _("No delay")))
		else:
			subtitle_delay_choicelist.append((str(i), _("%2.1f sec") % (i / 90000.)))
	config.subtitles.subtitle_noPTSrecordingdelay = ConfigSelection(default="315000", choices=subtitle_delay_choicelist)

	config.subtitles.dvb_subtitles_yellow = ConfigYesNo(default=False)
	config.subtitles.dvb_subtitles_original_position = ConfigSelection(default="0", choices=[
		("0", _("Original")),
		("1", _("Fixed")),
		("2", _("Relative"))
	])
	config.subtitles.subtitle_position = ConfigSelection(default="50", choices=[
		"0",
		"10",
		"20",
		"30",
		"40",
		"50",
		"60",
		"70",
		"80",
		"90",
		"100",
		"150",
		"200",
		"250",
		"300",
		"350",
		"400",
		"450"
	])
	config.subtitles.dvb_subtitles_centered = ConfigYesNo(default=False)
	config.subtitles.subtitle_bad_timing_delay = ConfigSelection(default="0", choices=subtitle_delay_choicelist)
	config.subtitles.dvb_subtitles_backtrans = ConfigSelection(default="0", choices=[
		("0", _("No transparency")),
		("25", _("10%")),
		("50", _("20%")),
		("75", _("30%")),
		("100", _("40%")),
		("125", _("50%")),
		("150", _("60%")),
		("175", _("70%")),
		("200", _("80%")),
		("225", _("90%")),
		("255", _("Full transparency"))
	])
	config.subtitles.pango_subtitle_colors = ConfigSelection(default="1", choices=[
		("0", _("Alternative")),
		("1", _("White")),
		("2", _("Yellow"))
	])
	config.subtitles.pango_subtitle_fontswitch = ConfigYesNo(default=True)
	config.subtitles.pango_subtitles_delay = ConfigSelection(default="0", choices=subtitle_delay_choicelist)
	config.subtitles.pango_subtitles_fps = ConfigSelection(default="1", choices=[
		("1", _("Original")),
		("23976", _("23.976")),
		("24000", _("24")),
		("25000", _("25")),
		("29970", _("29.97")),
		("30000", _("30"))
	])
	config.subtitles.pango_subtitle_removehi = ConfigYesNo(default=False)
	config.subtitles.pango_autoturnon = ConfigYesNo(default=True)

	config.autolanguage = ConfigSubsection()
	audio_language_choices = [
		("", _("None")),
		("orj dos ory org esl qaa und mis mul ORY ORJ Audio_ORJ", _("Original")),
		("ara", _("Arabic")),
		("eus baq", _("Basque")),
		("bul", _("Bulgarian")),
		("hrv", _("Croatian")),
		("chn sgp", _("Chinese - Simplified")),
		("twn hkn", _("Chinese - Traditional")),
		("ces cze", _("Czech")),
		("dan", _("Danish")),
		("dut ndl nld", _("Dutch")),
		("eng qaa", _("English")),
		("est", _("Estonian")),
		("fin", _("Finnish")),
		("fra fre", _("French")),
		("deu ger", _("German")),
		("ell gre grc", _("Greek")),
		("heb", _("Hebrew")),
		("hun", _("Hungarian")),
		("ind", _("Indonesian")),
		("ita", _("Italian")),
		("lav", _("Latvian")),
		("lit", _("Lithuanian")),
		("ltz", _("Luxembourgish")),
		("nor", _("Norwegian")),
		("fas per fa pes", _("Persian")),
		("pol", _("Polish")),
		("por dub Dub DUB ud1", _("Portuguese")),
		("ron rum", _("Romanian")),
		("rus", _("Russian")),
		("srp", _("Serbian")),
		("slk slo", _("Slovak")),
		("slv", _("Slovenian")),
		("spa", _("Spanish")),
		("swe", _("Swedish")),
		("tha", _("Thai")),
		("tur Audio_TUR", _("Turkish")),
		("ukr Ukr", _("Ukrainian"))
	]

	epg_language_choices = audio_language_choices[:1] + audio_language_choices[2:]

	def setEpgLanguage(configElement):
		eServiceEvent.setEPGLanguage(configElement.value)

	def setEpgLanguageAlternative(configElement):
		eServiceEvent.setEPGLanguageAlternative(configElement.value)

	def epglanguage(configElement):
		config.autolanguage.audio_epglanguage.setChoices([x for x in epg_language_choices if x[0] and x[0] != config.autolanguage.audio_epglanguage_alternative.value or not x[0] and not config.autolanguage.audio_epglanguage_alternative.value])
		config.autolanguage.audio_epglanguage_alternative.setChoices([x for x in epg_language_choices if x[0] and x[0] != config.autolanguage.audio_epglanguage.value or not x[0]])
	config.autolanguage.audio_epglanguage = ConfigSelection(default="", choices=epg_language_choices)
	config.autolanguage.audio_epglanguage_alternative = ConfigSelection(default="", choices=epg_language_choices)
	config.autolanguage.audio_epglanguage.addNotifier(setEpgLanguage)
	config.autolanguage.audio_epglanguage.addNotifier(epglanguage, initial_call=False)
	config.autolanguage.audio_epglanguage_alternative.addNotifier(setEpgLanguageAlternative)
	config.autolanguage.audio_epglanguage_alternative.addNotifier(epglanguage)

	def getselectedlanguages(range):
		return [eval("config.autolanguage.audio_autoselect%x.value" % x) for x in range]

	def autolanguage(configElement):
		config.autolanguage.audio_autoselect1.setChoices([x for x in audio_language_choices if x[0] and x[0] not in getselectedlanguages((2, 3, 4)) or not x[0] and not config.autolanguage.audio_autoselect2.value])
		config.autolanguage.audio_autoselect2.setChoices([x for x in audio_language_choices if x[0] and x[0] not in getselectedlanguages((1, 3, 4)) or not x[0] and not config.autolanguage.audio_autoselect3.value])
		config.autolanguage.audio_autoselect3.setChoices([x for x in audio_language_choices if x[0] and x[0] not in getselectedlanguages((1, 2, 4)) or not x[0] and not config.autolanguage.audio_autoselect4.value])
		config.autolanguage.audio_autoselect4.setChoices([x for x in audio_language_choices if x[0] and x[0] not in getselectedlanguages((1, 2, 3)) or not x[0]])
	config.autolanguage.audio_autoselect1 = ConfigSelection(default="", choices=audio_language_choices)
	config.autolanguage.audio_autoselect2 = ConfigSelection(default="", choices=audio_language_choices)
	config.autolanguage.audio_autoselect3 = ConfigSelection(default="", choices=audio_language_choices)
	config.autolanguage.audio_autoselect4 = ConfigSelection(default="", choices=audio_language_choices)
	config.autolanguage.audio_autoselect1.addNotifier(autolanguage, initial_call=False)
	config.autolanguage.audio_autoselect2.addNotifier(autolanguage, initial_call=False)
	config.autolanguage.audio_autoselect3.addNotifier(autolanguage, initial_call=False)
	config.autolanguage.audio_autoselect4.addNotifier(autolanguage)
	config.autolanguage.audio_defaultac3 = ConfigYesNo(default=True)
	config.autolanguage.audio_defaultddp = ConfigYesNo(default=False)
	config.autolanguage.audio_usecache = ConfigYesNo(default=True)

	subtitle_language_choices = audio_language_choices[:1] + audio_language_choices[2:]

	def getselectedsublanguages(range):
		return [eval("config.autolanguage.subtitle_autoselect%x.value" % x) for x in range]

	def autolanguagesub(configElement):
		config.autolanguage.subtitle_autoselect1.setChoices([x for x in subtitle_language_choices if x[0] and x[0] not in getselectedsublanguages((2, 3, 4)) or not x[0] and not config.autolanguage.subtitle_autoselect2.value])
		config.autolanguage.subtitle_autoselect2.setChoices([x for x in subtitle_language_choices if x[0] and x[0] not in getselectedsublanguages((1, 3, 4)) or not x[0] and not config.autolanguage.subtitle_autoselect3.value])
		config.autolanguage.subtitle_autoselect3.setChoices([x for x in subtitle_language_choices if x[0] and x[0] not in getselectedsublanguages((1, 2, 4)) or not x[0] and not config.autolanguage.subtitle_autoselect4.value])
		config.autolanguage.subtitle_autoselect4.setChoices([x for x in subtitle_language_choices if x[0] and x[0] not in getselectedsublanguages((1, 2, 3)) or not x[0]])
		choicelist = [("0", _("None"))]
		for y in range(1, 15 if config.autolanguage.subtitle_autoselect4.value else (7 if config.autolanguage.subtitle_autoselect3.value else(4 if config.autolanguage.subtitle_autoselect2.value else (2 if config.autolanguage.subtitle_autoselect1.value else 0)))):
			choicelist.append((str(y), ", ".join([eval("config.autolanguage.subtitle_autoselect%x.getText()" % x) for x in (y & 1, y & 2, y & 4 and 3, y & 8 and 4) if x])))
		if config.autolanguage.subtitle_autoselect3.value:
			choicelist.append((str(y + 1), "All"))
		config.autolanguage.equal_languages.setChoices(choicelist, default="0")
	config.autolanguage.equal_languages = ConfigSelection(default="0", choices=[str(x) for x in range(0, 16)])
	config.autolanguage.subtitle_autoselect1 = ConfigSelection(default="", choices=subtitle_language_choices)
	config.autolanguage.subtitle_autoselect2 = ConfigSelection(default="", choices=subtitle_language_choices)
	config.autolanguage.subtitle_autoselect3 = ConfigSelection(default="", choices=subtitle_language_choices)
	config.autolanguage.subtitle_autoselect4 = ConfigSelection(default="", choices=subtitle_language_choices)
	config.autolanguage.subtitle_autoselect1.addNotifier(autolanguagesub, initial_call=False)
	config.autolanguage.subtitle_autoselect2.addNotifier(autolanguagesub, initial_call=False)
	config.autolanguage.subtitle_autoselect3.addNotifier(autolanguagesub, initial_call=False)
	config.autolanguage.subtitle_autoselect4.addNotifier(autolanguagesub)
	config.autolanguage.subtitle_hearingimpaired = ConfigYesNo(default=False)
	config.autolanguage.subtitle_defaultimpaired = ConfigYesNo(default=False)
	config.autolanguage.subtitle_defaultdvb = ConfigYesNo(default=False)
	config.autolanguage.subtitle_usecache = ConfigYesNo(default=True)

	config.visionsettings = ConfigSubsection()

	config.oscaminfo = ConfigSubsection()
	if BoxInfo.getItem("OScamInstalled") or BoxInfo.getItem("NCamInstalled"):
		config.oscaminfo.showInExtensions = ConfigYesNo(default=True)
	else:
		config.oscaminfo.showInExtensions = ConfigYesNo(default=False)
	config.oscaminfo.userdatafromconf = ConfigYesNo(default=True)
	config.oscaminfo.autoupdate = ConfigYesNo(default=False)
	config.oscaminfo.username = ConfigText(default="username", fixed_size=False, visible_width=12)
	config.oscaminfo.password = ConfigPassword(default="password", fixed_size=False)
	config.oscaminfo.ip = ConfigIP(default=[127, 0, 0, 1], auto_jump=True)
	config.oscaminfo.port = ConfigInteger(default=16002, limits=(0, 65536))
	config.oscaminfo.intervall = ConfigSelectionNumber(min=1, max=600, stepwidth=1, default=10, wraparound=True)

	config.streaming = ConfigSubsection()
	config.streaming.stream_ecm = ConfigYesNo(default=False)
	config.streaming.descramble = ConfigYesNo(default=True)
	config.streaming.descramble_client = ConfigYesNo(default=False)
	config.streaming.stream_eit = ConfigYesNo(default=True)
	config.streaming.stream_ait = ConfigYesNo(default=True)
	config.streaming.authentication = ConfigYesNo(default=False)

	config.mediaplayer = ConfigSubsection()
	config.mediaplayer.useAlternateUserAgent = ConfigYesNo(default=False)
	config.mediaplayer.alternateUserAgent = ConfigText(default="")

	config.misc.softcam_setup = ConfigSubsection()
	config.misc.softcam_setup.extension_menu = ConfigYesNo(default=True)

	config.ntp = ConfigSubsection()

	def timesyncChanged(configElement):
		if configElement.value == "dvb" or not GetIPsFromNetworkInterfaces():
			eDVBLocalTimeHandler.getInstance().setUseDVBTime(True)
			eEPGCache.getInstance().timeUpdated()
			if configElement.value == "dvb" and islink("/etc/network/if-up.d/ntpdate-sync"):
				Console().ePopen("sed -i '/ntpdate-sync/d' /etc/cron/crontabs/root;unlink /etc/network/if-up.d/ntpdate-sync")
		else:
			eDVBLocalTimeHandler.getInstance().setUseDVBTime(False)
			eEPGCache.getInstance().timeUpdated()
			if not islink("/etc/network/if-up.d/ntpdate-sync"):
				Console().ePopen("echo '30 * * * * /usr/bin/ntpdate-sync silent' >>/etc/cron/crontabs/root;ln -s /usr/bin/ntpdate-sync /etc/network/if-up.d/ntpdate-sync")
	config.ntp.timesync = ConfigSelection(default="ntp", choices=[
		("auto", _("Auto")),
		("dvb", _("Transponder time")),
		("ntp", _("Internet time (NTP)"))
	])
	config.ntp.timesync.addNotifier(timesyncChanged)
	config.ntp.server = ConfigText("pool.ntp.org", fixed_size=False)


def updateChoices(sel, choices):
	if choices:
		defval = None
		val = int(sel.value)
		if not val in choices:
			tmp = choices[:]
			tmp.reverse()
			for x in tmp:
				if x < val:
					defval = str(x)
					break
		sel.setChoices(list(map(str, choices)), defval)


def preferredPath(path):
	if config.usage.setup_level.index < 2 or path == "<default>" or not path:
		return None	 # config.usage.default_path.value, but delay lookup until usage
	elif path == "<current>":
		return config.movielist.last_videodir.value
	elif path == "<timer>":
		return config.movielist.last_timer_videodir.value
	else:
		return path


def preferredTimerPath():
	return preferredPath(config.usage.timer_path.value)


def preferredInstantRecordPath():
	return preferredPath(config.usage.instantrec_path.value)


def defaultMoviePath():
	return defaultRecordingLocation(config.usage.default_path.value)


def showrotorpositionChoicesUpdate(update=False):
	choiceslist = [("no", _("no")), ("yes", _("yes")), ("withtext", _("with text")), ("tunername", _("with tuner name"))]
	count = 0
	for x in nimmanager.nim_slots:
		if nimmanager.getRotorSatListForNim(x.slot, only_first=True):
			choiceslist.append((str(x.slot), x.getSlotName() + _(" (auto detection)")))
			count += 1
	if count > 1:
		choiceslist.append(("all", _("all tuners") + _(" (auto detection)")))
		choiceslist.remove(("tunername", _("with tuner name")))
	if not update:
		config.misc.showrotorposition = ConfigSelection(default="no", choices=choiceslist)
	else:
		config.misc.showrotorposition.setChoices(choiceslist, "no")
	BoxInfo.setItem("isRotorTuner", count > 0)


def patchTuxtxtConfFile(dummyConfigElement):
	print("[UsageConfig] patching tuxtxt2.conf")
	if config.usage.tuxtxt_font_and_res.value == "X11_SD":
		tuxtxt2 = [
			["UseTTF", 0],
			["TTFBold", 1],
			["TTFScreenResX", 720],
			["StartX", 50],
			["EndX", 670],
			["StartY", 30],
			["EndY", 555],
			["TTFShiftY", 0],
			["TTFShiftX", 0],
			["TTFWidthFactor16", 26],
			["TTFHeightFactor16", 14]
		]
	elif config.usage.tuxtxt_font_and_res.value == "TTF_SD":
		tuxtxt2 = [
			["UseTTF", 1],
			["TTFBold", 1],
			["TTFScreenResX", 720],
			["StartX", 50],
			["EndX", 670],
			["StartY", 30],
			["EndY", 555],
			["TTFShiftY", 2],
			["TTFShiftX", 0],
			["TTFWidthFactor16", 29],
			["TTFHeightFactor16", 14]
		]
	elif config.usage.tuxtxt_font_and_res.value == "TTF_HD":
		tuxtxt2 = [
			["UseTTF", 1],
			["TTFBold", 0],
			["TTFScreenResX", 1280],
			["StartX", 80],
			["EndX", 1200],
			["StartY", 35],
			["EndY", 685],
			["TTFShiftY", -3],
			["TTFShiftX", 0],
			["TTFWidthFactor16", 26],
			["TTFHeightFactor16", 14]
		]
	elif config.usage.tuxtxt_font_and_res.value == "TTF_FHD":
		tuxtxt2 = [
			["UseTTF", 1],
			["TTFBold", 0],
			["TTFScreenResX", 1920],
			["StartX", 140],
			["EndX", 1780],
			["StartY", 52],
			["EndY", 1027],
			["TTFShiftY", -6],
			["TTFShiftX", 0],
			["TTFWidthFactor16", 26],
			["TTFHeightFactor16", 14]
		]
	elif config.usage.tuxtxt_font_and_res.value == "expert_mode":
		tuxtxt2 = [
			["UseTTF", int(config.usage.tuxtxt_UseTTF.value)],
			["TTFBold", int(config.usage.tuxtxt_TTFBold.value)],
			["TTFScreenResX", int(config.usage.tuxtxt_TTFScreenResX.value)],
			["StartX", config.usage.tuxtxt_StartX.value],
			["EndX", config.usage.tuxtxt_EndX.value],
			["StartY", config.usage.tuxtxt_StartY.value],
			["EndY", config.usage.tuxtxt_EndY.value],
			["TTFShiftY", int(config.usage.tuxtxt_TTFShiftY.value)],
			["TTFShiftX", int(config.usage.tuxtxt_TTFShiftX.value)],
			["TTFWidthFactor16", config.usage.tuxtxt_TTFWidthFactor16.value],
			["TTFHeightFactor16", config.usage.tuxtxt_TTFHeightFactor16.value]
		]
	tuxtxt2.append(["CleanAlgo", config.usage.tuxtxt_CleanAlgo.value])

	TUXTXT_CFG_FILE = "/etc/tuxtxt/tuxtxt2.conf"
	command = "sed -i -r '"
	for f in tuxtxt2:
		# replace keyword (%s) followed by any value ([-0-9]+) by that keyword \1 and the new value %d
		command += "s|(%s)\s+([-0-9]+)|\\1 %d|;" % (f[0], f[1])
	command += "' %s" % TUXTXT_CFG_FILE
	for f in tuxtxt2:
		# if keyword is not found in file, append keyword and value
		command += " ; if ! grep -q '%s' %s ; then echo '%s %d' >> %s ; fi" % (f[0], TUXTXT_CFG_FILE, f[0], f[1], TUXTXT_CFG_FILE)
	try:
		Console().ePopen(command)
	except:
		print("[UsageConfig] Error: failed to patch %s!" % TUXTXT_CFG_FILE)
	print("[UsageConfig] patched tuxtxt2.conf")

	config.usage.tuxtxt_ConfFileHasBeenPatched.setValue(True)
