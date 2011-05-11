# -*- coding: utf-8 -*-
#
#       search_thread_class.py
#       
#       Copyright 2011 Sevka <sevka@ukr.net>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import threading
import observer
import time
import os

class SearchEvent(observer.Event):
	'''
	Класс события, возникшего при поиске
	'''
	TYPE_FILE_FOUND = 1	#: Найден файл
	TYPE_NOTICE = 2		#: Возникла ошибка
	TYPE_END = 3		#: Поиск завершен успешно
	TYPE_ERROR = 4		#: Поиск завершен из-за фатальной ошибки
	
	type = None
	message = None
	files = None
	
	def __init__(self, type, arg = None):
		'''
		Конструктор
		:param type: Тип события
		'''
		self.type = type
		if type == self.TYPE_FILE_FOUND:
			self.files = arg
		if type == self.TYPE_NOTICE:
			self.message = arg

class SearchParams():
	'''
	Класс - структура параметров поиска
	'''
	FILE_TYPE_BOTH = 0
	FILE_TYPE_FILES_ONLY = 1
	FILE_TYPE_FOLDERS_ONLY = 2

	folder = None
	folderRecursive = True
	
	fileName = None
	fileType = 0
	fileExact = False
	fileCaseSensitive = False
	fileRegEx = False
	

class SearchThread(threading.Thread,observer.Observable):
	'''
	Класс-тред поиска
	'''
	STATUS_STOPPED = 0
	STATUS_RUNNED = 1
	STATUS_PAUSED = 2
	
	status = 0
	params = None #: SearchParams
	
		
	def __init__(self, params):
		'''
		Конструктор
		:param params: Параметры поиска
		:type params: SearchParams 
		'''
		threading.Thread.__init__(self)
		observer.Observable.__init__(self)
		self.params = params
		
	def run(self):
		'''
		Метод запускатор треда
		'''
		print 'Start search'
		print self.params.folder + " " + str(self.params.fileType)
		self.status = self.STATUS_RUNNED
		self.notifyObservers(SearchEvent(SearchEvent.TYPE_NOTICE,'Search with locate command'))
		files = self.locateSearch()
		if files:
			self.notifyObservers(SearchEvent(SearchEvent.TYPE_FILE_FOUND,files))
		for i in range(5):
			e = SearchEvent(SearchEvent.TYPE_NOTICE)
			e.message = "Bla-bla-bla"
			self.notifyObservers(e)
			time.sleep(1)
			if (self.status == self.STATUS_PAUSED):
				while 1:
					if self.status != self.STATUS_PAUSED:
						break
					time.sleep(1)
			if(self.status == self.STATUS_STOPPED):
				break
		self.notifyObservers(SearchEvent(SearchEvent.TYPE_END))
	
	def locateSearch(self):
		'''
		Поиск с помощью locate
		'''
		# locate -b -i '\core'|egrep "^/home/sevka"
		command = "locate "
		if not self.params.fileCaseSensitive:
			command = command + "-i "
		if self.params.fileExact:
			command = command + " -b '\\" + self.params.fileName + "'"
		else:
			command = command + " " + self.params.fileName
		command = command +	"|egrep \"^" + self.params.folder + '"'
		result = os.popen(command).read()
		lines = result.splitlines()
		result = []
		for file in lines:
			if os.path.exists(file):
				if (self.params.fileType == self.params.FILE_TYPE_BOTH) or (self.params.fileType == self.params.FILE_TYPE_FOLDERS_ONLY and os.path.isdir(file)) or	(self.params.fileType == self.params.FILE_TYPE_FILES_ONLY and os.path.isfile(file)):
					result.append(file)
		return result
	
	def pause(self):
		'''
		Поставить поиск на паузу
		'''
		self.status = self.STATUS_PAUSED
				
	def contin(self):
		'''
		Продолжить поиск после паузы
		'''
		self.status = self.STATUS_RUNNED
	
	def stop(self):
		'''
		Остановить поиск
		'''
		self.status = self.STATUS_STOPPED
		
		
