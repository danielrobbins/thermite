#!/usr/bin/python3

import os
import time
import glob
import sys

class Sensor(object):

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
			print("error writing")

	def _putint(self,path,i):
		try:
			f = open(path,'w')
			f.write(str(i))
			f.close()
		except OSError:
			print("error writing")

	def get(self):
		return self._getint(self.path)

class ThinkpadFan(Sensor):

	def __init__(self):
		self.level = 0
		self.max_level = 8
		self.set_level(3)
	
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

class PowerClamp(Sensor):

	def __init__(self):
		self.path = None
		for path in glob.glob('/sys/class/thermal/cooling_device*/'):
			if os.path.exists(path + '/type'):
				ty = getContents(path + '/type')
				if ty == 'intel_powerclamp':
					self.path = path + '/cur_state'
					break
		if self.path == None:
			print("Could not find intel_powerclamp cooling device. Make sure it is modprobed and enabled.")
			sys.exit(1)

	def get_level(self):
		return self._getint(self.path)

	def set_level(self,level):
		self._putint(self.path, level)

class Intel_PState(Sensor):
	
	base_path = '/sys/devices/system/cpu/intel_pstate'

	def __init__(self):

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

class CpuFrequencySettings(Sensor):
	

	def __init__(self):
		self.level = 0
		self.inc = 1
		base_path = '/sys/devices/system/cpu'
		self.min_freq = self._getint(base_path + '/cpu0/cpufreq/cpuinfo_min_freq')
		self.max_freq = self._getint(base_path + '/cpu0/cpufreq/cpuinfo_max_freq')
		print(self.max_freq)
		self.num_cpus = len(glob.glob(base_path + '/cpu[0-9]*'))
		f_avail_freq = base_path + '/cpu0/cpufreq/scaling_available_frequencies'
		if os.path.exists(f_avail_freq):
			self.avail_freq = self._getints(f_avail_freq)
			self.max_level = len(self.avail_freq)
		else:
			# get 
			self.max_level = 255 
			rng = self.max_freq - self.min_freq
			self.avail_freq = []
			for x in range(0,self.max_level):
				self.avail_freq.append(self.min_freq + (rng * x)//self.max_level)
			self.avail_freq.append(self.max_freq)

		self.set_level(0)
		self.going_up = True

	def set_level(self, level):
		freq = self.avail_freq[level]
		base_path = '/sys/devices/system/cpu/cpu'
		for x in range(0,self.num_cpus):
			self._putint(base_path + str(x) + '/cpufreq/scaling_max_freq', freq)
		print("set freq to level %s" % level)
		self.level = level

	def lower(self):
		if self.level == 0:
			return
		self.level -= 1
		self.set_level(self.level)

		#if self.going_up:
		#	# slow when we change direction
		#	self.going_up = False
		#	self.inc = 1
		#self.level = self.level - self.inc
		#self.inc = self.inc * 2
		#if self.level < 0:
		#	self.level = 0
		#	self.inc = 1
		#self.set_level(self.level)


	def max(self):
		if self.level == self.max_level:
			return
		self.level = self.max_level
		self.set_level(self.level)
		self.going_down = True
		self.inc = 1

	def upper(self):
		if self.level == self.max_level:
			return
		self.level += 1
		self.set_level(self.level)

		#if not self.going_up:
		#	self.going_up = True
		#	self.inc = 1
		#self.level = self.level + self.inc
		#self.inc = self.inc * 2
		#if self.level > self.max_level:
		#	self.level = self.max_level
		#self.set_level(self.level)

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

for dirpath in scanPath('/sys/class/thermal', prefixglob='thermal_zone*'):
	sensors.append({
		'name' : dirpath,
		'temp' : dirpath + '/temp'
	})

for dirpath in scanPath('/sys/class/hwmon', prefixglob='hwmon*'):
	temps = []
	for dirpath2 in scanPath(dirpath, prefixglob='temp*_input'):
		temps.append(dirpath2)
	sensors.append({
		'name' : getContents(dirpath + '/name'),
		'temp' : temps
	})

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

cpu = Intel_PState()
fan = ThinkpadFan()
clamp = PowerClamp()

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
	if max_temp < 49000:
		fan_targ = 0
	#elif max_temp > 39000 and max_temp < 42000:
	#	fan.set_level(1)
	#elif max_temp >= 42000 and max_temp < 45000:
	#	fan.set_level(2)
	elif max_temp >= 49000 and max_temp < 48000:
		fan_targ = 2
	elif max_temp >= 48000 and max_temp < 51000:
		fan_targ = 4
	elif max_temp >= 51000 and max_temp < 54000:
		fan_targ = 5
	elif max_temp >= 54000 and max_temp < 57000 and avg_temp <= 60000:
		fan_targ = 6
	elif avg_temp >= 57000 and max_temp < 60000 and avg_temp <= 63000:
		fan_targ = 7
	else:
		fan_targ = 8

	if variability < 1000 and fan_targ < 6:
		fan_targ -= 2
	elif variability < 3000 and fan_targ < 6:
		fan_targ -= 1
	if fan_targ < 0:
		fan_targ = 0
	fan.set_level(fan_targ)

	overtemp = False
	extreme_temp = False
	if (max_temp > 75000):
		overtemp = True
	if (max_temp > 80000):
		extreme_temp = True

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

	print("max_temp: %s, clamp %s, fan %s, cpu %s, var %s" % (max_temp, clamp_level, fan.level, cpu.level, variability))


	time.sleep(0.3)
	count += 1

# vim: ts=4 sw=4 noet

