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
import math
import os
import fnmatch
import re

class SearchEvent(observer.Event):
    '''
    Класс события, возникшего при поиске
    '''
    TYPE_FILE_FOUND = 1    #: Найден файл
    TYPE_NOTICE = 2        #: Возникла ошибка
    TYPE_END = 3        #: Поиск завершен успешно
    TYPE_ERROR = 4        #: Поиск завершен из-за фатальной ошибки
    
    type = None
    message = None
    files = None
    
    def __init__(self, type, arg=None):
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
    
    #additional
    textText = None
    textCaseSensitive = False
    textRegEx = False
    fileHidden = False

class SearchThread(threading.Thread, observer.Observable):
    '''
    Класс-тред поиска
    '''
    STATUS_STOPPED = 0
    STATUS_RUNNED = 1
    STATUS_PAUSED = 2

    locateResult = []    #: Файлы, найденные locate
    
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
    
    def isHidden(self, fileName, root=None):
        '''
        Метод проверяет, является ли файл/папка скрытым. 
        Он также возвращает True если хоть где-то в пути есть скрытая папка.
        :param fileName: Полный путь к файлу (можно и имя файла или относительный путь)
        :param root: Если задан параметр root, то в этом пути допускаются скрытые папки. В этот параметр нужно передать self.params.folder, 
                    чтобы можно было искать внутри скрытой папки если сама self.params.folder - скрытая. fileName в таком случае должен быть 
                    полным путем.
        '''
        if root:
            if not root.startswith('/') or (fileName.startwith('/') and not fileName.startwith(root)):
                return None
            if fileName.startwith('/'):
                fileName = fileName[len(root):]
        return fileName.find('/.') >= 0 or fileName.find('.') == 0
    
    def isTextExists(self, file):
        '''
        Ищет текст в файле
        '''
        if os.path.isdir(file):
            return False
        grepCommand = "grep --count --max-count=1 --no-messages " 
        if not self.params.textCaseSensitive:
            grepCommand = grepCommand + " --ignore-case "
        if self.params.textRegexCB:
            grepCommand = grepCommand + " --extended-regexp "
        grepCommand = grepCommand + "'" + self.params.textText + "' " + file
        print grepCommand
        grepResult = os.popen(grepCommand).read()
        if not grepResult or grepResult.splitlines()[0] != '1':
            return False
        else:
            return True
    def run(self):
        '''
        Метод запускатор треда
        '''
        print 'Start search'
        print self.params.folder + " " + str(self.params.fileType)
        self.status = self.STATUS_RUNNED
        self.notify_observers(SearchEvent(SearchEvent.TYPE_NOTICE, 'Search with locate command'))
        if self.params.fileName:
            files = self.locateSearch()
            if files:
                self.notify_observers(SearchEvent(SearchEvent.TYPE_FILE_FOUND, files))
        self.walkSearch()
        self.notify_observers(SearchEvent(SearchEvent.TYPE_END))
    
    def locateSearch(self):
        '''
        Поиск с помощью locate
        '''
        self.locateResult = []
        command = "locate --existing --follow --quiet "
        if not self.params.fileCaseSensitive:
            command = command + " --ignore-case "
        if self.params.fileRegEx:
            command = command + " --regex " + self.params.fileName
        elif self.params.fileExact:
            command = command + " --basename '\\" + self.params.fileName + "'"
        else:
            command = command + " " + self.params.fileName
        command = command +     "|egrep \"^" + self.params.folder + '"'
        print command
        result = os.popen(command).read()
        lines = result.splitlines()
        result = []
        for file in lines:
            if os.path.exists(file):
                if (not self.params.fileHidden) and self.isHidden(file):
                    continue
                if (self.params.fileType == self.params.FILE_TYPE_BOTH) or (self.params.fileType == self.params.FILE_TYPE_FOLDERS_ONLY and os.path.isdir(file)) or    (self.params.fileType == self.params.FILE_TYPE_FILES_ONLY and os.path.isfile(file)):
                    if self.params.textText and not self.isTextExists(file):
                        continue
                    self.locateResult.append(file)
        return self.locateResult
    
    def checkForPause(self):
        '''
        Проверям, не стоит ли поиск на паузе
        '''
        if (self.status == self.STATUS_PAUSED):
            while 1:
                if self.status != self.STATUS_PAUSED:
                    break
                time.sleep(1)
    
    def walkSearch(self):
        '''
        Поиск с помщью питона (os.walk)
        '''
        pattern = self.params.fileName
        if not self.params.fileRegEx and not self.params.fileExact:
            pattern = '*' + pattern + '*'
        result = []
        lastTime = time.time()
        for path, dirs, files in os.walk(self.params.folder):
            self.checkForPause()
            if(self.status == self.STATUS_STOPPED):
                break
            #Слишком часто вызывать notifyObservers не нужно.  К тому же почему-то программа падает при этом
            #Вызываем не чаще чем раз в секунду
            if round(time.time()) > lastTime:
                lastTime = round(time.time())
                self.notify_observers(SearchEvent(SearchEvent.TYPE_NOTICE, "Search in " + path + "..."))
            filesAndDirs = []
            if self.params.fileRegEx:
                prog = re.compile(pattern, re.IGNORECASE if not self.params.fileCaseSensitive else 0)
                for file in (files + dirs):
                    if prog.match(file):
                        filesAndDirs.append(file)
            else: # not RegEx
                if self.params.fileCaseSensitive:
                    filesAndDirs =     fnmatch.filter(files, pattern) + fnmatch.filter(dirs, pattern)
                else:
                    for n in files:
                        if fnmatch.fnmatch(n.lower(), pattern.lower()):
                            filesAndDirs.append(n)
                    for n in dirs:
                        if fnmatch.fnmatch(n.lower(), pattern.lower()):
                            filesAndDirs.append(n)
                
            for filename in filesAndDirs:
                self.checkForPause()
                if(self.status == self.STATUS_STOPPED):
                    break
                file = os.path.join(path, filename)
                if (not self.params.fileHidden) and self.isHidden(file) >= 0:
                    continue
                if file not in self.locateResult:
                    result.append(file)
                    self.notify_observers(SearchEvent(SearchEvent.TYPE_FILE_FOUND, [file]))
                print file
                    
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
        
