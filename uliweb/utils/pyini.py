#! /usr/bin/env python
#coding=utf-8
# This module is used to parse and create new style ini file. This
# new style ini file format should like a very simple python program
# but you can define section like normal ini file, for example:
#
#    [default]
#    key = value
#
# Then the result should be ini.default.key1 = value1
# Whole ini file will be parsed into a dict-like object, but you can access
# each section and key with '.', just like ini.section.key
# For value can be simple python data type, such as: tuple, list, dict, int
# float, string, etc. So it's very like a normal python file, but it's has
# some sections definition.

import sys, os
import re
import codecs
import StringIO
import locale
import copy
import tokenize
import token
from sorteddict import SortedDict
from traceback import print_exc

__all__ = ['SortedDict', 'Section', 'Ini', 'uni_prt']

try:
    set
except:
    from sets import Set as set

try:
    defaultencoding = locale.getdefaultlocale()[1]
except:
    defaultencoding = None

if not defaultencoding:
    defaultencoding = 'UTF-8'
try:
    codecs.lookup(defaultencoding)
except:
    defaultencoding = 'UTF-8'

r_encoding = re.compile(r'\s*coding\s*[=:]\s*([-\w.]+)')
r_var = re.compile(ur'(?<!\{)\{\{([^\{].*?)(?<!\})\}\}(?!\})', re.U)
__default_env__ = {}

def set_env(env=None):
    global __default_env__
    
    __default_env__.update(env or {})

def merge_data(values, prev=None):
    if prev:
        _type = type(prev)
        
    for value in values:
        if not isinstance(value, (list, dict, set)):
            return values[-1]
        
        if prev and _type != type(value):
            raise ValueError("Value %r should be the same type as previous type %r" % (value, _type))
        
        if not prev:
            prev = value
            _type = type(prev)
            continue
        
        if isinstance(value, list):
            for x in value:
                if x not in prev:
                    prev.append(x)
        elif isinstance(value, dict):
            for k, v in value.items():
                if k not in prev:
                    prev[k] = v
                else:
                    prev[k] = merge_data([v], prev[k])
        else:
            prev.update(value)
            
    return prev

def uni_prt(a, encoding='utf-8', beautiful=False, indent=0, convertors=None):
    convertors = convertors or {}
    escapechars = [("\\", "\\\\"), ("'", r"\'"), ('\"', r'\"'), ('\b', r'\b'),
        ('\t', r"\t"), ('\r', r"\r"), ('\n', r"\n")]
    s = []
    indent_char = ' '*4
    if isinstance(a, (list, tuple)):
        if isinstance(a, list):
            s.append(indent_char*indent + '[')
        else:
            s.append(indent_char*indent + '(')
        if beautiful:
            s.append('\n')
        for i, k in enumerate(a):
            if beautiful:
                ind = indent + 1
            else:
                ind = indent
            s.append(indent_char*ind + uni_prt(k, encoding, beautiful, indent+1, convertors=convertors))
            if i<len(a)-1:
                if beautiful:
                    s.append(',\n')
                else:
                    s.append(', ')
        if beautiful:
            s.append('\n')
        if isinstance(a, list):
            s.append(indent_char*indent + ']')
        else:
            if len(a) == 1:
                s.append(',')
            s.append(indent_char*indent + ')')
    elif isinstance(a, dict):
        s.append(indent_char*indent + '{')
        if beautiful:
            s.append('\n')
        for i, k in enumerate(a.items()):
            key, value = k
            if beautiful:
                ind = indent + 1
            else:
                ind = indent
            s.append('%s: %s' % (indent_char*ind + uni_prt(key, encoding, beautiful, indent+1, convertors=convertors), uni_prt(value, encoding, beautiful, indent+1, convertors=convertors)))
            if i<len(a.items())-1:
                if beautiful:
                    s.append(',\n')
                else:
                    s.append(', ')
        if beautiful:
            s.append('\n')
        s.append(indent_char*indent + '}')
    elif isinstance(a, str):
        t = a
        for i in escapechars:
            t = t.replace(i[0], i[1])
        s.append("'%s'" % t)
    elif isinstance(a, unicode):
        t = a
        for i in escapechars:
            t = t.replace(i[0], i[1])
        try:
            s.append("u'%s'" % t.encode(encoding))
        except:
            print_exc()
    else:
        _type = type(a)
        c_func = convertors.get(_type)
        if c_func:
            s.append(c_func(a))
        else:
            s.append(str(a))
    return ''.join(s)

def eval_value(value, globals, locals, encoding):
    txt = '#coding=%s\n%s' % (encoding, value)
    result = eval(txt, dict(globals), dict(locals))
    
    #process {{format}}
    def sub_(m):
        txt = m.group(1).strip()
        try:
            v = eval_value(str(txt), globals, locals, encoding)
            _type = type(txt)
            if not isinstance(v, (str, unicode)):
                v = _type(v)
            elif not isinstance(v, _type):
                if _type is unicode:
                    v = unicode(v, encoding)
                else:
                    v = v.encode(encoding)
        except:
            print_exc()
            v = m.group()
        return v
    
    if isinstance(result, (str, unicode)):
        result = r_var.sub(sub_, result)
    return result
    
class Empty(object): pass
class EvalValue(object):
    def __init__(self, value, filename, lineno, line):
        self.value = value
        self.filename = filename
        self.lineno = lineno
        self.line = line
        
    def __str__(self):
        return self.value
    
    def __repr__(self):
        return self.__str__()
    
class Lazy(object):
    """
    Lazy class can be used to save multiple EvalValue or normal data type
    You can use add() funciton to add new value, it'll be sotred as a list, 
    just like:
        
        [EvalValue, int, str]
    """
    def __init__(self, key, globals, sec_name, encoding):
        self.key = key
        self.values = []
        self.globals = globals
        self.sec_name = sec_name
        self.encoding = encoding
        self.cached_value = Empty
        
    def eval(self, value):
        try:
            v = eval_value(value, self.globals, self.globals[self.sec_name], self.encoding)
            return v
        except Exception as e:
            print_exc()
            raise Exception("Converting value (%s) error" % value)
        
    def add(self, value, replace=False):
        if not replace:
            self.values.append(value)
        else:
            self.values = [value]
        
    def get(self):
        if self.cached_value is Empty:
            result = []
            for v in self.values:
                value = self.eval(v)
                if not isinstance(value, (list, dict, set)):
                    self.cached_value = self.eval(self.values[-1])
                    break
                else:
                    result.append(value)
            
            if result:
                self.cached_value = merge_data(result)
                
            #sync
            self.globals[self.sec_name][self.key] = self.cached_value
            
        return self.cached_value
    
class RawValue(object):
    def __init__(self, filename, lineno, text, replace_flag=''):
        self.filename = filename
        self.lineno = lineno
        self.text = text
        self.replace_flag = replace_flag
        
    def __str__(self):
        _length = 30
        if len(self.filename) > _length:
            filename = '...' + self.filename[(len(self.filename)-_length+3):]
        else:
            filename = self.filename
        return '%-30s:%04d' % (filename, self.lineno)
    
    def value(self):
        if self.replace_flag:
            op = ' <= '
        else:
            op = ' = '
        return "%s%s" % (op, self.text)
    
class Section(SortedDict):
    def __init__(self, name, comments=None, encoding=None, root=None, info=None):
        super(Section, self).__init__()
        self._root = root
        self._name = name
        self.add_comment(comments=comments)
        self._field_comments = {}
        self._field_flag = {}
        self._encoding = encoding
        self._info = info
        
        #sync
        if self._root and self._lazy:
            self._root._globals.setdefault(name, SortedDict())
         
    @property
    def _lazy(self):
        if self._root:
            return self._root._lazy
        else:
            return False
        
    def add(self, key, value, comments=None, replace=False):
        self.__setitem__(key, value, replace)
        self._field_flag[key] = replace
        self.add_comment(key, comments)
        
    def __setitem__(self, key, value, replace=False):
        if self._lazy:
            if not key in self or replace:
                v = Lazy(key, self._root._globals, self._name, self._encoding)
            else:
                v = self[key]
            v.add(value)
        else:
            v = value
            if not replace:
                v = merge_data([value], self.get(key))
                
        super(Section, self).__setitem__(key, v, append=replace)
    
    def add_comment(self, key=None, comments=None):
        comments = comments or []
        if not isinstance(comments, (tuple, list)):
            comments = [comments]
        if not key:
            self._comments = comments
        else:
            self._field_comments[key] = copy.copy(comments)
        
    def comment(self, key=None):
        if not key:
            return self._comments
        else:
            return self._field_comments.get(key, [])
    
    def del_comment(self, key=None):
        self.add_comment(key, None)
        
    def dumps(self, out, convertors=None):
        if self._comments:
            print >> out, '\n'.join(self._comments)
        if self._root and self._root._raw:
            print >> out, '%s [%s]' % (self._info, self._name)
        else:
            print >> out, '[%s]' % self._name
        for f in self.keys():
            comments = self.comment(f)
            if comments:
                print >> out, '\n'.join(comments)
            if self._root and self._root._raw:
                print >> out, "%s %s%s" % (str(self[f]), f, self[f].value())
            else:
                if self._field_flag.get(f, False):
                    op = ' <= '
                else:
                    op = ' = '
                buf = f + op + uni_prt(self[f], self._encoding, convertors=convertors)
                if len(buf) > 79:
                    buf = f + op + uni_prt(self[f], self._encoding, True, convertors=convertors)
                print >> out, buf
            
    def __delitem__(self, key):
        super(Section, self).__delitem__(key)
        self.del_comment(key)
        
    def __delattr__(self, key):
        try: 
            del self[key]
        except KeyError, k: 
            raise AttributeError, k
    
    def __str__(self):     
        buf = StringIO.StringIO()
        self.dumps(buf)
        return buf.getvalue()
    
class Ini(SortedDict):
    def __init__(self, inifile='', commentchar=None, encoding=None, 
        env=None, convertors=None, lazy=False, writable=False, raw=False):
        """
        lazy is used to parse first but not deal at time, and only when 
        the user invoke finish() function, it'll parse the data.
        """
        super(Ini, self).__init__()
        self._inifile = inifile
        self._commentchar = commentchar or __default_env__.get('commentchar', '#')
        self._encoding = encoding or __default_env__.get('encoding', 'utf-8')
        self._env = __default_env__.get('env', {}).copy()
        self._env.update(env or {})
        self._env['set'] = set
        self.update(self._env)
        self._globals = SortedDict()
        self._convertors = __default_env__.get('convertors', {}).copy()
        self._convertors.update(convertors or {})
        self._lazy = lazy
        self._writable = writable
        self._raw = raw
        
        if lazy:
            self._globals = self._env.copy()
            
        if self._inifile:
            self.read(self._inifile)
        
    def set_filename(self, filename):
        self._inifile = filename
        
    def get_filename(self):
        return self._inifile
    
    filename = property(get_filename, set_filename)
    
    def read(self, fobj, filename=''):
        encoding = None
        
        if isinstance(fobj, (str, unicode)):
            f = open(fobj, 'rb')
            text = f.read()
            f.close()
        else:
            text = fobj.read()
            
        text = text + '\n'
        begin = 0
        if text.startswith(codecs.BOM_UTF8):
            begin = 3
            encoding = 'UTF-8'
        elif text.startswith(codecs.BOM_UTF16):
            begin = 2
            encoding = 'UTF-16'
            
        if not encoding:
            try:
                unicode(text, 'UTF-8')
                encoding = 'UTF-8'
            except:
                encoding = defaultencoding
                
        self._encoding = encoding
        
        f = StringIO.StringIO(text)
        f.seek(begin)
        lineno = 0
        comments = []
        status = 'c'
        section = None
        while 1:
            lastpos = f.tell()
            line = f.readline()
            lineno += 1
            if not line:
                break
            line = line.strip()
            if line:
                if line.startswith(self._commentchar):
                    if lineno == 1: #first comment line
                        b = r_encoding.search(line[1:])
                        if b:
                            self._encoding = b.groups()[0]
                            continue
                    comments.append(line)
                elif line.startswith('[') and line.endswith(']'):
                    sec_name = line[1:-1].strip()
                    #process include notation
                    if sec_name.startswith('include:'):
                        _filename = sec_name[8:].strip()
                        _filename = os.path.abspath(_filename)
                        if os.path.exists(_filename):
                            old_encoding = self._encoding
                            self.read(_filename)
                            self._encoding = old_encoding
                        else:
                            import warnings
                            warnings.warn(Warning("Can't find the file [%s], so just skip it" % _filename), stacklevel=2)
                        continue
                    info = RawValue(self._inifile, lineno, sec_name)
                    section = self.add(sec_name, comments, info=info)
                    comments = []
                elif '=' in line:
                    if section is None:
                        raise Exception, "No section found, please define it first in %s file" % self.filename

                    #if find <=, then it'll replace the old value for mutable variables
                    #because the default behavior will merge list and dict
                    pos = line.find('<=')
                    if pos != -1:
                        begin, end = pos, pos+2
                        replace_flag = True
                    else:
                        pos = line.find('=')
                        begin, end = pos, pos+1
                        replace_flag = False
                        
                    keyname = line[:begin].strip()
                    #check keyname
                    if keyname in self._env:
                        raise KeyError("Settings key %s is alread defined in env, please change it's name" % keyname)
                    
                    rest = line[end:].strip()
                    #if key= then value will be set ''
                    if rest == '':
                        v = None
                    else:
                        f.seek(lastpos+end)
                        try:
                            value, iden_existed = self.__read_line(f)
                        except Exception, e:
                            print_exc()
                            raise Exception, "Parsing ini file error in %s:%d:%s" % (filename or self._inifile, lineno, line)
                        if self._lazy:
                            if iden_existed:
                                v = EvalValue(value, filename or self._inifile, lineno, line)
                            else:
                                v = value
                        else:
                            if self._raw:
                                v = RawValue(self._inifile, lineno, value, replace_flag)
                            else:
                                try:
                                    v = eval_value(value, self.env(), self[sec_name], self._encoding)
                                except Exception as e:
                                    print_exc()
                                    print dict(self)
                                    raise Exception("Converting value (%s) error in %s:%d:%s" % (value, filename or self._inifile, lineno, line))
                    section.add(keyname, v, comments, replace=replace_flag)
                    comments = []
            else:
                comments.append(line)
                
    def save(self, filename=None):
        if not filename:
            filename = self.filename
        if not filename:
            filename = sys.stdout
        if isinstance(filename, (str, unicode)):
            f = open(filename, 'wb')
            need_close = True
        else:
            f = filename
            need_close = False
        
        print >> f, '#coding=%s' % self._encoding
        for s in self.keys():
            if s in self._env:
                continue
            section = self[s]
            section.dumps(f, convertors=self._convertors)
            
        if need_close:
            f.close()

    def __read_line(self, f):
        """
        Get logic line according the syntax not the physical line
        It'll return the line text and if there is identifier existed
        
        return line, bool
        """
        g = tokenize.generate_tokens(f.readline)
        
        buf = []
        time = 0
        iden_existed = False
        while 1:
            v = g.next()
            tokentype, t, start, end, line = v
            if tokentype == 54:
                continue
            if tokentype in (token.INDENT, token.DEDENT, tokenize.COMMENT):
                continue
            if tokentype == token.NAME:
                iden_existed = True
            if tokentype == token.NEWLINE:
                return ''.join(buf), iden_existed
            else:
                if t == '=' and time == 0:
                    time += 1
                    continue
                buf.append(t)
    
    def __setitem__(self, key, value):
        if key not in self:
            super(Ini, self).__setitem__(key, value)
            
    def update(self, value):
        for k, v in value.items():
            self.set_var(k, v)

    def add(self, sec_name, comments=None, info=None):
        if sec_name in self:
            section = self[sec_name]
        else:
            section = Section(sec_name, comments, self._encoding, root=self, info=info)
            self[sec_name] = section
        return section
    
    def __str__(self):     
        buf = StringIO.StringIO()
        self.save(buf)
        return buf.getvalue()
    
    def get_var(self, key, default=None):
        obj = self
        for i in key.split('/', 1):
            obj = obj.get(i)
            if obj is None:
                break
          
        if obj is None:
            return default
        return obj
    
    def set_var(self, key, value):
        s = key.split('/', 1)
        obj = self
        for i in s[:-1]:
            obj = obj.add(i)
        obj[s[-1]] = value
        
        return True
        
    def del_var(self, key):
        s = key.split('/', 1)
        obj = self
        for i in s[:-1]:
            obj = obj.get(i)
            if obj is None:
                return False
        
        if s[-1] in obj:
            del obj[s[-1]]
            flag = True
        else:
            flag = False
        
        return flag
    
    def items(self):
        return ((k, self[k]) for k in self.keys() if not k in self._env)
    
    def env(self):
        return self
    
    def freeze(self):
        """
        Process all EvalValue to real value
        """
        self._lazy = False
        for k, v in self.items():
            if k in self._env:
                continue
            for _k, _v in v.items():
                if isinstance(_v, Lazy):
                    if self.writable:
                        _v.get()
                    else:
                        v.__setitem__(_k, _v.get(), replace=True)
                        del _v
        del self._globals