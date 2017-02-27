#!/usr/bin/python3

import os
import time
import glob
import sys
import logging
from logging import info, debug, warning, error, critical
logging.basicConfig(level=logging.DEBUG)

class ThermalDevice(object):

	def _getint(self,path):
		f = open(path,"r")
		a = int(f.read())
		f.close()
		return a

	def _getints(self,path):
		f = open(path,"r")
		ints = []
		for i in f.read().split():
			ints.append(int(i))
		f.close()
		return ints

	def _put(self,path,s):
		try:
			f = open(path,'w')
			f.write(s)
			f.close()
		except OSError:
			critical("error writing %s to %s" % (s, path))

	def _putint(self,path,i):
		try:
			f = open(path,'w')
			f.write(str(i))
			f.close()
		except OSError:
			critical("error writing %s to %s" % (i, path))

	def get(self):
		return self._getint(self.path)

	def modprobe(self, mod):
		debug("Loading module %s" % mod)
		return subprocess.call(["/sbin/modprobe", mod ])


class ThinkpadFan(ThermalDevice):

	@property
	def enabled(self):
		debug("Checking to see if ThinkPad fan is enabled")
		return os.path.exists('/proc/acpi/ibm/fan')

	def activate(self):
		if not self.enabled:
			self.modprobe('thinkpad_acpi')

	def __init__(self):
		self.activate()
		self.level = 0
		self.max_level = 8
		if self.enabled:
			debug("Thinkpad fan enabled. Setting start level to 3.")
			self.set_level(3)
		else:
			debug("Could not detect ThinkPad fan.")
	
	def lower(self):
		if self.level == 0:
			pass
		else:
			self.level -= 1
		self.set_level(self.level)

	def upper(self):
		if self.level == 8:
			pass
		else:
			self.level += 1
		self.set_level(self.level)

	def set_level(self,level):
		self.level = level
		if level == 8:
			level = "disengaged"
		else:
			level = str(level)
		self._put('/proc/acpi/ibm/fan', 'level ' + level)

class IntelPowerClamp(ThermalDevice):

	@property
	def enabled(self):
		debug("Checking to see if Intel PowerClamp is available")
		return self.path != None

	def detect(self):
		self.path = None
		debug("Attempting to locate Intel PowerClamp cooling device")
		for path in glob.glob('/sys/class/thermal/cooling_device*/'):
			if os.path.exists(path + '/type'):
				ty = getContents(path + '/type')
				if ty == 'intel_powerclamp':
					debug("Found Intel PowerClamp")
					self.path = path + '/cur_state'
	
	def __init__(self):
		self.detect()
		if self.path == None:
			self.modprobe('intel_powerclamp')
			self.detect()
			if self.path == None:
				warn("Could not find intel_powerclamp cooling device.")

	def get_level(self):
		return self._getint(self.path)

	def set_level(self,level):
		self._putint(self.path, level)

class IntelPState(ThermalDevice):
	base_path = '/sys/devices/system/cpu/intel_pstate'

	@property
	def enabled(self):
		debug("Checking to see if Intel PState driver is available")
		return os.path.exists(self.base_path)

	def __init__(self):
		if not self.enabled:
			self.modprobe("intel_pstate")
			if not self.enabled:
				warn("Intel PState driver is NOT available")
		if self.enabled:
			debug("Found Intel PState driver.")
		self._putint(self.base_path + '/max_perf_pct', 100)
		self._putint(self.base_path + '/min_perf_pct', 1)
		self.level = self._getint(self.base_path + '/max_perf_pct')
	
	def set_level(self, level):
		self._putint(self.base_path + '/max_perf_pct', level)
		self.level = level

	def upper(self):
		self.level += 1
		if self.level > 100:
			self.level = 100
		self.set_level(self.level)

def getContents(path):
	if os.path.exists(path):
		a = open(path,'r')
		contents = a.read()
		a.close()
		return contents.strip()
	else:
		return None

sensors=[]

def scanPath(scanpath, prefixglob='*'):
	if os.path.isdir(scanpath):
		return glob.glob(scanpath + '/' + prefixglob)
	return []

# ZONE SENSORS
for dirpath in scanPath('/sys/class/thermal', prefixglob='thermal_zone*'):
	sensors.append({
		'name' : dirpath,
		'temp' : dirpath + '/temp'
	})

# HWMON SENSORS
for dirpath in scanPath('/sys/class/hwmon', prefixglob='hwmon*'):
	temps = []
	for dirpath2 in scanPath(dirpath, prefixglob='temp*_input'):
		temps.append(dirpath2)
	sensors.append({
		'name' : getContents(dirpath + '/name'),
		'temp' : temps
	})

debug("Found %s temperature sensors." % len(sensors))
if len(sensors) == 0:
	critical("I need at least one temp sensor to work. Exiting.")
	sys.exit(1)

def getTemps():
	global sensors
	temps = []
	for sensor in sensors:
		if type(sensor['temp']) == str:
			tempfiles = [ sensor['temp'] ]
		else:
			tempfiles = sensor['temp']
		for temp in tempfiles:
			temps.append(int(getContents(temp)))
	return temps

cpu = IntelPState()
fan = ThinkpadFan()
clamp = IntelPowerClamp()

thresh = 65000
fan_thresh = 50000
count = 0
max_overshoot = 0
max_temp = None
last_max_temp = None
variability_list = []
variability_len = 10
clamp_list = []
clamp_level = 0
max_clamp = 50 
last_fan_count = 0
last_freq_count = 0
cpu.set_level(100)
fan_duration = 0
fan_level = 0
fan.set_level(fan_level)
while True:
	last_max_temp = max_temp
	temps = getTemps()
	max_temp = max(temps)
	avg_temp = sum(temps)/len(temps)
	if (last_max_temp != None):
		velocity = max_temp - last_max_temp
	else:
		velocity = 0

	loadavg = os.getloadavg()[0]

	target_cpu_level = int(loadavg * 100)
	#if loadavg > 2:
	#	target_cpu_level = 80
	if target_cpu_level > 100:
		target_cpu_level = 100

	variability_list.append(max_temp)
	if len(variability_list) > variability_len:
		del(variability_list[0])

	variability = abs(max(variability_list) - min(variability_list))
	if len(variability_list) >=2 and variability_list[-1] >= variability_list[-2]:
		rise = True
	else:
		rise = False

	overtemp = False
	extreme_temp = False
	if (max_temp > 75000):
		overtemp = True
	if (max_temp > 80000):
		extreme_temp = True
	if not overtemp and max_temp > 60000:
		hot = True
	else:
		hot = False
	if not overtemp and not hot and max_temp > 55000:
		warm = True
	else:
		warm = False
	if max_temp < 40000:
		cold = True
	else:
		cold = False
	
	# This fan algorithm works well for AC power, but for battery, we probably want
	# to use modest additional powerclamping rather than turning on the fan, which
	# will save power in two ways -- more idle and less power for fan.

	# current AC algorithm:
	# run fan independently, based on temperature,
	# then, adjust cpu level gradually upwards unless max or overheat (in this case, lower significantly)
	# also clamp if extreme temp, or overtemp and lowering cpu level to 75 does not help.

	# proposed battery algorithm:
	# adjust CPU based on CPU usage, just like AC algorithm.
	# if system is getting hot, try to reign in temps with modest powerclamping.
	# if modest powerclamping appears unsuccessful, then start utilizing fans in parallel with powerclamp.
	# have a less-than-100 max cpu freq (75?) and be slower to raise it up again.

	
	min_fan = 1
	fan_prevlevel = fan_level
	if hot or overtemp:
		fan_level = 8
	elif warm and rise:
		fan_level += 1
	elif warm and not rise:
		if fan_duration > 3:
			fan_level -= 1
	elif not warm or not hot or not overtemp:
		fan_level = min_fan 
	if fan_level < min_fan:
		fan_level = min_fan
	elif fan_level > 8:
		fan_level = 8
	if warm and fan_level > 6:
		fan_level = 6
	if cold:
		fan_level = 0
	if fan_prevlevel == fan_level:
		fan_duration += 1
	else:
		fan_duration = 0
	fan.set_level(fan_level)

	cpu_level = cpu.level
	if overtemp:
		if variability > 20000 and rise:
			cpu_level -= 20
		elif variability > 10000 and rise:
			cpu_level -= 10
		else:
			cpu_level -= 5
	elif cpu_level < target_cpu_level:
		cpu_level += 5

	if cpu_level > target_cpu_level:
		cpu_level = target_cpu_level
	elif cpu_level < 0:
		cpu_level = 0
	cpu.set_level(cpu_level)

	if extreme_temp:
		clamp_level += 10
	elif cpu_level <=75 and overtemp:
		clamp_level += 5
	elif not overtemp:
		clamp_level -= 5

	if clamp_level > max_clamp:
		clamp_level = max_clamp 
	if clamp_level < 0:
		clamp_level = 0
	
	clamp.set_level(clamp_level)
	clamp_list.append(clamp_level)
	if len(clamp_list) > variability_len:
		del(clamp_list[0])

	info("max_temp: %s, clamp %s, fan %s, cpu %s, var %s" % (max_temp, clamp_level, fan.level, cpu.level, variability))


	time.sleep(0.3)
	count += 1

# vim: ts=4 sw=4 noet

